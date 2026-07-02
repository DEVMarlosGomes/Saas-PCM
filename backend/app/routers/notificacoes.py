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

router = APIRouter(tags=["Notificações"])


@router.get("/notificacoes")
async def list_notificacoes(
    apenas_nao_lidas: bool = False,
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notificacao).filter(
        Notificacao.destinatario_id == user.id,
        Notificacao.org_id == user.organization_id,
    )
    if apenas_nao_lidas:
        query = query.filter(Notificacao.lida == False)
    notifs = query.order_by(Notificacao.criada_em.desc()).limit(limit).all()
    return [
        {
            "id": str(n.id),
            "tipo": n.tipo,
            "titulo": n.titulo,
            "mensagem": n.mensagem,
            "os_id": str(n.os_id) if n.os_id else None,
            "lida": n.lida,
            "criada_em": n.criada_em.isoformat(),
            "lida_em": n.lida_em.isoformat() if n.lida_em else None,
        }
        for n in notifs
    ]

@router.get("/notificacoes/count")
async def count_nao_lidas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.query(Notificacao).filter(
        Notificacao.destinatario_id == user.id,
        Notificacao.org_id == user.organization_id,
        Notificacao.lida == False,
    ).count()
    return {"nao_lidas": count}

@router.post("/notificacoes/{notif_id}/ler")
async def marcar_lida(notif_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notif = db.query(Notificacao).filter(
        Notificacao.id == notif_id,
        Notificacao.destinatario_id == user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    notif.lida = True
    notif.lida_em = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}

@router.post("/notificacoes/ler-todas")
async def marcar_todas_lidas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notificacao).filter(
        Notificacao.destinatario_id == user.id,
        Notificacao.org_id == user.organization_id,
        Notificacao.lida == False,
    ).update({"lida": True, "lida_em": datetime.now(timezone.utc)})
    db.commit()
    return {"ok": True}


# ========== BILLING ENDPOINTS ==========
