"""
Main entry point for the Enhanced Email Librarian Server.
"""

import logging
import os
import sys
import uvicorn
from typing import Dict, Any

from .storage_manager import StorageManager
from .auth_manager import GmailAuthManager
from .organizer_factory import OrganizerFactory
from .job_manager import JobManager
from .job_processors import ShelvingJobProcessor, CatalogingJobProcessor
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
    # Get database URL from environment variables
    database_url = os.environ.get(
        "EMAIL_LIBRARIAN_DATABASE_URL", 
        os.environ.get("DATABASE_URL", "postgresql://librarian_user:secure_password_2024@postgres:5432/email_librarian")
    )
    
    # Build Qdrant URL from host/port or use default
    qdrant_host = os.environ.get("QDRANT_HOST", "qdrant")
    qdrant_port = os.environ.get("QDRANT_PORT", "6333")
    qdrant_url = os.environ.get("EMAIL_LIBRARIAN_QDRANT_URL", f"http://{qdrant_host}:{qdrant_port}")
    
    return {
        "database_url": database_url,
        "qdrant_url": qdrant_url,
        "redis_url": os.environ.get("REDIS_URL", "redis://:redis_password_2024@redis:6379/0"),
        "token_path": os.environ.get("GMAIL_TOKEN_PATH", "data/gmail_token.pickle"),
        "credentials_path": os.environ.get("GMAIL_CREDENTIALS_PATH", "config/credentials.json"),
        "frontend_serving_mode": os.environ.get("FRONTEND_MODE", "static"),
        "port": int(os.environ.get("PORT", "8000")),
        "host": os.environ.get("HOST", "0.0.0.0"),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "log_level": os.environ.get("LOG_LEVEL", "INFO")
    }

async def initialize_services(storage_manager, config):
    """Initialize storage manager with retries."""
    success = await storage_manager.initialize()
    if not success:
        logger.error("Failed to initialize storage manager")
        return False
    return True

def main():
    """Main entry point for the server."""
    try:
        # Get configuration
        config = get_config()

        # Initialize components
        auth_manager = GmailAuthManager()
        storage_manager = StorageManager(
            database_url=config["database_url"],
            qdrant_url=config["qdrant_url"]
        )
        organizer_factory = OrganizerFactory(config["credentials_path"])
        job_manager = JobManager(storage_manager, organizer_factory)
        
        # Initialize job processors with job_manager reference
        shelving_processor = ShelvingJobProcessor(
            database=storage_manager.database,
            organizer_factory=organizer_factory,
            job_manager=job_manager
        )
        
        cataloging_processor = CatalogingJobProcessor(
            database=storage_manager.database,
            organizer_factory=organizer_factory,
            job_manager=job_manager
        )
        
            # Register processors with job manager
        job_manager.register_processor("shelving", shelving_processor)
        job_manager.register_processor("cataloging", cataloging_processor)
        
        # Create server
        server = EnhancedEmailLibrarianServer(config)
        server.auth_manager = auth_manager
        server.storage_manager = storage_manager
        server.organizer_factory = organizer_factory
        server.job_manager = job_manager

        # Register processors with job manager
        job_manager.register_processor("shelving", shelving_processor)
        job_manager.register_processor("cataloging", cataloging_processor)
                
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
