"""
API router for the Enhanced Email Librarian system.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter as FastAPIRouter, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

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
        
    async def create_job(self, job_config: JobConfig, background_tasks: BackgroundTasks):
        """
        Create a new email processing job.
        
        Args:
            job_config: Job configuration
            background_tasks: FastAPI background tasks
            
        Returns:
            Job creation result
        """
        return await self.server.job_manager.create_job(job_config.dict(), background_tasks)
        
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
        query = "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT :limit"
        activities = await self.server.storage_manager.database.fetch_all(query, {"limit": limit})
        return {"activities": [dict(activity) for activity in activities]}
