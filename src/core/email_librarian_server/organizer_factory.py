"""
Factory for creating Gmail organizer instances.
"""

import logging
import sys
from typing import Dict, Any, Optional, Union, Protocol, cast, List
from pathlib import Path
from src.core.token_bucket import TokenBucket

logger = logging.getLogger(__name__)

# Define the protocol that Gmail organizers must follow
class GmailOrganizerProtocol(Protocol):
    """Protocol defining the required interface for Gmail organizers."""
    
    def authenticate(self) -> bool:
        """Authenticate with Gmail API."""
        ...
        
    def search_messages(self, query: str, max_results: int = 100) -> Dict[str, Any]:
        """Search Gmail messages by query."""
        ...
        
    def fetch_email(self, msg_id: str, format: str = "full") -> Dict[str, Any]:
        """Get a specific Gmail message by ID."""
        ...
        
    def create_label(self, label_name: str) -> Dict[str, Any]:
        """Create a new Gmail label."""
        ...
        
    def apply_label(self, msg_id: str, label_id: str) -> bool:
        """Apply a label to a message."""
        ...
    
    def list_labels(self) -> List[Dict[str, Any]]:
        """Return a list of labels (id/name/type) for the user."""
        ...


# Lightweight stub implementation for when real organizers aren't available
class OrganizerStub:
    """Stub implementation of the Gmail organizer interface."""
    
    def __init__(self):
        self.service = None
        self.labels = {}
        
    def authenticate(self) -> bool:
        logger.warning("Using stub Gmail organizer - authentication not available")
        return False
        
    def search_messages(self, query: str, max_results: int = 100) -> Dict[str, Any]:
        logger.warning("Using stub Gmail organizer - search not available")
        return {"status": "error", "messages": [], "message": "Gmail organizer not available"}
        
    def fetch_email(self, msg_id: str, format: str = "full") -> Dict[str, Any]:
        logger.warning("Using stub Gmail organizer - get message not available")
        return {"status": "error", "message": "Gmail organizer not available"}
        
    def create_label(self, label_name: str) -> Dict[str, Any]:
        logger.warning("Using stub Gmail organizer - label creation not available")
        return {"status": "error", "message": "Gmail organizer not available"}
        
    def apply_label(self, msg_id: str, label_id: str) -> bool:
        logger.warning("Using stub Gmail organizer - label application not available")
        return False

    def list_labels(self) -> List[Dict[str, Any]]:
        """Return an empty label list (safe stub)."""
        logger.warning("Using stub Gmail organizer - list_labels not available; returning empty list")
        return []


class OrganizerFactory:
    """Factory for creating Gmail organizer instances."""
    
    def __init__(self, credentials_path: str = 'config/credentials.json', token_path: str = 'data/gmail_token.pickle', limiter_rate: float = 1.0, limiter_capacity: int = 2):
        """
        Initialize the organizer factory.
        
        Args:
            credentials_path: Path to the Google API credentials JSON
            token_path: Path to the token pickle file
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        # Token bucket configuration for per-organizer rate limiting
        self.limiter_rate = float(limiter_rate)
        self.limiter_capacity = int(limiter_capacity)

        # Check if organizers are available
        try:
            sys.path.append('.')
            sys.path.append('./src/gmail')
            sys.path.append('./src/core')

            # Try to import the organizers
            from src.gmail.fast_gmail_organizer import AsyncHighPerformanceGmailOrganizer
            from src.gmail.gmail_organizer import GmailAIOrganizer
            self.high_performance_organizer = AsyncHighPerformanceGmailOrganizer
            self.standard_organizer = GmailAIOrganizer
            self.organizers_available = True
            logger.info("✅ Gmail organizers available")
        except ImportError as e:
            logger.warning(f"⚠️ Gmail organizers not available: {e}")
            self.high_performance_organizer = None
            self.standard_organizer = None
            self.organizers_available = False

        # Try to import container-compatible Gmail categories
        try:
            from container_gmail_categories import (
                ContainerGmailCategories,
                get_container_gmail_categories,
                get_container_batch_emails_with_fields,
                get_container_batch_emails_with_storage
            )
            self.container_gmail_categories = ContainerGmailCategories
            self.get_container_gmail_categories = get_container_gmail_categories
            self.get_container_batch_emails_with_fields = get_container_batch_emails_with_fields
            self.get_container_batch_emails_with_storage = get_container_batch_emails_with_storage
            self.container_gmail_available = True
            logger.info("✅ Container Gmail categories available")
        except ImportError as e:
            logger.warning(f"⚠️ Container Gmail categories not available: {e}")
            self.container_gmail_categories = None
            self.get_container_gmail_categories = None
            self.get_container_batch_emails_with_fields = None
            self.get_container_batch_emails_with_storage = None
            self.container_gmail_available = False
    
    def create_organizer(self, organizer_type: str = "high_performance", server: Any = None) -> Any:
        """
        Create a Gmail organizer instance.
        
        Args:
            organizer_type: Type of organizer to create ("high_performance" or "standard")
            
        Returns:
            Gmail organizer instance or stub if not available
        """
        if not self.organizers_available:
            logger.warning("Gmail organizers not available, returning stub")
            stub = OrganizerStub()
            if server is not None:
                try:
                    setattr(stub, "server", server)
                except Exception:
                    pass
            return stub
            
        if organizer_type == "high_performance" and self.high_performance_organizer:
            logger.info("Creating high performance Gmail organizer")
            org = self.high_performance_organizer(
                credentials_file=self.credentials_path,
                token_file=self.token_path
            )
            if server is not None:
                try:
                    setattr(org, "server", server)
                except Exception:
                    pass
            return org
       
        elif organizer_type == "standard" and self.standard_organizer:
            logger.info("Creating standard Gmail organizer")
            org = self.standard_organizer(
                credentials_file=self.credentials_path,
                token_file=self.token_path
            )
            if server is not None:
                try:
                    setattr(org, "server", server)
                except Exception:
                    pass
            return org
        else:
            logger.warning(f"Unknown organizer type '{organizer_type}', returning stub")
            stub = OrganizerStub()
            if server is not None:
                try:
                    setattr(stub, "server", server)
                except Exception:
                    pass
            return stub
