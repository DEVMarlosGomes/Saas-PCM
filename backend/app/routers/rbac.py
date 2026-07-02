"""
RBAC — gestão de papéis e permissões custom (Fase 5.3)

GET  /rbac/permissoes                   → lista todas as permissões disponíveis
GET  /rbac/papeis                       → lista papéis da org
POST /rbac/papeis                       → cria papel custom
PUT  /rbac/papeis/{id}/permissoes       → define permissões do papel
POST /rbac/papeis/{id}/usuarios         → atribui papel a usuário
DELETE /rbac/papeis/{id}/usuarios/{uid} → remove papel de usuário
GET  /rbac/me                           → permissões efetivas do usuário atual
"""
from __future__ import annotations

import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user, require_role, create_audit_log
from ..models.core import User, UserRole
from ..services import rbac_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rbac"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class PapelCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None


class PapelPermissoesUpdate(BaseModel):
    permissao_ids: List[str]


class AtribuirPapelRequest(BaseModel):
    user_id: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/rbac/permissoes")
async def list_permissoes(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERUSUARIO)),
    db: Session = Depends(get_db),
):
    rows = db.execute(sa_text(
        "SELECT id, recurso, acao, descricao FROM permissoes ORDER BY recurso, acao"
    )).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/rbac/papeis")
async def list_papeis(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERUSUARIO)),
    db: Session = Depends(get_db),
):
    rows = db.execute(sa_text("""
        SELECT p.id, p.nome, p.descricao, p.is_preset,
               COUNT(pp.permissao_id) AS num_permissoes
        FROM papeis p
        LEFT JOIN papel_permissoes pp ON pp.papel_id = p.id
        WHERE p.organization_id = :oid
        GROUP BY p.id ORDER BY p.is_preset DESC, p.nome
    """), {"oid": user.organization_id}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/rbac/papeis")
async def create_papel(
    body: PapelCreate,
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERUSUARIO)),
    db: Session = Depends(get_db),
):
    papel_id = uuid.uuid4()
    try:
        db.execute(sa_text("""
            INSERT INTO papeis (id, organization_id, nome, descricao, is_preset)
            VALUES (:id, :oid, :nome, :desc, FALSE)
        """), {"id": papel_id, "oid": user.organization_id,
               "nome": body.nome, "desc": body.descricao})
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, f"Papel '{body.nome}' já existe nesta organização.")

    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="papel", entidade_id=str(papel_id), acao="criar",
        ip=request.client.host if request.client else None,
    )
    return {"id": str(papel_id), "nome": body.nome}


@router.put("/rbac/papeis/{papel_id}/permissoes")
async def set_papel_permissoes(
    papel_id: str,
    body: PapelPermissoesUpdate,
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERUSUARIO)),
    db: Session = Depends(get_db),
):
    # Verificar ownership
    papel = db.execute(sa_text(
        "SELECT id, is_preset FROM papeis WHERE id=:id AND organization_id=:oid"
    ), {"id": papel_id, "oid": user.organization_id}).fetchone()
    if not papel:
        raise HTTPException(404)
    if papel.is_preset:
        raise HTTPException(403, "Papéis preset não podem ser modificados.")

    db.execute(sa_text("DELETE FROM papel_permissoes WHERE papel_id=:pid"), {"pid": papel_id})
    for perm_id in body.permissao_ids:
        db.execute(sa_text("""
            INSERT INTO papel_permissoes (papel_id, permissao_id)
            VALUES (:pid, :permid) ON CONFLICT DO NOTHING
        """), {"pid": papel_id, "permid": perm_id})
    db.commit()

    # Invalida cache para todos os usuários com este papel
    db.execute(sa_text("SELECT user_id FROM usuario_papeis WHERE papel_id=:pid"), {"pid": papel_id})

    return {"ok": True, "num_permissoes": len(body.permissao_ids)}


@router.post("/rbac/papeis/{papel_id}/usuarios")
async def atribuir_papel(
    papel_id: str,
    body: AtribuirPapelRequest,
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERUSUARIO)),
    db: Session = Depends(get_db),
):
    papel = db.execute(sa_text(
        "SELECT id FROM papeis WHERE id=:id AND organization_id=:oid"
    ), {"id": papel_id, "oid": user.organization_id}).fetchone()
    if not papel:
        raise HTTPException(404)

    try:
        db.execute(sa_text("""
            INSERT INTO usuario_papeis (user_id, papel_id, granted_by)
            VALUES (:uid, :pid, :gby) ON CONFLICT DO NOTHING
        """), {"uid": body.user_id, "pid": papel_id, "gby": user.id})
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(422, str(e))

    rbac_service.invalidate_cache(body.user_id, str(user.organization_id))

    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="usuario_papel", entidade_id=body.user_id, acao="atribuir_papel",
        dados_novos=f'{{"papel_id": "{papel_id}"}}',
        ip=request.client.host if request.client else None,
    )
    return {"ok": True}


@router.delete("/rbac/papeis/{papel_id}/usuarios/{target_user_id}")
async def remover_papel(
    papel_id: str,
    target_user_id: str,
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERUSUARIO)),
    db: Session = Depends(get_db),
):
    db.execute(sa_text(
        "DELETE FROM usuario_papeis WHERE papel_id=:pid AND user_id=:uid"
    ), {"pid": papel_id, "uid": target_user_id})
    db.commit()
    rbac_service.invalidate_cache(target_user_id, str(user.organization_id))
    return {"ok": True}


@router.get("/rbac/me")
async def my_permissions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna permissões efetivas do usuário atual (preset + custom)."""
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    preset = rbac_service.PRESET_PERMISSIONS.get(role_str, set())
    custom = rbac_service.get_user_custom_permissions(db, str(user.id), str(user.organization_id))
    all_perms = sorted(preset | custom)
    return {
        "role": role_str,
        "preset_permissions": sorted(preset),
        "custom_permissions": sorted(custom),
        "effective_permissions": all_perms,
    }
