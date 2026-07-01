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

router = APIRouter(tags=["Usuários"])


@router.get("/users/buscar-por-cracha")
async def buscar_por_cracha(cracha: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lookup de usuário pelo crachá/matrícula (employee_id). Retorna info resumida sem erro caso não encontre."""
    found = db.query(User).filter(
        User.organization_id == user.organization_id,
        User.employee_id == cracha,
        User.ativo == True,
    ).first()
    if found:
        return {
            "encontrado": True,
            "nome_completo": found.nome,
            "role": found.role.value,
            "setor": found.setor,
        }
    return {"encontrado": False, "nome_completo": None, "role": None, "setor": None}

@router.get("/users", response_model=List[UserResponse])
async def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    users = db.query(User).filter(User.organization_id == user.organization_id).all()
    return [UserResponse(
        id=str(u.id), email=u.email, nome=u.nome, role=u.role.value,
        setor=u.setor, is_lider=u.is_lider or False,
        employee_id=u.employee_id,
        generic_session_sector=u.generic_session_sector,
        organization_id=str(u.organization_id), ativo=u.ativo, created_at=u.created_at,
    ) for u in users]

@router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode criar usuários")
    
    # Check plan limit
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    allowed, msg = check_plan_limit(db, org, "users")
    if not allowed:
        raise HTTPException(status_code=402, detail=msg)
    
    existing = db.query(User).filter(User.email == data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    new_user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        nome=data.nome,
        role=data.role,
        setor=data.setor,
        is_lider=data.is_lider,
        employee_id=data.employee_id,
        organization_id=user.organization_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse(
        id=str(new_user.id), email=new_user.email, nome=new_user.nome, role=new_user.role.value,
        setor=new_user.setor, is_lider=new_user.is_lider or False,
        employee_id=new_user.employee_id,
        generic_session_sector=new_user.generic_session_sector,
        organization_id=str(new_user.organization_id), ativo=new_user.ativo, created_at=new_user.created_at,
    )

class UserUpdate(BaseModel):
    nome: Optional[str] = None
    role: Optional[UserRole] = None
    setor: Optional[str] = None
    is_lider: Optional[bool] = None
    employee_id: Optional[str] = None
    ativo: Optional[bool] = None

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode editar usuários")
    
    target_user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == user.organization_id
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # Prevent admin from demoting themselves
    if str(target_user.id) == str(user.id) and data.role and data.role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Você não pode alterar seu próprio cargo de admin")
    
    if data.nome is not None:
        target_user.nome = data.nome
    if data.role is not None:
        target_user.role = data.role
    if data.setor is not None:
        target_user.setor = data.setor
    if data.is_lider is not None:
        target_user.is_lider = data.is_lider
    if data.employee_id is not None:
        target_user.employee_id = data.employee_id
    if data.ativo is not None:
        if str(target_user.id) == str(user.id) and not data.ativo:
            raise HTTPException(status_code=400, detail="Você não pode desativar sua própria conta")
        target_user.ativo = data.ativo

    db.commit()
    db.refresh(target_user)
    create_audit_log(db, str(user.organization_id), str(user.id), "user", str(target_user.id), "update")

    return UserResponse(
        id=str(target_user.id), email=target_user.email, nome=target_user.nome, role=target_user.role.value,
        setor=target_user.setor, is_lider=target_user.is_lider or False,
        employee_id=target_user.employee_id,
        generic_session_sector=target_user.generic_session_sector,
        organization_id=str(target_user.organization_id), ativo=target_user.ativo, created_at=target_user.created_at,
    )

@router.delete("/users/{user_id}")
async def deactivate_user(user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode desativar usuários")
    
    if str(user_id) == str(user.id):
        raise HTTPException(status_code=400, detail="Você não pode desativar sua própria conta")
    
    target_user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == user.organization_id
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    target_user.ativo = False
    db.commit()
    
    create_audit_log(db, str(user.organization_id), str(user.id), "user", str(target_user.id), "deactivate")
    
    return {"message": "Usuário desativado com sucesso"}

# ========== COLABORADORES ENDPOINTS ==========
