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

from .interfaces import JobProcessor
from .organizer_factory import OrganizerFactory

logger = logging.getLogger(__name__)

class JobManager:
    """Manages asynchronous email processing jobs."""
    
    def __init__(self, database, organizer_factory: OrganizerFactory):
        """
        Initialize the job manager.
        
        Args:
            database: Database connection
            organizer_factory: Factory for creating Gmail organizers
        """
        self.database = database
        self.organizer_factory = organizer_factory
        self.active_jobs = {}
        self.job_processors = {}
        
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
        
        # Create job record
        job_record = {
            "id": job_id,
            "job_type": job_type,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "parameters": job_config,
            "progress": 0
        }
        
        # Store in active jobs
        self.active_jobs[job_id] = job_record
        
        # Store in database
        query = """
        INSERT INTO email_processing_jobs (id, job_type, status, created_at, parameters)
        VALUES (:id, :job_type, :status, :created_at, :parameters)
        """
        values = {
            "id": job_id,
            "job_type": job_type,
            "status": "pending",
            "created_at": job_record["created_at"],
            "parameters": job_config
        }
        await self.database.execute(query, values)
        
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
            
            results = await processor.process(job_id, parameters)
            
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
        values = {
            "id": job_id,
            "status": status,
            "updated_at": datetime.now().isoformat()
        }
        
        # Add results and error if provided
        if results or error_message:
            query += ", results = :results"
            if results:
                values["results"] = json.dumps(results)
            elif error_message:
                values["results"] = json.dumps({"error": error_message})
            
        # Add progress if provided
        if progress is not None:
            query += ", progress = :progress"
            values["progress"] = str(progress)
            
        # Add WHERE clause
        query += " WHERE id = :id"
        
        await self.database.execute(query, values)
        
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
        job = await self.database.fetch_one(query, {"job_id": job_id})
        
        if job:
            return dict(job)
        else:
            return {"status": "not_found", "message": f"Job {job_id} not found"}
            
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
        
        jobs = await self.database.fetch_all(query, values)
        return [dict(job) for job in jobs]
