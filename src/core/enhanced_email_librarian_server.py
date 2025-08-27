#!/usr/bin/env python3
"""
Enhanced Email Librarian Backend Server
Enterprise-grade FastAPI server with n8n, Qdrant, PostgreSQL, LangFuse, and CrewAI integration
This version uses the refactored OOP implementation.
"""

import logging
import os
import sys

# Import the refactored implementation
from src.core.email_librarian_server.main import main

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

app = main()

# Main entry point
if __name__ == "__main__":
    try:
        logger.info("Starting Enhanced Email Librarian Server using refactored implementation")

        # Note: The server is started by the main() function, so we don't need to start it here
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)
