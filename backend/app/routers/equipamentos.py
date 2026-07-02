from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from sqlalchemy.orm import Session

from ..deps import (
    get_db, get_current_user, check_plan_limit, check_plan_feature,
    criar_notificacao, create_audit_log, send_email_notification,
    hash_password, verify_password, create_access_token, create_refresh_token,
    set_auth_cookies, get_jwt_secret, get_org_usage, get_next_os_number,
    check_brute_force, record_failed_attempt, clear_failed_attempts,
    JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    SMTP_HOST, SMTP_USER,
)
from ..models.core import (
    Organization, User, Grupo, Subgrupo, Equipamento, OrdemServico,
    CustoOS, Setor, PlanoPreventivo, AuditoriaLog, LoginAttempt,
    PasswordResetToken, PaymentTransaction, OSEquipe, Colaborador,
    OSHistorico, OSExcecaoArea, Notificacao, ConfiguracaoMonitoramento,
    LeituraSensor, AlertaPreditivo,
    UserRole, TipoOS, PrioridadeOS, StatusOS, TipoCusto, PlanoSaaS, PLAN_LIMITS,
)
from ..schemas.main import (
    OrganizationCreate, OrganizationResponse,
    UserRegister, UserLogin, UserResponse, UserCreate,
    TechnicianSessionRequest, TecnicoLoginRequest,
    SetorCreate, SetorResponse, GrupoCreate, GrupoResponse,
    SubgrupoCreate, SubgrupoResponse,
    EquipamentoCreate, EquipamentoResponse,
    OSCreate, OSUpdate, OSResponse, OSEquipeCreate, OSEquipeResponse,
    OSHistoricoResponse, OSExcecaoAreaResponse, CustoMaoObraUpdate,
    CustoCreate, CustoResponse, PlanoCreate, PlanoResponse,
    DashboardKPIs, BillingPlanResponse, CheckoutRequest,
    ColaboradorCreate, ColaboradorUpdate, ColaboradorResponse,
)
from ..settings import settings
import jwt as _jwt

router = APIRouter(tags=["Equipamentos"])


@router.get("/equipamentos", response_model=List[EquipamentoResponse])
async def list_equipamentos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    equipamentos = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id,
        Equipamento.ativo == True
    ).all()
    return [EquipamentoResponse(
        id=str(e.id), codigo=e.codigo, nome=e.nome, descricao=e.descricao,
        localizacao=e.localizacao, valor_hora=e.valor_hora,
        grupo_id=str(e.grupo_id) if e.grupo_id else None,
        subgrupo_id=str(e.subgrupo_id) if e.subgrupo_id else None,
        criticidade=e.criticidade, ativo=e.ativo,
        organization_id=str(e.organization_id), created_at=e.created_at,
        parent_id=str(e.parent_id) if getattr(e, "parent_id", None) else None,
        nivel=getattr(e, "nivel", "maquina"),
    ) for e in equipamentos]

@router.get("/equipamentos/arvore")
async def get_equipamentos_arvore(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retorna hierarquia de equipamentos em árvore com métricas agregadas.
    Cada nó inclui MTTR, MTBF e custo total das OS dos filhos (transitivamente).
    """
    from sqlalchemy import func as _func

    all_equips = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id,
        Equipamento.ativo == True,
    ).all()

    # Pré-calcula métricas por equipamento (OS fechadas + revisadas)
    _os_q = db.query(
        OrdemServico.equipamento_id,
        _func.avg(OrdemServico.tempo_reparo).label("mttr"),
        _func.count(OrdemServico.id).label("total_os"),
    ).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.status.in_([StatusOS.FECHADA, StatusOS.REVISADA]),
    ).group_by(OrdemServico.equipamento_id).all()

    _custo_q = db.query(
        OrdemServico.equipamento_id,
        _func.sum(CustoOS.valor * CustoOS.quantidade).label("custo_total"),
    ).join(CustoOS, CustoOS.ordem_servico_id == OrdemServico.id).filter(
        OrdemServico.organization_id == user.organization_id,
    ).group_by(OrdemServico.equipamento_id).all()

    _metricas: dict = {}
    for row in _os_q:
        eid = str(row.equipamento_id)
        _metricas.setdefault(eid, {})["mttr_minutos"] = round(float(row.mttr or 0), 1)
        _metricas.setdefault(eid, {})["total_os"] = int(row.total_os)
    for row in _custo_q:
        eid = str(row.equipamento_id)
        _metricas.setdefault(eid, {})["custo_total"] = round(float(row.custo_total or 0), 2)

    def _build_node(equip) -> dict:
        eid = str(equip.id)
        m = _metricas.get(eid, {})
        children = [_build_node(c) for c in all_equips if str(getattr(c, "parent_id", None)) == eid]
        # Agrega métricas dos filhos recursivamente
        custo_filho = sum(c.get("metricas", {}).get("custo_total", 0) + c.get("metricas", {}).get("custo_filhos", 0) for c in children)
        os_filho = sum(c.get("metricas", {}).get("total_os", 0) + c.get("metricas", {}).get("os_filhos", 0) for c in children)
        return {
            "id": eid,
            "codigo": equip.codigo,
            "nome": equip.nome,
            "nivel": getattr(equip, "nivel", "maquina") or "maquina",
            "localizacao": equip.localizacao,
            "criticidade": equip.criticidade,
            "metricas": {
                "mttr_minutos": m.get("mttr_minutos", 0),
                "custo_total": m.get("custo_total", 0),
                "total_os": m.get("total_os", 0),
                # inclui filhos para drill-down
                "custo_filhos": custo_filho,
                "os_filhos": os_filho,
                "custo_agregado": round(m.get("custo_total", 0) + custo_filho, 2),
                "os_agregado": m.get("total_os", 0) + os_filho,
            },
            "filhos": children,
        }

    # Raízes: equipamentos sem pai (ou pai fora da mesma org)
    raizes = [e for e in all_equips if not getattr(e, "parent_id", None)]
    return [_build_node(r) for r in raizes]

@router.post("/equipamentos", response_model=EquipamentoResponse)
async def create_equipamento(data: EquipamentoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Check plan limit
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    allowed, msg = check_plan_limit(db, org, "equipamentos")
    if not allowed:
        raise HTTPException(status_code=402, detail=msg)
    
    # Fase 3: validar parent_id pertence à mesma org
    _parent_id = None
    if getattr(data, "parent_id", None):
        _parent = db.query(Equipamento).filter(
            Equipamento.id == data.parent_id,
            Equipamento.organization_id == user.organization_id,
        ).first()
        if not _parent:
            raise HTTPException(status_code=404, detail="Equipamento pai não encontrado.")
        _parent_id = _parent.id

    equipamento = Equipamento(
        codigo=data.codigo, nome=data.nome, descricao=data.descricao,
        localizacao=data.localizacao, valor_hora=data.valor_hora,
        grupo_id=data.grupo_id, subgrupo_id=data.subgrupo_id,
        criticidade=data.criticidade, organization_id=user.organization_id,
        parent_id=_parent_id, nivel=getattr(data, "nivel", "maquina") or "maquina",
    )
    db.add(equipamento)
    db.commit()
    db.refresh(equipamento)
    
    create_audit_log(db, str(user.organization_id), str(user.id), "equipamento", str(equipamento.id), "create")
    
    return EquipamentoResponse(
        id=str(equipamento.id), codigo=equipamento.codigo, nome=equipamento.nome,
        descricao=equipamento.descricao, localizacao=equipamento.localizacao,
        valor_hora=equipamento.valor_hora,
        grupo_id=str(equipamento.grupo_id) if equipamento.grupo_id else None,
        subgrupo_id=str(equipamento.subgrupo_id) if equipamento.subgrupo_id else None,
        criticidade=equipamento.criticidade, ativo=equipamento.ativo,
        organization_id=str(equipamento.organization_id), created_at=equipamento.created_at
    )

@router.get("/equipamentos/{equipamento_id}", response_model=EquipamentoResponse)
async def get_equipamento(equipamento_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    return EquipamentoResponse(
        id=str(equipamento.id), codigo=equipamento.codigo, nome=equipamento.nome,
        descricao=equipamento.descricao, localizacao=equipamento.localizacao,
        valor_hora=equipamento.valor_hora,
        grupo_id=str(equipamento.grupo_id) if equipamento.grupo_id else None,
        subgrupo_id=str(equipamento.subgrupo_id) if equipamento.subgrupo_id else None,
        criticidade=equipamento.criticidade, ativo=equipamento.ativo,
        organization_id=str(equipamento.organization_id), created_at=equipamento.created_at
    )

@router.put("/equipamentos/{equipamento_id}", response_model=EquipamentoResponse)
async def update_equipamento(equipamento_id: str, data: EquipamentoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.GERENTE_INDUSTRIAL, UserRole.SUPERVISOR_MANUTENCAO]:
        raise HTTPException(status_code=403, detail="Acesso negado")

    equipamento = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")

    import json as _json_eq
    _tracked = ["nome", "descricao", "localizacao", "valor_hora", "grupo_id", "subgrupo_id", "criticidade"]
    antes = {k: str(getattr(equipamento, k)) if getattr(equipamento, k) is not None else None for k in _tracked}

    for key, value in data.model_dump().items():
        setattr(equipamento, key, value)

    db.commit()
    db.refresh(equipamento)

    depois = {k: str(getattr(equipamento, k)) if getattr(equipamento, k) is not None else None for k in _tracked}
    alterados = {k: {"anterior": antes[k], "novo": depois[k]} for k in _tracked if antes[k] != depois[k]}

    create_audit_log(
        db, str(user.organization_id), str(user.id), "equipamento", str(equipamento.id), "update",
        dados_anteriores=_json_eq.dumps(antes, ensure_ascii=False),
        dados_novos=_json_eq.dumps({"alterados": alterados}, ensure_ascii=False),
    )

    return EquipamentoResponse(
        id=str(equipamento.id), codigo=equipamento.codigo, nome=equipamento.nome,
        descricao=equipamento.descricao, localizacao=equipamento.localizacao,
        valor_hora=equipamento.valor_hora,
        grupo_id=str(equipamento.grupo_id) if equipamento.grupo_id else None,
        subgrupo_id=str(equipamento.subgrupo_id) if equipamento.subgrupo_id else None,
        criticidade=equipamento.criticidade, ativo=equipamento.ativo,
        organization_id=str(equipamento.organization_id), created_at=equipamento.created_at
    )

@router.delete("/equipamentos/{equipamento_id}")
async def delete_equipamento(equipamento_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores podem excluir equipamentos.")

    equipamento = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")

    # Bloqueia exclusão se houver OS em aberto
    os_ativas = db.query(OrdemServico).filter(
        OrdemServico.equipamento_id == equipamento_id,
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.status != StatusOS.FECHADA,
    ).all()
    if os_ativas:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "equipamento_com_os_ativa",
                "message": f"Não é possível excluir. Este equipamento possui {len(os_ativas)} OS em aberto.",
                "os_ativas": [{"id": str(o.id), "numero": o.numero, "status": o.status} for o in os_ativas],
            },
        )

    import json as _json_del
    equipamento.ativo = False
    db.commit()

    create_audit_log(
        db, str(user.organization_id), str(user.id), "equipamento", str(equipamento.id), "delete",
        dados_novos=_json_del.dumps({"motivo": "exclusao_admin", "soft_delete": True}, ensure_ascii=False),
    )

    return {"message": "Equipamento excluído com sucesso"}

# ========== ORDENS DE SERVIÇO ENDPOINTS ==========

@router.get("/equipamentos/{equipamento_id}/historico")
async def get_equipamento_historico(equipamento_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Timeline completa de um equipamento"""
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    
    # OS do equipamento
    ordens = db.query(OrdemServico).filter(
        OrdemServico.equipamento_id == equipamento_id
    ).order_by(OrdemServico.created_at.desc()).all()
    
    # Custos totais
    total_custos = 0
    for o in ordens:
        custos = db.query(CustoOS).filter(CustoOS.ordem_servico_id == o.id).all()
        total_custos += sum(c.valor * c.quantidade for c in custos)
    
    # Tempo total parado
    tempo_total_parado = sum(o.tempo_total or 0 for o in ordens) / 60  # em horas
    custo_parada_total = tempo_total_parado * equipamento.valor_hora
    
    return {
        "equipamento": {
            "id": str(equipamento.id),
            "codigo": equipamento.codigo,
            "nome": equipamento.nome,
            "valor_hora": equipamento.valor_hora
        },
        "estatisticas": {
            "total_os": len(ordens),
            "corretivas": len([o for o in ordens if o.tipo == TipoOS.CORRETIVA]),
            "preventivas": len([o for o in ordens if o.tipo == TipoOS.PREVENTIVA]),
            "custo_total": round(total_custos, 2),
            "custo_parada_total": round(custo_parada_total, 2),
            "tempo_total_parado_horas": round(tempo_total_parado, 2)
        },
        "ordens": [{
            "id": str(o.id),
            "numero": o.numero,
            "tipo": o.tipo.value,
            "status": o.status.value,
            "descricao": o.descricao,
            "custo_parada": round(((o.tempo_total or 0) / 60) * equipamento.valor_hora, 2) if o.tempo_total and equipamento.valor_hora else None,
            "created_at": o.created_at.isoformat()
        } for o in ordens[:20]]
    }
