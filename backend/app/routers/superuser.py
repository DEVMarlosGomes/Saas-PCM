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

router = APIRouter(tags=["Superuser"])


@router.get("/superuser/empresas")
async def superuser_list_empresas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lista todas as organizações cadastradas na plataforma."""
    _require_superuser(user)
    orgs = db.query(Organization).order_by(Organization.created_at.desc()).all()
    result = []
    for org in orgs:
        usage = get_org_usage(db, org.id)
        limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])
        result.append({
            "id": str(org.id),
            "nome": org.nome,
            "cnpj": org.cnpj,
            "plano": org.plano.value,
            "plano_label": limits.get("label", org.plano.value),
            "subscription_status": org.subscription_status,
            "ativo": org.ativo,
            "plano_trial_expira_em": org.plano_trial_expira_em.isoformat() if org.plano_trial_expira_em else None,
            "created_at": org.created_at.isoformat() if org.created_at else None,
            "usage": usage,
            "limits": {
                "max_equipamentos": limits["max_equipamentos"],
                "max_users": limits["max_users"],
                "max_os_mes": limits["max_os_mes"],
            },
        })
    return {"empresas": result, "total": len(result)}


class SuperuserOrgCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    plano: PlanoSaaS = PlanoSaaS.DEMO
    admin_email: EmailStr
    admin_password: str
    admin_nome: str

@router.post("/superuser/empresas", status_code=201)
async def superuser_create_empresa(
    data: SuperuserOrgCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria nova empresa (organização) e seu admin inicial."""
    _require_superuser(user)

    existing = db.query(User).filter(User.email == data.admin_email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email do admin já cadastrado.")

    org = Organization(
        nome=data.nome,
        cnpj=data.cnpj,
        plano=data.plano,
        plano_trial_expira_em=datetime.now(timezone.utc) + timedelta(days=10),
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    _seed_grupos_padrao(db, org.id)

    admin_user = User(
        email=data.admin_email.lower(),
        password_hash=hash_password(data.admin_password),
        nome=data.admin_nome,
        role=UserRole.ADMIN,
        organization_id=org.id,
    )
    db.add(admin_user)
    db.commit()

    create_audit_log(
        db, str(org.id), str(user.id), "organization", str(org.id), "superuser_create"
    )
    return {"message": "Empresa criada com sucesso.", "org_id": str(org.id)}


class SuperuserOrgUpdate(BaseModel):
    nome: Optional[str] = None
    plano: Optional[PlanoSaaS] = None
    ativo: Optional[bool] = None
    subscription_status: Optional[str] = None

@router.put("/superuser/empresas/{org_id}")
async def superuser_update_empresa(
    org_id: str,
    data: SuperuserOrgUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edita ou suspende uma empresa."""
    _require_superuser(user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    if data.nome is not None:
        org.nome = data.nome
    if data.plano is not None:
        org.plano = data.plano
        limits = PLAN_LIMITS[data.plano]
        org.limite_equipamentos = limits["max_equipamentos"]
        org.limite_usuarios = limits["max_users"]
        org.limite_os_mes = limits["max_os_mes"]
    if data.ativo is not None:
        org.ativo = data.ativo
    if data.subscription_status is not None:
        org.subscription_status = data.subscription_status
    db.commit()
    create_audit_log(db, str(org.id), str(user.id), "organization", str(org.id), "superuser_update")
    return {"message": "Empresa atualizada.", "org_id": str(org.id)}

@router.get("/superuser/dashboard")
async def superuser_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Dashboard agregado: total OS abertas, disponibilidade média e alertas críticos."""
    _require_superuser(user)
    orgs = db.query(Organization).filter(Organization.ativo == True).all()
    total_orgs = len(orgs)
    total_os_abertas = db.query(OrdemServico).filter(
        OrdemServico.status.in_([StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA])
    ).count()
    total_os_mes = db.query(OrdemServico).filter(
        OrdemServico.created_at >= datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ).count()
    alertas_criticos = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.status == "ABERTO",
        AlertaPreditivo.severidade == "CRITICO",
    ).count()

    # Disponibilidade média (global — todas as orgs)
    os_reparo = db.query(OrdemServico).filter(OrdemServico.tempo_reparo != None).all()
    mttr_global = sum(o.tempo_reparo for o in os_reparo) / len(os_reparo) / 60 if os_reparo else 0
    first_os_global = db.query(OrdemServico).filter(
        OrdemServico.tipo == TipoOS.CORRETIVA
    ).order_by(OrdemServico.created_at).first()
    total_cor = db.query(OrdemServico).filter(OrdemServico.tipo == TipoOS.CORRETIVA).count()
    if first_os_global and total_cor > 1:
        days_op = (datetime.now(timezone.utc) - first_os_global.created_at).days or 1
        mtbf_global = (days_op * 24) / total_cor
    else:
        mtbf_global = 720
    disponibilidade_media = (mtbf_global / (mtbf_global + mttr_global) * 100) if (mtbf_global + mttr_global) > 0 else 100

    return {
        "total_empresas": total_orgs,
        "total_os_abertas": total_os_abertas,
        "total_os_mes": total_os_mes,
        "alertas_criticos": alertas_criticos,
        "disponibilidade_media": round(disponibilidade_media, 2),
    }


# ========== SEED DATA ==========
