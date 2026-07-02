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

router = APIRouter(tags=["Seed"])


@router.post("/seed-demo")
async def seed_demo_data(reset: bool = False, db: Session = Depends(get_db)):
    """Cria dados de demonstração completos com usuários por setor"""
    ORG_NOME = "Indústria AURIX Demo Ltda."
    ORG_NOME_OLD = "Empresa Demo"

    demo_org = (
        db.query(Organization).filter(Organization.nome == ORG_NOME).first()
        or db.query(Organization).filter(Organization.nome == ORG_NOME_OLD).first()
    )
    if demo_org and not reset:
        return {
            "message": "Dados de demonstração já existem. Use ?reset=true para recriar.",
            "email": "admin@demo.aurix", "senha": "admin123"
        }

    import random as _random
    from sqlalchemy import text as sa_text

    # ── Reset: deletar org existente em ordem de dependência ─────────────────
    if demo_org and reset:
        oid = str(demo_org.id)
        for table, col in [
            ("auditoria_logs",               "organization_id"),
            ("notificacoes",                 "org_id"),
            ("custos_os",                    "organization_id"),
            ("alertas_preditivos",           "organization_id"),
            ("leituras_sensor",              "organization_id"),
            ("configuracoes_monitoramento",  "organization_id"),
            ("ordens_servico",               "organization_id"),
            ("planos_preventivos",           "organization_id"),
            ("equipamentos",                 "organization_id"),
            ("subgrupos",                    "organization_id"),
            ("grupos",                       "organization_id"),
            ("payment_transactions",         "organization_id"),
            ("users",                        "organization_id"),
        ]:
            db.execute(sa_text(f"DELETE FROM {table} WHERE {col} = :oid"), {"oid": oid})
        db.execute(sa_text("DELETE FROM organizations WHERE id = :oid"), {"oid": oid})
        db.commit()
        db.expire_all()

    rng = _random.Random(42)  # deterministic for reproducibility
    now = datetime.now(timezone.utc)

    # ── Organização ──────────────────────────────────────────────────────────
    org = Organization(
        nome=ORG_NOME,
        cnpj="12.345.678/0001-90",
        plano=PlanoSaaS.AVANCADO,
        limite_equipamentos=50,
        limite_usuarios=100,
        limite_os_mes=-1,
        plano_trial_expira_em=now + timedelta(days=365),
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    # ── Grupos e Subgrupos ────────────────────────────────────────────────────
    G = {}  # nome → Grupo
    S = {}  # nome → Subgrupo
    estrutura = {
        "MECÂNICA":   ["Manutenção Preventiva", "Manutenção Corretiva", "Hidráulica", "Pneumática"],
        "ELÉTRICA":   ["Alta Tensão", "Automação/CLP", "Instrumentação", "Motores"],
        "T.I.":       ["Infraestrutura", "Sistemas", "Conectividade", "Segurança"],
        "UTILIDADES": ["Caldeiraria", "HVAC", "Compressores", "Utilidades Gerais"],
    }
    for grp_nome, subgrps in estrutura.items():
        grp = Grupo(organization_id=org_id, nome=grp_nome, descricao=f"Setor {grp_nome}")
        db.add(grp); db.flush(); G[grp_nome] = grp
        for sg in subgrps:
            s = Subgrupo(organization_id=org_id, grupo_id=grp.id, nome=sg)
            db.add(s); db.flush(); S[sg] = s
    db.commit()

    # ── Usuários (12 — todos os setores) ─────────────────────────────────────
    def _u(email, nome, role, setor=None, is_lider=False, senha="Aurix@2025"):
        return User(email=email, password_hash=hash_password(senha), nome=nome,
                    role=role, organization_id=org_id, setor=setor, is_lider=is_lider)

    u_admin     = _u("admin@demo.aurix",          "Carlos Mendes",          UserRole.ADMIN,    senha="admin123")
    u_lmec      = _u("lider.mecanica@demo.aurix",  "Roberto Souza",          UserRole.LIDER,    "MECÂNICA", True)
    u_t1mec     = _u("joao.silva@demo.aurix",      "João Silva",             UserRole.TECNICO,  "MECÂNICA")
    u_t2mec     = _u("pedro.costa@demo.aurix",     "Pedro Costa",            UserRole.TECNICO,  "MECÂNICA")
    u_opmec     = _u("marcos.lima@demo.aurix",     "Marcos Lima",            UserRole.OPERADOR, "MECÂNICA")
    u_lele      = _u("lider.eletrica@demo.aurix",  "Fernanda Rocha",         UserRole.LIDER,    "ELÉTRICA", True)
    u_t1ele     = _u("ana.santos@demo.aurix",      "Ana Santos",             UserRole.TECNICO,  "ELÉTRICA")
    u_t2ele     = _u("carlos.ferreira@demo.aurix", "Carlos Ferreira",        UserRole.TECNICO,  "ELÉTRICA")
    u_opele     = _u("lucia.pereira@demo.aurix",   "Lúcia Pereira",          UserRole.OPERADOR, "ELÉTRICA")
    u_lti       = _u("lider.ti@demo.aurix",        "Rafael Oliveira",        UserRole.LIDER,    "T.I.", True)
    u_t1ti      = _u("rodrigo.alves@demo.aurix",   "Rodrigo Alves",          UserRole.TECNICO,  "T.I.")
    u_opti      = _u("julia.moura@demo.aurix",     "Júlia Moura",            UserRole.OPERADOR, "T.I.")

    all_users = [u_admin,u_lmec,u_t1mec,u_t2mec,u_opmec,u_lele,u_t1ele,u_t2ele,u_opele,u_lti,u_t1ti,u_opti]
    db.add_all(all_users); db.commit()
    for u in all_users: db.refresh(u)

    # ── Equipamentos (15) ─────────────────────────────────────────────────────
    eq_defs = [
        # MECÂNICA
        ("EQ-001","Prensa Hidráulica 200T",    "Setor A — Prensas",        "MECÂNICA",   650,5, G["MECÂNICA"],S["Hidráulica"],         True),
        ("EQ-002","Torno CNC MAZAK QT200",     "Setor B — Usinagem",       "MECÂNICA",   900,5, G["MECÂNICA"],S["Manutenção Preventiva"],True),
        ("EQ-003","Fresadora Vertical Romi",   "Setor B — Usinagem",       "MECÂNICA",   750,4, G["MECÂNICA"],S["Manutenção Corretiva"], False),
        ("EQ-004","Compressor Atlas Copco GA55","Sala de Compressores",     "MECÂNICA",   350,4, G["MECÂNICA"],S["Pneumática"],          True),
        ("EQ-005","Bomba Centrífuga KSB 200",  "Setor A — Utilidades",     "MECÂNICA",   280,3, G["MECÂNICA"],S["Hidráulica"],          False),
        # ELÉTRICA
        ("EQ-006","Quadro Elétrico Principal", "Subestação",               "ELÉTRICA",   500,5, G["ELÉTRICA"],S["Alta Tensão"],         True),
        ("EQ-007","Motor Trifásico WEG 75kW",  "Setor C — Movimentação",   "ELÉTRICA",   420,4, G["ELÉTRICA"],S["Motores"],             True),
        ("EQ-008","CLP Siemens S7-1500",       "Painel Automação PA-01",   "ELÉTRICA",   600,5, G["ELÉTRICA"],S["Automação/CLP"],       False),
        ("EQ-009","Drive Inversor ABB ACS880", "Painel Automação PA-02",   "ELÉTRICA",   450,4, G["ELÉTRICA"],S["Automação/CLP"],       False),
        ("EQ-010","Gerador CAT DE500GC",       "Casa de Força",            "ELÉTRICA",   800,5, G["ELÉTRICA"],S["Instrumentação"],      True),
        # T.I.
        ("EQ-011","Servidor Dell PowerEdge R750","Data Center — Rack 01",  "T.I.",       300,4, G["T.I."],    S["Infraestrutura"],      True),
        ("EQ-012","Switch Core Cisco Cat.9500","Data Center — Rack 02",    "T.I.",       200,3, G["T.I."],    S["Conectividade"],       False),
        ("EQ-013","UPS APC Smart-UPS 10kVA",  "Data Center — Rack 03",    "T.I.",       150,4, G["T.I."],    S["Infraestrutura"],      False),
        # UTILIDADES
        ("EQ-014","Caldeira Thermax 500kg/h",  "Casa de Caldeiras",        "UTILIDADES", 720,5, G["UTILIDADES"],S["Caldeiraria"],       True),
        ("EQ-015","Sistema HVAC Carrier 100TR","Cobertura Industrial",      "UTILIDADES", 320,3, G["UTILIDADES"],S["HVAC"],             False),
    ]
    E = {}
    for (cod,nome,loc,setor,vh,crit,grp,sgrp,mon) in eq_defs:
        eq = Equipamento(organization_id=org_id, codigo=cod, nome=nome, localizacao=loc,
                         valor_hora=float(vh), grupo_id=grp.id, subgrupo_id=sgrp.id, criticidade=crit)
        db.add(eq); db.flush(); E[cod] = eq
    db.commit()

    # Set unmapped columns via raw SQL
    for (cod,_,_,setor,_,_,_,_,mon) in eq_defs:
        db.execute(sa_text(
            "UPDATE equipamentos SET setor=:s, monitoramento_ativo=:m WHERE id=:id"
        ), {"s": setor, "m": mon, "id": str(E[cod].id)})
    db.commit()

    # ── Configurações de Monitoramento ────────────────────────────────────────
    mon_cfgs = [
        ("EQ-001","Temperatura do Óleo",     "°C",   70,  85,  7),
        ("EQ-001","Pressão Hidráulica",       "bar",  200, 230, 7),
        ("EQ-002","Temperatura do Fuso",      "°C",   65,  80, 14),
        ("EQ-002","Vibração do Fuso",         "mm/s", 3.5, 6.0,14),
        ("EQ-004","Temperatura de Descarga",  "°C",   75,  90,  7),
        ("EQ-004","Nível de Óleo",            "%",    30,  15,  3),
        ("EQ-006","Temperatura do Barramento","°C",   55,  70,  7),
        ("EQ-007","Temperatura da Bobina",    "°C",   80, 100,  7),
        ("EQ-007","Vibração",                 "mm/s", 4.0, 7.0,14),
        ("EQ-010","Temperatura do Óleo",      "°C",   80,  95,  7),
        ("EQ-011","Temperatura da CPU",       "°C",   70,  85,  3),
        ("EQ-011","Uso de Disco",             "%",    80,  92,  7),
        ("EQ-014","Pressão do Vapor",         "bar",  8.0,10.0, 3),
        ("EQ-014","Temperatura da Câmara",    "°C",  180, 200,  3),
    ]
    CM = {}
    for (cod,param,un,at,cr,jd) in mon_cfgs:
        cm = ConfiguracaoMonitoramento(organization_id=org_id, equipamento_id=E[cod].id,
                                       parametro_nome=param, unidade=un,
                                       threshold_atencao=at, threshold_critico=cr,
                                       tendencia_janela_dias=jd, ativo=True)
        db.add(cm); db.flush(); CM[(cod,param)] = cm
    db.commit()

    # ── Leituras de sensor (30 dias, tendências variadas) ─────────────────────
    # (eq_code, param): (tipo, base_valor, slope_por_dia)
    # tipo "crescente"=subindo, "normal"=estável com ruído, "critico"=já alto
    tendencias = {
        ("EQ-001","Temperatura do Óleo"):      ("crescente", 52.0,  1.1),
        ("EQ-001","Pressão Hidráulica"):        ("normal",   172.0,  0.0),
        ("EQ-002","Temperatura do Fuso"):       ("normal",    45.0,  0.0),
        ("EQ-002","Vibração do Fuso"):          ("crescente",  1.8,  0.08),
        ("EQ-004","Temperatura de Descarga"):   ("normal",    61.0,  0.0),
        ("EQ-004","Nível de Óleo"):             ("crescente", 86.0, -1.9),
        ("EQ-006","Temperatura do Barramento"): ("normal",    42.0,  0.0),
        ("EQ-007","Temperatura da Bobina"):     ("critico",   83.0,  1.4),
        ("EQ-007","Vibração"):                  ("crescente",  3.0,  0.13),
        ("EQ-010","Temperatura do Óleo"):       ("normal",    65.0,  0.0),
        ("EQ-011","Temperatura da CPU"):        ("crescente", 61.0,  0.6),
        ("EQ-011","Uso de Disco"):              ("crescente", 73.0,  0.45),
        ("EQ-014","Pressão do Vapor"):          ("normal",     6.6,  0.0),
        ("EQ-014","Temperatura da Câmara"):     ("critico",  183.0,  2.0),
    }
    unidade_lookup = {(cod,param): un for (cod,param,un,_,_,_) in mon_cfgs}
    for (cod,param), (tipo,base,slope) in tendencias.items():
        eq = E[cod]
        un = unidade_lookup.get((cod,param), "")
        for day in range(30, 0, -1):
            idx = 30 - day
            noise = rng.uniform(-0.8, 0.8)
            if tipo == "crescente":
                val = base + slope * idx + noise
            elif tipo == "critico":
                val = base + slope * (idx * 0.4) + noise
            else:
                val = base + noise * 1.5
            val = max(0.0, round(val, 2))
            db.add(LeituraSensor(
                organization_id=org_id, equipamento_id=eq.id,
                parametro_nome=param, valor=val, unidade=un,
                fonte="sensor_iot", timestamp=now - timedelta(days=day), processado=True,
            ))
    db.commit()

    # ── Alertas Preditivos ────────────────────────────────────────────────────
    alertas_defs = [
        ("EQ-007","Temperatura da Bobina","CRITICO", 91.5, 80, "CRESCENTE",12,"Temperatura da bobina do Motor WEG 75kW acima do limiar crítico. Risco de queima do isolamento.","ABERTO"),
        ("EQ-014","Temperatura da Câmara","CRITICO",196.0,180, "CRITICA",   5,"Temperatura da câmara da Caldeira Thermax crítica. Ação imediata necessária.","ABERTO"),
        ("EQ-001","Temperatura do Óleo",  "ATENCAO", 68.5, 70, "CRESCENTE",28,"Temperatura do óleo hidráulico da Prensa 200T em tendência crescente.","ABERTO"),
        ("EQ-002","Vibração do Fuso",     "ATENCAO",  3.3, 3.5,"CRESCENTE",18,"Vibração do fuso do Torno CNC aumentando. Possível desgaste dos mancais.","ABERTO"),
        ("EQ-011","Uso de Disco",         "ATENCAO", 86.2, 80, "CRESCENTE",22,"Uso de disco do Servidor Dell acima de 80%. Planejar expansão.","ABERTO"),
        ("EQ-004","Nível de Óleo",        "ATENCAO", 31.0, 30, "CRESCENTE", 3,"Nível de óleo do Compressor próximo ao mínimo. Agendar reabastecimento.","OS_GERADA"),
        ("EQ-007","Vibração",             "ATENCAO",  3.9, 4.0,"CRESCENTE",15,"Vibração do Motor WEG próxima ao limiar de atenção.","RESOLVIDO"),
    ]
    for (cod,param,sev,val,thresh,tend,rul,desc,status_a) in alertas_defs:
        db.add(AlertaPreditivo(
            organization_id=org_id, equipamento_id=E[cod].id,
            parametro_nome=param, severidade=sev, valor_atual=val,
            threshold_violado=thresh, tendencia=tend, rul_estimado_dias=rul,
            descricao=desc, status=status_a,
            criado_em=now - timedelta(days=rng.randint(1,5)),
            resolvido_em=now - timedelta(hours=6) if status_a=="RESOLVIDO" else None,
        ))
    db.commit()

    # Atualizar status_saude via SQL (colunas não mapeadas no ORM)
    saude_map = {
        "EQ-001":("ATENCAO",28),"EQ-002":("ATENCAO",18),"EQ-004":("ATENCAO",3),
        "EQ-006":("NORMAL",None),"EQ-007":("CRITICO",12),"EQ-010":("NORMAL",None),
        "EQ-011":("ATENCAO",22),"EQ-014":("CRITICO",5),
    }
    for cod,(saude,rul) in saude_map.items():
        db.execute(sa_text(
            "UPDATE equipamentos SET status_saude=:s, rul_estimado_dias=:r WHERE id=:id"
        ), {"s": saude, "r": rul, "id": str(E[cod].id)})
    db.commit()

    # ── Ordens de Serviço (50 OS) ─────────────────────────────────────────────
    tipos_falha   = ["Mecânica","Elétrica","Hidráulica","Pneumática","Software","Instrumentação","Estrutural"]
    modos_falha   = ["Desgaste","Quebra","Vazamento","Curto-circuito","Travamento","Superaquecimento","Vibração excessiva"]
    causas_falha  = ["Uso inadequado","Falta de lubrificação","Fim de vida útil","Sobrecarga","Defeito de fábrica","Contaminação","Operação fora de faixa"]
    descricoes_cor = [
        "Prensa sem pressão — verificar bomba hidráulica e válvulas",
        "Torno parado por alarme de temperatura do fuso",
        "Fresadora com vibração anormal no eixo Z — rolamento suspeito",
        "Compressor não atinge pressão nominal — verificar válvulas",
        "Bomba com ruído anormal e perda de vazão na sucção",
        "Quadro elétrico com disjuntor disparando repetidamente",
        "Motor WEG com superaquecimento após 2h de operação contínua",
        "CLP em fault — falha na comunicação Profinet com periféricos",
        "Drive ABB com sobrecorrente — equipamento parado",
        "Gerador não participa do sincronismo com a rede",
        "Servidor com temperatura crítica da CPU — risco de desligamento",
        "Switch core com perda de uplink — link redundante ativo",
        "UPS em bypass — bateria descarregada, sem proteção",
        "Caldeira sem ignição — falha detectada na válvula de gás",
        "HVAC com mau funcionamento do compressor de refrigeração",
        "Prensa hidráulica com vazamento de óleo no cilindro principal",
        "Esteira transportadora com corrente solta no trecho 3",
        "Painel elétrico com arco-voltaico detectado no barramento",
    ]
    descricoes_prev = [
        "Troca de fluido hidráulico e substituição de filtros — preventiva mensal",
        "Inspeção de rolamentos, ajuste de correias e tensão de correntes",
        "Limpeza geral, lubrificação de guias e reaperto de fixações",
        "Inspeção elétrica completa, aperto de conexões e medição de isolamento",
        "Calibração de sensores de pressão, temperatura e nível",
        "Limpeza de condensadores, evaporadores e drenos de HVAC",
        "Inspeção de vedações, mangueiras e conexões hidráulicas",
        "Leitura de parâmetros do inversor de frequência e backup de configurações",
    ]
    solucoes = [
        "Peça substituída e equipamento testado em carga.",
        "Ajuste de parâmetros e recalibração realizada com sucesso.",
        "Limpeza profunda e lubrificação executadas conforme procedimento.",
        "Regulagem concluída e equipamento liberado para produção.",
        "Firmware atualizado e comunicação restabelecida.",
        "Componente danificado substituído por novo do estoque.",
        "Vazamento eliminado com troca do retentores e vedações.",
        "Conexões refeitas e disjuntor substituído — funcionamento normal.",
    ]

    # Setor → (equips, tecnicos, operador, lider)
    setor_map = {
        "MECÂNICA":   ([E["EQ-001"],E["EQ-002"],E["EQ-003"],E["EQ-004"],E["EQ-005"]], [u_t1mec,u_t2mec], u_opmec, u_lmec),
        "ELÉTRICA":   ([E["EQ-006"],E["EQ-007"],E["EQ-008"],E["EQ-009"],E["EQ-010"]], [u_t1ele,u_t2ele], u_opele, u_lele),
        "T.I.":       ([E["EQ-011"],E["EQ-012"],E["EQ-013"]],                          [u_t1ti],          u_opti,  u_lti),
        "UTILIDADES": ([E["EQ-014"],E["EQ-015"]],                                      [u_t1mec,u_t1ele], u_opmec, u_lmec),
    }
    setores_ciclo = list(setor_map.items())
    all_os = []

    for i in range(50):
        setor_nome, (s_equips, s_tecs, s_op, s_lider) = setores_ciclo[i % len(setores_ciclo)]
        eq = rng.choice(s_equips)
        tipo = rng.choices([TipoOS.CORRETIVA,TipoOS.PREVENTIVA,TipoOS.PREDITIVA], weights=[60,30,10])[0]
        prioridade = rng.choices(list(PrioridadeOS), weights=[15,40,30,15])[0]
        status = rng.choices(
            [StatusOS.ABERTA,StatusOS.EM_ATENDIMENTO,StatusOS.AGUARDANDO_REVISAO,StatusOS.REVISADA,StatusOS.FECHADA],
            weights=[20,15,15,10,40]
        )[0]
        created_at = now - timedelta(days=rng.randint(0, 90))
        if tipo == TipoOS.CORRETIVA:
            desc = rng.choice(descricoes_cor)
            ft = rng.choice(tipos_falha); fm = rng.choice(modos_falha); fc = rng.choice(causas_falha)
        elif tipo == TipoOS.PREVENTIVA:
            desc = rng.choice(descricoes_prev); ft = fm = fc = None
        else:
            desc = f"OS gerada por alerta preditivo — {eq.nome}"; ft = fm = fc = None
        tec = rng.choice(s_tecs)
        os_obj = OrdemServico(
            numero=i+1, organization_id=org_id,
            equipamento_id=eq.id, grupo_id=eq.grupo_id, subgrupo_id=eq.subgrupo_id,
            tipo=tipo, prioridade=prioridade, status=status, descricao=desc,
            solicitante_id=s_op.id, falha_tipo=ft, falha_modo=fm, falha_causa=fc,
            created_at=created_at,
        )
        if status in (StatusOS.EM_ATENDIMENTO,StatusOS.AGUARDANDO_REVISAO,StatusOS.REVISADA,StatusOS.FECHADA):
            delay = rng.randint(5, 180)
            os_obj.tecnico_id = tec.id
            os_obj.inicio_atendimento = created_at + timedelta(minutes=delay)
            os_obj.tempo_resposta = delay
            os_obj.dentro_sla = calculate_sla(prioridade, delay)
        if status in (StatusOS.AGUARDANDO_REVISAO,StatusOS.REVISADA,StatusOS.FECHADA):
            repair = rng.randint(30, 720)
            os_obj.fim_atendimento = os_obj.inicio_atendimento + timedelta(minutes=repair)
            os_obj.tempo_reparo = repair
            os_obj.tempo_total = (os_obj.tempo_resposta or 0) + repair
            os_obj.solucao = rng.choice(solucoes)
        if status in (StatusOS.REVISADA, StatusOS.FECHADA):
            os_obj.revisado_at = os_obj.fim_atendimento + timedelta(hours=rng.randint(1,8))
            os_obj.revisor_id = s_lider.id
        if status == StatusOS.FECHADA:
            os_obj.fechado_at = os_obj.revisado_at
        db.add(os_obj); all_os.append(os_obj)
    db.commit()
    for o in all_os: db.refresh(o)

    # ── Custos ────────────────────────────────────────────────────────────────
    descs_custo = {
        TipoCusto.CONSUMO:      ["Óleo lubrificante 20L","Graxa industrial 5kg","Fluido hidráulico 10L","Filtro de ar","Mangueira hidráulica"],
        TipoCusto.SUBSTITUICAO: ["Rolamento SKF 6205","Correia V-Belt A-65","Vedação de eixo","Capacitor 450V 40µF","Fusível NH3 200A","Contator Schneider 40A"],
        TipoCusto.MAO_OBRA:     ["Mão de obra técnica","Hora extra técnico","Serviço terceirizado Siemens","Consultor ABB"],
    }
    for os_obj in all_os:
        if os_obj.status in (StatusOS.FECHADA, StatusOS.REVISADA):
            for _ in range(rng.choices([0,1,2,3], weights=[15,45,30,10])[0]):
                tc = rng.choice(list(TipoCusto))
                db.add(CustoOS(
                    ordem_servico_id=os_obj.id, tipo=tc,
                    descricao=rng.choice(descs_custo[tc]),
                    valor=round(rng.uniform(30,1200),2),
                    quantidade=rng.randint(1,4),
                    organization_id=org_id,
                ))
    db.commit()

    # ── Planos Preventivos (12) ───────────────────────────────────────────────
    planos_defs = [
        ("EQ-001","Troca de Óleo Hidráulico",          30, 45, 5),
        ("EQ-002","Inspeção de Mancais do Fuso",        14, 10, 4),
        ("EQ-003","Lubrificação e Ajuste Geral",        30,  8,22),
        ("EQ-004","Troca de Filtro do Compressor",       7, 12,-5),   # vencido
        ("EQ-005","Inspeção de Vedações da Bomba",      60, 50,10),
        ("EQ-006","Termografia e Aperto Elétrico",      30, 20,10),
        ("EQ-007","Inspeção do Motor e Rolamentos",     14, 18,-4),   # vencido
        ("EQ-008","Backup e Atualização do CLP",        90, 30,60),
        ("EQ-010","Troca de Óleo do Gerador",          180, 90,90),
        ("EQ-011","Limpeza e Verificação do Servidor",  30, 25, 5),
        ("EQ-014","Inspeção de Segurança da Caldeira",  30, 35,-5),   # vencido
        ("EQ-015","Limpeza de Condensadores HVAC",      60, 40,20),
    ]
    for (cod,nome,freq,dias_atras,prox_delta) in planos_defs:
        db.add(PlanoPreventivo(
            organization_id=org_id, equipamento_id=E[cod].id,
            nome=nome, descricao=f"Manutenção preventiva — {nome.lower()}",
            frequencia_dias=freq,
            ultima_execucao=now - timedelta(days=dias_atras),
            proxima_execucao=now + timedelta(days=prox_delta),
        ))
    db.commit()

    # ── Notificações ─────────────────────────────────────────────────────────
    notifs = [
        (u_lele,  "alerta_critico", "Alerta Crítico", "Motor WEG 75kW com temperatura acima do limiar crítico. Verifique imediatamente.",  1),
        (u_admin, "alerta_critico", "Alerta Crítico", "Caldeira Thermax com temperatura próxima ao limite de segurança. Ação necessária.", 2),
        (u_lmec,  "preventivo_vencido","Preventivo Vencido","Troca de Filtro do Compressor (EQ-004) está vencida há 5 dias.",               3),
        (u_lele,  "preventivo_vencido","Preventivo Vencido","Inspeção do Motor WEG (EQ-007) está vencida há 4 dias.",                       4),
        (u_lmec,  "aprovacao_pendente","OS Aguardando Revisão","OS #3 — Compressor Atlas Copco aguarda sua revisão.",                       8),
        (u_lti,   "alerta_critico","Espaço em Disco","Servidor Dell PowerEdge com uso de disco acima de 86%. Planejar expansão.",           12),
    ]
    for (dest, tipo_n, titulo_n, msg, h) in notifs:
        db.add(Notificacao(
            org_id=org_id, destinatario_id=dest.id,
            tipo=tipo_n, titulo=titulo_n, mensagem=msg,
            lida=False, criada_em=now - timedelta(hours=h),
        ))
    db.commit()

    return {
        "message": "Dados de demonstração criados com sucesso.",
        "organizacao": ORG_NOME,
        "plano": "AVANCADO",
        "credenciais": {
            "admin":             {"email": "admin@demo.aurix",          "senha": "admin123",   "role": "admin",    "setor": None},
            "lider_mecanica":    {"email": "lider.mecanica@demo.aurix", "senha": "Aurix@2025", "role": "lider",    "setor": "MECÂNICA"},
            "tecnico_mec_1":     {"email": "joao.silva@demo.aurix",     "senha": "Aurix@2025", "role": "tecnico",  "setor": "MECÂNICA"},
            "tecnico_mec_2":     {"email": "pedro.costa@demo.aurix",    "senha": "Aurix@2025", "role": "tecnico",  "setor": "MECÂNICA"},
            "operador_mec":      {"email": "marcos.lima@demo.aurix",    "senha": "Aurix@2025", "role": "operador", "setor": "MECÂNICA"},
            "lider_eletrica":    {"email": "lider.eletrica@demo.aurix", "senha": "Aurix@2025", "role": "lider",    "setor": "ELÉTRICA"},
            "tecnico_ele_1":     {"email": "ana.santos@demo.aurix",     "senha": "Aurix@2025", "role": "tecnico",  "setor": "ELÉTRICA"},
            "tecnico_ele_2":     {"email": "carlos.ferreira@demo.aurix","senha": "Aurix@2025", "role": "tecnico",  "setor": "ELÉTRICA"},
            "operador_ele":      {"email": "lucia.pereira@demo.aurix",  "senha": "Aurix@2025", "role": "operador", "setor": "ELÉTRICA"},
            "lider_ti":          {"email": "lider.ti@demo.aurix",       "senha": "Aurix@2025", "role": "lider",    "setor": "T.I."},
            "tecnico_ti":        {"email": "rodrigo.alves@demo.aurix",  "senha": "Aurix@2025", "role": "tecnico",  "setor": "T.I."},
            "operador_ti":       {"email": "julia.moura@demo.aurix",    "senha": "Aurix@2025", "role": "operador", "setor": "T.I."},
        },
        "estatisticas": {
            "usuarios": 12, "equipamentos": 15, "ordens_servico": 50,
            "planos_preventivos": 12, "configs_monitoramento": len(mon_cfgs),
            "leituras_sensor": len(tendencias) * 30, "alertas_preditivos": len(alertas_defs),
        },
    }
