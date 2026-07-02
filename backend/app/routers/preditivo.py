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

from ..services import preditivo_service

router = APIRouter(tags=["Preditivo"])

# ── Serviço preditivo (funções extraídas para app/services/preditivo_service.py) ──
from ..services import preditivo_service


@router.get("/confiabilidade")
async def get_confiabilidade(
    t: float = 24.0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calcula indicadores de confiabilidade por equipamento:
    - λ (lambda) = falhas / tempo_operacao (taxa de falha)
    - R(t) = e^(-λ*t) (confiabilidade exponencial)
    - Risco = (1 - R(t)) * criticidade_equipamento (probabilidade × impacto)
    - Alertas automáticos por nível de risco

    Query param 't' = horizonte de tempo em horas para projeção (default: 24h)
    """
    from sqlalchemy import func

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")

    org_id = user.organization_id

    # Buscar todos equipamentos ativos
    equipamentos = db.query(Equipamento).filter(
        Equipamento.organization_id == org_id,
        Equipamento.ativo == True
    ).all()

    if not equipamentos:
        return {
            "horizonte_horas": t,
            "resumo": {"total_equipamentos": 0, "alertas_criticos": 0, "alertas_atencao": 0, "confiabilidade_media": 100.0, "lambda_medio": 0.0},
            "equipamentos": [],
            "alertas": []
        }

    now = datetime.now(timezone.utc)

    # Primeira OS corretiva global (para calcular janela de operação)
    first_os_global = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.tipo == TipoOS.CORRETIVA
    ).order_by(OrdemServico.created_at).first()

    resultados = []
    alertas = []

    for equip in equipamentos:
        # Buscar somente OS corretivas com parada para este equipamento
        os_corretivas = db.query(OrdemServico).filter(
            OrdemServico.organization_id == org_id,
            OrdemServico.equipamento_id == equip.id,
            OrdemServico.tipo == TipoOS.CORRETIVA,
            OrdemServico.status.in_([StatusOS.FECHADA, StatusOS.REVISADA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_REVISAO])
        ).all()

        falhas = len(os_corretivas)

        # Tempo total parado (minutos → horas)
        tempo_parado_horas = sum(o.tempo_total or 0 for o in os_corretivas) / 60

        # Tempo de operação: desde a criação do equipamento ou primeira OS, até agora, menos tempo parado
        ref_date = equip.created_at or (first_os_global.created_at if first_os_global else now)
        tempo_total_horas = max((now - ref_date).total_seconds() / 3600, 1)  # no mínimo 1h
        tempo_operacao = max(tempo_total_horas - tempo_parado_horas, 1)  # no mínimo 1h

        # λ (lambda) = falhas / tempo_operacao
        lam = falhas / tempo_operacao if tempo_operacao > 0 else 0

        # MTBF = 1/λ (horas)
        mtbf = (1 / lam) if lam > 0 else tempo_operacao

        # R(t) = e^(-λ*t) — confiabilidade no horizonte t
        r_t = math.exp(-lam * t) if lam > 0 else 1.0
        r_t_percent = round(r_t * 100, 2)

        # Probabilidade de falha no horizonte
        prob_falha = 1 - r_t

        # Risco = probabilidade × impacto (criticidade 1-5 normalizada para 0-1)
        impacto_normalizado = equip.criticidade / 5.0
        risco = prob_falha * impacto_normalizado
        risco_percent = round(risco * 100, 2)

        # Custo de risco projetado (probabilidade × custo/hora × horizonte)
        custo_risco = round(prob_falha * equip.valor_hora * t, 2) if equip.valor_hora else 0

        # Classificação de risco
        if risco_percent >= 60:
            nivel_risco = "critico"
        elif risco_percent >= 30:
            nivel_risco = "alto"
        elif risco_percent >= 10:
            nivel_risco = "atencao"
        else:
            nivel_risco = "normal"

        # Classificação de lambda
        if lam >= 0.05:
            lambda_status = "instavel"
        elif lam >= 0.01:
            lambda_status = "atencao"
        else:
            lambda_status = "estavel"

        resultado = {
            "equipamento_id": str(equip.id),
            "codigo": equip.codigo,
            "nome": equip.nome,
            "criticidade": equip.criticidade,
            "valor_hora": equip.valor_hora,
            "falhas": falhas,
            "tempo_operacao_horas": round(tempo_operacao, 2),
            "tempo_parado_horas": round(tempo_parado_horas, 2),
            "lambda": round(lam, 6),
            "lambda_status": lambda_status,
            "mtbf_horas": round(mtbf, 2),
            "confiabilidade_percent": r_t_percent,
            "prob_falha_percent": round(prob_falha * 100, 2),
            "risco_percent": risco_percent,
            "nivel_risco": nivel_risco,
            "custo_risco_projetado": custo_risco,
        }
        resultados.append(resultado)

        # Gerar alertas automáticos
        if nivel_risco == "critico":
            alertas.append({
                "tipo": "critico",
                "equipamento": equip.nome,
                "codigo": equip.codigo,
                "mensagem": f"⚠️ RISCO CRÍTICO: {equip.nome} ({equip.codigo}) — confiabilidade {r_t_percent}% em {t}h. λ={round(lam, 4)} falhas/h. Ação imediata necessária.",
                "lambda": round(lam, 4),
                "confiabilidade": r_t_percent,
                "risco": risco_percent,
            })
        elif nivel_risco == "alto":
            alertas.append({
                "tipo": "alto",
                "equipamento": equip.nome,
                "codigo": equip.codigo,
                "mensagem": f"🔶 RISCO ALTO: {equip.nome} ({equip.codigo}) — confiabilidade {r_t_percent}% em {t}h. Priorizar RCA e preventiva.",
                "lambda": round(lam, 4),
                "confiabilidade": r_t_percent,
                "risco": risco_percent,
            })
        elif nivel_risco == "atencao":
            alertas.append({
                "tipo": "atencao",
                "equipamento": equip.nome,
                "codigo": equip.codigo,
                "mensagem": f"🟡 ATENÇÃO: {equip.nome} ({equip.codigo}) — confiabilidade {r_t_percent}% em {t}h. Monitorar tendência.",
                "lambda": round(lam, 4),
                "confiabilidade": r_t_percent,
                "risco": risco_percent,
            })

    # Ordenar equipamentos por risco (maior primeiro)
    resultados.sort(key=lambda x: x["risco_percent"], reverse=True)
    alertas.sort(key=lambda x: x["risco"], reverse=True)

    # Resumo
    lambdas = [r["lambda"] for r in resultados if r["lambda"] > 0]
    confiabilidades = [r["confiabilidade_percent"] for r in resultados]

    resumo = {
        "total_equipamentos": len(resultados),
        "alertas_criticos": len([a for a in alertas if a["tipo"] == "critico"]),
        "alertas_alto": len([a for a in alertas if a["tipo"] == "alto"]),
        "alertas_atencao": len([a for a in alertas if a["tipo"] == "atencao"]),
        "confiabilidade_media": round(sum(confiabilidades) / len(confiabilidades), 2) if confiabilidades else 100.0,
        "lambda_medio": round(sum(lambdas) / len(lambdas), 6) if lambdas else 0,
        "equipamentos_instáveis": len([r for r in resultados if r["lambda_status"] == "instavel"]),
    }

    return {
        "horizonte_horas": t,
        "resumo": resumo,
        "equipamentos": resultados,
        "alertas": alertas,
    }

@router.get("/confiabilidade/{equipamento_id}/curva")
async def get_curva_confiabilidade(
    equipamento_id: str,
    max_t: float = 168.0,
    pontos: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Gera a curva de confiabilidade R(t) = e^(-λt) para um equipamento específico.
    Retorna pontos da curva para plotar gráfico.

    - max_t: horizonte máximo em horas (default: 168h = 1 semana)
    - pontos: número de pontos na curva (default: 50)
    """
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")

    equip = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()

    if not equip:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")

    now = datetime.now(timezone.utc)

    # Buscar OS corretivas
    os_corretivas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.equipamento_id == equip.id,
        OrdemServico.tipo == TipoOS.CORRETIVA,
        OrdemServico.status.in_([StatusOS.FECHADA, StatusOS.REVISADA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_REVISAO])
    ).all()

    falhas = len(os_corretivas)
    tempo_parado = sum(o.tempo_total or 0 for o in os_corretivas) / 60
    ref_date = equip.created_at or now
    tempo_total = max((now - ref_date).total_seconds() / 3600, 1)
    tempo_operacao = max(tempo_total - tempo_parado, 1)

    lam = falhas / tempo_operacao if tempo_operacao > 0 else 0
    mtbf = (1 / lam) if lam > 0 else tempo_operacao

    # Gerar pontos da curva
    curva = []
    step = max_t / pontos
    for i in range(pontos + 1):
        t_val = round(step * i, 2)
        r_val = math.exp(-lam * t_val) if lam > 0 else 1.0
        curva.append({
            "t": t_val,
            "R_t": round(r_val * 100, 2),
            "prob_falha": round((1 - r_val) * 100, 2),
        })

    return {
        "equipamento": {
            "id": str(equip.id),
            "codigo": equip.codigo,
            "nome": equip.nome,
            "criticidade": equip.criticidade,
        },
        "parametros": {
            "lambda": round(lam, 6),
            "mtbf_horas": round(mtbf, 2),
            "falhas": falhas,
            "tempo_operacao_horas": round(tempo_operacao, 2),
        },
        "curva": curva,
    }

# ========== RELATÓRIOS ==========

def sugerir_upgrade(plano_atual: PlanoSaaS, feature: str) -> str:
    ordem = [PlanoSaaS.DEMO, PlanoSaaS.ESSENCIAL, PlanoSaaS.PROFISSIONAL, PlanoSaaS.AVANCADO, PlanoSaaS.ENTERPRISE]
    idx = ordem.index(plano_atual) if plano_atual in ordem else 0
    for p in ordem[idx + 1:]:
        if PLAN_LIMITS.get(p, {}).get(feature):
            return p.value
    return PlanoSaaS.ENTERPRISE.value


def _require_feature(org: Organization, feature: str):
    plano = org.plano if org else PlanoSaaS.DEMO
    limits = PLAN_LIMITS.get(plano, PLAN_LIMITS[PlanoSaaS.DEMO])
    if not limits.get(feature, False):
        raise HTTPException(
            status_code=402,
            detail={
                "code": "feature_locked",
                "feature": feature,
                "mensagem": f"O recurso '{feature}' não está disponível no plano {limits.get('label', str(plano))}.",
                "plano_atual": plano.value if hasattr(plano, "value") else str(plano),
                "upgrade_sugerido": sugerir_upgrade(plano, feature),
                "url_upgrade": "/billing",
            }
        )

@router.post("/preditivo/configuracoes", status_code=201)
async def criar_config_monitoramento(
    data: ConfigMonitoramentoCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])
    max_pred = limits.get("max_equipamentos_preditivo", 0)
    if max_pred != -1:
        atual = db.query(ConfiguracaoMonitoramento).filter(
            ConfiguracaoMonitoramento.organization_id == user.organization_id,
            ConfiguracaoMonitoramento.ativo == True,
        ).distinct(ConfiguracaoMonitoramento.equipamento_id).count()
        if atual >= max_pred:
            raise HTTPException(status_code=402, detail={
                "code": "limite_atingido",
                "mensagem": f"Limite de {max_pred} equipamentos monitorados atingido no plano {limits.get('label')}.",
                "upgrade_sugerido": sugerir_upgrade(org.plano, "max_equipamentos_preditivo"),
                "url_upgrade": "/billing",
            })
    cfg = ConfiguracaoMonitoramento(
        organization_id=user.organization_id,
        equipamento_id=data.equipamento_id,
        parametro_nome=data.parametro_nome,
        unidade=data.unidade,
        threshold_atencao=data.threshold_atencao,
        threshold_critico=data.threshold_critico,
        tendencia_janela_dias=data.tendencia_janela_dias,
    )
    db.add(cfg)
    equip = db.query(Equipamento).filter(Equipamento.id == data.equipamento_id).first()
    if equip:
        equip.monitoramento_ativo = True
    db.commit()
    db.refresh(cfg)
    return {"id": str(cfg.id), "mensagem": "Monitoramento configurado"}

@router.get("/preditivo/configuracoes")
async def listar_configs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    cfgs = db.query(ConfiguracaoMonitoramento).filter(
        ConfiguracaoMonitoramento.organization_id == user.organization_id,
    ).all()
    equips = {str(e.id): e.nome for e in db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id).all()}
    return [{"id": str(c.id), "equipamento_id": str(c.equipamento_id),
             "equipamento_nome": equips.get(str(c.equipamento_id), ""),
             "parametro_nome": c.parametro_nome, "unidade": c.unidade,
             "threshold_atencao": c.threshold_atencao, "threshold_critico": c.threshold_critico,
             "tendencia_janela_dias": c.tendencia_janela_dias, "ativo": c.ativo} for c in cfgs]

@router.put("/preditivo/configuracoes/{cfg_id}")
async def atualizar_config(
    cfg_id: str, data: ConfigMonitoramentoCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    cfg = db.query(ConfiguracaoMonitoramento).filter(
        ConfiguracaoMonitoramento.id == cfg_id,
        ConfiguracaoMonitoramento.organization_id == user.organization_id,
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    cfg.threshold_atencao = data.threshold_atencao
    cfg.threshold_critico = data.threshold_critico
    cfg.tendencia_janela_dias = data.tendencia_janela_dias
    cfg.unidade = data.unidade
    db.commit()
    return {"mensagem": "Atualizado"}

@router.post("/preditivo/leituras", status_code=201)
async def registrar_leitura(
    data: LeituraCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    leitura = LeituraSensor(
        organization_id=user.organization_id,
        equipamento_id=data.equipamento_id,
        parametro_nome=data.parametro_nome,
        valor=data.valor,
        unidade=data.unidade,
        fonte=data.fonte,
        registrado_por=user.id,
        timestamp=data.timestamp or datetime.now(timezone.utc),
    )
    db.add(leitura)
    db.commit()
    db.refresh(leitura)
    preditivo_service.processar_leitura_preditiva(db, leitura)
    return {"id": str(leitura.id), "processado": leitura.processado}

@router.post("/preditivo/leituras/bulk", status_code=201)
async def registrar_leituras_bulk(
    data: LeiturasBulk,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    criadas = 0
    for item in data.leituras[:100]:  # limite de 100 por batch
        leitura = LeituraSensor(
            organization_id=user.organization_id,
            equipamento_id=item.equipamento_id,
            parametro_nome=item.parametro_nome,
            valor=item.valor,
            unidade=item.unidade,
            fonte=item.fonte or "api_externa",
            registrado_por=user.id,
            timestamp=item.timestamp or datetime.now(timezone.utc),
        )
        db.add(leitura)
        criadas += 1
    db.commit()
    return {"criadas": criadas, "mensagem": "Leituras agendadas para processamento"}

@router.get("/preditivo/leituras/{equipamento_id}")
async def historico_leituras(
    equipamento_id: str,
    parametro: Optional[str] = None,
    dias: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    q = db.query(LeituraSensor).filter(
        LeituraSensor.organization_id == user.organization_id,
        LeituraSensor.equipamento_id == equipamento_id,
        LeituraSensor.timestamp >= inicio,
    )
    if parametro:
        q = q.filter(LeituraSensor.parametro_nome == parametro)
    rows = q.order_by(LeituraSensor.timestamp).limit(500).all()
    return [{"id": str(r.id), "parametro_nome": r.parametro_nome, "valor": r.valor,
             "unidade": r.unidade, "fonte": r.fonte,
             "timestamp": r.timestamp.isoformat()} for r in rows]

@router.get("/preditivo/alertas")
async def listar_alertas(
    severidade: Optional[str] = None,
    status: Optional[str] = None,
    equipamento_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    q = db.query(AlertaPreditivo).filter(AlertaPreditivo.organization_id == user.organization_id)
    if severidade:
        q = q.filter(AlertaPreditivo.severidade == severidade.upper())
    if status:
        q = q.filter(AlertaPreditivo.status == status.upper())
    else:
        q = q.filter(AlertaPreditivo.status == "ABERTO")
    if equipamento_id:
        q = q.filter(AlertaPreditivo.equipamento_id == equipamento_id)
    alertas = q.order_by(AlertaPreditivo.criado_em.desc()).limit(100).all()
    equips = {str(e.id): e.nome for e in db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id).all()}
    return [{"id": str(a.id), "equipamento_id": str(a.equipamento_id),
             "equipamento_nome": equips.get(str(a.equipamento_id), ""),
             "parametro_nome": a.parametro_nome, "severidade": a.severidade,
             "valor_atual": a.valor_atual, "threshold_violado": a.threshold_violado,
             "tendencia": a.tendencia, "rul_estimado_dias": a.rul_estimado_dias,
             "descricao": a.descricao, "status": a.status,
             "criado_em": a.criado_em.isoformat()} for a in alertas]

@router.post("/preditivo/alertas/{alerta_id}/gerar-os")
async def gerar_os_alerta(
    alerta_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alerta = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.id == alerta_id,
        AlertaPreditivo.organization_id == user.organization_id,
    ).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    if alerta.status != "ABERTO":
        raise HTTPException(status_code=400, detail="Alerta já tratado")
    num = get_next_os_number(db, user.organization_id)
    os_new = OrdemServico(
        numero=num,
        organization_id=user.organization_id,
        equipamento_id=alerta.equipamento_id,
        tipo=TipoOS.PREDITIVA,
        prioridade=PrioridadeOS.CRITICA if alerta.severidade == "CRITICO" else PrioridadeOS.ALTA,
        status=StatusOS.ABERTA,
        descricao=alerta.descricao,
        falha_tipo="preditivo",
        solicitante_id=user.id,
    )
    db.add(os_new)
    alerta.status = "OS_GERADA"
    alerta.os_gerada_id = os_new.id
    db.commit()
    return {"os_numero": num, "mensagem": f"OS #{num} criada a partir do alerta"}

@router.post("/preditivo/alertas/{alerta_id}/ignorar")
async def ignorar_alerta(
    alerta_id: str, data: AlertaIgnorar,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(data.motivo.strip()) < 10:
        raise HTTPException(status_code=400, detail="Motivo deve ter pelo menos 10 caracteres")
    alerta = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.id == alerta_id,
        AlertaPreditivo.organization_id == user.organization_id,
    ).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    alerta.status = "IGNORADO"
    alerta.ignorado_por = user.id
    alerta.motivo_ignorado = data.motivo
    alerta.resolvido_em = datetime.now(timezone.utc)
    db.commit()
    return {"mensagem": "Alerta ignorado"}

@router.get("/preditivo/dashboard")
async def dashboard_preditivo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")

    equips = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id,
        Equipamento.monitoramento_ativo == True,
    ).all()
    total_mon = len(equips)
    normal = sum(1 for e in equips if getattr(e, "status_saude", "NORMAL") == "NORMAL")
    atencao = sum(1 for e in equips if getattr(e, "status_saude", "NORMAL") == "ATENCAO")
    critico = sum(1 for e in equips if getattr(e, "status_saude", "NORMAL") == "CRITICO")

    alertas_abertos = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.organization_id == user.organization_id,
        AlertaPreditivo.status == "ABERTO",
    ).all()
    alertas_criticos = [a for a in alertas_abertos if a.severidade == "CRITICO"]

    rul_vals = [e.rul_estimado_dias for e in equips if e.rul_estimado_dias is not None]
    media_rul = round(sum(rul_vals) / len(rul_vals), 1) if rul_vals else None

    menor_rul_equip = None
    if equips:
        candidatos = [(e, e.rul_estimado_dias) for e in equips if e.rul_estimado_dias is not None]
        if candidatos:
            e_min, rul_min = min(candidatos, key=lambda x: x[1])
            menor_rul_equip = {"nome": e_min.nome, "rul_dias": rul_min}

    # Histórico 30d de saúde (simplificado — conta alertas por dia)
    inicio_30d = datetime.now(timezone.utc) - timedelta(days=30)
    alertas_30d = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.organization_id == user.organization_id,
        AlertaPreditivo.criado_em >= inicio_30d,
    ).all()
    hist = {}
    for a in alertas_30d:
        d = a.criado_em.strftime("%Y-%m-%d")
        hist.setdefault(d, {"data": d, "atencao": 0, "critico": 0})
        hist[d][a.severidade.lower()] += 1

    top_risco = sorted(
        [{"equipamento_id": str(e.id), "nome": e.nome,
          "rul_dias": e.rul_estimado_dias,
          "status_saude": getattr(e, "status_saude", "NORMAL"),
          "custo_hora_parada": e.valor_hora}
         for e in equips],
        key=lambda x: (x["rul_dias"] or 9999),
    )[:5]

    return {
        "total_equipamentos_monitorados": total_mon,
        "equipamentos_normal": normal,
        "equipamentos_atencao": atencao,
        "equipamentos_critico": critico,
        "alertas_abertos": len(alertas_abertos),
        "alertas_criticos_abertos": len(alertas_criticos),
        "media_rul_dias": media_rul,
        "equipamento_menor_rul": menor_rul_equip,
        "historico_saude_30d": sorted(hist.values(), key=lambda x: x["data"]),
        "top_risco": top_risco,
    }

@router.get("/preditivo/saude-equipamentos")
async def saude_equipamentos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    equips = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id,
        Equipamento.ativo == True,
    ).all()
    alertas_abertos = {
        str(a.equipamento_id): a for a in db.query(AlertaPreditivo).filter(
            AlertaPreditivo.organization_id == user.organization_id,
            AlertaPreditivo.status == "ABERTO",
        ).all()
    }
    return [{"id": str(e.id), "nome": e.nome, "codigo": e.codigo,
             "localizacao": e.localizacao,
             "monitoramento_ativo": getattr(e, "monitoramento_ativo", False),
             "status_saude": getattr(e, "status_saude", "NORMAL"),
             "rul_estimado_dias": getattr(e, "rul_estimado_dias", None),
             "mttr_horas": getattr(e, "mttr_horas", None),
             "mtbf_horas": getattr(e, "mtbf_horas", None),
             "disponibilidade_percent": getattr(e, "disponibilidade_percent", None),
             "alerta_ativo": str(e.id) in alertas_abertos,
             "alerta_severidade": alertas_abertos[str(e.id)].severidade if str(e.id) in alertas_abertos else None,
             "valor_hora": e.valor_hora} for e in equips]


# ========== DASHBOARD AVANÇADO ==========
