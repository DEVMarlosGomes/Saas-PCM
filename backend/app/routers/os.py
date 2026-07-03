from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel, Field
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

from ..routers.evidencias import verificar_checklists_pendentes

router = APIRouter(tags=["Ordens de Serviço"])

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


@router.get("/ordens-servico", response_model=List[OSResponse])
async def list_os(
    status: Optional[str] = None,
    tipo: Optional[str] = None,
    prioridade: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id)
    
    if status:
        query = query.filter(OrdemServico.status == status)
    if tipo:
        query = query.filter(OrdemServico.tipo == tipo)
    if prioridade:
        query = query.filter(OrdemServico.prioridade == prioridade)
    
    ordens = query.order_by(OrdemServico.created_at.desc()).all()
    
    return [_build_os_response(o, db, user=user) for o in ordens]

@router.post("/ordens-servico", response_model=OSResponse)
async def create_os(data: OSCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check plan limit
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    allowed, msg = check_plan_limit(db, org, "os")
    if not allowed:
        raise HTTPException(status_code=402, detail=msg)

    # ── FASE 4: Restrição de tipo por grupo funcional ────────────────────────────
    _GRUPO_PRODUCAO_ROLES = [
        UserRole.OPERADOR, UserRole.LIDER_PRODUCAO, UserRole.SUPERVISOR_PRODUCAO, UserRole.LIDER,
    ]
    _TIPOS_EXCLUSIVOS_MANUTENCAO = [TipoOS.PREVENTIVA, TipoOS.PREDITIVA]
    if data.tipo in _TIPOS_EXCLUSIVOS_MANUTENCAO and user.role in _GRUPO_PRODUCAO_ROLES:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tipo_os_nao_permitido",
                "message": "Operadores e líderes de produção só podem abrir OS corretivas.",
            },
        )

    # Verify equipment exists
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == data.equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")

    # ── FASE 3.1: Bloqueio por failure_group ────────────────────────────────
    _TODOS_GRUPOS_FALHA = ["eletrico", "hidraulico", "mecanico", "pneumatico", "instrumentacao", "estrutural", "outro"]
    _STATUSES_ABERTOS = [StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA, StatusOS.AGUARDANDO_REVISAO]

    if data.failure_group:
        os_bloqueante = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.equipamento_id == data.equipamento_id,
            OrdemServico.failure_group == data.failure_group,
            OrdemServico.status.in_(_STATUSES_ABERTOS),
        ).first()
        if os_bloqueante:
            grupos_ocupados_rows = db.query(OrdemServico.failure_group).filter(
                OrdemServico.organization_id == user.organization_id,
                OrdemServico.equipamento_id == data.equipamento_id,
                OrdemServico.failure_group != None,
                OrdemServico.status.in_(_STATUSES_ABERTOS),
            ).distinct().all()
            grupos_ocupados = {r[0] for r in grupos_ocupados_rows if r[0]}
            grupos_disponiveis = [g for g in _TODOS_GRUPOS_FALHA if g not in grupos_ocupados]
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "bloqueio_grupo_falha",
                    "message": f"Equipamento já possui OS aberta para o grupo '{data.failure_group}'. Só é possível abrir OS de outro grupo de falha.",
                    "os_bloqueante": {
                        "id": str(os_bloqueante.id),
                        "numero": os_bloqueante.numero,
                        "failure_group": os_bloqueante.failure_group,
                        "status": os_bloqueante.status.value,
                    },
                    "grupos_disponiveis": grupos_disponiveis,
                },
            )

    # ── FASE 4: Resolver crachá do solicitante físico ───────────────────────────
    _sol_cracha = (data.solicitante_cracha or "").strip() or None
    _sol_nome = (data.solicitante_nome or "").strip() or None
    _sol_user_id = None
    if _sol_cracha:
        _sol_user = db.query(User).filter(
            User.organization_id == user.organization_id,
            User.employee_id == _sol_cracha,
            User.ativo == True,
        ).first()
        if _sol_user:
            _sol_nome = _sol_user.nome
            _sol_user_id = _sol_user.id

    numero = get_next_os_number(db, str(user.organization_id))
    now = datetime.now(timezone.utc)

    os = OrdemServico(
        numero=numero,
        equipamento_id=data.equipamento_id,
        grupo_id=data.grupo_id or equipamento.grupo_id,
        subgrupo_id=data.subgrupo_id or equipamento.subgrupo_id,
        tipo=data.tipo,
        prioridade=data.prioridade,
        descricao=data.descricao,
        falha_tipo=data.falha_tipo,
        falha_modo=data.falha_modo,
        falha_causa=data.falha_causa,
        failure_group=data.failure_group,
        area_manutencao=data.area_manutencao or None,
        subarea_manutencao=data.subarea_manutencao or None,
        solicitante_id=user.id,
        organization_id=user.organization_id,
        downtime_start=now,
        technician_employee_id=user.employee_id if user.role == UserRole.TECNICO else None,
        solicitante_cracha=_sol_cracha,
        solicitante_nome=_sol_nome,
        solicitante_user_id=_sol_user_id,
    )

    # Check reincidência
    os.reincidente = check_reincidencia(db, str(user.organization_id), data.equipamento_id, data.falha_tipo)

    db.add(os)
    db.commit()
    db.refresh(os)

    create_audit_log(db, str(user.organization_id), str(user.id), "ordem_servico", str(os.id), "create")
    _record_os_historico(db, os.id, "aberta", user_id=user.id, user_nome=user.nome, timestamp=now)
    db.commit()

    return _build_os_response(os, db, user=user)

@router.put("/ordens-servico/{os_id}", response_model=OSResponse)

@router.patch("/ordens-servico/{os_id}", response_model=OSResponse)
async def update_os(os_id: str, data: OSUpdate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    os = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id
    ).first()
    if not os:
        raise HTTPException(status_code=404, detail="OS não encontrada")

    # Offline sync conflict detection: if client sent a timestamp, check if
    # server record was updated after the client's last known state.
    client_ts_header = request.headers.get("X-Client-Timestamp")
    if client_ts_header and request.headers.get("X-Offline-Sync"):
        try:
            client_ts_ms = int(client_ts_header)
            if os.updated_at:
                server_ts_ms = int(os.updated_at.timestamp() * 1000)
                if server_ts_ms > client_ts_ms:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "conflict": True,
                            "message": "OS atualizada por outro usuário desde o último sync",
                            "server_updated_at": os.updated_at.isoformat(),
                        },
                    )
        except (ValueError, AttributeError):
            pass  # Timestamp inválido — ignora e processa normalmente

    import json as json_lib
    now = datetime.now(timezone.utc)
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
    # Track field changes for audit
    changes = {}
    
    if data.status:
        old_status = os.status
        changes["status"] = {"de": old_status.value, "para": data.status.value}
        os.status = data.status
        
        # Handle status transitions
        _aceitacao_label = None  # label customizado para o histórico de aceitação
        if data.status == StatusOS.EM_ATENDIMENTO and old_status == StatusOS.ABERTA:
            os.inicio_atendimento = now
            os.tempo_resposta = int((now - os.created_at).total_seconds() / 60)
            os.dentro_sla = calculate_sla(os.prioridade, os.tempo_resposta)
            if data.tecnico_id:
                os.tecnico_id = data.tecnico_id
            elif user.role in [UserRole.TECNICO, UserRole.LIDER]:
                os.tecnico_id = user.id
            # Registrar matrícula do técnico (via colaborador ou do próprio usuário)
            if data.matricula_tecnico:
                # Lookup colaborador para validação de área e label
                _col = db.query(Colaborador).filter(
                    Colaborador.organization_id == user.organization_id,
                    Colaborador.matricula == data.matricula_tecnico,
                    Colaborador.ativo == True,
                ).first()
                if _col:
                    # ── Validação de área de manutenção ──────────────────────────
                    _area_os = getattr(os, 'area_manutencao', None)
                    if _area_os and _area_os != 'geral':
                        _excecao_area = db.query(OSExcecaoArea).filter(
                            OSExcecaoArea.os_id == os.id,
                            OSExcecaoArea.matricula == data.matricula_tecnico,
                        ).first()
                        if not _excecao_area and not _area_compativel(_area_os, _col.setor or '', _col.cargo or ''):
                            raise HTTPException(
                                status_code=403,
                                detail={
                                    "error": "area_incompativel",
                                    "area_os": _area_os,
                                    "area_os_label": AREAS_MANUTENCAO_LABEL.get(_area_os, _area_os),
                                    "area_tecnico": _col.setor or _col.cargo or "",
                                    "mensagem": (
                                        f"Esta OS é de manutenção {AREAS_MANUTENCAO_LABEL.get(_area_os, _area_os)}. "
                                        f"Solicite ao líder técnico ou admin para autorizar seu crachá nesta OS."
                                    ),
                                }
                            )
                    # ── Monta label rico de aceitação ────────────────────────────
                    _area = data.area_tecnico or _col.setor or _col.cargo or "Manutenção"
                    _hora = now.strftime("%H:%M")
                    _aceitacao_label = f"Aceito por {_col.nome} · {_area} · {_hora}"
                os.technician_employee_id = data.matricula_tecnico
            elif user.role == UserRole.TECNICO and user.employee_id:
                os.technician_employee_id = user.employee_id

        elif data.status == StatusOS.AGUARDANDO_PECA and old_status == StatusOS.EM_ATENDIMENTO:
            # Técnico aguarda peça — OS permanece com ele, downtime continua
            pass

        elif data.status == StatusOS.EM_ATENDIMENTO and old_status == StatusOS.AGUARDANDO_PECA:
            # Retorno ao atendimento após chegada de peça
            pass

        elif data.status == StatusOS.AGUARDANDO_REVISAO:
            # ── Spec v5: exige relatório do técnico ──────────────────────────
            _rel_o_que = (data.relatorio_o_que_foi_realizado or "").strip()
            _rel_analise = (data.relatorio_analise_problema or "").strip()
            if not _rel_o_que or not _rel_analise:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "relatorio_obrigatorio",
                        "message": "Preencha 'O que foi realizado' e 'Análise do problema' para concluir a OS.",
                    },
                )
            os.relatorio_o_que_foi_realizado = _rel_o_que
            os.relatorio_analise_problema = _rel_analise
            os.relatorio_preenchido_em = now
            os.relatorio_preenchido_por = user.id
            # ─────────────────────────────────────────────────────────────────
            os.fim_atendimento = now
            if os.inicio_atendimento:
                os.tempo_reparo = int((now - os.inicio_atendimento).total_seconds() / 60)
            os.tempo_total = int((now - os.created_at).total_seconds() / 60)

            # ── Spec v6: calcular custo de mão de obra ───────────────────────
            _inicio = os.inicio_atendimento or os.created_at
            _horas = round((now - _inicio).total_seconds() / 3600, 2)
            _vh_tec = 0.0
            if os.tecnico_id:
                _tec_usr = db.query(User).filter(User.id == os.tecnico_id).first()
                if _tec_usr and _tec_usr.valor_hora:
                    _vh_tec = float(_tec_usr.valor_hora)
            # Acumula custo de membros da equipe (preventiva/preditiva)
            _custo_mo = _horas * _vh_tec
            _membros = db.query(OSEquipe).filter(OSEquipe.os_id == str(os.id)).all()
            for _m in _membros:
                if _m.user_id:
                    _m_usr = db.query(User).filter(User.id == _m.user_id).first()
                    if _m_usr and _m_usr.valor_hora:
                        _custo_mo += _horas * float(_m_usr.valor_hora)
            os.horas_trabalhadas = _horas
            os.valor_hora_tecnico = _vh_tec
            os.custo_mao_obra = round(_custo_mo, 2)
            
            # Auto-assign leader as reviewer — roteado pela área da OS
            _area_os_rev = getattr(os, 'area_manutencao', None)
            leader = _get_revisor(db, user.organization_id, _area_os_rev)
            if leader:
                os.revisor_id = leader.id
                changes["revisor_auto_atribuido"] = leader.nome
                _area_label_rev = AREAS_MANUTENCAO_LABEL.get(_area_os_rev or "", "")
                _area_txt = f" ({_area_label_rev})" if _area_label_rev else ""
                criar_notificacao(
                    db, org_id=os.organization_id, destinatario_id=leader.id,
                    tipo="revisao_pendente",
                    titulo=f"OS #{os.numero}{_area_txt} aguarda sua revisão",
                    mensagem=f"A OS #{os.numero} foi concluída e aguarda revisão. Prazo: 24 horas.",
                    os_id=os.id,
                )
                if org:
                    send_email_notification(
                        db, org, leader.id,
                        f"OS #{os.numero}{_area_txt} aguarda sua revisão",
                        f"<p>A OS <strong>#{os.numero}</strong>{_area_txt} foi concluída e aguarda sua revisão.</p><p>Prazo: 24 horas.</p>",
                    )

            # Set 24h review deadline
            os.review_deadline = now + timedelta(hours=24)

        elif data.status == StatusOS.REVISADA:
            # ── Validação de área para revisão ──────────────────────────────
            _area_rev = getattr(os, 'area_manutencao', None)
            _ROLES_REVISAO_GERAL = [UserRole.ADMIN, UserRole.LIDER]
            if user.role == UserRole.LIDER_MANUTENCAO_ELETRICA:
                if _area_rev != "eletrica":
                    raise HTTPException(
                        status_code=403,
                        detail="Líder da Elétrica só pode revisar OS da área Elétrica."
                    )
            elif user.role == UserRole.LIDER_MANUTENCAO_MECANICA:
                if _area_rev != "mecanica":
                    raise HTTPException(
                        status_code=403,
                        detail="Líder da Mecânica só pode revisar OS da área Mecânica."
                    )
            elif user.role not in _ROLES_REVISAO_GERAL:
                raise HTTPException(status_code=403, detail="Sem permissão para revisar esta OS.")
            os.revisado_at = now
            os.revisor_id = user.id
            criar_notificacao(
                db, org_id=os.organization_id, destinatario_id=os.solicitante_id,
                tipo="os_revisada",
                titulo=f"OS #{os.numero} revisada",
                mensagem=f"Sua ordem de serviço #{os.numero} foi revisada e está sendo encerrada.",
                os_id=os.id,
            )
            if org:
                send_email_notification(
                    db, org, os.solicitante_id,
                    f"OS #{os.numero} revisada",
                    f"<p>Sua ordem de serviço <strong>#{os.numero}</strong> foi revisada e está sendo encerrada.</p>",
                )

        elif data.status == StatusOS.FECHADA:
            # Fase 2 — verificar checklists obrigatórios antes de fechar
            try:
                from app.routers.evidencias import verificar_checklists_pendentes
                _checklist_err = verificar_checklists_pendentes(db, os, str(os.organization_id))
                if _checklist_err:
                    raise HTTPException(status_code=422, detail=_checklist_err)
            except HTTPException:
                raise
            except Exception as _ce:
                logger.warning("Falha ao verificar checklists: %s", _ce)

            os.fechado_at = now

            # Fase 2 — assinatura digital: hash do estado imutável da OS
            try:
                import hashlib as _hl, json as _json
                _state = {
                    "id": str(os.id),
                    "numero": os.numero,
                    "status": "fechada",
                    "descricao": os.descricao or "",
                    "solucao": data.solucao or os.solucao or "",
                    "tecnico_id": str(os.tecnico_id) if os.tecnico_id else None,
                    "fechado_at": now.isoformat(),
                    "organization_id": str(os.organization_id),
                }
                os.assinatura_hash = _hl.sha256(
                    _json.dumps(_state, sort_keys=True).encode()
                ).hexdigest()
                os.assinado_por = user.id
                os.assinado_em = now
            except Exception as _se:
                logger.warning("Falha ao gerar assinatura da OS: %s", _se)

            criar_notificacao(
                db, org_id=os.organization_id, destinatario_id=os.solicitante_id,
                tipo="os_fechada",
                titulo=f"OS #{os.numero} encerrada",
                mensagem=f"Sua ordem de serviço #{os.numero} foi oficialmente encerrada.",
                os_id=os.id,
            )
            if org:
                send_email_notification(
                    db, org, os.solicitante_id,
                    f"OS #{os.numero} encerrada",
                    f"<p>Sua ordem de serviço <strong>#{os.numero}</strong> foi oficialmente encerrada.</p>",
                )
    
    if data.solucao:
        if os.solucao != data.solucao:
            changes["solucao"] = {"de": os.solucao or "", "para": data.solucao}
        os.solucao = data.solucao
    if data.tecnico_id:
        os.tecnico_id = data.tecnico_id
    if data.falha_tipo:
        if os.falha_tipo != data.falha_tipo:
            changes["falha_tipo"] = {"de": os.falha_tipo or "", "para": data.falha_tipo}
        os.falha_tipo = data.falha_tipo
    if data.falha_modo:
        if os.falha_modo != data.falha_modo:
            changes["falha_modo"] = {"de": os.falha_modo or "", "para": data.falha_modo}
        os.falha_modo = data.falha_modo
    if data.falha_causa:
        if os.falha_causa != data.falha_causa:
            changes["falha_causa"] = {"de": os.falha_causa or "", "para": data.falha_causa}
        os.falha_causa = data.falha_causa
    if data.failure_group is not None:
        if os.failure_group != data.failure_group:
            changes["failure_group"] = {"de": os.failure_group or "", "para": data.failure_group}
        os.failure_group = data.failure_group
    if data.review_notes:
        os.review_notes = data.review_notes
        changes["review_notes"] = data.review_notes
    if data.area_manutencao is not None:
        os.area_manutencao = data.area_manutencao or None
    if data.subarea_manutencao is not None:
        os.subarea_manutencao = data.subarea_manutencao or None

    db.commit()
    db.refresh(os)

    # Grava entrada no histórico se houve mudança de status
    if data.status:
        _record_os_historico(
            db, os.id, data.status.value,
            user_id=user.id, user_nome=user.nome,
            timestamp=now,
            custom_label=_aceitacao_label if data.status == StatusOS.EM_ATENDIMENTO else None,
        )
        db.commit()

    # Enhanced audit log with field changes
    create_audit_log(
        db, str(user.organization_id), str(user.id), "ordem_servico", str(os.id), "update",
        dados_anteriores=None,
        dados_novos=json_lib.dumps(changes, ensure_ascii=False) if changes else None
    )

    # Fase 3 — broadcast SSE: mudança de status
    if data.status:
        try:
            from app.services.realtime import publish_sync as _pub
            _equip = db.query(Equipamento).filter(Equipamento.id == os.equipamento_id).first()
            _pub(str(os.organization_id), "os_status_changed", {
                "os_id": str(os.id),
                "numero": os.numero,
                "status": os.status.value,
                "equipamento": _equip.nome if _equip else None,
            })
        except Exception:
            pass

    return _build_os_response(os, db, user=user)

class OSReatribuirRequest(BaseModel):
    nova_matricula: str
    motivo: Optional[str] = None

@router.patch("/ordens-servico/{os_id}/reassinar", response_model=OSResponse)
async def reassinar_tecnico(
    os_id: str,
    data: OSReatribuirRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin/líder reatribui o técnico responsável por uma OS já em atendimento."""
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Apenas admin ou líder podem reatribuir técnicos")

    os = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os:
        raise HTTPException(status_code=404, detail="OS não encontrada")

    if os.status not in [StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_PECA]:
        raise HTTPException(status_code=400, detail="Só é possível reatribuir OS abertas ou em atendimento")

    # Lookup do novo colaborador
    novo_col = db.query(Colaborador).filter(
        Colaborador.organization_id == user.organization_id,
        Colaborador.matricula == data.nova_matricula.strip(),
        Colaborador.ativo == True,
    ).first()
    if not novo_col:
        raise HTTPException(status_code=404, detail="Matrícula não encontrada no cadastro de colaboradores")

    now = datetime.now(timezone.utc)
    area = novo_col.setor or novo_col.cargo or "Manutenção"
    hora = now.strftime("%H:%M")

    # Registrar técnico anterior para o label
    tecnico_anterior = os.technician_employee_id or "—"

    # Atualizar OS
    os.technician_employee_id = data.nova_matricula.strip()
    os.tecnico_id = None  # desvincula usuário anterior (referência interna)
    if os.status == StatusOS.ABERTA:
        os.inicio_atendimento = now
        os.tempo_resposta = int((now - os.created_at).total_seconds() / 60)
        os.dentro_sla = calculate_sla(os.prioridade, os.tempo_resposta)
        os.status = StatusOS.EM_ATENDIMENTO

    db.commit()

    # Histórico da reatribuição
    motivo_txt = f" · Motivo: {data.motivo.strip()}" if data.motivo and data.motivo.strip() else ""
    label_reatrib = f"Reatribuído para {novo_col.nome} · {area} · por {user.nome} às {hora}{motivo_txt}"
    _record_os_historico(
        db, os.id, os.status.value,
        user_id=user.id, user_nome=user.nome,
        timestamp=now, custom_label=label_reatrib,
    )
    db.commit()
    db.refresh(os)

    create_audit_log(db, str(user.organization_id), str(user.id), "ordem_servico", str(os.id), "reassign")

    return _build_os_response(os, db, user=user)

@router.get("/ordens-servico/{os_id}/excecoes-area", response_model=List[OSExcecaoAreaResponse])
async def list_excecoes_area(
    os_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista os crachás autorizados pelo líder/admin para atender esta OS fora da área."""
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    rows = db.query(OSExcecaoArea).filter(OSExcecaoArea.os_id == os_obj.id).order_by(OSExcecaoArea.created_at).all()
    return [OSExcecaoAreaResponse(
        id=str(r.id), os_id=str(r.os_id), matricula=r.matricula,
        colaborador_nome=r.colaborador_nome, autorizado_por_nome=r.autorizado_por_nome,
        created_at=r.created_at,
    ) for r in rows]


class _ExcecaoAreaCreate(BaseModel):
    matricula: str

@router.post("/ordens-servico/{os_id}/excecoes-area", response_model=OSExcecaoAreaResponse)
async def add_excecao_area(
    os_id: str,
    data: _ExcecaoAreaCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin/líder autoriza um crachá para atender esta OS fora da sua área habitual."""
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Apenas admin ou líder podem adicionar autorizações de área")
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")

    # Lookup colaborador
    col = db.query(Colaborador).filter(
        Colaborador.organization_id == user.organization_id,
        Colaborador.matricula == data.matricula.strip(),
        Colaborador.ativo == True,
    ).first()
    if not col:
        raise HTTPException(status_code=404, detail="Matrícula não encontrada no cadastro de colaboradores")

    # Evita duplicata
    existing = db.query(OSExcecaoArea).filter(
        OSExcecaoArea.os_id == os_obj.id,
        OSExcecaoArea.matricula == data.matricula.strip(),
    ).first()
    if existing:
        return OSExcecaoAreaResponse(
            id=str(existing.id), os_id=str(existing.os_id), matricula=existing.matricula,
            colaborador_nome=existing.colaborador_nome, autorizado_por_nome=existing.autorizado_por_nome,
            created_at=existing.created_at,
        )

    excecao = OSExcecaoArea(
        os_id=os_obj.id,
        matricula=data.matricula.strip(),
        colaborador_nome=col.nome,
        autorizado_por_id=user.id,
        autorizado_por_nome=user.nome,
    )
    db.add(excecao)
    db.commit()
    db.refresh(excecao)

    _record_os_historico(
        db, os_obj.id, os_obj.status.value,
        user_id=user.id, user_nome=user.nome,
        timestamp=datetime.now(timezone.utc),
        custom_label=f"Autorizado por {user.nome}: {col.nome} ({data.matricula.strip()}) poderá atender esta OS",
    )
    db.commit()

    return OSExcecaoAreaResponse(
        id=str(excecao.id), os_id=str(excecao.os_id), matricula=excecao.matricula,
        colaborador_nome=excecao.colaborador_nome, autorizado_por_nome=excecao.autorizado_por_nome,
        created_at=excecao.created_at,
    )

@router.delete("/ordens-servico/{os_id}/excecoes-area/{matricula}")
async def remove_excecao_area(
    os_id: str,
    matricula: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin/líder remove autorização de área de um crachá."""
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Apenas admin ou líder podem remover autorizações de área")
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    row = db.query(OSExcecaoArea).filter(
        OSExcecaoArea.os_id == os_obj.id,
        OSExcecaoArea.matricula == matricula,
    ).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}

@router.post("/ordens-servico/auto-approve")
async def auto_approve_expired_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Auto-approve work orders past their 24h review deadline"""
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    now = datetime.now(timezone.utc)
    expired = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.status == StatusOS.AGUARDANDO_REVISAO,
        OrdemServico.review_deadline != None,
        OrdemServico.review_deadline < now
    ).all()
    
    count = 0
    for os_item in expired:
        os_item.status = StatusOS.REVISADA
        os_item.revisado_at = now
        os_item.auto_approved = True
        os_item.review_notes = "Auto-aprovada: prazo de revisão de 24h expirado"
        count += 1
        create_audit_log(db, str(user.organization_id), str(user.id), "ordem_servico", str(os_item.id), "auto_approve")
    
    db.commit()
    return {"auto_approved": count, "message": f"{count} OS auto-aprovadas"}

@router.get("/ordens-servico/pending-reviews")
async def get_pending_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get work orders pending review for the current user"""
    now = datetime.now(timezone.utc)
    
    query = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.status == StatusOS.AGUARDANDO_REVISAO
    )
    
    # Filtro por role — cada líder vê apenas OS da sua área
    if user.role == UserRole.LIDER:
        query = query.filter(OrdemServico.revisor_id == user.id)
    elif user.role == UserRole.LIDER_MANUTENCAO_ELETRICA:
        query = query.filter(OrdemServico.area_manutencao == "eletrica")
    elif user.role == UserRole.LIDER_MANUTENCAO_MECANICA:
        query = query.filter(OrdemServico.area_manutencao == "mecanica")
    elif user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    pending = query.order_by(OrdemServico.review_deadline.asc()).all()
    
    results = []
    for o in pending:
        resp = _build_os_response(o, db, user=user)
        time_remaining = None
        if o.review_deadline:
            remaining = (o.review_deadline - now).total_seconds()
            time_remaining = max(0, round(remaining / 3600, 1))
        results.append({
            **resp.model_dump(),
            "hours_remaining": time_remaining,
            "is_expired": time_remaining is not None and time_remaining <= 0
        })
    
    return results

@router.get("/ordens-servico/{os_id}", response_model=OSResponse)
async def get_os(os_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    os = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id
    ).first()
    if not os:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return _build_os_response(os, db, user=user)


class OcorrenciaCreate(BaseModel):
    descricao: str

@router.post("/ordens-servico/{os_id}/ocorrencias", response_model=OSResponse)
async def add_ocorrencia(
    os_id: str,
    data: OcorrenciaCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Spec 3.2.2 — O operador adiciona uma nova ocorrência de falha à OS.
    Adiciona registro com timestamp sem sobrescrever o original.
    Notifica o técnico atribuído.
    """
    import json as _json

    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")

    if os_obj.status == StatusOS.FECHADA:
        raise HTTPException(status_code=400, detail="Não é possível adicionar ocorrências a uma OS fechada.")

    # Apenas operador, tecnico, lider e admin podem adicionar ocorrências
    if user.role not in (UserRole.OPERADOR, UserRole.TECNICO, UserRole.LIDER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acesso negado.")

    now = datetime.now(timezone.utc)
    nova_ocorrencia = {
        "timestamp": now.isoformat(),
        "descricao": data.descricao.strip(),
        "user_id": str(user.id),
        "user_nome": user.nome,
        "employee_id": user.employee_id,
    }

    try:
        ocorrencias = _json.loads(os_obj.occurrences) if os_obj.occurrences else []
    except Exception:
        ocorrencias = []

    ocorrencias.append(nova_ocorrencia)
    os_obj.occurrences = _json.dumps(ocorrencias, ensure_ascii=False)
    db.commit()

    # Notificar técnico atribuído
    if os_obj.tecnico_id:
        criar_notificacao(
            db,
            org_id=os_obj.organization_id,
            destinatario_id=os_obj.tecnico_id,
            tipo="nova_ocorrencia",
            titulo=f"Nova ocorrência na OS #{os_obj.numero}",
            mensagem=f"{user.nome} adicionou: {data.descricao[:100]}",
            os_id=os_obj.id,
        )

    create_audit_log(
        db, str(user.organization_id), str(user.id), "ordem_servico", str(os_obj.id),
        "add_ocorrencia",
        dados_novos=_json.dumps(nova_ocorrencia, ensure_ascii=False),
    )

    db.refresh(os_obj)
    return _build_os_response(os_obj, db, user=user)

@router.patch("/ordens-servico/{os_id}/ocorrencia")
async def patch_ocorrencia(
    os_id: str,
    data: OcorrenciaCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FASE 3.2 — Operador adiciona ocorrência a uma OS.
    Não altera status nem downtime_start. Append-only no array JSON.
    Notifica o técnico atribuído.
    """
    import json as _json

    if user.role not in (UserRole.OPERADOR, UserRole.TECNICO, UserRole.LIDER, UserRole.ADMIN, UserRole.SUPERUSUARIO):
        raise HTTPException(status_code=403, detail="Acesso negado.")

    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    if os_obj.status == StatusOS.FECHADA:
        raise HTTPException(status_code=400, detail="Não é possível adicionar ocorrências a uma OS fechada.")

    now = datetime.now(timezone.utc)
    nova = {
        "timestamp": now.isoformat(),
        "operador_id": str(user.id),
        "operador_nome": user.nome,
        "descricao": data.descricao.strip(),
    }

    try:
        lista = _json.loads(os_obj.occurrences) if os_obj.occurrences else []
    except Exception:
        lista = []

    lista.append(nova)
    os_obj.occurrences = _json.dumps(lista, ensure_ascii=False)
    db.commit()

    if os_obj.tecnico_id:
        criar_notificacao(
            db,
            org_id=os_obj.organization_id,
            destinatario_id=os_obj.tecnico_id,
            tipo="nova_ocorrencia",
            titulo=f"Nova ocorrência na OS #{os_obj.numero}",
            mensagem=f"{user.nome}: {data.descricao[:100]}",
            os_id=os_obj.id,
        )

    create_audit_log(
        db, str(user.organization_id), str(user.id), "ordem_servico", str(os_obj.id),
        "adicao_ocorrencia",
        dados_novos=_json.dumps(nova, ensure_ascii=False),
    )

    return {
        "id": str(os_obj.id),
        "occurrences": lista,
        "updated_at": now.isoformat(),
    }


# ========== EQUIPE DE OS (preventiva/preditiva) ==========
_GRUPO_MANUTENCAO_ROLES = [
    UserRole.ADMIN, UserRole.TECNICO,
    UserRole.LIDER_MANUTENCAO_ELETRICA, UserRole.LIDER_MANUTENCAO_MECANICA,
    UserRole.SUPERVISOR_MANUTENCAO, UserRole.ANALISTA_MANUTENCAO,
    UserRole.ENGENHEIRO_MANUTENCAO, UserRole.GERENTE_INDUSTRIAL,
]

def _build_equipe_response(m: OSEquipe, db: Session) -> OSEquipeResponse:
    adicionado_por_nome = None
    if m.adicionado_por:
        u = db.query(User).filter(User.id == m.adicionado_por).first()
        if u:
            adicionado_por_nome = u.nome
    return OSEquipeResponse(
        id=str(m.id), os_id=str(m.os_id),
        user_id=str(m.user_id) if m.user_id else None,
        nome_membro=m.nome_membro,
        cracha=m.cracha, especialidade=m.especialidade,
        adicionado_em=m.adicionado_em,
        adicionado_por=str(m.adicionado_por) if m.adicionado_por else None,
        adicionado_por_nome=adicionado_por_nome,
    )

@router.get("/ordens-servico/{os_id}/equipe", response_model=List[OSEquipeResponse])
async def get_os_equipe(os_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id, OrdemServico.organization_id == user.organization_id
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    membros = db.query(OSEquipe).filter(OSEquipe.os_id == os_id).order_by(OSEquipe.adicionado_em).all()
    return [_build_equipe_response(m, db) for m in membros]

@router.post("/ordens-servico/{os_id}/equipe", response_model=OSEquipeResponse)
async def add_os_equipe(os_id: str, data: OSEquipeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in _GRUPO_MANUTENCAO_ROLES:
        raise HTTPException(status_code=403, detail="Apenas equipe de manutenção pode gerenciar a equipe de OS.")
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id, OrdemServico.organization_id == user.organization_id
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")

    # Resolve membro via crachá se fornecido
    _user_id = None
    _nome = (data.nome_membro or "").strip()
    _cracha = (data.cracha or "").strip() or None
    if _cracha:
        found = db.query(User).filter(
            User.organization_id == user.organization_id,
            User.employee_id == _cracha,
            User.ativo == True,
        ).first()
        if found:
            _user_id = found.id
            _nome = found.nome

    if not _nome:
        raise HTTPException(status_code=422, detail="Nome do membro é obrigatório.")

    membro = OSEquipe(
        os_id=os_id,
        user_id=_user_id,
        nome_membro=_nome,
        cracha=_cracha,
        especialidade=(data.especialidade or "").strip() or None,
        adicionado_por=user.id,
    )
    db.add(membro)
    db.commit()
    db.refresh(membro)
    return _build_equipe_response(membro, db)

@router.get("/ordens-servico/{os_id}/historico", response_model=List[OSHistoricoResponse])
async def get_os_historico(os_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retorna a timeline de etapas de uma OS, ordenada por timestamp ASC."""
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id, OrdemServico.organization_id == user.organization_id
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    entradas = db.query(OSHistorico).filter(OSHistorico.os_id == os_id).order_by(OSHistorico.timestamp.asc()).all()
    return [OSHistoricoResponse(
        id=str(e.id), os_id=str(e.os_id),
        status_novo=e.status_novo, etapa_label=e.etapa_label,
        timestamp=e.timestamp,
        user_id=str(e.user_id) if e.user_id else None,
        user_nome=e.user_nome,
    ) for e in entradas]

@router.delete("/ordens-servico/{os_id}/equipe/{membro_id}", status_code=204)
async def remove_os_equipe(os_id: str, membro_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _PODE_REMOVER_ROLES = [UserRole.ADMIN, UserRole.SUPERVISOR_MANUTENCAO, UserRole.GERENTE_INDUSTRIAL,
                           UserRole.LIDER_MANUTENCAO_ELETRICA, UserRole.LIDER_MANUTENCAO_MECANICA]
    membro = db.query(OSEquipe).filter(
        OSEquipe.id == membro_id, OSEquipe.os_id == os_id
    ).first()
    if not membro:
        raise HTTPException(status_code=404, detail="Membro não encontrado")
    if user.role not in _PODE_REMOVER_ROLES and str(membro.adicionado_por) != str(user.id):
        raise HTTPException(status_code=403, detail="Sem permissão para remover este membro.")
    db.delete(membro)
    db.commit()
    return None

# ========== CUSTOS ENDPOINTS ==========

@router.patch("/ordens-servico/{os_id}/custo-mao-obra")
async def patch_custo_mao_obra(os_id: str, data: CustoMaoObraUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _PODE_CORRIGIR = [UserRole.ADMIN, UserRole.SUPERVISOR_MANUTENCAO, UserRole.ANALISTA_MANUTENCAO, UserRole.GERENTE_INDUSTRIAL]
    if user.role not in _PODE_CORRIGIR:
        raise HTTPException(status_code=403, detail="Sem permissão para ajustar custo de mão de obra.")
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id, OrdemServico.organization_id == user.organization_id
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    os_obj.horas_trabalhadas = data.horas_trabalhadas
    os_obj.valor_hora_tecnico = data.valor_hora_tecnico
    os_obj.custo_mao_obra = round(data.horas_trabalhadas * data.valor_hora_tecnico, 2)
    db.commit()
    create_audit_log(db, str(user.organization_id), str(user.id), "ordem_servico", str(os_obj.id), "patch_custo_mao_obra",
        dados_novos=f'{{"horas":{data.horas_trabalhadas},"valor_hora":{data.valor_hora_tecnico},"custo_mao_obra":{os_obj.custo_mao_obra}}}')
    return {"custo_mao_obra": os_obj.custo_mao_obra, "horas_trabalhadas": os_obj.horas_trabalhadas, "valor_hora_tecnico": os_obj.valor_hora_tecnico}

# ── Fase 1: Consumo de peça em OS ────────────────────────────────────────────

class ConsumoOSPayload(BaseModel):
    peca_id: str
    deposito_id: str
    quantidade: float = Field(..., gt=0)
    motivo: Optional[str] = None

@router.post("/ordens-servico/{os_id}/pecas", status_code=201)
async def consumir_peca_em_os(
    os_id: str,
    data: ConsumoOSPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra consumo de peça em uma OS: baixa atômica + custo somado à OS."""
    # Verifica feature flag do plano
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_estoque")

    # Roles permitidos: todos os de manutenção (técnico pode registrar o que usou)
    _PODE_CONSUMIR = {
        UserRole.ADMIN, UserRole.LIDER, UserRole.TECNICO,
        UserRole.SUPERVISOR_MANUTENCAO, UserRole.ANALISTA_MANUTENCAO,
        UserRole.ENGENHEIRO_MANUTENCAO, UserRole.LIDER_MANUTENCAO_ELETRICA,
        UserRole.LIDER_MANUTENCAO_MECANICA, UserRole.GERENTE_INDUSTRIAL,
    }
    if user.role not in _PODE_CONSUMIR:
        raise HTTPException(status_code=403, detail="Sem permissão para registrar consumo de peças.")

    # OS deve pertencer à org
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada.")

    # Importa modelos e services do módulo de estoque
    from app.models.estoque import Peca, Deposito, SaldoEstoque
    from app.services.estoque_service import registrar_saida, EstoqueError, saldo_total_peca

    peca = db.query(Peca).filter(
        Peca.id == data.peca_id,
        Peca.organization_id == user.organization_id,
    ).first()
    if not peca:
        raise HTTPException(status_code=404, detail="Peça não encontrada.")

    deposito = db.query(Deposito).filter(
        Deposito.id == data.deposito_id,
        Deposito.organization_id == user.organization_id,
    ).first()
    if not deposito:
        raise HTTPException(status_code=404, detail="Depósito não encontrado.")

    try:
        mov, saldo = registrar_saida(
            db, peca, deposito, data.quantidade,
            str(user.id), str(user.organization_id),
            motivo=data.motivo or f"Consumo na OS {os_obj.numero}",
            os_id=str(os_obj.id),
        )
    except EstoqueError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    # Soma custo à OS (campo custo_total_pecas — adicionado via migration)
    custo_mov = float(mov.custo_total or 0)
    custo_atual = float(os_obj.custo_total_pecas or 0) if hasattr(os_obj, "custo_total_pecas") else 0
    if hasattr(os_obj, "custo_total_pecas"):
        os_obj.custo_total_pecas = custo_atual + custo_mov

    db.commit()

    # Verifica ponto de pedido após baixa
    from app.services.estoque_service import verificar_ponto_pedido
    try:
        verificar_ponto_pedido(db, peca, saldo.quantidade, str(user.organization_id), criar_notificacao)
    except Exception:
        pass

    saldo_total = saldo_total_peca(db, str(peca.id), str(user.organization_id))

    create_audit_log(
        db, str(user.organization_id), str(user.id),
        "estoque", str(peca.id), "consumo_os",
        dados_novos=f'{{"os_id":"{os_id}","peca":"{peca.codigo}","qty":{data.quantidade},"custo":{custo_mov}}}',
        ip=None,
    )

    return {
        "movimento_id": str(mov.id),
        "peca_id": str(peca.id),
        "peca_codigo": peca.codigo,
        "peca_descricao": peca.descricao,
        "quantidade": data.quantidade,
        "custo_unitario": float(mov.custo_unitario or 0),
        "custo_total": custo_mov,
        "saldo_atual": saldo_total,
        "abaixo_ponto_pedido": saldo_total <= peca.ponto_pedido and peca.ponto_pedido > 0,
    }


# Endpoint: listar peças consumidas em uma OS

@router.get("/ordens-servico/{os_id}/pecas")
async def listar_pecas_da_os(
    os_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista todas as peças consumidas em uma OS, com custo total."""
    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada.")

    from app.models.estoque import MovimentoEstoque, Peca, Deposito, TipoMovimento
    movs = db.query(MovimentoEstoque).filter(
        MovimentoEstoque.os_id == os_id,
        MovimentoEstoque.organization_id == user.organization_id,
        MovimentoEstoque.tipo == TipoMovimento.SAIDA,
    ).order_by(MovimentoEstoque.criado_em).all()

    total_custo = sum(float(m.custo_total or 0) for m in movs)
    itens = []
    for m in movs:
        peca = m.peca
        dep = m.deposito
        itens.append({
            "movimento_id": str(m.id),
            "peca_id": str(m.peca_id),
            "peca_codigo": peca.codigo if peca else "",
            "peca_descricao": peca.descricao if peca else "",
            "unidade": peca.unidade if peca else "un",
            "deposito": dep.nome if dep else "",
            "quantidade": m.quantidade,
            "custo_unitario": float(m.custo_unitario or 0),
            "custo_total": float(m.custo_total or 0),
            "motivo": m.motivo,
            "criado_em": m.criado_em.isoformat() if m.criado_em else None,
        })

    return {"itens": itens, "custo_total_pecas": total_custo}


# ========== PLANOS PREVENTIVOS ENDPOINTS ==========
