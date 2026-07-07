"""
Teste de regressão — SecurityHeadersMiddleware

Bug: `response.headers.pop("Server", None)` — MutableHeaders (Starlette) não
tem `.pop()`, então TODA resposta que passava por este middleware quebrava
com AttributeError. Como o middleware fica por FORA do CORSMiddleware na
pilha (ver server.py), a exceção nunca chegava ao CORSMiddleware e o cliente
recebia um 500 sem headers de CORS — visto no browser como "erro de CORS".
"""
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.middleware.security_headers import SecurityHeadersMiddleware


def _client() -> TestClient:
    mini_app = FastAPI()

    @mini_app.get("/ping")
    async def ping():
        return {"ok": True}

    mini_app.add_middleware(SecurityHeadersMiddleware)
    return TestClient(mini_app)


def test_response_nao_quebra_e_remove_server_header():
    resp = _client().get("/ping")
    assert resp.status_code == 200
    assert "Server" not in resp.headers


def test_headers_de_seguranca_presentes():
    resp = _client().get("/ping")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in resp.headers
    assert "Referrer-Policy" in resp.headers
