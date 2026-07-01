"""
Service layer do módulo de Almoxarifado.

Toda lógica de negócio fica aqui — routers só delegam.
Regras:
  - Baixa atômica: movimento + saldo na mesma transação (db.flush antes de commit)
  - Saldo nunca negativo (salvo flag permitir_saldo_negativo na peça)
  - Custo médio ponderado recalculado a cada entrada
  - Ponto de pedido dispara notificação para admin/líder
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..models.estoque import Peca, Deposito, SaldoEstoque, MovimentoEstoque, TipoMovimento


class EstoqueError(Exception):
    """Erro de negócio do módulo de estoque (capturado pelo router → HTTP 422)."""
    def __init__(self, msg: str, status_code: int = 422):
        super().__init__(msg)
        self.status_code = status_code


def _get_or_create_saldo(db: Session, peca_id: str, deposito_id: str, org_id: str) -> SaldoEstoque:
    """Retorna SaldoEstoque existente ou cria com quantidade 0."""
    saldo = (
        db.query(SaldoEstoque)
        .filter(
            SaldoEstoque.peca_id == peca_id,
            SaldoEstoque.deposito_id == deposito_id,
        )
        .with_for_update()   # row-level lock para evitar race condition
        .first()
    )
    if saldo is None:
        saldo = SaldoEstoque(
            id=uuid.uuid4(),
            organization_id=org_id,
            peca_id=peca_id,
            deposito_id=deposito_id,
            quantidade=0,
        )
        db.add(saldo)
        db.flush()
    return saldo


def recalcular_custo_medio(db: Session, peca: Peca, deposito_id: str, org_id: str) -> Decimal:
    """
    Custo médio ponderado considerando todos os saldos em todos os depósitos
    com base nas últimas entradas.
    """
    # Soma qty * custo_unitario de todas as entradas da peça
    from sqlalchemy import func
    from sqlalchemy.orm import Query

    entradas = (
        db.query(MovimentoEstoque)
        .filter(
            MovimentoEstoque.peca_id == peca.id,
            MovimentoEstoque.organization_id == org_id,
            MovimentoEstoque.tipo == TipoMovimento.ENTRADA,
            MovimentoEstoque.custo_unitario.isnot(None),
        )
        .all()
    )

    if not entradas:
        return peca.custo_unitario or Decimal("0")

    total_valor = sum((e.custo_unitario or 0) * e.quantidade for e in entradas)
    total_qty = sum(e.quantidade for e in entradas)

    if total_qty == 0:
        return peca.custo_unitario or Decimal("0")

    return Decimal(str(total_valor / total_qty)).quantize(Decimal("0.0001"))


def registrar_entrada(
    db: Session,
    peca: Peca,
    deposito: Deposito,
    quantidade: float,
    custo_unitario: Decimal,
    usuario_id: str,
    org_id: str,
    motivo: Optional[str] = None,
    os_id: Optional[str] = None,
) -> MovimentoEstoque:
    """
    Registra uma entrada de estoque.
    Recalcula custo médio ponderado.
    Retorna o MovimentoEstoque criado (não commita — responsabilidade do caller).
    """
    if quantidade <= 0:
        raise EstoqueError("Quantidade deve ser maior que zero.")

    saldo = _get_or_create_saldo(db, str(peca.id), str(deposito.id), org_id)
    saldo.quantidade = (saldo.quantidade or 0) + quantidade
    saldo.atualizado_em = datetime.now(timezone.utc)

    custo_total = custo_unitario * Decimal(str(quantidade))

    mov = MovimentoEstoque(
        id=uuid.uuid4(),
        organization_id=org_id,
        peca_id=peca.id,
        deposito_id=deposito.id,
        tipo=TipoMovimento.ENTRADA,
        quantidade=quantidade,
        custo_unitario=custo_unitario,
        custo_total=custo_total,
        os_id=os_id,
        usuario_id=usuario_id,
        motivo=motivo,
        criado_em=datetime.now(timezone.utc),
    )
    db.add(mov)
    db.flush()

    # Atualiza custo médio ponderado na peça
    novo_custo_medio = recalcular_custo_medio(db, peca, str(deposito.id), org_id)
    peca.custo_medio = novo_custo_medio
    db.flush()

    return mov


def registrar_saida(
    db: Session,
    peca: Peca,
    deposito: Deposito,
    quantidade: float,
    usuario_id: str,
    org_id: str,
    motivo: Optional[str] = None,
    os_id: Optional[str] = None,
) -> tuple[MovimentoEstoque, SaldoEstoque]:
    """
    Registra uma saída de estoque (consumo em OS ou saída manual).
    Verifica saldo disponível.
    Retorna (MovimentoEstoque, SaldoEstoque atualizado).
    Não commita — responsabilidade do caller.
    """
    if quantidade <= 0:
        raise EstoqueError("Quantidade deve ser maior que zero.")

    saldo = _get_or_create_saldo(db, str(peca.id), str(deposito.id), org_id)
    saldo_atual = saldo.quantidade or 0

    if saldo_atual < quantidade and not peca.permitir_saldo_negativo:
        raise EstoqueError(
            f"Saldo insuficiente para '{peca.codigo} — {peca.descricao}': "
            f"disponível={saldo_atual:.2f} {peca.unidade}, solicitado={quantidade:.2f} {peca.unidade}.",
            status_code=422,
        )

    saldo.quantidade = saldo_atual - quantidade
    saldo.atualizado_em = datetime.now(timezone.utc)

    custo_unit = peca.custo_medio or peca.custo_unitario or Decimal("0")
    custo_total = custo_unit * Decimal(str(quantidade))

    mov = MovimentoEstoque(
        id=uuid.uuid4(),
        organization_id=org_id,
        peca_id=peca.id,
        deposito_id=deposito.id,
        tipo=TipoMovimento.SAIDA,
        quantidade=quantidade,
        custo_unitario=custo_unit,
        custo_total=custo_total,
        os_id=os_id,
        usuario_id=usuario_id,
        motivo=motivo,
        criado_em=datetime.now(timezone.utc),
    )
    db.add(mov)
    db.flush()

    return mov, saldo


def registrar_ajuste(
    db: Session,
    peca: Peca,
    deposito: Deposito,
    quantidade_nova: float,
    usuario_id: str,
    org_id: str,
    motivo: Optional[str] = None,
) -> MovimentoEstoque:
    """
    Ajuste de inventário: define o saldo para `quantidade_nova`.
    Registra a diferença como movimento de ajuste.
    """
    saldo = _get_or_create_saldo(db, str(peca.id), str(deposito.id), org_id)
    diferenca = quantidade_nova - (saldo.quantidade or 0)

    saldo.quantidade = quantidade_nova
    saldo.atualizado_em = datetime.now(timezone.utc)

    custo_unit = peca.custo_medio or peca.custo_unitario or Decimal("0")

    mov = MovimentoEstoque(
        id=uuid.uuid4(),
        organization_id=org_id,
        peca_id=peca.id,
        deposito_id=deposito.id,
        tipo=TipoMovimento.AJUSTE,
        quantidade=abs(diferenca),
        custo_unitario=custo_unit,
        custo_total=custo_unit * Decimal(str(abs(diferenca))),
        usuario_id=usuario_id,
        motivo=motivo or f"Ajuste de inventário: {saldo.quantidade - diferenca:.2f} → {quantidade_nova:.2f}",
        criado_em=datetime.now(timezone.utc),
    )
    db.add(mov)
    db.flush()

    return mov


def verificar_ponto_pedido(
    db: Session,
    peca: Peca,
    saldo_atual: float,
    org_id: str,
    criar_notif_fn,  # callable(db, org_id, dest_id, tipo, titulo, msg, os_id=None)
) -> bool:
    """
    Verifica se a peça está abaixo do ponto de pedido.
    Se estiver, cria notificações para todos os admin/líderes da org.
    Retorna True se abaixo do ponto.
    """
    if peca.ponto_pedido <= 0:
        return False
    if saldo_atual > peca.ponto_pedido:
        return False

    # Importa User aqui para não criar dependência circular no topo do módulo
    from sqlalchemy import or_
    try:
        from ..models.core import User, UserRole
    except ImportError:
        return True   # não conseguiu notificar, mas não bloqueia

    destinatarios = (
        db.query(User)
        .filter(
            User.organization_id == org_id,
            User.ativo == True,
            User.role.in_([
                UserRole.ADMIN, UserRole.LIDER,
                UserRole.SUPERVISOR_MANUTENCAO, UserRole.GERENTE_INDUSTRIAL,
            ]),
        )
        .all()
    )

    titulo = f"Estoque baixo: {peca.codigo}"
    msg = (
        f"Peça '{peca.descricao}' está com saldo {saldo_atual:.2f} {peca.unidade}, "
        f"abaixo do ponto de pedido ({peca.ponto_pedido:.2f} {peca.unidade}). "
        f"Lote econômico sugerido: {peca.lote_economico or '—'} {peca.unidade}."
    )

    for dest in destinatarios:
        try:
            criar_notif_fn(db, org_id, dest.id, "estoque_baixo", titulo, msg)
        except Exception:
            pass   # notificação é best-effort; não bloqueia a transação

    # Fase 3 — broadcast SSE dedicado para alerta de estoque
    try:
        from app.services.realtime import publish_sync
        publish_sync(str(org_id), "estoque_alerta", {
            "peca_id": str(peca.id),
            "peca_codigo": peca.codigo,
            "peca_nome": peca.descricao,
            "saldo": float(saldo_atual),
            "ponto_pedido": float(peca.ponto_pedido),
        })
    except Exception:
        pass

    return True


def saldo_total_peca(db: Session, peca_id: str, org_id: str) -> float:
    """Soma do saldo em todos os depósitos da org para uma peça."""
    saldos = (
        db.query(SaldoEstoque)
        .filter(
            SaldoEstoque.peca_id == peca_id,
            SaldoEstoque.organization_id == org_id,
        )
        .all()
    )
    return sum(s.quantidade or 0 for s in saldos)
