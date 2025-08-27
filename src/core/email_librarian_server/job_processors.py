"""
Email job processors for the Enhanced Email Librarian system.
"""

import logging
import time
import re
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union

from .interfaces import BaseJobProcessor
from .organizer_factory import OrganizerFactory

logger = logging.getLogger(__name__)

class ShelvingJobProcessor(BaseJobProcessor):
    """Processor for shelving/labeling email jobs."""
    
    def __init__(self, database, organizer_factory: OrganizerFactory, job_manager = None):
        """
        Initialize the shelving job processor.
        
        Args:
            database: Database connection
            organizer_factory: Factory for creating Gmail organizers
        """
        self.database = database
        self.organizer_factory = organizer_factory
        self.job_manager = job_manager
        
    async def process(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a shelving job using the template method pattern.
        
        Args:
            job_id: Unique job identifier
            parameters: Job parameters
            
        Returns:
            Job results
        """
        try:
            # Update status to running
            await self.update_job_status(job_id, "running")
            
            # Retrieve emails
            emails = await self.retrieve_emails(parameters)
            total_count = len(emails)
            
            # Update job with total count for progress tracking
            if self.job_manager:
                await self.job_manager.update_job_progress(job_id, 0, total_count)
            
            # Process emails with progress updates
            results = await self.process_emails_with_progress(emails, parameters, job_id)
            
            # Mark as completed
            await self.update_job_status(job_id, "completed", results)
            return results
            
        except Exception as e:
            logger.error(f"Shelving job {job_id} failed: {e}")
            await self.update_job_status(job_id, "failed", error_message=str(e))
            raise e
    
    async def process_emails_with_progress(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """
        Process emails with progress reporting.
        
        Args:
            emails: List of email data to process
            parameters: Job parameters
            job_id: Job ID for progress tracking
            
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
        
        # Process each email with progress updates
        processed_count = 0
        shelved_count = 0
        applied_labels = {}
        total_count = len(emails)
        
        for i, email in enumerate(emails):
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
                
                # Update progress every 5 emails or on last email
                if (processed_count % 5 == 0) or (processed_count == total_count):
                    if self.job_manager:
                        await self.job_manager.update_job_progress(job_id, processed_count, total_count)
                        
            except Exception as e:
                logger.error(f"Error processing email {email.get('id', 'unknown')}: {e}")
                processed_count += 1  # Still count as processed even if failed
                
                # Update progress on errors too
                if self.job_manager:
                    await self.job_manager.update_job_progress(job_id, processed_count, total_count)
                
        return {
            "processed_count": processed_count,
            "shelved_count": shelved_count,
            "applied_labels": applied_labels,
            "job_type": "shelving",
            "status": "completed",
            "message": f"Successfully shelved {shelved_count} out of {processed_count} emails"
        }
    
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
        Categorize emails and extract key information (backward compatibility method).
        """
        # Use the progress version without job_id for backward compatibility
        return await self.process_emails_with_progress(emails, parameters, "")

class CatalogingJobProcessor(BaseJobProcessor):
    """Processor for cataloging/categorizing email jobs."""
    
    def __init__(self, database, organizer_factory: OrganizerFactory, job_manager = None):
        """
        Initialize the cataloging job processor.
        
        Args:
            database: Database connection
            organizer_factory: Factory for creating Gmail organizers
        """
        self.database = database
        self.organizer_factory = organizer_factory
        self.job_manager = job_manager
        
    async def process(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a shelving job using the template method pattern.
        
        Args:
            job_id: Unique job identifier
            parameters: Job parameters
            
        Returns:
            Job results
        """
        try:
            # Update status to running
            await self.update_job_status(job_id, "running")
            
            # Retrieve emails
            emails = await self.retrieve_emails(parameters)
            total_count = len(emails)
            
            # Update job with total count for progress tracking
            if self.job_manager:
                await self.job_manager.update_job_progress(job_id, 0, total_count)
            
            # Process emails with progress updates
            results = await self.process_emails_with_progress(emails, parameters, job_id)
            
            # Mark as completed
            await self.update_job_status(job_id, "completed", results)
            return results
            
        except Exception as e:
            logger.error(f"Cataloging job {job_id} failed: {e}")
            await self.update_job_status(job_id, "failed", error_message=str(e))
            raise e
     
    async def retrieve_emails(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Retrieve emails for cataloging based on parameters.
        """
        try:
            organizer = self.organizer_factory.create_organizer("high_performance")
            
            # Extract parameters
            batch_size = parameters.get("batch_size", 10)
            date_range = parameters.get("date_range", {"start": None, "end": None})
            
            # Get emails within date range if specified
            start_date = date_range.get("start")
            end_date = date_range.get("end")
            
            logger.info(f"🔍 Retrieving emails for cataloging: batch_size={batch_size}, start_date={start_date}, end_date={end_date}")
            
            # Use date range if provided
            query = ""
            if start_date and end_date:
                # Format dates for Gmail query (YYYY/MM/DD)
                start_fmt = datetime.fromisoformat(start_date.replace('Z', '+00:00')).strftime('%Y/%m/%d')
                end_fmt = datetime.fromisoformat(end_date.replace('Z', '+00:00')).strftime('%Y/%m/%d')
                query = f"after:{start_fmt} before:{end_fmt}"
                logger.info(f"📅 Using date range query: {query}")
            
            # Get emails that match the query
            emails = await organizer.search_emails(query=query, max_results=batch_size)
            
            # Log results
            if emails:
                logger.info(f"✉️ Retrieved {len(emails)} emails for cataloging")
            else:
                logger.warning("⚠️ No emails found for cataloging with the specified criteria")
                
            return emails if isinstance(emails, list) else []
            
        except Exception as e:
            logger.error(f"Failed to retrieve emails for cataloging: {e}")
            return []
            
    async def update_job_status(self, job_id: str, status: str, results: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        """
        Update job status in the database.
        
        Args:
            job_id: Job identifier
            status: New status
            results: Optional job results
            error_message: Optional error message
        """
            # Check if database is available
        if not self.database:
            logger.warning(f"No database connection - cannot update job {job_id} status to {status}")
            return
        
        try:
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
            logger.debug(f"Updated job {job_id} status to {status}")
        
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status in database: {e}")
        # Don't raise - this shouldn't fail the entire job
    
    async def process_emails_with_progress(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """Process emails with progress reporting for cataloging."""
        if not emails:
            return {
                "processed_count": 0,
                "categorized_count": 0,
                "categories_created": [],
                "job_type": "cataloging",
                "status": "completed",
                "message": "No emails to process"
            }
        
        # Get existing categories from database
        existing_categories = await self._get_existing_categories()
        logger.info(f"Found {len(existing_categories)} existing categories")
        
        # Track stats
        processed_count = 0
        categorized_count = 0
        categories_used = set()
        categories_created = set()
        total_count = len(emails)
        
        # Process emails in batches for efficiency
        try:
            for i, email in enumerate(emails):
                try:
                    # Extract email content
                    subject = email.get("subject", "").lower()
                    sender = email.get("from", "").lower()
                    body = email.get("snippet", "").lower()
                    
                    # First try to find a match with existing categories
                    category = self._match_existing_category(subject, sender, body, existing_categories)
                    
                    # If no match found, generate a new category
                    if not category:
                        category = self._generate_new_category(subject, sender, body)
                        categories_created.add(category)
                        # Add to existing categories for future matching
                        existing_categories.append(category)
                        logger.info(f"🏷️ Created new category: {category}")
                    else:
                        categories_used.add(category)
                        logger.debug(f"📎 Using existing category: {category}")
                    
                    # Store category in email object
                    email["category"] = category
                    
                    # Store categorized email in database
                    if self.database:
                        await self.database.execute("""
                            INSERT INTO emails (id, subject, sender, category, content, metadata)
                            VALUES (:id, :subject, :sender, :category, :content, :metadata)
                            ON CONFLICT (id) DO UPDATE SET
                                category = :category,
                                processed_at = CURRENT_TIMESTAMP
                        """, {
                            "id": email.get("id", str(uuid.uuid4())),
                            "subject": email.get("subject", ""),
                            "sender": email.get("from", ""),
                            "category": category,
                            "content": email.get("snippet", ""),
                            "metadata": json.dumps(email)
                        })
                    
                    categorized_count += 1
                    processed_count += 1
                    
                    # Update progress every 5 emails or on last email
                    if (processed_count % 5 == 0) or (processed_count == total_count):
                        if self.job_manager:
                            await self.job_manager.update_job_progress(job_id, processed_count, total_count)
                    
                except Exception as e:
                    logger.error(f"Error categorizing email {email.get('id', 'unknown')}: {e}")
                    processed_count += 1
                    
                    # Update progress on errors too
                    if self.job_manager:
                        await self.job_manager.update_job_progress(job_id, processed_count, total_count)
            
            # Prepare results
            results = {
                "processed_count": processed_count,
                "categorized_count": categorized_count,
                "categories_used": list(categories_used),
                "categories_created": list(categories_created),
                "job_type": "cataloging",
                "status": "completed",
                "message": f"Successfully categorized {categorized_count} out of {processed_count} emails"
            }
            
            # Final progress update
            if self.job_manager:
                await self.job_manager.update_job_status(job_id, "completed", results=results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in cataloging process: {e}")
            if self.job_manager:
                await self.job_manager.update_job_status(job_id, "failed", error_message=str(e))
            raise
            
    async def process_emails(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Categorize emails and extract key information (backward compatibility method).
        """
        # Use the progress version without job_id for backward compatibility
        return await self.process_emails_with_progress(emails, parameters, "")
    #########################################

    async def _get_existing_categories(self) -> List[str]:
        """Get existing categories from the database."""
        try:
            if not self.database:
                return DEFAULT_CATEGORIES
                
            results = await self.database.fetch_all("""
                SELECT DISTINCT category FROM emails WHERE category IS NOT NULL
            """)
            
            categories = [row["category"] for row in results if row["category"]]
            
            # If no categories found, use defaults
            if not categories:
                return DEFAULT_CATEGORIES
                
            return categories
            
        except Exception as e:
            logger.error(f"Error fetching existing categories: {e}")
            return DEFAULT_CATEGORIES
    
    def _match_existing_category(self, subject: str, sender: str, body: str, existing_categories: List[str]) -> Optional[str]:
        """Match email to existing category based on content."""
        # Concatenate content for matching
        content = f"{subject} {sender} {body}".lower()
        
        # Keywords for common categories
        category_keywords = {
            "Finance": ["invoice", "payment", "bill", "receipt", "transaction", "financial", "budget", "accounting"],
            "Meetings": ["meeting", "calendar", "schedule", "appointment", "event", "join", "zoom", "teams", "invite"],
            "Marketing": ["newsletter", "offer", "promotion", "discount", "campaign", "subscribe", "sale", "marketing"],
            "Support": ["support", "help", "issue", "problem", "ticket", "request", "assistance", "resolve"],
            "Updates": ["update", "notification", "alert", "status", "announcement", "news"],
            "Travel": ["flight", "hotel", "booking", "reservation", "itinerary", "travel", "trip"]
        }
        
        # First try matching with keyword categories
        for category, keywords in category_keywords.items():
            if any(keyword in content for keyword in keywords):
                return category
        
        # If no keyword match, check if sender domain matches any existing category
        if "@" in sender:
            domain = sender.split("@")[1]
            domain_parts = domain.split(".")
            if len(domain_parts) > 1:
                company = domain_parts[-2].title()
                if company in existing_categories:
                    return company
                
        # Finally, look for matching words between subject and categories
        subject_words = set(re.findall(r'\w+', subject.lower()))
        for category in existing_categories:
            # If category name (or part of it) is in the subject
            if category.lower() in subject.lower():
                return category
            # If any word in category matches word in subject
            category_words = set(re.findall(r'\w+', category.lower()))
            if subject_words & category_words:  # intersection
                return category
        
        return None

    def _generate_new_category(self, subject: str, sender: str, body: str) -> str:
        """Generate a new category name based on email content."""
        # Simple heuristic approach - extract most meaningful word from subject
        # In a real system, we'd use NLP or call an LLM
        
        # Remove common words and stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "about", "re"}
        
        # Extract domain from sender as potential category
        sender_category = None
        if "@" in sender:
            domain = sender.split("@")[1]
            domain_parts = domain.split(".")
            if len(domain_parts) > 1:
                sender_category = domain_parts[-2].title()
        
        # Extract words from subject
        words = [word for word in re.findall(r'\w+', subject.lower()) if len(word) > 3 and word not in stop_words]
        
        # Try to find a meaningful noun/keyword
        if words:
            # Use the longest word as it might be more specific
            longest_word = max(words, key=len)
            return longest_word.title()
        
        # If no good words from subject, use sender domain
        if sender_category:
            return sender_category
        
        # Fallback
        return "Uncategorized"
 # Default categories if none exist in database
DEFAULT_CATEGORIES = [
        "Finance", "Meetings", "Marketing", "Support", "Updates", 
        "Travel", "Personal", "Work", "Shopping", "Social", "Uncategorized"
]