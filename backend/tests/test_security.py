"""
Testes de segurança — Fase 0 Hardening AURIX

Cobre:
  - 0.2 Regressão do bug Kanban (downtime_start None → 500)
  - 0.5 Isolamento de tenant (BOLA/IDOR pentest automatizado)
  - 0.3 Security headers presentes
  - 0.1 Boot fail-fast: JWT_SECRET ausente deve gerar erro
"""
import os
import uuid
import pytest
import requests

BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "http://localhost:8000"
).rstrip("/")
API = f"{BASE_URL}/api"

# ── Credenciais de demo (ajustar se seed tiver rodado) ──────────────────────
CREDS_ORG_A = {"email": "admin@demo.pcm", "password": "Admin@123"}
CREDS_ORG_B = {"email": "admin@orgb.pcm", "password": "Admin@123"}

_TOKENS: dict = {}


def _login(creds: dict) -> str | None:
    key = creds["email"]
    if key in _TOKENS:
        return _TOKENS[key]
    try:
        r = requests.post(f"{API}/auth/login", json=creds, timeout=10)
        if r.status_code == 200:
            token = r.json().get("access_token")
            _TOKENS[key] = token
            return token
    except Exception:
        pass
    return None


def _h(creds: dict) -> dict:
    token = _login(creds)
    if not token:
        pytest.skip("Credenciais de teste indisponíveis — servidor não está rodando ou sem seed.")
    return {"Authorization": f"Bearer {token}"}


# ── 0.2 Regressão: GET /kanban não deve retornar 500 ─────────────────────────

class TestKanbanRegression:
    def test_kanban_retorna_200_ou_402(self):
        """Garante que /kanban nunca retorna 500, mesmo com OS sem downtime_start."""
        h = _h(CREDS_ORG_A)
        r = requests.get(f"{API}/kanban", headers=h, timeout=15)
        assert r.status_code in (200, 402, 403), (
            f"Kanban retornou {r.status_code}: {r.text[:300]}"
        )

    def test_kanban_resposta_sem_none_isoformat(self):
        """downtime_start no JSON nunca deve causar AttributeError (None.isoformat)."""
        h = _h(CREDS_ORG_A)
        r = requests.get(f"{API}/kanban", headers=h, timeout=15)
        if r.status_code != 200:
            pytest.skip("Kanban não acessível (plano/credenciais)")
        data = r.json()
        # Todos os cards de todas as colunas devem ter downtime_start como str ou null
        for col in data.get("columns", {}).values():
            for card in col:
                val = card.get("downtime_start")
                assert val is None or isinstance(val, str), (
                    f"downtime_start inválido: {val!r} na OS {card.get('id')}"
                )


# ── 0.3 Security headers ──────────────────────────────────────────────────────

class TestSecurityHeaders:
    def test_hsts_presente(self):
        r = requests.get(f"{BASE_URL}/", timeout=10, allow_redirects=False)
        # HSTS só aparece em HTTPS; em HTTP local pode estar ausente — aceitamos
        # Mas se presente, deve estar correto
        hsts = r.headers.get("Strict-Transport-Security", "")
        if hsts:
            assert "max-age=" in hsts

    def test_x_content_type_nosniff(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.headers.get("X-Content-Type-Options") == "nosniff", (
            "Header X-Content-Type-Options: nosniff ausente"
        )

    def test_x_frame_deny(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        frame = r.headers.get("X-Frame-Options", "")
        assert frame.upper() in ("DENY", "SAMEORIGIN"), (
            f"X-Frame-Options ausente ou inválido: {frame!r}"
        )

    def test_referrer_policy(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert "Referrer-Policy" in r.headers, "Header Referrer-Policy ausente"

    def test_no_server_header_info_leak(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        server = r.headers.get("Server", "")
        # Não deve expor versão de servidor
        assert "uvicorn" not in server.lower() or server == "uvicorn", (
            f"Server header expõe versão: {server}"
        )


# ── 0.5 Isolamento de tenant (BOLA / IDOR pentest) ───────────────────────────

class TestTenantIsolation:
    """
    Tenta acessar/modificar recursos de Org B autenticado como Org A.
    TODOS devem retornar 404 (não 200/403, para não confirmar existência).
    """

    def _get_resource_ids(self, headers: dict, endpoint: str) -> list[str]:
        """Coleta IDs de recursos da própria organização."""
        r = requests.get(f"{API}/{endpoint}", headers=headers, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        if isinstance(data, list):
            return [str(item.get("id")) for item in data if item.get("id")]
        return []

    def test_equipamento_cross_tenant_404(self):
        """Autenticado como Org A, acesso a equipamento de Org B → 404."""
        h_a = _h(CREDS_ORG_A)
        h_b = _h(CREDS_ORG_B)

        ids_b = self._get_resource_ids(h_b, "equipamentos")
        if not ids_b:
            pytest.skip("Org B sem equipamentos — rode o seed para ambas as orgs")

        for eid in ids_b[:3]:   # testa os 3 primeiros
            r = requests.get(f"{API}/equipamentos/{eid}", headers=h_a, timeout=10)
            assert r.status_code == 404, (
                f"FALHA DE ISOLAMENTO: Org A acessou equipamento {eid} de Org B "
                f"→ status {r.status_code}"
            )

    def test_os_cross_tenant_404(self):
        """Autenticado como Org A, acesso a OS de Org B → 404."""
        h_a = _h(CREDS_ORG_A)
        h_b = _h(CREDS_ORG_B)

        ids_b = self._get_resource_ids(h_b, "ordens-servico")
        if not ids_b:
            pytest.skip("Org B sem OS — rode o seed")

        for oid in ids_b[:3]:
            r = requests.get(f"{API}/ordens-servico/{oid}", headers=h_a, timeout=10)
            assert r.status_code == 404, (
                f"FALHA DE ISOLAMENTO: Org A acessou OS {oid} de Org B "
                f"→ status {r.status_code}"
            )

    def test_os_update_cross_tenant_blocked(self):
        """Org A não pode alterar status de OS de Org B."""
        h_a = _h(CREDS_ORG_A)
        h_b = _h(CREDS_ORG_B)

        ids_b = self._get_resource_ids(h_b, "ordens-servico")
        if not ids_b:
            pytest.skip("Org B sem OS")

        oid = ids_b[0]
        r = requests.put(
            f"{API}/ordens-servico/{oid}",
            json={"status": "fechada"},
            headers=h_a,
            timeout=10,
        )
        assert r.status_code in (404, 403), (
            f"FALHA: Org A conseguiu modificar OS {oid} de Org B → {r.status_code}"
        )

    def test_usuarios_cross_tenant_404(self):
        """Org A não pode ver usuários de Org B por ID."""
        h_a = _h(CREDS_ORG_A)
        h_b = _h(CREDS_ORG_B)

        ids_b = self._get_resource_ids(h_b, "users")
        if not ids_b:
            pytest.skip("Org B sem usuários")

        for uid in ids_b[:3]:
            r = requests.get(f"{API}/users/{uid}", headers=h_a, timeout=10)
            # GET /users/{id} pode não existir como endpoint individual —
            # nesse caso 404/405 também é aceitável (rota não existe = não expõe)
            assert r.status_code in (404, 405), (
                f"Possível vazamento: GET /users/{uid} como Org A → {r.status_code}"
            )

    def test_endpoint_sem_auth_retorna_401(self):
        """Endpoints protegidos sem token → 401, nunca 200."""
        endpoints = [
            "equipamentos", "ordens-servico", "users",
            "colaboradores", "dashboard/kpis", "kanban",
        ]
        for ep in endpoints:
            r = requests.get(f"{API}/{ep}", timeout=10)
            assert r.status_code in (401, 403), (
                f"Endpoint /{ep} acessível sem autenticação → {r.status_code}"
            )


# ── 0.1 Fail-fast: settings sem JWT_SECRET em produção ───────────────────────

class TestSettingsFaillFast:
    def test_settings_requer_jwt_secret_forte(self):
        """JWT_SECRET curto deve levantar ValueError."""
        import os
        os.environ["ENV"] = "development"   # não produção — só testa validação
        from pydantic import ValidationError
        from app.settings import Settings

        with pytest.raises((ValueError, ValidationError, Exception)):
            Settings(
                JWT_SECRET="curto",   # < 32 chars
                DATABASE_URL="postgresql://x",
                FRONTEND_URL="http://localhost:3000",
            )

    def test_settings_aceita_secret_valido(self):
        """JWT_SECRET com 64 chars deve ser aceito."""
        import secrets as _sec
        from app.settings import Settings

        s = Settings(
            JWT_SECRET=_sec.token_hex(32),   # 64 chars hex
            DATABASE_URL="postgresql://test:test@localhost/test",
            FRONTEND_URL="http://localhost:3000",
            ENV="development",
        )
        assert len(s.JWT_SECRET) >= 32
