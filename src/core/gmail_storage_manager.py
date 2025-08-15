"""
Gmail Storage Manager - Comprehensive storage for Gmail API calls
Integrates PostgreSQL, Qdrant, and Redis for optimal data management
"""

import os
import json
import hashlib
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import asyncpg
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import redis.asyncio as redis

# Optional: Import sentence transformers if available
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("⚠️ sentence-transformers not available. Semantic search disabled.")

@dataclass
class EmailData:
    """Structured email data for storage"""
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    snippet: str
    labels: List[str]
    api_call_timestamp: datetime
    source_query: str

class GmailStorageManager:
    """Comprehensive storage manager for Gmail API data"""
    
    def __init__(self, postgres_url: Optional[str] = None, qdrant_host: Optional[str] = None, redis_url: Optional[str] = None):
        # Use environment variables as defaults
        self.postgres_url = postgres_url or os.getenv("DATABASE_URL")
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "qdrant")
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        
        # Initialize clients
        self.postgres_pool = None
        self.qdrant_client = None
        self.redis_client = None
        
        # Collection names
        self.qdrant_collection = "gmail_emails"
        
        # Embedding model for vector storage
        self.embedding_model = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize all storage systems"""
        if self._initialized:
            return True
            
        print("🚀 Initializing Gmail Storage Manager...")
        
        success = True
        
        # Initialize PostgreSQL
        if self.postgres_url:
            success &= await self._init_postgres()
        else:
            print("⚠️ No PostgreSQL URL provided")
            
        # Initialize Qdrant
        if self.qdrant_host:
            success &= await self._init_qdrant()
        else:
            print("⚠️ No Qdrant host provided")
            
        # Initialize Redis
        if self.redis_url:
            success &= await self._init_redis()
        else:
            print("⚠️ No Redis URL provided")
            
        # Initialize embedding model
        if EMBEDDINGS_AVAILABLE:
            await self._init_embedding_model()
            
        self._initialized = success
        print(f"✅ Gmail Storage Manager initialized: {success}")
        return success
        
    async def _init_postgres(self) -> bool:
        """Initialize PostgreSQL schema"""
        try:
            self.postgres_pool = await asyncpg.create_pool(
                self.postgres_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            
            async with self.postgres_pool.acquire() as conn:
                # API calls tracking table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS gmail_api_calls (
                        id SERIAL PRIMARY KEY,
                        call_type VARCHAR(50) NOT NULL,
                        query_used TEXT,
                        timestamp TIMESTAMP DEFAULT NOW(),
                        response_count INTEGER,
                        api_quota_used INTEGER DEFAULT 1,
                        success BOOLEAN DEFAULT TRUE,
                        error_message TEXT,
                        metadata JSONB,
                        execution_time_ms INTEGER
                    )
                """)
                
                # Emails metadata table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS gmail_emails (
                        gmail_id VARCHAR(255) PRIMARY KEY,
                        thread_id VARCHAR(255),
                        subject TEXT,
                        sender TEXT,
                        recipient TEXT,
                        date_sent TIMESTAMP,
                        snippet TEXT,
                        labels TEXT[], 
                        raw_headers JSONB,
                        api_call_id INTEGER REFERENCES gmail_api_calls(id),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        embedding_stored BOOLEAN DEFAULT FALSE,
                        cached_until TIMESTAMP,
                        storage_hash VARCHAR(64)
                    )
                """)
                
                # Labels/categories tracking
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS gmail_labels (
                        label_id VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        type VARCHAR(50), -- 'system' or 'user'
                        messages_total INTEGER DEFAULT 0,
                        messages_unread INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT NOW(),
                        api_call_id INTEGER REFERENCES gmail_api_calls(id)
                    )
                """)
                
                # Batch operations tracking
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS gmail_batch_operations (
                        id SERIAL PRIMARY KEY,
                        operation_type VARCHAR(50),
                        batch_size INTEGER,
                        emails_processed INTEGER,
                        started_at TIMESTAMP DEFAULT NOW(),
                        completed_at TIMESTAMP,
                        status VARCHAR(20) DEFAULT 'running',
                        api_calls_used INTEGER,
                        query_used TEXT,
                        metadata JSONB
                    )
                """)
                
                # Create indexes for better performance
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_gmail_emails_date_sent ON gmail_emails(date_sent DESC);
                    CREATE INDEX IF NOT EXISTS idx_gmail_emails_sender ON gmail_emails(sender);
                    CREATE INDEX IF NOT EXISTS idx_gmail_emails_labels ON gmail_emails USING GIN(labels);
                    CREATE INDEX IF NOT EXISTS idx_gmail_api_calls_timestamp ON gmail_api_calls(timestamp DESC);
                """)
                
            print("✅ PostgreSQL schema initialized")
            return True
            
        except Exception as e:
            print(f"❌ PostgreSQL initialization error: {e}")
            return False
        
    async def _init_qdrant(self) -> bool:
        """Initialize Qdrant collection for email embeddings"""
        try:
            self.qdrant_client = AsyncQdrantClient(
                host=self.qdrant_host, 
                port=6333,
                prefer_grpc=False,
                timeout=10,
                verify=False
            )
            
            # Check if collection exists
            collections = await self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.qdrant_collection not in collection_names:
                # Create collection for email embeddings
                await self.qdrant_client.create_collection(
                    collection_name=self.qdrant_collection,
                    vectors_config=VectorParams(
                        size=384,  # sentence-transformers all-MiniLM-L6-v2 default
                        distance=Distance.COSINE
                    )
                )
                print(f"✅ Created Qdrant collection: {self.qdrant_collection}")
            else:
                print(f"✅ Qdrant collection exists: {self.qdrant_collection}")
                
            return True
                
        except Exception as e:
            print(f"❌ Qdrant initialization error: {e}")
            return False
            
    async def _init_redis(self) -> bool:
        """Initialize Redis for caching"""
        try:
            # Create connection pool for better performance
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=10
            )
            
            await self.redis_client.ping()
            print("✅ Redis connection established")
            return True
            
        except Exception as e:
            print(f"❌ Redis initialization error: {e}")
            return False
            
    async def _init_embedding_model(self):
        """Initialize embedding model for vector storage"""
        try:
            if EMBEDDINGS_AVAILABLE:
                # Import SentenceTransformer here to ensure it's available
                from sentence_transformers import SentenceTransformer
                # Use lightweight model for fast embeddings
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("✅ Embedding model loaded (all-MiniLM-L6-v2)")
            else:
                print("⚠️ Embeddings not available - install sentence-transformers")
        except Exception as e:
            print(f"❌ Embedding model error: {e}")
    
    async def store_api_call_result(self, call_type: str, query: str, emails: List[Dict], 
                                  api_calls_used: int = 1, metadata: Optional[Dict] = None, 
                                  execution_time_ms: Optional[int] = None) -> Optional[int]:
        """Store the result of a Gmail API call in all three storage systems"""
        
        if not self._initialized:
            print("⚠️ Storage manager not initialized")
            return None
            
        start_time = datetime.now()
        
        # 1. Store API call record in PostgreSQL
        api_call_id = await self._store_api_call_record(
            call_type, query, len(emails), api_calls_used, metadata, execution_time_ms
        )
        
        if api_call_id is None:
            print("⚠️ Could not store API call record")
            return None
        
        # 2. Store each email in PostgreSQL and Qdrant
        stored_emails = []
        for email_data in emails:
            email_stored = await self._store_single_email(email_data, api_call_id)
            if email_stored:
                stored_emails.append(email_data)
        
        # 3. Cache results in Redis for fast retrieval
        await self._cache_api_results(call_type, query, stored_emails)
        
        # 4. Update batch operation if applicable
        if len(emails) > 1:
            await self._store_batch_operation(call_type, len(emails), api_calls_used, query)
        
        storage_time = (datetime.now() - start_time).total_seconds() * 1000
        print(f"📊 Stored API call: {call_type} -> {len(stored_emails)} emails -> API call ID: {api_call_id} ({storage_time:.0f}ms)")
        
        return api_call_id
        
    async def _store_api_call_record(self, call_type: str, query: str, response_count: int, 
                                   api_calls_used: int, metadata: Optional[Dict], execution_time_ms: Optional[int]) -> Optional[int]:
        """Store API call metadata in PostgreSQL"""
        if not self.postgres_pool:
            return None
            
        try:
            async with self.postgres_pool.acquire() as conn:
                api_call_id = await conn.fetchval("""
                    INSERT INTO gmail_api_calls 
                    (call_type, query_used, response_count, api_quota_used, metadata, execution_time_ms)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """, call_type, query, response_count, api_calls_used, 
                json.dumps(metadata or {}), execution_time_ms)
                
            return api_call_id
        except Exception as e:
            print(f"❌ Error storing API call record: {e}")
            return None
        
    async def _store_single_email(self, email_data: Dict, api_call_id: int) -> bool:
        """Store single email in PostgreSQL and Qdrant"""
        try:
            gmail_id = email_data.get('id')
            if not gmail_id:
                return False
                
            # Create storage hash to detect changes
            email_hash = hashlib.md5(json.dumps(email_data, sort_keys=True).encode()).hexdigest()
                
            # Check if email already exists with same content
            if self.postgres_pool:
                async with self.postgres_pool.acquire() as conn:
                    existing_hash = await conn.fetchval("""
                        SELECT storage_hash FROM gmail_emails WHERE gmail_id = $1
                    """, gmail_id)
                    
                    if existing_hash == email_hash:
                        print(f"📧 Email {gmail_id} unchanged, skipping storage")
                        return True
                        
                    # Store/Update in PostgreSQL
                    await conn.execute("""
                        INSERT INTO gmail_emails 
                        (gmail_id, thread_id, subject, sender, date_sent, snippet, labels, 
                         api_call_id, cached_until, storage_hash, raw_headers)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (gmail_id) DO UPDATE SET
                            updated_at = NOW(),
                            cached_until = $9,
                            api_call_id = $8,
                            storage_hash = $10,
                            subject = $3,
                            snippet = $6,
                            labels = $7
                    """, 
                    gmail_id,
                    email_data.get('threadId'),
                    email_data.get('subject', ''),
                    email_data.get('from', ''),
                    self._parse_email_date(email_data.get('date')),
                    email_data.get('snippet', ''),
                    email_data.get('labelIds', []),
                    api_call_id,
                    datetime.now() + timedelta(hours=24),  # Cache for 24 hours
                    email_hash,
                    json.dumps(email_data.get('headers', {}))
                    )
            
            # Store embedding in Qdrant
            await self._store_email_embedding(gmail_id, email_data)
            
            # Cache in Redis for immediate access
            await self._cache_single_email(gmail_id, email_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Error storing email {email_data.get('id', 'unknown')}: {e}")
            return False
            
    async def _store_email_embedding(self, gmail_id: str, email_data: Dict):
        """Store email embedding in Qdrant for semantic search"""
        try:
            if not self.embedding_model or not self.qdrant_client:
                return
                
            # Create text for embedding (subject + snippet + sender)
            embedding_text = f"{email_data.get('subject', '')} {email_data.get('snippet', '')} {email_data.get('from', '')}"
            
            # Generate embedding
            embedding = self.embedding_model.encode(embedding_text).tolist()
            
            # Create unique point ID for Qdrant
            point_id = hashlib.md5(gmail_id.encode()).hexdigest()
            
            # Store in Qdrant
            await self.qdrant_client.upsert(
                collection_name=self.qdrant_collection,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "gmail_id": gmail_id,
                            "subject": email_data.get('subject', ''),
                            "sender": email_data.get('from', ''),
                            "labels": email_data.get('labelIds', []),
                            "date": email_data.get('date', ''),
                            "snippet": email_data.get('snippet', '')[:200],  # Truncate snippet
                            "thread_id": email_data.get('threadId', ''),
                            "stored_at": datetime.now().isoformat()
                        }
                    )
                ]
            )
            
            # Mark as embedded in PostgreSQL
            if self.postgres_pool:
                async with self.postgres_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE gmail_emails SET embedding_stored = TRUE WHERE gmail_id = $1
                    """, gmail_id)
                    
            print(f"🔢 Stored embedding for email {gmail_id}")
            
        except Exception as e:
            print(f"❌ Error storing embedding for {gmail_id}: {e}")
    
    async def _cache_api_results(self, call_type: str, query: str, emails: List[Dict]):
        """Cache API results in Redis"""
        try:
            if not self.redis_client:
                return
                
            # Create cache key
            query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
            cache_key = f"gmail_api:{call_type}:{query_hash}"
            
            # Cache for 1 hour
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "call_type": call_type,
                "query": query,
                "count": len(emails),
                "emails": emails[:10]  # Cache first 10 for quick preview
            }
            
            await self.redis_client.setex(
                cache_key, 
                3600,  # 1 hour
                json.dumps(cache_data)
            )
            
            # Also cache the email IDs list for fast lookups
            email_ids = [email.get('id') for email in emails if email.get('id')]
            await self.redis_client.setex(
                f"{cache_key}:ids",
                3600,
                json.dumps(email_ids)
            )
            
            print(f"💾 Cached API results: {cache_key} ({len(emails)} emails)")
            
        except Exception as e:
            print(f"❌ Redis caching error: {e}")
    
    async def _cache_single_email(self, gmail_id: str, email_data: Dict):
        """Cache individual email in Redis"""
        try:
            if not self.redis_client:
                return
                
            cache_key = f"gmail_email:{gmail_id}"
            await self.redis_client.setex(
                cache_key,
                86400,  # 24 hours
                json.dumps(email_data)
            )
        except Exception as e:
            print(f"❌ Redis email caching error: {e}")
    
    async def get_cached_email(self, gmail_id: str) -> Optional[Dict]:
        """Get cached email from Redis"""
        try:
            if not self.redis_client:
                return None
                
            cache_key = f"gmail_email:{gmail_id}"
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            print(f"❌ Redis retrieval error: {e}")
        return None
    
    async def get_cached_api_result(self, call_type: str, query: str) -> Optional[Dict]:
        """Get cached API result from Redis"""
        try:
            if not self.redis_client:
                return None
                
            query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
            cache_key = f"gmail_api:{call_type}:{query_hash}"
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                cached_result = json.loads(cached_data)
                # Check if cache is still fresh (within 30 minutes for API calls)
                cache_time = datetime.fromisoformat(cached_result['timestamp'])
                if datetime.now() - cache_time < timedelta(minutes=30):
                    print(f"🚀 Using cached result for {call_type}: {query}")
                    return cached_result
                    
        except Exception as e:
            print(f"❌ Redis cache retrieval error: {e}")
        return None
    
    async def _store_batch_operation(self, operation_type: str, batch_size: int, 
                                   api_calls_used: int, query: str):
        """Store batch operation metadata"""
        if not self.postgres_pool:
            return
            
        try:
            async with self.postgres_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO gmail_batch_operations 
                    (operation_type, batch_size, emails_processed, api_calls_used, query_used, status, completed_at)
                    VALUES ($1, $2, $3, $4, $5, 'completed', NOW())
                """, operation_type, batch_size, batch_size, api_calls_used, query)
        except Exception as e:
            print(f"❌ Error storing batch operation: {e}")
    
    async def get_api_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive API usage statistics"""
        if not self.postgres_pool:
            return {"error": "PostgreSQL not available"}
            
        try:
            async with self.postgres_pool.acquire() as conn:
                # Total API calls today
                today_calls = await conn.fetchval("""
                    SELECT COALESCE(SUM(api_quota_used), 0) 
                    FROM gmail_api_calls 
                    WHERE DATE(timestamp) = CURRENT_DATE
                """)
                
                # Emails stored today
                today_emails = await conn.fetchval("""
                    SELECT COUNT(*) 
                    FROM gmail_emails 
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                
                # Recent batch operations
                recent_batches = await conn.fetch("""
                    SELECT * FROM gmail_batch_operations 
                    ORDER BY started_at DESC LIMIT 5
                """)
                
                # API call efficiency
                avg_emails_per_call = await conn.fetchval("""
                    SELECT COALESCE(AVG(response_count::float / NULLIF(api_quota_used, 0)), 0)
                    FROM gmail_api_calls 
                    WHERE DATE(timestamp) = CURRENT_DATE AND success = TRUE
                """)
                
            return {
                "today_api_calls": today_calls,
                "today_emails_stored": today_emails,
                "avg_emails_per_call": round(float(avg_emails_per_call or 0), 2),
                "recent_batches": [dict(batch) for batch in recent_batches],
                "storage_status": {
                    "postgresql": self.postgres_pool is not None,
                    "qdrant": self.qdrant_client is not None,
                    "redis": self.redis_client is not None,
                    "embeddings": self.embedding_model is not None
                }
            }
        except Exception as e:
            print(f"❌ Error getting API stats: {e}")
            return {"error": str(e)}
    
    async def semantic_search_emails(self, query_text: str, limit: int = 10) -> List[Dict]:
        """Search emails using semantic similarity"""
        try:
            if not self.embedding_model or not self.qdrant_client:
                return []
                
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query_text).tolist()
            
            # Search in Qdrant
            search_results = await self.qdrant_client.search(
                collection_name=self.qdrant_collection,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=0.5
            )
            
            return [
                {
                    "gmail_id": hit.payload.get("gmail_id", "") if hit.payload else "",
                    "subject": hit.payload.get("subject", "") if hit.payload else "",
                    "sender": hit.payload.get("sender", "") if hit.payload else "",
                    "similarity_score": hit.score,
                    "snippet": hit.payload.get("snippet", "") if hit.payload else "",
                    "date": hit.payload.get("date", "") if hit.payload else "",
                    "labels": hit.payload.get("labels", []) if hit.payload else []
                }
                for hit in search_results
            ]
            
        except Exception as e:
            print(f"❌ Semantic search error: {e}")
            return []
    
    def _parse_email_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse email date string to datetime"""
        if not date_str:
            return None
        try:
            # Handle various email date formats
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return None
    
    async def close(self):
        """Close all connections"""
        try:
            if self.postgres_pool:
                await self.postgres_pool.close()
            if self.qdrant_client:
                await self.qdrant_client.close()
            if self.redis_client:
                await self.redis_client.aclose()
            print("✅ Gmail Storage Manager connections closed")
        except Exception as e:
            print(f"❌ Error closing connections: {e}")

# Standalone functions for easy integration
async def store_gmail_api_result(call_type: str, query: str, emails: List[Dict], 
                               api_calls_used: int = 1, metadata: Optional[Dict] = None, 
                               execution_time_ms: Optional[int] = None) -> Optional[int]:
    """Store Gmail API result in all storage systems"""
    storage_manager = GmailStorageManager()
    
    await storage_manager.initialize()
    api_call_id = await storage_manager.store_api_call_result(
        call_type, query, emails, api_calls_used, metadata, execution_time_ms
    )
    await storage_manager.close()
    
    return api_call_id

async def get_cached_gmail_result(call_type: str, query: str) -> Optional[Dict]:
    """Get cached Gmail API result"""
    storage_manager = GmailStorageManager()
    await storage_manager.initialize()
    
    result = await storage_manager.get_cached_api_result(call_type, query)
    await storage_manager.close()
    
    return result

async def search_emails_semantic(query_text: str, limit: int = 10) -> List[Dict]:
    """Search emails using semantic similarity"""
    storage_manager = GmailStorageManager()
    await storage_manager.initialize()
    
    results = await storage_manager.semantic_search_emails(query_text, limit)
    await storage_manager.close()
    
    return results
