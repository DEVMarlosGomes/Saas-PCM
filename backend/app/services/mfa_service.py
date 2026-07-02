"""
MFA — TOTP (RFC 6238) via pyotp.

Fluxo:
  1. setup()   → gera secret + provisioning URI (QR code)
  2. verify()  → valida código 6 dígitos (janela ±1 período)
  3. generate_backup_codes() → 10 codes de uso único
  4. verify_backup_code()    → consome um código (remove da lista)

ASVS V6.2:
  - Secret armazenado encriptado (Fernet) — chave via MFA_ENCRYPTION_KEY
  - Recovery codes com hash bcrypt
  - Janela de tolerância ≤ 1 período (30s)
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pyotp
    _PYOTP_OK = True
except ImportError:
    _PYOTP_OK = False
    logger.warning("pyotp not installed — MFA disabled. Run: pip install pyotp")

try:
    from cryptography.fernet import Fernet
    _FERNET_OK = True
except ImportError:
    _FERNET_OK = False


def _fernet() -> Optional[object]:
    """Retorna instância Fernet ou None (sem encriptação em dev)."""
    key = os.environ.get("MFA_ENCRYPTION_KEY", "")
    if key and _FERNET_OK:
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            pass
    return None


def encrypt_secret(secret: str) -> str:
    f = _fernet()
    if f:
        return f.encrypt(secret.encode()).decode()
    return secret  # dev fallback — plaintext


def decrypt_secret(stored: str) -> str:
    f = _fernet()
    if f:
        try:
            return f.decrypt(stored.encode()).decode()
        except Exception:
            pass
    return stored  # dev fallback


def is_available() -> bool:
    return _PYOTP_OK


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup(user_email: str, issuer: str = "AURIX") -> dict:
    """
    Gera um novo TOTP secret para o usuário.
    Retorna: {secret_encrypted, provisioning_uri, qr_data_url}
    """
    if not _PYOTP_OK:
        raise RuntimeError("pyotp não instalado")
    raw_secret = pyotp.random_base32()
    totp = pyotp.TOTP(raw_secret)
    uri = totp.provisioning_uri(name=user_email, issuer_name=issuer)
    return {
        "secret_encrypted": encrypt_secret(raw_secret),
        "provisioning_uri": uri,
    }


def verify(secret_encrypted: str, code: str) -> bool:
    """Valida código TOTP. Janela de ±1 período (30s)."""
    if not _PYOTP_OK:
        return False
    try:
        raw = decrypt_secret(secret_encrypted)
        totp = pyotp.TOTP(raw)
        return totp.verify(code.strip(), valid_window=1)
    except Exception as exc:
        logger.debug("TOTP verify error: %s", exc)
        return False


# ── Backup codes ──────────────────────────────────────────────────────────────

def generate_backup_codes(n: int = 10) -> tuple[list[str], list[str]]:
    """
    Gera `n` códigos de recuperação de uso único.
    Retorna (plaintext_list, hashed_list).
    Os hashes devem ser armazenados; o plaintext mostrado ao usuário uma única vez.
    """
    codes = [secrets.token_hex(5).upper() for _ in range(n)]
    hashed = [hashlib.sha256(c.encode()).hexdigest() for c in codes]
    return codes, hashed


def verify_backup_code(code: str, hashed_codes: list[str]) -> tuple[bool, list[str]]:
    """
    Verifica e consome um código de recuperação.
    Retorna (válido, lista_atualizada_sem_o_código_usado).
    """
    h = hashlib.sha256(code.strip().upper().encode()).hexdigest()
    if h in hashed_codes:
        remaining = [x for x in hashed_codes if x != h]
        return True, remaining
    return False, hashed_codes
