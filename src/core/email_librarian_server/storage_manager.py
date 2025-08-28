"""
Storage manager for the Enhanced Email Librarian system.
"""
import os
import logging
import json
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import asyncpg
import asyncio
import uuid
from databases import Database as StorageDatabase
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Range

logger = logging.getLogger(__name__)

class StorageManager:
    """Manages database and vector storage operations."""

    def __init__(self, database_url: Optional[str] = None, qdrant_url: Optional[str] = None, collection_name: str = "emails"):
        """Initialize the storage manager."""
        self.database_url = database_url or os.environ.get(
            "DATABASE_URL", 
            "postgresql+asyncpg://postgres:postgres@localhost:5432/email_librarian"
        )
        self.qdrant_url = qdrant_url or os.environ.get(
            "QDRANT_URL", 
            "http://qdrant:6333"
        )
        self.collection_name = collection_name
        self.database: StorageDatabase | None = None
        self.qdrant_client: AsyncQdrantClient | None = None
        self.pool: asyncpg.Pool | None = None

        # Retry configuration
        self.max_retries = int(os.environ.get("STORAGE_MAX_RETRIES", "3"))
        self.retry_delay = float(os.environ.get("STORAGE_RETRY_DELAY", "2.0"))
        
    async def _retry_with_backoff(self, operation_name: str, operation_func, *args, **kwargs):
        """
        Execute an operation with exponential backoff retry logic.
        
        Args:
            operation_name: Name of the operation for logging
            operation_func: Async function to execute
            *args, **kwargs: Arguments to pass to the operation function
            
        Returns:
            Result of the operation or raises the last exception
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await operation_func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"⚠️ {operation_name} failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ {operation_name} failed after {self.max_retries + 1} attempts: {e}")
                    
        if last_exception is not None:
            raise last_exception
        else:
            raise Exception(f"{operation_name} failed but no exception was captured.")
        
    async def initialize(self):
        """Initialize database and vector DB connections with retry logic."""
        async def _initialize_connections():
            # Initialize PostgreSQL connection
            self.database = StorageDatabase(self.database_url)
            await self.database.connect()
            
            # Initialize connection pool for direct queries
            # asyncpg expects a postgresql:// URL (without '+asyncpg').
            # Accept both 'postgresql+asyncpg://' (used by 'databases') and 'postgresql://'.
            pool_url = self.database_url
            if isinstance(pool_url, str) and pool_url.startswith("postgresql+asyncpg://"):
                pool_url = pool_url.replace("postgresql+asyncpg://", "postgresql://", 1)

            self.pool = await asyncpg.create_pool(
                pool_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
                server_settings={
                    'application_name': 'email_librarian_server',
                }
            )
            
            # Initialize Qdrant client
            self.qdrant_client = AsyncQdrantClient(url=self.qdrant_url)
            
            # Test Qdrant connection
            await self.qdrant_client.get_collections()
            
            return True
            
        try:
            # Initialize connections with retry
            await self._retry_with_backoff(
                "Database and Vector DB initialization",
                _initialize_connections
            )
            
            # Initialize database schema with retry
            schema_success = await self._retry_with_backoff(
                "Database schema initialization",
                self.initialize_database_schema
            )
            
            if not schema_success:
                logger.warning("⚠️ Database schema initialization failed")
            
            # Ensure vector collection exists with retry
            await self._retry_with_backoff(
                "Vector collection setup",
                self.ensure_vector_collection
            )
            
            logger.info("✅ Storage manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing storage after retries: {e}")
            # Clean up partial connections
            await self._cleanup_partial_connections()
            return False
    
    
    async def _cleanup_partial_connections(self):
        """Clean up partially initialized connections."""
        try:
            if self.database and isinstance(self.database, StorageDatabase):
                await self.database.disconnect()
                self.database = None
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")
            
        try:
            if self.pool and isinstance(self.pool, asyncpg.Pool):
                await self.pool.close()
                self.pool = None
        except Exception as e:
            logger.warning(f"Error closing connection pool: {e}")
            
        # Qdrant client doesn't need explicit cleanup
        self.qdrant_client = None
        
    async def ensure_vector_collection(self, vector_size: int = 1536):
        """
        Ensure the vector collection exists in Qdrant.
        
        Args:
            vector_size: Dimension of the embedding vectors
        """
        try:
            if self.qdrant_client is None:
                logger.error("Qdrant client is not initialized.")
                return
            collections = await self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                await self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error ensuring vector collection: {e}")
            
    async def store_email_vector(self, email_id: str, vector: List[float], metadata: Dict[str, Any]) -> bool:
        """
        Store an email embedding vector in Qdrant with retry logic.
        """
        async def _store_vector():
            point_id = int(hash(email_id) % (2**63 - 1))

            if self.qdrant_client is None:
                self.qdrant_client = AsyncQdrantClient(url=self.qdrant_url)

            await self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=metadata
                    )
                ]
            )
            return True
            
        try:
            return await self._retry_with_backoff(
                f"Store email vector for {email_id}",
                _store_vector
            )
        except Exception as e:
            logger.error(f"Failed to store email vector for {email_id} after retries: {e}")
            return False
            
    async def search_similar_emails(self, query_vector: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for similar emails using vector similarity with retry logic.
        """
        async def _search_vectors():
            if self.qdrant_client is None:
                self.qdrant_client = AsyncQdrantClient(url=self.qdrant_url)
                
            search_result = await self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit
            )
            
            return [point.payload for point in search_result if point.payload is not None and isinstance(point.payload, dict)]
            
        try:
            return await self._retry_with_backoff(
                "Vector similarity search",
                _search_vectors
            )
        except Exception as e:
            logger.error(f"Failed to search similar emails after retries: {e}")
            return []
        
    async def close(self):
        """Close all database connections."""
        if self.database:
            await self.database.disconnect()
        if self.pool:
            await self.pool.close()
        # Qdrant client doesn't need explicit closing

    async def initialize_database_schema(self):
        """Create required database tables if they don't exist."""
        if not self.pool:
            logger.error("Database pool not initialized")
            return False
            
        try:
            async with self.pool.acquire() as connection:
                # Create jobs table
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS email_processing_jobs (
                        id UUID PRIMARY KEY,
                        job_type VARCHAR(50) NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        parameters JSONB,
                        results JSONB,
                        processed_count INTEGER DEFAULT 0,
                        total_count INTEGER DEFAULT 0,
                        progress DECIMAL(5,4) DEFAULT 0.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        error_message TEXT
                    );
                """)
                
                # Create emails table
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS emails (
                        id VARCHAR(255) PRIMARY KEY,
                        subject TEXT,
                        sender VARCHAR(255),
                        recipient VARCHAR(255),
                        content TEXT,
                        category VARCHAR(100),
                        labels TEXT[],
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Create indexes for performance
                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_jobs_status 
                    ON email_processing_jobs(status);
                """)
                
                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_jobs_type 
                    ON email_processing_jobs(job_type);
                """)
                
                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_emails_category 
                    ON emails(category);
                """)

                # Ensure legacy databases get any missing columns added to email_processing_jobs
                # This is important for deployments that have an older schema without 'parameters' etc.
                try:
                    await connection.execute("""
                        ALTER TABLE email_processing_jobs
                        ADD COLUMN IF NOT EXISTS parameters JSONB,
                        ADD COLUMN IF NOT EXISTS results JSONB,
                        ADD COLUMN IF NOT EXISTS processed_count INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS total_count INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS progress DECIMAL(5,4) DEFAULT 0.0,
                        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ADD COLUMN IF NOT EXISTS error_message TEXT
                    ;
                    """)
                except Exception:
                    # Some Postgres versions or SQL drivers may not support multi-add in one ALTER; try individually
                    try:
                        await connection.execute("""ALTER TABLE email_processing_jobs ADD COLUMN IF NOT EXISTS parameters JSONB;""")
                        await connection.execute("""ALTER TABLE email_processing_jobs ADD COLUMN IF NOT EXISTS results JSONB;""")
                        await connection.execute("""ALTER TABLE email_processing_jobs ADD COLUMN IF NOT EXISTS processed_count INTEGER DEFAULT 0;""")
                        await connection.execute("""ALTER TABLE email_processing_jobs ADD COLUMN IF NOT EXISTS total_count INTEGER DEFAULT 0;""")
                        await connection.execute("""ALTER TABLE email_processing_jobs ADD COLUMN IF NOT EXISTS progress DECIMAL(5,4) DEFAULT 0.0;""")
                        await connection.execute("""ALTER TABLE email_processing_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")
                        await connection.execute("""ALTER TABLE email_processing_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;""")
                        await connection.execute("""ALTER TABLE email_processing_jobs ADD COLUMN IF NOT EXISTS error_message TEXT;""")
                    except Exception as e:
                        logger.warning(f"Could not ensure legacy columns on email_processing_jobs: {e}")

                # activity_log table intentionally removed per configuration

                # Function state table to persist on/off toggles for features
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS function_state (
                        name TEXT PRIMARY KEY,
                        enabled BOOLEAN NOT NULL DEFAULT FALSE,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                logger.info("✅ Database schema initialized successfully")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error initializing database schema: {e}")
            return False
        
    async def store_email_metadata(self, email_data: Dict[str, Any]) -> bool:
        """Store email metadata in PostgreSQL with retry logic."""
        async def _store_metadata():
            if not self.database:
                raise ConnectionError("Database connection not available")
                
            await self.database.execute("""
                INSERT INTO emails (id, subject, sender, recipient, content, category, labels, metadata)
                VALUES (:id, :subject, :sender, :recipient, :content, :category, :labels, :metadata)
                ON CONFLICT (id) DO UPDATE SET
                    subject = EXCLUDED.subject,
                    content = EXCLUDED.content,
                    category = EXCLUDED.category,
                    labels = EXCLUDED.labels,
                    metadata = EXCLUDED.metadata,
                    processed_at = CURRENT_TIMESTAMP
            """, {
                "id": email_data.get("id"),
                "subject": email_data.get("subject"),
                "sender": email_data.get("sender"),
                "recipient": email_data.get("recipient"),
                "content": email_data.get("content", ""),
                "category": email_data.get("category"),
                "labels": email_data.get("labels", []),
                "metadata": json.dumps(email_data.get("metadata", {}))
            })
            return True
            
        try:
            return await self._retry_with_backoff(
                f"Store email metadata for {email_data.get('id', 'unknown')}",
                _store_metadata
            )
        except Exception as e:
            logger.error(f"Failed to store email metadata after retries: {e}")
            return False
        
    async def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job information by ID."""
        try:
            if not self.database:
                return None
                
            result = await self.database.fetch_one("""
                SELECT * FROM email_processing_jobs WHERE id = :job_id
            """, {"job_id": job_id})
            
            if result:
                return dict(result)
            return None
        except Exception as e:
            logger.error(f"Error retrieving job {job_id}: {e}")
            return None

    async def get_function_state(self, name: str) -> Optional[bool]:
        """Retrieve persisted function enabled state from the database."""
        try:
            if not self.database:
                logger.debug("Database not available for get_function_state")
                return None

            row = await self.database.fetch_one("""
                SELECT enabled FROM function_state WHERE name = :name
            """, {"name": name})

            if row is None:
                return None
            return bool(row["enabled"])
        except Exception as e:
            logger.error(f"Error getting function state for {name}: {e}")
            return None

    async def set_function_state(self, name: str, enabled: bool) -> bool:
        """Persist function enabled state into the database."""
        try:
            if not self.database:
                logger.debug("Database not available for set_function_state")
                return False

            await self.database.execute("""
                INSERT INTO function_state (name, enabled, updated_at)
                VALUES (:name, :enabled, CURRENT_TIMESTAMP)
                ON CONFLICT (name) DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = CURRENT_TIMESTAMP
            """, {"name": name, "enabled": enabled})
            return True
        except Exception as e:
            logger.error(f"Error setting function state for {name}: {e}")
            return False
        
    async def health_check(self) -> Dict[str, bool]:
        """
        Check the health of all storage connections.
        
        Returns:
            Dictionary with health status of each component
        """
        health = {
            "database": False,
            "qdrant": False,
            "overall": False
        }
        
        # Check PostgreSQL
        try:
            if self.database:
                await self.database.fetch_one("SELECT 1")
                health["database"] = True
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            
        # Check Qdrant
        try:
            if self.qdrant_client:
                await self.qdrant_client.get_collections()
                health["qdrant"] = True
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            
        health["overall"] = health["database"] and health["qdrant"]
        return health

    async def reconnect_if_needed(self) -> bool:
        """
        Reconnect to services if connections are lost.
        
        Returns:
            True if all connections are healthy
        """
        health = await self.health_check()
        
        if not health["overall"]:
            logger.info("🔄 Attempting to reconnect to storage services...")
            return await self.initialize()
            
        return True    
        
        