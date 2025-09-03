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

from ..interfaces import BaseJobProcessor
from ..organizer_factory import OrganizerFactory

logger = logging.getLogger(__name__)


async def list_message_ids_in_range(service, query: str, max_ids: int = 1000, page_size: int = 500, label_ids: Optional[List[str]] = None) -> List[str]:
    """Page through Gmail messages.list and return up to max_ids message ids.

    If `label_ids` is provided it will be passed to the Gmail API as
    `labelIds` (e.g. ['INBOX']) which is the recommended way to exclude
    archived messages (those without the INBOX label).
    """
    
    try:
        svc_present = service is not None
    except Exception:
        svc_present = False
    logger.info(
        "list_message_ids_in_range called: "
        "query=%r, max_ids=%s, page_size=%s, label_ids=%r, service_present=%s",
        query, max_ids, page_size, label_ids, svc_present
    )
    ids: List[str] = []
    loop = asyncio.get_event_loop()

    def list_page(page_token=None):
        params = {"userId": "me", "q": query, "maxResults": page_size}
        if page_token:
            params["pageToken"] = page_token
        if label_ids:
            params["labelIds"] = label_ids
        return service.users().messages().list(**params).execute()

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
            logger.info(f"CatalogingJobProcessor.process: starting job {job_id} with params keys={list(parameters.keys())}")
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
        all_emails = []  # Initialize with empty list to handle any exceptions
        
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
                    # Exclude archived messages by requesting only INBOX label ids
                    message_ids = await list_message_ids_in_range(service, query, max_ids=max_ids, page_size=page_size, label_ids=['INBOX'])
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

                # Batch-only retrieval: attempt fetch_email_batches with retries/backoff
                batch_emails: List[Dict[str, Any]] = []
                if hasattr(organizer, 'fetch_email_batches'):
                    batch_fn = organizer.fetch_email_batches
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
                        logger.warning(f"fetch_email_batches failed after {batch_attempts} attempts for shelving chunk {idx}; skipping this chunk.")
                else:
                    logger.warning("Organizer does not support fetch_email_batches; skipping chunk")

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
            
            # Support both parameter formats:
            # 1. Nested format: parameters.date_range.{start,end}
            # 2. Flat format: parameters.{start_date,end_date} or parameters.{startDate,endDate}
            # 3. Direct message_ids array from API router
            
            # First check if we already have message_ids directly from the API router
            message_ids_direct = parameters.get("message_ids")
            if message_ids_direct and isinstance(message_ids_direct, list) and len(message_ids_direct) > 0:
                logger.info(f"🔍 Using {len(message_ids_direct)} message_ids provided directly from API router")
            
            # Get start/end dates from either format
            start_date = None
            end_date = None
            
            # Try nested date_range format first
            date_range = parameters.get("date_range", {})
            if isinstance(date_range, dict):
                start_date = date_range.get("start")
                end_date = date_range.get("end")
            
            # If not found, try flat format with different key variations
            if not start_date:
                start_date = parameters.get("start_date") or parameters.get("startDate")
            if not end_date:
                end_date = parameters.get("end_date") or parameters.get("endDate")
            
            logger.info(f"🔍 Retrieving emails for cataloging: batch_size={batch_size}, start_date={start_date}, end_date={end_date}")
            
            # Try to use explicit query if provided by API router
            query = parameters.get("query", "")
            
            # Build query from dates if needed and no explicit query
            if not query and start_date and end_date:
                # Format dates for Gmail query (YYYY/MM/DD)
                try:
                    start_fmt = datetime.fromisoformat(start_date.replace('Z', '+00:00')).strftime('%Y/%m/%d')
                    end_fmt = datetime.fromisoformat(end_date.replace('Z', '+00:00')).strftime('%Y/%m/%d')
                    query = f"after:{start_fmt} before:{end_fmt}"
                    logger.info(f"📅 Using date range query: {query}")
                except Exception as e:
                    logger.warning(f"Failed to format dates for query: {e}")
            
            # Get message ids using Gmail API (paged) - prefer service when available
            message_ids: List[str] = []
            # Create tracking metadata for job progress/results
            tracking_metadata = {
                "message_ids_retrieved": False,
                "count_of_message_ids": 0,
                "message_ids_batched": False,
                "batched_ids": False,
                "emails_retrieved": False,
            }
            
            # First try using pre-fetched message_ids if available
            message_ids_direct = parameters.get("message_ids")
            if message_ids_direct and isinstance(message_ids_direct, list) and len(message_ids_direct) > 0:
                logger.info(f"Using {len(message_ids_direct)} message IDs provided directly from API router")
                message_ids = [str(mid) for mid in message_ids_direct if mid]
                tracking_metadata["message_ids_retrieved"] = True
                tracking_metadata["count_of_message_ids"] = len(message_ids)
                # Update job metadata with tracking info
                if self.job_manager and job_id:
                    await self.job_manager.update_job_metadata(job_id, tracking_metadata)
            
            # Only try API calls if we don't have message IDs yet
            if not message_ids:
                try:
                    # Create organizer and try a direct service-backed paged listing first
                    max_ids = parameters.get('max_ids', 1000)
                    page_size = min(parameters.get('page_size', 500), 500)
                    
                    if hasattr(organizer, 'service') and organizer.service:
                        service = organizer.service
                        # Use INBOX label filter to avoid archived messages
                        try:
                            logger.info(f"Calling list_message_ids_in_range with query: '{query}'")
                            message_ids = await list_message_ids_in_range(service, query, max_ids=max_ids, page_size=page_size, label_ids=['INBOX'])
                            if message_ids is not None:
                                tracking_metadata["message_ids_retrieved"] = len(message_ids) > 0
                                tracking_metadata["count_of_message_ids"] = len(message_ids)
                            else:
                                tracking_metadata["message_ids_retrieved"] = False
                                tracking_metadata["count_of_message_ids"] = 0
                            # Update job metadata with tracking info
                            if self.job_manager and job_id:
                                await self.job_manager.update_job_metadata(job_id, tracking_metadata)
                        except Exception as e:
                            logger.warning(f"Service-backed list_message_ids_in_range failed: {e}")
                except Exception as e:
                    logger.warning(f"Failed to get message IDs via service: {e}")
                
                # If no message_ids yet, try fallback methods
                if not message_ids:
                    # Fallback: try organizer.search_messages or organizer.list_message_ids_in_range if present
                    search_call = None
                    if hasattr(organizer, "search_messages"):
                        search_call = organizer.search_messages(query=query, max_results=10000)
                    elif hasattr(organizer, "list_message_ids_in_range"):
                        # Get start and end as timestamps if available
                        start_ts = None
                        end_ts = None
                        if start_date and end_date:
                            try:
                                # Use the already imported datetime
                                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                start_ts = int(start_dt.timestamp())
                                end_ts = int(end_dt.timestamp())
                            except Exception as e:
                                logger.warning(f"Failed to convert dates to timestamps: {e}")
                        
                        if start_ts and end_ts:
                            search_call = organizer.list_message_ids_in_range(start_ts, end_ts)
                    
                    # Execute the search call if available
                    if search_call is not None:
                        if asyncio.iscoroutine(search_call):
                            results = await search_call
                        else:
                            results = search_call
                            
                        # Normalize to a flat list of message ids
                        extracted_ids = []
                        if results is not None:
                            if isinstance(results, list):
                                for item in results:
                                    if isinstance(item, str):
                                        extracted_ids.append(item)
                                    elif isinstance(item, dict):
                                        # common keys
                                        mid = item.get("id") or item.get("message_id") or item.get("messageId")
                                        if mid:
                                            extracted_ids.append(str(mid))
                                    else:
                                        # try to stringify anything else
                                        try:
                                            extracted_ids.append(str(item))
                                        except Exception:
                                            continue
                            elif isinstance(results, dict):
                                # single object -> try to extract id
                                mid = results.get("id") or results.get("message_id") or results.get("messageId")
                                if mid:
                                    extracted_ids = [str(mid)]
                                # Also check if there's a messages array
                                messages = results.get("messages", [])
                                if isinstance(messages, list):
                                    for msg in messages:
                                        if isinstance(msg, dict):
                                            mid = msg.get("id")
                                            if mid:
                                                extracted_ids.append(str(mid))
                                
                        if extracted_ids:
                            message_ids = extracted_ids
                            tracking_metadata["message_ids_retrieved"] = True
                            tracking_metadata["count_of_message_ids"] = len(message_ids)
                            # Update job metadata with tracking info
                            if self.job_manager and job_id:
                                await self.job_manager.update_job_metadata(job_id, tracking_metadata)
                
                # Last resort: try get_recent_emails if no message_ids yet
                if not message_ids and hasattr(organizer, 'get_recent_emails'):
                    try:
                        recent_ids = organizer.get_recent_emails(max_results=parameters.get('batch_size', 100), days_back=90)
                        if recent_ids and isinstance(recent_ids, list):
                            message_ids = recent_ids
                            tracking_metadata["message_ids_retrieved"] = True
                            tracking_metadata["count_of_message_ids"] = len(message_ids)
                            # Update job metadata with tracking info
                            if self.job_manager and job_id:
                                await self.job_manager.update_job_metadata(job_id, tracking_metadata)
                    except Exception as e:
                        logger.warning(f"Failed to get recent emails: {e}")


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
            total_ids = len(message_ids) if message_ids is not None else 0
            tracking_metadata["message_ids_batched"] = total_ids > 0
            # Update job metadata with tracking info
            if self.job_manager and job_id:
                await self.job_manager.update_job_metadata(job_id, tracking_metadata)

            # Defensive check - ensure message_ids is not None before iteration
            if message_ids is None:
                logger.warning("Message IDs is None - cannot process batches")
                message_ids = []  # Use empty list for safety
                
            for idx, id_chunk in enumerate(chunk_list(message_ids, batch_size)):
                tracking_metadata["batched_ids"] = True
                # Update job metadata with tracking info
                if self.job_manager and job_id:
                    try:
                        await self.job_manager.update_job_metadata(job_id, tracking_metadata)
                    except Exception as e:
                        logger.error(f"Failed to update metadata during batching: {e}")
                # check cancellation
                if self.job_manager and job_id:
                    try:
                        status = await self.job_manager.get_job_status(job_id)
                        if status.get('status') == 'cancelled':
                            logger.info('Cataloging retrieval cancelled by job_manager')
                            break
                    except Exception:
                        pass

                # Batch-only retrieval: attempt fetch_email_batches with retries/backoff
                batch_emails: List[Dict[str, Any]] = []
                if hasattr(organizer, 'fetch_email_batches'):
                    batch_fn = organizer.fetch_email_batches
                    for attempt in range(1, batch_attempts + 1):
                        try:
                            # Honor per-organizer rate limiter if attached
                            if getattr(organizer, 'rate_limiter', None):
                                try:
                                    await organizer.rate_limiter.consume()
                                except Exception:
                                    pass

                            # First try the normalized version of batch fetch if available
                            if hasattr(organizer, 'fetch_email_batches_normalized'):
                                logger.info("Using fetch_email_batches_normalized instead of regular fetch_email_batches")
                                if asyncio.iscoroutinefunction(organizer.fetch_email_batches_normalized):
                                    raw_emails = await organizer.fetch_email_batches_normalized(id_chunk)
                                else:
                                    raw_emails = await asyncio.to_thread(partial(organizer.fetch_email_batches_normalized, id_chunk))
                            else:
                                # Fall back to regular batch function
                                if asyncio.iscoroutinefunction(batch_fn):
                                    raw_emails = await batch_fn(id_chunk)
                                else:
                                    raw_emails = await asyncio.to_thread(partial(batch_fn, id_chunk))
                            
                            # Enhanced debugging of raw_emails structure
                            logger.info(f"Raw emails type: {type(raw_emails)}")
                            
                            # Additional debugging to inspect structure
                            if raw_emails is not None:
                                try:
                                    if isinstance(raw_emails, dict):
                                        logger.info(f"Raw emails is a dictionary with keys: {list(raw_emails.keys())}")
                                    elif isinstance(raw_emails, list):
                                        logger.info(f"Raw emails is a list of length {len(raw_emails)}")
                                        # Check first item type
                                        if raw_emails and len(raw_emails) > 0:
                                            first_item = raw_emails[0]
                                            logger.info(f"First item type: {type(first_item)}")
                                            if isinstance(first_item, dict):
                                                logger.info(f"First item keys: {list(first_item.keys())}")
                                            elif isinstance(first_item, list):
                                                logger.info(f"First item is list of length: {len(first_item)}")
                                    else:
                                        logger.info(f"Raw emails is neither dict nor list: {str(raw_emails)[:100]}")
                                except Exception as debug_err:
                                    logger.error(f"Error during debugging: {debug_err}")
                            
                            # Check if it's a single email instead of a list
                            if not hasattr(raw_emails, '__iter__') or isinstance(raw_emails, dict):
                                logger.info(f"Converting single email to list: {type(raw_emails)}")
                                # Convert to proper dictionary type first
                                if isinstance(raw_emails, dict):
                                    email_dict = {
                                        "id": raw_emails.get("id", "unknown"),
                                        "subject": raw_emails.get("subject", ""),
                                        "from": raw_emails.get("from", raw_emails.get("sender", "")),
                                        "snippet": raw_emails.get("snippet", raw_emails.get("body", ""))
                                    }
                                    batch_emails = [email_dict]  # Wrap single item in list as a proper dict
                                else:
                                    # Try to convert to a dictionary
                                    try:
                                        email_dict = {
                                            "id": str(getattr(raw_emails, 'id', "unknown")),
                                            "subject": str(getattr(raw_emails, 'subject', "")),
                                            "from": str(getattr(raw_emails, 'from', "")),
                                            "snippet": str(getattr(raw_emails, 'snippet', ""))
                                        }
                                        batch_emails = [email_dict]
                                    except Exception as convert_err:
                                        logger.error(f"Failed to convert single email: {convert_err}")
                                        # Create an empty dict as fallback
                                        batch_emails = [{"id": "unknown", "subject": "", "from": "", "snippet": ""}]
                                break  # Exit the retry loop
                                
                                # Normalize email format to ensure dictionaries with proper keys
                                normalized = []
                                
                                # Add detailed debug logging
                                logger.info(f"Raw emails details - type: {type(raw_emails)}, dir: {dir(raw_emails)[:100]}...")
                                
                                try:
                                    # Just create a basic list of dictionaries with consistent keys
                                    logger.info(f"Starting normalization for {type(raw_emails)}")
                                    
                                    if isinstance(raw_emails, dict):
                                        # Single email as a dict
                                        logger.info("Processing raw_emails as a single dict")
                                        normalized = [{
                                            "id": str(raw_emails.get("id", raw_emails.get("message_id", "unknown"))),
                                            "subject": str(raw_emails.get("subject", "")),
                                            "from": str(raw_emails.get("from", raw_emails.get("sender", ""))),
                                            "snippet": str(raw_emails.get("snippet", raw_emails.get("body", "")))
                                        }]
                                    else:
                                        # Try to treat as a list-like object
                                        logger.info(f"Converting raw_emails of type {type(raw_emails)} to a list of dictionaries")
                                        
                                        # Safety check - make sure raw_emails is iterable
                                        if not hasattr(raw_emails, '__iter__'):
                                            logger.error(f"raw_emails is not iterable: {type(raw_emails)}")
                                            normalized = [{"id": "not-iterable", "subject": "", "from": "", "snippet": ""}]
                                        else:
                                            # Initialize list
                                            normalized = []
                                            
                                            try:
                                                # Debug the raw_emails structure
                                                raw_list = list(raw_emails)  # Convert to list
                                                logger.info(f"Raw list length: {len(raw_list)}")
                                                if len(raw_list) > 0:
                                                    logger.info(f"First raw item type: {type(raw_list[0])}")
                                            except Exception as list_err:
                                                logger.error(f"Error inspecting raw_emails: {list_err}")
                                        
                                            # Safely iterate through items
                                            try:
                                                for i, item in enumerate(raw_emails):
                                                    logger.info(f"Processing item {i}, type: {type(item)}")
                                                    email_dict = {}
                                                    
                                                    # Case 1: It's already a dict
                                                    if isinstance(item, dict):
                                                        email_dict = {
                                                            "id": str(item.get("id", item.get("message_id", f"unknown-{i}"))),
                                                            "subject": str(item.get("subject", "")),
                                                            "from": str(item.get("from", item.get("sender", ""))),
                                                            "snippet": str(item.get("snippet", item.get("body", "")))
                                                        }
                                                        logger.info(f"Item {i} processed as dictionary")
                                                    # Case 2: It's a list/tuple
                                                    elif isinstance(item, (list, tuple)):
                                                        # Better safe way to extract data from list
                                                        item_list = list(item)  # Make sure it's a list
                                                        logger.info(f"Item {i} is a list of length {len(item_list)}")
                                                        
                                                        # Create a dictionary with safe accesses
                                                        email_dict = {
                                                            "id": str(item_list[0]) if len(item_list) > 0 else f"unknown-{i}",
                                                            "subject": str(item_list[1]) if len(item_list) > 1 else "",
                                                            "from": str(item_list[2]) if len(item_list) > 2 else "",
                                                            "snippet": str(item_list[3]) if len(item_list) > 3 else ""
                                                        }
                                                        logger.info(f"Item {i} processed as list into dictionary: {email_dict}")
                                                    # Case 3: It's some other object
                                                    else:
                                                        # Last resort - try to stringify it
                                                        logger.info(f"Processing item {i} as object with attributes")
                                                        email_dict = {
                                                            "id": str(getattr(item, "id", f"unknown-{i}")),
                                                            "subject": str(getattr(item, "subject", "")),
                                                            "from": str(getattr(item, "from_address", getattr(item, "sender", ""))),
                                                            "snippet": str(getattr(item, "body", getattr(item, "snippet", "")))
                                                        }
                                                        logger.info(f"Item {i} processed as object: {email_dict}")
                                                    
                                                    # Make sure ID is not empty
                                                    if not email_dict["id"] or email_dict["id"] == "None":
                                                        email_dict["id"] = f"generated-{i}"
                                                        
                                                    # Add the processed email to our normalized list
                                                    normalized.append(email_dict)
                                                    logger.info(f"Added email {i} to normalized list")
                                                    
                                            except Exception as item_err:
                                                logger.error(f"Error processing items: {item_err}")
                                                # Add a placeholder if the loop failed
                                                normalized.append({"id": f"iteration-error", "subject": "", "from": "", "snippet": ""})
                                except Exception as e:
                                    logger.error(f"Complete failure in email normalization: {e}")
                                    # Create empty emails as a last resort
                                    try:
                                        # Try to at least count how many emails we have
                                        count = len(raw_emails) if hasattr(raw_emails, "__len__") else 10
                                        logger.info(f"Creating {count} placeholder emails")
                                        normalized = [{"id": f"placeholder-{i}", "subject": "", "from": "", "snippet": ""} for i in range(count)]
                                    except:
                                        logger.error("Could not even count emails - using minimal fallback")
                                        normalized = [{"id": "complete-failure", "subject": "", "from": "", "snippet": ""}]
                                        normalized = []
                                
                                batch_emails = normalized
                                logger.info(f"Normalized {len(batch_emails)} emails to dictionary format")
                            # success
                            break
                        except Exception as e:
                            logger.warning(f"Batch get failed for chunk {idx} attempt {attempt}: {e}")
                            if attempt < batch_attempts:
                                await asyncio.sleep(2 ** attempt)
                    if not batch_emails:
                        logger.warning(f"fetch_email_batches failed after {batch_attempts} attempts for chunk {idx}; skipping this chunk.")
                else:
                    logger.warning("Organizer does not support fetch_email_batches; skipping chunk")

                emails.extend(batch_emails)

                # Update progress
                if self.job_manager and job_id:
                    await self.job_manager.update_job_progress(job_id, len(emails), total_ids)

                # small pause between batches to avoid bursts
                await asyncio.sleep(batch_pause_sec)

            logger.info(f"After retrieval attempts, fetched {len(emails)} emails")
            if len(emails) > 0:
                # Debug email structure
                sample_email = emails[0]
                email_type = type(sample_email)
                logger.info(f"Email data type: {email_type}")
                if isinstance(sample_email, list):
                    logger.info(f"Email is a list of length {len(sample_email)}")
                    # Convert list items to dictionaries if they aren't already
                    emails = [dict(zip(['id', 'subject', 'from', 'snippet'], email)) if isinstance(email, (list, tuple)) else email for email in emails]
                    logger.info(f"Converted emails to dictionary format: {type(emails[0])}")
                logger.debug(f"Fetched email sample ids: {[e.get('id') if hasattr(e, 'get') else str(e)[:20] for e in emails[:5]]}")
                tracking_metadata["emails_retrieved"] = True
            else:
                logger.warning("No emails were fetched by any retrieval method")
                tracking_metadata["emails_retrieved"] = False
                
            # Update final tracking state
            if self.job_manager and job_id:
                await self.job_manager.update_job_metadata(job_id, tracking_metadata)

            # Log final results
            if emails:
                logger.info(f"✉️ Retrieved {len(emails)} emails for cataloging")
                # Debug email structure in detail
                sample_email = emails[0]
                logger.info(f"Email data type: {type(sample_email)}")
                logger.info(f"Email sample structure: {str(sample_email)[:200]}")
                
                # If emails are returned as lists or tuples instead of dictionaries, convert them
                # Convert non-dictionary emails to dictionaries
                logger.info("Converting emails to ensure dictionary format")
                normalized_emails = []
                for email in emails:
                    # If it's already a dictionary with get method, keep it as is
                    if hasattr(email, 'get'):
                        normalized_emails.append(email)
                    # If it's a list/tuple, convert to dictionary with safe indexing
                    elif isinstance(email, (list, tuple)):
                        email_dict = {}
                        # Create a dictionary with basic expected fields using safe indexing
                        email_list = list(email)  # Convert tuple to list if needed
                        email_dict["id"] = str(email_list[0]) if len(email_list) > 0 else "unknown"
                        email_dict["subject"] = str(email_list[1]) if len(email_list) > 1 else ""
                        email_dict["from"] = str(email_list[2]) if len(email_list) > 2 else ""
                        email_dict["snippet"] = str(email_list[3]) if len(email_list) > 3 else ""
                        normalized_emails.append(email_dict)
                    # If it's something else, try to convert using attribute access
                    else:
                        normalized_emails.append({
                            "id": str(getattr(email, 'id', None) or id(email)),
                            "subject": str(getattr(email, 'subject', "")),
                            "from": str(getattr(email, 'from_address', getattr(email, 'sender', ""))),
                            "snippet": str(getattr(email, 'body', getattr(email, 'content', "")))
                        })
                
                emails = normalized_emails
                if emails:
                    logger.info(f"After normalization, email type: {type(emails[0])}")
            else:
                logger.warning("⚠️ No emails found for cataloging with the specified criteria")
                emails = []  # Initialize to empty list if None
            
            # ENSURE WE ALWAYS RETURN A LIST OF DICTIONARIES
            try:
                logger.info(f"Starting final normalization, emails type: {type(emails)}")
                
                # If emails is None, set it to an empty list to avoid exceptions
                if emails is None:
                    logger.warning("Emails is None, defaulting to empty list")
                    emails = []
                    
                # Fix for the 'list' object has no attribute 'get' error
                # If emails is a list of lists rather than list of dicts, convert it
                if isinstance(emails, list) and len(emails) > 0 and isinstance(emails[0], list):
                    logger.warning("Emails is a list of lists, converting to list of dicts")
                    emails = [dict(zip(['id', 'subject', 'from', 'snippet'], email)) if isinstance(email, list) else email for email in emails]
                
                logger.info(f"After initial checks, processing {len(emails)} emails")
                normalized_emails = []
                
                for i, email in enumerate(emails):
                    if email is None:
                        continue  # Skip None values
                    
                    # Always convert to dictionary if not already
                    if isinstance(email, dict) and hasattr(email, 'get'):
                        # Already a dictionary
                        normalized_emails.append(email)
                    elif isinstance(email, (list, tuple)):
                        # Convert list/tuple to dictionary
                        email_list = list(email)
                        email_dict = {
                            "id": str(email_list[0]) if len(email_list) > 0 else f"unknown-{i}",
                            "subject": str(email_list[1]) if len(email_list) > 1 else "",
                            "from": str(email_list[2]) if len(email_list) > 2 else "",
                            "snippet": str(email_list[3]) if len(email_list) > 3 else ""
                        }
                        normalized_emails.append(email_dict)
                    else:
                        # Convert object to dictionary
                        email_dict = {
                            "id": str(getattr(email, 'id', None) or f"unknown-{i}"),
                            "subject": str(getattr(email, 'subject', "") or ""),
                            "from": str(getattr(email, 'from', getattr(email, 'sender', ""))),
                            "snippet": str(getattr(email, 'snippet', getattr(email, 'body', "")))
                        }
                        normalized_emails.append(email_dict)
                
                if normalized_emails:
                    logger.info(f"Returning {len(normalized_emails)} normalized dictionary emails")
                    sample = normalized_emails[0]
                    logger.info(f"Sample email type: {type(sample)}, sample: {str(sample)[:100]}")
                    return normalized_emails
                
                # If we didn't get any valid emails, create minimal placeholders
                logger.warning("No valid emails found, creating minimal placeholders")
                return [{"id": f"placeholder-{i}", "subject": "", "from": "", "snippet": "", "minimal": True} for i in range(min(5, len(emails)))]
                
            except Exception as safety_err:
                logger.error(f"Complete failure in safety check: {safety_err}")
                # Return placeholder emails as absolute last resort
                return [{"id": "safety-fallback", "subject": "Error occurred", "from": "", "snippet": ""}]
            # No additional exception handling needed - already handled above
            
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
            # Convert list of emails to list of dictionaries first to avoid 'list' object has no attribute 'get' error
            normalized_emails = []
            logger.info(f"Starting normalization for {len(emails)} emails")
            
            for i, email in enumerate(emails):
                # Create a normalized dictionary for each email regardless of its original structure
                email_dict = {}
                
                try:
                    # CASE 1: Dictionary-like with .get method
                    if hasattr(email, 'get'):
                        email_dict = {
                            "id": email.get("id", f"unknown-{i}"),
                            "subject": email.get("subject", ""),
                            "from": email.get("from", email.get("sender", "")),
                            "snippet": email.get("snippet", email.get("body", "")),
                        }
                    # CASE 2: List or tuple
                    elif isinstance(email, (list, tuple)):
                        email_list = list(email)  # Convert tuple to list if needed
                        email_dict = {
                            "id": str(email_list[0]) if len(email_list) > 0 else f"unknown-{i}",
                            "subject": str(email_list[1]) if len(email_list) > 1 else "",
                            "from": str(email_list[2]) if len(email_list) > 2 else "",
                            "snippet": str(email_list[3]) if len(email_list) > 3 else ""
                        }
                    # CASE 3: Object with attributes
                    else:
                        email_dict = {
                            "id": str(getattr(email, 'id', getattr(email, 'message_id', f"unknown-{i}"))),
                            "subject": str(getattr(email, 'subject', "")),
                            "from": str(getattr(email, 'from', getattr(email, 'sender', getattr(email, 'from_address', "")))),
                            "snippet": str(getattr(email, 'snippet', getattr(email, 'body', getattr(email, 'content', ""))))
                        }
                except Exception as norm_err:
                    logger.error(f"Error normalizing email {i}: {norm_err}, using empty dict instead")
                    email_dict = {"id": f"error-{i}", "subject": "", "from": "", "snippet": ""}
                
                normalized_emails.append(email_dict)
            
            # Replace original emails with normalized dictionaries
            emails = normalized_emails
            logger.info(f"Successfully normalized {len(emails)} emails to dictionaries")
            
            # Now process the normalized emails
            for i, email in enumerate(emails):
                try:
                    # All emails are now dictionaries with these fields
                    subject = email.get("subject", "").lower()
                    sender = email.get("from", "").lower()
                    body = email.get("snippet", "").lower()
                    email_id = email.get("id", f"unknown-{i}")
                    
                    logger.debug(f"Processing email {i}: id={email_id}, subject={subject[:30]}")
                    
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
                    
                    # Store category in email object - now we know it's a dictionary
                    try:
                        # All emails are now dictionaries, so we can directly set the category
                        email["category"] = category
                    except Exception as set_err:
                        logger.warning(f"Could not set category on email object: {set_err}")
                    
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