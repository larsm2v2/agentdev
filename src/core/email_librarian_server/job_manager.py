"""
Job manager for processing email-related tasks.
"""

import logging
import time
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, Awaitable
import asyncio

from fastapi import WebSocket

from .interfaces import JobProcessor
from .organizer_factory import OrganizerFactory
from .storage_manager import StorageManager
from databases import Database as JobsDatabase

logger = logging.getLogger(__name__)

class JobManager:
    """Manages asynchronous email processing jobs."""

    def __init__(self, storage_manager: StorageManager, organizer_factory: OrganizerFactory):
        """
        Initialize the job manager.
        
        Args:
            database: Database connection
            organizer_factory: Factory for creating Gmail organizers
        """
        self.storage_manager = storage_manager
        self.database = storage_manager.database if storage_manager else None
        self.organizer_factory = organizer_factory
        self.active_jobs = {}
        self.job_processors = {}
        self.progress_clients = {}

    def register_processor(self, job_type: str, processor: JobProcessor):
        """
        Register a job processor for a specific job type.
        
        Args:
            job_type: Type of job
            processor: Job processor implementation
        """
        self.job_processors[job_type] = processor
        logger.info(f"Registered processor for job type: {job_type}")
        
    async def create_job(self, job_config: Dict[str, Any], background_tasks) -> Dict[str, Any]:
        """
        Create a new job and schedule it for processing.
        
        Args:
            job_config: Job configuration
            background_tasks: FastAPI background tasks
            
        Returns:
            Job details with ID
        """
        job_id = str(uuid.uuid4())
        job_type = job_config.get("job_type", "unknown")
        
         # Validate processor exists
        if job_type not in self.job_processors:
            logger.warning(f"No processor registered for job type: {job_type}")

        # Create job record
        # Use a datetime object for DB writes, but keep an ISO string for the in-memory record
        created_at_dt = datetime.now()
        # If callers provide an estimated total (e.g. from get_message_ids_range), capture it
        params = job_config.get("parameters") if isinstance(job_config, dict) else {}
        estimated_total = None
        if isinstance(params, dict):
            estimated_total = params.get("estimated_total_emails") or params.get("max_emails")

        job_record = {
            "id": job_id,
            "job_type": job_type,
            "status": "pending",
            "created_at": created_at_dt.isoformat(),
            "parameters": job_config,
            "progress": 0,
            "processed_count": 0,
            "total_count": int(estimated_total) if estimated_total is not None else None,
        }
        
        # Store in active jobs
        self.active_jobs[job_id] = job_record
        
        # Store in database
        # Insert with optional processed_count/total_count/progress when available
        query = """
        INSERT INTO email_processing_jobs (id, job_type, status, created_at, config, parameters, processed_count, total_count, progress)
        VALUES (:id, :job_type, :status, :created_at, :config, :parameters, :processed_count, :total_count, :progress)
        """
        values = {
            "id": job_id,
            "job_type": job_type,
            "status": "pending",
            # pass a real datetime to the DB driver
            "created_at": created_at_dt,
            # store config and parameters as JSON text for compatibility with DB driver
            "config": json.dumps(job_config),
            "parameters": json.dumps(job_config),
            "processed_count": 0,
            "total_count": int(estimated_total) if estimated_total is not None else None,
            "progress": 0,
        }
        if not self.database:
            logger.warning("No database connection - job will only exist in memory")
    
        if self.database is not None:
            await self.database.execute(query, values)
        else:
            logger.error("Database connection is not available. Cannot update job status.")
        
        # Schedule the job for processing
        # Log the job_config shape for debugging data-flow
        try:
            preview = {k: (v if k != 'parameters' else list(v.keys()) if isinstance(v, dict) else type(v)) for k, v in (job_config.items() if isinstance(job_config, dict) else [])}
        except Exception:
            preview = str(type(job_config))
        logger.info(f"JobManager.create_job: scheduling job {job_id} type={job_type} preview={preview}")
        
        # Enhanced debugging
        if background_tasks is None:
            logger.error(f"❌ JobManager.create_job: background_tasks is None for job {job_id}! Job will not be processed.")
        else:
            logger.info(f"✅ JobManager.create_job: adding task to background_tasks for job {job_id}")
            
        # IMPORTANT FIX: Start processing the job immediately in this request handler
        # Don't wait for background_tasks to pick it up
        try:
            # Still add to background_tasks for proper FastAPI request handling
            background_tasks.add_task(lambda: None)  # Add dummy task
            logger.info(f"✅ JobManager.create_job: added dummy task to background_tasks")
            
            # Start the job processing in a separate task
            import asyncio
            asyncio.create_task(self.process_job(job_id, job_config))
            logger.info(f"✅ JobManager.create_job: created asyncio task for job {job_id}")
        except Exception as e:
            logger.error(f"❌ JobManager.create_job: Failed to create task for job {job_id}: {e}", exc_info=True)
        
        # Return the job details
        return {
            "job_id": job_id,
            "status": "pending",
            "message": f"Job scheduled for processing: {job_type}"
        }
        
    async def process_job(self, job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a job using the appropriate processor.
        
        Args:
            job_id: Job identifier
            parameters: Job parameters
            
        Returns:
            Job results
        """
        logger.info(f"⚡ JobManager.process_job: STARTED for job {job_id}")
        job_type = parameters.get("job_type", "unknown")

        # Update job status
        logger.info(
            f"JobManager.process_job: starting job {job_id} with raw parameters keys={list(parameters.keys()) if isinstance(parameters, dict) else type(parameters)}"
        )
        try:
            await self.update_job_status(job_id, "processing")
            logger.info(f"✅ JobManager.process_job: updated status to 'processing' for job {job_id}")
        except Exception as e:
            logger.error(f"❌ JobManager.process_job: Failed to update job status: {e}")

        # Get processor for job type
        processor = self.job_processors.get(job_type)
        if not processor:
            logger.error(f"❌ JobManager.process_job: No processor registered for job type: {job_type}")
            logger.error(f"Available processors: {list(self.job_processors.keys())}")
            await self.update_job_status(job_id, "failed", error_message=f"No processor for job type: {job_type}")
            return {"status": "error", "message": f"No processor for job type: {job_type}"}
        
        logger.info(f"✅ JobManager.process_job: Found processor for job type: {job_type}")

        try:
            # Process the job
            logger.info(f"Processing job {job_id} of type {job_type}")
            start_time = time.time()

            # Many callers pass a job_config dict with keys like {"job_type": ..., "parameters": {...}}
            # Unwrap that structure when present so processors receive the expected parameters dict.
            proc_params = parameters.get("parameters", parameters) if isinstance(parameters, dict) else parameters
            # Normalize: ensure proc_params is a dict when possible
            if not isinstance(proc_params, dict):
                logger.warning(f"JobManager.process_job: proc_params is not a dict (type={type(proc_params)}); wrapping in dict")
                proc_params = {"value": proc_params}
            logger.info(
                f"JobManager.process_job: invoking processor for job {job_id} type={job_type} with proc_params keys={list(proc_params.keys())}"
            )

            logger.info(f"⏳ JobManager.process_job: Calling processor.process for job {job_id}")
            try:
                results = await processor.process(job_id, proc_params)
                logger.info(f"✅ JobManager.process_job: processor.process completed for job {job_id}")
            except Exception as e:
                logger.error(f"❌ JobManager.process_job: processor.process failed with error: {e}", exc_info=True)
                raise

            # Calculate execution time
            execution_time = time.time() - start_time

            # Update job status
            await self.update_job_status(job_id, "completed", results=results)

            # Log completion
            logger.info(f"Job {job_id} completed in {execution_time:.2f}s")

            return results
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            await self.update_job_status(job_id, "failed", error_message=str(e))
            return {"status": "error", "message": f"Job processing failed: {str(e)}"}
            
    async def update_job_status(self, job_id: str, status: str, results: Optional[Dict[str, Any]] = None, 
                               error_message: Optional[str] = None, progress: Optional[int] = None):
        """
        Update the status of a job in the database and active jobs.
        
        Args:
            job_id: Job identifier
            status: New status
            results: Optional job results
            error_message: Optional error message
            progress: Optional progress percentage
        """
        # Update active jobs
        if job_id in self.active_jobs:
            self.active_jobs[job_id]["status"] = status
            if progress is not None:
                self.active_jobs[job_id]["progress"] = progress
            if results:
                self.active_jobs[job_id]["results"] = results
            if error_message:
                self.active_jobs[job_id]["error"] = error_message
                
        # Update database
        query = """
        UPDATE email_processing_jobs 
        SET status = :status, 
            updated_at = :updated_at
        """
        # Use datetime object for DB; keep ISO string for in-memory record
        updated_at_dt = datetime.now()
        values: Dict[str, Any] = {
            "id": job_id,
            "status": status,
            "updated_at": updated_at_dt
        }

        # Add results and/or error if provided. Always store a valid JSON string in the
        # results column to avoid database "invalid input syntax for type json" errors.
        if results is not None or error_message:
            query += ", results = :results"
            try:
                if results is None and error_message:
                    # Only an error message was provided
                    payload = {"status": "failed", "error": str(error_message)}
                elif isinstance(results, dict):
                    payload = results
                else:
                    # Results might be a primitive or other type; coerce into a dict
                    payload = {"result": results}

                # Serialize with default=str to safely coerce any non-serializable values
                values["results"] = json.dumps(payload, ensure_ascii=False, default=str)
            except Exception as e:
                # Last-resort: store a minimal JSON object describing the failure
                logger.warning(f"Failed to JSON-serialize results for job {job_id}: {e}")
                values["results"] = json.dumps({"error": "results serialization failure", "info": str(e)})

        # Add progress if provided
        if progress is not None:
            query += ", progress = :progress"
            values["progress"] = progress

        # Add WHERE clause
        query += " WHERE id = :id"

        if self.database is not None:
            # Execute DB update with datetime object
            await self.database.execute(query, values)
        else:
            logger.error("Database connection is not available. Cannot update job status.")

    async def update_job_metadata(self, job_id: str, metadata: Dict[str, Any]):
        """Update arbitrary metadata for a job in memory and persist to DB (stored inside results.metadata).

        This merges provided metadata into any existing `metadata` key inside the `results` JSON column.
        """
        try:
            # Update in-memory record
            if job_id in self.active_jobs:
                jm = self.active_jobs[job_id]
                existing_meta = jm.get("metadata") or {}
                if not isinstance(existing_meta, dict):
                    existing_meta = {}
                existing_meta.update(metadata or {})
                jm["metadata"] = existing_meta
                # If metadata includes total_count, reflect it in the in-memory job record
                try:
                    if metadata and isinstance(metadata, dict) and "total_count" in metadata:
                        tc = metadata.get("total_count")
                        jm["total_count"] = int(tc) if tc is not None else jm.get("total_count")
                        logger.info(f"JobManager: set in-memory total_count for {job_id} => {jm.get('total_count')}")
                except Exception:
                    pass

            # Persist into DB by merging into `results` JSON column if database is available
            if self.database:
                try:
                    row = await self.database.fetch_one("SELECT results FROM email_processing_jobs WHERE id = :job_id", {"job_id": job_id})
                    existing_results = {}
                    if row and row["results"]:
                        try:
                            existing_results = json.loads(row["results"]) if isinstance(row["results"], str) else (row["results"] or {})
                        except Exception:
                            existing_results = {"raw_results": row["results"]}

                    # Ensure dict
                    if not isinstance(existing_results, dict):
                        existing_results = {"value": existing_results}

                    meta = existing_results.get("metadata") or {}
                    if not isinstance(meta, dict):
                        meta = {}
                    meta.update(metadata or {})
                    existing_results["metadata"] = meta

                    await self.database.execute(
                        """
                        UPDATE email_processing_jobs
                        SET results = :results
                        WHERE id = :id
                        """,
                        {"results": json.dumps(existing_results), "id": job_id}
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist job metadata for {job_id}: {e}")
        except Exception as e:
            logger.exception(f"Error updating job metadata for {job_id}: {e}")
        
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status information
        """
        # Check active jobs first
        if job_id in self.active_jobs:
            # Return a copy and merge any `results` dict into top-level for convenience
            job_copy = dict(self.active_jobs[job_id])
            try:
                res = job_copy.get("results")
                if isinstance(res, dict):
                    for k, v in res.items():
                        if k not in job_copy:
                            job_copy[k] = v
            except Exception:
                pass
            return job_copy
            
        # Check database
        query = "SELECT * FROM email_processing_jobs WHERE id = :job_id"
        if self.database is not None:
            job = await self.database.fetch_one(query, {"job_id": job_id})
            if job:
                result = dict(job)
                # If results column exists and is JSON text, parse it and merge useful keys
                try:
                    raw_results = result.get("results")
                    parsed = None
                    if raw_results is not None:
                        if isinstance(raw_results, str):
                            try:
                                parsed = json.loads(raw_results)
                            except Exception:
                                # Keep as raw string
                                parsed = {"raw_results": raw_results}
                        elif isinstance(raw_results, dict):
                            parsed = raw_results

                    if isinstance(parsed, dict):
                        # Attach parsed results under 'results' and merge top-level non-conflicting keys
                        result["results"] = parsed
                        for k, v in parsed.items():
                            if k not in result:
                                result[k] = v
                    else:
                        # Store whatever we could parse
                        result["results"] = parsed
                except Exception:
                    # If anything goes wrong parsing results, keep original row
                    pass
                return result
            else:
                return {"status": "not_found", "message": f"Job {job_id} not found"}
        else:
            logger.error("Database connection is not available. Cannot retrieve job status.")
            return {"status": "error", "message": "Database connection is not available."}
            
        
            
    async def list_jobs(self, limit: int = 100, job_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List jobs in the system.
        
        Args:
            limit: Maximum number of jobs to return
            job_type: Filter by job type
            
        Returns:
            List of job records
        """
        query = "SELECT * FROM email_processing_jobs"
        values = {}
        
        if job_type:
            query += " WHERE job_type = :job_type"
            values["job_type"] = job_type
            
        query += " ORDER BY created_at DESC LIMIT :limit"
        values["limit"] = limit

        if self.database is not None:
            jobs = await self.database.fetch_all(query, values)
            return [dict(job) for job in jobs]
        else:
            logger.error("Database connection is not available. Cannot list jobs.")
            return []

    def register_progress_client(self, job_id: str, websocket: WebSocket):
        """Register a WebSocket client for progress updates."""
        if job_id not in self.progress_clients:
            self.progress_clients[job_id] = set()
        self.progress_clients[job_id].add(websocket)

    def unregister_progress_client(self, job_id: str, websocket: WebSocket):
        """Unregister a WebSocket client."""
        if job_id in self.progress_clients and websocket in self.progress_clients[job_id]:
            self.progress_clients[job_id].remove(websocket)

    async def cancel_job(self, job_id: str) -> bool:
        """Request cancellation of a running or pending job.

        This marks the job as cancelled (best-effort). Processors should
        periodically check job status via get_job_status and respect a
        cancelled state if they want to stop early.
        """
        # Update in-memory state
        job = self.active_jobs.get(job_id)
        if not job:
            # If not active in memory, try DB lookup
            if self.database:
                row = await self.database.fetch_one("SELECT status FROM email_processing_jobs WHERE id = :job_id", {"job_id": job_id})
                if not row:
                    return False
            else:
                return False

        # Mark cancelled in-memory
        if job:
            job["status"] = "cancelled"
            job["updated_at"] = datetime.now().isoformat()

        # Persist to DB
        if self.database:
            try:
                await self.database.execute(
                    """
                    UPDATE email_processing_jobs
                    SET status = :status, updated_at = :updated_at
                    WHERE id = :job_id
                    """,
                    {"status": "cancelled", "updated_at": datetime.now(), "job_id": job_id}
                )
            except Exception as e:
                logger.warning(f"Failed to persist job cancellation for {job_id}: {e}")

        # Notify any registered websocket clients about the change
        if job_id in self.progress_clients:
            try:
                status = await self.get_job_status(job_id)
                for websocket in list(self.progress_clients[job_id]):
                    try:
                        await websocket.send_json(status)
                    except Exception:
                        self.progress_clients[job_id].discard(websocket)
            except Exception:
                logger.exception("Failed to notify progress clients of cancellation")

        logger.info(f"Job {job_id} cancellation requested")
        return True
        
    async def update_job_progress(self, job_id: str, processed: int, total: int):
        """Update job progress and notify clients."""
        # Update job record
        job = self.active_jobs.get(job_id)
        if job:
            job["processed_count"] = processed
            job["total_count"] = total
            job["progress"] = processed / total if total > 0 else 0
            # keep human-friendly timestamp in memory
            job["updated_at"] = datetime.now().isoformat()
            logger.info(f"📊 Job {job_id}: {processed}/{total} ({job['progress']:.1%})")
            
            # Store in database if available
            if self.database:
                try:
                    await self.database.execute(
                        """
                        UPDATE email_processing_jobs 
                        SET 
                            processed_count = :processed, 
                            total_count = :total,
                            progress = :progress,
                            updated_at = :updated_at
                        WHERE id = :job_id
                        """,
                        {
                            "processed": processed,
                            "total": total,
                            "progress": processed / total if total > 0 else 0,
                            # pass datetime object
                            "updated_at": datetime.now(),
                            "job_id": job_id
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to update job progress in database: {e}")
                
            # Notify WebSocket clients
            if hasattr(self, 'progress_clients') and job_id in self.progress_clients:
                status = await self.get_job_status(job_id)
                for websocket in list(self.progress_clients[job_id]):
                    try:
                        await websocket.send_json(status)
                    except Exception as e:
                        logger.error(f"Failed to send progress update: {e}")
                        # Client likely disconnected
                        self.progress_clients[job_id].discard(websocket)

    def get_active_job_id(self, job_type: str) -> Optional[str]:
        #Get the ID of an active job of the specified type.
        for job_id, job in self.active_jobs.items():
            if job.get("job_type") == job_type and job.get("status") in ["pending", "processing"]:
                return job_id
        return None

    def get_most_recent_job_id(self, job_type: str) -> Optional[str]:
        """
        Get the ID of the most recent job of the specified type (including completed jobs).
        
        Args:
            job_type: Type of job to find
            
        Returns:
            Job ID of the most recent job, or None if no jobs of that type exist
        """
        most_recent_job = None
        most_recent_time = None
        
        for job_id, job in self.active_jobs.items():
            if job.get("job_type") == job_type:
                job_time = job.get("created_at")
                if job_time:
                    # Parse the ISO string to compare times
                    try:
                        from datetime import datetime
                        current_time = datetime.fromisoformat(job_time.replace('Z', '+00:00'))
                        if most_recent_time is None or current_time > most_recent_time:
                            most_recent_time = current_time
                            most_recent_job = job_id
                    except (ValueError, AttributeError):
                        # If we can't parse the time, use this job as fallback
                        if most_recent_job is None:
                            most_recent_job = job_id
        
        return most_recent_job




