"""
Message ID Retrieval Processor for the Enhanced Email Librarian system.

This module provides functionality to retrieve message IDs within a specific date range.
"""

import logging
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

# Import the necessary components
from ..interfaces import BaseJobProcessor
from ..organizer_factory import OrganizerFactory

# Define the EmailJobProcessor that we'll use
class EmailJobProcessor:
    """Core processing functions for email jobs."""
    
    def __init__(self, organizer_factory):
        self.organizer_factory = organizer_factory
        
    async def get_message_ids_in_range(self, start_timestamp, end_timestamp, max_ids=10000):
        """Get message IDs in the given time range."""
        logger.info(f"EmailJobProcessor.get_message_ids_in_range: start={start_timestamp}, end={end_timestamp}, max={max_ids}")
        
        try:
            organizer = self.organizer_factory.create_organizer()
            logger.info(f"EmailJobProcessor.get_message_ids_in_range: Created organizer: {type(organizer)}")
            
            # Create a Gmail query using epoch seconds
            query = f"after:{start_timestamp} before:{end_timestamp}"
            logger.info(f"EmailJobProcessor.get_message_ids_in_range: Query: {query}")
            
            # Try different methods available in the organizer
            if hasattr(organizer, "search_messages"):
                logger.info(f"EmailJobProcessor.get_message_ids_in_range: Calling search_messages")
                results = organizer.search_messages(query=query, max_results=max_ids)
                if asyncio.iscoroutine(results):
                    logger.info(f"EmailJobProcessor.get_message_ids_in_range: Awaiting coroutine result")
                    results = await results
                logger.info(f"EmailJobProcessor.get_message_ids_in_range: Retrieved {len(results) if results else 0} message IDs")
                return results
            
            # Try the users().messages().list method via the service attribute
            elif hasattr(organizer, "service"):
                logger.info(f"EmailJobProcessor.get_message_ids_in_range: Using service.users().messages().list")
                try:
                    results = organizer.service.users().messages().list(
                        userId='me',
                        q=query,
                        maxResults=max_ids
                    ).execute()
                    
                    messages = results.get('messages', [])
                    message_ids = [msg['id'] for msg in messages]
                    logger.info(f"EmailJobProcessor.get_message_ids_in_range: Retrieved {len(message_ids)} message IDs")
                    return message_ids
                except Exception as e:
                    logger.error(f"❌ EmailJobProcessor.get_message_ids_in_range: Error using service: {e}")
            
            else:
                logger.warning(f"❌ EmailJobProcessor.get_message_ids_in_range: Organizer {type(organizer)} does not have search_messages method or service attribute")
            
            return []
        except Exception as e:
            logger.error(f"❌ EmailJobProcessor.get_message_ids_in_range: Error: {e}", exc_info=True)
            raise
    
    def batch_message_ids(self, message_ids, chunk_size=10):
        """Split message IDs into batches."""
        result = []
        for i in range(0, len(message_ids), chunk_size):
            result.append(message_ids[i:i + chunk_size])
        return result
        
        async def get_message_ids_in_range(self, start_timestamp, end_timestamp, max_ids=10000):
            """Get message IDs in the given time range."""
            organizer = self.organizer_factory.create_organizer()
            
            # Create a Gmail query using epoch seconds
            query = f"after:{start_timestamp} before:{end_timestamp}"
            
            # Try organizer methods
            if hasattr(organizer, "search_messages"):
                results = organizer.search_messages(query=query, max_results=max_ids)
                if asyncio.iscoroutine(results):
                    results = await results
                return results
            
            return []
        
        def batch_message_ids(self, message_ids, chunk_size=10):
            """Split message IDs into batches."""
            result = []
            for i in range(0, len(message_ids), chunk_size):
                result.append(message_ids[i:i + chunk_size])
            return result

logger = logging.getLogger(__name__)


class MessageIDRetrievalProcessor(BaseJobProcessor):
    """Processor for retrieving message IDs within a date range."""
    
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
        """Process a message ID retrieval job.
        
        Args:
            job_id: Job identifier
            parameters: Job parameters including date range
            
        Returns:
            Job results including message IDs
        """
        logger.info(f"⚡ MessageIDRetrievalProcessor.process: Starting message ID retrieval job {job_id}")
        logger.info(f"MessageIDRetrievalProcessor.process: Parameters: {parameters}")
        
        try:
            # Update job status to running
            await self.update_job_status(job_id, "running")
            
            # Extract and validate parameters
            start_date = parameters.get("start_date") or parameters.get("startDate")
            end_date = parameters.get("end_date") or parameters.get("endDate")
            max_ids = parameters.get("max_ids") or parameters.get("max_emails") or 10000
            batch_size = parameters.get("batch_size") or 100
            
            logger.info(f"MessageIDRetrievalProcessor.process: Extracted parameters: start_date={start_date}, end_date={end_date}, max_ids={max_ids}, batch_size={batch_size}")
            
            if not start_date or not end_date:
                error_msg = "Missing required parameters: start_date and end_date"
                logger.error(f"❌ MessageIDRetrievalProcessor.process: {error_msg}")
                results = {"status": "failed", "message": error_msg, "job_id": job_id}
                await self.update_job_status(job_id, "failed", None, error_msg)
                return results
            
            # Convert dates to timestamps
            try:
                start_ts = self._parse_date_to_timestamp(start_date)
                end_ts = self._parse_date_to_timestamp(end_date)
            except ValueError as e:
                error_msg = f"Invalid date format: {str(e)}"
                results = {"status": "failed", "message": error_msg, "job_id": job_id}
                await self.update_job_status(job_id, "failed", None, error_msg)
                return results
            
            # Get message IDs
            progress_results = {"message": "Retrieving message IDs from Gmail", "job_id": job_id}
            await self.update_job_status(job_id, "running", progress_results)
            
            logger.info(f"⏳ MessageIDRetrievalProcessor.process: Retrieving message IDs in range {start_date} to {end_date} (ts: {start_ts} to {end_ts})")
            try:
                message_ids = await self.email_processor.get_message_ids_in_range(
                    start_timestamp=start_ts,
                    end_timestamp=end_ts,
                    max_ids=max_ids
                )
                logger.info(f"✅ MessageIDRetrievalProcessor.process: Retrieved {len(message_ids)} message IDs")
            except Exception as e:
                logger.error(f"❌ MessageIDRetrievalProcessor.process: Failed to get message IDs: {e}", exc_info=True)
                raise
            
            # Create batches if requested
            if batch_size and batch_size > 0:
                batches = self.email_processor.batch_message_ids(message_ids, batch_size)
            else:
                batches = [message_ids]
            
            # Create success results and include message IDs before persisting so
            # downstream callers (which read job status) will see the list.
            success_msg = f"Retrieved {len(message_ids)} message IDs in {len(batches)} batches"
            results = {
                "status": "completed",
                "message": success_msg,
                "job_id": job_id,
                "processed_count": len(message_ids),
                "total_count": len(message_ids),
                "job_type": "message_id_retrieval",
                "message_ids": message_ids,
                "batches": batches,
                "batch_count": len(batches),
                "message_count": len(message_ids),
                "parameters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "batch_size": batch_size
                }
            }

            # Persist the full results (including message_ids) so get_job_status
            # will expose them to callers that poll job status.
            await self.update_job_status(job_id, "completed", results)

            # Return results
            return results
            
        except Exception as e:
            error_msg = f"Error retrieving message IDs: {str(e)}"
            logger.exception(error_msg)
            
            results = {
                "status": "failed",
                "message": error_msg,
                "job_id": job_id,
                "job_type": "message_id_retrieval",
                "parameters": parameters
            }
            
            await self.update_job_status(job_id, "failed", None, error_msg)
            return results
    
    async def update_job_status(self, job_id: str, status: str, results: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        """Update job status in the job manager.
        
        Args:
            job_id: Job identifier
            status: New status
            results: Job results dictionary
            error_message: Error message if job failed
        """
        # Get the message for logging only
        if error_message is not None and status == "failed":
            message = error_message
        elif results and isinstance(results.get("message"), str):
            message = results.get("message")
        else:
            message = None
            
        # Create a minimal metadata dict with only the status
        metadata = {"status": status}
        
        if self.job_manager and hasattr(self.job_manager, "update_job_status"):
            try:
                # Pass a structured results dict so JobManager can persist a valid
                # JSON object. Avoid passing positional string message that was
                # previously misinterpreted as the results payload.
                payload = {"status": status}
                if message:
                    payload["message"] = message
                if metadata:
                    # Ensure metadata is a dict before merging
                    existing_meta = payload.get("metadata")
                    if not isinstance(existing_meta, dict):
                        existing_meta = {}
                    try:
                        existing_meta.update(metadata)
                    except Exception:
                        # Fallback: store stringified metadata
                        existing_meta = {"raw": str(metadata)}
                    payload["metadata"] = str(existing_meta)
                await self.job_manager.update_job_status(job_id, status, results=payload)
            except Exception as e:
                logger.warning(f"Failed to update job status: {e}")
        else:
            logger.debug(f"Job status update [no job manager]: {job_id} -> {status}: {message}")
    
    async def retrieve_emails(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Retrieve emails based on job parameters.
        This is a required abstract method that we're not using in this processor.
        
        Args:
            parameters: Job parameters
            
        Returns:
            Empty list - we're not processing emails in this job
        """
        return []
        
    async def process_emails(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a batch of emails with parameters.
        This is a required abstract method that we're not using in this processor.
        
        Args:
            emails: List of email data
            parameters: Job parameters
            
        Returns:
            Empty results - we're not processing emails in this job
        """
        return {"processed": 0, "status": "not_implemented"}
        
    def _parse_date_to_timestamp(self, date_value) -> int:
        """Parse a date value to a Unix timestamp.
        
        Args:
            date_value: Date in various formats
            
        Returns:
            Unix timestamp as integer
        """
        # Numeric types
        if isinstance(date_value, (int, float)):
            return int(date_value)
        
        # String values
        if isinstance(date_value, str):
            s = date_value.strip()
            
            # Try numeric epoch string
            try:
                if "." in s:
                    return int(float(s))
                return int(s)
            except Exception:
                pass
            
            # Try common date formats
            for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", 
                       "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", 
                       "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    dt = datetime.strptime(s, fmt)
                    return int(dt.replace(tzinfo=timezone.utc).timestamp())
                except Exception:
                    continue
                    
            # Try ISO parsing
            try:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp())
            except Exception:
                pass
                
        # Invalid format
        raise ValueError(f"Invalid date format: {date_value}. Use YYYY/MM/DD, ISO, or epoch seconds")
