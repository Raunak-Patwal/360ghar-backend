import os
import logging
import uvicorn
from app.main import app

from dotenv import load_dotenv
load_dotenv()

# Set up basic logging before uvicorn takes over
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    port_str = os.getenv("PORT", "8000")

    logger.info(f"Starting Container - PORT: {port_str}")
    
    # Handle Railway's PORT environment variable properly
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        logger.warning(f"Invalid PORT value '{port_str}', falling back to 8000")
        port = 8000

    environment = os.getenv("ENVIRONMENT", "development")
    reload = environment == "development"

    # Build uvicorn options with safe feature detection
    uvicorn_kwargs = {
        "host": "0.0.0.0",
        "port": port,
        "reload": reload,
        "log_level": "info",
        "use_colors": True,
        # Keep workers=1 to avoid reload conflicts; uvicorn enforces it with reload anyway
        "workers": 1,
    }

    if reload:
        uvicorn_kwargs["reload_dirs"] = ["app"]

    # Prefer uvloop when available and not on Windows
    if os.name != "nt":
        try:
            import uvloop  # noqa: F401
            uvicorn_kwargs["loop"] = "uvloop"
        except Exception:
            logger.info("uvloop not available; using default asyncio loop")

    # Prefer httptools HTTP parser when available
    try:
        import httptools  # noqa: F401
        uvicorn_kwargs["http"] = "httptools"
    except Exception:
        logger.info("httptools not available; using default http implementation")

    # Configure uvicorn with better reload settings
    uvicorn.run("app.main:app", **uvicorn_kwargs)
