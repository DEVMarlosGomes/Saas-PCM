# CLAUDE.md — Convenções do projeto AURIX

## Segurança (NÃO NEGOCIÁVEL)
- **Nenhum segredo no código.** Tudo via env var. Fail-fast se var crítica ausente.
- **Toda query é tenant-scoped por `organization_id`.** Proibido query sem filtro de tenant.
- **Toda entrada validada por schema Pydantic.** Nunca confiar em input do cliente.
- **Toda ação sensível gera AuditoriaLog** (quem, o quê, quando, IP, user-agent).
- Senhas: bcrypt (já em uso). Tokens: JWT assinado com segredo forte de env (≥ 32 bytes).
- Após carregar qualquer recurso por ID, validar `obj.organization_id == user.organization_id` → retornar 404 se divergir (não 403 — não confirmar existência).
- Cookie de refresh: `samesite="strict"`, `httponly=True`, `secure=True` em produção.
- CORS: nunca `["*"]` com `allow_credentials=True`. Usar lista explícita de origens.

## Comandos
- **Backend:** `cd backend && uvicorn server:app --reload`
- **Testes backend:** `cd backend && pytest -v tests/`
- **Lint/audit backend:** `cd backend && black . && flake8 . && bandit -r . && pip-audit`
- **Frontend:** `cd frontend && npm start`
- **Build frontend:** `cd frontend && npm run build`
- **Testes frontend:** `cd frontend && npm test`

## Regras de arquitetura
- Lógica **nova** vai em `backend/app/{routers,services,schemas,models}`. NÃO engordar `server.py`.
- `server.py` deve ser desmontado em routers ao longo das fases (ver Fase 4).
- Migrações de schema via **Alembic versionado** — nunca `ALTER` inline em código de aplicação.
- Quando `ALTER TYPE` for inevitável (PostgreSQL enum), usar conexão com `isolation_level="AUTOCOMMIT"`.
- Todo endpoint que aceita ID de recurso deve validar ownership de tenant ANTES de processar.
- Use `scoped_query(model, user, db)` de `backend/app/utils/tenant.py` em vez de `.query(Model)` direto.

## Estrutura de pastas relevantes
```
backend/
  server.py            ← monolito atual (migrar progressivamente)
  app/
    settings.py        ← Pydantic BaseSettings (fail-fast em produção)
    config.py          ← constantes de plano/SLA (sem segredos)
    middleware/
      security_headers.py  ← HSTS, CSP, X-Frame, etc.
      tenant.py            ← TenantIsolationMiddleware
    utils/
      tenant.py        ← scoped_query helper
    models/
    schemas/
    routers/
    services/
  tests/
    test_security.py   ← testes de pentest de isolamento de tenant
```

## Variáveis de ambiente obrigatórias (produção)
Ver `backend/.env.example` para a lista completa.
As críticas são: `JWT_SECRET`, `DATABASE_URL`, `FRONTEND_URL`.
A aplicação **não sobe** se alguma estiver ausente em `ENV=production`.

## Frameworks de segurança de referência
- OWASP ASVS 5.0 Nível 2 (L3 em auth, billing, tenant isolation)
- OWASP Top 10 2021 + Top 10 API 2023
- LGPD: dados pessoais mascarados em logs
- NIST CSF 2.0: Identify → Protect → Detect → Respond → Recover
