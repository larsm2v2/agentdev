"""
Email job processors for the Enhanced Email Librarian system.
"""

import logging
import time
import re
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Iterable
import asyncio
import math
from functools import partial

from .interfaces import BaseJobProcessor
from .organizer_factory import OrganizerFactory

logger = logging.getLogger(__name__)


async def list_message_ids_in_range(service, query: str, max_ids: int = 1000, page_size: int = 500) -> List[str]:
    """Page through Gmail messages.list and return up to max_ids message ids."""
    ids: List[str] = []
    loop = asyncio.get_event_loop()

    def list_page(page_token=None):
        if page_token:
            return service.users().messages().list(userId='me', q=query, maxResults=page_size, pageToken=page_token).execute()
        return service.users().messages().list(userId='me', q=query, maxResults=page_size).execute()

    page_token = None
    while True:
        try:
            res = await asyncio.to_thread(list_page, page_token)
        except Exception as e:
            logger.warning(f"Gmail list page failed: {e}")
            break
        msgs = res.get('messages') or []
        ids.extend([m.get('id') for m in msgs if m.get('id')])
        if len(ids) >= max_ids:
            ids = ids[:max_ids]
            break
        page_token = res.get('nextPageToken')
        if not page_token:
            break
    return ids


def chunk_list(iterable: Iterable, size: int):
    """Yield successive chunks of given size from iterable."""
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk

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
            emails = await self.retrieve_emails(parameters, job_id)
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
        
    async def retrieve_emails(self, parameters: Dict[str, Any], job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve emails for shelving based on parameters using a paged-list then chunked retrieval.

        Behavior:
        - Build a Gmail query from date_range if provided
        - Use organizer.service (paged) to build a canonical list of message ids (via list_message_ids_in_range)
        - Chunk ids and for each chunk prefer organizer.batch_get_messages
        - Fallback to bounded concurrent per-id fetch using organizer.get_message / get_email_content
        - Update job_manager progress and check for cancellation between chunks
        """
        try:
            organizer_type = parameters.get("organizer_type", "high_performance")
            organizer = self.organizer_factory.create_organizer(organizer_type)

            # Safer defaults for production
            batch_size = parameters.get("batch_size", 25)
            batch_pause_sec = parameters.get('batch_pause_sec', 0.5)
            batch_attempts = parameters.get('batch_attempts', 5)
            date_range = parameters.get("date_range", {"start": None, "end": None})
            concurrency = parameters.get("concurrency", 8)
            max_ids = parameters.get("max_ids", 1000)
            page_size = min(parameters.get("page_size", 500), 500)

            start_date = date_range.get("start")
            end_date = date_range.get("end")

            logger.info(f"🔍 Retrieving emails for shelving: batch_size={batch_size}, start_date={start_date}, end_date={end_date}")

            query = ""
            if start_date and end_date:
                start_fmt = datetime.fromisoformat(start_date.replace('Z', '+00:00')).strftime('%Y/%m/%d')
                end_fmt = datetime.fromisoformat(end_date.replace('Z', '+00:00')).strftime('%Y/%m/%d')
                query = f"after:{start_fmt} before:{end_fmt}"
                logger.info(f"📅 Using date range query: {query}")

            # Obtain canonical message id list (paged)
            message_ids: List[str] = []
            try:
                if hasattr(organizer, 'service') and organizer.service:
                    service = organizer.service
                    message_ids = await list_message_ids_in_range(service, query, max_ids=max_ids, page_size=page_size)
                else:
                    # Fallback helpers
                    if hasattr(organizer, 'search_messages'):
                        try:
                            sr = organizer.search_messages(query=query, max_results=parameters.get('batch_size', 100))
                            if isinstance(sr, dict) and sr.get('status') == 'success':
                                message_ids = sr.get('messages', [])
                        except Exception:
                            pass
                    if not message_ids and hasattr(organizer, 'get_recent_emails'):
                        try:
                            message_ids = organizer.get_recent_emails(max_results=parameters.get('batch_size', 100), days_back=90)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Failed to obtain message ids for shelving: {e}")

            logger.info(f"📬 Found {len(message_ids)} message ids for shelving")
            # Estimate API calls: messages.list pages + batch_get_messages calls
            try:
                safe_page_size = parameters.get('page_size', 500)
                list_calls = max(1, math.ceil(len(message_ids) / safe_page_size)) if safe_page_size else 1
            except Exception:
                list_calls = 1
            safe_batch_size = parameters.get('batch_size', batch_size)
            batch_calls = max(0, math.ceil(len(message_ids) / safe_batch_size)) if safe_batch_size else 0
            estimated_api_calls = list_calls + batch_calls
            logger.info(f"🔢 Estimated API calls for shelving: list_calls={list_calls}, batch_calls={batch_calls}, total={estimated_api_calls}")
            if self.job_manager and job_id:
                try:
                    # Try to surface estimated calls to job manager if it supports metadata updates
                    if hasattr(self.job_manager, 'update_job_metadata'):
                        await self.job_manager.update_job_metadata(job_id, {'estimated_api_calls': estimated_api_calls})
                    elif hasattr(self.job_manager, 'set_job_metadata'):
                        await self.job_manager.set_job_metadata(job_id, {'estimated_api_calls': estimated_api_calls})
                except Exception:
                    pass
            logger.debug(f"Organizer type: {organizer.__class__.__name__}; service present: {hasattr(organizer, 'service') and bool(getattr(organizer, 'service', None))}")
            logger.debug(f"Message IDs sample: {message_ids[:10]}")

            if not message_ids:
                logger.warning("⚠️ No message ids found for shelving query")
                return []

            emails: List[Dict[str, Any]] = []
            total_ids = len(message_ids)

            for idx, id_chunk in enumerate(chunk_list(message_ids, batch_size)):
                # Check cancellation
                if self.job_manager and job_id:
                    try:
                        status = await self.job_manager.get_job_status(job_id)
                        if status.get('status') == 'cancelled':
                            logger.info('Shelving retrieval cancelled by job_manager')
                            break
                    except Exception:
                        pass

                # Batch-only retrieval: attempt batch_get_messages with retries/backoff
                batch_emails: List[Dict[str, Any]] = []
                if hasattr(organizer, 'batch_get_messages'):
                    batch_fn = organizer.batch_get_messages
                    for attempt in range(1, batch_attempts + 1):
                        try:
                            # Honor per-organizer rate limiter if attached
                            if getattr(organizer, 'rate_limiter', None):
                                try:
                                    await organizer.rate_limiter.consume()
                                except Exception:
                                    # If rate limiter fails for any reason, proceed without blocking
                                    pass

                            if asyncio.iscoroutinefunction(batch_fn):
                                batch_emails = await batch_fn(id_chunk)
                            else:
                                batch_emails = await asyncio.to_thread(partial(batch_fn, id_chunk))
                            # success
                            break
                        except Exception as e:
                            logger.warning(f"Batch get failed for shelving chunk {idx} attempt {attempt}: {e}")
                            if attempt < batch_attempts:
                                await asyncio.sleep(2 ** attempt)
                    if not batch_emails:
                        logger.warning(f"Batch_get_messages failed after {batch_attempts} attempts for shelving chunk {idx}; skipping this chunk.")
                else:
                    logger.warning("Organizer does not support batch_get_messages; skipping chunk")

                emails.extend(batch_emails)

                # Update progress
                if self.job_manager and job_id:
                    await self.job_manager.update_job_progress(job_id, len(emails), total_ids)

                # small pause between batches to avoid bursts
                    await asyncio.sleep(batch_pause_sec)

            logger.info(f"After retrieval attempts, fetched {len(emails)} emails for shelving")
            if len(emails) > 0:
                logger.debug(f"Fetched email sample ids: {[e.get('id') for e in emails[:5]]}")
            else:
                logger.warning("No emails were fetched by any retrieval method for shelving")

            return emails

        except Exception as e:
            logger.error(f"Failed to retrieve emails for shelving: {e}")
            return []
                
    async def process_emails(self, emails: List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Categorize emails and extract key information (backward compatibility method).
        """
        # Use the progress version without job_id for backward compatibility
        return await self.process_emails_with_progress(emails, parameters, "")

class CatalogingJobProcessor(BaseJobProcessor):
    """Processor for cataloging/categorizing email jobs."""
    
    def __init__(self, database, organizer_factory: OrganizerFactory, job_manager: Optional[Any] = None, storage_manager: Optional[Any] = None):
        """
        Initialize the cataloging job processor.

        Args:
            database: Database connection
            organizer_factory: Factory for creating Gmail organizers
            job_manager: Optional JobManager for progress reporting
            storage_manager: Optional StorageManager for persisting metadata/vectors
        """
        self.database = database
        self.organizer_factory = organizer_factory
        self.job_manager = job_manager
        # Optional storage manager to persist metadata and vectors
        self.storage_manager = storage_manager
        
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
     
    async def retrieve_emails(self, parameters: Dict[str, Any], job_id: Optional[str] = None) -> List[Dict[str, Any]]:
      
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
            
            # Get message ids using Gmail API (paged) - prefer service when available
            message_ids: List[str] = []
            try:
                if hasattr(organizer, 'service') and organizer.service:
                    service = organizer.service
                    max_ids = parameters.get('max_ids', 1000)
                    page_size = min(parameters.get('page_size', 500), 500)
                    message_ids = await list_message_ids_in_range(service, query, max_ids=max_ids, page_size=page_size)
                else:
                    # Fallback to organizer helpers
                    if hasattr(organizer, 'search_messages'):
                        try:
                            sr = organizer.search_messages(query=query, max_results=parameters.get('batch_size', 100))
                            if isinstance(sr, dict) and sr.get('status') == 'success':
                                message_ids = sr.get('messages', [])
                        except Exception:
                            pass
                    if not message_ids and hasattr(organizer, 'get_recent_emails'):
                        try:
                            message_ids = organizer.get_recent_emails(max_results=parameters.get('batch_size', 100), days_back=90)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Failed to obtain message ids: {e}")

            logger.info(f"📬 Found {len(message_ids)} message ids for cataloging")
            # Estimate API calls: messages.list pages + batch_get_messages calls
            try:
                safe_page_size = parameters.get('page_size', 500)
                list_calls = max(1, math.ceil(len(message_ids) / safe_page_size)) if safe_page_size else 1
            except Exception:
                list_calls = 1
            safe_batch_size = parameters.get('batch_size', batch_size)
            batch_calls = max(0, math.ceil(len(message_ids) / safe_batch_size)) if safe_batch_size else 0
            estimated_api_calls = list_calls + batch_calls
            logger.info(f"🔢 Estimated API calls for cataloging: list_calls={list_calls}, batch_calls={batch_calls}, total={estimated_api_calls}")
            if self.job_manager and job_id:
                try:
                    if hasattr(self.job_manager, 'update_job_metadata'):
                        await self.job_manager.update_job_metadata(job_id, {'estimated_api_calls': estimated_api_calls})
                    elif hasattr(self.job_manager, 'set_job_metadata'):
                        await self.job_manager.set_job_metadata(job_id, {'estimated_api_calls': estimated_api_calls})
                except Exception:
                    pass
            logger.debug(f"Organizer type: {organizer.__class__.__name__}; service present: {hasattr(organizer, 'service') and bool(getattr(organizer, 'service', None))}")
            logger.debug(f"Message IDs sample: {message_ids[:10]}")

            if not message_ids:
                logger.warning("⚠️ No message ids found for cataloging query")
                return []

            # Safer defaults for production
            batch_size = parameters.get('batch_size', 25)
            batch_pause_sec = parameters.get('batch_pause_sec', 0.5)
            batch_attempts = parameters.get('batch_attempts', 5)
            emails: List[Dict[str, Any]] = []
            total_ids = len(message_ids)

            for idx, id_chunk in enumerate(chunk_list(message_ids, batch_size)):
                # check cancellation
                if self.job_manager and job_id:
                    try:
                        status = await self.job_manager.get_job_status(job_id)
                        if status.get('status') == 'cancelled':
                            logger.info('Cataloging retrieval cancelled by job_manager')
                            break
                    except Exception:
                        pass

                # Batch-only retrieval: attempt batch_get_messages with retries/backoff
                batch_emails: List[Dict[str, Any]] = []
                if hasattr(organizer, 'batch_get_messages'):
                    batch_fn = organizer.batch_get_messages
                    for attempt in range(1, batch_attempts + 1):
                        try:
                            # Honor per-organizer rate limiter if attached
                            if getattr(organizer, 'rate_limiter', None):
                                try:
                                    await organizer.rate_limiter.consume()
                                except Exception:
                                    pass

                            if asyncio.iscoroutinefunction(batch_fn):
                                batch_emails = await batch_fn(id_chunk)
                            else:
                                batch_emails = await asyncio.to_thread(partial(batch_fn, id_chunk))
                            # success
                            break
                        except Exception as e:
                            logger.warning(f"Batch get failed for chunk {idx} attempt {attempt}: {e}")
                            if attempt < batch_attempts:
                                await asyncio.sleep(2 ** attempt)
                    if not batch_emails:
                        logger.warning(f"Batch_get_messages failed after {batch_attempts} attempts for chunk {idx}; skipping this chunk.")
                else:
                    logger.warning("Organizer does not support batch_get_messages; skipping chunk")

                emails.extend(batch_emails)

                # Update progress
                if self.job_manager and job_id:
                    await self.job_manager.update_job_progress(job_id, len(emails), total_ids)

                # small pause between batches to avoid bursts
                await asyncio.sleep(batch_pause_sec)

            logger.info(f"After retrieval attempts, fetched {len(emails)} emails")
            if len(emails) > 0:
                logger.debug(f"Fetched email sample ids: {[e.get('id') for e in emails[:5]]}")
            else:
                logger.warning("No emails were fetched by any retrieval method")

            # Log final results
            if emails:
                logger.info(f"✉️ Retrieved {len(emails)} emails for cataloging")
            else:
                logger.warning("⚠️ No emails found for cataloging with the specified criteria")

            return emails
            
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
                    # Persist categorized email metadata (either via storage manager helper or direct DB)
                    if self.storage_manager and hasattr(self.storage_manager, "store_email_metadata"):
                        try:
                            await self.storage_manager.store_email_metadata({
                                "id": email.get("id", str(uuid.uuid4())),
                                "subject": email.get("subject", ""),
                                "sender": email.get("from", ""),
                                "category": category,
                                "content": email.get("snippet", ""),
                                "metadata": email
                            })
                        except Exception as e:
                            logger.warning(f"Failed to store email metadata via storage_manager: {e}")
                    elif self.database:
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

                    # Optionally store a vector embedding for the email if storage_manager supports it
                    if self.storage_manager and hasattr(self.storage_manager, "store_email_vector"):
                        try:
                            # Create a simple deterministic embedding from the subject text as a placeholder
                            subj = email.get("subject", "") or ""
                            h = abs(hash(subj))
                            # small vector of length 8 for tests and Qdrant storage
                            vec = [float((h >> (i * 8)) & 0xFF) / 255.0 for i in range(8)]
                            await self.storage_manager.store_email_vector(email.get("id", str(uuid.uuid4())), vec, {"category": category})
                        except Exception as e:
                            logger.warning(f"Failed to store email vector: {e}")
                    
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