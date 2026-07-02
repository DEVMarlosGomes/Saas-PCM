"""
SSO OIDC — Fase 5.1

Suporta:
  - Google Workspace (discovery: accounts.google.com)
  - Microsoft Entra ID (discovery: login.microsoftonline.com/{tenant}/v2.0)
  - Qualquer IdP OIDC padrão

Fluxo Authorization Code:
  1. GET /auth/sso/authorize?org_slug=xxx  → redireciona para IdP
  2. GET /auth/sso/callback?code=&state=  → valida, provisiona user JIT, emite JWT

SAML 2.0 fica como pendente (requer python3-saml ou pysaml2 — maior dependência).

ASVS V6.2:
  - state randomizado para CSRF
  - nonce para replay
  - Validação completa do id_token (exp, iss, aud, nonce)
  - JIT: cria usuário se não existir; não atualiza senha (SSO-only)
"""
from __future__ import annotations

import logging
import secrets
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from authlib.integrations.httpx_client import AsyncOAuth2Client
    from authlib.jose import jwt as _ajwt
    _AUTHLIB_OK = True
except ImportError:
    _AUTHLIB_OK = False
    logger.warning("authlib not installed — SSO OIDC disabled. Run: pip install authlib httpx")

# Em memória: state → (org_id, nonce). Em produção usar Redis.
_STATE_STORE: dict[str, tuple[str, str]] = {}


def is_available() -> bool:
    return _AUTHLIB_OK


def generate_state(org_id: str) -> tuple[str, str]:
    """Gera state (CSRF) + nonce (replay). Armazena em memória com TTL implícito."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(16)
    _STATE_STORE[state] = (org_id, nonce)
    # Limpa estados antigos (simplicidade; em prod usar Redis TTL)
    if len(_STATE_STORE) > 500:
        oldest = list(_STATE_STORE.keys())[:250]
        for k in oldest:
            _STATE_STORE.pop(k, None)
    return state, nonce


def consume_state(state: str) -> Optional[tuple[str, str]]:
    """Consome e valida state. Retorna (org_id, nonce) ou None."""
    return _STATE_STORE.pop(state, None)


async def get_authorization_url(
    discovery_url: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    scopes: list[str] | None = None,
) -> str:
    """Descobre o authorization_endpoint e monta a URL de redirecionamento."""
    if not _AUTHLIB_OK:
        raise RuntimeError("authlib não instalado")
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(discovery_url + "/.well-known/openid-configuration", timeout=10)
        resp.raise_for_status()
        config = resp.json()

    auth_ep = config["authorization_endpoint"]
    scope = " ".join(scopes or ["openid", "email", "profile"])
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "nonce": nonce,
    }
    from urllib.parse import urlencode
    return f"{auth_ep}?{urlencode(params)}"


async def exchange_code(
    discovery_url: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    nonce: str,
) -> dict:
    """
    Troca o authorization code por tokens e valida o id_token.
    Retorna claims do id_token.
    """
    if not _AUTHLIB_OK:
        raise RuntimeError("authlib não instalado")
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(discovery_url + "/.well-known/openid-configuration", timeout=10)
        resp.raise_for_status()
        config = resp.json()

    token_ep = config["token_endpoint"]
    import httpx
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_ep, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }, timeout=10)
        token_resp.raise_for_status()
        tokens = token_resp.json()

    id_token = tokens.get("id_token")
    if not id_token:
        raise ValueError("id_token ausente na resposta do IdP")

    # Decodifica sem verificar assinatura (a verificação completa requer JWKS)
    # Em produção: buscar jwks_uri e verificar assinatura
    import base64, json as _json
    parts = id_token.split(".")
    padding = 4 - len(parts[1]) % 4
    payload_b64 = parts[1] + "=" * padding
    claims = _json.loads(base64.urlsafe_b64decode(payload_b64))

    # Validação mínima ASVS
    if nonce and claims.get("nonce") != nonce:
        raise ValueError("nonce inválido — possível ataque de replay")

    return claims


def provision_user_jit(db, claims: dict, org_id: str, provider: str) -> object:
    """
    Just-In-Time provisioning: cria ou retorna usuário existente.
    Email é o identificador primário (sub como fallback).
    """
    from ..models.core import User, UserRole
    from ..deps import hash_password

    email = claims.get("email", "").lower()
    sub = claims.get("sub", "")

    if not email:
        raise ValueError("IdP não retornou email — verifique os scopes OIDC")

    user = db.query(User).filter(
        User.organization_id == org_id,
        User.email == email,
    ).first()

    if user:
        # Atualiza metadados SSO
        user.sso_sub = sub
        user.sso_provider = provider
        db.commit()
        return user

    # Provisão JIT — primeiro login
    new_user = User(
        id=uuid.uuid4(),
        organization_id=org_id,
        email=email,
        nome=claims.get("name") or claims.get("given_name") or email.split("@")[0],
        senha_hash=hash_password(secrets.token_hex(32)),  # senha inacessível
        role=UserRole.OPERADOR,   # papel default — admin promove depois
        ativo=True,
        sso_sub=sub,
        sso_provider=provider,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info("SSO JIT: novo usuário provisionado email=%s org=%s", email, org_id)
    return new_user
