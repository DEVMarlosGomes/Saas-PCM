from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel
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

router = APIRouter(tags=["Colaboradores"])


@router.get("/colaboradores/lookup")
async def lookup_colaborador(matricula: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    col = db.query(Colaborador).filter(
        Colaborador.organization_id == user.organization_id,
        Colaborador.matricula == matricula,
        Colaborador.ativo == True,
    ).first()
    if col:
        return {"encontrado": True, "id": str(col.id), "nome": col.nome, "cargo": col.cargo, "setor": col.setor}
    return {"encontrado": False, "id": None, "nome": None, "cargo": None, "setor": None}

@router.get("/colaboradores", response_model=List[ColaboradorResponse])
async def list_colaboradores(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    cols = db.query(Colaborador).filter(
        Colaborador.organization_id == user.organization_id,
    ).order_by(Colaborador.nome).all()
    return [ColaboradorResponse(
        id=str(c.id), nome=c.nome, matricula=c.matricula,
        cargo=c.cargo, setor=c.setor, ativo=c.ativo, created_at=c.created_at,
    ) for c in cols]

@router.post("/colaboradores", response_model=ColaboradorResponse, status_code=201)
async def create_colaborador(data: ColaboradorCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode cadastrar colaboradores")
    existing = db.query(Colaborador).filter(
        Colaborador.organization_id == user.organization_id,
        Colaborador.matricula == data.matricula,
        Colaborador.ativo == True,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um colaborador ativo com esta matrícula")
    col = Colaborador(
        organization_id=user.organization_id,
        nome=data.nome,
        matricula=data.matricula,
        cargo=data.cargo,
        setor=data.setor,
    )
    db.add(col)
    db.commit()
    db.refresh(col)
    return ColaboradorResponse(
        id=str(col.id), nome=col.nome, matricula=col.matricula,
        cargo=col.cargo, setor=col.setor, ativo=col.ativo, created_at=col.created_at,
    )

@router.put("/colaboradores/{col_id}", response_model=ColaboradorResponse)
async def update_colaborador(col_id: str, data: ColaboradorUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode editar colaboradores")
    col = db.query(Colaborador).filter(
        Colaborador.id == col_id,
        Colaborador.organization_id == user.organization_id,
    ).first()
    if not col:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    if data.matricula and data.matricula != col.matricula:
        dup = db.query(Colaborador).filter(
            Colaborador.organization_id == user.organization_id,
            Colaborador.matricula == data.matricula,
            Colaborador.ativo == True,
            Colaborador.id != col.id,
        ).first()
        if dup:
            raise HTTPException(status_code=400, detail="Já existe um colaborador ativo com esta matrícula")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(col, field, val)
    db.commit()
    db.refresh(col)
    return ColaboradorResponse(
        id=str(col.id), nome=col.nome, matricula=col.matricula,
        cargo=col.cargo, setor=col.setor, ativo=col.ativo, created_at=col.created_at,
    )

@router.delete("/colaboradores/{col_id}")
async def delete_colaborador(col_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode excluir colaboradores")
    col = db.query(Colaborador).filter(
        Colaborador.id == col_id,
        Colaborador.organization_id == user.organization_id,
    ).first()
    if not col:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    col.ativo = False
    db.commit()
    return {"ok": True}

# ========== ORGANIZATION SETTINGS ==========
class OrganizationUpdate(BaseModel):
    nome: Optional[str] = None
    cnpj: Optional[str] = None
