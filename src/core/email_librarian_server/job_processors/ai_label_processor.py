"""
AI Label Assignment Processor for the Enhanced Email Librarian system.

This module provides functionality to bulk assign labels to emails using AI.
"""

import logging
import asyncio
import json
from typing import Dict, List, Any, Optional
import os
from datetime import datetime

# Import the necessary components
from ..interfaces import BaseJobProcessor
from .job_processors import EmailJobProcessor

logger = logging.getLogger(__name__)

class AILabelAssignmentProcessor(BaseJobProcessor):
    """Job processor for bulk assigning labels to emails using AI."""
    
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
        self.email_processor = None
        if organizer_factory:
            self.email_processor = EmailJobProcessor(organizer_factory)
    
    async def process(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process an AI label assignment job.
        
        Args:
            job_id: Job identifier
            parameters: Job parameters including message IDs or email data
            
        Returns:
            Dict with results including labeled emails
        """
        logger.info(f"Starting AI label assignment job {job_id}")
        
        try:
            # Check if we have the necessary components
            if not self.organizer_factory:
                error_msg = "Organizer factory is required for AI label assignment"
                await self.update_job_status(job_id, "failed", None, error_msg)
                return {"status": "failed", "message": error_msg}
                
            if not self.email_processor:
                self.email_processor = EmailJobProcessor(self.organizer_factory)
            
            # Update job status to running
            status_update = {"message": "Starting AI label assignment"}
            await self.update_job_status(job_id, "running", status_update)
            
            # Extract parameters
            message_ids = parameters.get("message_ids", [])
            email_data = parameters.get("emails", [])
            include_raw = parameters.get("include_raw", True)
            max_body_length = parameters.get("max_body_length", 400)
            custom_categories = parameters.get("custom_categories", [])
            
            # Either we need message IDs or email data
            if not message_ids and not email_data:
                error_msg = "Either message_ids or emails parameter is required"
                await self.update_job_status(job_id, "failed", None, error_msg)
                return {"status": "failed", "message": error_msg}
            
            # Update status
            await self.update_job_status(job_id, "running", {
                "message": "Preparing emails for processing",
                "job_id": job_id
            })
            
            # If we have message IDs but no email data, retrieve the emails first
            emails_to_process = email_data
            if message_ids and not email_data:
                logger.info(f"Retrieving {len(message_ids)} emails for AI labeling")
                
                # Batch the message IDs for efficient processing
                batch_size = parameters.get("batch_size", 10)
                batches = self.email_processor.batch_message_ids(message_ids, batch_size)
                
                # Retrieve emails for all batches
                emails_to_process = []
                for batch_index, batch in enumerate(batches):
                    # Update progress
                    progress_update = {
                        "message": f"Retrieving email batch {batch_index + 1} of {len(batches)}",
                        "processed_count": batch_index,
                        "total_count": len(batches)
                    }
                    await self.update_job_status(job_id, "running", progress_update)
                    
                    # Retrieve the batch
                    batch_emails = await self.email_processor.retrieve_email_batch(
                        batch, include_raw_body=include_raw, max_body_length=max_body_length)
                    emails_to_process.extend(batch_emails)
            
            # Check if we have any emails to process
            if not emails_to_process:
                error_msg = "No emails available for processing"
                await self.update_job_status(job_id, "failed", None, error_msg)
                return {"status": "failed", "message": error_msg}
            
            # Update status for AI processing
            await self.update_job_status(job_id, "running", {
                "message": f"Processing {len(emails_to_process)} emails with AI",
                "processed_count": 0,
                "total_count": len(emails_to_process),
                "job_id": job_id
            })
            
            # Get available labels from storage or parameters
            available_labels = custom_categories
            if not available_labels and self.storage_manager:
                try:
                    if hasattr(self.storage_manager, "get_labels"):
                        labels = await self.storage_manager.get_labels()
                        if labels:
                            # Extract label names if we got a list of dictionaries
                            if isinstance(labels[0], dict):
                                available_labels = [label.get("name") for label in labels if label.get("name")]
                            else:
                                available_labels = labels
                except Exception as e:
                    logger.warning(f"Could not retrieve labels from storage: {e}")
            
            # Ensure we have some default categories if none were found
            if not available_labels:
                available_labels = [
                    "Work", "Personal", "Finance", "Shopping", "Travel", 
                    "Social", "Updates", "Promotions", "Forums", "Other"
                ]
            
            # Create batches for AI processing
            ai_batch_size = parameters.get("ai_batch_size", 5)  # Process 5 emails at a time with AI
            ai_batches = [emails_to_process[i:i+ai_batch_size] for i in range(0, len(emails_to_process), ai_batch_size)]
            
            # Create a high-performance organizer for AI classification
            if not self.organizer_factory:
                raise ValueError("Organizer factory is not initialized.")
            organizer = self.organizer_factory.create_organizer("high_performance")
            
            # Process batches with the AI
            processed_emails = []
            total_processed = 0
            
            for batch_index, batch in enumerate(ai_batches):
                # Update progress
                progress_update = {
                    "message": f"Processing AI batch {batch_index + 1} of {len(ai_batches)}",
                    "processed_count": total_processed,
                    "total_count": len(emails_to_process),
                    "job_id": job_id
                }
                await self.update_job_status(job_id, "running", progress_update)
                
                # Process with AI
                if hasattr(organizer, "classify_batch"):
                    # Use the high-performance organizer's built-in classify_batch method
                    try:
                        classified_batch = await organizer.classify_batch(batch, available_labels)
                        processed_emails.extend(classified_batch)
                        total_processed += len(classified_batch)
                    except Exception as e:
                        logger.error(f"Error in AI batch classification: {e}")
                        # If batch classification fails, try individual processing
                        for email in batch:
                            try:
                                result = await self.assign_label_with_ai(email, available_labels, organizer)
                                processed_emails.append(result)
                                total_processed += 1
                            except Exception as inner_e:
                                logger.error(f"Error processing individual email: {inner_e}")
                                # Add email with error info
                                email["ai_error"] = str(inner_e)
                                email["assigned_category"] = "Uncategorized"
                                processed_emails.append(email)
                                total_processed += 1
                else:
                    # Process emails individually
                    for email in batch:
                        try:
                            result = await self.assign_label_with_ai(email, available_labels, organizer)
                            processed_emails.append(result)
                            total_processed += 1
                        except Exception as e:
                            logger.error(f"Error in individual AI classification: {e}")
                            # Add email with error info
                            email["ai_error"] = str(e)
                            email["assigned_category"] = "Uncategorized"
                            processed_emails.append(email)
                            total_processed += 1
            
            # Apply the labels if requested
            apply_labels = parameters.get("apply_labels", False)
            if apply_labels:
                await self.update_job_status(job_id, "running", {
                    "message": "Applying AI-assigned labels to emails",
                    "processed_count": 0,
                    "total_count": len(processed_emails),
                    "job_id": job_id
                })
                
                # Apply labels in batches
                results = []
                for i in range(0, len(processed_emails), ai_batch_size):
                    batch = processed_emails[i:i+ai_batch_size]
                    batch_results = await self.apply_labels(batch, organizer)
                    results.extend(batch_results)
                    
                    # Update progress
                    await self.update_job_status(job_id, "running", {
                        "message": f"Applied labels to {len(results)} of {len(processed_emails)} emails",
                        "processed_count": len(results),
                        "total_count": len(processed_emails),
                        "job_id": job_id
                    })
                
                # Count successes
                successful_labels = sum(1 for r in results if r.get("success", False))
                
                # Create result with detailed information
                result = {
                    "status": "completed",
                    "message": f"Successfully processed {len(processed_emails)} emails, applied {successful_labels} labels",
                    "job_id": job_id,
                    "processed_count": len(processed_emails),
                    "total_count": len(processed_emails),
                    "labels_applied": successful_labels,
                    "emails": processed_emails,
                    "apply_results": results
                }
            else:
                # Create result without applying labels
                result = {
                    "status": "completed",
                    "message": f"Successfully processed {len(processed_emails)} emails with AI",
                    "job_id": job_id,
                    "processed_count": len(processed_emails),
                    "total_count": len(processed_emails),
                    "emails": processed_emails
                }
            
            # Update job status with results
            await self.update_job_status(job_id, "completed", result)
            return result
            
        except Exception as e:
            error_msg = f"Error in AI label assignment job: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self.update_job_status(job_id, "failed", None, error_msg)
            return {"status": "failed", "message": error_msg}
    
    async def assign_label_with_ai(self, email: Dict[str, Any], available_labels: List[str], organizer=None) -> Dict[str, Any]:
        """Assign a label to an email using AI.
        
        Args:
            email: Email data dictionary
            available_labels: List of available labels
            organizer: Optional organizer to use
            
        Returns:
            Email with AI-assigned label
        """
        if not organizer:
            if not self.organizer_factory:
                raise ValueError("Organizer factory is not initialized.")
            organizer = self.organizer_factory.create_organizer("high_performance")
            
        # Extract email content
        subject = email.get("subject", "")
        sender = email.get("from", "")
        body = email.get("raw_body", "") or email.get("body", "") or email.get("snippet", "")
        
        # Check if the organizer has a suggest_category method
        if hasattr(organizer, "suggest_category"):
            try:
                # Call the suggest_category method
                result = organizer.suggest_category(subject, sender, body)
                if asyncio.iscoroutine(result):
                    category = await result
                else:
                    category = result
                
                # Handle different return formats
                if isinstance(category, dict):
                    email["assigned_category"] = category.get("category", "Uncategorized")
                    email["ai_confidence"] = category.get("confidence", 0.0)
                    email["ai_generated"] = True
                else:
                    email["assigned_category"] = str(category) if category else "Uncategorized"
                    email["ai_generated"] = True
            except Exception as e:
                logger.error(f"Error suggesting category: {e}")
                email["assigned_category"] = "Uncategorized"
                email["ai_error"] = str(e)
                email["ai_generated"] = False
        else:
            # Call OpenAI directly if needed
            try:
                prompt = (
                    f"Subject: {subject}\nFrom: {sender}\n\nBody: {body[:400]}...\n\n"
                    f"Based on the email above, assign ONE category from this list: {', '.join(available_labels)}. "
                    "Reply with ONLY the category name."
                )
                
                # Check for OpenAI API key
                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    logger.warning("OpenAI API key not found, using default category")
                    email["assigned_category"] = "Uncategorized"
                    email["ai_error"] = "No OpenAI API key available"
                    email["ai_generated"] = False
                    return email
                
                # Import OpenAI
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=api_key)
                    
                    # Make API call
                    response = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=50,
                        temperature=0.0
                    )
                    
                    # Extract category
                    category_content = response.choices[0].message.content
                    if category_content is not None:
                        category = category_content.strip()
                    else:
                        category = "Uncategorized"
                    
                    # Validate against available labels
                    if category in available_labels:
                        email["assigned_category"] = category
                    else:
                        email["assigned_category"] = "Uncategorized"
                    
                    email["ai_generated"] = True
                    
                except ImportError:
                    logger.warning("OpenAI package not installed")
                    email["assigned_category"] = "Uncategorized" 
                    email["ai_error"] = "OpenAI package not installed"
                    email["ai_generated"] = False
            except Exception as e:
                logger.error(f"Error calling OpenAI: {e}")
                email["assigned_category"] = "Uncategorized"
                email["ai_error"] = str(e)
                email["ai_generated"] = False
        
        # Add timestamp for when this was processed
        email["ai_processed_at"] = datetime.now().isoformat()
        
        return email
    
    async def apply_labels(self, emails: List[Dict[str, Any]], organizer=None) -> List[Dict[str, Any]]:
        """Apply AI-assigned labels to emails.
        
        Args:
            emails: List of email data dictionaries with assigned_category
            organizer: Optional organizer to use
            
        Returns:
            List of results with success/failure status
        """
        if not organizer:
            if not self.organizer_factory:
                raise ValueError("Organizer factory is not initialized.")
            organizer = self.organizer_factory.create_organizer()
        
        results = []
        
        # Process in parallel with rate limiting
        sem = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
        
        async def apply_label(email):
            """Apply a label to a single email."""
            async with sem:
                email_id = email.get("id") or email.get("message_id")
                category = email.get("assigned_category", "Uncategorized")
                
                if not email_id:
                    return {"id": "unknown", "success": False, "error": "Missing email ID"}
                
                try:
                    # First create the label if it doesn't exist
                    if hasattr(organizer, "create_label"):
                        label_result = organizer.create_label(category)
                        if asyncio.iscoroutine(label_result):
                            label_result = await label_result
                        
                        if not label_result or label_result.get("status") != "success":
                            return {"id": email_id, "success": False, "error": "Failed to create label"}
                        
                        # Get the label ID
                        label_id = label_result.get("label", {}).get("id")
                        if not label_id:
                            return {"id": email_id, "success": False, "error": "No label ID returned"}
                        
                        # Apply the label
                        apply_result = organizer.apply_label(email_id, label_id)
                        if asyncio.iscoroutine(apply_result):
                            apply_result = await apply_result
                        
                        if not apply_result:
                            return {"id": email_id, "success": False, "error": "Failed to apply label"}
                        
                        return {"id": email_id, "success": True, "label": category}
                    else:
                        return {"id": email_id, "success": False, "error": "Organizer doesn't support create_label"}
                    
                except Exception as e:
                    return {"id": email_id, "success": False, "error": str(e)}
        
        # Apply labels concurrently
        tasks = [apply_label(email) for email in emails]
        return await asyncio.gather(*tasks)
    
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
