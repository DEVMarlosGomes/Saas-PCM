"""
Authentication and authorization services.
Handles JWT tokens, password hashing, brute-force protection, and tenant-scoped auth.
"""
import os
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Response, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import (
    JWT_SECRET, JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    UserRole
)
from ..models.models import User, LoginAttempt


# ========== Password Hashing ==========
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ========== JWT Token Management ==========
def get_jwt_secret() -> str:
    return JWT_SECRET


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set HTTP-only auth cookies with proper security settings based on environment."""
    is_production = os.environ.get("FRONTEND_URL", "").startswith("https")
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=900,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=604800,
        path="/"
    )


# ========== Current User Dependency ==========
async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    FastAPI dependency that extracts and validates the current user from JWT.
    Supports both cookie-based and header-based authentication.
    """
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
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


# ========== Role-based Access Dependencies ==========
def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require ADMIN role."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user


def require_admin_or_leader(user: User = Depends(get_current_user)) -> User:
    """Require ADMIN or LIDER role."""
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return user


def require_technical(user: User = Depends(get_current_user)) -> User:
    """Require ADMIN, LIDER, or TECNICO role."""
    if user.role not in [UserRole.ADMIN, UserRole.LIDER, UserRole.TECNICO]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return user


# ========== Brute Force Protection ==========
def check_brute_force(db: Session, identifier: str) -> bool:
    attempt = db.query(LoginAttempt).filter(LoginAttempt.identifier == identifier).first()
    if attempt and attempt.locked_until:
        if datetime.now(timezone.utc) < attempt.locked_until:
            return False
        else:
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
