"""
Storage manager for the Enhanced Email Librarian system.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import asyncpg
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Range

logger = logging.getLogger(__name__)

class StorageManager:
    """Manages database and vector storage operations."""
    
    def __init__(self, database_url: Optional[str] = None, qdrant_url: Optional[str] = None, collection_name: str = "emails"):
        """
        Initialize the storage manager.
        
        Args:
            database_url: PostgreSQL database URL
            qdrant_url: Qdrant vector DB URL
            collection_name: Qdrant collection name for email vectors
        """
        self.database_url = database_url or "postgresql://postgres:postgres@localhost:5432/email_librarian"
        self.qdrant_url = qdrant_url or "http://localhost:6333"
        self.collection_name = collection_name
        self.database = None
        self.qdrant_client = None
        self.pool = None
        
    async def initialize(self):
        """Initialize database and vector DB connections."""
        try:
            # Initialize PostgreSQL connection
            import databases
            self.database = databases.Database(self.database_url)
            await self.database.connect()
            
            # Initialize connection pool for direct queries
            self.pool = await asyncpg.create_pool(self.database_url)
            
            # Initialize Qdrant client
            self.qdrant_client = AsyncQdrantClient(url=self.qdrant_url)
            
            # Ensure collection exists
            await self.ensure_vector_collection()
            
            logger.info("✅ Storage manager initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Error initializing storage: {e}")
            return False
            
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
        Store an email embedding vector in Qdrant.
        
        Args:
            email_id: Unique email identifier
            vector: Embedding vector
            metadata: Email metadata to store with the vector
            
        Returns:
            Success status
        """
        try:
            point_id = int(hash(email_id) % (2**63 - 1))  # Convert string ID to integer

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
        except Exception as e:
            logger.error(f"Error storing email vector: {e}")
            return False
            
    async def search_similar_emails(self, query_vector: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for similar emails using vector similarity.
        
        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            
        Returns:
            List of similar email metadata
        """
        try:
            if self.qdrant_client is None:
                self.qdrant_client = AsyncQdrantClient(url=self.qdrant_url)
            search_result = await self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit
            )
            
            return [point.payload for point in search_result if point.payload is not None and isinstance(point.payload, dict)]
        except Exception as e:
            logger.error(f"Error searching similar emails: {e}")
            return []
            
    async def close(self):
        """Close all database connections."""
        if self.database:
            await self.database.disconnect()
        if self.pool:
            await self.pool.close()
        # Qdrant client doesn't need explicit closing
