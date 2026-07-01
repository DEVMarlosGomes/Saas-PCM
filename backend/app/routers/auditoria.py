from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from sqlalchemy.orm import Session

from ..deps import (
    get_db, get_current_user, check_plan_limit, check_plan_feature,
    criar_notificacao, create_audit_log, send_email_notification,
    hash_password, verify_password, create_access_token, create_refresh_token,
    set_auth_cookies, get_jwt_secret, get_org_usage, get_next_os_number,
    check_brute_force, record_failed_attempt, clear_failed_attempts,
    JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    SMTP_HOST, SMTP_USER,
)
from ..models.core import (
    Organization, User, Grupo, Subgrupo, Equipamento, OrdemServico,
    CustoOS, Setor, PlanoPreventivo, AuditoriaLog, LoginAttempt,
    PasswordResetToken, PaymentTransaction, OSEquipe, Colaborador,
    OSHistorico, OSExcecaoArea, Notificacao, ConfiguracaoMonitoramento,
    LeituraSensor, AlertaPreditivo,
    UserRole, TipoOS, PrioridadeOS, StatusOS, TipoCusto, PlanoSaaS, PLAN_LIMITS,
)
from ..schemas.main import (
    OrganizationCreate, OrganizationResponse,
    UserRegister, UserLogin, UserResponse, UserCreate,
    TechnicianSessionRequest, TecnicoLoginRequest,
    SetorCreate, SetorResponse, GrupoCreate, GrupoResponse,
    SubgrupoCreate, SubgrupoResponse,
    EquipamentoCreate, EquipamentoResponse,
    OSCreate, OSUpdate, OSResponse, OSEquipeCreate, OSEquipeResponse,
    OSHistoricoResponse, OSExcecaoAreaResponse, CustoMaoObraUpdate,
    CustoCreate, CustoResponse, PlanoCreate, PlanoResponse,
    DashboardKPIs, BillingPlanResponse, CheckoutRequest,
    ColaboradorCreate, ColaboradorUpdate, ColaboradorResponse,
)
from ..settings import settings
import jwt as _jwt

router = APIRouter(tags=["Auditoria"])


@router.get("/auditoria")
async def list_auditoria(
    entidade: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")

    query = db.query(AuditoriaLog).filter(AuditoriaLog.organization_id == user.organization_id)
    if entidade:
        query = query.filter(AuditoriaLog.entidade == entidade)

    logs = query.order_by(AuditoriaLog.created_at.desc()).limit(limit).all()

    user_cache = {}
    def _get_user_nome(uid):
        if not uid: return None
        key = str(uid)
        if key not in user_cache:
            u = db.query(User).filter(User.id == uid).first()
            user_cache[key] = u.nome if u else None
        return user_cache[key]

    return [{
        "id": str(l.id),
        "user_id": str(l.user_id) if l.user_id else None,
        "user_nome": _get_user_nome(l.user_id),
        "entidade": l.entidade,
        "entidade_id": str(l.entidade_id),
        "acao": l.acao,
        "dados_novos": l.dados_novos,
        "dados_anteriores": l.dados_anteriores,
        "created_at": l.created_at.isoformat()
    } for l in logs]

@router.get("/auditoria/os/{os_id}")
async def get_os_audit_dossier(os_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Dossier completo de auditoria de uma OS: timeline, custos, equipe, notificações, logs."""
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")

    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")

    # ── OS completa ──────────────────────────────────────────────────────────
    os_data = _build_os_response(os_obj, db, user=user)

    # ── Histórico de status ──────────────────────────────────────────────────
    historico = db.query(OSHistorico).filter(
        OSHistorico.os_id == os_id
    ).order_by(OSHistorico.timestamp.asc()).all()
    historico_data = [{
        "id": str(h.id),
        "status_novo": h.status_novo,
        "etapa_label": h.etapa_label,
        "timestamp": h.timestamp.isoformat(),
        "user_id": str(h.user_id) if h.user_id else None,
        "user_nome": h.user_nome,
    } for h in historico]

    # ── Custos ───────────────────────────────────────────────────────────────
    custos = db.query(CustoOS).filter(
        CustoOS.ordem_servico_id == os_id,
        CustoOS.organization_id == user.organization_id,
    ).order_by(CustoOS.created_at.asc()).all()
    _usr_cache: dict = {}
    def _nome(uid):
        if not uid: return None
        k = str(uid)
        if k not in _usr_cache:
            u = db.query(User).filter(User.id == uid).first()
            _usr_cache[k] = u.nome if u else None
        return _usr_cache[k]

    custos_data = [{
        "id": str(c.id),
        "tipo": c.tipo.value,
        "descricao": c.descricao,
        "valor": float(c.valor),
        "quantidade": float(c.quantidade),
        "total": round(float(c.valor) * float(c.quantidade), 2),
        "criado_por_nome": _nome(getattr(c, 'criado_por', None)),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    } for c in custos]

    # ── Equipe ───────────────────────────────────────────────────────────────
    equipe = db.query(OSEquipe).filter(
        OSEquipe.os_id == os_id
    ).order_by(OSEquipe.adicionado_em.asc()).all()
    equipe_data = [{
        "id": str(m.id),
        "nome_membro": m.nome_membro,
        "cracha": m.cracha,
        "especialidade": m.especialidade,
        "adicionado_em": m.adicionado_em.isoformat() if m.adicionado_em else None,
        "adicionado_por_nome": _nome(m.adicionado_por),
    } for m in equipe]

    # ── Notificações vinculadas à OS ─────────────────────────────────────────
    notifs = db.query(Notificacao).filter(
        Notificacao.os_id == os_id,
        Notificacao.org_id == user.organization_id,
    ).order_by(Notificacao.criada_em.asc()).all()
    notifs_data = [{
        "id": str(n.id),
        "tipo": n.tipo,
        "titulo": n.titulo,
        "mensagem": n.mensagem,
        "destinatario_nome": _nome(n.destinatario_id),
        "lida": n.lida,
        "criada_em": n.criada_em.isoformat(),
        "lida_em": n.lida_em.isoformat() if n.lida_em else None,
    } for n in notifs]

    # ── Logs de auditoria para esta OS ───────────────────────────────────────
    audit_logs = db.query(AuditoriaLog).filter(
        AuditoriaLog.entidade_id == os_id,
        AuditoriaLog.organization_id == user.organization_id,
    ).order_by(AuditoriaLog.created_at.asc()).all()
    audit_data = [{
        "id": str(l.id),
        "acao": l.acao,
        "user_nome": _nome(l.user_id),
        "dados_novos": l.dados_novos,
        "dados_anteriores": l.dados_anteriores,
        "created_at": l.created_at.isoformat(),
    } for l in audit_logs]

    return {
        "os": os_data,
        "historico": historico_data,
        "custos": custos_data,
        "equipe": equipe_data,
        "notificacoes": notifs_data,
        "audit_logs": audit_data,
    }

# ========== NOTIFICAÇÕES ENDPOINTS ==========
