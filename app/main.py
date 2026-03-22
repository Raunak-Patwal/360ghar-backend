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


load_dotenv()

# Configure logging
setup_logging()
logger = get_logger(__name__)

# Initialize Sentry
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        # Set sample rate for performance monitoring
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "development" else 0.1,
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
        # Release tracking
        release="360ghar-backend@2.0.0",
        # FastAPI integration
        integrations=[
            sentry_sdk.integrations.fastapi.FastApiIntegration(),
            sentry_sdk.integrations.sqlalchemy.SqlalchemyIntegration(),
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
        "version": "2.0.0",
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
            "version": "2.0.0",
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
