from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel, EmailStr
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
from ..middleware.rate_limiter import (
    limiter, LIMIT_AUTH, LIMIT_BILLING, LIMIT_IOT, LIMIT_APIKEY, LIMIT_STRICT,
)
from slowapi.errors import RateLimitExceeded

router = APIRouter(tags=["IoT"])


@router.post("/iot/telemetria", status_code=201)
async def receive_telemetria(
    payload: IoTTelemetria,
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive sensor telemetry from IoT devices. Authenticated via X-API-Key."""
    org = await _get_iot_org(request, db)

    equip = db.query(Equipamento).filter(
        Equipamento.id == payload.equipamento_id,
        Equipamento.organization_id == org.id,
    ).first()
    if not equip:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")

    result = {
        "recebido": True,
        "equipamento": equip.nome,
        "sensor": payload.sensor,
        "valor": payload.valor,
        "timestamp": (payload.timestamp or datetime.now(timezone.utc)).isoformat(),
        "os_criada": False,
    }

    # Auto-create corrective OS on alert
    if payload.alerta:
        num = get_next_os_number(db, org.id)
        desc = payload.mensagem or f"Alerta IoT: {payload.sensor} = {payload.valor} {payload.unidade or ''}".strip()
        os_alert = OrdemServico(
            numero=num,
            organization_id=org.id,
            equipamento_id=equip.id,
            tipo=TipoOS.CORRETIVA,
            prioridade=PrioridadeOS.ALTA,
            status=StatusOS.ABERTA,
            descricao=desc,
            falha_tipo="iot_alert",
            reincidente=check_reincidencia(db, str(org.id), payload.equipamento_id, "iot_alert"),
        )
        db.add(os_alert)
        db.commit()
        db.refresh(os_alert)
        result["os_criada"] = True
        result["os_numero"] = os_alert.numero

        # Notify admin
        admin = db.query(User).filter(
            User.organization_id == org.id,
            User.role == UserRole.ADMIN,
            User.ativo == True,
        ).first()
        if admin:
            criar_notificacao(
                db, org_id=org.id, destinatario_id=admin.id,
                tipo="iot_alert",
                titulo=f"Alerta IoT: {equip.nome}",
                mensagem=desc,
                os_id=os_alert.id,
            )
            send_email_notification(
                db, org, admin.id,
                f"Alerta IoT — {equip.nome}",
                f"<p><strong>Sensor:</strong> {payload.sensor}<br><strong>Valor:</strong> {payload.valor} {payload.unidade or ''}<br>{desc}</p>",
            )

    return result


# ========== PASSWORD RESET ==========
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str
