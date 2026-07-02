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

router = APIRouter(tags=["Organização"])


@router.get("/organization")
async def get_organization(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current organization details"""
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    usage = get_org_usage(db, org.id)
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])

    feature_labels = {
        "relatorios": "Relatórios avançados",
        "dashboard_avancado": "Dashboard avançado",
        "kanban": "Kanban de OS",
        "modulo_preditivo": "Análise preditiva",
        "planos_preventivos": "Manutenção preventiva",
        "aprovacao_setor": "Aprovação por setor",
        "notificacoes_email": "Notificações por e-mail",
        "exportacao_pdf": "Exportação PDF",
        "api_iot": "API IoT / Webhooks",
        "sso": "SSO / Login único",
        "grupos_subgrupos": "Grupos e subgrupos",
    }
    features_list = [label for key, label in feature_labels.items() if limits.get(key)]

    return {
        "id": str(org.id),
        "nome": org.nome,
        "cnpj": org.cnpj,
        "plano": org.plano.value,
        "subscription_status": org.subscription_status,
        "ativo": org.ativo,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "limits": {
            "max_equipamentos": limits["max_equipamentos"],
            "max_users": limits["max_users"],
            "max_os_mes": limits["max_os_mes"],
        },
        "usage": usage,
        "features": features_list,
        "plan_features": limits,
        "has_api_key": bool(org.api_key),
        "api_key_preview": (org.api_key[:12] + "..." if org.api_key else None),
    }

@router.put("/organization")
async def update_organization(data: OrganizationUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update organization details (admin only)"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode editar a organização")
    
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    if data.nome:
        org.nome = data.nome
    if data.cnpj is not None:
        org.cnpj = data.cnpj
    
    db.commit()
    db.refresh(org)
    
    create_audit_log(db, str(user.organization_id), str(user.id), "organization", str(org.id), "update")
    
    return {"message": "Organização atualizada", "nome": org.nome}

# ========== API KEY MANAGEMENT ==========

@router.post("/organization/generate-api-key")
@limiter.limit(LIMIT_APIKEY)
async def generate_api_key(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate (or regenerate) API key for the organization. Admin only."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode gerenciar API keys")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    _require_feature(org, "api_iot")
    new_key = "aurix_" + secrets.token_hex(28)
    org.api_key = new_key
    db.commit()
    create_audit_log(db, str(user.organization_id), str(user.id), "organization", str(org.id), "generate_api_key")
    return {"api_key": new_key}

@router.delete("/organization/api-key")
async def revoke_api_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke the organization's API key. Admin only."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode gerenciar API keys")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    org.api_key = None
    db.commit()
    create_audit_log(db, str(user.organization_id), str(user.id), "organization", str(org.id), "revoke_api_key")
    return {"message": "API key revogada"}


# ========== IoT TELEMETRIA ==========

class IoTTelemetria(BaseModel):
    equipamento_id: str
    sensor: str
    valor: float
    unidade: Optional[str] = None
    timestamp: Optional[datetime] = None
    alerta: Optional[bool] = False
    mensagem: Optional[str] = None


async def _get_iot_org(request: Request, db: Session = Depends(get_db)) -> Organization:
    """Authenticate IoT requests via X-API-Key header."""
    api_key_header = request.headers.get("X-API-Key")
    if not api_key_header:
        raise HTTPException(status_code=401, detail="X-API-Key header obrigatório")
    org = db.query(Organization).filter(
        Organization.api_key == api_key_header,
        Organization.ativo == True,
    ).first()
    if not org:
        raise HTTPException(status_code=401, detail="API key inválida ou organização inativa")
    _require_feature(org, "api_iot")
    return org

@router.get("/grupos", response_model=List[GrupoResponse])
async def list_grupos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    grupos = db.query(Grupo).filter(Grupo.organization_id == user.organization_id).all()
    return [GrupoResponse(
        id=str(g.id), nome=g.nome, descricao=g.descricao,
        organization_id=str(g.organization_id), created_at=g.created_at
    ) for g in grupos]

@router.post("/grupos", response_model=GrupoResponse)
async def create_grupo(data: GrupoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    grupo = Grupo(nome=data.nome, descricao=data.descricao, organization_id=user.organization_id)
    db.add(grupo)
    db.commit()
    db.refresh(grupo)
    return GrupoResponse(
        id=str(grupo.id), nome=grupo.nome, descricao=grupo.descricao,
        organization_id=str(grupo.organization_id), created_at=grupo.created_at
    )

# ========== SUBGRUPOS ENDPOINTS ==========

@router.get("/subgrupos", response_model=List[SubgrupoResponse])
async def list_subgrupos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subgrupos = db.query(Subgrupo).filter(Subgrupo.organization_id == user.organization_id).all()
    return [SubgrupoResponse(
        id=str(s.id), grupo_id=str(s.grupo_id), nome=s.nome, descricao=s.descricao,
        organization_id=str(s.organization_id), created_at=s.created_at
    ) for s in subgrupos]

@router.post("/subgrupos", response_model=SubgrupoResponse)
async def create_subgrupo(data: SubgrupoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    subgrupo = Subgrupo(
        grupo_id=data.grupo_id, nome=data.nome, descricao=data.descricao,
        organization_id=user.organization_id
    )
    db.add(subgrupo)
    db.commit()
    db.refresh(subgrupo)
    return SubgrupoResponse(
        id=str(subgrupo.id), grupo_id=str(subgrupo.grupo_id), nome=subgrupo.nome,
        descricao=subgrupo.descricao, organization_id=str(subgrupo.organization_id), created_at=subgrupo.created_at
    )

# ========== SETORES ENDPOINTS ==========
