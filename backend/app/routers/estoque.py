"""
Router do módulo de Almoxarifado — Fase 1.

Todos os endpoints:
  - São tenant-scoped (organization_id do JWT)
  - Verificam feature flag modulo_estoque no plano da org
  - Role-gated conforme especificação

Prefixo registrado em server.py: /api (o router não tem prefix próprio).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.estoque import (
    Peca, Deposito, SaldoEstoque, MovimentoEstoque, Fornecedor, TipoMovimento,
)
from ..schemas.estoque import (
    FornecedorCreate, FornecedorUpdate, FornecedorResponse,
    PecaCreate, PecaUpdate, PecaResponse,
    DepositoCreate, DepositoUpdate, DepositoResponse,
    SaldoResponse, MovimentoCreate, MovimentoResponse,
    ConsumoOSCreate, ConsumoOSResponse,
)
from ..services.estoque_service import (
    registrar_entrada, registrar_saida, registrar_ajuste,
    verificar_ponto_pedido, saldo_total_peca, EstoqueError,
)

router = APIRouter(tags=["Almoxarifado"])


# ── Dependency stub — substituído em server.py via app.dependency_overrides ───

async def get_current_user_stub():
    """
    Placeholder para o dependency de autenticação.
    Substituído em server.py com:
        app.dependency_overrides[get_current_user_stub] = get_current_user
    """
    raise RuntimeError("get_current_user_stub não foi substituído via dependency_overrides.")


def _check_estoque_plano(user, db: Session) -> None:
    """
    Verifica se o plano da org suporta modulo_estoque.
    Levanta 402 se não suportar.
    """
    try:
        from ..models.core import Organization, PLAN_LIMITS
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        if org:
            limites = PLAN_LIMITS.get(org.plano, {})
            if not limites.get("modulo_estoque", False):
                plano_label = limites.get("label", org.plano.value if org.plano else "Demo")
                raise HTTPException(
                    status_code=402,
                    detail=(
                        f"O módulo de Almoxarifado não está disponível no plano {plano_label}. "
                        "Faça upgrade para o Profissional ou superior."
                    ),
                )
    except HTTPException:
        raise
    except Exception:
        pass   # se não conseguir verificar (testes), deixa passar


def _str_id(v) -> str:
    return str(v) if v else None


# ═══════════════════════════════════════════════════════════════════════════════
# FORNECEDORES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/fornecedores", response_model=list[FornecedorResponse])
async def listar_fornecedores(
    apenas_ativos: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),   # substituído em server.py
):
    _check_estoque_plano(user, db)
    q = db.query(Fornecedor).filter(Fornecedor.organization_id == user.organization_id)
    if apenas_ativos:
        q = q.filter(Fornecedor.ativo == True)
    items = q.order_by(Fornecedor.nome).all()
    return [
        FornecedorResponse(
            id=_str_id(f.id), organization_id=_str_id(f.organization_id),
            nome=f.nome, cnpj=f.cnpj, contato=f.contato, email=f.email,
            telefone=f.telefone, observacoes=f.observacoes, ativo=f.ativo,
            criado_em=f.criado_em,
        )
        for f in items
    ]


@router.post("/fornecedores", response_model=FornecedorResponse, status_code=201)
async def criar_fornecedor(
    data: FornecedorCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    _requer_roles(user, ["admin", "lider", "supervisor_manutencao", "gerente_industrial"])
    f = Fornecedor(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        nome=data.nome,
        cnpj=data.cnpj,
        contato=data.contato,
        email=data.email,
        telefone=data.telefone,
        observacoes=data.observacoes,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return FornecedorResponse(
        id=_str_id(f.id), organization_id=_str_id(f.organization_id),
        nome=f.nome, cnpj=f.cnpj, contato=f.contato, email=f.email,
        telefone=f.telefone, observacoes=f.observacoes, ativo=f.ativo,
        criado_em=f.criado_em,
    )


@router.put("/fornecedores/{forn_id}", response_model=FornecedorResponse)
async def atualizar_fornecedor(
    forn_id: str,
    data: FornecedorUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    _requer_roles(user, ["admin", "lider", "supervisor_manutencao", "gerente_industrial"])
    f = _get_fornecedor(db, forn_id, user.organization_id)
    for campo, val in data.model_dump(exclude_unset=True).items():
        setattr(f, campo, val)
    f.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    db.refresh(f)
    return FornecedorResponse(
        id=_str_id(f.id), organization_id=_str_id(f.organization_id),
        nome=f.nome, cnpj=f.cnpj, contato=f.contato, email=f.email,
        telefone=f.telefone, observacoes=f.observacoes, ativo=f.ativo,
        criado_em=f.criado_em,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PEÇAS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/pecas", response_model=list[PecaResponse])
async def listar_pecas(
    apenas_ativas: bool = True,
    fornecedor_id: Optional[str] = None,
    busca: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    q = db.query(Peca).filter(Peca.organization_id == user.organization_id)
    if apenas_ativas:
        q = q.filter(Peca.ativo == True)
    if fornecedor_id:
        q = q.filter(Peca.fornecedor_principal_id == fornecedor_id)
    if busca:
        like = f"%{busca}%"
        q = q.filter(Peca.codigo.ilike(like) | Peca.descricao.ilike(like))
    pecas = q.order_by(Peca.codigo).all()
    return [_build_peca_response(p, db, user.organization_id) for p in pecas]


@router.post("/pecas", response_model=PecaResponse, status_code=201)
async def criar_peca(
    data: PecaCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    _requer_roles(user, ["admin", "lider", "supervisor_manutencao", "gerente_industrial", "analista_manutencao"])

    existente = db.query(Peca).filter(
        Peca.organization_id == user.organization_id,
        Peca.codigo == data.codigo,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail=f"Já existe uma peça com código '{data.codigo}'.")

    if data.fornecedor_principal_id:
        _get_fornecedor(db, data.fornecedor_principal_id, user.organization_id)

    p = Peca(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        codigo=data.codigo,
        descricao=data.descricao,
        unidade=data.unidade,
        custo_unitario=data.custo_unitario,
        custo_medio=data.custo_unitario,   # custo médio inicial = custo unitário informado
        ponto_pedido=data.ponto_pedido,
        lote_economico=data.lote_economico,
        fornecedor_principal_id=data.fornecedor_principal_id,
        permitir_saldo_negativo=data.permitir_saldo_negativo,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _build_peca_response(p, db, user.organization_id)


@router.get("/pecas/{peca_id}", response_model=PecaResponse)
async def detalhar_peca(
    peca_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    p = _get_peca(db, peca_id, user.organization_id)
    return _build_peca_response(p, db, user.organization_id)


@router.put("/pecas/{peca_id}", response_model=PecaResponse)
async def atualizar_peca(
    peca_id: str,
    data: PecaUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    _requer_roles(user, ["admin", "lider", "supervisor_manutencao", "gerente_industrial", "analista_manutencao"])
    p = _get_peca(db, peca_id, user.organization_id)

    if data.fornecedor_principal_id is not None and data.fornecedor_principal_id:
        _get_fornecedor(db, data.fornecedor_principal_id, user.organization_id)

    for campo, val in data.model_dump(exclude_unset=True).items():
        setattr(p, campo, val)
    p.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    return _build_peca_response(p, db, user.organization_id)


@router.delete("/pecas/{peca_id}", status_code=204)
async def desativar_peca(
    peca_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    _requer_roles(user, ["admin", "gerente_industrial"])
    p = _get_peca(db, peca_id, user.organization_id)
    p.ativo = False
    p.atualizado_em = datetime.now(timezone.utc)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# DEPÓSITOS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/depositos", response_model=list[DepositoResponse])
async def listar_depositos(
    apenas_ativos: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    q = db.query(Deposito).filter(Deposito.organization_id == user.organization_id)
    if apenas_ativos:
        q = q.filter(Deposito.ativo == True)
    items = q.order_by(Deposito.nome).all()
    return [
        DepositoResponse(
            id=_str_id(d.id), organization_id=_str_id(d.organization_id),
            nome=d.nome, localizacao=d.localizacao, ativo=d.ativo, criado_em=d.criado_em,
        )
        for d in items
    ]


@router.post("/depositos", response_model=DepositoResponse, status_code=201)
async def criar_deposito(
    data: DepositoCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    _requer_roles(user, ["admin", "lider", "gerente_industrial"])
    d = Deposito(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        nome=data.nome,
        localizacao=data.localizacao,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return DepositoResponse(
        id=_str_id(d.id), organization_id=_str_id(d.organization_id),
        nome=d.nome, localizacao=d.localizacao, ativo=d.ativo, criado_em=d.criado_em,
    )


@router.put("/depositos/{dep_id}", response_model=DepositoResponse)
async def atualizar_deposito(
    dep_id: str,
    data: DepositoUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    _requer_roles(user, ["admin", "lider", "gerente_industrial"])
    d = _get_deposito(db, dep_id, user.organization_id)
    for campo, val in data.model_dump(exclude_unset=True).items():
        setattr(d, campo, val)
    db.commit()
    db.refresh(d)
    return DepositoResponse(
        id=_str_id(d.id), organization_id=_str_id(d.organization_id),
        nome=d.nome, localizacao=d.localizacao, ativo=d.ativo, criado_em=d.criado_em,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SALDOS DE ESTOQUE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/estoque/saldo", response_model=list[SaldoResponse])
async def listar_saldos(
    peca_id: Optional[str] = None,
    deposito_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    q = db.query(SaldoEstoque).filter(SaldoEstoque.organization_id == user.organization_id)
    if peca_id:
        q = q.filter(SaldoEstoque.peca_id == peca_id)
    if deposito_id:
        q = q.filter(SaldoEstoque.deposito_id == deposito_id)
    saldos = q.all()

    resultado = []
    for s in saldos:
        peca = s.peca
        dep = s.deposito
        if not peca or not dep:
            continue
        custo = peca.custo_medio or peca.custo_unitario or Decimal("0")
        resultado.append(
            SaldoResponse(
                peca_id=_str_id(s.peca_id),
                peca_codigo=peca.codigo,
                peca_descricao=peca.descricao,
                peca_unidade=peca.unidade,
                deposito_id=_str_id(s.deposito_id),
                deposito_nome=dep.nome,
                quantidade=s.quantidade or 0,
                custo_medio=custo,
                valor_total=custo * Decimal(str(s.quantidade or 0)),
                ponto_pedido=peca.ponto_pedido,
                abaixo_ponto_pedido=(s.quantidade or 0) <= peca.ponto_pedido and peca.ponto_pedido > 0,
                atualizado_em=s.atualizado_em or peca.criado_em,
            )
        )
    return resultado


@router.get("/estoque/abaixo-ponto-pedido", response_model=list[SaldoResponse])
async def listar_abaixo_ponto_pedido(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    saldos = db.query(SaldoEstoque).filter(
        SaldoEstoque.organization_id == user.organization_id,
    ).all()

    resultado = []
    for s in saldos:
        peca = s.peca
        dep = s.deposito
        if not peca or not dep or peca.ponto_pedido <= 0:
            continue
        if (s.quantidade or 0) <= peca.ponto_pedido:
            custo = peca.custo_medio or peca.custo_unitario or Decimal("0")
            resultado.append(
                SaldoResponse(
                    peca_id=_str_id(s.peca_id),
                    peca_codigo=peca.codigo,
                    peca_descricao=peca.descricao,
                    peca_unidade=peca.unidade,
                    deposito_id=_str_id(s.deposito_id),
                    deposito_nome=dep.nome,
                    quantidade=s.quantidade or 0,
                    custo_medio=custo,
                    valor_total=custo * Decimal(str(s.quantidade or 0)),
                    ponto_pedido=peca.ponto_pedido,
                    abaixo_ponto_pedido=True,
                    atualizado_em=s.atualizado_em or peca.criado_em,
                )
            )
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# MOVIMENTOS MANUAIS (entrada/ajuste)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/estoque/movimento", response_model=MovimentoResponse, status_code=201)
async def registrar_movimento(
    data: MovimentoCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    _requer_roles(user, ["admin", "lider", "supervisor_manutencao", "gerente_industrial", "analista_manutencao"])

    peca = _get_peca(db, data.peca_id, user.organization_id)
    deposito = _get_deposito(db, data.deposito_id, user.organization_id)

    try:
        if data.tipo == "entrada":
            mov = registrar_entrada(
                db, peca, deposito, data.quantidade,
                data.custo_unitario, str(user.id), str(user.organization_id), data.motivo,
            )
            db.commit()
        elif data.tipo == "saida":
            mov, saldo = registrar_saida(
                db, peca, deposito, data.quantidade,
                str(user.id), str(user.organization_id), data.motivo,
            )
            db.commit()
            _disparar_ponto_pedido(db, peca, saldo.quantidade, str(user.organization_id))
        else:   # ajuste
            mov = registrar_ajuste(
                db, peca, deposito, data.quantidade,
                str(user.id), str(user.organization_id), data.motivo,
            )
            db.commit()
            # Verifica ponto de pedido após ajuste
            saldo = db.query(SaldoEstoque).filter(
                SaldoEstoque.peca_id == peca.id,
                SaldoEstoque.deposito_id == deposito.id,
            ).first()
            if saldo:
                _disparar_ponto_pedido(db, peca, saldo.quantidade, str(user.organization_id))
    except EstoqueError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    return _build_movimento_response(mov, peca, deposito, user)


@router.get("/estoque/movimentos", response_model=list[MovimentoResponse])
async def listar_movimentos(
    peca_id: Optional[str] = None,
    deposito_id: Optional[str] = None,
    os_id: Optional[str] = None,
    tipo: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    q = db.query(MovimentoEstoque).filter(
        MovimentoEstoque.organization_id == user.organization_id,
    )
    if peca_id:
        q = q.filter(MovimentoEstoque.peca_id == peca_id)
    if deposito_id:
        q = q.filter(MovimentoEstoque.deposito_id == deposito_id)
    if os_id:
        q = q.filter(MovimentoEstoque.os_id == os_id)
    if tipo:
        q = q.filter(MovimentoEstoque.tipo == tipo)
    movs = q.order_by(MovimentoEstoque.criado_em.desc()).limit(limit).all()
    return [_build_movimento_response(m, m.peca, m.deposito, user) for m in movs]


# ═══════════════════════════════════════════════════════════════════════════════
# CONSUMO EM OS  (endpoint primário: POST /ordens-servico/{os_id}/pecas)
# Registrado separadamente em server.py para ter acesso ao model OrdemServico
# ═══════════════════════════════════════════════════════════════════════════════

# Este endpoint é definido em server.py (acesso ao OrdemServico) e
# chama os services deste módulo. Ver server.py: POST /ordens-servico/{os_id}/pecas


# ═══════════════════════════════════════════════════════════════════════════════
# RELATÓRIO: CONSUMO POR EQUIPAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/relatorios/consumo-por-equipamento")
async def consumo_por_equipamento(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_stub),
):
    _check_estoque_plano(user, db)
    from sqlalchemy import func

    q = db.query(MovimentoEstoque).filter(
        MovimentoEstoque.organization_id == user.organization_id,
        MovimentoEstoque.tipo == TipoMovimento.SAIDA,
        MovimentoEstoque.os_id.isnot(None),
    )
    if data_inicio:
        q = q.filter(MovimentoEstoque.criado_em >= data_inicio)
    if data_fim:
        q = q.filter(MovimentoEstoque.criado_em <= data_fim)

    movs = q.all()

    # Agrupa por equipamento via OS
    por_equipamento: dict = {}
    for m in movs:
        try:
            from ..models.core import OrdemServico, Equipamento
            os_obj = db.query(OrdemServico).filter(OrdemServico.id == m.os_id).first()
            if not os_obj:
                continue
            eq_id = str(os_obj.equipamento_id) if os_obj.equipamento_id else "sem_equipamento"
            eq_nome = os_obj.equipamento_nome if hasattr(os_obj, "equipamento_nome") else eq_id
        except Exception:
            eq_id = str(m.os_id)
            eq_nome = "OS " + str(m.os_id)[:8]

        if eq_id not in por_equipamento:
            por_equipamento[eq_id] = {
                "equipamento_id": eq_id,
                "equipamento_nome": eq_nome,
                "total_pecas": 0,
                "custo_total": Decimal("0"),
            }
        por_equipamento[eq_id]["total_pecas"] += 1
        por_equipamento[eq_id]["custo_total"] += m.custo_total or Decimal("0")

    return sorted(por_equipamento.values(), key=lambda x: x["custo_total"], reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════════════════════

def _requer_roles(user, roles: list[str]) -> None:
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role_val not in roles:
        raise HTTPException(status_code=403, detail="Sem permissão para esta operação.")


def _get_peca(db: Session, peca_id: str, org_id) -> Peca:
    p = db.query(Peca).filter(
        Peca.id == peca_id,
        Peca.organization_id == org_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Peça não encontrada.")
    return p


def _get_deposito(db: Session, dep_id: str, org_id) -> Deposito:
    d = db.query(Deposito).filter(
        Deposito.id == dep_id,
        Deposito.organization_id == org_id,
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Depósito não encontrado.")
    return d


def _get_fornecedor(db: Session, forn_id: str, org_id) -> Fornecedor:
    f = db.query(Fornecedor).filter(
        Fornecedor.id == forn_id,
        Fornecedor.organization_id == org_id,
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    return f


def _build_peca_response(p: Peca, db: Session, org_id) -> PecaResponse:
    saldo = saldo_total_peca(db, str(p.id), str(org_id))
    forn_nome = None
    if p.fornecedor_principal_id and p.fornecedor_principal:
        forn_nome = p.fornecedor_principal.nome
    return PecaResponse(
        id=_str_id(p.id),
        organization_id=_str_id(p.organization_id),
        codigo=p.codigo,
        descricao=p.descricao,
        unidade=p.unidade,
        custo_unitario=p.custo_unitario or Decimal("0"),
        custo_medio=p.custo_medio or Decimal("0"),
        ponto_pedido=p.ponto_pedido or 0,
        lote_economico=p.lote_economico,
        fornecedor_principal_id=_str_id(p.fornecedor_principal_id),
        fornecedor_nome=forn_nome,
        ativo=p.ativo,
        permitir_saldo_negativo=p.permitir_saldo_negativo,
        criado_em=p.criado_em,
        saldo_total=saldo,
        abaixo_ponto_pedido=saldo <= p.ponto_pedido and p.ponto_pedido > 0,
    )


def _build_movimento_response(mov: MovimentoEstoque, peca, deposito, user) -> MovimentoResponse:
    return MovimentoResponse(
        id=_str_id(mov.id),
        organization_id=_str_id(mov.organization_id),
        peca_id=_str_id(mov.peca_id),
        peca_codigo=peca.codigo if peca else "",
        peca_descricao=peca.descricao if peca else "",
        deposito_id=_str_id(mov.deposito_id),
        deposito_nome=deposito.nome if deposito else "",
        tipo=mov.tipo.value if hasattr(mov.tipo, "value") else str(mov.tipo),
        quantidade=mov.quantidade,
        custo_unitario=mov.custo_unitario,
        custo_total=mov.custo_total,
        os_id=_str_id(mov.os_id),
        usuario_id=_str_id(mov.usuario_id),
        motivo=mov.motivo,
        criado_em=mov.criado_em,
    )


def _disparar_ponto_pedido(db: Session, peca: Peca, saldo_atual: float, org_id: str) -> None:
    try:
        from ..deps import criar_notificacao
        verificar_ponto_pedido(db, peca, saldo_atual, org_id, criar_notificacao)
    except Exception:
        pass   # notificação é best-effort
