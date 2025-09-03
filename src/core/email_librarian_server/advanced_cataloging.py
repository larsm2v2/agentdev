"""
Advanced cataloging implementation using the pipeline of processors:
1. MessageIDRetrievalProcessor
2. MessageIDBatchProcessor 
3. EmailBatchRetrievalProcessor
4. AILabelAssignmentProcessor
5. GmailLabelProcessor

This module provides an enhanced cataloging flow using the processor pipeline.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
import time
import uuid

from fastapi import HTTPException, BackgroundTasks

logger = logging.getLogger(__name__)

async def start_advanced_cataloging(api_router, background_tasks: BackgroundTasks, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Start advanced email cataloging process using the processor pipeline.
    
    Args:
        api_router: The API router instance
        background_tasks: FastAPI background tasks
        parameters: Job parameters including batch size and date range
            
    Returns:
        Job information
    """
    try:
        params = parameters or {}

        # Normalize common keys (frontend may send startDate / endDate)
        start = params.get("start_date") or params.get("startDate")
        end = params.get("end_date") or params.get("endDate")
        if not start or not end:
            raise HTTPException(status_code=400, detail="start_date and end_date are required")

        # Extract cataloging parameters
        batch_size = params.get("batch_size", 20)  # Default batch size for efficient processing
        apply_labels = params.get("apply_labels", True)  # Whether to apply labels at the end
        
        # Create master job for the entire pipeline
        master_job_id = str(uuid.uuid4())
        master_job_config = {
            "job_type": "advanced_cataloging",
            "parameters": params,
            "status": "pending",
            "created_at": time.time(),
            "sub_jobs": []
        }
        
        # Store the master job in the job manager
        if hasattr(api_router.server.job_manager, "active_jobs"):
            api_router.server.job_manager.active_jobs[master_job_id] = master_job_config
            
        # Add the task to process the advanced cataloging pipeline
        background_tasks.add_task(
            process_advanced_cataloging,
            api_router=api_router,
            master_job_id=master_job_id,
            parameters=params,
            background_tasks=background_tasks
        )
        
        return {
            "status": "started",
            "message": "Advanced cataloging pipeline started",
            "job_id": master_job_id
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start advanced cataloging: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_advanced_cataloging(api_router, master_job_id: str, parameters: Dict[str, Any], background_tasks: Optional[Any] = None):
    """
    Process the advanced cataloging pipeline using the individual processors.
    
    This function runs the entire pipeline:
    1. MessageIDRetrievalProcessor - Retrieve message IDs in the date range
    2. MessageIDBatchProcessor - Split message IDs into batches
    3. EmailBatchRetrievalProcessor - Retrieve email content for each batch
    4. AILabelAssignmentProcessor - Assign AI labels to emails
    5. GmailLabelProcessor - Apply labels to Gmail messages
    
    Args:
        api_router: The API router instance
        master_job_id: The ID of the master job
        parameters: Job parameters
        background_tasks: FastAPI background tasks for job creation
    """
    try:
        # Update master job status
        if hasattr(api_router.server.job_manager, "active_jobs"):
            api_router.server.job_manager.active_jobs[master_job_id]["status"] = "running"
            api_router.server.job_manager.active_jobs[master_job_id]["start_time"] = time.time()
        
        logger.info(f"Starting advanced cataloging pipeline for job {master_job_id}")
        
        # Get the job manager
        job_manager = api_router.server.job_manager
        
        # STEP 1: Message ID Retrieval
        logger.info("Step 1: Retrieving message IDs")
        message_id_params = {
            "start_timestamp": parameters.get("start_timestamp"),
            "end_timestamp": parameters.get("end_timestamp"),
            "start_date": parameters.get("start_date") or parameters.get("startDate"),
            "end_date": parameters.get("end_date") or parameters.get("endDate"),
            "max_ids": parameters.get("max_ids", 1000)
        }
        
        # Log the parameters before creating the job
        logger.info(f"Message ID Retrieval - Input parameters: {message_id_params}")
        
        message_id_job = await job_manager.create_job({
            "job_type": "message_id_retrieval",
            "parameters": message_id_params
        }, background_tasks)
        
        # Log the job creation result
        logger.info(f"Message ID Retrieval - Job created with ID: {message_id_job.get('id') or message_id_job.get('job_id')}")
        
        message_id_job_id = message_id_job.get("id") or message_id_job.get("job_id")
        
        # Add to sub-jobs
        if hasattr(job_manager, "active_jobs") and master_job_id in job_manager.active_jobs:
            job_manager.active_jobs[master_job_id]["sub_jobs"].append({
                "job_id": message_id_job_id,
                "job_type": "message_id_retrieval",
                "status": "running"
            })
        
        # Wait for the message ID job to complete
        message_id_result = await wait_for_job_completion(job_manager, message_id_job_id)
        
        # Log the result of the job
        logger.info(f"Message ID Retrieval - Job {message_id_job_id} completed with status: {message_id_result.get('status')}")
        
        if message_id_result.get("status") != "completed":
            logger.error(f"Message ID retrieval failed: {message_id_result.get('error')}")
            raise Exception(f"Message ID retrieval failed: {message_id_result.get('error')}")
        
        # Extract message IDs from the result
        message_ids = message_id_result.get("message_ids", [])
        total_messages = len(message_ids)
        
        # Log the output/result
        logger.info(f"Message ID Retrieval - Retrieved {total_messages} message IDs (sample first 5): {message_ids[:5] if message_ids else []}")
        
        if not message_ids:
            logger.warning("No message IDs found in the specified date range")
            # Update master job status
            if hasattr(job_manager, "active_jobs"):
                job_manager.active_jobs[master_job_id]["status"] = "completed"
                job_manager.active_jobs[master_job_id]["end_time"] = time.time()
                job_manager.active_jobs[master_job_id]["message"] = "No messages found in the specified date range"
            return
        
        logger.info(f"Retrieved {total_messages} message IDs")
        
        # STEP 2: Message ID Batch Processing
        logger.info("Step 2: Batching message IDs")
        batch_size = parameters.get("batch_size", 20)
        
        # Log the parameters before creating the job
        batch_params = {
            "message_ids": message_ids,
            "batch_size": batch_size
        }
        logger.info(f"Message ID Batch - Input parameters: batch_size={batch_size}, message_ids_count={len(message_ids)}")
        
        batch_job = await job_manager.create_job({
            "job_type": "message_id_batch",
            "parameters": batch_params
        }, background_tasks)
        
        # Log the job creation result
        logger.info(f"Message ID Batch - Job created with ID: {batch_job.get('id') or batch_job.get('job_id')}")
        
        batch_job_id = batch_job.get("id") or batch_job.get("job_id")
        
        # Add to sub-jobs
        if hasattr(job_manager, "active_jobs") and master_job_id in job_manager.active_jobs:
            job_manager.active_jobs[master_job_id]["sub_jobs"].append({
                "job_id": batch_job_id,
                "job_type": "message_id_batch",
                "status": "running"
            })
        
        # Wait for the batch job to complete
        batch_result = await wait_for_job_completion(job_manager, batch_job_id)
        
        # Log the result of the job
        logger.info(f"Message ID Batch - Job {batch_job_id} completed with status: {batch_result.get('status')}")
        
        if batch_result.get("status") != "completed":
            logger.error(f"Message ID batching failed: {batch_result.get('error')}")
            raise Exception(f"Message ID batching failed: {batch_result.get('error')}")
        
        # Extract batches from the result
        batches = batch_result.get("batches", [])
        total_batches = len(batches)
        
        # Log the output/result
        logger.info(f"Message ID Batch - Created {total_batches} batches with sizes: {[len(b) for b in batches[:5]]}{' (showing first 5 batches)' if len(batches) > 5 else ''}")
        
        if not batches:
            logger.warning("Failed to batch message IDs")
            # Update master job status
            if hasattr(job_manager, "active_jobs"):
                job_manager.active_jobs[master_job_id]["status"] = "failed"
                job_manager.active_jobs[master_job_id]["end_time"] = time.time()
                job_manager.active_jobs[master_job_id]["error"] = "Failed to batch message IDs"
            return
        
        logger.info(f"Created {total_batches} batches of message IDs")
        
        # STEP 3 & 4: Process each batch to retrieve emails and assign labels
        all_emails = []
        processed_count = 0
        
        # Update master job with total counts
        if hasattr(job_manager, "active_jobs") and master_job_id in job_manager.active_jobs:
            job_manager.active_jobs[master_job_id]["total_batches"] = total_batches
            job_manager.active_jobs[master_job_id]["processed_batches"] = 0
            job_manager.active_jobs[master_job_id]["total_messages"] = total_messages
            job_manager.active_jobs[master_job_id]["processed_messages"] = 0
        
        for batch_index, batch in enumerate(batches):
            try:
                # STEP 3: Email Batch Retrieval
                logger.info(f"Processing batch {batch_index + 1}/{total_batches}")
                
                # Log the parameters before creating the job
                email_batch_params = {
                    "message_ids": batch,
                    "include_raw_body": True
                }
                logger.info(f"Email Batch Retrieval ({batch_index + 1}/{total_batches}) - Input parameters: message_ids_count={len(batch)}, message_ids_sample={batch[:3]}...")
                
                email_batch_job = await job_manager.create_job({
                    "job_type": "email_batch_retrieval",
                    "parameters": email_batch_params
                }, background_tasks)
                
                # Log the job creation result
                logger.info(f"Email Batch Retrieval ({batch_index + 1}/{total_batches}) - Job created with ID: {email_batch_job.get('id') or email_batch_job.get('job_id')}")
                
                email_batch_job_id = email_batch_job.get("id") or email_batch_job.get("job_id")
                
                # Add to sub-jobs
                if hasattr(job_manager, "active_jobs") and master_job_id in job_manager.active_jobs:
                    job_manager.active_jobs[master_job_id]["sub_jobs"].append({
                        "job_id": email_batch_job_id,
                        "job_type": "email_batch_retrieval",
                        "batch_index": batch_index,
                        "status": "running"
                    })
                
                # Wait for the email batch job to complete
                email_batch_result = await wait_for_job_completion(job_manager, email_batch_job_id)
                
                # Log the result of the job
                logger.info(f"Email Batch Retrieval ({batch_index + 1}/{total_batches}) - Job {email_batch_job_id} completed with status: {email_batch_result.get('status')}")
                
                if email_batch_result.get("status") != "completed":
                    logger.warning(f"Email batch retrieval failed for batch {batch_index}: {email_batch_result.get('error')}")
                    continue
                
                # Extract emails from the result
                emails = email_batch_result.get("emails", [])
                
                # Log the output/result
                logger.info(f"Email Batch Retrieval ({batch_index + 1}/{total_batches}) - Retrieved {len(emails)} emails, subject samples: {[e.get('subject', 'No subject') for e in emails[:3]]}")
                
                if not emails:
                    logger.warning(f"No emails retrieved for batch {batch_index}")
                    continue
                
                # STEP 4: AI Label Assignment
                logger.info(f"Assigning AI labels to batch {batch_index + 1}/{total_batches}")
                
                # Log the parameters before creating the job
                ai_label_params = {
                    "emails": emails
                }
                logger.info(f"AI Label Assignment ({batch_index + 1}/{total_batches}) - Input parameters: emails_count={len(emails)}, email_ids_sample={[e.get('id') for e in emails[:3]]}")
                
                ai_label_job = await job_manager.create_job({
                    "job_type": "ai_label_assignment",
                    "parameters": ai_label_params
                }, background_tasks)
                
                # Log the job creation result
                logger.info(f"AI Label Assignment ({batch_index + 1}/{total_batches}) - Job created with ID: {ai_label_job.get('id') or ai_label_job.get('job_id')}")
                
                ai_label_job_id = ai_label_job.get("id") or ai_label_job.get("job_id")
                
                # Add to sub-jobs
                if hasattr(job_manager, "active_jobs") and master_job_id in job_manager.active_jobs:
                    job_manager.active_jobs[master_job_id]["sub_jobs"].append({
                        "job_id": ai_label_job_id,
                        "job_type": "ai_label_assignment",
                        "batch_index": batch_index,
                        "status": "running"
                    })
                
                # Wait for the AI label job to complete
                ai_label_result = await wait_for_job_completion(job_manager, ai_label_job_id)
                
                # Log the result of the job
                logger.info(f"AI Label Assignment ({batch_index + 1}/{total_batches}) - Job {ai_label_job_id} completed with status: {ai_label_result.get('status')}")
                
                if ai_label_result.get("status") != "completed":
                    logger.warning(f"AI label assignment failed for batch {batch_index}: {ai_label_result.get('error')}")
                    continue
                
                # Extract labeled emails
                labeled_emails = ai_label_result.get("emails", [])
                
                # Log the output/result - show the assigned categories
                category_samples = {}
                for e in labeled_emails[:5]:
                    email_id = e.get('id', 'unknown')
                    category = e.get('assigned_category', 'Uncategorized')
                    category_samples[email_id] = category
                
                logger.info(f"AI Label Assignment ({batch_index + 1}/{total_batches}) - Labeled {len(labeled_emails)} emails, category samples: {category_samples}")
                
                # Add to the collection of all processed emails
                all_emails.extend(labeled_emails)
                processed_count += len(labeled_emails)
                
                # Update master job progress
                if hasattr(job_manager, "active_jobs") and master_job_id in job_manager.active_jobs:
                    job_manager.active_jobs[master_job_id]["processed_batches"] = batch_index + 1
                    job_manager.active_jobs[master_job_id]["processed_messages"] = processed_count
                    job_manager.active_jobs[master_job_id]["progress"] = min(
                        100, 
                        int((processed_count / total_messages) * 100) if total_messages else 100
                    )
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_index}: {e}")
                # Continue with the next batch
        
        # STEP 5: Apply Gmail Labels (if requested)
        if parameters.get("apply_labels", True) and all_emails:
            logger.info("Step 5: Applying labels to Gmail messages")
            
            # Create a label mapping based on assigned categories
            label_mapping = {}
            for email in all_emails:
                message_id = email.get("id") or email.get("message_id")
                if message_id and "assigned_category" in email:
                    label_mapping[message_id] = email["assigned_category"]
            
            # Log the parameters before creating the job
            label_count = len(label_mapping) if label_mapping else 0
            sample_mapping = dict(list(label_mapping.items())[:3]) if label_mapping else {}
            logger.info(f"Gmail Label Application - Input parameters: label_mapping for {label_count} emails, "
                       f"samples: {sample_mapping}, default_label='Uncategorized'")

            # Apply labels
            gmail_label_job = await job_manager.create_job({
                "job_type": "gmail_label_application",
                "parameters": {
                    "label_mapping": label_mapping,
                    "default_label": "Uncategorized"
                }
            }, background_tasks)
            
            # Log the job creation result
            gmail_label_job_id = gmail_label_job.get("id") or gmail_label_job.get("job_id")
            logger.info(f"Gmail Label Application - Job created with ID: {gmail_label_job_id}")
            
            # Add to sub-jobs
            if hasattr(job_manager, "active_jobs") and master_job_id in job_manager.active_jobs:
                job_manager.active_jobs[master_job_id]["sub_jobs"].append({
                    "job_id": gmail_label_job_id,
                    "job_type": "gmail_label_application",
                    "status": "running"
                })
            
            # Wait for the Gmail label job to complete
            gmail_label_result = await wait_for_job_completion(job_manager, gmail_label_job_id)
            
            # Log the result of the job
            logger.info(f"Gmail Label Application - Job {gmail_label_job_id} completed with status: {gmail_label_result.get('status')}")
            
            if gmail_label_result.get("status") != "completed":
                logger.warning(f"Gmail label application failed: {gmail_label_result.get('error')}")
            else:
                labeled_count = gmail_label_result.get('labeled_count', 0)
                logger.info(f"Gmail Label Application - Successfully applied labels to {labeled_count} emails")
                # Log any additional details if available
                if 'label_counts' in gmail_label_result:
                    logger.info(f"Gmail Label Application - Label distribution: {gmail_label_result['label_counts']}")
        
        # Update master job status
        if hasattr(job_manager, "active_jobs"):
            job_manager.active_jobs[master_job_id]["status"] = "completed"
            job_manager.active_jobs[master_job_id]["end_time"] = time.time()
            job_manager.active_jobs[master_job_id]["processed_count"] = processed_count
            job_manager.active_jobs[master_job_id]["total_count"] = total_messages
            job_manager.active_jobs[master_job_id]["message"] = f"Successfully processed {processed_count} of {total_messages} emails"
        
        logger.info(f"Advanced cataloging pipeline completed for job {master_job_id}")
        
    except Exception as e:
        logger.error(f"Advanced cataloging pipeline failed: {e}")
        # Update master job status
        if hasattr(api_router.server.job_manager, "active_jobs") and master_job_id in api_router.server.job_manager.active_jobs:
            api_router.server.job_manager.active_jobs[master_job_id]["status"] = "failed"
            api_router.server.job_manager.active_jobs[master_job_id]["end_time"] = time.time()
            api_router.server.job_manager.active_jobs[master_job_id]["error"] = str(e)

async def wait_for_job_completion(job_manager, job_id: str, timeout: int = 600, poll_interval: int = 2) -> Dict[str, Any]:
    """
    Wait for a job to complete with timeout.
    
    Args:
        job_manager: The job manager
        job_id: The job ID to wait for
        timeout: Maximum time to wait in seconds
        poll_interval: How often to check job status in seconds
        
    Returns:
        The job result
    """
    start_time = time.time()
    logger.info(f"wait_for_job_completion: Waiting for job {job_id} to complete (timeout: {timeout}s)")
    
    poll_count = 0
    while time.time() - start_time < timeout:
        poll_count += 1
        # Get job status
        job_status = await job_manager.get_job_status(job_id)
        
        if poll_count % 5 == 0 or job_status.get("status") in ["completed", "failed"]:
            logger.info(f"wait_for_job_completion: Job {job_id} status after {int(time.time() - start_time)}s: {job_status.get('status')} - {job_status.get('message', '')}")
        
        if job_status.get("status") in ["completed", "failed"]:
            logger.info(f"wait_for_job_completion: Job {job_id} finished with status: {job_status.get('status')}")
            return job_status
        
        # Wait before checking again
        await asyncio.sleep(poll_interval)
    
    # If we get here, the job timed out
    logger.error(f"❌ wait_for_job_completion: Job {job_id} timed out after {timeout} seconds")
    return {
        "status": "failed",
        "error": f"Job {job_id} timed out after {timeout} seconds"
    }
