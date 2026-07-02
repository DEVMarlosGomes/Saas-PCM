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

router = APIRouter(tags=["Planos Preventivos"])


@router.get("/planos-preventivos", response_model=List[PlanoResponse])
async def list_planos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "planos_preventivos")
    planos = db.query(PlanoPreventivo).filter(
        PlanoPreventivo.organization_id == user.organization_id,
        PlanoPreventivo.ativo == True
    ).all()
    return [PlanoResponse(
        id=str(p.id), equipamento_id=str(p.equipamento_id), nome=p.nome,
        descricao=p.descricao, frequencia_dias=p.frequencia_dias,
        ultima_execucao=p.ultima_execucao, proxima_execucao=p.proxima_execucao,
        ativo=p.ativo, organization_id=str(p.organization_id), created_at=p.created_at
    ) for p in planos]

@router.post("/planos-preventivos", response_model=PlanoResponse)
async def create_plano(data: PlanoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "planos_preventivos")
    
    # Verify equipment exists
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == data.equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    
    proxima = datetime.now(timezone.utc) + timedelta(days=data.frequencia_dias)
    
    plano = PlanoPreventivo(
        equipamento_id=data.equipamento_id,
        nome=data.nome,
        descricao=data.descricao,
        frequencia_dias=data.frequencia_dias,
        proxima_execucao=proxima,
        organization_id=user.organization_id
    )
    db.add(plano)
    db.commit()
    db.refresh(plano)
    
    return PlanoResponse(
        id=str(plano.id), equipamento_id=str(plano.equipamento_id), nome=plano.nome,
        descricao=plano.descricao, frequencia_dias=plano.frequencia_dias,
        ultima_execucao=plano.ultima_execucao, proxima_execucao=plano.proxima_execucao,
        ativo=plano.ativo, organization_id=str(plano.organization_id), created_at=plano.created_at
    )

@router.post("/planos-preventivos/{plano_id}/executar")
async def executar_plano(plano_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Gera uma OS preventiva a partir do plano"""
    plano = db.query(PlanoPreventivo).filter(
        PlanoPreventivo.id == plano_id,
        PlanoPreventivo.organization_id == user.organization_id
    ).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    
    equipamento = db.query(Equipamento).filter(Equipamento.id == plano.equipamento_id).first()
    
    numero = get_next_os_number(db, str(user.organization_id))
    
    os = OrdemServico(
        numero=numero,
        equipamento_id=plano.equipamento_id,
        grupo_id=equipamento.grupo_id if equipamento else None,
        subgrupo_id=equipamento.subgrupo_id if equipamento else None,
        tipo=TipoOS.PREVENTIVA,
        prioridade=PrioridadeOS.MEDIA,
        descricao=f"Manutenção preventiva: {plano.nome}",
        solicitante_id=user.id,
        organization_id=user.organization_id
    )
    db.add(os)
    
    # Update plano
    now = datetime.now(timezone.utc)
    plano.ultima_execucao = now
    plano.proxima_execucao = now + timedelta(days=plano.frequencia_dias)
    
    db.commit()
    db.refresh(os)
    
    return {"message": "OS preventiva criada", "os_id": str(os.id), "numero": os.numero}

# ========== DASHBOARD / INDICADORES ==========
