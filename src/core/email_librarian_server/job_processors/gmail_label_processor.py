"""
Gmail Label Processor for the Enhanced Email Librarian system.

This module provides functionality to apply labels to Gmail messages.
"""

import logging
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import the necessary components
from ..interfaces import BaseJobProcessor
from .job_processors import EmailJobProcessor

logger = logging.getLogger(__name__)

class GmailLabelProcessor(BaseJobProcessor):
    """Job processor for applying labels to Gmail messages."""
    
    def __init__(self, database=None, organizer_factory=None, job_manager=None, storage_manager=None):
        """Initialize the processor.
        
        Args:
            database: Database connection
            organizer_factory: Factory for creating organizers
            job_manager: Job manager instance
            storage_manager: Storage manager instance
        """
        self.database = database
        self.organizer_factory = organizer_factory
        self.job_manager = job_manager
        self.storage_manager = storage_manager
        self.email_processor = EmailJobProcessor(organizer_factory) if organizer_factory else None
    
    async def process(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process a labeling job.
        
        Args:
            job_id: Unique job identifier
            parameters: Job parameters including:
                - message_ids: List of message IDs to apply labels to
                - label_info: Label information (name, description, etc.)
                - label_mapping: Mapping of message IDs to label names
            
        Returns:
            Job results
        """
        try:
            # Update status to running
            logger.info(f"GmailLabelProcessor: Starting label application job {job_id}")
            await self.update_job_status(job_id, "running")
            
            # Get message IDs from parameters
            message_ids = parameters.get("message_ids", [])
            label_mapping = parameters.get("label_mapping", {})
            default_label = parameters.get("default_label")
            
            # Validate required parameters
            if not message_ids and not label_mapping:
                error_message = "No message IDs or label mapping provided"
                logger.error(f"GmailLabelProcessor: {error_message}")
                await self.update_job_status(job_id, "failed", error_message=error_message)
                return {"status": "failed", "error": error_message}
            
            # Create organizer for Gmail operations
            organizer = self.organizer_factory.create_organizer("high_performance") if self.organizer_factory else None
            
            # Apply labels based on the provided mapping
            results = await self.apply_labels_to_emails(
                message_ids=message_ids, 
                label_mapping=label_mapping,
                default_label=default_label,
                organizer=organizer,
                job_id=job_id
            )
            
            # Prepare success results
            success_count = sum(1 for r in results if r.get("success", False))
            total_count = len(results)
            
            job_results = {
                "processed_count": total_count,
                "labeled_count": success_count,
                "job_type": "gmail_labeling",
                "status": "completed",
                "message": f"Successfully labeled {success_count} of {total_count} emails"
            }
            
            # Mark as completed
            await self.update_job_status(job_id, "completed", job_results)
            logger.info(f"GmailLabelProcessor: Successfully labeled {success_count} of {total_count} emails")
            return job_results
            
        except Exception as e:
            logger.error(f"Gmail labeling job {job_id} failed: {e}")
            await self.update_job_status(job_id, "failed", error_message=str(e))
            raise e
    
    async def update_job_status(self, job_id: str, status: str, results: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        """
        Update job status in the database.
        
        Args:
            job_id: Job identifier
            status: New status
            results: Optional job results
            error_message: Optional error message
        """
        if not self.database:
            logger.warning(f"No database connection - cannot update job {job_id} status to {status}")
            return
            
        query = """
        UPDATE email_processing_jobs 
        SET status = :status, 
            updated_at = :updated_at
        """
        values = {
            "id": job_id,
            "status": status,
            "updated_at": datetime.now()
        }
        
        if results or error_message:
            query += ", results = :results"
            if results:
                values["results"] = json.dumps(results)
            elif error_message:
                values["results"] = json.dumps({"error": error_message})
                
        query += " WHERE id = :id"
        
        await self.database.execute(query, values)
        
    async def retrieve_emails(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Retrieve emails based on job parameters.
        
        Args:
            parameters: Job parameters
            
        Returns:
            List of emails
        """
        # Since we're applying labels to existing emails or message IDs,
        # we might not need to retrieve full emails in this processor
        message_ids = parameters.get("message_ids", [])
        if message_ids:
            # For label application, we can work with minimal email representations
            return [{"id": mid, "message_id": mid} for mid in message_ids]
        
        # If message IDs aren't directly provided, check if we have existing emails
        emails = parameters.get("emails", [])
        if emails:
            return emails
            
        # If neither is provided, try to retrieve emails based on other criteria
        if self.email_processor:
            # Extract time range if available
            start_timestamp = parameters.get("start_timestamp")
            end_timestamp = parameters.get("end_timestamp")
            
            if start_timestamp and end_timestamp:
                try:
                    # Get message IDs in date range
                    ids = await self.email_processor.get_message_ids_in_range(
                        start_timestamp=start_timestamp,
                        end_timestamp=end_timestamp,
                        max_ids=parameters.get("max_ids", 1000)
                    )
                    # Return minimal representations
                    return [{"id": mid, "message_id": mid} for mid in ids]
                except Exception as e:
                    logger.error(f"Failed to retrieve message IDs in range: {e}")
        
        # If we couldn't retrieve emails, return an empty list
        return []
    
    async def process_emails(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process emails with label application.
        
        Args:
            emails: List of email data
            parameters: Job parameters
            
        Returns:
            Processing results
        """
        # Extract message IDs from emails
        message_ids = [str(email.get("id") or email.get("message_id")) for email in emails if email.get("id") or email.get("message_id")]
        
        # Get label mapping from parameters
        label_mapping = parameters.get("label_mapping", {})
        default_label = parameters.get("default_label")
        
        # Create organizer
        organizer = self.organizer_factory.create_organizer("high_performance") if self.organizer_factory else None
        
        # Apply labels based on the mapping
        results = await self.apply_labels_to_emails(
            message_ids=message_ids,
            label_mapping=label_mapping,
            default_label=default_label,
            organizer=organizer
        )
        
        # Count successes
        success_count = sum(1 for r in results if r.get("success", False))
        
        return {
            "processed_count": len(message_ids),
            "labeled_count": success_count,
            "job_type": "gmail_labeling",
            "status": "completed",
            "message": f"Successfully labeled {success_count} of {len(message_ids)} emails"
        }
        
    async def apply_labels_to_emails(self, message_ids: List[str], label_mapping: Optional[Dict[str, str]] = None,
                                   default_label: Optional[str] = None, organizer = None, job_id: Optional[str] = None) -> List[Dict]:
        """
        Apply labels to emails based on mapping or default label.
        
        Args:
            message_ids: List of message IDs
            label_mapping: Optional mapping of message IDs to label names
            default_label: Optional default label to apply if no mapping exists
            organizer: Optional organizer (will create one if not provided)
            job_id: Optional job ID for progress tracking
            
        Returns:
            List of results with success/failure status
        """
        if not organizer and self.organizer_factory:
            organizer = self.organizer_factory.create_organizer("high_performance")
            
        if not organizer:
            logger.error("No organizer available for label application")
            return [{"success": False, "error": "No organizer available"}]
        
        results = []
        total_count = len(message_ids)
        
        # Process in parallel with rate limiting
        sem = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
        
        async def apply_label(email_id, label_name):
            async with sem:
                if not email_id or not label_name:
                    return {
                        "id": email_id or "unknown",
                        "label": label_name or "unknown",
                        "success": False,
                        "error": "Missing email ID or label name"
                    }
                
                try:
                    # First create the label if it doesn't exist
                    label_result = organizer.create_label(label_name)
                    if asyncio.iscoroutine(label_result):
                        label_result = await label_result
                    
                    if not label_result:
                        return {
                            "id": email_id,
                            "label": label_name,
                            "success": False,
                            "error": "Failed to create label"
                        }
                    
                    # Handle different response formats
                    label_id = None
                    if isinstance(label_result, dict):
                        if label_result.get("status") == "success":
                            label_id = label_result.get("label", {}).get("id")
                        else:
                            return {
                                "id": email_id,
                                "label": label_name,
                                "success": False,
                                "error": f"Failed to create label: {label_result.get('error', 'Unknown error')}"
                            }
                    else:
                        # Try to extract label ID directly
                        try:
                            if hasattr(label_result, "id"):
                                label_id = label_result.id
                            elif hasattr(label_result, "label_id"):
                                label_id = label_result.label_id
                        except Exception:
                            pass
                    
                    if not label_id:
                        return {
                            "id": email_id,
                            "label": label_name,
                            "success": False,
                            "error": "No label ID returned"
                        }
                    
                    # Apply the label
                    apply_result = organizer.apply_label(email_id, label_id)
                    if asyncio.iscoroutine(apply_result):
                        apply_result = await apply_result
                    
                    if not apply_result:
                        return {
                            "id": email_id,
                            "label": label_name,
                            "success": False,
                            "error": "Failed to apply label"
                        }
                    
                    return {
                        "id": email_id,
                        "label": label_name,
                        "success": True,
                        "label_id": label_id
                    }
                except Exception as e:
                    logger.error(f"Error applying label: {e}")
                    return {
                        "id": email_id,
                        "label": label_name,
                        "success": False,
                        "error": str(e)
                    }
        
        # Prepare tasks for label application
        tasks = []
        processed_count = 0
        
        for email_id in message_ids:
            # Determine which label to apply
            label_to_apply = None
            
            # Check mapping first
            if label_mapping and email_id in label_mapping:
                label_to_apply = label_mapping[email_id]
            # Fall back to default label
            elif default_label:
                label_to_apply = default_label
            
            if label_to_apply:
                tasks.append(apply_label(email_id, label_to_apply))
            
            # Update progress periodically
            processed_count += 1
            if self.job_manager and job_id and processed_count % 10 == 0:
                progress = min(100, int((processed_count / total_count) * 100)) if total_count else 100
                await self.job_manager.update_job_progress(job_id, progress)
        
        # Apply labels concurrently
        results = await asyncio.gather(*tasks)
        
        # Final progress update
        if self.job_manager and job_id:
            await self.job_manager.update_job_progress(job_id, 100)
            
        return results
