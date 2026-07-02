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

router = APIRouter(tags=["Custos"])


@router.get("/custos", response_model=List[CustoResponse])
async def list_custos(ordem_servico_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(CustoOS).filter(CustoOS.organization_id == user.organization_id)
    if ordem_servico_id:
        query = query.filter(CustoOS.ordem_servico_id == ordem_servico_id)
    custos = query.all()
    return [CustoResponse(
        id=str(c.id), ordem_servico_id=str(c.ordem_servico_id), tipo=c.tipo.value,
        descricao=c.descricao, valor=c.valor, quantidade=c.quantidade,
        organization_id=str(c.organization_id),
        criado_por=str(c.criado_por) if getattr(c, 'criado_por', None) else None,
        created_at=c.created_at,
    ) for c in custos]

@router.post("/custos", response_model=CustoResponse)
async def create_custo(data: CustoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER, UserRole.TECNICO]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Verify OS exists
    os = db.query(OrdemServico).filter(
        OrdemServico.id == data.ordem_servico_id,
        OrdemServico.organization_id == user.organization_id
    ).first()
    if not os:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    
    custo = CustoOS(
        ordem_servico_id=data.ordem_servico_id,
        tipo=data.tipo,
        descricao=data.descricao,
        valor=data.valor,
        quantidade=data.quantidade,
        organization_id=user.organization_id,
        criado_por=user.id,
    )
    db.add(custo)
    db.commit()
    db.refresh(custo)

    create_audit_log(db, str(user.organization_id), str(user.id), "custo_os", str(custo.id), "create")

    return CustoResponse(
        id=str(custo.id), ordem_servico_id=str(custo.ordem_servico_id), tipo=custo.tipo.value,
        descricao=custo.descricao, valor=custo.valor, quantidade=custo.quantidade,
        organization_id=str(custo.organization_id),
        criado_por=str(custo.criado_por) if custo.criado_por else None,
        created_at=custo.created_at,
    )

@router.delete("/custos/{custo_id}", status_code=204)
async def delete_custo(custo_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    custo = db.query(CustoOS).filter(
        CustoOS.id == custo_id,
        CustoOS.organization_id == user.organization_id,
    ).first()
    if not custo:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    _PODE_EXCLUIR_CUSTO = [
        UserRole.ADMIN, UserRole.SUPERVISOR_MANUTENCAO, UserRole.GERENTE_INDUSTRIAL,
        UserRole.LIDER_MANUTENCAO_ELETRICA, UserRole.LIDER_MANUTENCAO_MECANICA, UserRole.ANALISTA_MANUTENCAO,
    ]
    # Quem criou o item, técnico atribuído à OS, ou supervisores
    os_obj = db.query(OrdemServico).filter(OrdemServico.id == custo.ordem_servico_id).first()
    eh_tecnico_responsavel = os_obj and str(os_obj.tecnico_id) == str(user.id)
    eh_criador = custo.criado_por and str(custo.criado_por) == str(user.id)

    if not eh_criador and not eh_tecnico_responsavel and user.role not in _PODE_EXCLUIR_CUSTO:
        raise HTTPException(status_code=403, detail="Sem permissão para remover este item.")

    create_audit_log(db, str(user.organization_id), str(user.id), "custo_os", str(custo.id), "delete")
    db.delete(custo)
    db.commit()
    return None
