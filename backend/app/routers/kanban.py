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

router = APIRouter(tags=["Kanban"])


@router.get("/kanban")
async def get_kanban(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna OS agrupadas por status para o board Kanban — cards enriquecidos."""
    import json as _json

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "kanban")

    query = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.status != StatusOS.FECHADA,
    )
    # Operador vê apenas o próprio setor
    if user.role == UserRole.OPERADOR and user.setor:
        from sqlalchemy import text as _sa_text_k
        rows = db.execute(
            _sa_text_k("SELECT id FROM equipamentos WHERE organization_id = :org AND setor = :setor AND ativo = TRUE"),
            {"org": str(user.organization_id), "setor": user.setor},
        ).fetchall()
        equip_ids_setor = [r[0] for r in rows]
        query = query.filter(OrdemServico.equipamento_id.in_(equip_ids_setor))
    ordens = query.order_by(OrdemServico.created_at.desc()).all()

    # Build lookup maps
    eq_map = {str(e.id): e for e in db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id).all()}
    user_obj_map = {str(u.id): u for u in db.query(User).filter(
        User.organization_id == user.organization_id).all()}
    grupo_map = {str(g.id): g.nome for g in db.query(Grupo).filter(
        Grupo.organization_id == user.organization_id).all()}

    column_ids = [
        StatusOS.ABERTA.value,
        StatusOS.EM_ATENDIMENTO.value,
        StatusOS.AGUARDANDO_PECA.value,
        StatusOS.AGUARDANDO_REVISAO.value,
        StatusOS.REVISADA.value,
    ]
    columns = {s: [] for s in column_ids}

    for o in ordens:
        col = o.status.value
        if col not in columns:
            continue

        equip = eq_map.get(str(o.equipamento_id))
        tecnico_obj = user_obj_map.get(str(o.tecnico_id)) if o.tecnico_id else None
        solicitante_obj = user_obj_map.get(str(o.solicitante_id)) if o.solicitante_id else None

        # occurrences count
        try:
            occ_list = _json.loads(o.occurrences) if getattr(o, "occurrences", None) else []
        except Exception:
            occ_list = []

        columns[col].append({
            "id": str(o.id),
            "numero": o.numero,
            # Equipamento enriquecido
            "equipamento": equip.nome if equip else "—",
            "equipamento_codigo": equip.codigo if equip else None,
            "equipamento_localizacao": equip.localizacao if equip else None,
            # Grupo de equipamento (classificação) e grupo de falha (novo)
            "grupo_id": str(o.grupo_id) if o.grupo_id else None,
            "grupo_nome": grupo_map.get(str(o.grupo_id)) if o.grupo_id else None,
            "failure_group": getattr(o, "failure_group", None),
            # Tipo e prioridade
            "tipo": o.tipo.value,
            "prioridade": o.prioridade.value,
            # Pessoas
            "solicitante": solicitante_obj.nome if solicitante_obj else None,
            "solicitante_role": solicitante_obj.role.value if solicitante_obj else None,
            "tecnico": tecnico_obj.nome if tecnico_obj else None,
            "tecnico_employee_id": getattr(o, "technician_employee_id", None) or (tecnico_obj.employee_id if tecnico_obj else None),
            # Descricao
            "descricao": (o.descricao or "")[:100],
            # Timestamps
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "inicio_atendimento": o.inicio_atendimento.isoformat() if o.inicio_atendimento else None,
            "downtime_start": ((getattr(o, "downtime_start", None) or o.created_at).isoformat() if (getattr(o, "downtime_start", None) or o.created_at) else None),
            # SLA
            "dentro_sla": o.dentro_sla,
            "tempo_resposta": o.tempo_resposta,
            # Extras
            "reincidente": o.reincidente,
            "occurrences_count": len(occ_list),
        })

    return {
        "columns": [
            {"id": "aberta",             "label": "Aberto",           "cards": columns["aberta"]},
            {"id": "em_atendimento",     "label": "Em Atendimento",   "cards": columns["em_atendimento"]},
            {"id": "aguardando_peca",    "label": "Aguardando Peça",  "cards": columns["aguardando_peca"]},
            {"id": "aguardando_revisao", "label": "Ag. Revisão",      "cards": columns["aguardando_revisao"]},
            {"id": "revisada",           "label": "Revisada",         "cards": columns["revisada"]},
        ]
    }


# ========== SUPERUSUÁRIO — PORTAL DE GESTÃO DE EMPRESAS ==========

def _require_superuser(user: User):
    if user.role != UserRole.SUPERUSUARIO:
        raise HTTPException(status_code=403, detail="Acesso exclusivo do Superusuário.")
