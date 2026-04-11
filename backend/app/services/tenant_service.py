"""
Tenant (Organization) service layer.
Handles plan limits, usage tracking, and tenant-scoped operations.
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models.models import Organization, User, Equipamento, OrdemServico, AuditoriaLog
from ..config import PLAN_LIMITS, PlanoSaaS


def get_org_usage(db: Session, org_id) -> dict:
    """Get current usage counts for an organization."""
    now = datetime.now(timezone.utc)
    first_day_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    equipamentos_count = db.query(Equipamento).filter(
        Equipamento.organization_id == org_id,
        Equipamento.ativo == True
    ).count()

    users_count = db.query(User).filter(
        User.organization_id == org_id,
        User.ativo == True
    ).count()

    os_mes_count = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.created_at >= first_day_month
    ).count()

    return {
        "equipamentos": equipamentos_count,
        "users": users_count,
        "os_mes": os_mes_count
    }


def check_plan_limit(db: Session, org: Organization, resource: str) -> tuple:
    """
    Check if organization has reached its plan limit for a resource.
    Returns (allowed: bool, message: str)
    """
    usage = get_org_usage(db, org.id)
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.FREE])

    limit_map = {
        "equipamentos": ("max_equipamentos", usage["equipamentos"]),
        "users": ("max_users", usage["users"]),
        "os": ("max_os_mes", usage["os_mes"]),
    }

    if resource not in limit_map:
        return True, ""

    limit_key, current = limit_map[resource]
    max_val = limits[limit_key]

    if current >= max_val:
        plan_label = limits["label"]
        return False, f"Limite do plano {plan_label} atingido: {current}/{max_val} {resource}. Faça upgrade para continuar."

    return True, ""


def create_audit_log(
    db: Session, org_id: str, user_id: str, entidade: str,
    entidade_id: str, acao: str, dados_anteriores: str = None,
    dados_novos: str = None
):
    """Create an audit log entry scoped to the organization."""
    log = AuditoriaLog(
        organization_id=org_id,
        user_id=user_id,
        entidade=entidade,
        entidade_id=entidade_id,
        acao=acao,
        dados_anteriores=dados_anteriores,
        dados_novos=dados_novos
    )
    db.add(log)
    db.commit()


def get_next_os_number(db: Session, org_id: str) -> int:
    """Get the next sequential OS number for an organization."""
    last_os = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id
    ).order_by(OrdemServico.numero.desc()).first()
    return (last_os.numero + 1) if last_os else 1
