"""
Email Batch Retrieval Processor for the Enhanced Email Librarian system.

This module provides functionality to retrieve email batches with raw content and labels.
"""

import logging
import asyncio
import json
import ast
from typing import Dict, List, Any, Optional
from email import message_from_bytes, policy

# Import the necessary components
from ..interfaces import BaseJobProcessor
from .message_id_processor import EmailJobProcessor

logger = logging.getLogger(__name__)

class EmailBatchRetrievalProcessor(BaseJobProcessor):
    """Job processor for retrieving email batches with raw content and labels."""
    
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
    
    async def process(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process an email batch retrieval job.
        
        Args:
            job_id: Job identifier
            parameters: Job parameters including message IDs, batch size
            
        Returns:
            Dict with results including batches of emails with content and labels
        """
        logger.info(f"Starting email batch retrieval job {job_id}")
        
        try:
            # Update job status to running
            status_update = {"message": "Retrieving email batches"}
            await self.update_job_status(job_id, "running", status_update)
            
            # Extract parameters
            payload = parameters
            
            # Normalize incoming payload
            if not isinstance(payload, dict):
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        try:
                            payload = ast.literal_eval(payload)
                        except Exception:
                            error_msg = "Request body must be a JSON object"
                            await self.update_job_status(job_id, "failed", None, error_msg)
                            return {"status": "failed", "message": error_msg}
                else:
                    error_msg = "Request body must be a JSON object"
                    await self.update_job_status(job_id, "failed", None, error_msg)
                    return {"status": "failed", "message": error_msg}

            # Support wrapper with 'input'
            raw_input = payload.get("input")
            if isinstance(raw_input, str):
                try:
                    payload = json.loads(raw_input)
                except Exception:
                    try:
                        payload = ast.literal_eval(raw_input)
                    except Exception:
                        error_msg = "Input field must contain valid JSON"
                        await self.update_job_status(job_id, "failed", None, error_msg)
                        return {"status": "failed", "message": error_msg}

            # Extract batches / chunk_size / count
            batches_raw = payload.get("batches") or payload.get("batched_message_ids") or payload.get("message_ids")
            chunk_size = payload.get("chunk_size")
            count = payload.get("count")
            include_labels = payload.get("include_labels", True)  # Default to including labels

            if batches_raw is None:
                error_msg = "Payload must include 'batches' or 'batched_message_ids'"
                await self.update_job_status(job_id, "failed", None, error_msg)
                return {"status": "failed", "message": error_msg}

            # Allow stringified batches
            if isinstance(batches_raw, str):
                try:
                    batches_raw = json.loads(batches_raw)
                except Exception:
                    try:
                        batches_raw = ast.literal_eval(batches_raw)
                    except Exception:
                        error_msg = "Batches must be a list or a stringified list"
                        await self.update_job_status(job_id, "failed", None, error_msg)
                        return {"status": "failed", "message": error_msg}

            # Update status with more details
            status_update = {"message": "Processing batches", "job_id": job_id}
            await self.update_job_status(job_id, "running", status_update)

            # Normalize to list[list[str]]
            if isinstance(batches_raw, list) and batches_raw and not any(isinstance(i, list) for i in batches_raw):
                batches = [[str(i) for i in batches_raw if i]]
            else:
                if not isinstance(batches_raw, list):
                    error_msg = "Batches must be a list of lists"
                    await self.update_job_status(job_id, "failed", None, error_msg)
                    return {"status": "failed", "message": error_msg}
                    
                batches = []
                for b in batches_raw:
                    if not isinstance(b, list):
                        error_msg = "Each batch must be a list of message IDs"
                        await self.update_job_status(job_id, "failed", None, error_msg)
                        return {"status": "failed", "message": error_msg}
                        
                    clean = [str(x) for x in b if x]
                    if clean:
                        batches.append(clean)

            try:
                chunk_size = None if chunk_size is None else int(chunk_size)
            except Exception:
                error_msg = "Chunk_size must be an integer if provided"
                await self.update_job_status(job_id, "failed", None, error_msg)
                return {"status": "failed", "message": error_msg}

            # Create organizer
            if not self.organizer_factory:
                error_msg = "Organizer factory is not available"
                await self.update_job_status(job_id, "failed", None, error_msg)
                return {"status": "failed", "message": error_msg}
                
            organizer = self.organizer_factory.create_organizer()

            if not hasattr(organizer, "fetch_email"):
                # Return batches of IDs when fetch not available
                result = {
                    "status": "completed",
                    "message": "Fetch not available, returning ID batches only",
                    "requested": count or sum(len(b) for b in batches),
                    "returned": sum(len(b) for b in batches),
                    "batches": batches
                }
                await self.update_job_status(job_id, "completed", result)
                return result

            # Use a semaphore for bounded concurrency
            async def _fetch_email_with_labels(mid: str, include_labels: bool = True):
                """Fetch an email with its content and optionally labels."""
                try:
                    # Fetch email content
                    out = organizer.fetch_email(mid)
                    res = await out if asyncio.iscoroutine(out) else out
                    
                    # Extract data
                    email_data = {}
                    
                    if isinstance(res, dict):
                        email_data = res.get("data") or res
                    else:
                        # Convert object to dict
                        try:
                            email_data = {
                                "message_id": mid,
                                "sender": getattr(res, "sender", "") or getattr(res, "from", "") or "",
                                "subject": getattr(res, "subject", "") or "",
                                "raw": getattr(res, "raw", None) or getattr(res, "raw_body", None)
                            }
                        except Exception as e:
                            logger.warning(f"Error converting email object to dict: {e}")
                            email_data = {"message_id": mid, "error": str(e)}
                    
                    # Ensure message_id is included
                    if "message_id" not in email_data:
                        email_data["message_id"] = mid
                    
                    # Fetch labels if requested
                    if include_labels:
                        if hasattr(organizer, "get_message_labels"):
                            try:
                                labels_result = organizer.get_message_labels(mid)
                                if asyncio.iscoroutine(labels_result):
                                    labels = await labels_result
                                else:
                                    labels = labels_result
                                    
                                # Add labels to email_data
                                email_data["labels"] = labels
                            except Exception as e:
                                logger.warning(f"Error fetching labels for message {mid}: {e}")
                                email_data["labels_error"] = str(e)
                        else:
                            logger.info("Organizer does not implement get_message_labels")
                            
                    return email_data
                    
                except Exception as e:
                    logger.warning(f"Error fetching email {mid}: {e}")
                    return {"message_id": mid, "error": str(e)}
            
            # Process batches
            output_batches = []
            total_requested = 0
            total_returned = 0
            
            for batch_index, batch in enumerate(batches):
                # Update progress
                progress_update = {
                    "message": f"Processing batch {batch_index + 1} of {len(batches)}",
                    "processed_count": batch_index,
                    "total_count": len(batches)
                }
                await self.update_job_status(job_id, "running", progress_update)
                
                ids = [str(mid) for mid in batch if mid]
                if not ids:
                    output_batches.append([])
                    continue
                
                # Apply chunk size if specified
                to_fetch = ids if not chunk_size or chunk_size <= 0 else ids[:int(chunk_size)]
                total_requested += len(to_fetch)
                
                # Use semaphore for bounded concurrency
                sem = asyncio.Semaphore(min(10, max(1, len(to_fetch))))
                
                async def _bounded_fetch(mid):
                    async with sem:
                        return await _fetch_email_with_labels(mid, include_labels)
                
                # Process batch with concurrency
                tasks = [_bounded_fetch(mid) for mid in to_fetch]
                results = await asyncio.gather(*tasks)
                
                # Filter out None results
                batch_results = [r for r in results if r is not None]
                total_returned += len(batch_results)
                output_batches.append(batch_results)
            
            # Create success response
            result = {
                "status": "completed",
                "message": f"Successfully retrieved {total_returned} emails from {total_requested} requested",
                "job_id": job_id,
                "requested": count or total_requested,
                "returned": total_returned,
                "batches": output_batches,
                "include_labels": include_labels
            }
            
            # Update job status
            await self.update_job_status(job_id, "completed", result)
            
            return result
            
        except Exception as e:
            error_msg = f"Error in email batch retrieval job: {str(e)}"
            logger.error(error_msg, exc_info=True)
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
