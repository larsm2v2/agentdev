"""
Main entry point for the Enhanced Email Librarian Server.
"""

import logging
import os
import sys
import uvicorn
from typing import Dict, Any

from .server import EnhancedEmailLibrarianServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/enhanced_email_librarian_server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_config() -> Dict[str, Any]:
    """
    Get server configuration from environment variables or defaults.
    
    Returns:
        Server configuration dictionary
    """
    return {
        "database_url": os.environ.get("EMAIL_LIBRARIAN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/email_librarian"),
        "qdrant_url": os.environ.get("EMAIL_LIBRARIAN_QDRANT_URL", "http://localhost:6333"),
        "token_path": os.environ.get("EMAIL_LIBRARIAN_TOKEN_PATH", "data/gmail_token.pickle"),
        "credentials_path": os.environ.get("EMAIL_LIBRARIAN_CREDENTIALS_PATH", "config/credentials.json"),
        "frontend_serving_mode": os.environ.get("EMAIL_LIBRARIAN_FRONTEND_MODE", "static"),
        "port": int(os.environ.get("EMAIL_LIBRARIAN_PORT", "8000")),
        "host": os.environ.get("EMAIL_LIBRARIAN_HOST", "0.0.0.0"),
        "environment": os.environ.get("EMAIL_LIBRARIAN_ENVIRONMENT", "development")
    }

def main():
    """Main entry point for the server."""
    try:
        # Get configuration
        config = get_config()
        
        # Create server
        server = EnhancedEmailLibrarianServer(config)
        
        # Create FastAPI app
        app = server.create_app()
        
        # Run server if this is the main module
        if __name__ == "__main__":
            logger.info(f"Starting server on {config['host']}:{config['port']}")
            uvicorn.run(app, host=config["host"], port=config["port"])
            
        return app
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)

app = main()

if __name__ == "__main__":
    # This block will only execute if running directly (not imported)
    pass
