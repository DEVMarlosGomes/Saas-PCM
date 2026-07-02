"""
Application configuration and constants.
Centralizes all SaaS plan limits, JWT settings, and feature flags for AURIX.
"""
import os
import secrets
import enum


# ========== JWT Configuration ==========
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7


# ========== ENUMS ==========
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    LIDER = "lider"
    TECNICO = "tecnico"
    OPERADOR = "operador"


class TipoOS(str, enum.Enum):
    CORRETIVA = "corretiva"
    PREVENTIVA = "preventiva"
    PREDITIVA = "preditiva"


class PrioridadeOS(str, enum.Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class StatusOS(str, enum.Enum):
    ABERTA = "aberta"
    EM_ATENDIMENTO = "em_atendimento"
    AGUARDANDO_REVISAO = "aguardando_revisao"
    REVISADA = "revisada"
    FECHADA = "fechada"


class TipoCusto(str, enum.Enum):
    CONSUMO = "consumo"
    SUBSTITUICAO = "substituicao"
    MAO_OBRA = "mao_obra"


class PlanoSaaS(str, enum.Enum):
    DEMO = "demo"
    ESSENCIAL = "essencial"
    PROFISSIONAL = "profissional"
    AVANCADO = "avancado"
    ENTERPRISE = "enterprise"


# ========== Plan Limits & Feature Flags ==========
PLAN_LIMITS = {
    PlanoSaaS.DEMO: {
        "label": "Demo",
        "subtitulo": "Experimente a Aurix",
        "preco_mensal": 0.0,
        "stripe_price_id": None,
        "cta_tipo": "trial",
        "cta_texto": "Experimentar Grátis",
        "destaque": False,
        "duracao_dias": 10,
        "max_equipamentos": 5,
        "max_users": 3,
        "max_os_mes": 10,
        "price": 0.0,
        "relatorios": False,
        "grupos_subgrupos": False,
        "aprovacao_setor": False,
        "modulo_preditivo": False,
        "planos_preventivos": False,
        "api_iot": False,
        "notificacoes_email": False,
        "exportacao_pdf": False,
        "sso": False,
        "suporte": "none",
        "dashboard_avancado": False,
        "kanban": False,
        "modulo_estoque": False,
        "modulo_evidencias": False,
        "features": [
            "Até 3 colaboradores",
            "Até 5 equipamentos",
            "10 dias de teste",
            "Sem análise de relatórios",
        ],
    },
    PlanoSaaS.ESSENCIAL: {
        "label": "Essencial",
        "subtitulo": "Comece com eficiência",
        "preco_mensal": 250.0,
        "stripe_price_id": "price_essencial_mensal",
        "cta_tipo": "stripe_checkout",
        "cta_texto": "Assinar Plano",
        "destaque": False,
        "max_equipamentos": 20,
        "max_users": 10,
        "max_os_mes": 100,
        "price": 250.0,
        "relatorios": True,
        "grupos_subgrupos": True,
        "aprovacao_setor": True,
        "modulo_preditivo": False,
        "planos_preventivos": False,
        "api_iot": False,
        "notificacoes_email": True,
        "exportacao_pdf": False,
        "sso": False,
        "suporte": "email",
        "dashboard_avancado": False,
        "kanban": False,
        "modulo_estoque": False,
        "modulo_evidencias": False,
        "features": [
            "Até 10 colaboradores",
            "Até 20 equipamentos",
            "Análise de indicadores",
            "Suporte por e-mail",
        ],
    },
    PlanoSaaS.PROFISSIONAL: {
        "label": "Profissional",
        "subtitulo": "Escala com inteligência",
        "preco_mensal": 490.0,
        "stripe_price_id": "price_profissional_mensal",
        "cta_tipo": "stripe_checkout",
        "cta_texto": "Assinar Plano",
        "destaque": True,
        "max_equipamentos": 35,
        "max_users": 45,
        "max_os_mes": -1,
        "price": 490.0,
        "relatorios": True,
        "grupos_subgrupos": True,
        "aprovacao_setor": True,
        "modulo_preditivo": True,
        "max_equipamentos_preditivo": 10,
        "planos_preventivos": True,
        "api_iot": True,
        "notificacoes_email": True,
        "exportacao_pdf": True,
        "sso": False,
        "suporte": "prioritario",
        "dashboard_avancado": True,
        "kanban": True,
        "setores_independentes": True,
        "relatorios_custo": True,
        "modulo_estoque": True,
        "modulo_evidencias": True,
        "features": [
            "Até 45 colaboradores",
            "Até 35 equipamentos",
            "Setores independentes",
            "Dashboards e Kanban",
            "Almoxarifado e estoque",
            "Suporte prioritário",
        ],
    },
    PlanoSaaS.AVANCADO: {
        "label": "Avançado",
        "subtitulo": "Gestão que gera resultado",
        "preco_mensal": 790.0,
        "stripe_price_id": "price_avancado_mensal",
        "cta_tipo": "stripe_checkout",
        "cta_texto": "Assinar Plano",
        "destaque": False,
        "max_equipamentos": 50,
        "max_users": 100,
        "max_os_mes": -1,
        "price": 790.0,
        "relatorios": True,
        "relatorios_personalizados": True,
        "grupos_subgrupos": True,
        "aprovacao_setor": True,
        "modulo_preditivo": True,
        "max_equipamentos_preditivo": 30,
        "planos_preventivos": True,
        "api_iot": True,
        "notificacoes_email": True,
        "notificacoes_whatsapp": True,
        "exportacao_pdf": True,
        "integracoes_basicas": True,
        "sso": False,
        "suporte": "prioritario",
        "dashboard_avancado": True,
        "kanban": True,
        "setores_independentes": True,
        "relatorios_custo": True,
        "analise_pareto": True,
        "modulo_estoque": True,
        "modulo_evidencias": True,
        "features": [
            "Até 100 colaboradores",
            "Até 50 equipamentos",
            "Dashboards avançados",
            "Almoxarifado completo",
            "Relatórios personalizados",
            "Integrações básicas",
            "Suporte prioritário",
        ],
    },
    PlanoSaaS.ENTERPRISE: {
        "label": "Enterprise",
        "subtitulo": "Solução sem limites",
        "preco_mensal": 1290.0,
        "stripe_price_id": None,
        "cta_tipo": "contato",
        "cta_texto": "Fale Conosco",
        "destaque": False,
        "max_equipamentos": -1,
        "max_users": -1,
        "max_os_mes": -1,
        "price": 1290.0,
        "max_equipamentos_preditivo": -1,
        "relatorios": True,
        "relatorios_personalizados": True,
        "grupos_subgrupos": True,
        "aprovacao_setor": True,
        "modulo_preditivo": True,
        "planos_preventivos": True,
        "api_iot": True,
        "notificacoes_email": True,
        "notificacoes_whatsapp": True,
        "exportacao_pdf": True,
        "integracoes_avancadas": True,
        "sso": True,
        "suporte": "dedicado",
        "dashboard_avancado": True,
        "kanban": True,
        "setores_independentes": True,
        "relatorios_custo": True,
        "analise_pareto": True,
        "onboarding_personalizado": True,
        "sla_customizado": True,
        "modulo_estoque": True,
        "modulo_evidencias": True,
        "features": [
            "Colaboradores ilimitados",
            "Equipamentos ilimitados",
            "Todas funcionalidades",
            "Integrações avançadas",
            "Suporte dedicado",
            "SLA personalizado",
        ],
    },
}


def check_feature(plano: PlanoSaaS, feature: str) -> bool:
    """Verifica se o plano tem acesso a uma feature."""
    info = PLAN_LIMITS.get(plano, {})
    return bool(info.get(feature, False))


def check_limit(plano: PlanoSaaS, recurso: str, contagem_atual: int) -> tuple:
    """
    Verifica se a org está dentro dos limites do plano.
    Retorna (ok: bool, mensagem: str).
    """
    info = PLAN_LIMITS.get(plano, PLAN_LIMITS[PlanoSaaS.DEMO])
    limite = info.get(f"max_{recurso}", 0)
    if limite == -1:
        return True, ""
    if contagem_atual >= limite:
        label = info.get("label", plano.value)
        return False, (
            f"Limite de {recurso} atingido ({contagem_atual}/{limite}) "
            f"no plano {label}. Faça upgrade para continuar."
        )
    return True, ""


def sugerir_upgrade(plano_atual: PlanoSaaS, feature_necessaria: str) -> str:
    """Retorna o menor plano que tem a feature necessária."""
    ordem = [
        PlanoSaaS.DEMO,
        PlanoSaaS.ESSENCIAL,
        PlanoSaaS.PROFISSIONAL,
        PlanoSaaS.AVANCADO,
        PlanoSaaS.ENTERPRISE,
    ]
    idx = ordem.index(plano_atual) if plano_atual in ordem else 0
    for p in ordem[idx + 1 :]:
        if PLAN_LIMITS[p].get(feature_necessaria):
            return p.value
    return PlanoSaaS.ENTERPRISE.value


# SLA Configuration (in minutes by priority)
SLA_LIMITS = {
    PrioridadeOS.CRITICA: 30,
    PrioridadeOS.ALTA: 60,
    PrioridadeOS.MEDIA: 120,
    PrioridadeOS.BAIXA: 480,
}
