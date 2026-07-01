"""
Testes unitários de billing — Fase 4.3

Cobre: limites de plano, feature flags, check_plan_limit, check_plan_feature.
Não requer servidor ou banco de dados real.
"""
import os
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("JWT_SECRET", "test-secret-32-characters-for-test!!")

from app.models.core import PLAN_LIMITS, PlanoSaaS
from app.deps import check_plan_feature, check_plan_limit


# ── Estrutura de PLAN_LIMITS ───────────────────────────────────────────────────

REQUIRED_KEYS = {"max_equipamentos", "max_users", "max_os_mes", "label"}

@pytest.mark.parametrize("plano", list(PlanoSaaS))
def test_plan_limits_have_required_keys(plano):
    assert plano in PLAN_LIMITS
    for key in REQUIRED_KEYS:
        assert key in PLAN_LIMITS[plano], f"Plano {plano} missing key: {key}"


def test_demo_plan_limits():
    demo = PLAN_LIMITS[PlanoSaaS.DEMO]
    assert demo["max_equipamentos"] == 5
    assert demo["max_users"] == 3
    assert demo["max_os_mes"] == 10


def test_enterprise_plan_unlimited():
    ent = PLAN_LIMITS[PlanoSaaS.ENTERPRISE]
    assert ent["max_equipamentos"] == -1
    assert ent["max_users"] == -1
    assert ent["max_os_mes"] == -1


def test_modulo_estoque_not_in_demo():
    assert PLAN_LIMITS[PlanoSaaS.DEMO].get("modulo_estoque") is False


def test_modulo_estoque_in_profissional():
    assert PLAN_LIMITS[PlanoSaaS.PROFISSIONAL].get("modulo_estoque") is True


def test_modulo_evidencias_in_avancado():
    assert PLAN_LIMITS[PlanoSaaS.AVANCADO].get("modulo_evidencias") is True


def test_sso_only_enterprise():
    assert PLAN_LIMITS[PlanoSaaS.ENTERPRISE].get("sso") is True
    for plano in (PlanoSaaS.DEMO, PlanoSaaS.ESSENCIAL, PlanoSaaS.PROFISSIONAL, PlanoSaaS.AVANCADO):
        assert not PLAN_LIMITS[plano].get("sso")


# ── check_plan_feature ────────────────────────────────────────────────────────

def _make_org(plano: PlanoSaaS):
    org = MagicMock()
    org.plano = plano
    return org


def test_check_plan_feature_demo_no_estoque():
    org = _make_org(PlanoSaaS.DEMO)
    assert check_plan_feature(org, "modulo_estoque") is False


def test_check_plan_feature_profissional_has_preditivo():
    org = _make_org(PlanoSaaS.PROFISSIONAL)
    assert check_plan_feature(org, "modulo_preditivo") is True


def test_check_plan_feature_enterprise_has_all():
    org = _make_org(PlanoSaaS.ENTERPRISE)
    for flag in ("modulo_estoque", "modulo_evidencias", "modulo_preditivo", "sso", "kanban"):
        assert check_plan_feature(org, flag) is True, f"Enterprise missing: {flag}"


def test_check_plan_feature_unknown_flag_returns_false():
    org = _make_org(PlanoSaaS.ENTERPRISE)
    assert check_plan_feature(org, "feature_inexistente") is False


# ── check_plan_limit ──────────────────────────────────────────────────────────

def _make_db_with_counts(equip=0, users=0, os_mes=0):
    db = MagicMock()
    # Simula .filter().count()
    db.query.return_value.filter.return_value.count.return_value = max(equip, users, os_mes)
    # Override por resource
    def count_side_effect(*args, **kwargs):
        return equip
    db.query.return_value.filter.return_value.count.side_effect = None
    # Simplificado: retorna equip para qualquer query
    db.query.return_value.filter.return_value.count.return_value = equip
    return db


def test_check_plan_limit_demo_equip_at_max():
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 5  # Já no limite
    org = _make_org(PlanoSaaS.DEMO)
    org.id = "org-1"

    # Precisa de get_org_usage que faz queries separadas
    from unittest.mock import patch
    with patch("app.deps.get_org_usage") as mock_usage:
        mock_usage.return_value = {"equipamentos": 5, "users": 1, "os_mes": 0}
        ok, msg = check_plan_limit(db, org, "equipamentos")
        assert ok is False
        assert "Limite" in msg


def test_check_plan_limit_enterprise_always_ok():
    db = MagicMock()
    org = _make_org(PlanoSaaS.ENTERPRISE)
    org.id = "org-2"
    from unittest.mock import patch
    with patch("app.deps.get_org_usage") as mock_usage:
        mock_usage.return_value = {"equipamentos": 9999, "users": 9999, "os_mes": 9999}
        ok, msg = check_plan_limit(db, org, "equipamentos")
        assert ok is True


def test_check_plan_limit_unknown_resource():
    db = MagicMock()
    org = _make_org(PlanoSaaS.DEMO)
    org.id = "org-3"
    ok, msg = check_plan_limit(db, org, "unknown_resource")
    assert ok is True  # recursos desconhecidos não bloqueiam
