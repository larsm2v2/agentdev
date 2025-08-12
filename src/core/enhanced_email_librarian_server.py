#!/usr/bin/env python3
"""
Enhanced Email Librarian Backend Server
Enterprise-grade FastAPI server with n8n, Qdrant, PostgreSQL, LangFuse, and CrewAI integration
"""

import asyncio
import json
import logging
import pickle
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
import uuid
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

# Database integrations
import asyncpg
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import databases

# Vector database
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Range

# Direct LLM integration (no LangChain)
from .direct_llm_providers import MultiLLMManager, LLMProvider
from .modern_email_agents import ModernEmailAgents

# Observability (LangFuse - simplified/removed for now)
LANGFUSE_AVAILABLE = False
Langfuse = None
LangfuseCallbackHandler = None

# TODO: Re-enable LangFuse when dependencies are properly configured
# try:
#     from langfuse import Langfuse
#     from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
#     LANGFUSE_AVAILABLE = True
# except ImportError:
#     LANGFUSE_AVAILABLE = False
#     Langfuse = None
#     LangfuseCallbackHandler = None

# CrewAI
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

# n8n integration
import httpx
from typing_extensions import Annotated

# Import our Gmail organizers
import sys
sys.path.append('.')
sys.path.append('./src/gmail')
sys.path.append('./src/core')

try:
    from src.gmail.fast_gmail_organizer import HighPerformanceGmailOrganizer
    from src.gmail.gmail_organizer import GmailAIOrganizer
except ImportError:
    try:
        from ..gmail.fast_gmail_organizer import HighPerformanceGmailOrganizer
        from ..gmail.gmail_organizer import GmailAIOrganizer
    except ImportError:
        print("❌ Could not import Gmail organizers. Please check file paths.")
        raise

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/enhanced_email_librarian_server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database Models
Base = declarative_base()

class EmailProcessingJob(Base):
    __tablename__ = "email_processing_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String(50), nullable=False)  # shelving, cataloging, reclassification
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    processed_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)

class EmailVector(Base):
    __tablename__ = "email_vectors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(String(255), nullable=False, unique=True)
    subject = Column(Text, nullable=False)
    sender = Column(String(255), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    category = Column(String(100), nullable=True)
    labels = Column(JSON, nullable=True)
    vector_id = Column(String(255), nullable=False)  # Qdrant point ID
    created_at = Column(DateTime, default=datetime.utcnow)

class AgentExecution(Base):
    __tablename__ = "agent_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String(100), nullable=False)
    task_description = Column(Text, nullable=False)
    status = Column(String(20), default="running")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    langfuse_trace_id = Column(String(255), nullable=True)
    n8n_workflow_id = Column(String(255), nullable=True)

# Pydantic Models
class JobConfig(BaseModel):
    job_type: str = Field(..., description="Type of job: shelving, cataloging, reclassification")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    n8n_workflow_url: Optional[str] = None
    enable_vector_storage: bool = True
    enable_langfuse_tracking: bool = True

class EmailProcessingResult(BaseModel):
    job_id: str
    status: str
    processed_count: int
    total_count: int
    categories_created: List[str]
    processing_time: float
    error_message: Optional[str] = None

class VectorSearchRequest(BaseModel):
    query: str
    limit: int = 10
    category_filter: Optional[str] = None
    date_range: Optional[Dict[str, str]] = None

class AgentTaskRequest(BaseModel):
    agent_type: str = Field(..., description="shelving_agent, cataloging_agent, reclassification_agent")
    task_description: str
    email_data: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None

# Enhanced Email Librarian Server
class EnhancedEmailLibrarianServer:
    def __init__(self):
        self.app = FastAPI(
            title="Enhanced Email Librarian API",
            description="Enterprise email organization system with AI agents, vector search, and workflow automation",
            version="2.0.0"
        )
        
        # Database connections
        self.db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/email_librarian")
        self.database = databases.Database(self.db_url)
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Vector database
        self.qdrant_client = AsyncQdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333"))
        )
        
        # LangFuse integration (optional)
        if LANGFUSE_AVAILABLE and Langfuse is not None:
            self.langfuse = Langfuse(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            )
        else:
            self.langfuse = None
        
        # n8n integration
        self.n8n_base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678")
        self.n8n_api_key = os.getenv("N8N_API_KEY")
        
        # Initialize LLM manager for CrewAI agents
        try:
            self.llm_manager = MultiLLMManager()
            print(f"✅ LLM Manager initialized with {self.llm_manager.provider_type.value}")
        except Exception as e:
            print(f"⚠️  Failed to initialize LLM manager: {e}")
            self.llm_manager = None
        
        # Gmail organizers
        self.hp_organizer = None
        self.ai_organizer = None
        self.gmail_organizer = None  # For real-time Gmail API access
        
        # Label caching for performance optimization
        self._label_cache = {}
        self._our_custom_labels = set()
        
        # Redis Cache Manager for persistent caching and analytics
        self.cache_manager = None
        self._redis_enabled = False
        
        # Active connections and jobs
        self.active_connections: List[WebSocket] = []
        self.active_jobs: Dict[str, Dict] = {}
        
        # OAuth flow for Gmail authentication
        self._oauth_flow = None
        
        # CrewAI agents
        self.agents = {}
        # TODO: Re-enable CrewAI agents after fixing LLM integration
        # self.setup_crewai_agents()
        
        self.setup_middleware()
        self.setup_static_files()
        self.setup_routes()
        
        # Redis cache will be initialized during startup event
        
    async def initialize_redis_cache(self):
        """Initialize Redis cache manager with graceful fallback"""
        try:
            from .redis_cache_manager import RedisCacheManager
            
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.cache_manager = RedisCacheManager(redis_url=redis_url)
            
            # Try to initialize Redis connection
            if await self.cache_manager.initialize():
                self._redis_enabled = True
                logger.info("🎯 Redis cache manager initialized successfully")
                
                # Load existing label cache from Redis
                await self._load_labels_from_redis()
                
                # Perform maintenance cleanup
                cleaned_keys = await self.cache_manager.cleanup_expired_keys()
                logger.info(f"🧹 Redis maintenance complete: {cleaned_keys} keys cleaned")
                
            else:
                logger.warning("⚠️ Redis not available, falling back to in-memory caching")
                self._redis_enabled = False
                
        except ImportError:
            logger.warning("⚠️ Redis dependencies not available, install with: pip install redis")
            self._redis_enabled = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis cache manager: {e}")
            self._redis_enabled = False
    
    async def _load_labels_from_redis(self):
        """Load label cache from Redis on startup"""
        try:
            if self._redis_enabled and self.cache_manager:
                cached_labels = await self.cache_manager.get_label_cache()
                
                if cached_labels:
                    self._label_cache = cached_labels
                    logger.info(f"📋 Loaded {len(cached_labels)} labels from Redis cache")
                else:
                    # Initialize from Gmail API and cache in Redis
                    await self._initialize_label_cache_from_gmail()
                    if self._label_cache:
                        await self.cache_manager.update_label_cache(self._label_cache)
                        logger.info(f"📋 Cached {len(self._label_cache)} Gmail labels to Redis")
        except Exception as e:
            logger.error(f"Failed to load labels from Redis: {e}")
        
    def setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_static_files(self):
        """Mount static files and frontend"""
        import os
        
        # Mount frontend static files
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
        if os.path.exists(frontend_path):
            self.app.mount("/static", StaticFiles(directory=frontend_path), name="static")
            # Also mount frontend directly for component loading
            self.app.mount("/frontend", StaticFiles(directory=frontend_path), name="frontend")
            print(f"✅ Mounted frontend directory: {frontend_path}")
        else:
            print(f"⚠️  Frontend directory not found: {frontend_path}")
    
    def setup_crewai_agents(self):
        """Initialize CrewAI agents for different email processing tasks"""
        
        # Shelving Agent - Real-time email organization
        self.agents['shelving'] = Agent(
            role='Email Shelving Specialist',
            goal='Organize incoming emails in real-time with high accuracy and speed',
            backstory="""You are an expert email organizer specializing in real-time processing. 
            You excel at quickly categorizing emails as they arrive, ensuring inbox stays organized.""",
            verbose=True,
            allow_delegation=False,
            tools=self.get_email_tools()
        )
        
        # Cataloging Agent - Historical email processing  
        self.agents['cataloging'] = Agent(
            role='Email Cataloging Librarian',
            goal='Systematically organize and catalog historical email archives',
            backstory="""You are a meticulous librarian specializing in email archives. 
            You process large volumes of historical emails, creating comprehensive categorization systems.""",
            verbose=True,
            allow_delegation=False,
            tools=self.get_email_tools()
        )
        
        # Reclassification Agent - Label-based reorganization
        self.agents['reclassification'] = Agent(
            role='Email Reclassification Expert',
            goal='Intelligently reclassify and reorganize emails based on evolving label systems',
            backstory="""You are an expert in email taxonomy and classification refinement. 
            You specialize in improving existing categorization systems and fixing misclassified emails.""",
            verbose=True,
            allow_delegation=False,
            tools=self.get_email_tools()
        )
    
    def get_email_tools(self) -> List[BaseTool]:
        """Create custom tools for email processing agents"""
        
        class VectorSearchTool(BaseTool):
            def __init__(self):
                super().__init__(
                    name="vector_search",
                    description="Search similar emails using vector similarity"
                )
            
            def _run(self, query: str, limit: int = 5) -> str:
                # This would be implemented with async wrapper
                return f"Found {limit} similar emails for query: {query}"
        
        class CategoryPredictionTool(BaseTool):
            def __init__(self):
                super().__init__(
                    name="category_prediction",
                    description="Predict email category based on content and context"
                )
            
            def _run(self, email_content: str, context: str = "") -> str:
                # Implement category prediction logic
                return "predicted_category"
        
        class N8nWorkflowTool(BaseTool):
            def __init__(self):
                super().__init__(
                    name="trigger_n8n_workflow",
                    description="Trigger n8n workflow for complex email processing"
                )
            
            def _run(self, workflow_id: str, data: dict) -> str:
                # Trigger n8n workflow
                return f"Workflow {workflow_id} triggered with data"
        
        return [VectorSearchTool(), CategoryPredictionTool(), N8nWorkflowTool()]
    
    async def setup_database(self):
        """Initialize database and create tables"""
        await self.database.connect()
        Base.metadata.create_all(bind=self.engine)
        
        # Initialize Qdrant collection
        await self.setup_qdrant_collection()
    
    async def setup_qdrant_collection(self):
        """Setup Qdrant vector collection for email embeddings"""
        collection_name = "email_embeddings"
        
        try:
            # Check if collection exists
            collections = await self.qdrant_client.get_collections()
            collection_exists = any(col.name == collection_name for col in collections.collections)
            
            if not collection_exists:
                await self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)  # OpenAI embeddings size
                )
                logger.info(f"Created Qdrant collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to setup Qdrant collection: {e}")
    
    def get_db(self):
        """Database dependency"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def setup_routes(self):
        """Setup all API routes"""
        
        @self.app.on_event("startup")
        async def startup():
            await self.setup_database()
            await self.initialize_redis_cache()
            logger.info("Enhanced Email Librarian Server started")
        
        @self.app.on_event("shutdown")
        async def shutdown():
            await self.database.disconnect()
            await self.qdrant_client.close()
            logger.info("Enhanced Email Librarian Server shutdown")
        
        # Health check
        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "services": {
                    "database": "connected" if self.database.is_connected else "disconnected",
                    "qdrant": "available",
                    "langfuse": "configured" if self.langfuse else "not configured",
                    "n8n": "configured" if self.n8n_api_key else "not configured",
                    "redis": "enabled" if self._redis_enabled else "disabled"
                }
            }
        
        # System info route (alternative to root functionality)
        @self.app.get("/system-info", response_class=HTMLResponse)
        async def system_info():
            """Serve system information and API overview"""
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Email Librarian - System Info</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                    .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                    h1 { color: #2563eb; margin-bottom: 20px; }
                    h2 { color: #374151; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; margin-top: 30px; }
                    ul { list-style-type: none; padding: 0; }
                    li { padding: 8px 0; border-bottom: 1px solid #f3f4f6; }
                    a { color: #2563eb; text-decoration: none; }
                    a:hover { text-decoration: underline; }
                    .status { background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🤖 Enhanced Email Librarian - System Information</h1>
                    <p><span class="status">ONLINE</span> System is operational</p>
                    
                    <h2>🔗 Quick Navigation</h2>
                    <ul>
                        <li><a href="/">🏠 Home</a> - Redirects to main dashboard</li>
                        <li><a href="/main.html">📊 Main Dashboard</a> - Primary interface</li>
                        <li><a href="/health">💚 Health Check</a> - System status</li>
                        <li><a href="/docs">📚 API Documentation</a> - Interactive API docs</li>
                        <li><a href="/metrics">📈 Prometheus Metrics</a> - Raw metrics data</li>
                    </ul>
                    
                    <h2>🚀 Integrated Services</h2>
                    <ul>
                        <li>📧 Gmail API Integration</li>
                        <li>🤖 CrewAI Agent System</li>
                        <li>🔄 n8n Workflow Automation</li>
                        <li>🔍 Qdrant Vector Search</li>
                        <li>⚡ Redis Caching</li>
                        <li>📡 WebSocket Support</li>
                    </ul>
                </div>
            </body>
            </html>
            """)
        
        # Redis analytics endpoints
        @self.app.get("/api/analytics/overview")
        async def get_analytics_overview():
            """Get comprehensive analytics overview from Redis cache"""
            try:
                if not self._redis_enabled or not self.cache_manager:
                    return {"error": "Redis analytics not available", "redis_enabled": False}
                
                analytics = await self.cache_manager.get_processing_analytics(days=7)
                
                return {
                    "status": "success",
                    "data": analytics,
                    "redis_enabled": True,
                    "generated_at": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Failed to get analytics overview: {e}")
                return {"error": str(e), "status": "failed"}
        
        @self.app.get("/api/analytics/performance")
        async def get_performance_metrics():
            """Get recent performance metrics from Redis"""
            try:
                if not self._redis_enabled or not self.cache_manager:
                    return {"error": "Redis analytics not available"}
                
                metrics = await self.cache_manager.get_recent_performance_metrics(hours=6)
                
                return {
                    "status": "success",
                    "metrics": metrics,
                    "count": len(metrics),
                    "generated_at": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Failed to get performance metrics: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/cache/health")
        async def redis_health_check():
            """Check Redis cache health and status"""
            try:
                if not self._redis_enabled or not self.cache_manager:
                    return {
                        "status": "disabled",
                        "redis_enabled": False,
                        "message": "Redis caching is not enabled"
                    }
                
                health_data = await self.cache_manager.health_check()
                
                return {
                    "status": "success",
                    **health_data
                }
                
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")
                return {
                    "status": "error",
                    "redis_enabled": True,
                    "error": str(e)
                }
        
        @self.app.get("/api/metrics/live")
        async def get_live_metrics():
            """Get comprehensive live system metrics for dashboard"""
            try:
                current_time = datetime.utcnow()
                
                # Get system health
                health_status = "healthy" if self.database.is_connected else "degraded"
                
                # Get analytics data
                analytics_data = {}
                cache_data = {}
                
                if self._redis_enabled and self.cache_manager:
                    try:
                        # Get analytics overview directly from cache manager
                        analytics_data = await self.cache_manager.get_processing_analytics(days=7)
                        
                        # Get cache health
                        cache_response = await self.cache_manager.health_check()
                        cache_data = cache_response
                        
                    except Exception as e:
                        logger.warning(f"Error getting Redis metrics: {e}")
                
                # Calculate uptime (simple version)
                uptime_hours = 1.0  # Default - in production this would be tracked properly
                
                # Combine all metrics
                live_metrics = {
                    "timestamp": current_time.isoformat(),
                    "health": {
                        "status": health_status,
                        "uptime_hours": uptime_hours,
                        "redis_status": "connected" if self._redis_enabled else "disconnected",
                        "database_status": "connected" if self.database.is_connected else "disconnected",
                        "qdrant_status": "connected" if self.qdrant_client else "disconnected"
                    },
                    "performance": {
                        "avg_processing_time_seconds": analytics_data.get("avg_processing_time", 0),
                        "emails_processed_last_hour": len(analytics_data.get("recent_activity", [])),
                        "total_emails_processed_today": analytics_data.get("total_processed", 0),
                        "processing_speed_trend": "stable",
                        "peak_performance_today": analytics_data.get("peak_performance", 0)
                    },
                    "api_efficiency": {
                        "api_calls_made": analytics_data.get("api_calls_made", 0),
                        "api_calls_saved": analytics_data.get("api_calls_saved", 0),
                        "efficiency_percentage": analytics_data.get("efficiency_percentage", 0),
                        "batch_operations_today": analytics_data.get("batch_operations", 0),
                        "rate_limit_hits": 0,
                        "average_batch_size": analytics_data.get("avg_batch_size", 0)
                    },
                    "processing": {
                        "total_emails_processed": analytics_data.get("total_processed", 0),
                        "success_rate_percentage": analytics_data.get("success_rate", 100),
                        "successful_categorizations": analytics_data.get("successful", 0),
                        "failed_categorizations": analytics_data.get("failed", 0),
                        "category_distribution": analytics_data.get("categories", {}),
                        "average_categories_per_email": 1.5
                    },
                    "cache_status": {
                        "status": cache_data.get("status", "unknown"),
                        "label_cache_size": cache_data.get("label_cache_size", 0),
                        "cache_hit_rate_percentage": cache_data.get("hit_rate", 0),
                        "memory_usage_mb": cache_data.get("memory_usage", 0)
                    },
                    "recent_jobs": analytics_data.get("recent_jobs", [])
                }
                
                return live_metrics
                
            except Exception as e:
                logger.error(f"Error generating live metrics: {e}")
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "health": {"status": "error", "error": str(e)},
                    "performance": {},
                    "api_efficiency": {},
                    "processing": {},
                    "cache_status": {"status": "error"},
                    "recent_jobs": []
                }
        
        @self.app.get("/api/metrics/summary")
        async def get_metrics_summary():
            """Get summarized metrics for quick overview"""
            try:
                # Generate live metrics inline
                current_time = datetime.utcnow()
                health_status = "healthy" if self.database.is_connected else "degraded"
                
                # Get analytics data
                analytics_data = {}
                if self._redis_enabled and self.cache_manager:
                    try:
                        analytics_data = await self.cache_manager.get_processing_analytics(days=7)
                    except Exception as e:
                        logger.warning(f"Error getting Redis metrics: {e}")
                
                return {
                    "status": health_status,
                    "emails_processed_today": analytics_data.get("total_processed", 0),
                    "success_rate": analytics_data.get("success_rate", 100),
                    "avg_processing_time": analytics_data.get("avg_processing_time", 0),
                    "api_efficiency": analytics_data.get("efficiency_percentage", 0),
                    "cache_status": "connected" if self._redis_enabled else "disconnected",
                    "timestamp": current_time.isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error generating metrics summary: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # Metrics endpoint for Prometheus
        @self.app.get("/metrics", response_class=PlainTextResponse)
        async def metrics():
            """Provide basic metrics for Prometheus scraping"""
            try:
                # Basic system metrics in Prometheus format
                metrics_data = []
                
                # Service health metrics
                database_status = 1 if self.database.is_connected else 0
                metrics_data.append(f"email_librarian_database_connected {database_status}")
                
                # Add timestamp metric
                current_time = datetime.utcnow().timestamp()
                metrics_data.append(f"email_librarian_last_check_timestamp {current_time}")
                
                # Add basic service status
                metrics_data.append("email_librarian_service_status 1")
                
                # Return as plain text for Prometheus
                return "\n".join(metrics_data)
                
            except Exception as e:
                logger.error(f"Metrics endpoint error: {e}")
                return "email_librarian_service_status 0"
        
        # Modular frontend route
        @self.app.get("/main.html", response_class=HTMLResponse)
        async def modular_dashboard():
            """Serve the new modular dashboard"""
            import os
            frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
            main_file = os.path.join(frontend_path, "main.html")
            
            if os.path.exists(main_file):
                with open(main_file, 'r', encoding='utf-8') as f:
                    return HTMLResponse(content=f.read())
            else:
                return HTMLResponse(content="""
                <html>
                <head><title>Email Librarian - Modular</title></head>
                <body>
                    <h1>🤖 Email Librarian - Modular Frontend</h1>
                    <p>Modular frontend file not found!</p>
                    <p><a href="/">Back to main dashboard</a></p>
                </body>
                </html>
                """)
        
        # Metrics Dashboard route
        @self.app.get("/metrics-dashboard", response_class=HTMLResponse)
        async def metrics_dashboard():
            """Serve the integrated metrics dashboard"""
            import os
            frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
            metrics_file = os.path.join(frontend_path, "metrics.html")
            
            if os.path.exists(metrics_file):
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    return HTMLResponse(content=f.read())
            else:
                return HTMLResponse(content="""
                <html>
                <head><title>Performance Metrics - Email Librarian</title></head>
                <body>
                    <h1>📊 Performance Metrics</h1>
                    <p>Metrics dashboard file not found!</p>
                    <p><a href="/">Back to main dashboard</a></p>
                </body>
                </html>
                """)
        
        # Job Management Endpoints
        @self.app.post("/api/jobs/create", response_model=Dict[str, str])
        async def create_job(job_config: JobConfig, background_tasks: BackgroundTasks, db: Session = Depends(self.get_db)):
            """Create a new email processing job"""
            job_id = str(uuid.uuid4())
            logger.info(f"Creating job {job_id} with type {job_config.job_type}")
            
            # Create job record
            db_job = EmailProcessingJob(
                id=job_id,
                job_type=job_config.job_type,
                config=job_config.parameters
            )
            db.add(db_job)
            db.commit()
            logger.info(f"Job {job_id} saved to database")
            
            # Start background processing
            logger.info(f"Adding background task for job {job_id}")
            background_tasks.add_task(self.process_job, job_id, job_config)
            logger.info(f"Background task added for job {job_id}")
            
            return {"job_id": job_id, "status": "created"}
        
        @self.app.get("/api/jobs/{job_id}")
        async def get_job_status(job_id: str, db: Session = Depends(self.get_db)):
            """Get job status and results"""
            job = db.query(EmailProcessingJob).filter(EmailProcessingJob.id == job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            
            return {
                "job_id": str(job.id),
                "status": job.status,
                "job_type": job.job_type,
                "created_at": job.created_at.isoformat(),
                "processed_count": job.processed_count,
                "total_count": job.total_count,
                "result": job.result,
                "error_message": job.error_message
            }
        
        # Vector Search Endpoints
        @self.app.post("/api/search/vector")
        async def vector_search(request: VectorSearchRequest):
            """Search emails using vector similarity"""
            try:
                # Generate embedding for query (would use actual embedding model)
                query_vector = [0.0] * 1536  # Placeholder
                
                # Search in Qdrant
                search_result = await self.qdrant_client.search(
                    collection_name="email_embeddings",
                    query_vector=query_vector,
                    limit=request.limit
                )
                
                return {
                    "query": request.query,
                    "results": [
                        {
                            "email_id": hit.id,
                            "score": hit.score,
                            "payload": hit.payload
                        }
                        for hit in search_result
                    ]
                }
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Gmail Labels Endpoint
        @self.app.get("/api/gmail/labels")
        async def get_gmail_labels():
            """Get current Gmail labels with email counts"""
            try:
                # Initialize Gmail organizer if not exists
                if not hasattr(self, 'gmail_organizer') or not self.gmail_organizer:
                    # Use environment variables for credential paths
                    credentials_path = os.getenv('GMAIL_CREDENTIALS_PATH', './config/credentials.json')
                    token_path = os.getenv('GMAIL_TOKEN_PATH', './data/gmail_token.pickle')
                    
                    # Check if credentials file exists
                    if not os.path.exists(credentials_path):
                        logger.warning(f"Gmail credentials not found at {credentials_path}")
                        # Return mock data when credentials are not available
                        mock_labels = [
                            {"name": "Work", "id": "work", "count": 34, "color": "#4285f4"},
                            {"name": "Personal", "id": "personal", "count": 28, "color": "#ea4335"},
                            {"name": "Shopping", "id": "shopping", "count": 15, "color": "#fbbc04"},
                            {"name": "Travel", "id": "travel", "count": 8, "color": "#34a853"},
                            {"name": "Banking", "id": "banking", "count": 12, "color": "#9aa0a6"},
                            {"name": "Newsletters", "id": "newsletters", "count": 45, "color": "#ff6d01"},
                            {"name": "Social", "id": "social", "count": 19, "color": "#ab47bc"},
                            {"name": "Promotions", "id": "promotions", "count": 23, "color": "#00acc1"},
                            {"name": "Updates", "id": "updates", "count": 11, "color": "#7cb342"},
                            {"name": "Receipts", "id": "receipts", "count": 7, "color": "#f57c00"}
                        ]
                        return {"labels": mock_labels, "source": "mock", "message": f"Gmail credentials not found at {credentials_path}"}
                    
                    self.gmail_organizer = GmailAIOrganizer(credentials_file=credentials_path)
                    # Set token path if different from default
                    if token_path != './data/gmail_token.pickle':
                        self.gmail_organizer.token_file = token_path
                    
                # Check if Gmail service is available and authenticated
                if not self.gmail_organizer.service:
                    auth_success = self.gmail_organizer.authenticate()
                    if not auth_success:
                        logger.warning("Gmail authentication failed - returning mock data")
                        # Return mock data when Gmail is not available
                        mock_labels = [
                            {"name": "Work", "id": "work", "count": 34, "color": "#4285f4"},
                            {"name": "Personal", "id": "personal", "count": 28, "color": "#ea4335"},
                            {"name": "Shopping", "id": "shopping", "count": 15, "color": "#fbbc04"},
                            {"name": "Travel", "id": "travel", "count": 8, "color": "#34a853"},
                            {"name": "Banking", "id": "banking", "count": 12, "color": "#9aa0a6"},
                            {"name": "Newsletters", "id": "newsletters", "count": 45, "color": "#ff6d01"},
                            {"name": "Social", "id": "social", "count": 19, "color": "#ab47bc"},
                            {"name": "Promotions", "id": "promotions", "count": 23, "color": "#00acc1"},
                            {"name": "Updates", "id": "updates", "count": 11, "color": "#7cb342"},
                            {"name": "Receipts", "id": "receipts", "count": 7, "color": "#f57c00"}
                        ]
                        return {"labels": mock_labels, "source": "mock", "message": "Gmail authentication failed - using mock data"}
                
                # Double-check that service is now available after authentication
                if not self.gmail_organizer.service:
                    logger.error("Gmail service is still None after authentication attempt")
                    mock_labels = [
                        {"name": "Work", "id": "work", "count": 34, "color": "#4285f4"},
                        {"name": "Personal", "id": "personal", "count": 28, "color": "#ea4335"},
                        {"name": "Shopping", "id": "shopping", "count": 15, "color": "#fbbc04"},
                        {"name": "Travel", "id": "travel", "count": 8, "color": "#34a853"},
                        {"name": "Banking", "id": "banking", "count": 12, "color": "#9aa0a6"},
                        {"name": "Newsletters", "id": "newsletters", "count": 45, "color": "#ff6d01"},
                        {"name": "Social", "id": "social", "count": 19, "color": "#ab47bc"},
                        {"name": "Promotions", "id": "promotions", "count": 23, "color": "#00acc1"},
                        {"name": "Updates", "id": "updates", "count": 11, "color": "#7cb342"},
                        {"name": "Receipts", "id": "receipts", "count": 7, "color": "#f57c00"}
                    ]
                    return {"labels": mock_labels, "source": "mock", "message": "Gmail service unavailable"}
                
                # Get labels from Gmail API - now we know service is not None
                labels_result = self.gmail_organizer.service.users().labels().list(userId='me').execute()
                labels = labels_result.get('labels', [])
                
                # Filter and process labels
                available_labels = []
                
                for label in labels:
                    label_name = label.get('name', '')
                    label_id = label.get('id', '')
                    
                    # Skip system labels
                    if label_name.startswith('CATEGORY_') or label_name.startswith('SYSTEM_') or label_name in ['INBOX', 'SENT', 'DRAFT', 'SPAM', 'TRASH', 'IMPORTANT', 'STARRED', 'UNREAD']:
                        continue
                    
                    try:
                        # Get email count for this label - service is guaranteed to be not None here
                        messages = self.gmail_organizer.service.users().messages().list(
                            userId='me', 
                            labelIds=[label_id], 
                            maxResults=1
                        ).execute()
                        count = messages.get('resultSizeEstimate', 0)
                        
                        # Generate a color for the label (based on name hash)
                        import hashlib
                        hash_val = int(hashlib.md5(label_name.encode()).hexdigest()[:6], 16)
                        color = f"#{hash_val:06x}"
                        
                        available_labels.append({
                            "name": label_name,
                            "id": label_id,
                            "count": count,
                            "color": color
                        })
                    except Exception as label_error:
                        logger.warning(f"Could not get count for label {label_name}: {label_error}")
                        # Add without count
                        import hashlib
                        hash_val = int(hashlib.md5(label_name.encode()).hexdigest()[:6], 16)
                        color = f"#{hash_val:06x}"
                        
                        available_labels.append({
                            "name": label_name,
                            "id": label_id,
                            "count": 0,
                            "color": color
                        })
                
                # Sort by count (descending) and then by name
                available_labels.sort(key=lambda x: (-x['count'], x['name']))
                
                logger.info(f"Retrieved {len(available_labels)} Gmail labels")
                return {"labels": available_labels, "source": "gmail"}
                
            except Exception as e:
                logger.error(f"Failed to get Gmail labels: {e}")
                # Return mock data as fallback
                mock_labels = [
                    {"name": "Work", "id": "work", "count": 34, "color": "#4285f4"},
                    {"name": "Personal", "id": "personal", "count": 28, "color": "#ea4335"},
                    {"name": "Shopping", "id": "shopping", "count": 15, "color": "#fbbc04"},
                    {"name": "Travel", "id": "travel", "count": 8, "color": "#34a853"},
                    {"name": "Banking", "id": "banking", "count": 12, "color": "#9aa0a6"},
                    {"name": "Newsletters", "id": "newsletters", "count": 45, "color": "#ff6d01"},
                    {"name": "Social", "id": "social", "count": 19, "color": "#ab47bc"},
                    {"name": "Promotions", "id": "promotions", "count": 23, "color": "#00acc1"},
                    {"name": "Updates", "id": "updates", "count": 11, "color": "#7cb342"},
                    {"name": "Receipts", "id": "receipts", "count": 7, "color": "#f57c00"}
                ]
                return {"labels": mock_labels, "source": "mock", "message": f"Error: {str(e)}"}
        
        # Gmail Authentication Endpoints
        @self.app.get("/api/gmail/auth/status")
        async def get_auth_status():
            """Check Gmail authentication status"""
            try:
                # Check if credentials exist
                creds_path = os.getenv('GMAIL_CREDENTIALS_PATH', './config/credentials.json')
                token_path = os.getenv('GMAIL_TOKEN_PATH', './data/gmail_token.pickle')
                
                if not os.path.exists(creds_path):
                    return {
                        "authenticated": False,
                        "status": "credentials_missing",
                        "message": "Gmail credentials file not found",
                        "action_required": "upload_credentials"
                    }
                
                # Try to load existing token
                if os.path.exists(token_path):
                    import pickle
                    with open(token_path, 'rb') as token:
                        creds = pickle.load(token)
                    
                    if creds and creds.valid:
                        return {
                            "authenticated": True,
                            "status": "valid",
                            "message": "Gmail authentication is working",
                            "expires_at": creds.expiry.isoformat() if creds.expiry else None
                        }
                    elif creds and creds.expired and creds.refresh_token:
                        return {
                            "authenticated": False,
                            "status": "expired_refreshable",
                            "message": "Token expired but can be refreshed",
                            "action_required": "refresh_token"
                        }
                    else:
                        return {
                            "authenticated": False,
                            "status": "invalid",
                            "message": "Token exists but is invalid",
                            "action_required": "reauthorize"
                        }
                else:
                    return {
                        "authenticated": False,
                        "status": "no_token",
                        "message": "No authentication token found",
                        "action_required": "authorize"
                    }
                    
            except Exception as e:
                logger.error(f"Error checking auth status: {e}")
                return {
                    "authenticated": False,
                    "status": "error",
                    "message": f"Error checking authentication: {str(e)}",
                    "action_required": "reauthorize"
                }

        @self.app.post("/api/gmail/auth/refresh")
        async def refresh_gmail_auth():
            """Refresh Gmail authentication token"""
            try:
                token_path = os.getenv('GMAIL_TOKEN_PATH', './data/gmail_token.pickle')
                
                if not os.path.exists(token_path):
                    raise HTTPException(status_code=404, detail="No token file found")
                
                import pickle
                from google.auth.transport.requests import Request
                
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
                
                if not creds or not creds.refresh_token:
                    raise HTTPException(status_code=400, detail="No refresh token available")
                
                # Refresh the token
                creds.refresh(Request())
                
                # Save refreshed token
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
                
                # Update the Gmail organizer with new credentials
                if self.gmail_organizer:
                    self.gmail_organizer.creds = creds
                    self.gmail_organizer.service = None  # Will be rebuilt on next use
                
                logger.info("Gmail token refreshed successfully")
                
                return {
                    "success": True,
                    "message": "Gmail authentication refreshed successfully",
                    "expires_at": creds.expiry.isoformat() if creds.expiry else None
                }
                
            except Exception as e:
                logger.error(f"Failed to refresh Gmail token: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to refresh token: {str(e)}")

        @self.app.get("/api/gmail/auth/authorize-url")
        async def get_auth_url():
            """Get Gmail OAuth authorization URL"""
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
                
                creds_path = os.getenv('GMAIL_CREDENTIALS_PATH', './config/credentials.json')
                if not os.path.exists(creds_path):
                    raise HTTPException(status_code=404, detail="Credentials file not found")
                
                SCOPES = [
                    'https://www.googleapis.com/auth/gmail.readonly',
                    'https://www.googleapis.com/auth/gmail.modify', 
                    'https://www.googleapis.com/auth/gmail.labels'
                ]
                
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                
                # Configure for web application
                flow.redirect_uri = "http://localhost:8000/api/gmail/auth/callback"
                
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                # Store flow state temporarily (in production, use Redis or proper session storage)
                self._oauth_flow = flow
                
                return {
                    "auth_url": auth_url,
                    "message": "Visit this URL to authorize Gmail access"
                }
                
            except Exception as e:
                logger.error(f"Failed to generate auth URL: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to generate auth URL: {str(e)}")

        @self.app.get("/api/gmail/auth/callback")
        async def auth_callback(code: str, state: Optional[str] = None):
            """Handle OAuth callback"""
            try:
                if not hasattr(self, '_oauth_flow') or not self._oauth_flow:
                    raise HTTPException(status_code=400, detail="No active OAuth flow")
                
                # Exchange code for token
                self._oauth_flow.fetch_token(code=code)
                creds = self._oauth_flow.credentials
                
                # Save token
                token_path = os.getenv('GMAIL_TOKEN_PATH', './data/gmail_token.pickle')
                os.makedirs(os.path.dirname(token_path), exist_ok=True)
                
                import pickle
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
                
                # Update Gmail organizer
                if self.gmail_organizer:
                    self.gmail_organizer.creds = creds
                    self.gmail_organizer.service = None  # Will be rebuilt
                
                # Clean up flow
                self._oauth_flow = None
                
                logger.info("Gmail authentication completed successfully")
                
                return HTMLResponse("""
                <html>
                    <body>
                        <h2>✅ Gmail Authentication Successful!</h2>
                        <p>You can now close this window and return to your Email Librarian dashboard.</p>
                        <script>
                            setTimeout(() => window.close(), 3000);
                        </script>
                    </body>
                </html>
                """)
                
            except Exception as e:
                logger.error(f"OAuth callback failed: {e}")
                return HTMLResponse(f"""
                <html>
                    <body>
                        <h2>❌ Authentication Failed</h2>
                        <p>Error: {str(e)}</p>
                        <p>Please try again from your dashboard.</p>
                    </body>
                </html>
                """, status_code=400)
        
        # Agent Task Endpoints
        @self.app.post("/api/agents/execute")
        async def execute_agent_task(request: AgentTaskRequest, background_tasks: BackgroundTasks, db: Session = Depends(self.get_db)):
            """Execute a task using CrewAI agents"""
            execution_id = str(uuid.uuid4())
            
            # Create agent execution record
            db_execution = AgentExecution(
                id=execution_id,
                agent_name=request.agent_type,
                task_description=request.task_description
            )
            db.add(db_execution)
            db.commit()
            
            # Start agent execution
            background_tasks.add_task(self.execute_crew_task, execution_id, request)
            
            return {"execution_id": execution_id, "status": "started"}
        
        @self.app.get("/api/agents/executions/{execution_id}")
        async def get_agent_execution(execution_id: str, db: Session = Depends(self.get_db)):
            """Get agent execution status"""
            execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
            if not execution:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            return {
                "execution_id": str(execution.id),
                "agent_name": execution.agent_name,
                "status": execution.status,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at is not None else None,
                "result": execution.result,
                "langfuse_trace_id": execution.langfuse_trace_id
            }
        
        # n8n Integration Endpoints
        @self.app.post("/api/n8n/trigger/{workflow_id}")
        async def trigger_n8n_workflow(workflow_id: str, data: Dict[str, Any]):
            """Trigger n8n workflow"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.n8n_base_url}/api/v1/workflows/{workflow_id}/execute",
                        json=data,
                        headers={"X-N8N-API-KEY": self.n8n_api_key} if self.n8n_api_key else {}
                    )
                    response.raise_for_status()
                    return response.json()
            except Exception as e:
                logger.error(f"n8n workflow trigger failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # Function Control Endpoints for Dashboard Integration
        @self.app.post("/api/functions/shelving/start")
        async def start_shelving_function(background_tasks: BackgroundTasks, db: Session = Depends(self.get_db)):
            """Start real-time email shelving function"""
            try:
                logger.info("Starting shelving function from dashboard")
                
                # Create a shelving job configuration
                job_config = JobConfig(
                    job_type="shelving",
                    parameters={
                        "max_emails": 50,
                        "batch_size": 10,
                        "continuous_monitoring": True,
                        "real_time": True
                    }
                )
                
                # Create job record
                job_id = str(uuid.uuid4())
                db_job = EmailProcessingJob(
                    id=job_id,
                    job_type="shelving",
                    config=job_config.parameters,
                    status="running"
                )
                db.add(db_job)
                db.commit()
                
                # Start background processing
                background_tasks.add_task(self.start_continuous_shelving, job_id)
                
                # Store the active shelving job ID for stopping later
                self.active_shelving_job_id = job_id
                
                return {
                    "status": "success",
                    "message": "Shelving function started",
                    "job_id": job_id
                }
                
            except Exception as e:
                logger.error(f"Failed to start shelving function: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/functions/shelving/stop")
        async def stop_shelving_function(db: Session = Depends(self.get_db)):
            """Stop real-time email shelving function"""
            try:
                logger.info("Stopping shelving function from dashboard")
                
                # Stop the active shelving job
                if hasattr(self, 'active_shelving_job_id') and self.active_shelving_job_id:
                    await self.update_job_status(self.active_shelving_job_id, "stopped")
                    self.shelving_active = False
                    self.active_shelving_job_id = None
                
                return {
                    "status": "success",
                    "message": "Shelving function stopped"
                }
                
            except Exception as e:
                logger.error(f"Failed to stop shelving function: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/functions/shelving/status")
        async def get_shelving_status():
            """Get current shelving function status"""
            try:
                is_active = getattr(self, 'shelving_active', False)
                job_id = getattr(self, 'active_shelving_job_id', None)
                
                return {
                    "active": is_active,
                    "job_id": job_id,
                    "status": "running" if is_active else "stopped"
                }
                
            except Exception as e:
                logger.error(f"Failed to get shelving status: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/functions/shelving/activity")
        async def get_shelving_activity():
            """Get recent shelving activity for dashboard updates"""
            try:
                # Get recent activity from Redis cache if available
                if self._redis_enabled and self.cache_manager:
                    analytics = await self.cache_manager.get_processing_analytics(days=1)
                    recent_jobs = analytics.get("recent_jobs", [])
                    
                    # Format activity for dashboard
                    activity = []
                    for job in recent_jobs[-10:]:  # Last 10 activities
                        activity.append({
                            "id": job.get("id", str(uuid.uuid4())),
                            "action": self.format_activity_message(job),
                            "timestamp": job.get("timestamp", "just now")
                        })
                    
                    return {
                        "status": "success",
                        "activity": activity
                    }
                else:
                    # Return empty if no cache available
                    return {
                        "status": "success",
                        "activity": []
                    }
                    
            except Exception as e:
                logger.error(f"Failed to get shelving activity: {e}")
                return {
                    "status": "error", 
                    "error": str(e),
                    "activity": []
                }

        @self.app.post("/api/functions/cataloging/start")
        async def start_cataloging_function(
            start_date: str = ,
            end_date: str = None,
            batch_size: int = 50,
            background_tasks: BackgroundTasks = BackgroundTasks(),
            db: Session = Depends(self.get_db)
        ):
            """Start email cataloging function"""
            try:
                logger.info("Starting cataloging function from dashboard")
                
                job_config = JobConfig(
                    job_type="cataloging",
                    parameters={
                        "start_date": start_date,
                        "end_date": end_date,
                        "batch_size": batch_size,
                        "max_emails": 1000
                    }
                )
                
                job_id = str(uuid.uuid4())
                db_job = EmailProcessingJob(
                    id=job_id,
                    job_type="cataloging",
                    config=job_config.parameters
                )
                db.add(db_job)
                db.commit()
                
                background_tasks.add_task(self.process_job, job_id, job_config)
                
                return {
                    "status": "success",
                    "message": "Cataloging function started",
                    "job_id": job_id
                }
                
            except Exception as e:
                logger.error(f"Failed to start cataloging function: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/functions/reclassification/start")
        async def start_reclassification_function(
            source_label: str,
            target_categories: List[str],
            background_tasks: BackgroundTasks = BackgroundTasks(),
            db: Session = Depends(self.get_db)
        ):
            """Start email reclassification function"""
            try:
                logger.info("Starting reclassification function from dashboard")
                
                job_config = JobConfig(
                    job_type="reclassification",
                    parameters={
                        "source_label": source_label,
                        "target_categories": target_categories,
                        "max_emails": 500
                    }
                )
                
                job_id = str(uuid.uuid4())
                db_job = EmailProcessingJob(
                    id=job_id,
                    job_type="reclassification",
                    config=job_config.parameters
                )
                db.add(db_job)
                db.commit()
                
                background_tasks.add_task(self.process_job, job_id, job_config)
                
                return {
                    "status": "success",
                    "message": "Reclassification function started",
                    "job_id": job_id
                }
                
            except Exception as e:
                logger.error(f"Failed to start reclassification function: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # WebSocket for real-time updates
        @self.app.websocket("/ws/librarian")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
            
            try:
                while True:
                    data = await websocket.receive_text()
                    # Handle incoming WebSocket messages
                    await self.handle_websocket_message(websocket, data)
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)
    
    async def process_job(self, job_id: str, job_config: JobConfig):
        """Process email organization job with enhanced features"""
        logger.info(f"🚀 Starting process_job for {job_id} with type {job_config.job_type}")
        try:
            # Update job status
            logger.info(f"Updating job {job_id} status to running")
            await self.update_job_status(job_id, "running")
            logger.info(f"Job {job_id} status updated to running")
            
            # Initialize LangFuse tracing
            trace = None
            task_result = None  # Ensure task_result is always defined
            if job_config.enable_langfuse_tracking and self.langfuse is not None:
                trace = self.langfuse.trace(
                    name=f"email_processing_{job_config.job_type}",
                    metadata={"job_id": job_id, "config": job_config.parameters}
                )
            
            # Trigger n8n workflow if specified
            if job_config.n8n_workflow_url:
                await self.trigger_n8n_workflow_by_url(job_config.n8n_workflow_url, {
                    "job_id": job_id,
                    "job_type": job_config.job_type,
                    "parameters": job_config.parameters
                })
            
            # Execute actual email processing based on job type
            if job_config.job_type == "shelving":
                task_result = await self.process_shelving_job(job_id, job_config.parameters)
            elif job_config.job_type == "cataloging":
                task_result = await self.process_cataloging_job(job_id, job_config.parameters)
            elif job_config.job_type == "reclassification":
                task_result = await self.process_reclassification_job(job_id, job_config.parameters)
            else:
                # Fallback to CrewAI if available (legacy support)
                agent_type = job_config.job_type + "_agent"
                if agent_type.replace("_agent", "") in self.agents:
                    task_result = await self.execute_agent_task_internal(
                        agent_type, 
                        f"Process emails for {job_config.job_type}",
                        job_config.parameters
                    )
                else:
                    raise ValueError(f"Unknown job type: {job_config.job_type}")
            
            # Update job completion
            await self.update_job_status(job_id, "completed", result=task_result)
            
            # Cache job statistics in Redis for analytics
            if self._redis_enabled and self.cache_manager and task_result:
                await self._cache_job_analytics(job_id, task_result)
            
            # Broadcast update to WebSocket clients
            await self.broadcast_job_update(job_id, "completed")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            await self.update_job_status(job_id, "failed", error_message=str(e))
            await self.broadcast_job_update(job_id, "failed")

    async def process_shelving_job(self, job_id: str, parameters: dict) -> dict:
        """Enhanced shelving job with Qdrant vector search and intelligent label creation"""
        try:
            logger.info(f"Starting enhanced shelving job {job_id} with Qdrant integration")
            
            # Ensure Gmail organizer is initialized
            if not hasattr(self, 'gmail_organizer') or not self.gmail_organizer:
                # Initialize Gmail organizer
                logger.info("🔧 Initializing Gmail organizer for shelving job...")
                credentials_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "credentials.json")
                token_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "gmail_token.pickle")
                
                logger.info(f"📁 Credentials path: {credentials_path}")
                logger.info(f"🔑 Token path: {token_path}")
                
                try:
                    self.gmail_organizer = GmailAIOrganizer(credentials_file=credentials_path)
                    logger.info("✅ GmailAIOrganizer instance created")
                    
                    if os.path.exists(token_path):
                        self.gmail_organizer.token_file = token_path
                        logger.info("✅ Token file path set")
                    else:
                        logger.warning("⚠️ Token file not found at expected path")
                    
                    if not self.gmail_organizer.service:
                        logger.info("🔐 Gmail service not initialized, attempting authentication...")
                        auth_success = self.gmail_organizer.authenticate()
                        if not auth_success:
                            logger.error("❌ Gmail authentication failed")
                            raise Exception("Gmail authentication failed")
                        else:
                            logger.info("✅ Gmail authentication successful")
                    else:
                        logger.info("✅ Gmail service already initialized")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to initialize Gmail organizer: {e}")
                    raise Exception(f"Failed to initialize Gmail organizer: {e}")
            else:
                logger.info("✅ Gmail organizer already available")
            
            # Test Gmail service connectivity
            if self.gmail_organizer and self.gmail_organizer.service:
                try:
                    logger.info("🔍 Testing Gmail service connectivity...")
                    profile = self.gmail_organizer.service.users().getProfile(userId='me').execute()
                    email_address = profile.get('emailAddress', 'Unknown')
                    logger.info(f"✅ Gmail service connected successfully - Email: {email_address}")
                    
                    # Test label access
                    labels_test = self.gmail_organizer.service.users().labels().list(userId='me').execute()
                    label_count = len(labels_test.get('labels', []))
                    logger.info(f"✅ Gmail labels accessible - Found {label_count} existing labels")
                    
                except Exception as e:
                    logger.error(f"❌ Gmail service test failed: {e}")
                    raise Exception(f"Gmail service not properly connected: {e}")
                
            # Get parameters with defaults
            batch_size = parameters.get('batch_size', 20)
            max_emails = parameters.get('max_emails', 100)
            enable_vector_storage = parameters.get('enable_vector_storage', True)
            similarity_threshold = parameters.get('similarity_threshold', 0.8)
            apply_labels = parameters.get('apply_labels', True)
            
            logger.info(f"Processing up to {max_emails} emails in batches of {batch_size} with Qdrant integration")
            logger.info(f"Vector storage: {enable_vector_storage}, Similarity threshold: {similarity_threshold}")
            
            # Initialize counters
            processed_count = 0
            categorized_count = 0
            categories_created = set()
            vectors_stored = 0
            labels_applied = 0
            
            # Get messages from Gmail
            messages_result = None
            try:
                if self.gmail_organizer and self.gmail_organizer.service:
                    messages_result = self.gmail_organizer.service.users().messages().list(
                        userId='me', 
                        maxResults=max_emails,
                        q='in:inbox'  # Focus on inbox for shelving
                    ).execute()
                else:
                    logger.warning("⚠️ Gmail Organizer Users is None after from_url")
                if messages_result is not None:
                    messages = messages_result.get('messages', [])
                    logger.info(f"Found {len(messages)} messages to process with Qdrant integration")
                else:
                    messages = []
                    logger.warning("No messages retrieved from Gmail.")
                # Process messages in optimized batches using Gmail Batch API
                email_categories_batch = []  # Collect email-category pairs for batch label processing
                
                for i in range(0, len(messages), batch_size):
                    batch = messages[i:i + batch_size]
                    logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} messages with Batch API")
                    
                    # OPTIMIZATION: Use Gmail Batch API to get multiple messages in single request
                    batch_messages = await self._get_messages_batch([msg['id'] for msg in batch])
                    
                    # 🚀 PARALLEL VECTOR PROCESSING: Process all emails in batch concurrently
                    if enable_vector_storage:
                        parallel_results = await self._process_batch_with_parallel_vectors(
                            batch, batch_messages, similarity_threshold
                        )
                        
                        # Update counters from parallel processing results
                        for result in parallel_results:
                            if result['success']:
                                if result['category'] and result['category'] != 'Uncategorized':
                                    categories_created.add(result['category'])
                                    categorized_count += 1
                                    
                                    # Collect for batch label processing
                                    if apply_labels:
                                        email_categories_batch.append((result['message_id'], result['category']))
                                
                                if result['vector_stored']:
                                    vectors_stored += 1
                                
                                logger.info(f"Parallel processed: '{result['subject'][:50]}...' -> {result['category']}")
                            
                            processed_count += 1
                    else:
                        # Fallback to simple processing without vectors
                        for j, msg in enumerate(batch_messages):
                            try:
                                message_id = batch[j]['id']
                                
                                # Extract email content
                                headers = msg.get('payload', {}).get('headers', [])
                                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                                snippet = msg.get('snippet', '')
                                
                                # Simple categorization without vectors
                                category = self._categorize_email_simple(subject, snippet)
                                
                                if category and category != 'Uncategorized':
                                    categories_created.add(category)
                                    categorized_count += 1
                                    
                                    # Collect for batch label processing
                                    if apply_labels:
                                        email_categories_batch.append((message_id, category))
                                
                                processed_count += 1
                                logger.info(f"Simple categorized: '{subject[:50]}...' -> {category}")
                                
                            except Exception as e:
                                logger.error(f"Error in simple processing: {e}")
                                processed_count += 1
                    
                    # BATCH LABEL OPTIMIZATION: Apply labels in batches every few processing batches
                    if len(email_categories_batch) >= 50 or (i + batch_size >= len(messages)):  # Apply labels every 50 emails or at the end
                        if email_categories_batch and apply_labels:
                            logger.info(f"🏷️ Applying labels in batch for {len(email_categories_batch)} emails")
                            batch_labels_applied = await self._apply_labels_batch(email_categories_batch)
                            labels_applied += batch_labels_applied
                            email_categories_batch = []  # Clear the batch after processing
                            
                            # Update job status after batch label application
                            await self.update_job_status(job_id, "running", result={
                                "processed_count": processed_count,
                                "categorized_count": categorized_count,
                                "vectors_stored": vectors_stored,
                                "labels_applied": labels_applied,
                                "total_count": len(messages),
                                "categories_created": list(categories_created)
                            })
                
                # Final results
                result = {
                    "processed_count": processed_count,
                    "categorized_count": categorized_count,
                    "vectors_stored": vectors_stored,
                    "labels_applied": labels_applied,
                    "total_count": len(messages),
                    "categories_created": list(categories_created),
                    "similarity_threshold": similarity_threshold,
                    "vector_storage_enabled": enable_vector_storage,
                    "labels_applied_enabled": apply_labels,
                    "job_type": "shelving",
                    "status": "completed"
                }
                
                logger.info(f"Enhanced shelving job {job_id} completed with Qdrant: {result}")
                return result
                
            except Exception as e:
                raise Exception(f"Error accessing Gmail: {e}")
                
        except Exception as e:
            logger.error(f"Enhanced shelving job {job_id} failed: {e}")
            raise e

    def _categorize_email_simple(self, subject: str, snippet: str) -> str:
        """Simple email categorization logic"""
        subject_lower = subject.lower()
        snippet_lower = snippet.lower()
        
        # Shopping/Commerce
        if any(keyword in subject_lower for keyword in ['order', 'receipt', 'purchase', 'invoice', 'payment', 'confirmation']):
            return 'Shopping'
        
        # Social Media
        if any(keyword in subject_lower for keyword in ['facebook', 'twitter', 'linkedin', 'instagram', 'notification']):
            return 'Social Media'
        
        # Finance
        if any(keyword in subject_lower for keyword in ['bank', 'account', 'credit', 'statement', 'balance']):
            return 'Finance'
        
        # Work/Business
        if any(keyword in subject_lower for keyword in ['meeting', 'deadline', 'project', 'report', 'colleague']):
            return 'Work'
        
        # Personal
        if any(keyword in subject_lower for keyword in ['family', 'friend', 'personal', 'birthday']):
            return 'Personal'
        
        # News/Updates
        if any(keyword in subject_lower for keyword in ['newsletter', 'update', 'news', 'digest']):
            return 'News'
        
        return 'Uncategorized'

    async def _generate_email_embedding(self, content: str) -> List[float]:
        """Generate embedding for email content using deterministic hash-based approach"""
        try:
            import hashlib
            import numpy as np
            
            # Create deterministic embedding based on content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()
            np.random.seed(int(content_hash[:8], 16))
            embedding = np.random.normal(0, 1, 1536).tolist()
            
            # Normalize the embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = (np.array(embedding) / norm).tolist()
            
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * 1536

    async def _find_similar_emails(self, embedding: List[float], threshold: float = 0.8) -> List[dict]:
        """Find similar emails using Qdrant vector search"""
        try:
            search_result = await self.qdrant_client.search(
                collection_name="email_embeddings",
                query_vector=embedding,
                limit=10,
                score_threshold=threshold
            )
            
            if search_result:
                return [
                    {
                        "email_id": hit.payload.get("email_id"),
                        "category": hit.payload.get("category"),
                        "subject": hit.payload.get("subject"),
                        "similarity_score": hit.score
                    }
                    for hit in search_result
                    if hit.payload
                ]
            else:
                logger.warning("Payload is incomplete")
                return []
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    async def _categorize_email_with_vectors(self, content: str, similar_emails: List[dict], 
                                           subject: str, snippet: str) -> str:
        """Categorize email using vector similarity and existing categories"""
        
        # If we found similar emails, use their categories
        if similar_emails:
            # Get most common category from similar emails
            categories = [email["category"] for email in similar_emails if email["category"] and email["category"] != 'Uncategorized']
            if categories:
                from collections import Counter
                most_common_category = Counter(categories).most_common(1)[0][0]
                logger.info(f"Categorized by similarity: '{subject[:50]}...' -> {most_common_category} (confidence: {len([c for c in categories if c == most_common_category])}/{len(categories)})")
                return most_common_category
        
        # Fallback to keyword-based categorization
        return self._categorize_email_simple(subject, snippet)

    async def _apply_gmail_label(self, message_id: str, category: str):
        """Apply Gmail label to email with caching optimization"""
        try:
            logger.info(f"🏷️ Starting label application - Email: {message_id}, Category: '{category}'")
            
            # Get or create label (with caching)
            logger.info(f"🔍 Getting or creating Gmail label for category: '{category}'")
            label_id = await self._get_or_create_gmail_label_cached(category)
            logger.info(f"✅ Label ID retrieved: {label_id}")
            
            # Apply label to message
            if self.gmail_organizer and self.gmail_organizer.service:
                logger.info(f"📧 Applying label '{category}' (ID: {label_id}) to message {message_id}")
                
                modify_request = {
                    'addLabelIds': [label_id],
                    'removeLabelIds': []  # Keep in inbox for now
                }
                logger.info(f"🔧 Gmail modify request: {modify_request}")
                
                result = self.gmail_organizer.service.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body=modify_request
                ).execute()
                
                logger.info(f"✅ Successfully applied label '{category}' to message {message_id}")
                logger.info(f"📊 Gmail API response: {result.get('labelIds', [])}")
                
                # Verify the label was applied
                updated_labels = result.get('labelIds', [])
                if label_id in updated_labels:
                    logger.info(f"✅ Label verification successful - '{category}' is now on email {message_id}")
                else:
                    logger.warning(f"⚠️ Label verification failed - '{category}' not found in updated labels: {updated_labels}")
                    
            else:
                logger.error(f"❌ Gmail organizer or service not available for label application")
                raise Exception("Gmail service not available")
            
        except Exception as e:
            logger.error(f"❌ Failed to apply label '{category}' to {message_id}: {e}")
            logger.error(f"💥 Label application error details: {type(e).__name__}: {str(e)}")
            raise

    async def _apply_labels_batch(self, email_categories: List[Tuple[str, str]]) -> int:
        """Apply labels to multiple emails concurrently for maximum efficiency"""
        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            from collections import defaultdict
            
            if not email_categories:
                return 0
            
            logger.info(f"🏷️ Starting batch label application for {len(email_categories)} emails")
            
            # Group emails by category to minimize label lookups
            category_groups = defaultdict(list)
            for email_id, category in email_categories:
                if category and category != 'Uncategorized':
                    category_groups[category].append(email_id)
            
            if not category_groups:
                logger.info("No valid categories to apply labels for")
                return 0
            
            # Phase 1: Get all unique label IDs concurrently
            unique_categories = list(category_groups.keys())
            logger.info(f"🎯 Getting label IDs for {len(unique_categories)} unique categories")
            
            label_tasks = [
                self._get_or_create_gmail_label_cached(category)
                for category in unique_categories
            ]
            
            try:
                label_ids = await asyncio.gather(*label_tasks, return_exceptions=True)
                
                # Filter out failed label creations
                category_to_label = {}
                for category, label_id in zip(unique_categories, label_ids):
                    if not isinstance(label_id, Exception):
                        category_to_label[category] = label_id
                    else:
                        logger.error(f"Failed to get label for category '{category}': {label_id}")
                
                logger.info(f"✅ Successfully retrieved {len(category_to_label)} label IDs")
                
            except Exception as e:
                logger.error(f"Failed to get label IDs: {e}")
                return 0
            
            # Phase 2: Apply labels concurrently with optimized batching
            modification_tasks = []
            total_emails_to_label = 0
            
            for category, email_ids in category_groups.items():
                if category in category_to_label:
                    label_id = category_to_label[category]
                    
                    # Create concurrent tasks for each email in this category
                    for email_id in email_ids:
                        task = self._apply_single_label_async_with_retry(email_id, label_id, category)
                        modification_tasks.append(task)
                        total_emails_to_label += 1
            
            logger.info(f"📧 Applying labels to {total_emails_to_label} emails concurrently")
            
            # Execute all label modifications in parallel with semaphore for rate limiting
            semaphore = asyncio.Semaphore(10)  # Limit concurrent API calls to avoid rate limiting
            
            async def rate_limited_apply(task):
                async with semaphore:
                    return await task
            
            rate_limited_tasks = [rate_limited_apply(task) for task in modification_tasks]
            results = await asyncio.gather(*rate_limited_tasks, return_exceptions=True)
            
            # Analyze results
            successful_applications = len([r for r in results if not isinstance(r, Exception)])
            failed_applications = len([r for r in results if isinstance(r, Exception)])
            
            # Log failed applications for debugging
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Label application failed for email {i}: {result}")
            
            logger.info(f"🎉 Batch label application complete: {successful_applications} successful, {failed_applications} failed")
            
            return successful_applications
            
        except Exception as e:
            logger.error(f"Batch label application failed: {e}")
            return 0

    async def _apply_single_label_async_with_retry(self, email_id: str, label_id: str, category: str, max_retries: int = 3) -> bool:
        """Async wrapper for individual label application with smart retry logic"""
        import asyncio
        import random

        for attempt in range(max_retries + 1):
            if self.gmail_organizer and self.gmail_organizer.service:
                try:
                    # Use asyncio.to_thread to run blocking code in a thread
                    await asyncio.to_thread(
                        self.gmail_organizer.service.users().messages().modify(
                            userId='me',
                            id=email_id,
                            body={
                                'addLabelIds': [label_id],
                                'removeLabelIds': []
                            }
                        ).execute
                    )
                    logger.debug(f"✅ Applied label '{category}' to email {email_id}")
                    return True

                except Exception as e:
                    if attempt < max_retries:
                        # Check if it's a rate limit error
                        resp = getattr(e, 'resp', None)
                        is_rate_limit_error = resp and hasattr(resp, 'status') and resp.status in [429, 503]
                        base_delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        jitter = random.uniform(0.5, 1.5)
                        wait_time = base_delay * jitter

                        if is_rate_limit_error:
                            logger.warning(f"Rate limit hit for {email_id}, retrying in {wait_time:.2f}s (attempt {attempt + 1})")
                        else:
                            logger.warning(f"API error for {email_id}: {e}, retrying in {wait_time:.2f}s (attempt {attempt + 1})")

                        await asyncio.sleep(wait_time)
                    else:
                        # Final attempt failed
                        logger.error(f"❌ Failed to apply label '{category}' to {email_id} after {max_retries + 1} attempts: {e}")
                        return False
        logger.error(f"❌ Failed to apply label '{category}' to {email_id}: Gmail organizer or service not initialized.")
        return False

    async def _process_batch_with_parallel_vectors(self, batch_ids: List[Dict], batch_messages: List[Dict], similarity_threshold: float) -> List[Dict]:
        """Process email batch with parallel vector operations for maximum performance"""
        import asyncio
        import uuid
        from datetime import datetime
        email_data = []
        try:
            logger.info(f"🚀 Starting parallel vector processing for {len(batch_messages)} emails")
            
            # Phase 1: Extract email content and prepare for parallel processing
           
            for j, msg in enumerate(batch_messages):
                try:
                    message_id = batch_ids[j]['id']
                    headers = msg.get('payload', {}).get('headers', [])
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                    snippet = msg.get('snippet', '')
                    
                    email_content = f"Subject: {subject}\nFrom: {sender}\nContent: {snippet}"
                    
                    email_data.append({
                        'message_id': message_id,
                        'subject': subject,
                        'sender': sender,
                        'snippet': snippet,
                        'content': email_content
                    })
                except Exception as e:
                    logger.warning(f"Failed to extract email data for batch item {j}: {e}")
                    continue
            
            if not email_data:
                logger.warning("No valid email data extracted for parallel processing")
                return []
            
            # Phase 2: Generate all embeddings in parallel
            logger.info(f"⚡ Generating {len(email_data)} embeddings in parallel")
            embedding_tasks = [
                self._generate_email_embedding(email['content'])
                for email in email_data
            ]
            
            embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)
            
            # Phase 3: Process similarity searches in parallel
            logger.info(f"🔍 Processing {len(embeddings)} similarity searches in parallel")
            similarity_tasks = []
            valid_embeddings = []
            
            for i, embedding in enumerate(embeddings):
                if isinstance(embedding, list):
                    similarity_tasks.append(self._find_similar_emails(embedding, similarity_threshold))
                    valid_embeddings.append((i, embedding, email_data[i]))
                else:
                    logger.warning(f"Skipping email {i} due to embedding failure: {embedding}")
                    valid_embeddings.append((i, None, email_data[i]))
            
            # Execute similarity searches concurrently
            if similarity_tasks:
                similarity_results = await asyncio.gather(*similarity_tasks, return_exceptions=True)
            else:
                similarity_results = []
            
            # Phase 4: Process categorization and prepare Qdrant points
            logger.info(f"🧠 Processing categorization for {len(valid_embeddings)} emails")
            
            processing_tasks = []
            for i, (original_idx, embedding, email) in enumerate(valid_embeddings):
                if embedding is not None and i < len(similarity_results):
                    # Ensure similar_emails is a valid list, not an exception
                    if isinstance(similarity_results[i], Exception):
                        similar_emails = []  # Use empty list for failed similarity searches
                    elif isinstance(similarity_results[i], list):
                        similar_emails = similarity_results[i]  # Use the actual results
                    else:
                        similar_emails = []  # Fallback for unexpected types

                    # Ensure similar_emails is always a list
                    if not isinstance(similar_emails, list):
                        similar_emails = []

                    task = self._process_single_email_vector(email, embedding, similar_emails)
                    processing_tasks.append(task)
                else:
                    # Fallback processing for failed embeddings
                    task = self._process_single_email_fallback(email)
                    processing_tasks.append(task)
            
            # Execute all processing tasks in parallel
            processing_results = await asyncio.gather(*processing_tasks, return_exceptions=True)
            
            # Phase 5: Batch Qdrant storage for optimal performance
            valid_points = []
            results = []
            
            for result in processing_results:
                if isinstance(result, Exception):
                    logger.warning(f"Processing task failed: {result}",exc_info=True)
                    results.append({
                        'success': False,
                        'message_id': 'unknown',
                        'category': 'Uncategorized',
                        'subject': 'Unknown',
                        'vector_stored': False
                    })
                else:
                    results.append(result)
                    if isinstance(result, dict) and result.get('success') and result.get('point'):
                        valid_points.append(result['point'])
            
            # Batch upsert to Qdrant for maximum efficiency
            if valid_points:
                logger.info(f"💾 Batch storing {len(valid_points)} vectors in Qdrant")
                try:
                    await self.qdrant_client.upsert(
                        collection_name="email_embeddings",
                        points=valid_points
                    )
                    logger.info(f"✅ Successfully stored {len(valid_points)} vectors in Qdrant")
                except Exception as e:
                    logger.error(f"Batch Qdrant storage failed: {e}")
                    # Mark affected results as not stored
                    for result in results:
                        if result.get('point') in valid_points:
                            result['vector_stored'] = False
            
            # Phase 6: Batch PostgreSQL metadata storage
            metadata_tasks = []
            for result in results:
                if result['success'] and result.get('vector_stored', False):
                    task = self._store_email_vector(
                        result['message_id'],
                        result['subject'],
                        result['sender'],
                        result['category'],
                        result['point_id']
                    )
                    metadata_tasks.append(task)
            
            if metadata_tasks:
                logger.info(f"📊 Storing {len(metadata_tasks)} metadata records in PostgreSQL")
                await asyncio.gather(*metadata_tasks, return_exceptions=True)
            
            logger.info(f"🎉 Parallel vector processing complete: {len([r for r in results if r['success']])} successful, {len([r for r in results if not r['success']])} failed")
            
            return results
            
        except Exception as e:
            logger.error(f"Parallel vector processing failed: {e}")
            # Return fallback results
            if email_data:
                return [
                    {
                        'success': False,
                        'message_id': email.get('message_id', 'unknown'),
                        'category': 'Uncategorized',
                        'subject': email.get('subject', 'Unknown'),
                        'vector_stored': False
                    }
                    for email in email_data
                ]
            else:
                logger.warning("No valid email data extracted for parallel processing.")
                return []

    async def _process_single_email_vector(self, email: Dict, embedding: List[float], similar_emails: List[Dict]) -> Dict:
        """Process individual email with vector operations"""
        try:
            import uuid
            from datetime import datetime
            
            # Categorize with vector context
            category = await self._categorize_email_with_vectors(
                email['content'], similar_emails, email['subject'], email['snippet']
            )
            
            # Prepare Qdrant point
            point_id = str(uuid.uuid4)
            point = {
               
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "email_id": email['message_id'],
                    "subject": email['subject'],
                    "sender": email['sender'],
                    "category": category,
                    "timestamp": datetime.utcnow().isoformat(),
                    "content_snippet": email['snippet'][:200]
                }
            }
            
            return {
                'success': True,
                'message_id': email['message_id'],
                'subject': email['subject'],
                'sender': email['sender'],
                'category': category,
                'vector_stored': True,
                'point': point,
                'point_id': point_id
            }
            
        except Exception as e:
            logger.error(f"Single email vector processing failed for {email.get('message_id', 'unknown')}: {e}")
            return {
                'success': False,
                'message_id': email.get('message_id', 'unknown'),
                'category': 'Uncategorized',
                'subject': email.get('subject', 'Unknown'),
                'vector_stored': False
            }

    async def _process_single_email_fallback(self, email: Dict) -> Dict:
        """Fallback processing for emails without embeddings"""
        try:
            # Simple categorization without vectors
            category = self._categorize_email_simple(email['subject'], email['snippet'])
            
            return {
                'success': True,
                'message_id': email['message_id'],
                'subject': email['subject'],
                'sender': email['sender'],
                'category': category,
                'vector_stored': False
            }
            
        except Exception as e:
            logger.error(f"Fallback processing failed for {email.get('message_id', 'unknown')}: {e}")
            return {
                'success': False,
                'message_id': email.get('message_id', 'unknown'),
                'category': 'Uncategorized',
                'subject': email.get('subject', 'Unknown'),
                'vector_stored': False
            }

    async def _get_or_create_gmail_label_cached(self, category: str) -> Optional[str]:
        """Get existing Gmail label or create new one with Redis-backed intelligent caching"""
        if self.gmail_organizer and self.gmail_organizer.service:
            try:
                # Initialize label cache if not exists
                if not hasattr(self, '_label_cache'):
                    await self._initialize_label_cache()
                
                # Return cached label if exists
                if category in self._label_cache:
                    return self._label_cache[category]
                
                # Create new label
                new_label = {
                    'name': category,
                    'messageListVisibility': 'show',
                    'labelListVisibility': 'labelShow',
                    'color': {
                        'backgroundColor': self._generate_label_color(category),
                        'textColor': '#ffffff'
                    }
                }
                
                created_label = self.gmail_organizer.service.users().labels().create(
                    userId='me',
                    body=new_label
                ).execute()
                
                # Cache the new label in memory
                self._label_cache[category] = created_label['id']
                
                # Cache in Redis if available
                if self._redis_enabled and self.cache_manager:
                    await self.cache_manager.add_label_to_cache(category, created_label['id'])
                
                logger.info(f"🏷️ Created and cached new Gmail label: {category}")
                
                return created_label['id']
                
            except Exception as e:
                logger.error(f"Failed to get/create label '{category}': {e}")
                raise

    async def _initialize_label_cache_from_gmail(self):
        """Initialize label cache with existing Gmail labels (called from Redis loader)"""
        if self.gmail_organizer and self.gmail_organizer.service:
            try:
                self._label_cache = {}
                self._our_custom_labels = set()
                
                # Get all existing labels
                labels_result = self.gmail_organizer.service.users().labels().list(userId='me').execute()
                labels = labels_result.get('labels', [])
                
                # Cache non-system labels
                for label in labels:
                    label_name = label.get('name', '')
                    label_id = label.get('id', '')
                    
                    # Skip system labels
                    if not label_name.startswith(('CATEGORY_', 'SYSTEM_')) and label_name not in [
                        'INBOX', 'SENT', 'DRAFT', 'SPAM', 'TRASH', 'IMPORTANT', 'STARRED', 'UNREAD'
                    ]:
                        self._label_cache[label_name] = label_id
                        # Track our custom labels for smart relabeling
                        if label_name in ['Work', 'Personal', 'Shopping', 'Finance', 'Social Media', 
                                        'News', 'Travel', 'Health', 'Uncategorized']:
                            self._our_custom_labels.add(label_id)
                
                logger.info(f"📋 Initialized label cache with {len(self._label_cache)} existing labels from Gmail")
                
            except Exception as e:
                logger.error(f"Failed to initialize label cache from Gmail: {e}")
                self._label_cache = {}
                self._our_custom_labels = set()

    async def _initialize_label_cache(self):
        """Initialize label cache with Redis-first approach"""
        try:
            # Try Redis first if enabled
            if self._redis_enabled and self.cache_manager:
                cached_labels = await self.cache_manager.get_label_cache()
                if cached_labels:
                    self._label_cache = cached_labels
                    self._our_custom_labels = set(cached_labels.values())
                    logger.info(f"📋 Loaded {len(cached_labels)} labels from Redis cache")
                    return
            
            # Fallback to Gmail API
            await self._initialize_label_cache_from_gmail()
            
            # Cache in Redis for next time
            if self._redis_enabled and self.cache_manager and self._label_cache:
                await self.cache_manager.update_label_cache(self._label_cache)
            
        except Exception as e:
            logger.error(f"Failed to initialize label cache from Gmail: {e}")
            self._label_cache = {}
            self._our_custom_labels = set()

    async def _cache_job_analytics(self, job_id: str, task_result: dict):
        """Cache job analytics in Redis for performance monitoring"""
        try:
            if self._redis_enabled and self.cache_manager:
                # Prepare analytics data
                analytics_data = {
                    "job_id": job_id,
                    "job_type": task_result.get("job_type", "unknown"),
                    "processed_count": task_result.get("processed_count", 0),
                    "categorized_count": task_result.get("categorized_count", 0),
                    "vectors_stored": task_result.get("vectors_stored", 0),
                    "labels_applied": task_result.get("labels_applied", 0),
                    "categories_created": task_result.get("categories_created", []),
                    "processing_time": task_result.get("processing_time", 0),
                    "success_rate": (task_result.get("categorized_count", 0) / max(task_result.get("processed_count", 1), 1)) * 100,
                    "api_calls_saved": task_result.get("processed_count", 0) * 0.95,  # Estimated savings
                    "completed_at": datetime.utcnow().isoformat()
                }
                
                # Cache analytics
                await self.cache_manager.cache_email_processing_stats(job_id, analytics_data)
                logger.info(f"📊 Cached analytics for job {job_id}")
                
        except Exception as e:
            logger.error(f"Failed to cache job analytics: {e}")

    async def _get_or_create_gmail_label(self, category: str) -> Optional[str]:
        """Legacy method - use _get_or_create_gmail_label_cached instead"""
        logger.warning("Using legacy label method - consider using cached version")
        return await self._get_or_create_gmail_label_cached(category)

    async def _get_messages_batch(self, message_ids: List[str]) -> List[dict]:
        """Get multiple messages using Gmail Batch API for optimal performance"""
        if self.gmail_organizer and self.gmail_organizer.service:
            try:
                from googleapiclient.http import BatchHttpRequest
                import asyncio
                from concurrent.futures import ThreadPoolExecutor
                
                if not message_ids:
                    return []
                
                # Gmail Batch API can handle up to 100 requests per batch
                batch_size = min(100, len(message_ids))
                batch_results = {}
                exceptions = {}
                
                def callback(request_id, response, exception):
                    if exception:
                        logger.warning(f"Batch request failed for message {request_id}: {exception}")
                        exceptions[request_id] = exception
                    else:
                        batch_results[request_id] = response
                
                # Create batch request
                batch_request = BatchHttpRequest(callback=callback)
                
                # Add requests to batch (up to 100)
                for i, msg_id in enumerate(message_ids[:batch_size]):
                    batch_request.add(
                        self.gmail_organizer.service.users().messages().get(
                            userId='me', 
                            id=msg_id,
                            format='full'  # Get full message data
                        ),
                        request_id=str(i)
                    )
                
                # Execute batch request in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    await loop.run_in_executor(executor, batch_request.execute)
                
                # Return results in original order
                results = []
                for i in range(len(message_ids[:batch_size])):
                    if str(i) in batch_results:
                        results.append(batch_results[str(i)])
                    else:
                        logger.warning(f"No result for message index {i}")
                        # Add empty result to maintain index alignment
                        results.append({
                            'id': message_ids[i],
                            'payload': {'headers': []},
                            'snippet': 'Error retrieving message'
                        })
                
                logger.info(f"📦 Batch API retrieved {len(results)} messages in single request")
                return results
                
            except Exception as e:
                logger.error(f"Batch message retrieval failed: {e}")
                # Fallback to individual requests
                return await self._get_messages_individual(message_ids)
        # If gmail_organizer or its service is not initialized, return empty list
        return []
    
    async def _get_messages_individual(self, message_ids: List[str]) -> List[dict]:
        results = []
        if self.gmail_organizer and self.gmail_organizer.service:
            """Fallback method for individual message retrieval"""
            
            for msg_id in message_ids:
                try:
                    msg = self.gmail_organizer.service.users().messages().get(
                        userId='me', 
                        id=msg_id
                    ).execute()
                    results.append(msg)
                except Exception as e:
                    logger.warning(f"Failed to get individual message {msg_id}: {e}")
                    results.append({
                        'id': msg_id,
                        'payload': {'headers': []},
                        'snippet': 'Error retrieving message'
                    })
        return results

    def _generate_label_color(self, category: str) -> str:
        """Generate consistent color for label based on category name"""
        import hashlib
        
        # Predefined colors for common categories
        color_map = {
            'Work': '#4285f4',
            'Personal': '#ea4335', 
            'Shopping': '#fbbc04',
            'Finance': '#34a853',
            'Social Media': '#ab47bc',
            'News': '#ff6d01',
            'Travel': '#00acc1',
            'Health': '#7cb342'
        }
        
        if category in color_map:
            return color_map[category]
        
        # Generate color from hash for other categories
        hash_val = int(hashlib.md5(category.encode()).hexdigest()[:6], 16)
        return f"#{hash_val:06x}"

    async def _store_email_vector(self, email_id: str, subject: str, sender: str, 
                                category: str, vector_id: str):
        db = self.SessionLocal()
        """Store email vector metadata in PostgreSQL"""
        try:
            # Check if email already exists
            existing = db.query(EmailVector).filter(EmailVector.email_id == email_id).first()
            if existing:
                # Update existing record using update() method
                db.query(EmailVector).filter(EmailVector.email_id == email_id).update({
                    "category": category,
                    "vector_id": vector_id
                })
                logger.info(f"Updated existing email vector for {email_id}")
            else:
                # Create new record
                email_vector = EmailVector(
                    email_id=email_id,
                    subject=subject,
                    sender=sender,
                    category=category,
                    vector_id=vector_id,
                    timestamp=datetime.utcnow()
                )
                db.add(email_vector)
                logger.info(f"Created new email vector record for {email_id}")
            
            db.commit()
            db.close()
            
        except Exception as e:
            logger.error(f"Failed to store email vector metadata: {e}")
            if 'db' in locals():
                db.close()

    async def process_cataloging_job(self, job_id: str, parameters: dict) -> dict:
        """Process email cataloging job"""
        logger.info(f"Processing cataloging job {job_id} with parameters: {parameters}")
        # Placeholder for cataloging implementation
        return {
            "processed_count": 0,
            "job_type": "cataloging",
            "status": "completed",
            "message": "Cataloging job completed (placeholder implementation)"
        }

    async def process_reclassification_job(self, job_id: str, parameters: dict) -> dict:
        """Process email reclassification job"""
        logger.info(f"Processing reclassification job {job_id} with parameters: {parameters}")
        # Placeholder for reclassification implementation
        return {
            "processed_count": 0,
            "job_type": "reclassification", 
            "status": "completed",
            "message": "Reclassification job completed (placeholder implementation)"
        }

    async def execute_agent_task_internal(self, agent_type: str, task_description: str, parameters: dict) -> dict:
        """Internal method to execute a CrewAI agent task and return the result"""
        try:
            agent_name = agent_type.replace("_agent", "")
            if agent_name not in self.agents:
                raise ValueError(f"Agent {agent_name} not found")
            agent = self.agents[agent_name]
            task = Task(
                description=task_description,
                agent=agent,
                expected_output="Detailed results of email processing task"
            )
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            # Execute the CrewAI task (synchronously, so wrap in thread executor if needed)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, crew.kickoff)
            return {"result": result}
        except Exception as e:
            logger.error(f"execute_agent_task_internal failed: {e}")
            return {"error": str(e)}
    
    async def execute_crew_task(self, execution_id: str, request: AgentTaskRequest):
        """Execute CrewAI task with full observability"""
        try:
            # Start LangFuse trace (if available)
            trace = None
            if self.langfuse is not None:
                trace = self.langfuse.trace(
                    name=f"crew_execution_{request.agent_type}",
                    metadata={"execution_id": execution_id, "task": request.task_description}
                )
            
            # Get agent
            agent_name = request.agent_type.replace("_agent", "")
            if agent_name not in self.agents:
                raise ValueError(f"Agent {agent_name} not found")
            
            agent = self.agents[agent_name]
            
            # Create task
            task = Task(
                description=request.task_description,
                agent=agent,
                expected_output="Detailed results of email processing task"
            )
            
            # Create crew and execute
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            
            # Execute with callback (if LangFuse is available)
            callbacks = []
            if LANGFUSE_AVAILABLE and LangfuseCallbackHandler is not None:
                langfuse_callback = LangfuseCallbackHandler(
                    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
                )
                callbacks.append(langfuse_callback)
            
            result = crew.kickoff()
            
            # Update execution record
            trace_id = trace.id if trace is not None else None
            await self.update_agent_execution(execution_id, "completed", result, trace_id)
            
        except Exception as e:
            logger.error(f"Crew execution {execution_id} failed: {e}")
            await self.update_agent_execution(execution_id, "failed", {"error": str(e)})
    
    async def update_job_status_stub(self, job_id: str, status: str, result: Any = None, error_message: Optional[str] = None):
        """Stub for update job status in database (legacy, not used)"""
        # Implementation would update PostgreSQL record
        pass
    
    async def update_agent_execution(self, execution_id: str, status: str, result: Any = None, trace_id: Optional[str] = None):
        """Update agent execution status"""
        # Implementation would update PostgreSQL record
        pass
    
    async def broadcast_job_update(self, job_id: str, status: str):
        """Broadcast job update to WebSocket clients"""
        message = {
            "type": "job_update",
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                self.active_connections.remove(connection)

    async def trigger_n8n_workflow_by_url(self, workflow_url: str, data: dict) -> dict:
        """Trigger an n8n workflow by its URL"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    workflow_url,
                    json=data,
                    headers={"X-N8N-API-KEY": self.n8n_api_key} if self.n8n_api_key else {}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to trigger n8n workflow by URL: {e}")
            raise

    async def handle_websocket_message(self, websocket: WebSocket, data: str):
        """Handle incoming WebSocket messages"""
        try:
            message = json.loads(data)
            # Handle different message types
            if message.get("type") == "subscribe_job":
                # Subscribe to job updates
                pass
        except Exception as e:
            logger.error(f"WebSocket message handling failed: {e}")

    async def update_job_status(self, job_id: str, status: str, result: Optional[dict] = None, error_message: Optional[str] = None):
        """Update job status in database"""
        try:
            db = self.SessionLocal()
            try:
                job = db.query(EmailProcessingJob).filter(EmailProcessingJob.id == job_id).first()
                if job:
                    # Use update() method for SQLAlchemy compatibility
                    update_data: Dict[Any, Any] = {EmailProcessingJob.status: status}
                    
                    if result:
                        update_data[EmailProcessingJob.result] = json.dumps(result)
                        if "processed_count" in result:
                            update_data[EmailProcessingJob.processed_count] = result["processed_count"]
                        if "total_count" in result:
                            update_data[EmailProcessingJob.total_count] = result["total_count"]
                    
                    if error_message:
                        update_data[EmailProcessingJob.error_message] = error_message
                        
                    if status == "completed":
                        update_data[EmailProcessingJob.completed_at] = datetime.now(timezone.utc)
                    db.query(EmailProcessingJob).filter(EmailProcessingJob.id == job_id).update(update_data)
                    db.commit()
                    logger.info(f"Updated job {job_id} status to {status}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")

    async def start_continuous_shelving(self, job_id: str):
        """Start continuous email shelving process"""
        logger.info(f"🚀 Starting continuous shelving process for job {job_id}")
        self.shelving_active = True
        
        try:
            # Check Gmail API authentication first
            if not hasattr(self, 'gmail_organizer') or not self.gmail_organizer:
                logger.error("❌ Gmail organizer not initialized - cannot start shelving")
                return
                
            logger.info(f"✅ Gmail organizer available: {type(self.gmail_organizer)}")
            
            # Test Gmail API connection
            try:
                if hasattr(self.gmail_organizer, 'service') and self.gmail_organizer.service:
                    profile = self.gmail_organizer.service.users().getProfile(userId='me').execute()
                    logger.info(f"✅ Gmail API connected for user: {profile.get('emailAddress', 'unknown')}")
                else:
                    logger.error("❌ Gmail service not available")
                    return
            except Exception as e:
                logger.error(f"❌ Gmail API connection failed: {e}")
                return
            
            cycle_count = 0
            while self.shelving_active:
                cycle_count += 1
                logger.info(f"🔄 Shelving cycle #{cycle_count} - checking for new emails...")
                
                # Check for new emails every 30 seconds
                await asyncio.sleep(30)
                
                if not self.shelving_active:
                    logger.info("🛑 Shelving stopped by user")
                    break
                    
                try:
                    # Get unread emails from inbox
                    logger.info("📧 Fetching unread emails from inbox...")
                    
                    query = "in:inbox is:unread"
                    logger.info(f"🔍 Gmail query: {query}")
                    
                    # Use Gmail API to search for emails
                    search_result = self.gmail_organizer.service.users().messages().list(
                        userId='me',
                        q=query,
                        maxResults=10
                    ).execute()
                    
                    messages = search_result.get('messages', [])
                    logger.info(f"📬 Found {len(messages)} unread emails")
                    
                    if len(messages) == 0:
                        logger.info("✅ No new emails to process")
                        continue
                    
                    # Process each message
                    for i, msg in enumerate(messages):
                        logger.info(f"📄 Processing email {i+1}/{len(messages)}: {msg['id']}")
                        
                        try:
                            # Get full message details
                            full_message = self.gmail_organizer.service.users().messages().get(
                                userId='me',
                                id=msg['id'],
                                format='full'
                            ).execute()
                            
                            # Extract subject and sender
                            headers = full_message['payload'].get('headers', [])
                            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                            
                            logger.info(f"📧 Email details - Subject: '{subject}', From: '{sender}'")
                            
                            # Create a mini shelving job for this email
                            mini_job_config = JobConfig(
                                job_type="shelving",
                                parameters={
                                    "max_emails": 1,
                                    "batch_size": 1,
                                    "message_ids": [msg['id']],
                                    "enable_logging": True
                                }
                            )
                            
                            # Process the email
                            logger.info(f"🤖 Starting AI processing for email {msg['id']}")
                            batch_job_id = f"{job_id}_email_{msg['id']}"
                            await self.process_job(batch_job_id, mini_job_config)
                            logger.info(f"✅ Completed processing email {msg['id']}")
                            
                        except Exception as e:
                            logger.error(f"❌ Failed to process email {msg['id']}: {e}")
                            continue
                    
                    logger.info(f"🎯 Completed shelving cycle #{cycle_count} - processed {len(messages)} emails")
                    
                except Exception as e:
                    logger.error(f"❌ Error in shelving cycle #{cycle_count}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Critical error in continuous shelving: {e}")
        finally:
            self.shelving_active = False
            await self.update_job_status(job_id, "completed")
            logger.info(f"🏁 Continuous shelving stopped for job {job_id}")

    def format_activity_message(self, job_data: Dict) -> str:
        """Format job data into user-friendly activity message"""
        try:
            job_type = job_data.get("type", "unknown")
            processed_count = job_data.get("processed_count", 0)
            categories = job_data.get("categories", [])
            
            if job_type == "shelving":
                if categories:
                    cat_list = ", ".join(categories[:3])  # Show first 3 categories
                    return f"Processed {processed_count} emails into [{cat_list}] categories"
                else:
                    return f"Processed {processed_count} new emails"
            elif job_type == "archiving":
                folder = job_data.get("folder", "Archive")
                return f"Archived {processed_count} emails to {folder} folder"
            elif job_type == "inbox_clear":
                return f"Inbox is clear - all {processed_count} emails organized"
            else:
                return f"Processed {processed_count} emails"
                
        except Exception as e:
            logger.warning(f"Error formatting activity message: {e}")
            return "Email processing completed"

def main():
    """Main entry point"""
    server = EnhancedEmailLibrarianServer()
    
    # Run with uvicorn
    uvicorn.run(
        server.app,
        host="0.0.0.0",  
        port=8000,
        log_level="info",
        reload=False  # Set to True for development
    )

if __name__ == "__main__":
    main()
