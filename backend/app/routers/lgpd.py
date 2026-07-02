"""
LGPD — endpoints de privacidade e proteção de dados (Fase 5.5)

GET  /lgpd/export              → exporta todos os dados pessoais do titular
POST /lgpd/delete-request      → solicita exclusão/anonimização
GET  /lgpd/requests            → lista solicitações do usuário atual
POST /lgpd/consent             → registra/atualiza consentimento
GET  /lgpd/consent             → lista consentimentos ativos
POST /lgpd/process/{id}        → admin processa solicitação pendente

LGPD Art. 18 — direitos do titular:
  - Acesso (export)
  - Eliminação (delete-request)
  - Portabilidade (export JSON/CSV)
  - Revogação de consentimento
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user, require_role, create_audit_log
from ..models.core import (
    AuditoriaLog, Equipamento, Notificacao, OrdemServico,
    Organization, User, UserRole,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["lgpd"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ConsentimentoRequest(BaseModel):
    finalidade: str   # ex.: "notificacoes_email", "analytics", "whatsapp"
    consentiu: bool


class DeleteRequest(BaseModel):
    motivo: Optional[str] = None
    confirmar: bool = False   # deve ser True para enviar


class ProcessarSolicitacaoRequest(BaseModel):
    acao: str    # "aprovar" | "rejeitar"
    resposta: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mask_email(email: str) -> str:
    parts = email.split("@")
    if len(parts) != 2:
        return "***@***"
    local = parts[0]
    domain = parts[1]
    masked_local = local[:2] + "***" if len(local) > 2 else "***"
    return f"{masked_local}@{domain}"


def _anonymize_user(db: Session, user: User):
    """Anonimiza dados pessoais do usuário (não exclui a conta — preserva integridade referencial)."""
    uid = str(user.id)
    anon_email = f"anon_{uid[:8]}@removed.lgpd"
    user.email = anon_email
    user.nome = "Usuário Removido"
    user.employee_id = None
    user.generic_session_sector = None
    user.ativo = False
    if hasattr(user, "whatsapp_numero"):
        user.whatsapp_numero = None
        user.whatsapp_optin = False
    db.commit()
    logger.info("LGPD: user %s anonymized", uid)


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/lgpd/export")
async def lgpd_export(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retorna todos os dados pessoais do titular em JSON (Art. 18 LGPD — portabilidade).
    """
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()

    os_list = db.query(OrdemServico).filter(
        OrdemServico.solicitante_id == user.id,
    ).limit(500).all()

    audits = db.query(AuditoriaLog).filter(
        AuditoriaLog.user_id == user.id,
    ).limit(500).all()

    notifs = db.query(Notificacao).filter(
        Notificacao.destinatario_id == user.id,
    ).limit(200).all()

    export = {
        "exportado_em": datetime.now(timezone.utc).isoformat(),
        "titular": {
            "id": str(user.id),
            "email": user.email,
            "nome": user.nome,
            "role": str(user.role),
            "setor": user.setor,
            "employee_id": user.employee_id,
            "ativo": user.ativo,
            "criado_em": user.created_at.isoformat() if user.created_at else None,
        },
        "organizacao": {
            "id": str(org.id) if org else None,
            "nome": org.nome if org else None,
        },
        "ordens_servico_abertas": [
            {
                "id": str(o.id), "numero": o.numero,
                "status": str(o.status),
                "criada_em": o.created_at.isoformat() if o.created_at else None,
            }
            for o in os_list
        ],
        "auditoria": [
            {
                "acao": a.acao, "entidade": a.entidade,
                "timestamp": a.criado_em.isoformat() if a.criado_em else None,
            }
            for a in audits
        ],
        "notificacoes": [
            {"tipo": n.tipo, "titulo": n.titulo, "criada_em": n.criada_em.isoformat() if n.criada_em else None}
            for n in notifs
        ],
    }

    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="user", entidade_id=str(user.id), acao="lgpd_export",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return JSONResponse(content=export, headers={
        "Content-Disposition": f'attachment; filename="lgpd-export-{str(user.id)[:8]}.json"',
    })


# ── Delete / anonimização ─────────────────────────────────────────────────────

@router.post("/lgpd/delete-request")
async def lgpd_delete_request(
    body: DeleteRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra solicitação de exclusão/anonimização de dados pessoais."""
    if not body.confirmar:
        raise HTTPException(400, "Confirme a solicitação enviando confirmar=true.")

    # Verificar se já há solicitação pendente
    existing = db.execute(sa_text(
        "SELECT id FROM lgpd_solicitacoes WHERE user_id=:uid AND status='pendente'"
    ), {"uid": user.id}).fetchone()
    if existing:
        raise HTTPException(409, "Já existe uma solicitação de exclusão pendente para este usuário.")

    sol_id = uuid.uuid4()
    db.execute(sa_text("""
        INSERT INTO lgpd_solicitacoes (id, user_id, organization_id, tipo, status, solicitado_em)
        VALUES (:id, :uid, :oid, 'exclusao', 'pendente', now())
    """), {"id": sol_id, "uid": user.id, "oid": user.organization_id})
    db.commit()

    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="lgpd_solicitacao", entidade_id=str(sol_id), acao="lgpd_delete_request",
        dados_novos=json.dumps({"motivo": body.motivo or ""}),
        ip=request.client.host if request.client else None,
    )
    return {"id": str(sol_id), "message": "Solicitação registrada. Será processada em até 15 dias úteis."}


@router.get("/lgpd/requests")
async def lgpd_list_requests(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(sa_text("""
        SELECT id, tipo, status, solicitado_em, processado_em, resposta
        FROM lgpd_solicitacoes WHERE user_id = :uid ORDER BY solicitado_em DESC
    """), {"uid": user.id}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.post("/lgpd/process/{sol_id}")
async def lgpd_process(
    sol_id: str,
    body: ProcessarSolicitacaoRequest,
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERUSUARIO)),
    db: Session = Depends(get_db),
):
    """Admin processa uma solicitação LGPD (aprovar = anonimiza o usuário)."""
    row = db.execute(sa_text(
        "SELECT * FROM lgpd_solicitacoes WHERE id=:id AND organization_id=:oid"
    ), {"id": sol_id, "oid": user.organization_id}).fetchone()
    if not row:
        raise HTTPException(404)
    if row.status != "pendente":
        raise HTTPException(409, f"Solicitação já está com status '{row.status}'.")

    if body.acao == "aprovar" and row.tipo == "exclusao":
        target = db.query(User).filter(User.id == row.user_id).first()
        if target:
            _anonymize_user(db, target)

    db.execute(sa_text("""
        UPDATE lgpd_solicitacoes
        SET status=:status, processado_em=now(), resposta=:resp
        WHERE id=:id
    """), {"status": "aprovado" if body.acao == "aprovar" else "rejeitado",
           "resp": body.resposta, "id": sol_id})
    db.commit()

    create_audit_log(
        db, org_id=user.organization_id, user_id=user.id,
        entidade="lgpd_solicitacao", entidade_id=sol_id,
        acao=f"lgpd_{body.acao}",
        ip=request.client.host if request.client else None,
    )
    return {"ok": True}


# ── Consentimento ─────────────────────────────────────────────────────────────

@router.post("/lgpd/consent")
async def lgpd_register_consent(
    body: ConsentimentoRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra ou atualiza consentimento do titular para uma finalidade."""
    consent_id = uuid.uuid4()
    db.execute(sa_text("""
        INSERT INTO lgpd_consentimentos
            (id, user_id, organization_id, finalidade, consentiu, ip, user_agent)
        VALUES (:id, :uid, :oid, :fin, :con, :ip, :ua)
    """), {
        "id": consent_id, "uid": user.id, "oid": user.organization_id,
        "fin": body.finalidade, "con": body.consentiu,
        "ip": request.client.host if request.client else None,
        "ua": request.headers.get("user-agent", "")[:500],
    })

    # Atualizar opt-in de WhatsApp se aplicável
    if body.finalidade == "whatsapp":
        if hasattr(user, "whatsapp_optin"):
            user.whatsapp_optin = body.consentiu

    db.commit()
    return {"id": str(consent_id), "finalidade": body.finalidade, "consentiu": body.consentiu}


@router.get("/lgpd/consent")
async def lgpd_list_consent(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista últimos consentimentos por finalidade."""
    rows = db.execute(sa_text("""
        SELECT DISTINCT ON (finalidade)
            finalidade, consentiu, registrado_em
        FROM lgpd_consentimentos
        WHERE user_id = :uid
        ORDER BY finalidade, registrado_em DESC
    """), {"uid": user.id}).fetchall()
    return [dict(r._mapping) for r in rows]
