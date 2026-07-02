"""
Dependências FastAPI compartilhadas entre todos os routers.
"""
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
import json as _json

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import SessionLocal
from .settings import settings
from .models.core import (
    AuditoriaLog, LoginAttempt, Notificacao, Organization,
    OrdemServico, Equipamento, User, UserRole, PLAN_LIMITS, PlanoSaaS,
)

logger = logging.getLogger(__name__)

# ── JWT config ─────────────────────────────────────────────────────────────────
JWT_SECRET = settings.JWT_SECRET or secrets.token_hex(32)
JWT_ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

SMTP_HOST = settings.SMTP_HOST
SMTP_PORT = settings.SMTP_PORT
SMTP_USER = settings.SMTP_USER
SMTP_PASSWORD = settings.SMTP_PASSWORD
SMTP_FROM = settings.SMTP_FROM

_db_initialized = False


def _ensure_schema():
    global _db_initialized
    if _db_initialized:
        return
    try:
        from .database import engine, Base
        from .models import core as _core   # noqa: register models
        from .models import estoque as _est  # noqa
        from .models import evidencias as _ev  # noqa
        Base.metadata.create_all(bind=engine)
        _db_initialized = True
    except Exception as exc:
        logger.warning("Schema init skipped: %s", exc)


def get_db():
    _ensure_schema()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Password / JWT ──────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_jwt_secret() -> str:
    return JWT_SECRET


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response, access_token: str, refresh_token: str):
    prod = settings.is_production
    response.set_cookie(
        key="access_token", value=access_token,
        httponly=True, secure=prod, samesite="strict" if prod else "lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=prod, samesite="strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400, path="/api/auth/refresh",
    )


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Tipo de token inválido")
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def require_role(*roles: UserRole):
    async def dep(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Você não tem permissão para esta ação.")
        return user
    return dep


# ── Brute-force protection ──────────────────────────────────────────────────────

def check_brute_force(db: Session, identifier: str) -> bool:
    attempt = db.query(LoginAttempt).filter(LoginAttempt.identifier == identifier).first()
    if attempt and attempt.locked_until:
        if datetime.now(timezone.utc) < attempt.locked_until:
            return False
        attempt.attempts = 0
        attempt.locked_until = None
        db.commit()
    return True


def record_failed_attempt(db: Session, identifier: str):
    attempt = db.query(LoginAttempt).filter(LoginAttempt.identifier == identifier).first()
    if not attempt:
        attempt = LoginAttempt(identifier=identifier, attempts=1)
        db.add(attempt)
    else:
        attempt.attempts += 1
        if attempt.attempts >= 5:
            attempt.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.commit()


def clear_failed_attempts(db: Session, identifier: str):
    db.query(LoginAttempt).filter(LoginAttempt.identifier == identifier).delete()
    db.commit()


# ── Plan helpers ────────────────────────────────────────────────────────────────

def get_org_usage(db: Session, org_id) -> dict:
    now = datetime.now(timezone.utc)
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "equipamentos": db.query(Equipamento).filter(
            Equipamento.organization_id == org_id, Equipamento.ativo == True).count(),
        "users": db.query(User).filter(
            User.organization_id == org_id, User.ativo == True).count(),
        "os_mes": db.query(OrdemServico).filter(
            OrdemServico.organization_id == org_id,
            OrdemServico.created_at >= first_day).count(),
    }


def check_plan_limit(db: Session, org: Organization, resource: str) -> tuple:
    usage = get_org_usage(db, org.id)
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])
    limit_map = {
        "equipamentos": ("max_equipamentos", usage["equipamentos"]),
        "users": ("max_users", usage["users"]),
        "os": ("max_os_mes", usage["os_mes"]),
    }
    if resource not in limit_map:
        return True, ""
    limit_key, current = limit_map[resource]
    max_val = limits[limit_key]
    if max_val == -1:
        return True, ""
    if current >= max_val:
        return False, (
            f"Limite do plano {limits['label']} atingido: {current}/{max_val} {resource}. "
            "Faça upgrade para continuar."
        )
    return True, ""


def check_plan_feature(org: Organization, feature: str) -> bool:
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])
    return bool(limits.get(feature, False))


# ── Audit log ──────────────────────────────────────────────────────────────────

def create_audit_log(
    db: Session, org_id, user_id, entidade, entidade_id, acao,
    dados_anteriores=None, dados_novos=None, ip=None, user_agent=None,
):
    meta: dict = {}
    if ip:
        meta["_ip"] = ip
    if user_agent:
        meta["_ua"] = user_agent[:200]
    if meta:
        try:
            existing = _json.loads(dados_novos) if dados_novos else {}
            existing.update(meta)
            dados_novos = _json.dumps(existing, ensure_ascii=False)
        except Exception:
            pass
    db.add(AuditoriaLog(
        organization_id=org_id, user_id=user_id,
        entidade=entidade, entidade_id=entidade_id, acao=acao,
        dados_anteriores=dados_anteriores, dados_novos=dados_novos,
    ))
    db.commit()
    logger.info("[AUDIT] org=%s user=%s acao=%s entidade=%s id=%s ip=%s",
                org_id, user_id, acao, entidade, entidade_id, ip or "—")


# ── Notifications ──────────────────────────────────────────────────────────────

def criar_notificacao(db: Session, org_id, destinatario_id, tipo, titulo, mensagem, os_id=None):
    notif = Notificacao(
        org_id=org_id, destinatario_id=destinatario_id,
        tipo=tipo, titulo=titulo, mensagem=mensagem, os_id=os_id,
    )
    db.add(notif)
    db.commit()
    try:
        from .services.realtime import publish_sync
        publish_sync(str(org_id), "notificacao_nova", {
            "id": str(notif.id), "tipo": tipo, "titulo": titulo,
            "mensagem": mensagem, "os_id": str(os_id) if os_id else None,
        })
    except Exception:
        pass


def send_email_notification(db: Session, org: Organization, destinatario_id, subject: str, html_body: str):
    if not PLAN_LIMITS.get(org.plano, {}).get("notificacoes_email"):
        return
    if not SMTP_HOST or not SMTP_USER:
        return
    try:
        dest = db.query(User).filter(User.id == destinatario_id, User.ativo == True).first()
        if not dest:
            return
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AURIX] {subject}"
        msg["From"] = SMTP_FROM
        msg["To"] = dest.email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.sendmail(SMTP_FROM, [dest.email], msg.as_string())
    except Exception as exc:
        logger.warning("Email notification failed: %s", exc)


# ── OS helpers ─────────────────────────────────────────────────────────────────

def get_next_os_number(db: Session, org_id: str) -> int:
    last = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id
    ).order_by(OrdemServico.numero.desc()).first()
    return (last.numero + 1) if last else 1
