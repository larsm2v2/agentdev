"""
Message ID Batch Processor for the Enhanced Email Librarian system.

This module provides functionality to batch message IDs for processing.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional

# Import the necessary components
from ..interfaces import BaseJobProcessor
from .message_id_processor import EmailJobProcessor

logger = logging.getLogger(__name__)

class MessageIDBatchProcessor(BaseJobProcessor):
    """Job processor for batching message IDs."""
    
    def __init__(self, database=None, organizer_factory=None, job_manager=None, storage_manager=None):
        """Initialize the processor.
        
        Args:
            database: Database connection
            organizer_factory: Factory for creating organizers
            job_manager: Job manager instance
            storage_manager: Storage manager instance
        """
        super().__init__()
        self.database = database
        self.job_manager = job_manager
        self.organizer_factory = organizer_factory
        self.storage_manager = storage_manager
        
        # Only create EmailJobProcessor if we have an organizer factory
        if organizer_factory:
            self.email_processor = EmailJobProcessor(organizer_factory)
    
    async def process(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process a message ID batch job.
        
        Args:
            job_id: Job identifier
            parameters: Job parameters including message IDs and batch size
            
        Returns:
            Dict with results including batches and statistics
        """
        logger.info(f"Starting message ID batch job {job_id}")
        
        try:
            # Update job status to running
            status_update = {"message": "Batching message IDs"}
            await self.update_job_status(job_id, "running", status_update)
            
            # Check for required parameters
            message_ids = parameters.get('message_ids')
            batch_size = parameters.get('batch_size', 10)
            
            if not message_ids:
                error_msg = "Missing required parameter: message_ids is required"
                await self.update_job_status(job_id, "failed", None, error_msg)
                return {"status": "failed", "message": error_msg}
            
            # Update status with more details
            status_update = {"message": "Creating message ID batches", "job_id": job_id}
            await self.update_job_status(job_id, "running", status_update)
            
            # Create batches
            try:
                batches = self.email_processor.batch_message_ids(message_ids, batch_size)
                
                # Create success message and results
                success_msg = f"Created {len(batches)} batches from {len(message_ids)} message IDs"
                results = {
                    "status": "completed",
                    "message": success_msg,
                    "job_id": job_id,
                    "batches": batches,
                    "batch_count": len(batches),
                    "message_count": len(message_ids),
                    "batch_size": batch_size
                }
                
                # Update job status
                await self.update_job_status(job_id, "completed", results)
                
                # Return results
                return results
                
            except Exception as e:
                error_msg = f"Error creating message ID batches: {str(e)}"
                logger.error(error_msg)
                await self.update_job_status(job_id, "failed", None, error_msg)
                return {"status": "failed", "message": error_msg}
                
        except Exception as e:
            error_msg = f"Error in message ID batch job: {str(e)}"
            logger.error(error_msg)
            await self.update_job_status(job_id, "failed", None, error_msg)
            return {"status": "failed", "message": error_msg}
    
    async def update_job_status(self, job_id: str, status: str, results: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        """Update job status in the job manager."""
        try:
            if self.job_manager and hasattr(self.job_manager, 'update_job_status'):
                await self.job_manager.update_job_status(job_id, status, results, error_message)
        except Exception as e:
            logger.warning(f"Failed to update job status: {e}")
    
    async def retrieve_emails(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Not used but required by base class."""
        return []
        
    async def process_emails(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Not used but required by base class."""
        return {}
