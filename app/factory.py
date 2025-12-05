"""
Application factory for creating FastAPI app instances.
"""
import fastmcp
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.api_v1.api import api_router
from app.core.cache import cache_manager
from app.core.config import settings
from app.core.database import engine
from app.core.logging import get_logger
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import RequestIDMiddleware, SecurityHeadersMiddleware
from app.mcp.auth_provider import SupabaseAuthProvider, configure_fastmcp_auth
from app.mcp.server import mcp

logger = get_logger(__name__)


def create_app(testing: bool = False) -> FastAPI:
    """Create and configure FastAPI application."""

    # Configure FastMCP auth to use Supabase-backed JWT verification for HTTP.
    configure_fastmcp_auth()
    mcp.auth = SupabaseAuthProvider()

    # Create the MCP HTTP sub-application once so we can use its lifespan
    # and mount it under /mcp on the main FastAPI app.
    mcp_app = mcp.http_app(
        path="/",
        transport="http",
        json_response=False,
        stateless_http=True,
        middleware=None,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan manager for startup and shutdown events."""
        async with mcp_app.lifespan(app):
            try:
                # Initialize cache manager (optional Redis connection)
                if not testing:
                    try:
                        await cache_manager.connect()
                    except Exception as cache_e:
                        logger.warning(f"Cache connection skipped/failed: {cache_e}")

                # Optional: start push notification scheduler
                if not testing:
                    try:
                        from app.services.notification_scheduler import (
                            start_notification_scheduler,
                        )
                        start_notification_scheduler(app)
                    except Exception as sched_e:
                        logger.error(f"Failed to start notification scheduler: {sched_e}")

                # Optional: start vector sync scheduler
                if not testing:
                    try:
                        from app.services.vector_sync_scheduler import (
                            start_vector_sync_scheduler,
                        )
                        start_vector_sync_scheduler(app)
                    except Exception as sched_vec_e:
                        logger.error(f"Failed to start vector sync scheduler: {sched_vec_e}")
            except Exception as e:
                logger.error(f"Application startup failed: {e}")

            logger.info(
                "API started",
                extra={
                    "event": "startup",
                    "env": settings.ENVIRONMENT,
                    "version": "2.0.0",
                },
            )

            yield

            # Shutdown
            if not testing:
                try:
                    await cache_manager.disconnect()
                except Exception as cache_e:
                    logger.warning(f"Cache disconnect skipped/failed: {cache_e}")
            await engine.dispose()
            logger.info("API shutdown", extra={"event": "shutdown"})

    app = FastAPI(
        lifespan=lifespan,
        debug=(settings.ENVIRONMENT == "development"),
        title="360Ghar Real Estate Platform",
        description="Tinder-like real estate platform backend APIs with SQLAlchemy + Supabase Auth",
        version="2.0.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        contact={
            "name": "360Ghar Development Team",
            "email": "dev@360ghar.com",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
        servers=[
            {
                "url": "http://localhost:8000",
                "description": "Development server",
            },
            {
                "url": "https://api.360ghar.com",
                "description": "Production server",
            },
        ],
    )

    # Configure CORS properly for production and development
    if settings.ENVIRONMENT == "development" or testing:
        cors_origins = ["*"]
        cors_credentials = False
    else:
        cors_origins = settings.CORS_ORIGINS
        cors_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRF-Token",
            "X-API-Key",
            "Cache-Control",
            "Pragma",
            "Expires",
            "X-Process-Time",
            "X-Performance-Tier",
        ],
        expose_headers=[
            "Content-Length",
            "Content-Range",
            "X-Process-Time",
            "X-Performance-Tier",
        ],
        max_age=86400,
    )

    # Add request ID tracking for debugging
    app.add_middleware(RequestIDMiddleware)

    # Add security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Add global rate limiting (works with or without Redis)
    if not testing:
        app.add_middleware(
            RateLimitMiddleware,
            calls=100,
            period=60,
            scope="global"
        )

    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Mount MCP HTTP app at /mcp using FastMCP's HTTP transport.
    app.mount("/mcp", mcp_app)

    return app
