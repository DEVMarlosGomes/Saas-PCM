"""
SecurityHeadersMiddleware — injeta headers de segurança em TODAS as respostas HTTP.

Cobre OWASP ASVS 5.0 L2, itens:
  14.4.1 — X-Content-Type-Options: nosniff
  14.4.2 — Content-Disposition (arquivos — aplicado no endpoint)
  14.4.3 — X-Frame-Options: DENY
  14.4.4 — Content-Security-Policy
  14.4.5 — Referrer-Policy
  14.4.6 — Strict-Transport-Security (apenas HTTPS)
  14.4.7 — Permissions-Policy
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# CSP conservador — REST API não serve HTML, então default-src 'none' é seguro.
# Ajuste se o backend servir algum template HTML.
_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'none'; "
    "base-uri 'none'"
)

_PERMISSIONS = (
    "geolocation=(), "
    "microphone=(), "
    "camera=(), "
    "payment=(), "
    "usb=()"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["Permissions-Policy"] = _PERMISSIONS
        response.headers["X-DNS-Prefetch-Control"] = "off"

        # HSTS somente se a requisição chegou por HTTPS (proxy/load balancer pode setar header)
        forwarded_proto = (
            request.headers.get("X-Forwarded-Proto", "")
            or request.headers.get("X-Forwarded-Protocol", "")
        )
        if (
            request.url.scheme == "https"
            or forwarded_proto.lower() == "https"
        ):
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        # Remove header que expõe versão do servidor
        response.headers.pop("Server", None)

        return response
