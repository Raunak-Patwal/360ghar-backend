import os
import logging
import uvicorn
from app.main import app

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
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info",
    )
