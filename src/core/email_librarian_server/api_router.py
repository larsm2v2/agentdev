"""
API router for the Enhanced Email Librarian system.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter as FastAPIRouter, BackgroundTasks, Body, Depends, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
import asyncio

# Import the advanced cataloging implementation
from .advanced_cataloging import start_advanced_cataloging

logger = logging.getLogger(__name__)

# Pydantic models
class JobConfig(BaseModel):
    """Job configuration model."""
    
    job_type: str
    parameters: Dict[str, Any] = {}


class EmailProcessingResult(BaseModel):
    """Email processing result model."""
    
    job_id: str
    status: str
    message: str
    results: Optional[Dict[str, Any]] = None


class VectorSearchRequest(BaseModel):
    """Vector search request model."""
    
    query: str
    limit: int = 10
    filters: Optional[Dict[str, Any]] = None


class APIRouter:
    """API router for the Enhanced Email Librarian system."""
    
    def __init__(self, server):
        """
        Initialize the API router.
        
        Args:
            server: Main server instance
        """
        self.server = server
        self.router = FastAPIRouter(prefix="/api")
        self.setup_routes()
        
    def setup_routes(self):
        """Set up API routes."""
        # Job management routes
        self.router.post("/jobs/create", response_model=EmailProcessingResult)(self.create_job)
        self.router.get("/jobs/{job_id}", response_model=EmailProcessingResult)(self.get_job_status)
        self.router.get("/jobs", response_model=List[EmailProcessingResult])(self.list_jobs)

        # Gmail authentication routes
        self.router.get("/auth/status")(self.get_auth_status)
        self.router.get("/auth/login")(self.login)
        self.router.get("/auth/logout")(self.logout)

        # Email search routes
        self.router.post("/search/vector")(self.search_similar_emails)
        self.router.get("/search/query")(self.search_emails)

        # System routes
        self.router.get("/system/status")(self.get_system_status)
        self.router.get("/system/activity")(self.get_activity_log)

        # Web Socket
        self.router.websocket("/ws/jobs/{job_id}")(self.job_progress_websocket)

        # Polling Progress
        self.router.get("/functions/shelving/progress")(self.get_shelving_progress)

        # Cataloging endpoints
        # Standard cataloging - uses a single processor approach
        self.router.post("/functions/cataloging/start")(self.start_cataloging)
        # Advanced cataloging - uses the processor pipeline for more flexibility and control:
        # 1. MessageIDRetrievalProcessor - Get message IDs in date range
        # 2. MessageIDBatchProcessor - Split message IDs into batches
        # 3. EmailBatchRetrievalProcessor - Retrieve email content for each batch
        # 4. AILabelAssignmentProcessor - Assign AI labels to emails
        # 5. GmailLabelProcessor - Apply labels to Gmail
        self.router.post("/functions/cataloging/advanced")(self.start_advanced_cataloging)
        self.router.get("/functions/cataloging/progress")(self.get_cataloging_progress)
        
        # Shelving endpoints
        self.router.post("/functions/shelving/start")(self.start_shelving)
        self.router.get("/functions/cataloging/categories")(self.get_categories)

        # Reclassification labels endpoint (frontend expects GET /api/labels)
        self.router.get("/labels")(self.get_labels)
        # Management: force-refresh labels from Gmail organizer and persist
        self.router.post("/labels/refresh")(self.refresh_labels)

        # Generic function toggle endpoints (shelving, cataloging, reclassification, workflows)
        # frontend expects POST /api/<function>/toggle
        self.router.post("/{function_name}/toggle")(self.toggle_function)

        # Expose function status
        self.router.get("/{function_name}/status")(self.get_function_status)

        # Admin: list all function states
        self.router.get("/functions")(self.list_functions)

        # Job cancellation
        self.router.post("/jobs/{job_id}/cancel")(self.cancel_job)
        
    # Expose test endpoints
        self.router.get("/test/get_message_ids_range")(self.get_message_ids_range)
        self.router.post("/test/batch_message_ids")(self.batch_message_ids)
        self.router.post("/test/retrieve_sample_batch_emails")(self.retrieve_sample_batch_emails)
        self.router.post("/test/retrieve_sample_batch_emails_raw")(self.retrieve_sample_batch_emails_raw)

    async def create_job(self, job_config: JobConfig, background_tasks: BackgroundTasks):
        """
        Create a new email processing job.
        
        Args:
            job_config: Job configuration
            background_tasks: FastAPI background tasks
            
        Returns:
            Job creation result
        """
        return await self.server.job_manager.create_job(job_config.model_dump(), background_tasks)
        
    async def get_job_status(self, job_id: str):
        """
        Get job status by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status information
        """
        status = await self.server.job_manager.get_job_status(job_id)
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return status
        
    async def list_jobs(self, limit: int = 100, job_type: Optional[str] = None):
        """
        List jobs in the system.
        
        Args:
            limit: Maximum number of jobs to return
            job_type: Filter by job type
            
        Returns:
            List of job records
        """
        return await self.server.job_manager.list_jobs(limit=limit, job_type=job_type)
        
    async def get_auth_status(self):
        """
        Get Gmail authentication status.
        
        Returns:
            Authentication status information
        """
        credentials = self.server.auth_manager.get_credentials()
        return {
            "authenticated": credentials is not None and credentials.valid,
            "expired": credentials is not None and credentials.expired,
            "has_refresh_token": credentials is not None and credentials.refresh_token is not None
        }
        
    async def login(self):
        """
        Start Gmail authentication process.
        
        Returns:
            Authentication result
        """
        credentials = self.server.auth_manager.authenticate()
        if credentials:
            return {"status": "success", "message": "Authentication successful"}
        else:
            raise HTTPException(status_code=401, detail="Authentication failed")
            
    async def logout(self):
        """
        Log out and clear credentials.
        
        Returns:
            Logout result
        """
        # In a real implementation, we'd invalidate the token
        return {"status": "success", "message": "Logged out"}
        
    async def search_similar_emails(self, search_request: VectorSearchRequest):
        """
        Search for similar emails using vector similarity.
        
        Args:
            search_request: Vector search request
            
        Returns:
            Search results
        """
        # In a real implementation, we'd get embedding from LLM and search
        return {"status": "success", "message": "Search completed", "results": []}
        
    async def search_emails(self, query: str, max_results: int = 100):
        """
        Search emails by query string.
        
        Args:
            query: Gmail query string
            max_results: Maximum number of results
            
        Returns:
            Search results
        """
        # Create organizer
        gmail_organizer = self.server.organizer_factory.create_organizer()
        
        # Search messages
        search_result = gmail_organizer.search_messages(query=query, max_results=max_results)
        return search_result
        
    async def get_system_status(self):
        """
        Get system status information.
        
        Returns:
            System status information
        """
        return {
            "status": "operational",
            "services": {
                "database": self.server.storage_manager.database is not None,
                "vector_db": self.server.storage_manager.qdrant_client is not None,
                "gmail": self.server.organizer_factory.organizers_available
            },
            "version": "2.0.0",
            "active_jobs": len(self.server.job_manager.active_jobs)
        }
        
    async def get_activity_log(self, limit: int = 100):
        """
        Get system activity log.
        
        Args:
            limit: Maximum number of activities to return
            
        Returns:
            Activity log entries
        """
        # Activity log storage has been disabled; return in-memory/broadcast-only activities
        return {"activities": []}

    async def job_progress_websocket(self, websocket: WebSocket, job_id: str):
        """WebSocket endpoint for real-time job progress updates."""
        await websocket.accept()
        try:
            # Register this connection with job manager
            self.server.job_manager.register_progress_client(job_id, websocket)
            
            # Keep connection open
            while True:
                # Wait for client messages (ping)
                data = await websocket.receive_text()
                if data == "ping":
                    # Send current status
                    status = await self.server.job_manager.get_job_status(job_id)
                    await websocket.send_json(status)
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            self.server.job_manager.unregister_progress_client(job_id, websocket)
            logger.info(f"Client disconnected from job {job_id}")
    
    async def get_shelving_progress(self):
        #Get current progress of active shelving job.
        recent_job_id = self.server.job_manager.get_most_recent_job_id("shelving")
        if not recent_job_id:
            return {"status": "no_active_job", "progress": 0}
            
        job_status = await self.server.job_manager.get_job_status(recent_job_id)
        
        # Extract progress information
        processed = job_status.get("processed_count", 0)
        total = job_status.get("total_count", 1)  # Prevent division by zero
        progress = processed / total if total > 0 else 0
        
        return {
            "status": job_status.get("status", "unknown"),
            "progress": progress,
            "processed_count": processed,
            "total_count": total,
            "job_id": recent_job_id
        }
        
    async def start_shelving(self, background_tasks: BackgroundTasks, parameters: Dict[str, Any] = Body(...)):
        """
        Start email shelving process.
        
        Args:
            background_tasks: FastAPI background tasks
            parameters: Job parameters including batch size and date range
            
        Returns:
            Job information
        """
        try:
            params = parameters or {}

            # normalize common keys (frontend may send startDate / endDate)
            start = params.get("start_date") or params.get("startDate")
            end = params.get("end_date") or params.get("endDate")
            if not start or not end:
                raise HTTPException(status_code=400, detail="start_date and end_date are required")

            # Estimate total message count using existing helper so job metadata can show progress%
            total_ids = None
            try:
                # reuse existing helper to get message ids count
                res = await self.get_message_ids_range(start, end, params.get("batch_size", 50))
                logger.info(f"Estimated total emails for shelving between {start} and {end}: {res.get('count', 0)}")
                total_ids = res.get("count", 0)
                # ensure the actual message ids are passed into the job parameters
                # so processors can operate directly without re-building the query.
                params.setdefault("message_ids", res.get("message_ids", []))
                params.setdefault("count_of_message_ids", int(total_ids or 0))
                # also include a simple query string fallback (processor may ignore if message_ids present)
                try:
                    params.setdefault("query", f"after:{start} before:{end}")
                except Exception:
                    # non-fatal: processors should use message_ids if provided
                    pass
                # propagate estimated total into parameters for processors
                params.setdefault("estimated_total_emails", total_ids)
                params.setdefault("max_emails", total_ids)
            except Exception as e:
                logger.warning(f"Could not estimate total emails for shelving: {e}")


            job_config = {"job_type": "shelving", "parameters": params}
            
            # Prefer JobManager.create_job when available
            create_fn = getattr(self.server.job_manager, "create_job", None)
            if callable(create_fn):
                job_result_raw = create_fn(job_config, background_tasks)
                if asyncio.iscoroutine(job_result_raw):
                    job_result = await job_result_raw
                else:
                    job_result = job_result_raw
                # try to persist total_count metadata if possible
                try:
                    # job_result may be nested {"job": {...}} or a dict with job_id
                    j_id = None
                    if isinstance(job_result, dict):
                        job = job_result.get("job")
                        if job and isinstance(job, dict):
                            j_id = job.get("job_id") or job.get("id")
                        else:
                            j_id = job_result.get("job_id") or job_result.get("id")
                    if j_id and hasattr(self.server.job_manager, "update_job_metadata"):
                            logger.info(f"start_shelving: attaching total_count={total_ids} to job {j_id}")
                            await self.server.job_manager.update_job_metadata(j_id, {"total_count": total_ids})
                            try:
                                if hasattr(self.server.job_manager, "active_jobs") and j_id in self.server.job_manager.active_jobs:
                                    self.server.job_manager.active_jobs[j_id]["total_count"] = int(total_ids) if total_ids is not None else self.server.job_manager.active_jobs[j_id].get("total_count")
                                    logger.info(f"start_shelving: in-memory active_jobs[{j_id}].total_count set => {self.server.job_manager.active_jobs[j_id].get('total_count')}")
                            except Exception:
                                logger.debug("start_shelving: failed to set in-memory total_count")
                except Exception:
                    logger.debug("Failed to attach total_count metadata to job")

                return {"status": "success", "message": "Shelving started", "job": job_result}

            # Fallback: if job manager isn't implemented/doesn't start worker, start processor directly
            import uuid, time
            job_id = str(uuid.uuid4())
            try:
                # register minimal active job for progress endpoints if job_manager.active_jobs exists
                if hasattr(self.server.job_manager, "active_jobs"):
                    self.server.job_manager.active_jobs[job_id] = {
                        "job_type": "shelving",
                        "status": "running",
                        "start_time": time.time(),
                        "processed_count": 0,
                        "total_count": total_ids or 0,
                    }
            except Exception:
                logger.debug("Could not register job in job_manager.active_jobs")
                
            # Return response before processing starts
            response = {
                "job_id": job_id,
                "job_type": "shelving",
                "status": "scheduled",
                "message": "Shelving job scheduled",
            }
            
            if total_ids is not None:
                response["count_of_message_ids"] = str(int(total_ids))
                response["estimated_total_emails"] = str(int(total_ids))
                
            return response
                
        except Exception as e:
            logger.error(f"Error starting shelving: {e}")
            raise HTTPException(status_code=500, detail=f"Error starting shelving: {str(e)}")
    
    async def start_cataloging(self, background_tasks: BackgroundTasks, parameters: Dict[str, Any] = Body(...)):
        """
        Start email cataloging process.
        
        Args:
            background_tasks: FastAPI background tasks
            parameters: Job parameters including batch size and date range
            
        Returns:
            Job information
        """
        try:
            params = parameters or {}

            # normalize common keys (frontend may send startDate / endDate)
            start = params.get("start_date") or params.get("startDate")
            end = params.get("end_date") or params.get("endDate")
            if not start or not end:
                raise HTTPException(status_code=400, detail="start_date and end_date are required")

            # Estimate total message count using existing helper so job metadata can show progress%
            total_ids = None
            try:
                # reuse existing helper to get message ids count
                res = await self.get_message_ids_range(start, end, params.get("batch_size", 50))
                logger.info(f"Estimated total emails for cataloging between {start} and {end}: {res.get('count', 0)}")
                total_ids = res.get("count", 0)
                # ensure the actual message ids are passed into the job parameters
                # so processors can operate directly without re-building the query.
                params.setdefault("message_ids", res.get("message_ids", []))
                params.setdefault("count_of_message_ids", int(total_ids or 0))
                # also include a simple query string fallback (processor may ignore if message_ids present)
                try:
                    params.setdefault("query", f"after:{start} before:{end}")
                except Exception:
                    # non-fatal: processors should use message_ids if provided
                    pass
                # propagate estimated total into parameters for processors
                params.setdefault("estimated_total_emails", total_ids)
                params.setdefault("max_emails", total_ids)
            except Exception as e:
                logger.warning(f"Could not estimate total emails for cataloging: {e}")


            job_config = {"job_type": "cataloging", "parameters": params}

            # Prefer JobManager.create_job when available
            create_fn = getattr(self.server.job_manager, "create_job", None)
            if callable(create_fn):
                job_result_raw = create_fn(job_config, background_tasks)
                if asyncio.iscoroutine(job_result_raw):
                    job_result = await job_result_raw
                else:
                    job_result = job_result_raw
                # try to persist total_count metadata if possible
                try:
                    # job_result may be nested {"job": {...}} or a dict with job_id
                    j_id = None
                    if isinstance(job_result, dict):
                        job = job_result.get("job")
                        if job and isinstance(job, dict):
                            j_id = job.get("job_id") or job.get("id")
                        else:
                            j_id = job_result.get("job_id") or job_result.get("id")
                    if j_id and hasattr(self.server.job_manager, "update_job_metadata"):
                            logger.info(f"start_cataloging: attaching total_count={total_ids} to job {j_id}")
                            await self.server.job_manager.update_job_metadata(j_id, {"total_count": total_ids})
                            try:
                                if hasattr(self.server.job_manager, "active_jobs") and j_id in self.server.job_manager.active_jobs:
                                    self.server.job_manager.active_jobs[j_id]["total_count"] = int(total_ids) if total_ids is not None else self.server.job_manager.active_jobs[j_id].get("total_count")
                                    logger.info(f"start_cataloging: in-memory active_jobs[{j_id}].total_count set => {self.server.job_manager.active_jobs[j_id].get('total_count')}")
                            except Exception:
                                logger.debug("start_cataloging: failed to set in-memory total_count")
                except Exception:
                    logger.debug("Failed to attach total_count metadata to job")

                return {"status": "success", "message": "Cataloging started", "job": job_result}

            # Fallback: if job manager isn't implemented/doesn't start worker, start processor directly
            import uuid, time
            job_id = str(uuid.uuid4())
            try:
                # register minimal active job for progress endpoints if job_manager.active_jobs exists
                if hasattr(self.server.job_manager, "active_jobs"):
                    self.server.job_manager.active_jobs[job_id] = {
                        "job_type": "cataloging",
                        "status": "running",
                        "start_time": time.time(),
                        "processed_count": 0,
                        "total_count": total_ids or 0,
                    }
            except Exception:
                logger.debug("Could not register job in job_manager.active_jobs")

            # delegate to server processor as background task
            bg_target = getattr(self.server, "process_cataloging_job", None)
            if callable(bg_target):
                background_tasks.add_task(bg_target, job_id, params)
                return {"status": "started", "message": "Cataloging job enqueued (fallback)", "job_id": job_id}

            raise HTTPException(status_code=501, detail="No job manager or processor available to start cataloging")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to start cataloging: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def start_advanced_cataloging(self, background_tasks: BackgroundTasks, parameters: Dict[str, Any] = Body(...)):
        """
        Start advanced email cataloging process using the processor pipeline.
        
        This uses a pipeline of processors:
        1. MessageIDRetrievalProcessor - Retrieve message IDs in the date range
        2. MessageIDBatchProcessor - Split message IDs into batches
        3. EmailBatchRetrievalProcessor - Retrieve email content for each batch
        4. AILabelAssignmentProcessor - Assign AI labels to emails
        5. GmailLabelProcessor - Apply labels to Gmail messages
        
        Args:
            background_tasks: FastAPI background tasks
            parameters: Job parameters including batch size and date range
                
        Returns:
            Job information
        """
        return await start_advanced_cataloging(self, background_tasks, parameters)

    async def get_cataloging_progress(self):
        """Get current progress of active cataloging job."""
        try:
            logger.debug("Starting get_cataloging_progress endpoint call")
            
            # Default response in case of any issues
            default_response = {
                "status": "unknown",
                "progress": 0.0,
                "processed_count": 0,
                "total_count": 1,
                "job_id": None,
                "results": {},
                "message_ids_retrieved": False,
                "count_of_message_ids": 0,
                "message_ids_batched": False,
                "batched_ids": False,
                "emails_retrieved": False
            }
            
            # Get the most recent cataloging job (including completed ones)
            if not hasattr(self.server, "job_manager"):
                logger.error("job_manager not available on server instance")
                return default_response
                
            try:
                recent_job_id = self.server.job_manager.get_most_recent_job_id("cataloging")
                if not recent_job_id:
                    logger.info("No active cataloging job found")
                    default_response["status"] = "no_active_job"
                    return default_response
            except Exception as e:
                logger.error(f"Error getting most recent job ID: {e}")
                return default_response
            
            # Get job status
            try:
                job_status = await self.server.job_manager.get_job_status(recent_job_id)
                if not job_status or not isinstance(job_status, dict):
                    logger.error(f"Invalid job status returned for {recent_job_id}: {job_status}")
                    default_response["job_id"] = recent_job_id
                    return default_response
            except Exception as e:
                logger.error(f"Error getting job status for {recent_job_id}: {e}")
                default_response["job_id"] = recent_job_id
                return default_response
            
            # Extract progress information with defensive coding
            processed = 0
            total = 1
            progress = 0.0
            
            try:
                processed = job_status.get("processed_count")
                if processed is None:
                    processed = 0
                else:
                    try:
                        processed = int(processed)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid processed_count: {processed}, using 0")
                        processed = 0
                
                total = job_status.get("total_count")
                if total is None or total == 0:  # Prevent division by zero
                    total = 1
                else:
                    try:
                        total = int(total)
                        if total <= 0:
                            total = 1
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid total_count: {total}, using 1")
                        total = 1
                        
                try:
                    progress = float(processed) / float(total)
                except (ZeroDivisionError, TypeError, ValueError):
                    progress = 0.0
            except Exception as e:
                logger.error(f"Error calculating progress: {e}")
            
            # Extract tracking metadata if available
            metadata = {}
            try:
                if job_status.get("metadata") is not None and isinstance(job_status.get("metadata"), dict):
                    metadata = job_status.get("metadata", {})
                elif (job_status.get("results") is not None and 
                      isinstance(job_status.get("results"), dict) and 
                      job_status.get("results", {}).get("metadata") is not None and
                      isinstance(job_status.get("results", {}).get("metadata"), dict)):
                    metadata = job_status.get("results", {}).get("metadata", {})
            except Exception as e:
                logger.error(f"Error extracting metadata: {e}")
                
            # Safely get tracking fields
            def safe_bool(value, default=False):
                if value is None:
                    return default
                try:
                    return bool(value)
                except (ValueError, TypeError):
                    return default
                    
            def safe_int(value, default=0):
                if value is None:
                    return default
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default
            
            # Build response with all safety checks
            response = {
                "status": str(job_status.get("status", "unknown")),
                "progress": float(progress) if progress is not None else 0.0,
                "processed_count": safe_int(processed),
                "total_count": safe_int(total),
                "job_id": str(recent_job_id) if recent_job_id else None,
                "results": job_status.get("results", {}) if isinstance(job_status.get("results"), dict) else {},
                # Include tracking fields with extensive safety checks
                "message_ids_retrieved": safe_bool(metadata.get("message_ids_retrieved")) if metadata else False,
                "count_of_message_ids": safe_int(metadata.get("count_of_message_ids")) if metadata else 0,
                "message_ids_batched": safe_bool(metadata.get("message_ids_batched")) if metadata else False,
                "batched_ids": safe_bool(metadata.get("batched_ids")) if metadata else False,
                "emails_retrieved": safe_bool(metadata.get("emails_retrieved")) if metadata else False
            }
            
            logger.debug(f"Returning cataloging progress: {response}")
            return response
        except Exception as e:
            logger.exception(f"Unhandled error in get_cataloging_progress: {e}")
            return {
                "status": "error",
                "message": f"Internal server error: {str(e)}",
                "progress": 0.0,
                "processed_count": 0,
                "total_count": 1,
                "job_id": None,
                "results": {},
                "message_ids_retrieved": False,
                "count_of_message_ids": 0,
                "message_ids_batched": False,
                "batched_ids": False,
                "emails_retrieved": False
            }

    async def cancel_job(self, job_id: str):
        """Cancel a job by id (best-effort)."""
        try:
            ok = await self.server.job_manager.cancel_job(job_id)
            if not ok:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            return {"status": "success", "message": f"Cancellation requested for {job_id}"}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error cancelling job {job_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_categories(self):
    # Get all available categories.
        try:
            if not self.server.storage_manager.database:
                return {"categories": []}
                
            result = await self.server.storage_manager.database.fetch_all("""
                SELECT category, COUNT(*) as count 
                FROM emails 
                WHERE category IS NOT NULL 
                GROUP BY category 
                ORDER BY count DESC
            """)
            
            categories = [{"name": row["category"], "count": row["count"]} for row in result]
            
            return {"categories": categories}
        except Exception as e:
            logger.error(f"Error retrieving categories: {e}")
            return {"categories": []}

    # In-memory function state (fallback)
    _function_state: Dict[str, bool] = {
        "shelving": False,
        "cataloging": False,
        "reclassification": False,
        "workflows": True,
    }

    async def toggle_function(self, function_name: str, body: Dict[str, Any] = Body(...)):
        """Toggle a named function on/off. Returns the new enabled state."""
        enabled = bool(body.get("enabled", True))

        # Try to persist to DB first
        try:
            storage_mgr = self.server.storage_manager
            if storage_mgr and hasattr(storage_mgr, "set_function_state"):
                ok = await storage_mgr.set_function_state(function_name, enabled)
                if ok:
                    logger.info(f"Persisted function state for {function_name} => {enabled}")
                else:
                    logger.warning(f"Failed to persist function state for {function_name}; falling back to memory")
        except Exception as e:
            logger.exception(f"Error persisting function state for {function_name}: {e}")
            ok = False

        # Update in-memory fallback state
        self._function_state[function_name] = enabled

        # Broadcast status change via server websocket
        try:
            await self.server.add_activity("function_toggle", f"{function_name} toggled", {"function": function_name, "enabled": enabled})
        except Exception:
            logger.exception("Failed to broadcast function toggle")

        return {"function": function_name, "enabled": enabled}

    async def get_function_status(self, function_name: str):
        """Return the current status for a named function."""
        # Try DB-backed state first
        try:
            storage_mgr = self.server.storage_manager
            if storage_mgr and hasattr(storage_mgr, "get_function_state"):
                state = await storage_mgr.get_function_state(function_name)
                if state is not None:
                    return {"function": function_name, "enabled": state}
        except Exception as e:
            logger.exception(f"Error reading persisted function state for {function_name}: {e}")

        # Fall back to in-memory state
        enabled = self._function_state.get(function_name, False)
        return {"function": function_name, "enabled": enabled}

    async def list_functions(self):
        """Return a list of known functions and their current states (DB-backed or fallback)."""
        functions = {}
        try:
            storage_mgr = self.server.storage_manager
            if storage_mgr and hasattr(storage_mgr, "database") and storage_mgr.database:
                # Fetch all persisted function states
                rows = await storage_mgr.database.fetch_all("SELECT name, enabled FROM function_state")
                for r in rows:
                    functions[r["name"]] = bool(r["enabled"])
        except Exception:
            logger.exception("Error reading persisted function states")

        # Ensure fallback values are present
        for name, val in self._function_state.items():
            if name not in functions:
                functions[name] = val

        return {"functions": functions}

    async def get_labels(self):
        """Return a list of labels usable for reclassification.

        Attempts to read from storage manager first, then falls back to using a
        Gmail organizer (if available). Returns an empty list on any failure so
        the frontend can continue operating.
        """
        try:
            # Try storage-backed label list first
            storage_mgr = self.server.storage_manager
            logger.debug(f"get_labels: storage_mgr present={storage_mgr is not None}")
            if storage_mgr and hasattr(storage_mgr, "get_labels"):
                try:
                    labels = await storage_mgr.get_labels()
                    logger.debug(f"get_labels: storage_mgr.get_labels returned type={type(labels)}")
                    if isinstance(labels, list) and labels:
                        logger.info(f"get_labels: returning {len(labels)} labels from storage")
                        return labels
                    else:
                        logger.info("get_labels: storage returned no labels or non-list")
                except Exception as e:
                    logger.exception(f"get_labels: storage.get_labels threw: {e}")

            # Fallback: try Gmail organizer to enumerate user labels
            if self.server.organizer_factory and self.server.organizer_factory.organizers_available:
                organizer = self.server.organizer_factory.create_organizer()
                logger.debug(f"get_labels: organizer created type={type(organizer)}")
                try:
                    # Assume organizer exposes a method to list labels
                    gmail_labels = organizer.list_labels() if hasattr(organizer, "list_labels") else None
                    logger.debug(f"get_labels: organizer.list_labels returned type={type(gmail_labels)}")
                    if isinstance(gmail_labels, list) and gmail_labels:
                        logger.info(f"get_labels: returning {len(gmail_labels)} labels from organizer")
                        # Normalize to simple list of names or dicts as expected by frontend
                        return gmail_labels
                    else:
                        logger.info("get_labels: organizer returned no labels or non-list")
                except Exception as e:
                    logger.exception(f"Failed to retrieve labels from Gmail organizer: {e}")

        except Exception as e:
            logger.exception(f"Error while fetching reclassification labels: {e}")

        # Last resort: return empty list to avoid 404 for frontend
        logger.info("get_labels: returning empty list as last resort")
        return []

    async def refresh_labels(self):
        """Force-refresh labels from the Gmail organizer, update Redis cache and Postgres table.

        Returns the list of labels that were discovered and persisted.
        """
        try:
            # Create organizer
            if not (self.server.organizer_factory and self.server.organizer_factory.organizers_available):
                raise HTTPException(status_code=503, detail="Gmail organizers not available")

            organizer = self.server.organizer_factory.create_organizer()

            # Call list_labels (support sync or async implementations)
            if hasattr(organizer, "list_labels"):
                labels_raw = organizer.list_labels()
                if asyncio.iscoroutine(labels_raw):
                    labels = await labels_raw
                else:
                    labels = labels_raw
            else:
                raise HTTPException(status_code=501, detail="Organizer does not implement list_labels")

            # Normalize into id->name mapping for Redis cache and list of dicts for DB
            cache_map = {}
            db_rows = []
            for item in labels or []:
                if isinstance(item, dict):
                    lid = item.get("id") or item.get("label_id") or item.get("name")
                    name = item.get("name") or item.get("label") or str(lid)
                    typ = item.get("type") or "user"
                else:
                    lid = str(item)
                    name = str(item)
                    typ = "user"

                cache_map[name] = lid
                db_rows.append({"label_id": lid, "name": name, "type": typ})

            # Update Redis cache if redis_cache_manager available (or storage manager wrapper)
            try:
                redis_mgr = getattr(self.server.storage_manager, 'redis_cache_manager', None)
                if not redis_mgr:
                    redis_mgr = getattr(self.server, 'redis_cache_manager', None)

                if redis_mgr and hasattr(redis_mgr, 'update_label_cache'):
                    await redis_mgr.update_label_cache(cache_map)
                    logger.info(f"Refreshed Redis label cache with {len(cache_map)} entries")
            except Exception as e:
                logger.warning(f"Failed to update Redis label cache: {e}")

            # Upsert into Postgres gmail_labels table if database available
            try:
                db = self.server.storage_manager.database
                if db:
                    # Use a simple upsert - assumes table gmail_labels(label_id TEXT PRIMARY KEY, name TEXT, type TEXT)
                    for r in db_rows:
                        await db.execute("""
                            INSERT INTO gmail_labels (label_id, name, type) VALUES (:label_id, :name, :type)
                            ON CONFLICT (label_id) DO UPDATE SET name = EXCLUDED.name, type = EXCLUDED.type
                        """, r)
                    logger.info(f"Persisted {len(db_rows)} labels to Postgres gmail_labels table")
            except Exception as e:
                logger.warning(f"Failed to persist labels to Postgres: {e}")

            return labels or []

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to refresh reclassification labels: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_message_ids_range(self, start: str, end: str, chunk_size: int):
        """
        Return message ids for emails in the given (epoch seconds) range.

        Args:
            start: start time as POSIX seconds (inclusive)
            end: end time as POSIX seconds (exclusive)

        Returns:
            Dict with count and list of message ids.
        """
        try:
            # Accept either POSIX ints or date strings like YYYY/MM/DD; convert to epoch seconds
            if start is None or end is None:
                raise HTTPException(status_code=400, detail="start and end parameters are required")

            def to_posix(v):
                """Convert an input value to POSIX seconds.

                Accepts:
                - int or float
                - numeric strings (e.g. "1690000000" or "1690000000.5")
                - date strings in common formats (YYYY/MM/DD, YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY)
                - ISO-8601 strings
                """
                from datetime import datetime, timezone

                # numeric types
                if isinstance(v, (int, float)):
                    return int(v)

                # strings (could be numeric epoch or date formats)
                if isinstance(v, str):
                    s = v.strip()

                    # Try numeric epoch string first (int or float)
                    try:
                        # allow floats like '1690000000.123'
                        if "." in s:
                            return int(float(s))
                        return int(s)
                    except Exception:
                        pass

                    # Try common date formats
                    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            dt = datetime.strptime(s, fmt)
                            return int(dt.replace(tzinfo=timezone.utc).timestamp())
                        except Exception:
                            continue

                    # Try ISO parsing
                    try:
                        dt = datetime.fromisoformat(s)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return int(dt.timestamp())
                    except Exception:
                        raise HTTPException(status_code=400, detail=f"Invalid date format: {s}. Use YYYY/MM/DD, ISO, or epoch seconds")

                # Anything else is invalid
                raise HTTPException(status_code=400, detail="start and end must be integers, numeric strings, or date strings")

            start_ts = to_posix(start)
            end_ts = to_posix(end)
            if start_ts >= end_ts:
                raise HTTPException(status_code=400, detail="start must be less than end")

            # Build a Gmail query using epoch seconds; Gmail accepts after: and before: with epoch
            query = f"after:{start_ts} before:{end_ts}"

            # Create organizer and try a direct service-backed paged listing first
            organizer = self.server.organizer_factory.create_organizer()
            # Prefer direct service-backed, paged listing (uses labelIds to exclude archived)
            try:
                # local import of the helper in same package
                from .job_processors.job_processors import list_message_ids_in_range

                if hasattr(organizer, "service") and getattr(organizer, "service", None):
                    try:
                        ids = await list_message_ids_in_range(
                            organizer.service,
                            query,
                            max_ids=10000,
                            page_size=500,
                            label_ids=["INBOX"],
                        )
                        return {"count": len(ids), "message_ids": ids, "chunk_size": chunk_size}
                    except Exception as e:
                        logger.warning(f"Service-backed list_message_ids_in_range failed: {e}")
            except Exception:
                # Import failed or helper not available; fall back to organizer methods
                pass

            # Fallback: try organizer.search_messages or organizer.list_message_ids_in_range if present
            search_call = None
            if hasattr(organizer, "search_messages"):
                search_call = organizer.search_messages(query=query, max_results=10000)
            else:
                # Fallback: try a generic messages list function if present on organizer
                if hasattr(organizer, "list_message_ids_in_range"):
                    search_call = organizer.list_message_ids_in_range(start, end)

            if search_call is None:
                raise HTTPException(status_code=501, detail="Organizer does not implement a search API")

            if asyncio.iscoroutine(search_call):
                results = await search_call
            else:
                results = search_call

            # Normalize to a flat list of message ids
            ids: List[str] = []
            if results is None:
                ids = []
            elif isinstance(results, list):
                for item in results:
                    if isinstance(item, str):
                        ids.append(item)
                    elif isinstance(item, dict):
                        # common keys
                        mid = item.get("id") or item.get("message_id") or item.get("messageId")
                        if mid:
                            ids.append(str(mid))
                    else:
                        # try to stringify anything else
                        try:
                            ids.append(str(item))
                        except Exception:
                            continue
            else:
                # single object -> try to extract id
                if isinstance(results, dict):
                    mid = results.get("id") or results.get("message_id") or results.get("messageId")
                    ids = [str(mid)] if mid else []
                else:
                    ids = [str(results)]

            return {"count": len(ids), "message_ids": ids, "chunk_size": chunk_size}

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in get_message_ids_range: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def batch_message_ids(self, payload: Dict[str, Any] = Body(...)):

        """
        Split a flat list of message ids into batches.

        Expects a JSON object body with keys:
        - message_ids: list of ids
        - chunk_size: optional int (default 100)

        Returns a dict with total count and list of batches.
        """
        try:
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="request body must be a JSON object")

            message_ids = payload.get("message_ids")
            chunk_size = payload.get("chunk_size", 10)

            if not isinstance(message_ids, list):
                raise HTTPException(status_code=400, detail="message_ids must be a list")
            try:
                chunk_size = int(chunk_size)
            except Exception:
                raise HTTPException(status_code=400, detail="chunk_size must be an integer")
            if chunk_size <= 0:
                raise HTTPException(status_code=400, detail="chunk_size must be a positive integer")

            # normalize to strings and remove falsy values
            ids = [str(x) for x in message_ids if x]
            batches = [ids[i : i + chunk_size] for i in range(0, len(ids), chunk_size)]

            return {"count": len(ids), "batches": batches, "chunk_size": chunk_size}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in batch_message_ids: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def retrieve_sample_batch_emails(self, payload: Dict[str, Any] = Body(...)):
        try:
            # Normalize incoming payload (accept JSON object or stringified JSON)
            if not isinstance(payload, dict):
                if isinstance(payload, str):
                    import json, ast
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        try:
                            payload = ast.literal_eval(payload)
                        except Exception:
                            raise HTTPException(status_code=400, detail="request body must be a JSON object")
                else:
                    raise HTTPException(status_code=400, detail="request body must be a JSON object")

            # Support wrapper with 'input'
            raw_input = payload.get("input")
            if isinstance(raw_input, str):
                import json, ast
                try:
                    payload = json.loads(raw_input)
                except Exception:
                    try:
                        payload = ast.literal_eval(raw_input)
                    except Exception:
                        raise HTTPException(status_code=400, detail="input field must contain valid JSON")

            # Extract batches / chunk_size / count
            batches_raw = payload.get("batches") or payload.get("batched_message_ids") or payload.get("message_ids")
            chunk_size = payload.get("chunk_size")
            count = payload.get("count")

            if batches_raw is None:
                raise HTTPException(status_code=400, detail="payload must include 'batches' or 'batched_message_ids'")

            # Allow stringified batches
            import json, ast
            if isinstance(batches_raw, str):
                try:
                    batches_raw = json.loads(batches_raw)
                except Exception:
                    try:
                        batches_raw = ast.literal_eval(batches_raw)
                    except Exception:
                        raise HTTPException(status_code=400, detail="batches must be a list or a stringified list")

            # Normalize to list[list[str]]
            if isinstance(batches_raw, list) and batches_raw and not any(isinstance(i, list) for i in batches_raw):
                batches = [[str(i) for i in batches_raw if i]]
            else:
                if not isinstance(batches_raw, list):
                    raise HTTPException(status_code=400, detail="batches must be a list of lists")
                batches = []
                for b in batches_raw:
                    if not isinstance(b, list):
                        raise HTTPException(status_code=400, detail="each batch must be a list of message ids")
                    clean = [str(x) for x in b if x]
                    if clean:
                        batches.append(clean)

            try:
                chunk_size = None if chunk_size is None else int(chunk_size)
            except Exception:
                raise HTTPException(status_code=400, detail="chunk_size must be an integer if provided")

            organizer = self.server.organizer_factory.create_organizer()

            if not hasattr(organizer, "fetch_email"):
                # return batches of ids when fetch not available
                return {"requested": count or sum(len(b) for b in batches), "returned": sum(len(b) for b in batches), "batches": batches}

            # bounded concurrency across a batch
            MAX_BODY = 400

            async def _fetch_and_sanitize(mid: str):
                try:
                    out = organizer.fetch_email(mid)
                    res = await out if asyncio.iscoroutine(out) else await asyncio.to_thread(out)
                    body = ""
                    sender = ""
                    subject = ""

                    if isinstance(res, dict):
                        data = res.get("data") or res
                        sender = data.get("sender") or data.get("from") or data.get("from_address") or data.get("return_path") or ""
                        subject = data.get("subject") or data.get("title") or ""
                        raw_b = data.get("raw_body") or data.get("raw") or data.get("body") or ""
                        if isinstance(raw_b, (bytes, bytearray)):
                            try:
                                body = raw_b.decode("utf-8", errors="replace")
                            except Exception:
                                body = str(raw_b)
                        else:
                            body = str(raw_b or "")
                    else:
                        try:
                            sender = getattr(res, "sender", "") or getattr(res, "from", "") or ""
                        except Exception:
                            sender = ""
                        try:
                            subject = getattr(res, "subject", "") or ""
                        except Exception:
                            subject = ""
                        try:
                            raw_b = getattr(res, "raw_body", None) or getattr(res, "raw", None) or getattr(res, "body", None)
                            if isinstance(raw_b, (bytes, bytearray)):
                                body = raw_b.decode("utf-8", errors="replace")
                            else:
                                body = str(raw_b or "")
                        except Exception:
                            body = ""

                    sender = str(sender) if sender is not None else ""
                    subject = str(subject) if subject is not None else ""
                    body = (body or "")[:MAX_BODY]

                    return {"sender": sender, "subject": subject, "body": body, "message_id": mid}
                except Exception as e:
                    logger.debug(f"failed to fetch {mid}: {e}")
                    return None

            output_batches = []
            total_requested = 0
            total_returned = 0

            for batch in batches:
                ids = [str(mid) for mid in batch if mid]
                if not ids:
                    output_batches.append([])
                    continue

                to_fetch = ids if not chunk_size or chunk_size <= 0 else ids[:int(chunk_size)]
                total_requested += len(to_fetch)

                sem = asyncio.Semaphore(min(10, max(1, len(to_fetch))))
                # create fetch tasks bound to semaphore
                async def _bounded_fetch(mid):
                    async with sem:
                        return await _fetch_and_sanitize(mid)

                tasks = [_bounded_fetch(mid) for mid in to_fetch]
                results = await asyncio.gather(*tasks)
                sanitized = [r for r in results if r is not None]

                total_returned += len(sanitized)
                output_batches.append(sanitized)

            return {"requested": count or total_requested, "returned": total_returned, "batches": output_batches}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in retrieve_sample_batch_emails: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def retrieve_sample_batch_emails_raw(self, payload: Dict[str, Any] = Body(...)):
        """
        Accept a JSON payload (same shapes as retrieve_sample_batch_emails) and
        return full/raw email content per message id. The response contains a
        list of objects: { message_id, raw, meta? } where `raw` is a string
        (decoded if base64/raw bytes were provided) or None when not available.
        """
        import json, ast, base64
        from email import message_from_bytes, policy

        try:
            # Normalize incoming payload (accept JSON object or stringified JSON)
            if not isinstance(payload, dict):
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        try:
                            payload = ast.literal_eval(payload)
                        except Exception:
                            raise HTTPException(status_code=400, detail="request body must be a JSON object")
                else:
                    raise HTTPException(status_code=400, detail="request body must be a JSON object")

            # Support wrapper with 'input' containing a stringified JSON
            raw_input = payload.get("input")
            if isinstance(raw_input, str):
                try:
                    payload = json.loads(raw_input)
                except Exception:
                    try:
                        payload = ast.literal_eval(raw_input)
                    except Exception:
                        raise HTTPException(status_code=400, detail="input field must contain valid JSON")

            # Extract batches / chunk_size / count
            batches_raw = payload.get("batches") or payload.get("batched_message_ids") or payload.get("message_ids")
            chunk_size = payload.get("chunk_size")
            count = payload.get("count")

            if batches_raw is None:
                raise HTTPException(status_code=400, detail="payload must include 'batches' or 'batched_message_ids'")

            # Allow batches to be passed as a JSON string
            if isinstance(batches_raw, str):
                try:
                    batches_raw = json.loads(batches_raw)
                except Exception:
                    try:
                        batches_raw = ast.literal_eval(batches_raw)
                    except Exception:
                        raise HTTPException(status_code=400, detail="batches must be a list or a stringified list")

            # Normalize to list[list[str]] (single flat list becomes one batch)
            if isinstance(batches_raw, list) and batches_raw and not any(isinstance(i, list) for i in batches_raw):
                batches = [[str(i) for i in batches_raw if i]]
            else:
                if not isinstance(batches_raw, list):
                    raise HTTPException(status_code=400, detail="batches must be a list of lists")
                batches = []
                for b in batches_raw:
                    if not isinstance(b, list):
                        raise HTTPException(status_code=400, detail="each batch must be a list of message ids")
                    clean = [str(x) for x in b if x]
                    if clean:
                        batches.append(clean)

            # Validate chunk_size
            try:
                chunk_size = None if chunk_size is None else int(chunk_size)
            except Exception:
                raise HTTPException(status_code=400, detail="chunk_size must be an integer if provided")

            # Build list of ids to fetch
            organizer = self.server.organizer_factory.create_organizer()
            flat_ids = [str(mid) for batch in batches for mid in batch if mid]
            if not flat_ids:
                return {"requested": count or 0, "returned": 0, "messages": []}

            if not hasattr(organizer, "fetch_email"):
                return {"requested": count or len(flat_ids), "returned": len(flat_ids), "message_ids": flat_ids}

            to_fetch = flat_ids if not chunk_size or chunk_size <= 0 else flat_ids[:int(chunk_size)]

            # Bounded concurrency
            sem = asyncio.Semaphore(min(10, max(1, len(to_fetch))))

            MAX_RAW_LEN = 400

            def _truncate_raw(s: Optional[str]) -> Optional[str]:
                if s is None:
                    return None
                try:
                    s = str(s)
                except Exception:
                    return None
                if len(s) > MAX_RAW_LEN:
                    return s[:MAX_RAW_LEN]
                return s

            def _make_result(mid: str, raw: Optional[str] = None, **extras):
                return_dict = {"message_id": mid, "raw": _truncate_raw(raw)}
                # include any extra metadata (meta, data, etc.)
                for k, v in extras.items():
                    return_dict[k] = v
                return return_dict

            async def _fetch_raw(mid: str):
                async with sem:
                    try:
                        out = organizer.fetch_email(mid)
                        res = await out if asyncio.iscoroutine(out) else await asyncio.to_thread(out)

                        # If bytes, decode
                        if isinstance(res, (bytes, bytearray)):
                            try:
                                return _make_result(mid, res.decode("utf-8", errors="replace"))
                            except Exception:
                                return _make_result(mid, str(res))

                        # If dict, look for common raw fields or gmail body.data
                        if isinstance(res, dict):
                            raw_val = None
                            for k in ("raw", "raw_message", "raw_rfc822", "rawEmail"):
                                raw_val = res.get(k)
                                if raw_val:
                                    break

                            if not raw_val:
                                body = res.get("raw_body") or {}
                                if isinstance(body, dict):
                                    raw_val = body.get("data")

                            if raw_val:
                                # bytes
                                if isinstance(raw_val, (bytes, bytearray)):
                                    try:
                                        raw_str = raw_val.decode("utf-8", errors="replace")
                                    except Exception:
                                        raw_str = str(raw_val)
                                elif isinstance(raw_val, str):
                                    # attempt base64 decode; if fails, return as-is
                                    try:
                                        raw_bytes = base64.urlsafe_b64decode(raw_val + "===")
                                        raw_str = raw_bytes.decode("utf-8", errors="replace")
                                    except Exception:
                                        raw_str = raw_val
                                else:
                                    raw_str = str(raw_val)

                                meta = {k: v for k, v in res.items() if k not in ("raw", "body")}
                                return _make_result(mid, raw_str, meta=meta)

                            # no raw content found, include the dict
                            return _make_result(mid, None, data=res)

                        # Objects with .raw attribute
                        if hasattr(res, "raw"):
                            r = getattr(res, "raw")
                            if isinstance(r, (bytes, bytearray)):
                                try:
                                    return _make_result(mid, r.decode("utf-8", errors="replace"))
                                except Exception:
                                    return _make_result(mid, str(r))
                            return _make_result(mid, str(r))

                        # email.message objects
                        if hasattr(res, "as_string"):
                            try:
                                return _make_result(mid, res.as_string())
                            except Exception:
                                pass
                        if hasattr(res, "as_bytes"):
                            try:
                                b = res.as_bytes()
                                return _make_result(mid, b.decode("utf-8", errors="replace"))
                            except Exception:
                                pass

                        # Fallback: try to parse common raw bytes in attributes
                        try:
                            # sometimes organizer returns {'payload': {'raw': '...'}}
                            if isinstance(res, dict):
                                p = res.get("payload") or res.get("message")
                                if isinstance(p, dict):
                                    rv = p.get("raw") or p.get("raw_body", {}).get("data")
                                    if rv:
                                        if isinstance(rv, str):
                                            try:
                                                raw_bytes = base64.urlsafe_b64decode(rv + "===")
                                                return _make_result(mid, raw_bytes.decode("utf-8", errors="replace"))
                                            except Exception:
                                                return _make_result(mid, rv)
                        except Exception:
                            pass

                        # Final fallback
                        return _make_result(mid, str(res))
                    except Exception as e:
                        logger.debug(f"failed to fetch raw {mid}: {e}")
                        return None

            tasks = [_fetch_raw(mid) for mid in to_fetch]
            results = await asyncio.gather(*tasks)
            sanitized = [r for r in results if r is not None]

            return {"requested": count or len(to_fetch), "returned": len(sanitized), "messages": sanitized}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in retrieve_sample_batch_emails_raw: {e}")
            raise HTTPException(status_code=500, detail=str(e))
