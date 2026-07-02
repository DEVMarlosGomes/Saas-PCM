"""
Fase 5 — unit tests para MFA service, RBAC service, LGPD anonymization.
Roda sem banco de dados (usa MagicMock).
"""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

# ── env stubs must be set before any app import ──────────────────────────────
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests-only-32bytes!!")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_f5.db")
os.environ.setdefault("MFA_ENCRYPTION_KEY", "")  # will be handled by service


# ═════════════════════════════════════════════════════════════════════════════
# MFA SERVICE
# ═════════════════════════════════════════════════════════════════════════════

class TestMFAService(unittest.TestCase):
    """Tests for app.services.mfa_service (pyotp + Fernet)."""

    def setUp(self):
        from cryptography.fernet import Fernet
        self.key = Fernet.generate_key()
        os.environ["MFA_ENCRYPTION_KEY"] = self.key.decode()
        # Reimport so module picks up the key
        import importlib, app.services.mfa_service as m
        importlib.reload(m)
        self.mfa = m

    def _skip_if_no_pyotp(self):
        try:
            import pyotp  # noqa
        except ImportError:
            self.skipTest("pyotp not installed")

    def test_setup_returns_provisioning_uri(self):
        self._skip_if_no_pyotp()
        result = self.mfa.setup("user@example.com")
        self.assertIn("provisioning_uri", result)
        self.assertIn("secret_encrypted", result)
        self.assertIn("otpauth://totp/", result["provisioning_uri"])

    def test_setup_qr_key_present(self):
        self._skip_if_no_pyotp()
        result = self.mfa.setup("user@example.com", issuer="AURIX")
        self.assertIn("qr_data", result)

    def test_verify_valid_code(self):
        self._skip_if_no_pyotp()
        import pyotp
        from cryptography.fernet import Fernet
        secret = pyotp.random_base32()
        f = Fernet(self.key)
        encrypted = f.encrypt(secret.encode()).decode()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        self.assertTrue(self.mfa.verify(encrypted, code))

    def test_verify_wrong_code(self):
        self._skip_if_no_pyotp()
        import pyotp
        from cryptography.fernet import Fernet
        secret = pyotp.random_base32()
        f = Fernet(self.key)
        encrypted = f.encrypt(secret.encode()).decode()
        self.assertFalse(self.mfa.verify(encrypted, "000000"))

    def test_generate_backup_codes_count(self):
        codes, hashed = self.mfa.generate_backup_codes(10)
        self.assertEqual(len(codes), 10)
        self.assertEqual(len(hashed), 10)

    def test_backup_code_format(self):
        codes, _ = self.mfa.generate_backup_codes(5)
        for c in codes:
            # token_hex(5) → 10 hex chars uppercased
            self.assertEqual(len(c), 10, f"Expected 10-char code, got {c!r}")

    def test_verify_backup_code_success(self):
        codes, hashed = self.mfa.generate_backup_codes(5)
        ok, remaining = self.mfa.verify_backup_code(codes[0], hashed)
        self.assertTrue(ok)
        self.assertEqual(len(remaining), 4)

    def test_verify_backup_code_wrong(self):
        _, hashed = self.mfa.generate_backup_codes(5)
        ok, remaining = self.mfa.verify_backup_code("BADCODE", hashed)
        self.assertFalse(ok)
        self.assertEqual(len(remaining), 5)

    def test_verify_backup_code_consumed(self):
        codes, hashed = self.mfa.generate_backup_codes(3)
        _, remaining1 = self.mfa.verify_backup_code(codes[0], hashed)
        ok2, remaining2 = self.mfa.verify_backup_code(codes[0], remaining1)
        self.assertFalse(ok2)
        self.assertEqual(len(remaining2), 2)


# ═════════════════════════════════════════════════════════════════════════════
# RBAC SERVICE
# ═════════════════════════════════════════════════════════════════════════════

class TestRBACService(unittest.TestCase):
    """Tests for app.services.rbac_service (permission logic, no DB)."""

    def setUp(self):
        import importlib, app.services.rbac_service as r
        importlib.reload(r)
        self.rbac = r

    def test_superusuario_has_wildcard(self):
        self.assertTrue(self.rbac.has_permission("superusuario", "os", "criar"))
        self.assertTrue(self.rbac.has_permission("superusuario", "billing", "ler"))
        self.assertTrue(self.rbac.has_permission("superusuario", "anything", "delete"))

    def test_admin_can_manage_users(self):
        self.assertTrue(self.rbac.has_permission("admin", "usuarios", "criar"))
        self.assertTrue(self.rbac.has_permission("admin", "usuarios", "ver"))

    def test_tecnico_can_view_os(self):
        self.assertTrue(self.rbac.has_permission("tecnico", "os", "ver"))

    def test_tecnico_cannot_manage_users(self):
        self.assertFalse(self.rbac.has_permission("tecnico", "usuarios", "criar"))
        self.assertFalse(self.rbac.has_permission("tecnico", "billing", "ler"))

    def test_operador_can_create_os(self):
        self.assertTrue(self.rbac.has_permission("operador", "os", "criar"))

    def test_operador_cannot_access_financeiro(self):
        self.assertFalse(self.rbac.has_permission("operador", "financeiro", "ler"))

    def test_unknown_role_denied(self):
        self.assertFalse(self.rbac.has_permission("ghost_role", "os", "ver"))

    def test_wildcard_resource(self):
        """admin has os:* which should match any acao on os"""
        self.assertTrue(self.rbac.has_permission("admin", "os", "deletar"))
        self.assertTrue(self.rbac.has_permission("admin", "os", "exportar"))

    def test_cache_invalidation_no_error(self):
        """invalidate_cache must not raise even for unknown user/org."""
        self.rbac.invalidate_cache("unknown_user_id", "unknown_org_id")


# ═════════════════════════════════════════════════════════════════════════════
# LGPD — anonymization helper
# ═════════════════════════════════════════════════════════════════════════════

class TestLGPDAnonymization(unittest.TestCase):
    """Tests the _anonymize_user helper logic from lgpd.py."""

    def _make_fake_user(self, uid="abc12345"):
        u = MagicMock()
        u.id = uid
        u.nome = "João Silva"
        u.email = "joao@empresa.com"
        u.employee_id = "EMP001"
        u.generic_session_sector = "Manutenção"
        u.ativo = True
        return u

    def test_anonymization_clears_pii(self):
        from app.routers.lgpd import _anonymize_user
        db = MagicMock()
        user = self._make_fake_user()
        _anonymize_user(db, user)
        self.assertIn("removed.lgpd", user.email)
        self.assertIsNone(user.employee_id)
        self.assertIsNone(user.generic_session_sector)
        self.assertFalse(user.ativo)

    def test_anonymized_email_contains_uid_prefix(self):
        from app.routers.lgpd import _anonymize_user
        db = MagicMock()
        user = self._make_fake_user(uid="testuser1234")
        _anonymize_user(db, user)
        self.assertIn("testuser", user.email)

    def test_anonymization_calls_db_commit(self):
        from app.routers.lgpd import _anonymize_user
        db = MagicMock()
        user = self._make_fake_user()
        _anonymize_user(db, user)
        db.commit.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
# Report Service — basic smoke tests
# ═════════════════════════════════════════════════════════════════════════════

class TestReportService(unittest.TestCase):
    """Smoke tests for PDF/Excel generation — verify bytes returned."""

    def _sample_os_list(self):
        return [
            {
                "numero": 1, "equipamento_nome": "Bomba A",
                "tipo": "corretiva", "status": "fechada",
                "prioridade": "alta", "created_at": "2026-06-01",
                "tecnico_nome": "João", "tempo_reparo": 120,
                "solucao": "Troca de rolamento", "custo_parada": 500.0,
            },
        ]

    def test_generate_os_pdf_returns_bytes(self):
        try:
            from app.services.report_service import generate_os_pdf
            result = generate_os_pdf(self._sample_os_list(), "Org Teste", "06/2026")
            self.assertIsInstance(result, bytes)
            self.assertGreater(len(result), 0)
            # PDF magic bytes
            self.assertTrue(result.startswith(b"%PDF"))
        except RuntimeError as e:
            self.skipTest(f"reportlab not installed: {e}")

    def test_generate_kpi_pdf_returns_bytes(self):
        try:
            from app.services.report_service import generate_kpi_pdf
            kpis = {
                "total_os_mes": 10, "os_abertas": 3, "os_atrasadas": 1,
                "mttr": 2.5, "mtbf": 48.0, "disponibilidade": 95.0,
                "custo_total_mes": 1500.00,
            }
            result = generate_kpi_pdf(kpis, "Org Teste", "06/2026")
            self.assertIsInstance(result, bytes)
            self.assertTrue(result.startswith(b"%PDF"))
        except RuntimeError as e:
            self.skipTest(f"reportlab not installed: {e}")

    def test_generate_os_excel_returns_bytes(self):
        try:
            from app.services.report_service import generate_os_excel
            result = generate_os_excel(self._sample_os_list(), "Org Teste", "06/2026")
            self.assertIsInstance(result, bytes)
            # xlsx magic bytes (PK zip)
            self.assertTrue(result[:2] == b"PK")
        except RuntimeError as e:
            self.skipTest(f"openpyxl not installed: {e}")


if __name__ == "__main__":
    unittest.main()
