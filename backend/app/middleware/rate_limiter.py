"""
Rate limiting via slowapi (wrapper de limits sobre Starlette).

Limites aplicados em server.py com o decorator @limiter.limit("N/period"):
  - Login / registro : 10/minute  (brute-force)
  - Billing / Stripe : 20/minute  (abuso de trial)
  - IoT / telemetria : 200/minute (alta frequência, mas não ilimitada)
  - API key gen      : 5/minute   (evitar enumeração)
  - Default catch-all: 300/minute (proteção geral)

O handler customizado retorna JSON consistente com os outros erros da API.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse


def _get_identifier(request: Request) -> str:
    """Usa IP real considerando proxies reversos."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # O primeiro IP na lista é o cliente original
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_identifier,
    default_limits=["300/minute"],
    # Não levanta exceção para rotas sem decorator — apenas as anotadas são limitadas
    enabled=True,
)


async def rate_limit_exceeded_handler(request: Request, exc) -> JSONResponse:
    retry_after = getattr(exc, "retry_after", None)
    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Muitas requisições. Aguarde um momento e tente novamente.",
            "code": "RATE_LIMIT_EXCEEDED",
        },
        headers=headers,
    )


# Limites reutilizáveis por categoria — importe estes em server.py
LIMIT_AUTH = "10/minute"        # login, register, forgot-password
LIMIT_BILLING = "20/minute"     # checkout, webhook, plan change
LIMIT_IOT = "200/minute"        # telemetria, ping de sensores
LIMIT_APIKEY = "5/minute"       # geração de API keys
LIMIT_STRICT = "5/minute"       # ações sensíveis (delete, reassign)
