"""
MFA — TOTP endpoints (Fase 5.2)

POST /auth/mfa/setup          → gera secret + URI de provisionamento
POST /auth/mfa/enable         → confirma código + ativa MFA + retorna backup codes
POST /auth/mfa/verify         → verifica código durante login (pré-sessão)
POST /auth/mfa/disable        → desativa MFA (exige senha)
GET  /auth/mfa/backup-codes   → lista quantos backup codes restam
POST /auth/mfa/use-backup     → usa código de recuperação

Roles que DEVEM ter MFA habilitado: admin, lider, gerente_industrial,
supervisor_manutencao (verificado em get_current_user_with_mfa).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user, create_audit_log
from ..models.core import User, UserRole
from ..services import mfa_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mfa"])

# Papéis que exigem MFA em produção
MFA_REQUIRED_ROLES = {
    UserRole.ADMIN,
    UserRole.SUPERUSUARIO,
    UserRole.LIDER,
    UserRole.GERENTE_INDUSTRIAL,
    UserRole.SUPERVISOR_MANUTENCAO,
}


# ── Schemas ────────────────────────────────────────────────────────────────────

class MFASetupResponse(BaseModel):
    provisioning_uri: str
    message: str


class MFAEnableRequest(BaseModel):
    code: str


class MFAEnableResponse(BaseModel):
    backup_codes: list[str]
    message: str


class MFAVerifyRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    password: str
    code: str


class MFABackupRequest(BaseModel):
    code: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/auth/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Gera um novo TOTP secret (não ativa ainda)."""
    if not mfa_service.is_available():
        raise HTTPException(503, "MFA não disponível — instale pyotp.")

    if user.mfa_enabled:
        raise HTTPException(400, "MFA já está ativo. Desative primeiro para reconfigurar.")

    result = mfa_service.setup(user.email)
    # Salva secret pendente (ainda não ativado)
    user.mfa_secret = result["secret_encrypted"]
    db.commit()

    return MFASetupResponse(
        provisioning_uri=result["provisioning_uri"],
        message="Escaneie o QR code no seu app autenticador e confirme com /auth/mfa/enable.",
    )


@router.post("/auth/mfa/enable", response_model=MFAEnableResponse)
async def mfa_enable(
    body: MFAEnableRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirma código TOTP e ativa MFA. Retorna backup codes (mostrar 1x)."""
    if not user.mfa_secret:
        raise HTTPException(400, "Execute /auth/mfa/setup primeiro.")

    if not mfa_service.verify(user.mfa_secret, body.code):
        raise HTTPException(422, "Código inválido ou expirado.")

    plaintext, hashed = mfa_service.generate_backup_codes()
    user.mfa_enabled = True
    user.mfa_backup_codes = json.dumps(hashed)
    db.commit()

    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="user", entidade_id=str(user.id), acao="mfa_enabled",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    logger.info("MFA enabled for user %s", user.id)

    return MFAEnableResponse(
        backup_codes=plaintext,
        message="MFA ativado com sucesso. Guarde os códigos de recuperação — eles não serão exibidos novamente.",
    )


@router.post("/auth/mfa/verify")
async def mfa_verify(
    body: MFAVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verifica código TOTP (chamado no login quando mfa_enabled=True)."""
    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(400, "MFA não está ativado para este usuário.")

    if not mfa_service.verify(user.mfa_secret, body.code):
        raise HTTPException(422, "Código MFA inválido ou expirado.")

    return {"ok": True}


@router.post("/auth/mfa/disable")
async def mfa_disable(
    body: MFADisableRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desativa MFA. Exige senha + código TOTP válido."""
    from ..deps import verify_password
    if not verify_password(body.password, user.senha_hash):
        raise HTTPException(403, "Senha incorreta.")

    if not mfa_service.verify(user.mfa_secret, body.code):
        raise HTTPException(422, "Código MFA inválido.")

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_backup_codes = None
    db.commit()

    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="user", entidade_id=str(user.id), acao="mfa_disabled",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"ok": True, "message": "MFA desativado."}


@router.get("/auth/mfa/backup-codes")
async def mfa_backup_count(
    user: User = Depends(get_current_user),
):
    """Retorna quantos códigos de recuperação restam (nunca os hashes)."""
    if not user.mfa_enabled:
        raise HTTPException(400, "MFA não está ativo.")
    codes = json.loads(user.mfa_backup_codes or "[]")
    return {"remaining": len(codes)}


@router.post("/auth/mfa/use-backup")
async def mfa_use_backup(
    body: MFABackupRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Autentica usando um backup code (consume o código)."""
    if not user.mfa_enabled:
        raise HTTPException(400, "MFA não está ativo.")
    hashed = json.loads(user.mfa_backup_codes or "[]")
    valid, remaining = mfa_service.verify_backup_code(body.code, hashed)
    if not valid:
        raise HTTPException(422, "Código de recuperação inválido ou já utilizado.")
    user.mfa_backup_codes = json.dumps(remaining)
    db.commit()
    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="user", entidade_id=str(user.id), acao="mfa_backup_used",
        dados_novos=f'{{"remaining": {len(remaining)}}}',
        ip=request.client.host if request.client else None,
    )
    return {"ok": True, "remaining": len(remaining)}
