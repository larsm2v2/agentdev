"""
Enhanced Email Librarian Server - Main class
"""

import logging
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, cast
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .auth_manager import GmailAuthManager
from .storage_manager import StorageManager
from .organizer_factory import OrganizerFactory
from .job_manager import JobManager
from .job_processors import ShelvingJobProcessor, CatalogingJobProcessor
from .api_router import APIRouter

logger = logging.getLogger(__name__)

class EnhancedEmailLibrarianServer:
    """Main server class for the Enhanced Email Librarian system."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Enhanced Email Librarian Server.
        
        Args:
            config: Server configuration
        """
        self.config = config or {}
        self.auth_manager = GmailAuthManager(
            token_path=self.config.get("token_path", "data/gmail_token.pickle"),
            credentials_path=self.config.get("credentials_path", "config/credentials.json")
        )
        self.storage_manager = StorageManager(
            database_url=self.config.get("database_url"),
            qdrant_url=self.config.get("qdrant_url")
        )
        self.organizer_factory = OrganizerFactory(
            credentials_path=self.config.get("credentials_path", "config/credentials.json")
        )
        self.job_manager = JobManager(
            database=None,  # Will be set after database initialization
            organizer_factory=self.organizer_factory
        )
        self.api_router = None  # Will be set after FastAPI app is created
        self.app = None  # Will be set in create_app
        self.websocket_connections = {}
        
    def create_app(self) -> FastAPI:
        """
        Create and configure the FastAPI application.
        
        Returns:
            Configured FastAPI application
        """
        # Create lifespan context manager
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            await self.startup()
            yield
            # Shutdown
            await self.shutdown()
            
        # Create FastAPI app
        app = FastAPI(
            title="Enhanced Email Librarian",
            description="Enterprise-grade email management system",
            version="2.0.0",
            lifespan=lifespan
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Create API router
        self.api_router = APIRouter(self)
        app.include_router(self.api_router.router)
        
        # Add WebSocket endpoint
        app.websocket("/ws")(self.websocket_endpoint)
        
        # Setup frontend routes
        frontend_serving_mode = self.config.get("frontend_serving_mode", "static")
        
        if frontend_serving_mode == "static":
            # Serve static frontend files
            app.mount("/dashboard", StaticFiles(directory="frontend", html=True), name="frontend")
            
            # Redirect root to dashboard
            @app.get("/")
            async def redirect_to_dashboard():
                return RedirectResponse(url="/dashboard")
        else:
            # Serve frontend dynamically
            @app.get("/")
            async def get_frontend():
                return FileResponse("frontend/index.html")
                
            @app.get("/dashboard")
            async def get_dashboard():
                return FileResponse("frontend/dashboard/index.html")
                
            @app.get("/dashboard/{path:path}")
            async def get_dashboard_path(path: str):
                file_path = f"frontend/dashboard/{path}"
                if Path(file_path).exists():
                    return FileResponse(file_path)
                return FileResponse("frontend/dashboard/index.html")
                
        # Store the app
        self.app = app
        return app
        
    async def startup(self):
        """Perform startup tasks."""
        logger.info("Starting Enhanced Email Librarian Server...")
        
        # Initialize storage
        await self.storage_manager.initialize()
        
        # Set database in job manager
        self.job_manager.database = self.storage_manager.database
        
        # Register job processors
        shelving_processor = ShelvingJobProcessor(
            database=self.storage_manager.database,
            organizer_factory=self.organizer_factory
        )
        self.job_manager.register_processor("shelving", shelving_processor)
        
        cataloging_processor = CatalogingJobProcessor(
            database=self.storage_manager.database,
            organizer_factory=self.organizer_factory
        )
        self.job_manager.register_processor("cataloging", cataloging_processor)
        
        # Add initial activity
        await self.add_activity("system", "Email Librarian server started and ready", {"version": "2.0.0"})
        
        logger.info("✅ Enhanced Email Librarian Server started")
        
    async def shutdown(self):
        """Perform shutdown tasks."""
        logger.info("Shutting down Enhanced Email Librarian Server...")
        
        # Close storage connections
        await self.storage_manager.close()
        
        # Close WebSocket connections
        for ws in self.websocket_connections.values():
            await ws.close()
            
        logger.info("✅ Enhanced Email Librarian Server shut down")
        
    async def websocket_endpoint(self, websocket: WebSocket):
        """
        WebSocket endpoint for real-time updates.
        
        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        client_id = f"client_{time.time()}"
        self.websocket_connections[client_id] = websocket
        
        try:
            # Send initial status
            await websocket.send_json({
                "type": "system_status",
                "data": {
                    "status": "connected",
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # Listen for messages
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    await self.handle_websocket_message(websocket, client_id, message)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": "Invalid JSON"}
                    })
        except WebSocketDisconnect:
            if client_id in self.websocket_connections:
                del self.websocket_connections[client_id]
            logger.info(f"Client {client_id} disconnected")
            
    async def handle_websocket_message(self, websocket: WebSocket, client_id: str, message: Dict[str, Any]):
        """
        Handle WebSocket message.
        
        Args:
            websocket: WebSocket connection
            client_id: Client identifier
            message: Message data
        """
        message_type = message.get("type")
        
        if message_type == "ping":
            await websocket.send_json({
                "type": "pong",
                "data": {
                    "timestamp": datetime.now().isoformat(),
                    "client_id": client_id
                }
            })
        elif message_type == "get_job_status":
            job_id = message.get("job_id")
            if job_id:
                status = await self.job_manager.get_job_status(job_id)
                await websocket.send_json({
                    "type": "job_status",
                    "data": status
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Job ID required"}
                })
        else:
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"Unknown message type: {message_type}"}
            })
            
    async def broadcast_message(self, message_type: str, data: Dict[str, Any]):
        """
        Broadcast message to all WebSocket clients.
        
        Args:
            message_type: Type of message
            data: Message data
        """
        message = {
            "type": message_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        for client_id, websocket in list(self.websocket_connections.items()):
            try:
                await websocket.send_json(message)
            except Exception:
                logger.warning(f"Failed to send message to client {client_id}")
                
    async def add_activity(self, activity_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """
        Add activity to activity log.
        
        Args:
            activity_type: Type of activity
            description: Activity description
            details: Additional details
        """
        try:
            if self.storage_manager.database is None:
                logger.warning("Cannot add activity: database not initialized")
                return
                
            query = """
            INSERT INTO activity_log (activity_type, description, details, created_at)
            VALUES (:activity_type, :description, :details, :created_at)
            RETURNING id
            """
            
            values = {
                "activity_type": activity_type,
                "description": description,
                "details": json.dumps(details) if details else None,
                "created_at": datetime.now().isoformat()
            }
            
            result = await self.storage_manager.database.execute(query, values)
            
            # Broadcast activity to WebSocket clients
            await self.broadcast_message("activity", {
                "id": str(result),
                "activity_type": activity_type,
                "description": description,
                "details": details,
                "created_at": values["created_at"]
            })
            
            return result
        except Exception as e:
            logger.error(f"Error adding activity: {e}")
            return None
