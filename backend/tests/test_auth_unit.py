"""
Testes unitários de autenticação — Fase 4.3

Cobre: hash de senha, JWT (create/verify/expirado), brute-force lockout.
Não requer servidor ou banco de dados real.
"""
import os
import pytest

# JWT_SECRET precisa estar presente antes de importar deps
os.environ.setdefault("JWT_SECRET", "test-secret-32-characters-for-test!!")

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import jwt as _jwt

from app.deps import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, get_jwt_secret,
    check_brute_force, record_failed_attempt, clear_failed_attempts,
    JWT_ALGORITHM,
)


# ── Senha ──────────────────────────────────────────────────────────────────────

def test_hash_password_returns_bcrypt_hash():
    h = hash_password("Aurix@2025")
    assert h.startswith("$2b$") or h.startswith("$2a$")


def test_verify_password_correct():
    h = hash_password("Aurix@2025")
    assert verify_password("Aurix@2025", h) is True


def test_verify_password_wrong():
    h = hash_password("Aurix@2025")
    assert verify_password("WrongPass", h) is False


def test_hash_password_different_each_call():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2  # salt diferente


# ── JWT ────────────────────────────────────────────────────────────────────────

def test_create_access_token_payload():
    token = create_access_token("user-uuid-123", "user@example.com")
    payload = _jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == "user-uuid-123"
    assert payload["email"] == "user@example.com"
    assert payload["type"] == "access"


def test_create_refresh_token_payload():
    token = create_refresh_token("user-uuid-456")
    payload = _jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == "user-uuid-456"
    assert payload["type"] == "refresh"


def test_access_token_expires_correctly():
    token = create_access_token("uid", "e@e.com")
    payload = _jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    # access token deve expirar em ~8h (480min)
    assert timedelta(hours=7) < (exp - now) < timedelta(hours=9)


def test_expired_token_raises():
    secret = get_jwt_secret()
    token = _jwt.encode(
        {"sub": "uid", "type": "access", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        secret,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(_jwt.ExpiredSignatureError):
        _jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])


def test_token_wrong_secret_raises():
    token = create_access_token("uid", "e@e.com")
    with pytest.raises(_jwt.InvalidSignatureError):
        _jwt.decode(token, "wrong-secret", algorithms=[JWT_ALGORITHM])


# ── Brute-force ────────────────────────────────────────────────────────────────

def _make_db():
    return MagicMock()


def test_check_brute_force_no_attempt():
    db = _make_db()
    db.query.return_value.filter.return_value.first.return_value = None
    assert check_brute_force(db, "user@test.com") is True


def test_check_brute_force_locked():
    from app.models.core import LoginAttempt
    db = _make_db()
    attempt = MagicMock()
    attempt.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.query.return_value.filter.return_value.first.return_value = attempt
    assert check_brute_force(db, "user@test.com") is False


def test_check_brute_force_expired_lock():
    db = _make_db()
    attempt = MagicMock()
    attempt.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.query.return_value.filter.return_value.first.return_value = attempt
    result = check_brute_force(db, "user@test.com")
    assert result is True
    assert attempt.attempts == 0
    assert attempt.locked_until is None


def test_record_failed_attempt_creates_new():
    db = _make_db()
    db.query.return_value.filter.return_value.first.return_value = None
    record_failed_attempt(db, "new@test.com")
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_record_failed_attempt_locks_at_five():
    db = _make_db()
    attempt = MagicMock()
    attempt.attempts = 4
    attempt.locked_until = None
    db.query.return_value.filter.return_value.first.return_value = attempt
    record_failed_attempt(db, "user@test.com")
    assert attempt.attempts == 5
    assert attempt.locked_until is not None


def test_clear_failed_attempts():
    db = _make_db()
    db.query.return_value.filter.return_value.delete.return_value = 1
    clear_failed_attempts(db, "user@test.com")
    db.commit.assert_called_once()
