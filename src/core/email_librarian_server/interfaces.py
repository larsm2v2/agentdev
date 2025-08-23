"""
Core interfaces and protocols for the Enhanced Email Librarian system.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Protocol, Union


class EmailRetriever(Protocol):
    """Protocol defining the interface for email retrieval."""
    
    async def retrieve_emails(self, query: str, batch_size: int) -> Dict[str, Any]:
        """
        Retrieve emails based on query and batch size.
        
        Args:
            query: Gmail query string
            batch_size: Number of emails to retrieve
            
        Returns:
            Dict with status, emails list, and storage info
        """
        ...


class EmailClassifier(Protocol):
    """Protocol defining the interface for email classification."""
    
    async def classify_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify an email into categories.
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            Classification results
        """
        ...


class EmailLabeler(Protocol):
    """Protocol defining the interface for applying labels to emails."""
    
    async def apply_label(self, email_id: str, label: str) -> bool:
        """
        Apply a label to an email.
        
        Args:
            email_id: Gmail email ID
            label: Label to apply
            
        Returns:
            Success status
        """
        ...


class JobProcessor(ABC):
    """Base abstract class for job processors."""
    
    @abstractmethod
    async def process(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a job with given parameters.
        
        Args:
            job_id: Unique job identifier
            parameters: Job parameters
            
        Returns:
            Job results
        """
        pass


class BaseJobProcessor(JobProcessor):
    """Template method pattern implementation for job processing."""
    
    async def process(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Template method for job processing."""
        try:
            await self.update_job_status(job_id, "running")
            emails = await self.retrieve_emails(parameters)
            results = await self.process_emails(emails, parameters)
            await self.update_job_status(job_id, "completed", results)
            return results
        except Exception as e:
            await self.update_job_status(job_id, "failed", error_message=str(e))
            raise e
    
    @abstractmethod
    async def update_job_status(self, job_id: str, status: str, results: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        """Update job status in the database."""
        pass
    
    @abstractmethod
    async def retrieve_emails(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve emails based on job parameters."""
        pass
    
    @abstractmethod
    async def process_emails(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process the retrieved emails."""
        pass
