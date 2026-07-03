from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel
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

router = APIRouter(tags=["Relatórios"])

# ── OS helpers ────────────────────────────────────────────────────────────────
_ETAPAS_LABEL = {
    "aberta": "Abertura da OS",
    "em_atendimento": "Início do atendimento",
    "aguardando_peca": "Aguardando peça/material",
    "aguardando_revisao": "Enviada para revisão",
    "revisada": "Revisão concluída",
    "fechada": "Finalização da OS",
    "cancelada": "OS cancelada",
}

AREAS_MANUTENCAO_LABEL = {
    "eletrica": "Elétrica", "mecanica": "Mecânica", "hidraulica": "Hidráulica",
    "pneumatica": "Pneumática", "instrumentacao": "Instrumentação",
    "civil": "Civil", "utilidades": "Utilidades", "predial": "Predial", "geral": "Geral",
}

_AREAS_KEYWORDS = {
    "eletrica": ["eletric", "electr"], "mecanica": ["mecanic", "mechan"],
    "hidraulica": ["hidraul", "hydraul"], "pneumatica": ["pneumat"],
    "instrumentacao": ["instrument"], "civil": ["civil"],
    "utilidades": ["utilidad"], "predial": ["predial"], "geral": [],
}

_AREA_REVISOR_ROLE = {
    "eletrica": "LIDER_MANUTENCAO_ELETRICA",
    "mecanica": "LIDER_MANUTENCAO_MECANICA",
}

def _record_os_historico(db, os_id, status_novo, user_id=None, user_nome=None, timestamp=None, custom_label=None):
    label = custom_label or _ETAPAS_LABEL.get(status_novo, status_novo)
    db.add(OSHistorico(
        os_id=os_id, status_novo=status_novo, etapa_label=label,
        timestamp=timestamp or datetime.now(timezone.utc),
        user_id=user_id, user_nome=user_nome,
    ))

def _get_revisor(db, org_id, area):
    role_str = _AREA_REVISOR_ROLE.get(area or "")
    if role_str:
        role_enum = getattr(UserRole, role_str, None)
        if role_enum:
            lider = db.query(User).filter(
                User.organization_id == org_id,
                User.role == role_enum, User.ativo == True,
            ).first()
            if lider:
                return lider
    return db.query(User).filter(
        User.organization_id == org_id,
        User.role == UserRole.LIDER, User.ativo == True,
    ).first()

def _area_compativel(area_os, setor, cargo):
    if not area_os or area_os == "geral":
        return True
    import unicodedata
    def _norm(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
    keywords = _AREAS_KEYWORDS.get(area_os, [])
    if not keywords:
        return True
    haystack = _norm(f"{setor} {cargo}")
    return any(_norm(kw) in haystack for kw in keywords)

def calculate_sla(prioridade, tempo_resposta):
    sla_map = {PrioridadeOS.CRITICA: 30, PrioridadeOS.ALTA: 60, PrioridadeOS.MEDIA: 120, PrioridadeOS.BAIXA: 480}
    return tempo_resposta <= sla_map.get(prioridade, 120)

def check_reincidencia(db, org_id, equipamento_id, falha_tipo):
    if not falha_tipo:
        return False
    thirty = datetime.now(timezone.utc) - timedelta(days=30)
    count = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.equipamento_id == equipamento_id,
        OrdemServico.falha_tipo == falha_tipo,
        OrdemServico.created_at >= thirty,
    ).count()
    return count > 1

def _build_os_response(o, db, user=None):
    from sqlalchemy import text as _sa_text
    custo_parada = None
    equipamento_nome = equipamento_codigo = equipamento_localizacao = equipamento_setor = None
    equip = db.query(Equipamento).filter(Equipamento.id == o.equipamento_id).first()
    if equip:
        equipamento_nome = equip.nome
        equipamento_codigo = equip.codigo
        equipamento_localizacao = equip.localizacao
        if o.tempo_total and equip.valor_hora:
            custo_parada = round((o.tempo_total / 60) * equip.valor_hora, 2)
        row = db.execute(_sa_text("SELECT setor FROM equipamentos WHERE id = :id"),
                         {"id": str(equip.id)}).fetchone()
        equipamento_setor = row[0] if row else None

    solicitante_nome = getattr(o, 'solicitante_nome', None)
    if not solicitante_nome and o.solicitante_id:
        sol = db.query(User).filter(User.id == o.solicitante_id).first()
        if sol:
            solicitante_nome = sol.nome

    tecnico_nome = tecnico_emp_id = None
    if o.tecnico_id:
        tec = db.query(User).filter(User.id == o.tecnico_id).first()
        if tec:
            tecnico_nome = tec.nome
            tecnico_emp_id = tec.employee_id
    _tech_emp = getattr(o, "technician_employee_id", None)
    if not tecnico_nome and _tech_emp:
        col = db.query(Colaborador).filter(
            Colaborador.organization_id == o.organization_id,
            Colaborador.matricula == _tech_emp,
        ).first()
        if col:
            tecnico_nome = col.nome
            tecnico_emp_id = col.matricula

    revisor_nome = None
    if o.revisor_id:
        rev = db.query(User).filter(User.id == o.revisor_id).first()
        if rev:
            revisor_nome = rev.nome

    grupo_nome = None
    if o.grupo_id:
        grp = db.query(Grupo).filter(Grupo.id == o.grupo_id).first()
        if grp:
            grupo_nome = grp.nome

    occ_raw = getattr(o, "occurrences", None)
    try:
        occ_list = json.loads(occ_raw) if occ_raw else []
    except Exception:
        occ_list = []
    occurrences_count = len(occ_list)

    _rel_preenchido_nome = None
    _rel_por_id = getattr(o, 'relatorio_preenchido_por', None)
    if _rel_por_id:
        _rel_user = db.query(User).filter(User.id == _rel_por_id).first()
        if _rel_user:
            _rel_preenchido_nome = _rel_user.nome

    if user is not None and user.role not in (UserRole.ADMIN, UserRole.SUPERUSUARIO):
        if user.role == UserRole.LIDER:
            if equipamento_setor and user.setor and equipamento_setor.upper() != user.setor.upper():
                custo_parada = None
        else:
            custo_parada = None

    _excecoes_matriculas = []
    try:
        _exc_rows = db.query(OSExcecaoArea).filter(OSExcecaoArea.os_id == o.id).all()
        _excecoes_matriculas = [e.matricula for e in _exc_rows]
    except Exception:
        pass

    return OSResponse(
        id=str(o.id), numero=o.numero, equipamento_id=str(o.equipamento_id),
        equipamento_nome=equipamento_nome, equipamento_codigo=equipamento_codigo,
        equipamento_localizacao=equipamento_localizacao, equipamento_setor=equipamento_setor,
        grupo_id=str(o.grupo_id) if o.grupo_id else None, grupo_nome=grupo_nome,
        subgrupo_id=str(o.subgrupo_id) if o.subgrupo_id else None,
        tipo=o.tipo.value, prioridade=o.prioridade.value, status=o.status.value,
        descricao=o.descricao, solucao=o.solucao,
        solicitante_id=str(o.solicitante_id), solicitante_nome=solicitante_nome,
        tecnico_id=str(o.tecnico_id) if o.tecnico_id else None,
        tecnico_nome=tecnico_nome, tecnico_employee_id=tecnico_emp_id,
        technician_employee_id=getattr(o, "technician_employee_id", None),
        revisor_id=str(o.revisor_id) if o.revisor_id else None, revisor_nome=revisor_nome,
        created_at=o.created_at, inicio_atendimento=o.inicio_atendimento,
        fim_atendimento=o.fim_atendimento,
        downtime_start=getattr(o, "downtime_start", None),
        tempo_resposta=o.tempo_resposta, response_time_min=o.tempo_resposta,
        tempo_reparo=o.tempo_reparo, tempo_total=o.tempo_total,
        dentro_sla=o.dentro_sla, falha_tipo=o.falha_tipo,
        falha_modo=o.falha_modo, falha_causa=o.falha_causa,
        failure_group=getattr(o, "failure_group", None),
        reincidente=o.reincidente, occurrences=occ_raw,
        occurrences_count=occurrences_count, organization_id=str(o.organization_id),
        custo_parada=custo_parada, review_deadline=o.review_deadline,
        review_notes=o.review_notes, auto_approved=o.auto_approved or False,
        solicitante_cracha=getattr(o, 'solicitante_cracha', None),
        solicitante_user_id=str(o.solicitante_user_id) if getattr(o, 'solicitante_user_id', None) else None,
        relatorio_o_que_foi_realizado=getattr(o, 'relatorio_o_que_foi_realizado', None),
        relatorio_analise_problema=getattr(o, 'relatorio_analise_problema', None),
        relatorio_preenchido_em=getattr(o, 'relatorio_preenchido_em', None),
        relatorio_preenchido_por_nome=_rel_preenchido_nome,
        custo_mao_obra=getattr(o, 'custo_mao_obra', None),
        horas_trabalhadas=getattr(o, 'horas_trabalhadas', None),
        valor_hora_tecnico=getattr(o, 'valor_hora_tecnico', None),
        area_manutencao=getattr(o, 'area_manutencao', None),
        subarea_manutencao=getattr(o, 'subarea_manutencao', None),
        excecoes_area_matriculas=_excecoes_matriculas,
    )


@router.get("/relatorios/os")
async def relatorio_os(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    status: Optional[str] = None,
    tipo: Optional[str] = None,
    equipamento_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")

    query = db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id)

    if data_inicio:
        try:
            dt = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
            query = query.filter(OrdemServico.created_at >= dt)
        except ValueError:
            pass
    if data_fim:
        try:
            dt = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc)
            query = query.filter(OrdemServico.created_at <= dt)
        except ValueError:
            pass
    if status:
        query = query.filter(OrdemServico.status == status)
    if tipo:
        query = query.filter(OrdemServico.tipo == tipo)
    if equipamento_id:
        query = query.filter(OrdemServico.equipamento_id == equipamento_id)

    ordens = query.order_by(OrdemServico.created_at.desc()).all()

    # Enrich with equipment names
    eq_map = {str(e.id): e.nome for e in db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()}
    user_map = {str(u.id): u.nome for u in db.query(User).filter(User.organization_id == user.organization_id).all()}

    rows = []
    for o in ordens:
        rows.append({
            "numero": o.numero,
            "equipamento": eq_map.get(str(o.equipamento_id), "—"),
            "tipo": o.tipo.value,
            "prioridade": o.prioridade.value,
            "status": o.status.value,
            "descricao": o.descricao,
            "solicitante": user_map.get(str(o.solicitante_id), "—"),
            "tecnico": user_map.get(str(o.tecnico_id), "—") if o.tecnico_id else "—",
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "tempo_resposta_min": o.tempo_resposta,
            "tempo_reparo_min": o.tempo_reparo,
            "tempo_total_min": o.tempo_total,
            "dentro_sla": o.dentro_sla,
            "reincidente": o.reincidente,
            "falha_tipo": o.falha_tipo,
        })

    total = len(ordens)
    por_status = {}
    for o in ordens:
        por_status[o.status.value] = por_status.get(o.status.value, 0) + 1
    por_tipo = {}
    for o in ordens:
        por_tipo[o.tipo.value] = por_tipo.get(o.tipo.value, 0) + 1

    fechadas = [o for o in ordens if o.status in (StatusOS.FECHADA, StatusOS.REVISADA)]
    sla_ok = sum(1 for o in fechadas if o.dentro_sla)
    tempos_reparo = [o.tempo_reparo for o in fechadas if o.tempo_reparo]
    media_reparo = round(sum(tempos_reparo) / len(tempos_reparo), 1) if tempos_reparo else None

    return {
        "total": total,
        "por_status": por_status,
        "por_tipo": por_tipo,
        "sla_percent": round(sla_ok / len(fechadas) * 100, 1) if fechadas else None,
        "media_reparo_min": media_reparo,
        "ordens": rows,
    }

@router.get("/relatorios/custos")
async def relatorio_custos(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    setor: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import text as sa_text
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")
    # Admin: full access; Lider: only their setor; others: forbidden
    if user.role not in (UserRole.ADMIN, UserRole.LIDER):
        raise HTTPException(status_code=403, detail="Apenas administradores e líderes podem acessar o relatório financeiro.")
    # Lider is always restricted to own setor regardless of ?setor param
    if user.role == UserRole.LIDER:
        setor = user.setor

    query = db.query(CustoOS).filter(CustoOS.organization_id == user.organization_id)
    if data_inicio:
        try:
            dt = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
            query = query.filter(CustoOS.created_at >= dt)
        except ValueError:
            pass
    if data_fim:
        try:
            dt = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc)
            query = query.filter(CustoOS.created_at <= dt)
        except ValueError:
            pass

    custos = query.all()

    # Build equipment map with setor (setor is not in ORM — fetch via raw SQL)
    equips = db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()
    equip_setor_map: dict = {}
    if setor:
        setor_rows = db.execute(sa_text(
            "SELECT id, setor FROM equipamentos WHERE organization_id = :org"
        ), {"org": str(user.organization_id)}).fetchall()
        equip_setor_map = {str(r[0]): (r[1] or "").upper() for r in setor_rows}
    eq_map = {str(e.id): e.nome for e in equips}
    os_map = {str(o.id): o for o in db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id).all()}

    # Filter custos by setor if applicable
    if setor:
        setor_upper = setor.upper()
        filtered = []
        for c in custos:
            os_obj = os_map.get(str(c.ordem_servico_id))
            if os_obj and equip_setor_map.get(str(os_obj.equipamento_id), "") == setor_upper:
                filtered.append(c)
        custos = filtered

    # ── Ordens no período para custo mão de obra / parada ──────────────────────
    os_q = db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id)
    if data_inicio:
        try:
            _dt0 = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
            os_q = os_q.filter(OrdemServico.created_at >= _dt0)
        except ValueError:
            pass
    if data_fim:
        try:
            _dt1 = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc)
            os_q = os_q.filter(OrdemServico.created_at <= _dt1)
        except ValueError:
            pass
    ordens_periodo = os_q.all()

    # Valor/hora por equipamento para custo de parada
    eq_valor_hora_map = {str(e.id): (e.valor_hora or 0.0) for e in equips}

    def _parada(o):
        return round((o.tempo_total / 60) * eq_valor_hora_map.get(str(o.equipamento_id), 0), 2) if o.tempo_total else 0.0

    # ── Totais globais ──────────────────────────────────────────────────────────
    total_geral = sum(c.valor * c.quantidade for c in custos)
    custo_mao_obra_total = round(sum(o.custo_mao_obra or 0 for o in ordens_periodo), 2)
    custo_parada_total   = round(sum(_parada(o) for o in ordens_periodo), 2)
    custo_total_completo = round(total_geral + custo_mao_obra_total + custo_parada_total, 2)

    # ── por_tipo (materiais) ─────────────────────────────────────────────────
    por_tipo: dict = {}
    for c in custos:
        tipo = c.tipo.value
        por_tipo[tipo] = por_tipo.get(tipo, 0) + c.valor * c.quantidade

    # ── breakdown por tipo de OS ────────────────────────────────────────────
    _bk_os: dict = {}
    for o in ordens_periodo:
        t = o.tipo.value
        if t not in _bk_os:
            _bk_os[t] = {"materiais": 0.0, "mao_obra": 0.0, "parada": 0.0}
        _bk_os[t]["mao_obra"] += (o.custo_mao_obra or 0)
        _bk_os[t]["parada"]   += _parada(o)
    for c in custos:
        os_obj = os_map.get(str(c.ordem_servico_id))
        if os_obj:
            t = os_obj.tipo.value
            if t not in _bk_os:
                _bk_os[t] = {"materiais": 0.0, "mao_obra": 0.0, "parada": 0.0}
            _bk_os[t]["materiais"] += c.valor * c.quantidade
    breakdown_por_tipo_os = {
        t: {"total": round(v["materiais"]+v["mao_obra"]+v["parada"], 2), "materiais": round(v["materiais"],2), "mao_obra": round(v["mao_obra"],2), "parada": round(v["parada"],2)}
        for t, v in _bk_os.items()
    }

    # ── breakdown por equipamento (top 5 com componentes) ───────────────────
    _eq_bk: dict = {}
    for o in ordens_periodo:
        eq_nome = eq_map.get(str(o.equipamento_id), "Desconhecido")
        if eq_nome not in _eq_bk:
            _eq_bk[eq_nome] = {"materiais": 0.0, "mao_obra": 0.0, "parada": 0.0}
        _eq_bk[eq_nome]["mao_obra"] += (o.custo_mao_obra or 0)
        _eq_bk[eq_nome]["parada"]   += _parada(o)
    for c in custos:
        os_obj = os_map.get(str(c.ordem_servico_id))
        if os_obj:
            eq_nome = eq_map.get(str(os_obj.equipamento_id), "Desconhecido")
            if eq_nome not in _eq_bk:
                _eq_bk[eq_nome] = {"materiais": 0.0, "mao_obra": 0.0, "parada": 0.0}
            _eq_bk[eq_nome]["materiais"] += c.valor * c.quantidade

    por_equipamento_top5 = sorted([
        {"equipamento": k, "custo_total": round(v["materiais"]+v["mao_obra"]+v["parada"],2),
         "custo_materiais": round(v["materiais"],2), "custo_mao_obra": round(v["mao_obra"],2), "custo_parada": round(v["parada"],2)}
        for k, v in _eq_bk.items()
    ], key=lambda x: x["custo_total"], reverse=True)[:5]

    # compatibilidade legada (total apenas) — mantido para não quebrar clientes
    por_equipamento_legacy = sorted(
        [{"equipamento": k, "total": round(v["materiais"]+v["mao_obra"]+v["parada"], 2)} for k, v in _eq_bk.items()],
        key=lambda x: x["total"], reverse=True
    )

    # ── CAPEX / OPEX ─────────────────────────────────────────────────────────
    # OPEX = corretivas (manutenção não planejada); CAPEX = preventivas + preditivas
    _mat_corr = sum(c.valor * c.quantidade for c in custos
                    if os_map.get(str(c.ordem_servico_id)) and os_map[str(c.ordem_servico_id)].tipo.value == "corretiva")
    _mo_corr  = sum((o.custo_mao_obra or 0) for o in ordens_periodo if o.tipo.value == "corretiva")
    _par_corr = sum(_parada(o) for o in ordens_periodo if o.tipo.value == "corretiva")
    _mat_plan = sum(c.valor * c.quantidade for c in custos
                    if os_map.get(str(c.ordem_servico_id)) and os_map[str(c.ordem_servico_id)].tipo.value in ("preventiva", "preditiva"))
    _mo_plan  = sum((o.custo_mao_obra or 0) for o in ordens_periodo if o.tipo.value in ("preventiva", "preditiva"))
    _par_plan = sum(_parada(o) for o in ordens_periodo if o.tipo.value in ("preventiva", "preditiva"))
    capex_opex = {
        "opex":  round(_mat_corr + _mo_corr + _par_corr, 2),
        "capex": round(_mat_plan + _mo_plan + _par_plan, 2),
    }

    # ── Breakdown mensal (para gráfico de barras empilhadas) ─────────────────
    from collections import defaultdict as _dd
    _mes_bk: dict = _dd(lambda: {"materiais": 0.0, "mao_obra": 0.0, "parada": 0.0})
    for o in ordens_periodo:
        _mk = o.created_at.strftime("%Y-%m") if o.created_at else "—"
        _mes_bk[_mk]["mao_obra"] += (o.custo_mao_obra or 0)
        _mes_bk[_mk]["parada"]   += _parada(o)
    for c in custos:
        os_obj = os_map.get(str(c.ordem_servico_id))
        if os_obj and os_obj.created_at:
            _mk = os_obj.created_at.strftime("%Y-%m")
            _mes_bk[_mk]["materiais"] += c.valor * c.quantidade
    por_mes = sorted([
        {"mes": k, "materiais": round(v["materiais"],2), "mao_obra": round(v["mao_obra"],2), "parada": round(v["parada"],2)}
        for k, v in _mes_bk.items()
    ], key=lambda x: x["mes"])

    return {
        # ── Campos legados (não alterar) ──────────────────────────────────────
        "total_geral": round(total_geral, 2),
        "por_tipo": {k: round(v, 2) for k, v in por_tipo.items()},
        "por_equipamento": por_equipamento_legacy,
        "total_registros": len(custos),
        # ── Novos campos CAPEX/OPEX ───────────────────────────────────────────
        "custos_periodo": {
            "custo_materiais_total": round(total_geral, 2),
            "custo_mao_obra_total": custo_mao_obra_total,
            "custo_parada_total": custo_parada_total,
            "custo_total": custo_total_completo,
            "breakdown_por_tipo_os": breakdown_por_tipo_os,
            "breakdown_por_equipamento": por_equipamento_top5,
            "classificacao_capex_opex": capex_opex,
            "por_mes": por_mes,
        },
    }

@router.get("/relatorios/pareto")
async def relatorio_pareto(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")

    query = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.tipo == TipoOS.CORRETIVA,
    )
    if data_inicio:
        try:
            dt = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
            query = query.filter(OrdemServico.created_at >= dt)
        except ValueError:
            pass
    if data_fim:
        try:
            dt = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc)
            query = query.filter(OrdemServico.created_at <= dt)
        except ValueError:
            pass

    ordens = query.all()
    total = len(ordens)

    eq_map = {str(e.id): e.nome for e in db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()}

    por_tipo_falha: dict = {}
    por_equipamento: dict = {}
    por_causa: dict = {}

    for o in ordens:
        if o.falha_tipo:
            por_tipo_falha[o.falha_tipo] = por_tipo_falha.get(o.falha_tipo, 0) + 1
        eq_nome = eq_map.get(str(o.equipamento_id), "Desconhecido")
        por_equipamento[eq_nome] = por_equipamento.get(eq_nome, 0) + 1
        if o.falha_causa:
            por_causa[o.falha_causa] = por_causa.get(o.falha_causa, 0) + 1

    def build_pareto(d: dict):
        items = sorted([{"label": k, "count": v} for k, v in d.items()], key=lambda x: x["count"], reverse=True)
        acc = 0
        for item in items:
            acc += item["count"]
            item["percent"] = round(item["count"] / total * 100, 1) if total else 0
            item["acumulado"] = round(acc / total * 100, 1) if total else 0
        return items

    return {
        "total_corretivas": total,
        "por_tipo_falha": build_pareto(por_tipo_falha),
        "por_equipamento": build_pareto(por_equipamento),
        "por_causa": build_pareto(por_causa),
    }

@router.get("/relatorios/preventivos")
async def relatorio_preventivos(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")

    now = datetime.now(timezone.utc)
    planos = db.query(PlanoPreventivo).filter(
        PlanoPreventivo.organization_id == user.organization_id,
        PlanoPreventivo.ativo == True,
    ).all()

    eq_map = {str(e.id): e.nome for e in db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()}

    total = len(planos)
    vencidos = [p for p in planos if p.proxima_execucao and p.proxima_execucao < now]
    proximos_7d = [p for p in planos if p.proxima_execucao and now <= p.proxima_execucao <= now + timedelta(days=7)]
    executados = [p for p in planos if p.ultima_execucao]

    compliance = round(len(executados) / total * 100, 1) if total else 0

    rows = []
    for p in sorted(planos, key=lambda x: (x.proxima_execucao or datetime.max.replace(tzinfo=timezone.utc))):
        dias_atraso = None
        if p.proxima_execucao and p.proxima_execucao < now:
            dias_atraso = (now - p.proxima_execucao).days
        rows.append({
            "id": str(p.id),
            "nome": p.nome,
            "equipamento": eq_map.get(str(p.equipamento_id), "—"),
            "frequencia_dias": p.frequencia_dias,
            "ultima_execucao": p.ultima_execucao.isoformat() if p.ultima_execucao else None,
            "proxima_execucao": p.proxima_execucao.isoformat() if p.proxima_execucao else None,
            "status": "vencido" if dias_atraso is not None else ("proximo" if p in proximos_7d else "ok"),
            "dias_atraso": dias_atraso,
        })

    return {
        "total": total,
        "compliance_percent": compliance,
        "vencidos": len(vencidos),
        "proximos_7d": len(proximos_7d),
        "executados_alguma_vez": len(executados),
        "planos": rows,
    }

@router.get("/relatorios/kpis")
async def relatorio_kpis(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")
    now = datetime.now(timezone.utc)
    dt_inicio = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc) if data_inicio else now - timedelta(days=30)
    dt_fim = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc) if data_fim else now

    os_list = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.created_at >= dt_inicio,
        OrdemServico.created_at <= dt_fim,
        OrdemServico.tipo == TipoOS.CORRETIVA,
        OrdemServico.status == StatusOS.FECHADA,
    ).all()

    tempos_reparo = [o.tempo_reparo for o in os_list if o.tempo_reparo]
    mttr = round(sum(tempos_reparo) / len(tempos_reparo) / 60, 2) if tempos_reparo else 0.0

    equips = {}
    for o in os_list:
        eid = str(o.equipamento_id)
        equips.setdefault(eid, []).append(o)
    mtbf_vals = []
    disp_vals = []
    for eid, os_eq in equips.items():
        if len(os_eq) >= 2:
            datas = sorted([o.created_at for o in os_eq])
            span_h = (datas[-1] - datas[0]).total_seconds() / 3600
            mtbf_vals.append(span_h / len(os_eq))
            parada_h = sum((o.tempo_total or 0) for o in os_eq) / 60
            disp_vals.append(max(0.0, (span_h - parada_h) / span_h * 100) if span_h else 100.0)

    mtbf = round(sum(mtbf_vals) / len(mtbf_vals), 2) if mtbf_vals else 0.0
    disponibilidade = round(sum(disp_vals) / len(disp_vals), 1) if disp_vals else 100.0

    return {
        "periodo": {"inicio": dt_inicio.isoformat(), "fim": dt_fim.isoformat()},
        "mttr_horas": mttr,
        "mtbf_horas": mtbf,
        "disponibilidade_percent": disponibilidade,
        "total_os_corretivas": len(os_list),
        "total_equipamentos_com_falha": len(equips),
    }

@router.get("/relatorios/equipamentos")
async def relatorio_equipamentos(
    equipamento_id: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")
    now = datetime.now(timezone.utc)
    dt_inicio = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc) if data_inicio else now - timedelta(days=90)
    dt_fim = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc) if data_fim else now

    equips_q = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id, Equipamento.ativo == True)
    if equipamento_id:
        equips_q = equips_q.filter(Equipamento.id == equipamento_id)
    equips = equips_q.all()

    resultado = []
    for e in equips:
        os_list = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.equipamento_id == e.id,
            OrdemServico.created_at >= dt_inicio,
            OrdemServico.created_at <= dt_fim,
        ).all()
        corretivas = [o for o in os_list if o.tipo == TipoOS.CORRETIVA]
        tempos = [o.tempo_reparo for o in corretivas if o.tempo_reparo]
        mttr = round(sum(tempos) / len(tempos) / 60, 2) if tempos else None
        resultado.append({
            "id": str(e.id), "codigo": e.codigo, "nome": e.nome,
            "localizacao": e.localizacao, "criticidade": e.criticidade,
            "total_os": len(os_list),
            "os_corretivas": len(corretivas),
            "os_preventivas": len([o for o in os_list if o.tipo == TipoOS.PREVENTIVA]),
            "mttr_horas": mttr,
            "status_saude": getattr(e, "status_saude", "NORMAL"),
            "disponibilidade_percent": getattr(e, "disponibilidade_percent", None),
        })
    return sorted(resultado, key=lambda x: x["os_corretivas"], reverse=True)


# ========== MÓDULO PREDITIVO COMPLETO ==========

class ConfigMonitoramentoCreate(BaseModel):
    equipamento_id: str
    parametro_nome: str
    unidade: Optional[str] = None
    threshold_atencao: float
    threshold_critico: float
    tendencia_janela_dias: int = 7

class LeituraCreate(BaseModel):
    equipamento_id: str
    parametro_nome: str
    valor: float
    unidade: Optional[str] = None
    fonte: str = "manual"
    timestamp: Optional[datetime] = None

class LeiturasBulk(BaseModel):
    leituras: List[LeituraCreate]

class AlertaIgnorar(BaseModel):
    motivo: str


# ── Exportações PDF / Excel (Fase 5.4) ───────────────────────────────────────

@router.get("/relatorios/os/export/pdf")
def exportar_os_pdf(
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..services.report_service import generate_os_pdf
    from fastapi.responses import StreamingResponse
    import io

    check_plan_feature(current_user, db, "exportacao_pdf")

    query = db.query(OrdemServico).filter(
        OrdemServico.organization_id == current_user.organization_id
    )
    if status:
        query = query.filter(OrdemServico.status == status)
    if data_inicio:
        query = query.filter(OrdemServico.created_at >= data_inicio)
    if data_fim:
        query = query.filter(OrdemServico.created_at <= data_fim)

    os_objs = query.order_by(OrdemServico.created_at.desc()).limit(1000).all()
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    org_nome = org.nome if org else "AURIX"
    periodo = f"{data_inicio or '...'} — {data_fim or '...'}"

    os_list = [
        {
            "numero": o.numero, "equipamento_nome": o.equipamento_nome,
            "tipo": o.tipo.value if o.tipo else "", "status": o.status.value if o.status else "",
            "prioridade": o.prioridade.value if o.prioridade else "",
            "created_at": str(o.created_at), "tecnico_nome": o.tecnico_nome,
            "tempo_reparo": o.tempo_reparo, "solucao": o.solucao, "custo_parada": o.custo_parada,
        }
        for o in os_objs
    ]

    pdf_bytes = generate_os_pdf(os_list, org_nome, periodo)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=os_{data_inicio or 'all'}_{data_fim or 'all'}.pdf"},
    )


@router.get("/relatorios/os/export/excel")
def exportar_os_excel(
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..services.report_service import generate_os_excel
    from fastapi.responses import StreamingResponse
    import io

    check_plan_feature(current_user, db, "exportacao_pdf")

    query = db.query(OrdemServico).filter(
        OrdemServico.organization_id == current_user.organization_id
    )
    if status:
        query = query.filter(OrdemServico.status == status)
    if data_inicio:
        query = query.filter(OrdemServico.created_at >= data_inicio)
    if data_fim:
        query = query.filter(OrdemServico.created_at <= data_fim)

    os_objs = query.order_by(OrdemServico.created_at.desc()).limit(1000).all()
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    org_nome = org.nome if org else "AURIX"
    periodo = f"{data_inicio or '...'} — {data_fim or '...'}"

    os_list = [
        {
            "numero": o.numero, "equipamento_nome": o.equipamento_nome,
            "tipo": o.tipo.value if o.tipo else "", "status": o.status.value if o.status else "",
            "prioridade": o.prioridade.value if o.prioridade else "",
            "created_at": str(o.created_at), "tecnico_nome": o.tecnico_nome,
            "tempo_reparo": o.tempo_reparo, "solucao": o.solucao, "custo_parada": o.custo_parada,
        }
        for o in os_objs
    ]

    xlsx_bytes = generate_os_excel(os_list, org_nome, periodo)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=os_{data_inicio or 'all'}_{data_fim or 'all'}.xlsx"},
    )


@router.get("/relatorios/kpi/export/pdf")
def exportar_kpi_pdf(
    mes: Optional[int] = Query(None),
    ano: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..services.report_service import generate_kpi_pdf
    from fastapi.responses import StreamingResponse
    import io
    from datetime import datetime

    check_plan_feature(current_user, db, "exportacao_pdf")

    now = datetime.now()
    mes = mes or now.month
    ano = ano or now.year

    # Reusa lógica do endpoint de dashboard KPIs
    org_id = current_user.organization_id
    start = datetime(ano, mes, 1, tzinfo=timezone.utc)
    end = datetime(ano, mes + 1, 1, tzinfo=timezone.utc) if mes < 12 else datetime(ano + 1, 1, 1, tzinfo=timezone.utc)

    os_mes = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.created_at >= start,
        OrdemServico.created_at < end,
    ).all()

    abertas = [o for o in os_mes if o.status and o.status.value not in ("fechada", "cancelada")]
    atrasadas = [
        o for o in abertas
        if o.prazo_sla and o.prazo_sla < datetime.now(timezone.utc)
    ]
    tempos = [o.tempo_reparo for o in os_mes if o.tempo_reparo]
    mttr = sum(tempos) / len(tempos) / 60 if tempos else 0
    custos = [o.custo_parada or 0 for o in os_mes]

    kpis = {
        "total_os_mes": len(os_mes),
        "os_abertas": len(abertas),
        "os_atrasadas": len(atrasadas),
        "mttr": round(mttr, 1),
        "mtbf": 0,
        "disponibilidade": 0,
        "custo_total_mes": sum(custos),
    }

    org = db.query(Organization).filter(Organization.id == org_id).first()
    org_nome = org.nome if org else "AURIX"
    periodo = f"{mes:02d}/{ano}"

    pdf_bytes = generate_kpi_pdf(kpis, org_nome, periodo)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=kpi_{periodo.replace('/', '-')}.pdf"},
    )
