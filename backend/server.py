"""
AURIX — Bootstrap server (Fase 4).
Mantém: middlewares, SSE, startup/shutdown, registro de routers.
Toda lógica de negócio vive em app/{routers,services,schemas,models}.
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio as _asyncio
import logging

import jwt as _jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text as _sa_text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.cors import CORSMiddleware

from app.settings import settings
from app.middleware.logging_config import configure_logging
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.tenant import TenantIsolationMiddleware

from app.database import engine, SessionLocal, Base
# Importar todos os módulos de models para que Base.metadata os conheça
import app.models.core          # noqa: F401
import app.models.estoque       # noqa: F401
import app.models.evidencias    # noqa: F401
try:
    import app.models.models    # noqa: F401
except ImportError:
    pass

from app.models.core import User
from app.deps import get_current_user, get_jwt_secret
from app.services.db_migrations import DDL as _DDL, ALTER_TYPES as _ALTER_TYPES

configure_logging(is_production=settings.is_production)
logger = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AURIX — Tecnologia para a Gestão Industrial",
    version="4.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

# ── Middlewares ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(TenantIsolationMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── Routers (Fase 4) ──────────────────────────────────────────────────────────
from app.routers import (
    auth, users, colaboradores, organization, sectors,
    equipamentos, os, custos, preventivos, iot,
    dashboard, auditoria, notificacoes, billing,
    preditivo, relatorios, kanban, superuser, seed,
)
from app.routers.estoque import router as _estoque_router, get_current_user_stub as _estoque_stub
from app.routers.evidencias import router as _evidencias_router, get_current_user_stub as _evidencias_stub

for _r in (
    auth.router, users.router, colaboradores.router, organization.router,
    sectors.router, equipamentos.router, os.router, custos.router,
    preventivos.router, iot.router, dashboard.router, auditoria.router,
    notificacoes.router, billing.router, preditivo.router, relatorios.router,
    kanban.router, superuser.router, seed.router,
):
    app.include_router(_r, prefix="/api")

# Fase 1/2 routers com dependency_overrides
app.dependency_overrides[_estoque_stub] = get_current_user
app.dependency_overrides[_evidencias_stub] = get_current_user
app.include_router(_estoque_router, prefix="/api")
app.include_router(_evidencias_router, prefix="/api")

# ── Root ─────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "AURIX — Tecnologia para a Gestão Industrial", "version": "4.0.0"}


# ── Healthchecks (NIST Detect) ────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Liveness probe — responde 200 se o processo está vivo."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness probe — verifica conectividade com DB."""
    try:
        with engine.connect() as conn:
            conn.execute(_sa_text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "db": str(exc)},
        )

# ── SSE — tempo real por tenant (Fase 3) ─────────────────────────────────────
@app.get("/api/events")
async def sse_events(token: str, request: Request):
    """
    Server-Sent Events autenticado por JWT via query param.
    Canal isolado por organization_id — eventos de um tenant nunca chegam a outro.
    Keepalive a cada 25 s via SSE comment `: ping`.
    """
    try:
        payload = _jwt.decode(token, get_jwt_secret(), algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if payload.get("type") != "access" or not user_id:
            raise ValueError("token inválido")
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Token inválido ou expirado."})

    db = SessionLocal()
    try:
        _user = db.query(User).filter(User.id == user_id).first()
        if not _user or not _user.ativo:
            return JSONResponse(status_code=401, content={"detail": "Usuário não autorizado."})
        org_id = str(_user.organization_id)
    finally:
        db.close()

    from app.services.realtime import subscribe, unsubscribe
    q = subscribe(org_id)

    async def _generator():
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await _asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {msg}\n\n"
                except _asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            unsubscribe(org_id, q)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ── Schema init (create_all + ALTER TABLE idempotentes) ──────────────────────
_db_ready = False


def _init_database():
    global _db_ready
    if _db_ready:
        return
    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            for sql in _DDL:
                try:
                    conn.execute(_sa_text(sql))
                except Exception as exc:
                    logger.debug("Migration skipped: %s — %s", sql[:60], exc)
            conn.commit()
        ac_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
        with ac_engine.connect() as conn:
            for sql in _ALTER_TYPES:
                try:
                    conn.execute(_sa_text(sql))
                except Exception as exc:
                    logger.debug("ALTER TYPE skipped: %s — %s", sql[:60], exc)
        _db_ready = True
        logger.info("Database schema verified.")
    except SQLAlchemyError as exc:
        logger.warning("Database unavailable at startup: %s", exc)


# ── Lifecycle ─────────────────────────────────────────────────────────────────
_scheduler = None


@app.on_event("startup")
async def startup():
    global _scheduler
    logger.info("Starting AURIX v4.0.0 ...")
    settings.log_security_status()
    # ── Sentry (4.2 — Observabilidade) ────────────────────────────────────────
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
                send_default_pii=False,  # LGPD: sem PII nos eventos
                integrations=[FastApiIntegration(), SqlalchemyIntegration()],
                release=f"aurix@4.0.0",
            )
            logger.info("Sentry initialized (DSN present).")
        except ImportError:
            logger.warning("sentry-sdk not installed — error tracking disabled.")
    _init_database()
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.services.scheduler import (
            job_processar_leituras, job_atualizar_mttr_mtbf,
            job_gerar_os_preventivas, job_auto_aprovar_sla, run_job,
        )
        _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
        _scheduler.add_job(lambda: run_job(job_processar_leituras),  "interval", minutes=15, id="proc_leituras")
        _scheduler.add_job(lambda: run_job(job_auto_aprovar_sla),    "interval", minutes=30, id="auto_aprovar")
        _scheduler.add_job(lambda: run_job(job_gerar_os_preventivas), "cron",    hour=7,  minute=0, id="os_preventivas")
        _scheduler.add_job(lambda: run_job(job_atualizar_mttr_mtbf),  "cron",    hour=0,  minute=0, id="mttr_mtbf")
        _scheduler.start()
        logger.info("APScheduler started with 4 jobs.")
    except ImportError:
        logger.warning("APScheduler not installed — background jobs disabled.")
    except Exception as exc:
        logger.warning("APScheduler failed to start: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
    logger.info("AURIX shutdown complete.")
