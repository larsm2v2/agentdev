"""
Email job processors for the Enhanced Email Librarian system.
"""

import logging
import time
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union

from .interfaces import BaseJobProcessor
from .organizer_factory import OrganizerFactory

logger = logging.getLogger(__name__)

class ShelvingJobProcessor(BaseJobProcessor):
    """Processor for shelving/labeling email jobs."""
    
    def __init__(self, database, organizer_factory: OrganizerFactory):
        """
        Initialize the shelving job processor.
        
        Args:
            database: Database connection
            organizer_factory: Factory for creating Gmail organizers
        """
        self.database = database
        self.organizer_factory = organizer_factory
        
    async def update_job_status(self, job_id: str, status: str, results: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        """
        Update job status in the database.
        
        Args:
            job_id: Job identifier
            status: New status
            results: Optional job results
            error_message: Optional error message
        """
        query = """
        UPDATE email_processing_jobs 
        SET status = :status, 
            updated_at = :updated_at
        """
        values = {
            "id": job_id,
            "status": status,
            "updated_at": datetime.now().isoformat()
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
            parameters: Job parameters with query and batch_size
            
        Returns:
            List of email data
        """
        query = parameters.get("query", "in:inbox is:unread")
        batch_size = parameters.get("batch_size", 10)
        
        # Create organizer
        organizer_type = parameters.get("organizer_type", "high_performance")
        gmail_organizer = self.organizer_factory.create_organizer(organizer_type)
        
        # Check for container batch method
        if self.organizer_factory.container_gmail_available and self.organizer_factory.get_container_batch_emails_with_storage:
            try:
                logger.info("⚡ Using efficient batch method for shelving...")
                batch_result = await self.organizer_factory.get_container_batch_emails_with_storage(
                    batch_size=batch_size,
                    query=query
                )
                
                if batch_result["status"] != "success":
                    logger.error(f"❌ Batch email retrieval failed: {batch_result.get('message', 'Unknown error')}")
                    return []
                    
                emails = batch_result.get("emails", [])
                storage_info = batch_result.get("storage")
                if storage_info is None or not isinstance(storage_info, dict):
                    storage_info = {}
                
                # Get API calls info
                api_calls = "unknown"
                if isinstance(batch_result, dict):
                    summary = batch_result.get('summary', {})
                    if isinstance(summary, dict):
                        api_calls = summary.get('api_calls', 'unknown')
                
                logger.info(f"📬 Retrieved {len(emails)} unread emails using batch method (API calls: {api_calls})")
                
                # Log storage integration success
                if storage_info and isinstance(storage_info, dict):
                    postgresql_id = storage_info.get('postgresql_id', 'N/A')
                    qdrant_stored = storage_info.get('qdrant_stored', 0)
                    logger.info(f"💾 Storage integration: PostgreSQL ID {postgresql_id}, Qdrant stored: {qdrant_stored} vectors")
                elif storage_info:
                    logger.info(f"💾 Storage integration available: {type(storage_info).__name__}")
                    
                return emails
            except Exception as e:
                logger.error(f"Error using batch method: {e}")
                logger.warning("⚠️ Falling back to direct Gmail API calls")
        
        # Fallback to standard method
        try:
            logger.info(f"🔍 Retrieving emails with query: {query}")
            search_result = gmail_organizer.search_messages(query=query, max_results=batch_size)
            
            if search_result["status"] != "success":
                logger.error(f"❌ Email search failed: {search_result.get('message', 'Unknown error')}")
                return []
                
            message_ids = search_result.get("messages", [])
            logger.info(f"📬 Found {len(message_ids)} matching messages")
            
            emails = []
            for msg_id in message_ids:
                msg_data = gmail_organizer.get_message(msg_id)
                if msg_data["status"] == "success":
                    emails.append(msg_data["message"])
            
            logger.info(f"📬 Retrieved {len(emails)} emails using standard method")
            return emails
        except Exception as e:
            logger.error(f"Error retrieving emails: {e}")
            return []
            
    async def process_emails(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply labels to emails based on their content.
        
        Args:
            emails: List of email data to process
            parameters: Job parameters
            
        Returns:
            Processing results
        """
        if not emails:
            return {
                "processed_count": 0,
                "shelved_count": 0,
                "job_type": "shelving",
                "status": "completed",
                "message": "No emails to process"
            }
            
        # Create organizer
        organizer_type = parameters.get("organizer_type", "high_performance")
        gmail_organizer = self.organizer_factory.create_organizer(organizer_type)
        
        # Process each email
        processed_count = 0
        shelved_count = 0
        applied_labels = {}
        
        for email in emails:
            try:
                # Extract email ID and content
                email_id = email.get("id")
                if not email_id:
                    logger.warning("⚠️ Email missing ID, skipping")
                    continue
                
                # Determine label
                label = "Processed"
                if "category" in email:
                    label = email["category"]
                elif "suggested_category" in email:
                    label = email["suggested_category"]
                    
                # Apply label
                label_result = gmail_organizer.create_label(label)
                if label_result["status"] == "success":
                    label_id = label_result["label"]["id"]
                    
                    # Apply label to email
                    if gmail_organizer.apply_label(email_id, label_id):
                        shelved_count += 1
                        if label not in applied_labels:
                            applied_labels[label] = 0
                        applied_labels[label] += 1
                
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing email {email.get('id', 'unknown')}: {e}")
                
        return {
            "processed_count": processed_count,
            "shelved_count": shelved_count,
            "applied_labels": applied_labels,
            "job_type": "shelving",
            "status": "completed",
            "message": f"Successfully shelved {shelved_count} out of {processed_count} emails"
        }


class CatalogingJobProcessor(BaseJobProcessor):
    """Processor for cataloging/categorizing email jobs."""
    
    def __init__(self, database, organizer_factory: OrganizerFactory):
        """
        Initialize the cataloging job processor.
        
        Args:
            database: Database connection
            organizer_factory: Factory for creating Gmail organizers
        """
        self.database = database
        self.organizer_factory = organizer_factory
        
    async def update_job_status(self, job_id: str, status: str, results: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        """
        Update job status in the database.
        
        Args:
            job_id: Job identifier
            status: New status
            results: Optional job results
            error_message: Optional error message
        """
        query = """
        UPDATE email_processing_jobs 
        SET status = :status, 
            updated_at = :updated_at
        """
        values = {
            "id": job_id,
            "status": status,
            "updated_at": datetime.now().isoformat()
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
            parameters: Job parameters with query, start_date, end_date, batch_size
            
        Returns:
            List of email data
        """
        batch_size = parameters.get("batch_size", 25)
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        
        # Create Gmail query with date range
        gmail_query = "in:inbox "
        if start_date:
            gmail_query += f"after:{start_date} "
        if end_date:
            gmail_query += f"before:{end_date} "
            
        logger.info(f"🔍 Gmail query: {gmail_query}")
        
        # Use container methods if available
        if self.organizer_factory.container_gmail_available and self.organizer_factory.get_container_batch_emails_with_storage:
            try:
                result = await self.organizer_factory.get_container_batch_emails_with_storage(
                    batch_size=batch_size,
                    query=gmail_query
                )
                
                if result["status"] != "success":
                    logger.error(f"❌ Batch email retrieval failed: {result.get('message', 'Unknown error')}")
                    return []
                    
                emails = result.get("emails", [])
                logger.info(f"📬 Retrieved {len(emails)} emails")
                return emails
            except Exception as e:
                logger.error(f"Error using container method: {e}")
                logger.warning("⚠️ Falling back to standard method")
                
        # Fallback to standard method
        organizer_type = parameters.get("organizer_type", "high_performance")
        gmail_organizer = self.organizer_factory.create_organizer(organizer_type)
        
        try:
            search_result = gmail_organizer.search_messages(query=gmail_query, max_results=batch_size)
            
            if search_result["status"] != "success":
                logger.error(f"❌ Email search failed: {search_result.get('message', 'Unknown error')}")
                return []
                
            message_ids = search_result.get("messages", [])
            logger.info(f"📬 Found {len(message_ids)} matching messages")
            
            emails = []
            for msg_id in message_ids:
                msg_data = gmail_organizer.get_message(msg_id)
                if msg_data["status"] == "success":
                    emails.append(msg_data["message"])
            
            logger.info(f"📬 Retrieved {len(emails)} emails using standard method")
            return emails
        except Exception as e:
            logger.error(f"Error retrieving emails: {e}")
            return []
            
    async def process_emails(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Categorize emails and extract key information.
        
        Args:
            emails: List of email data to process
            parameters: Job parameters
            
        Returns:
            Processing results
        """
        if not emails:
            return {
                "processed_count": 0,
                "categorized_count": 0,
                "categories_created": [],
                "job_type": "cataloging",
                "status": "completed",
                "message": "No emails to process"
            }
            
            # Use container categorization if available
            all_categories = set()
            categorized_count = 0
            
            try:
                # Direct categorization - this would depend on the actual implementation
                logger.info("Categorizing emails...")
                
                # Simple stub approach - assume we can extract categories from emails directly
                for email in emails:
                    # In a real implementation, we'd use AI to categorize or extract from existing data
                    if "subject" in email:
                        subject = email.get("subject", "").lower()
                        
                        # Simplified categorization rules
                        if "invoice" in subject or "payment" in subject:
                            category = "Finance"
                        elif "meeting" in subject or "schedule" in subject:
                            category = "Meetings"
                        elif "report" in subject or "update" in subject:
                            category = "Updates"
                        else:
                            category = "General"
                            
                        # Store category back in email
                        email["category"] = category
                        all_categories.add(category)
                        categorized_count += 1
                
                logger.info(f"✅ Categorized {categorized_count} emails into {len(all_categories)} categories")
                
                return {
                    "processed_count": len(categorized_emails),
                    "categorized_count": len(categorized_emails),
                    "categories_created": list(all_categories),
                    "job_type": "cataloging",
                    "status": "completed",
                    "message": f"Successfully categorized {len(categorized_emails)} emails"
                }
            except Exception as e:
                logger.error(f"Error in container categorization: {e}")
                logger.warning("⚠️ Falling back to standard method")
                
        # Fallback to simpler approach - just count emails
        return {
            "processed_count": len(emails),
            "categorized_count": 0,
            "categories_created": [],
            "job_type": "cataloging",
            "status": "completed",
            "message": f"Processed {len(emails)} emails (no categorization available)"
        }
