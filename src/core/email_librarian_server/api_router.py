"""
API router for the Enhanced Email Librarian system.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter as FastAPIRouter, BackgroundTasks, Body, Depends, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
import asyncio

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
        self.router.post("/functions/cataloging/start")(self.start_cataloging)
        self.router.get("/functions/cataloging/progress")(self.get_cataloging_progress)
        self.router.get("/functions/cataloging/categories")(self.get_categories)
        # Generic function toggle endpoints (shelving, cataloging, reclassification, workflows)
        # frontend expects POST /api/<function>/toggle
        self.router.post("/{function_name}/toggle")(self.toggle_function)

        # Expose function status
        self.router.get("/{function_name}/status")(self.get_function_status)

        # Admin: list all function states
        self.router.get("/functions")(self.list_functions)

        # Job cancellation
        self.router.post("/jobs/{job_id}/cancel")(self.cancel_job)

        
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
            # Create job config with parameters
            job_config = {
                "job_type": "cataloging",
                "parameters": parameters
            }
            
            # Create and start job
            job_result = await self.server.job_manager.create_job(job_config, background_tasks)
            
            return {
                "status": "success",
                "message": "Cataloging started",
                "job": job_result
            }
            
        except Exception as e:
            logger.error(f"Failed to start cataloging: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_cataloging_progress(self):
        """Get current progress of active cataloging job."""
        try:
            # Get the most recent cataloging job (including completed ones)
            recent_job_id = self.server.job_manager.get_most_recent_job_id("cataloging")
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
                "job_id": recent_job_id,
                "results": job_status.get("results", {})
            }
        except Exception as e:
            logger.error(f"Error getting cataloging progress: {e}")
            raise HTTPException(status_code=500, detail=str(e))

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