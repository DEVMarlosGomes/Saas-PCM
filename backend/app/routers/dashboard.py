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

router = APIRouter(tags=["Dashboard"])

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


@router.get("/dashboard/kpis", response_model=DashboardKPIs)
async def get_dashboard_kpis(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import text as _sa_text
    org_id = user.organization_id
    now = datetime.now(timezone.utc)
    first_day_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Spec §3 / §4: escopo por setor para OPERADOR e LIDER ─────────────────
    # Determinar IDs de equipamentos no setor do usuário
    setor_equip_ids = None
    setor_usuario = user.setor or (user.generic_session_sector if user.role == UserRole.TECNICO else None)
    if user.role in (UserRole.OPERADOR, UserRole.LIDER) and setor_usuario:
        rows = db.execute(
            _sa_text("SELECT id FROM equipamentos WHERE organization_id = :org AND setor = :setor AND ativo = TRUE"),
            {"org": str(org_id), "setor": setor_usuario},
        ).fetchall()
        setor_equip_ids = [r[0] for r in rows]

    def _os_query():
        q = db.query(OrdemServico).filter(OrdemServico.organization_id == org_id)
        if setor_equip_ids is not None:
            q = q.filter(OrdemServico.equipamento_id.in_(setor_equip_ids))
        return q

    # Total OS do mês
    total_os_mes = _os_query().filter(
        OrdemServico.created_at >= first_day_month
    ).count()
    
    # OS abertas
    os_abertas = _os_query().filter(
        OrdemServico.status.in_([StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA])
    ).count()

    # OS atrasadas (fora do SLA)
    os_atrasadas = _os_query().filter(OrdemServico.dentro_sla == False).count()

    # MTTR (Mean Time To Repair) - média em horas
    os_com_reparo = _os_query().filter(OrdemServico.tempo_reparo != None).all()
    mttr = sum(o.tempo_reparo for o in os_com_reparo) / len(os_com_reparo) / 60 if os_com_reparo else 0

    # MTBF (Mean Time Between Failures) — simplificado
    first_os = _os_query().filter(
        OrdemServico.tipo == TipoOS.CORRETIVA
    ).order_by(OrdemServico.created_at).first()

    total_corretivas = _os_query().filter(OrdemServico.tipo == TipoOS.CORRETIVA).count()

    if first_os and total_corretivas > 1:
        days_operating = (now - first_os.created_at).days or 1
        mtbf = (days_operating * 24) / total_corretivas
    else:
        mtbf = 720  # Default 30 dias em horas

    # Disponibilidade = (MTBF / (MTBF + MTTR)) * 100
    disponibilidade = (mtbf / (mtbf + mttr) * 100) if (mtbf + mttr) > 0 else 100

    # Custos do mês
    custos_mes_ids = [str(o.id) for o in _os_query().filter(OrdemServico.created_at >= first_day_month).all()]
    if custos_mes_ids:
        custos_mes = db.query(CustoOS).filter(
            CustoOS.organization_id == org_id,
            CustoOS.ordem_servico_id.in_(custos_mes_ids),
        ).all()
    else:
        custos_mes = []
    custo_total_mes = sum(c.valor * c.quantidade for c in custos_mes)

    # Custo de máquina parada do mês
    os_mes_com_tempo = _os_query().filter(
        OrdemServico.created_at >= first_day_month,
        OrdemServico.tempo_total != None,
    ).all()
    
    custo_parada = 0
    for o in os_mes_com_tempo:
        equip = db.query(Equipamento).filter(Equipamento.id == o.equipamento_id).first()
        if equip:
            horas_parada = o.tempo_total / 60
            custo_parada += horas_parada * equip.valor_hora
    
    # Mix de tipos de OS (todas — sem filtro mensal para dar visão completa)
    preventivas = _os_query().filter(OrdemServico.tipo == TipoOS.PREVENTIVA).count()
    corretivas  = _os_query().filter(OrdemServico.tipo == TipoOS.CORRETIVA).count()
    preditivas  = _os_query().filter(OrdemServico.tipo == TipoOS.PREDITIVA).count()

    from sqlalchemy import func

    # Top equipamentos por falhas
    top_falhas_q = _os_query().filter(OrdemServico.tipo == TipoOS.CORRETIVA)
    top_falhas = (
        db.query(OrdemServico.equipamento_id, func.count(OrdemServico.id).label("total"))
        .filter(OrdemServico.id.in_([o.id for o in top_falhas_q.all()]))
        .group_by(OrdemServico.equipamento_id)
        .order_by(func.count(OrdemServico.id).desc())
        .limit(5)
        .all()
    )
    top_equipamentos_falhas = []
    for eq_id, total in top_falhas:
        equip = db.query(Equipamento).filter(Equipamento.id == eq_id).first()
        if equip:
            top_equipamentos_falhas.append({"nome": equip.nome, "codigo": equip.codigo, "total": total})

    # Top equipamentos por custo
    top_custos_os_ids = [o.id for o in _os_query().all()]
    if top_custos_os_ids:
        top_custos = (
            db.query(OrdemServico.equipamento_id, func.sum(CustoOS.valor * CustoOS.quantidade).label("total"))
            .join(CustoOS)
            .filter(OrdemServico.id.in_(top_custos_os_ids))
            .group_by(OrdemServico.equipamento_id)
            .order_by(func.sum(CustoOS.valor * CustoOS.quantidade).desc())
            .limit(5)
            .all()
        )
    else:
        top_custos = []
    top_equipamentos_custos = []
    for eq_id, total in top_custos:
        equip = db.query(Equipamento).filter(Equipamento.id == eq_id).first()
        if equip:
            top_equipamentos_custos.append({"nome": equip.nome, "codigo": equip.codigo, "total": float(total or 0)})

    # Average response time
    os_com_resposta = _os_query().filter(OrdemServico.tempo_resposta != None).all()
    avg_tempo_resposta = sum(o.tempo_resposta for o in os_com_resposta) / len(os_com_resposta) if os_com_resposta else 0

    # Top equipamentos por downtime (tempo parado)
    all_os_ids = [o.id for o in _os_query().filter(OrdemServico.tempo_total != None).all()]
    if all_os_ids:
        top_downtime_raw = (
            db.query(OrdemServico.equipamento_id, func.sum(OrdemServico.tempo_total).label("total_downtime"))
            .filter(OrdemServico.id.in_(all_os_ids))
            .group_by(OrdemServico.equipamento_id)
            .order_by(func.sum(OrdemServico.tempo_total).desc())
            .limit(5)
            .all()
        )
    else:
        top_downtime_raw = []
    top_equipamentos_downtime = []
    for eq_id, total_dt in top_downtime_raw:
        equip = db.query(Equipamento).filter(Equipamento.id == eq_id).first()
        if equip:
            hours = round((total_dt or 0) / 60, 1)
            top_equipamentos_downtime.append({"nome": equip.nome, "codigo": equip.codigo, "total_horas": hours})

    # Financial fields: ADMIN/SUPERUSUARIO/LIDER com setor recebem valores
    _is_fin = user.role in (UserRole.ADMIN, UserRole.SUPERUSUARIO, UserRole.LIDER)
    return DashboardKPIs(
        total_os_mes=total_os_mes,
        os_abertas=os_abertas,
        os_atrasadas=os_atrasadas,
        mttr=round(mttr, 2),
        mtbf=round(mtbf, 2),
        disponibilidade=round(disponibilidade, 2),
        custo_total_mes=round(custo_total_mes, 2) if _is_fin else 0.0,
        custo_parada_mes=round(custo_parada, 2) if _is_fin else 0.0,
        avg_tempo_resposta=round(avg_tempo_resposta, 1),
        preventiva_vs_corretiva={"preventiva": preventivas, "corretiva": corretivas, "preditiva": preditivas},
        top_equipamentos_falhas=top_equipamentos_falhas,
        top_equipamentos_custos=top_equipamentos_custos if _is_fin else [],
        top_equipamentos_downtime=top_equipamentos_downtime
    )

@router.get("/dashboard/backlog")
async def get_backlog(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retorna backlog de OS"""
    org_id = user.organization_id
    
    abertas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.status == StatusOS.ABERTA
    ).count()
    
    em_atendimento = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.status == StatusOS.EM_ATENDIMENTO
    ).count()
    
    aguardando_revisao = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.status == StatusOS.AGUARDANDO_REVISAO
    ).count()
    
    aguardando_peca = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.status == StatusOS.AGUARDANDO_PECA
    ).count()

    atrasadas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.dentro_sla == False,
        OrdemServico.status.in_([StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA])
    ).count()

    return {
        "abertas": abertas,
        "em_atendimento": em_atendimento,
        "aguardando_peca": aguardando_peca,
        "aguardando_revisao": aguardando_revisao,
        "atrasadas": atrasadas,
        "total_pendentes": abertas + em_atendimento + aguardando_peca + aguardando_revisao
    }

@router.get("/dashboard/operador")
async def get_dashboard_operador(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FASE 4.1 — KPIs do setor para OPERADOR e TECNICO.
    Escopo: equipamentos do setor do usuário logado.
    """
    from sqlalchemy import func as _func, text as _sa_text

    _ROLES_OP_DASH = {UserRole.OPERADOR, UserRole.TECNICO, UserRole.LIDER_PRODUCAO, UserRole.SUPERVISOR_PRODUCAO}
    if user.role not in _ROLES_OP_DASH:
        raise HTTPException(status_code=403, detail="Acesso restrito a operadores e técnicos.")

    setor_nome = user.setor or user.generic_session_sector
    if not setor_nome:
        raise HTTPException(status_code=400, detail="Usuário sem setor definido. Configure o setor no perfil.")

    # Resolve setor entity (opcional — pode não existir)
    setor_entity = db.query(Setor).filter(
        Setor.organization_id == user.organization_id,
        Setor.nome == setor_nome,
        Setor.ativo == True,
    ).first()
    setor_id = str(setor_entity.id) if setor_entity else None

    now = datetime.now(timezone.utc)
    first_day_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # IDs de equipamentos do setor
    equip_ids_rows = db.execute(
        _sa_text("SELECT id FROM equipamentos WHERE organization_id = :org AND setor = :setor AND ativo = TRUE"),
        {"org": str(user.organization_id), "setor": setor_nome},
    ).fetchall()
    equip_ids = [r[0] for r in equip_ids_rows]

    def _os_q():
        q = db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id)
        if equip_ids:
            q = q.filter(OrdemServico.equipamento_id.in_(equip_ids))
        else:
            q = q.filter(False)  # setor sem equipamentos → vazio
        return q

    # OS do mês
    os_mes = _os_q().filter(OrdemServico.created_at >= first_day_month).count()

    # MTTR (minutos)
    os_com_reparo = _os_q().filter(OrdemServico.tempo_reparo != None).all()
    mttr_min = (sum(o.tempo_reparo for o in os_com_reparo) / len(os_com_reparo)) if os_com_reparo else 0.0

    # MTBF (horas)
    total_corretivas = _os_q().filter(OrdemServico.tipo == TipoOS.CORRETIVA).count()
    first_os = _os_q().filter(OrdemServico.tipo == TipoOS.CORRETIVA).order_by(OrdemServico.created_at).first()
    if first_os and total_corretivas > 1:
        days = (now - first_os.created_at).days or 1
        mtbf_h = (days * 24) / total_corretivas
    else:
        mtbf_h = 720.0

    # Disponibilidade
    mttr_h = mttr_min / 60
    disponibilidade = (mtbf_h / (mtbf_h + mttr_h) * 100) if (mtbf_h + mttr_h) > 0 else 100.0

    # Tempo de resposta médio
    os_com_resp = _os_q().filter(OrdemServico.tempo_resposta != None).all()
    tempo_resposta_medio = (sum(o.tempo_resposta for o in os_com_resp) / len(os_com_resp)) if os_com_resp else 0.0

    # OS abertas do setor
    _ABERTOS = [StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA]
    os_abertas_objs = _os_q().filter(OrdemServico.status.in_(_ABERTOS)).all()
    os_abertas = [
        {
            "id": str(o.id), "numero": o.numero, "status": o.status.value,
            "prioridade": o.prioridade.value, "failure_group": o.failure_group,
            "descricao": o.descricao[:120], "created_at": o.created_at.isoformat(),
        }
        for o in os_abertas_objs
    ]

    # Equipamentos em manutenção
    equip_em_manutencao_ids = list({str(o.equipamento_id) for o in os_abertas_objs})
    equipamentos_em_manutencao = []
    for eid in equip_em_manutencao_ids:
        eq = db.query(Equipamento).filter(Equipamento.id == eid).first()
        if eq:
            equipamentos_em_manutencao.append({"id": str(eq.id), "codigo": eq.codigo, "nome": eq.nome})

    return {
        "setor_id": setor_id,
        "setor_nome": setor_nome,
        "disponibilidade_percent": round(disponibilidade, 1),
        "mttr_minutos": round(mttr_min, 1),
        "mtbf_horas": round(mtbf_h, 1),
        "os_mes": os_mes,
        "tempo_resposta_medio_min": round(tempo_resposta_medio, 1),
        "os_abertas": os_abertas,
        "equipamentos_em_manutencao": equipamentos_em_manutencao,
    }

@router.get("/dashboard/lider")
async def get_dashboard_lider(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FASE 4.2 — KPIs completos + financeiros para LIDER, ADMIN e SUPERUSUARIO.
    LIDER: escopo do seu setor. ADMIN/SUPERUSUARIO: toda a organização.
    """
    from sqlalchemy import func as _func

    _ROLES_LIDER_DASH = {
        UserRole.LIDER, UserRole.ADMIN, UserRole.SUPERUSUARIO,
        UserRole.LIDER_MANUTENCAO_ELETRICA, UserRole.LIDER_MANUTENCAO_MECANICA,
        UserRole.SUPERVISOR_MANUTENCAO, UserRole.ANALISTA_MANUTENCAO,
        UserRole.ENGENHEIRO_MANUTENCAO, UserRole.GERENTE_INDUSTRIAL,
    }
    if user.role not in _ROLES_LIDER_DASH:
        raise HTTPException(status_code=403, detail="Acesso restrito a líderes e administradores.")

    now = datetime.now(timezone.utc)
    first_day_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Escopo: LIDER com setor filtra por setor; todos os outros veem a organização inteira
    equip_ids = None
    setor_nome = None
    setor_id = None
    if user.role == UserRole.LIDER and user.setor:
        setor_nome = user.setor
        from sqlalchemy import text as _sa_text
        rows = db.execute(
            _sa_text("SELECT id FROM equipamentos WHERE organization_id = :org AND setor = :setor AND ativo = TRUE"),
            {"org": str(user.organization_id), "setor": setor_nome},
        ).fetchall()
        equip_ids = [r[0] for r in rows]
        setor_entity = db.query(Setor).filter(
            Setor.organization_id == user.organization_id, Setor.nome == setor_nome, Setor.ativo == True
        ).first()
        setor_id = str(setor_entity.id) if setor_entity else None

    def _os_q():
        q = db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id)
        if equip_ids is not None:
            q = q.filter(OrdemServico.equipamento_id.in_(equip_ids)) if equip_ids else q.filter(False)
        return q

    # OS do mês
    os_mes = _os_q().filter(OrdemServico.created_at >= first_day_month).count()

    # MTTR
    os_com_reparo = _os_q().filter(OrdemServico.tempo_reparo != None).all()
    mttr_min = (sum(o.tempo_reparo for o in os_com_reparo) / len(os_com_reparo)) if os_com_reparo else 0.0

    # MTBF
    total_corretivas = _os_q().filter(OrdemServico.tipo == TipoOS.CORRETIVA).count()
    first_os = _os_q().filter(OrdemServico.tipo == TipoOS.CORRETIVA).order_by(OrdemServico.created_at).first()
    if first_os and total_corretivas > 1:
        days = (now - first_os.created_at).days or 1
        mtbf_h = (days * 24) / total_corretivas
    else:
        mtbf_h = 720.0
    mttr_h = mttr_min / 60
    disponibilidade = (mtbf_h / (mtbf_h + mttr_h) * 100) if (mtbf_h + mttr_h) > 0 else 100.0

    # Tempo de resposta médio
    os_com_resp = _os_q().filter(OrdemServico.tempo_resposta != None).all()
    tempo_resposta_medio = (sum(o.tempo_resposta for o in os_com_resp) / len(os_com_resp)) if os_com_resp else 0.0

    # Custo total de parada do mês
    os_mes_objs = _os_q().filter(OrdemServico.created_at >= first_day_month, OrdemServico.tempo_total != None).all()
    custo_parada_mes = 0.0
    custo_por_equip: dict = {}
    for o in os_mes_objs:
        eq = db.query(Equipamento).filter(Equipamento.id == o.equipamento_id).first()
        if eq and eq.valor_hora:
            c = (o.tempo_total / 60) * eq.valor_hora
            custo_parada_mes += c
            eid = str(eq.id)
            custo_por_equip[eid] = custo_por_equip.get(eid, {"nome": eq.nome, "codigo": eq.codigo, "custo": 0.0})
            custo_por_equip[eid]["custo"] += c

    top_equipamentos_custo = sorted(custo_por_equip.values(), key=lambda x: x["custo"], reverse=True)[:5]
    for t in top_equipamentos_custo:
        t["custo"] = round(t["custo"], 2)

    # OS por grupo de falha
    grupos_falha_rows = _os_q().filter(
        OrdemServico.failure_group != None,
        OrdemServico.created_at >= first_day_month,
    ).all()
    os_por_grupo_falha: dict = {}
    for o in grupos_falha_rows:
        g = o.failure_group or "outro"
        os_por_grupo_falha[g] = os_por_grupo_falha.get(g, 0) + 1

    # Técnicos ativos agora
    _ABERTOS = [StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA]
    tecnico_ids_ativos = list({str(o.tecnico_id) for o in _os_q().filter(
        OrdemServico.status == StatusOS.EM_ATENDIMENTO,
        OrdemServico.tecnico_id != None,
    ).all()})
    tecnicos_ativos = []
    for tid in tecnico_ids_ativos:
        t = db.query(User).filter(User.id == tid).first()
        if t:
            tecnicos_ativos.append({"id": str(t.id), "nome": t.nome, "employee_id": t.employee_id})

    # Pendentes de revisão
    pendentes_revisao = _os_q().filter(OrdemServico.status == StatusOS.AGUARDANDO_REVISAO).count()

    # OS abertas (resumo)
    os_abertas_objs = _os_q().filter(OrdemServico.status.in_(_ABERTOS)).all()
    os_abertas = [
        {
            "id": str(o.id), "numero": o.numero, "status": o.status.value,
            "prioridade": o.prioridade.value, "failure_group": o.failure_group,
            "descricao": o.descricao[:120], "created_at": o.created_at.isoformat(),
        }
        for o in os_abertas_objs
    ]

    # Equipamentos em manutenção
    equip_em_manutencao_ids = list({str(o.equipamento_id) for o in os_abertas_objs})
    equipamentos_em_manutencao = []
    for eid in equip_em_manutencao_ids:
        eq = db.query(Equipamento).filter(Equipamento.id == eid).first()
        if eq:
            equipamentos_em_manutencao.append({"id": str(eq.id), "codigo": eq.codigo, "nome": eq.nome})

    return {
        "setor_id": setor_id,
        "setor_nome": setor_nome,
        "disponibilidade_percent": round(disponibilidade, 1),
        "mttr_minutos": round(mttr_min, 1),
        "mtbf_horas": round(mtbf_h, 1),
        "os_mes": os_mes,
        "tempo_resposta_medio_min": round(tempo_resposta_medio, 1),
        "custo_total_parada_mes": round(custo_parada_mes, 2),
        "top_equipamentos_custo": top_equipamentos_custo,
        "os_por_grupo_falha": os_por_grupo_falha,
        "tecnicos_ativos": tecnicos_ativos,
        "pendentes_revisao": pendentes_revisao,
        "os_abertas": os_abertas,
        "equipamentos_em_manutencao": equipamentos_em_manutencao,
    }

@router.get("/dashboard/superusuario")
async def get_dashboard_superusuario(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FASE 4.3 — Visão consolidada de todas as empresas. Apenas SUPERUSUARIO.
    """
    if user.role != UserRole.SUPERUSUARIO:
        raise HTTPException(status_code=403, detail="Acesso exclusivo para superusuários.")

    orgs = db.query(Organization).filter(Organization.ativo == True).all()

    empresas = []
    total_os_abertas = 0
    alertas_criticos = 0

    for org in orgs:
        usuarios_ativos = db.query(User).filter(
            User.organization_id == org.id, User.ativo == True
        ).count()

        os_abertas_count = db.query(OrdemServico).filter(
            OrdemServico.organization_id == org.id,
            OrdemServico.status.in_([StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA]),
        ).count()

        total_os_abertas += os_abertas_count

        # Criticas abertas
        criticas = db.query(OrdemServico).filter(
            OrdemServico.organization_id == org.id,
            OrdemServico.prioridade == PrioridadeOS.CRITICA,
            OrdemServico.status.in_([StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA]),
        ).count()
        if criticas > 0:
            alertas_criticos += 1

        # Disponibilidade média simples
        os_com_reparo = db.query(OrdemServico).filter(
            OrdemServico.organization_id == org.id,
            OrdemServico.tempo_reparo != None,
        ).all()
        mttr_h_org = (sum(o.tempo_reparo for o in os_com_reparo) / len(os_com_reparo) / 60) if os_com_reparo else 0
        total_corr = db.query(OrdemServico).filter(
            OrdemServico.organization_id == org.id, OrdemServico.tipo == TipoOS.CORRETIVA
        ).count()
        first_corr = db.query(OrdemServico).filter(
            OrdemServico.organization_id == org.id, OrdemServico.tipo == TipoOS.CORRETIVA
        ).order_by(OrdemServico.created_at).first()
        if first_corr and total_corr > 1:
            days = (datetime.now(timezone.utc) - first_corr.created_at).days or 1
            mtbf_h_org = (days * 24) / total_corr
        else:
            mtbf_h_org = 720.0
        disponibilidade_org = (
            (mtbf_h_org / (mtbf_h_org + mttr_h_org) * 100) if (mtbf_h_org + mttr_h_org) > 0 else 100.0
        )

        # Último acesso
        ultimo_acesso_user = db.query(User).filter(
            User.organization_id == org.id, User.ativo == True, User.updated_at != None
        ).order_by(User.updated_at.desc()).first()

        empresas.append({
            "id": str(org.id),
            "nome": org.nome,
            "plano": org.plano.value,
            "usuarios_ativos": usuarios_ativos,
            "os_abertas": os_abertas_count,
            "disponibilidade_media": round(disponibilidade_org, 1),
            "ultimo_acesso": ultimo_acesso_user.updated_at.isoformat() if ultimo_acesso_user and ultimo_acesso_user.updated_at else None,
            "status_contrato": org.subscription_status or "ativo",
        })

    return {
        "empresas": empresas,
        "totais": {
            "empresas_ativas": len(orgs),
            "os_abertas_total": total_os_abertas,
            "alertas_criticos": alertas_criticos,
        },
    }

@router.get("/dashboard/tendencia")
async def get_tendencia(
    dias: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna série temporal de OS abertas nos últimos N dias (dashboard avançado)."""
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "dashboard_avancado")

    now = datetime.now(timezone.utc)
    from sqlalchemy import func, cast, Date as SADate

    result = []
    for i in range(dias - 1, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        total = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.created_at >= day_start,
            OrdemServico.created_at < day_end,
        ).count()
        corretivas = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.created_at >= day_start,
            OrdemServico.created_at < day_end,
            OrdemServico.tipo == TipoOS.CORRETIVA,
        ).count()
        fechadas = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.created_at >= day_start,
            OrdemServico.created_at < day_end,
            OrdemServico.status == StatusOS.FECHADA,
        ).count()
        result.append({
            "data": day_start.strftime("%d/%m"),
            "total": total,
            "corretivas": corretivas,
            "fechadas": fechadas,
        })

    return {"dias": dias, "serie": result}


# ========== KANBAN ==========
