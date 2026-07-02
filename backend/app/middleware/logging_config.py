"""
Configuração de logging estruturado para AURIX.

Em produção: JSON (um objeto por linha, pronto para Loki/CloudWatch).
Em dev: formato legível com cores via logging padrão.
"""
import json
import logging
import logging.config
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Serializa cada LogRecord como uma linha JSON — sem PII."""

    _MASK = frozenset({"password", "senha", "token", "secret", "authorization", "jwt"})

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()

        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": msg,
        }

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # Campos extras adicionados com logger.info("...", extra={...})
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in {
                "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name", "message",
            }
            and not k.startswith("_")
        }
        for k, v in extras.items():
            if k.lower() in _JsonFormatter._MASK:
                extras[k] = "***"
        if extras:
            payload["ctx"] = extras

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(is_production: bool = False) -> None:
    """
    Chame uma vez no startup.
    is_production=True → JSON em stdout.
    is_production=False → formato legível em stdout.
    """
    root = logging.getLogger()

    if root.handlers:
        # Já configurado (e.g., uvicorn configurou antes); apenas ajusta nível.
        root.setLevel(logging.INFO)
        return

    handler = logging.StreamHandler(sys.stdout)

    if is_production:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {"console": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout"}},
            "loggers": {
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"level": "WARNING"},   # suprime GET /health spam
                "sqlalchemy.engine": {"level": "WARNING"},
            },
        }
    )

    root.setLevel(logging.INFO)
    root.addHandler(handler)
