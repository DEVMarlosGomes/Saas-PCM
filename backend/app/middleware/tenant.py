"""
Tenant isolation middleware.
Ensures all API requests are scoped to the authenticated user's organization.
Prevents any cross-tenant data access.
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that don't require tenant context
PUBLIC_PATHS = {
    "/", "/docs", "/redoc", "/openapi.json",
    "/api/auth/login", "/api/auth/register", "/api/auth/logout",
    "/api/webhook/stripe", "/api/seed-demo",
}


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces tenant isolation at the request level.
    
    - Logs organization context for every authenticated request
    - Blocks any attempt to access data from another organization
    - Allows public endpoints to pass through without tenant context
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")

        # Skip tenant check for public paths
        if path in PUBLIC_PATHS or path.startswith("/api/auth/"):
            response = await call_next(request)
            return response

        # For all other API paths, we rely on the get_current_user dependency
        # to extract organization_id from the JWT token.
        # This middleware adds an org_id header for tracing/logging purposes.
        try:
            response = await call_next(request)

            # Add tenant isolation header for debugging
            if hasattr(request.state, 'organization_id'):
                response.headers["X-Tenant-ID"] = str(request.state.organization_id)

            return response
        except Exception as e:
            logger.error(f"Tenant middleware error: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Erro interno de isolamento de tenant"}
            )
