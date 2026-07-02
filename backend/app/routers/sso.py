"""
SSO OIDC — endpoints (Fase 5.1)

GET /auth/sso/providers          → lista provedores configurados para uma org
GET /auth/sso/authorize          → inicia fluxo OIDC (redireciona para IdP)
GET /auth/sso/callback           → callback OIDC, JIT provision, emite JWT
POST /auth/sso/configure         → admin configura provedor OIDC da org

Para SAML: endpoint separado em /auth/sso/saml/* (pendente — requer pysaml2).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import (
    get_db, get_current_user, require_role,
    create_access_token, create_refresh_token, set_auth_cookies,
)
from ..models.core import Organization, User, UserRole
from ..services import sso_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sso"])

_REDIRECT_BASE = os.environ.get("FRONTEND_URL", "http://localhost:3000")
_CALLBACK_URL = os.environ.get("SSO_CALLBACK_URL", "http://localhost:8000/api/auth/sso/callback")


# ── Schemas ────────────────────────────────────────────────────────────────────

class OIDCConfigRequest(BaseModel):
    provider: str           # "google" | "azure" | "oidc"
    client_id: str
    client_secret: str
    discovery_url: str
    sso_required: bool = False


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/auth/sso/providers")
async def list_providers(
    org_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(
        Organization.id == (org_id or user.organization_id)
    ).first()
    if not org:
        raise HTTPException(404)
    return {
        "sso_enabled": getattr(org, "sso_enabled", False),
        "provider": getattr(org, "sso_provider", None),
        "sso_required": getattr(org, "sso_required", False),
    }


@router.post("/auth/sso/configure")
async def configure_sso(
    body: OIDCConfigRequest,
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERUSUARIO)),
    db: Session = Depends(get_db),
):
    """Admin configura o provedor OIDC da organização."""
    from ..services import rbac_service
    if not rbac_service.has_permission(user.role, "sso", "configurar"):
        raise HTTPException(403, "Sem permissão para configurar SSO.")

    org = db.query(Organization).filter(
        Organization.id == user.organization_id
    ).first()
    if not org:
        raise HTTPException(404)

    org.sso_enabled = True
    org.sso_provider = body.provider
    org.oidc_client_id = body.client_id
    org.oidc_client_secret = body.client_secret
    org.oidc_discovery_url = body.discovery_url.rstrip("/")
    org.sso_required = body.sso_required
    db.commit()

    from ..deps import create_audit_log
    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="organization", entidade_id=str(org.id), acao="sso_configure",
        dados_novos=f'{{"provider": "{body.provider}", "sso_required": {str(body.sso_required).lower()}}}',
        ip=request.client.host if request.client else None,
    )
    return {"ok": True, "provider": body.provider}


@router.get("/auth/sso/authorize")
async def sso_authorize(
    org_slug: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Redireciona para o IdP OIDC configurado para a organização."""
    if not sso_service.is_available():
        raise HTTPException(503, "SSO não disponível — instale authlib e httpx.")

    org = None
    if org_id:
        org = db.query(Organization).filter(Organization.id == org_id).first()
    elif org_slug:
        org = db.query(Organization).filter(Organization.nome == org_slug).first()

    if not org or not getattr(org, "sso_enabled", False):
        raise HTTPException(404, "SSO não configurado para esta organização.")

    state, nonce = sso_service.generate_state(str(org.id))

    try:
        url = await sso_service.get_authorization_url(
            discovery_url=org.oidc_discovery_url,
            client_id=org.oidc_client_id,
            redirect_uri=_CALLBACK_URL,
            state=state,
            nonce=nonce,
        )
    except Exception as exc:
        logger.error("SSO authorize error: %s", exc)
        raise HTTPException(502, f"Erro ao conectar com o IdP: {exc}")

    return RedirectResponse(url=url, status_code=302)


@router.get("/auth/sso/callback")
async def sso_callback(
    code: str = Query(...),
    state: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Callback OIDC: valida state, troca code, provisiona usuário, emite JWT."""
    ctx = sso_service.consume_state(state)
    if not ctx:
        raise HTTPException(400, "State inválido ou expirado. Tente novamente.")

    org_id, nonce = ctx
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return RedirectResponse(f"{_REDIRECT_BASE}/login?sso_error=org_not_found")

    try:
        claims = await sso_service.exchange_code(
            discovery_url=org.oidc_discovery_url,
            client_id=org.oidc_client_id,
            client_secret=org.oidc_client_secret,
            redirect_uri=_CALLBACK_URL,
            code=code,
            nonce=nonce,
        )
    except Exception as exc:
        logger.error("SSO callback error: %s", exc)
        return RedirectResponse(f"{_REDIRECT_BASE}/login?sso_error=token_exchange_failed")

    try:
        user = sso_service.provision_user_jit(db, claims, org_id, org.sso_provider or "oidc")
    except Exception as exc:
        logger.error("SSO JIT provision error: %s", exc)
        return RedirectResponse(f"{_REDIRECT_BASE}/login?sso_error=provision_failed")

    if not user.ativo:
        return RedirectResponse(f"{_REDIRECT_BASE}/login?sso_error=user_inactive")

    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))

    # Redireciona para frontend com token em cookie
    from fastapi.responses import Response
    response = RedirectResponse(url=f"{_REDIRECT_BASE}/dashboard", status_code=302)
    set_auth_cookies(response, access_token, refresh_token)
    return response
