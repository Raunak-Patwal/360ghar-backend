import logging
import yaml

from dotenv import load_dotenv
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.factory import create_app
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.utils import utc_now_iso
import sentry_sdk
import sentry_sdk.integrations.fastapi
import sentry_sdk.integrations.sqlalchemy
from sentry_sdk.integrations.logging import LoggingIntegration


load_dotenv()

# Configure logging
setup_logging()
logger = get_logger(__name__)


def _sentry_before_send(event, hint):
    """Strip sensitive headers from Sentry event payloads."""
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        if isinstance(headers, dict):
            headers.pop("authorization", None)
            headers.pop("x-api-key", None)
    return event


# Initialize Sentry
if settings.SENTRY_DSN:
    _is_dev = settings.ENVIRONMENT == "development"
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        # Free tier: keep traces low to stay within quota (100K/mo)
        traces_sample_rate=(
            settings.SENTRY_TRACES_SAMPLE_RATE
            if settings.SENTRY_TRACES_SAMPLE_RATE is not None
            else (0.5 if _is_dev else 0.05)
        ),
        send_default_pii=True,
        release=f"360ghar-backend@{settings.APP_VERSION}",
        before_send=_sentry_before_send,
        integrations=[
            sentry_sdk.integrations.fastapi.FastApiIntegration(),
            sentry_sdk.integrations.sqlalchemy.SqlalchemyIntegration(),
            LoggingIntegration(
                level=logging.WARNING,
                event_level=None,
            ),
        ],
    )
    logger.info("Sentry initialized", extra={"environment": settings.ENVIRONMENT})
else:
    logger.warning("Sentry DSN not configured - error tracking disabled")

# Create app using factory
app = create_app()


@app.get("/")
async def root():
    return {
        "message": "360Ghar Real Estate Platform API",
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with database connectivity"""
    try:
        from app.core.database import AsyncSessionLocal
        
        # Test database connection
        db_status = "unknown"
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception as db_e:
            logger.error(f"Database health check failed: {db_e}")
            db_status = "disconnected"
        
        overall_status = "healthy" if db_status == "connected" else "degraded"

        return {
            "status": overall_status,
            "database": db_status,
            **(
                {
                    "database_url": (
                        settings.DATABASE_URL.split("@", 1)[1]
                        if "@" in settings.DATABASE_URL
                        else "configured"
                    )
                }
                if settings.ENVIRONMENT != "production"
                else {}
            ),
            "timestamp": utc_now_iso(),
            "version": settings.APP_VERSION,
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.get("/config")
async def get_config():
    """Get app configuration (non-sensitive)"""
    return {
        "api_version": settings.API_V1_STR,
        "environment": settings.ENVIRONMENT,
        "database": "SQLAlchemy + PostgreSQL",
        "auth": "Supabase",
        "features": [
            "User Authentication",
            "Property Discovery",
            "Location-based Search",
            "Swipe Functionality",
            "Visit Scheduling",
            "Short-stay Bookings",
            "Analytics",
        ],
    }


@app.get(f"{settings.API_V1_STR}/openapi.yaml")
async def get_openapi_yaml():
    """Download OpenAPI specification as YAML file"""
    openapi_json = app.openapi()
    yaml_str = yaml.dump(openapi_json, default_flow_style=False, sort_keys=False)
    return Response(
        content=yaml_str,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": "attachment; filename=360ghar-openapi-spec.yaml"
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc} - {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": str(exc),
            "error": {
                "message": str(exc),
                "type": "ValidationError",
                "path": str(request.url),
                "method": request.method,
                "timestamp": utc_now_iso()
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(exc)} - {request.method} {request.url.path}", exc_info=True)
    sentry_sdk.capture_exception(exc)

    # Don't expose internal errors in production
    if settings.ENVIRONMENT == "production":
        message = "An unexpected error occurred"
    else:
        message = str(exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": message,
            "error": {
                "message": message,
                "type": "InternalServerError",
                "path": str(request.url),
                "method": request.method,
                "timestamp": utc_now_iso()
            }
        }
    )


@app.get("/debug-sentry")
async def trigger_sentry_error():
    """Trigger a test error for Sentry verification (dev only)."""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404)
    raise RuntimeError("Sentry test error - this is intentional")
