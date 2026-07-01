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

router = APIRouter(tags=["Setores"])


@router.post("/sectors", response_model=SetorResponse, status_code=201)
async def create_setor(
    data: SetorCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria um setor com senha genérica para login de técnicos. Apenas ADMIN."""
    if user.role not in (UserRole.ADMIN, UserRole.SUPERUSUARIO):
        raise HTTPException(status_code=403, detail="Apenas administradores podem criar setores.")
    if not data.nome.strip():
        raise HTTPException(status_code=400, detail="Nome do setor obrigatório.")
    if len(data.senha_tecnico) < 4:
        raise HTTPException(status_code=400, detail="A senha genérica deve ter ao menos 4 caracteres.")

    setor = Setor(
        organization_id=user.organization_id,
        nome=data.nome.strip(),
        senha_tecnico_hash=hash_password(data.senha_tecnico),
    )
    db.add(setor)
    db.commit()
    db.refresh(setor)
    return SetorResponse(id=str(setor.id), nome=setor.nome, organization_id=str(setor.organization_id), ativo=setor.ativo)

@router.get("/sectors", response_model=List[SetorResponse])
async def list_setores(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista setores da organização. ADMIN e LIDER."""
    if user.role not in (UserRole.ADMIN, UserRole.SUPERUSUARIO, UserRole.LIDER):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    setores = db.query(Setor).filter(Setor.organization_id == user.organization_id).order_by(Setor.nome).all()
    return [SetorResponse(id=str(s.id), nome=s.nome, organization_id=str(s.organization_id), ativo=s.ativo) for s in setores]

@router.put("/sectors/{sector_id}", response_model=SetorResponse)
async def update_setor(
    sector_id: str,
    data: SetorCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza nome e/ou senha genérica de um setor. Apenas ADMIN."""
    if user.role not in (UserRole.ADMIN, UserRole.SUPERUSUARIO):
        raise HTTPException(status_code=403, detail="Apenas administradores podem editar setores.")
    setor = db.query(Setor).filter(Setor.id == sector_id, Setor.organization_id == user.organization_id).first()
    if not setor:
        raise HTTPException(status_code=404, detail="Setor não encontrado.")
    setor.nome = data.nome.strip()
    if data.senha_tecnico:
        if len(data.senha_tecnico) < 4:
            raise HTTPException(status_code=400, detail="A senha genérica deve ter ao menos 4 caracteres.")
        setor.senha_tecnico_hash = hash_password(data.senha_tecnico)
    db.commit()
    db.refresh(setor)
    return SetorResponse(id=str(setor.id), nome=setor.nome, organization_id=str(setor.organization_id), ativo=setor.ativo)

@router.delete("/sectors/{sector_id}")
async def delete_setor(
    sector_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desativa um setor (soft delete). Apenas ADMIN."""
    if user.role not in (UserRole.ADMIN, UserRole.SUPERUSUARIO):
        raise HTTPException(status_code=403, detail="Apenas administradores podem remover setores.")
    setor = db.query(Setor).filter(Setor.id == sector_id, Setor.organization_id == user.organization_id).first()
    if not setor:
        raise HTTPException(status_code=404, detail="Setor não encontrado.")
    setor.ativo = False
    db.commit()
    return {"message": "Setor desativado."}


# ========== EQUIPAMENTOS ENDPOINTS ==========
