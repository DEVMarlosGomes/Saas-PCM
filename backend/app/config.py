"""
Application configuration and constants.
Centralizes all SaaS plan limits, JWT settings, and feature flags.
"""
import os
import secrets
import enum


# ========== JWT Configuration ==========
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours for SaaS session
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
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# ========== Plan Limits Configuration ==========
PLAN_LIMITS = {
    PlanoSaaS.FREE: {
        "max_equipamentos": 10,
        "max_users": 5,
        "max_os_mes": 50,
        "price": 0.00,
        "label": "Free",
        "features": [
            "Até 10 equipamentos",
            "Até 5 usuários",
            "50 OS/mês",
            "Dashboard básico",
            "Suporte por email",
        ],
    },
    PlanoSaaS.PRO: {
        "max_equipamentos": 100,
        "max_users": 50,
        "max_os_mes": 500,
        "price": 99.00,
        "label": "Pro",
        "features": [
            "Até 100 equipamentos",
            "Até 50 usuários",
            "500 OS/mês",
            "Dashboard completo",
            "Planos preventivos",
            "Exportação de relatórios",
            "Suporte prioritário",
        ],
    },
    PlanoSaaS.ENTERPRISE: {
        "max_equipamentos": 9999,
        "max_users": 999,
        "max_os_mes": 9999,
        "price": 299.00,
        "label": "Enterprise",
        "features": [
            "Equipamentos ilimitados",
            "Usuários ilimitados",
            "OS ilimitadas",
            "Dashboard avançado com IA",
            "API de integração",
            "Relatórios customizados",
            "Suporte 24/7 dedicado",
            "SLA garantido",
        ],
    },
}

# SLA Configuration (in minutes by priority)
SLA_LIMITS = {
    PrioridadeOS.CRITICA: 30,
    PrioridadeOS.ALTA: 60,
    PrioridadeOS.MEDIA: 120,
    PrioridadeOS.BAIXA: 480,
}
