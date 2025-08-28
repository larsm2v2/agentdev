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
        job_record = {
            "id": job_id,
            "job_type": job_type,
            "status": "pending",
            "created_at": created_at_dt.isoformat(),
            "parameters": job_config,
            "progress": 0
        }
        
        # Store in active jobs
        self.active_jobs[job_id] = job_record
        
        # Store in database
        query = """
        INSERT INTO email_processing_jobs (id, job_type, status, created_at, config, parameters)
        VALUES (:id, :job_type, :status, :created_at, :config, :parameters)
        """
        values = {
            "id": job_id,
            "job_type": job_type,
            "status": "pending",
            # pass a real datetime to the DB driver
            "created_at": created_at_dt,
            # store config and parameters as JSON text for compatibility with DB driver
            "config": json.dumps(job_config),
            "parameters": json.dumps(job_config)
        }
        if not self.database:
            logger.warning("No database connection - job will only exist in memory")
    
        if self.database is not None:
            await self.database.execute(query, values)
        else:
            logger.error("Database connection is not available. Cannot update job status.")
        
        # Schedule the job for processing
        background_tasks.add_task(self.process_job, job_id, job_config)
        
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
        job_type = parameters.get("job_type", "unknown")

        # Update job status
        await self.update_job_status(job_id, "processing")

        # Get processor for job type
        processor = self.job_processors.get(job_type)
        if not processor:
            logger.error(f"No processor registered for job type: {job_type}")
            await self.update_job_status(job_id, "failed", error_message=f"No processor for job type: {job_type}")
            return {
                "status": "error",
                "message": f"No processor for job type: {job_type}"
            }

        try:
            # Process the job
            logger.info(f"Processing job {job_id} of type {job_type}")
            start_time = time.time()

            # Many callers pass a job_config dict with keys like {"job_type": ..., "parameters": {...}}
            # Unwrap that structure when present so processors receive the expected parameters dict.
            proc_params = parameters.get("parameters", parameters) if isinstance(parameters, dict) else parameters

            results = await processor.process(job_id, proc_params)

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
            return {
                "status": "error",
                "message": f"Job processing failed: {str(e)}"
            }
            
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
        values = {
            "id": job_id,
            "status": status,
            "updated_at": updated_at_dt
        }
        
        # Add results and error if provided
        if results or error_message:
            query += ", results = :results"
            if results:
                values["results"] = json.dumps(results) if isinstance(results, dict) else str(results)
            elif error_message:
                values["results"] = json.dumps({"error": error_message})
            
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
            return self.active_jobs[job_id]
            
        # Check database
        query = "SELECT * FROM email_processing_jobs WHERE id = :job_id"
        if self.database is not None:
            job = await self.database.fetch_one(query, {"job_id": job_id})
            if job:
                return dict(job)
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




