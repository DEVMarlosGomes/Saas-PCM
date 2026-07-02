"""
RBAC configurável — Fase 5.3

Mantém os papéis existentes como presets imutáveis (admin, lider, tecnico, operador).
Organizações Enterprise podem criar papéis custom com permissões granulares.

Permissões: <recurso>:<ação>
  Exemplos: os:criar, os:fechar, equipamentos:editar, relatorios:exportar,
            billing:ver, usuarios:gerenciar, estoque:baixa

Verificação via cache em memória (TTL 60s) para não bater no banco em cada request.
"""
from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Optional

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from ..models.core import UserRole

logger = logging.getLogger(__name__)

# ── Mapa de permissões dos papéis preset ─────────────────────────────────────
# Fonte da verdade para papéis built-in; papéis custom vêm do banco.

PRESET_PERMISSIONS: dict[str, set[str]] = {
    "superusuario": {"*:*"},   # tudo
    "admin": {
        "os:*", "equipamentos:*", "usuarios:*", "relatorios:*",
        "billing:*", "dashboard:*", "estoque:*", "preditivo:*",
        "kanban:*", "auditoria:ver", "lgpd:*", "mfa:*", "sso:*",
    },
    "gerente_industrial": {
        "os:*", "equipamentos:*", "relatorios:*", "dashboard:*",
        "preditivo:ver", "kanban:ver", "estoque:ver",
    },
    "supervisor_manutencao": {
        "os:criar", "os:atualizar", "os:fechar", "os:revisar",
        "equipamentos:ver", "equipamentos:editar",
        "relatorios:ver", "dashboard:ver", "kanban:ver",
    },
    "lider_manutencao_eletrica": {
        "os:criar", "os:atualizar", "os:fechar", "os:revisar",
        "equipamentos:ver", "kanban:ver", "estoque:ver",
    },
    "lider_manutencao_mecanica": {
        "os:criar", "os:atualizar", "os:fechar", "os:revisar",
        "equipamentos:ver", "kanban:ver", "estoque:ver",
    },
    "analista_manutencao": {
        "os:ver", "os:criar", "relatorios:ver", "preditivo:ver", "dashboard:ver",
    },
    "engenheiro_manutencao": {
        "os:*", "equipamentos:*", "relatorios:*", "preditivo:*", "dashboard:ver",
    },
    "lider": {
        "os:criar", "os:atualizar", "os:fechar", "os:revisar",
        "equipamentos:ver", "kanban:ver", "estoque:ver", "usuarios:ver",
    },
    "supervisor_producao": {
        "os:criar", "equipamentos:ver", "kanban:ver", "dashboard:ver",
    },
    "lider_producao": {
        "os:criar", "equipamentos:ver", "kanban:ver",
    },
    "tecnico": {
        "os:ver", "os:atualizar", "equipamentos:ver", "estoque:ver",
    },
    "operador": {
        "os:criar", "os:ver", "equipamentos:ver",
    },
}


def _role_str(role) -> str:
    return role.value if hasattr(role, "value") else str(role)


def has_permission(role, recurso: str, acao: str) -> bool:
    """
    Verifica se um papel preset tem permissão para <recurso>:<acao>.
    Suporta wildcard: admin tem os:* → True para os:criar, os:fechar, etc.
    Para papéis custom (não preset), use has_custom_permission().
    """
    perms = PRESET_PERMISSIONS.get(_role_str(role), set())
    if "*:*" in perms:
        return True
    target = f"{recurso}:{acao}"
    if target in perms:
        return True
    if f"{recurso}:*" in perms:
        return True
    return False


# ── Permissões custom (banco) ─────────────────────────────────────────────────

_perm_cache: dict[str, tuple[set[str], float]] = {}
_CACHE_TTL = 60.0  # segundos


def _cache_key(user_id: str, org_id: str) -> str:
    return f"{org_id}:{user_id}"


def invalidate_cache(user_id: str, org_id: str):
    _perm_cache.pop(_cache_key(user_id, org_id), None)


def get_user_custom_permissions(db: Session, user_id: str, org_id: str) -> set[str]:
    """Retorna permissões dos papéis custom atribuídos ao usuário."""
    key = _cache_key(user_id, org_id)
    cached = _perm_cache.get(key)
    if cached and (time.monotonic() - cached[1]) < _CACHE_TTL:
        return cached[0]

    rows = db.execute(sa_text("""
        SELECT p.recurso, p.acao
        FROM usuario_papeis up
        JOIN papeis pa ON pa.id = up.papel_id
        JOIN papel_permissoes pp ON pp.papel_id = pa.id
        JOIN permissoes p ON p.id = pp.permissao_id
        WHERE up.user_id = :uid AND pa.organization_id = :oid
    """), {"uid": user_id, "oid": org_id}).fetchall()

    perms: set[str] = {f"{r.recurso}:{r.acao}" for r in rows}
    _perm_cache[key] = (perms, time.monotonic())
    return perms


def has_custom_permission(db: Session, user_id: str, org_id: str, recurso: str, acao: str) -> bool:
    perms = get_user_custom_permissions(db, user_id, org_id)
    if "*:*" in perms:
        return True
    if f"{recurso}:{acao}" in perms:
        return True
    if f"{recurso}:*" in perms:
        return True
    return False


# ── Seed de permissões built-in ───────────────────────────────────────────────

def seed_permissoes(db: Session):
    """Cria as permissões granulares na tabela `permissoes` se não existirem."""
    all_perms = [
        ("os", "criar"), ("os", "ver"), ("os", "atualizar"), ("os", "fechar"),
        ("os", "revisar"), ("os", "excluir"),
        ("equipamentos", "criar"), ("equipamentos", "ver"), ("equipamentos", "editar"), ("equipamentos", "excluir"),
        ("usuarios", "criar"), ("usuarios", "ver"), ("usuarios", "gerenciar"),
        ("relatorios", "ver"), ("relatorios", "exportar"),
        ("billing", "ver"), ("billing", "gerenciar"),
        ("dashboard", "ver"),
        ("estoque", "ver"), ("estoque", "baixa"), ("estoque", "entrada"), ("estoque", "gerenciar"),
        ("preditivo", "ver"), ("preditivo", "configurar"),
        ("kanban", "ver"),
        ("auditoria", "ver"),
        ("lgpd", "exportar"), ("lgpd", "processar"),
        ("mfa", "configurar"),
        ("sso", "configurar"),
    ]
    for recurso, acao in all_perms:
        try:
            db.execute(sa_text("""
                INSERT INTO permissoes (id, recurso, acao, descricao)
                VALUES (gen_random_uuid(), :r, :a, :d)
                ON CONFLICT (recurso, acao) DO NOTHING
            """), {"r": recurso, "a": acao, "d": f"{acao.capitalize()} {recurso}"})
        except Exception:
            pass
    try:
        db.commit()
    except Exception:
        db.rollback()


def create_preset_roles(db: Session, org_id: str):
    """Cria papéis preset para uma nova organização."""
    presets = [
        ("admin", "Administrador — acesso total"),
        ("lider", "Líder de Manutenção — aprova OS e gerencia equipe"),
        ("tecnico", "Técnico — executa OS"),
        ("operador", "Operador — abre OS"),
    ]
    for nome, desc in presets:
        try:
            db.execute(sa_text("""
                INSERT INTO papeis (id, organization_id, nome, descricao, is_preset)
                VALUES (gen_random_uuid(), :oid, :nome, :desc, TRUE)
                ON CONFLICT (organization_id, nome) DO NOTHING
            """), {"oid": org_id, "nome": nome, "desc": desc})
        except Exception:
            pass
    try:
        db.commit()
    except Exception:
        db.rollback()
