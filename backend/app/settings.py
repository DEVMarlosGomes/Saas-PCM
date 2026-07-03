"""
Configuração centralizada da aplicação via variáveis de ambiente.

Regra: TODA variável crítica é obrigatória em ENV=production.
A aplicação levanta RuntimeError no boot se alguma estiver ausente — fail-fast.
Nunca use valores default de segurança no código.
"""
import logging
import os
import sys

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Arquivo .env lido automaticamente se existir (dev/staging).
# Em produção, as vars devem vir do ambiente (Docker/K8s secrets).
_ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Geral ────────────────────────────────────────────────────────────────
    ENV: str = "development"

    # ── Segurança JWT ────────────────────────────────────────────────────────
    JWT_SECRET: str = ""               # obrigatório em produção
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480   # 8h
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Banco de dados ────────────────────────────────────────────────────────
    DATABASE_URL: str = ""             # obrigatório em produção

    # ── Frontend / CORS ───────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"   # obrigatório em produção
    # Origens extras sempre permitidas (não secretas — URLs públicas do deploy)
    CORS_EXTRA_ORIGINS: str = "https://aurixpcm.vercel.app"

    # ── Stripe (opcional em dev, obrigatório em prod se billing ativo) ───────
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # ── SMTP (fail-silent, opcional) ──────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@aurix.com.br"

    # ── Sentry (opcional) ─────────────────────────────────────────────────────
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    @field_validator("JWT_SECRET")
    @classmethod
    def _jwt_secret_forte(cls, v: str) -> str:
        if v and len(v) < 32:
            raise ValueError(
                "JWT_SECRET deve ter no mínimo 32 caracteres. "
                "Gere um com: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @model_validator(mode="after")
    def _validar_producao(self) -> "Settings":
        """Bloqueia o boot em produção se vars críticas estiverem ausentes."""
        if self.ENV.lower() not in ("production", "prod"):
            return self

        erros: list[str] = []
        if not self.JWT_SECRET:
            erros.append("JWT_SECRET")
        if not self.DATABASE_URL:
            erros.append("DATABASE_URL")
        if not self.FRONTEND_URL or self.FRONTEND_URL == "http://localhost:3000":
            erros.append("FRONTEND_URL (não pode ser localhost em produção)")

        if erros:
            msg = (
                "AURIX não pode iniciar em produção. "
                f"Variáveis ausentes/inválidas: {', '.join(erros)}. "
                "Consulte backend/.env.example para a lista completa."
            )
            logger.critical(msg)
            raise RuntimeError(msg)

        return self

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in ("production", "prod")

    @property
    def cors_origins(self) -> list[str]:
        """Retorna lista de origens permitidas. Nunca retorna ['*'] com credentials."""
        raw = self.FRONTEND_URL.strip()
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if not origins:
            origins = ["http://localhost:3000"]
        # Adiciona origens extras configuradas (default: URL de produção no Vercel)
        for extra in self.CORS_EXTRA_ORIGINS.split(","):
            extra = extra.strip()
            if extra and extra not in origins:
                origins.append(extra)
        return origins

    def log_security_status(self) -> None:
        """Loga (sem expor valores) quais variáveis de segurança estão presentes."""
        status = {
            "JWT_SECRET": "✓ presente" if self.JWT_SECRET else "✗ AUSENTE",
            "DATABASE_URL": "✓ presente" if self.DATABASE_URL else "✗ AUSENTE",
            "FRONTEND_URL": f"✓ {self.FRONTEND_URL}",
            "STRIPE_SECRET_KEY": "✓ presente" if self.STRIPE_SECRET_KEY else "— não configurado",
            "SMTP_HOST": f"✓ {self.SMTP_HOST}" if self.SMTP_HOST else "— não configurado",
            "SENTRY_DSN": "✓ presente" if self.SENTRY_DSN else "— não configurado",
            "ENV": self.ENV,
        }
        for k, v in status.items():
            logger.info("[AURIX Boot] %s: %s", k, v)


# Instância única — levanta RuntimeError no boot se configuração inválida
try:
    settings = Settings()
    settings.log_security_status()
except Exception as exc:
    logger.critical("Falha ao carregar configurações: %s", exc)
    # Em produção, aborta o processo imediatamente (fail-fast)
    if os.environ.get("ENV", "development").lower() in ("production", "prod"):
        sys.exit(1)
    raise
