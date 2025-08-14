"""
Redis Cache Manager for Enhanced Email Librarian
Provides persistent caching, analytics, and cross-session data persistence
"""

import redis.asyncio as redis
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import hashlib

logger = logging.getLogger(__name__)

class RedisCacheManager:
    """Advanced Redis caching system for email processing optimization"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 0):
        """Initialize Redis cache manager with connection pooling"""
        self.redis_url = redis_url
        self.db = db
        self.redis_client = None
        self.connection_pool = None
        
        # Cache TTL settings
        self.label_cache_ttl = timedelta(hours=24)  # Labels cached for 24 hours
        self.stats_cache_ttl = timedelta(days=7)    # Stats cached for 7 days
        self.session_cache_ttl = timedelta(hours=12) # Session data for 12 hours
        
        # Cache keys
        self.LABEL_CACHE_KEY = "gmail:labels:cache"
        self.STATS_PREFIX = "email:stats"
        self.SESSION_PREFIX = "session"
        self.ANALYTICS_PREFIX = "analytics"
        
    async def initialize(self) -> bool:
        """Initialize Redis connection with health check"""
        try:
            logger.info(f"🔗 Attempting to connect to Redis: {self.redis_url}")
            
            # Create connection pool for better performance
            self.connection_pool = redis.ConnectionPool.from_url(
                self.redis_url, 
                db=self.db,
                max_connections=20,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # Health check
            await self.redis_client.ping()
            
            logger.info(f"✅ Redis cache manager initialized successfully (DB: {self.db})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis cache manager: {e}")
            return False
    
    async def close(self):
        """Close Redis connections gracefully"""
        try:
            if self.redis_client:
                await self.redis_client.aclose()
            if self.connection_pool:
                await self.connection_pool.aclose()
            logger.info("Redis connections closed successfully")
        except Exception as e:
            logger.error(f"Error closing Redis connections: {e}")
    
    # ============= LABEL CACHING METHODS =============
    
    async def get_label_cache(self) -> Dict[str, str]:
        """Load Gmail label cache from Redis"""
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return {}
            
        try:
            cache_data = await self.redis_client.get(self.LABEL_CACHE_KEY)
            if cache_data:
                labels = json.loads(cache_data)
                logger.info(f"📋 Loaded {len(labels)} labels from Redis cache")
                return labels
            
            logger.info("No label cache found in Redis")
            return {}
            
        except Exception as e:
            logger.warning(f"Failed to load label cache from Redis: {e}")
            return {}
    
    async def update_label_cache(self, labels: Dict[str, str]) -> bool:
        """Update Gmail label cache in Redis with TTL"""
        try:
            if not self.redis_client:
                logger.error("Redis client is not initialized. Call 'initialize()' before using cache methods.")
                return False

            await self.redis_client.setex(
                self.LABEL_CACHE_KEY,
                self.label_cache_ttl,
                json.dumps(labels)
            )
            
            logger.info(f"📋 Updated Redis label cache with {len(labels)} labels")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update label cache in Redis: {e}")
            return False
    
    async def add_label_to_cache(self, category: str, label_id: str) -> bool:
        """Add single label to cache without full reload"""
        try:
            # Get current cache
            current_cache = await self.get_label_cache()
            
            # Add new label
            current_cache[category] = label_id
            
            # Update cache
            return await self.update_label_cache(current_cache)
            
        except Exception as e:
            logger.error(f"Failed to add label to cache: {e}")
            return False
    
    async def remove_label_from_cache(self, category: str) -> bool:
        """Remove label from cache"""
        try:
            current_cache = await self.get_label_cache()
            
            if category in current_cache:
                del current_cache[category]
                return await self.update_label_cache(current_cache)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove label from cache: {e}")
            return False
    
    # ============= PROCESSING STATISTICS METHODS =============
    
    async def cache_email_processing_stats(self, job_id: str, stats: Dict[str, Any]) -> bool:
        """Cache email processing statistics for analytics"""
        try:
            if not self.redis_client:
                return False
                
            key = f"{self.STATS_PREFIX}:{job_id}"
            
            # Add timestamp to stats
            stats['cached_at'] = datetime.utcnow().isoformat()
            stats['job_id'] = job_id
            
            await self.redis_client.setex(
                key,
                self.stats_cache_ttl,
                json.dumps(stats)
            )
            
            logger.info(f"📊 Cached processing stats for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache processing stats: {e}")
            return False
    
    async def get_processing_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive processing analytics from cached data"""
        try:
            if not self.redis_client:
                return {
                    "total_jobs": 0,
                    "total_emails_processed": 0,
                    "total_vectors_stored": 0,
                    "total_labels_applied": 0,
                    "categories_discovered": set(),
                    "average_processing_time": 0,
                    "success_rate": 0,
                    "daily_breakdown": {}
                }
                
            # Get all stats keys
            pattern = f"{self.STATS_PREFIX}:*"
            keys = await self.redis_client.keys(pattern)
            
            if not keys:
                return {
                    "total_jobs": 0,
                    "total_emails_processed": 0,
                    "total_vectors_stored": 0,
                    "total_labels_applied": 0,
                    "categories_discovered": set(),
                    "average_processing_time": 0,
                    "success_rate": 0,
                    "daily_breakdown": {}
                }
            
            # Get all stats in parallel
            stats_data = await self.redis_client.mget(keys)
            
            analytics = {
                "total_jobs": 0,
                "total_emails_processed": 0,
                "total_vectors_stored": 0,
                "total_labels_applied": 0,
                "categories_discovered": set(),
                "processing_times": [],
                "daily_breakdown": {},
                "performance_trends": []
            }
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            for stats_json in stats_data:
                if stats_json:
                    try:
                        stats = json.loads(stats_json)
                        
                        # Filter by date if timestamp available
                        cached_time = None
                        if 'cached_at' in stats:
                            cached_time = datetime.fromisoformat(stats['cached_at'])
                            if cached_time < cutoff_date:
                                continue
                        
                        # Aggregate statistics
                        analytics["total_jobs"] += 1
                        analytics["total_emails_processed"] += stats.get("processed_count", 0)
                        analytics["total_vectors_stored"] += stats.get("vectors_stored", 0)
                        analytics["total_labels_applied"] += stats.get("labels_applied", 0)
                        
                        # Categories
                        categories = stats.get("categories_created", [])
                        analytics["categories_discovered"].update(categories)
                        
                        # Processing times
                        if "processing_time" in stats:
                            analytics["processing_times"].append(stats["processing_time"])
                        
                        # Daily breakdown
                        if cached_time is not None:
                            date_key = cached_time.strftime("%Y-%m-%d")
                            if date_key not in analytics["daily_breakdown"]:
                                analytics["daily_breakdown"][date_key] = {
                                    "jobs": 0, "emails": 0, "vectors": 0, "labels": 0
                                }
                            
                            analytics["daily_breakdown"][date_key]["jobs"] += 1
                            analytics["daily_breakdown"][date_key]["emails"] += stats.get("processed_count", 0)
                            analytics["daily_breakdown"][date_key]["vectors"] += stats.get("vectors_stored", 0)
                            analytics["daily_breakdown"][date_key]["labels"] += stats.get("labels_applied", 0)
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse stats JSON: {e}")
                        continue
            
            # Calculate derived metrics
            if analytics["processing_times"]:
                analytics["average_processing_time"] = sum(analytics["processing_times"]) / len(analytics["processing_times"])
            else:
                analytics["average_processing_time"] = 0
            
            # Success rate calculation
            if analytics["total_emails_processed"] > 0:
                analytics["success_rate"] = (analytics["total_vectors_stored"] / analytics["total_emails_processed"]) * 100
            else:
                analytics["success_rate"] = 0
            
            # Convert set to list for JSON serialization
            analytics["categories_discovered"] = list(analytics["categories_discovered"])
            
            logger.info(f"📈 Generated analytics for {analytics['total_jobs']} jobs covering {days} days")
            
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get processing analytics: {e}")
            return {"error": str(e)}
    
    # ============= SESSION MANAGEMENT METHODS =============
    
    async def cache_session_data(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Cache session data for user preferences and state"""
        try:
            if not self.redis_client:
                return False
                
            key = f"{self.SESSION_PREFIX}:{session_id}"
            
            # Add metadata
            data['last_updated'] = datetime.utcnow().isoformat()
            data['session_id'] = session_id
            
            await self.redis_client.setex(
                key,
                self.session_cache_ttl,
                json.dumps(data)
            )
            
            logger.info(f"💾 Cached session data for {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache session data: {e}")
            return False
    
    async def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from cache"""
        try:
            if not self.redis_client:
                return None
                
            key = f"{self.SESSION_PREFIX}:{session_id}"
            data = await self.redis_client.get(key)
            
            if data:
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get session data: {e}")
            return None
    
    async def extend_session(self, session_id: str) -> bool:
        """Extend session expiration time"""
        try:
            if not self.redis_client:
                return False
                
            key = f"{self.SESSION_PREFIX}:{session_id}"
            return await self.redis_client.expire(key, self.session_cache_ttl)
            
        except Exception as e:
            logger.error(f"Failed to extend session: {e}")
            return False
    
    # ============= PERFORMANCE MONITORING METHODS =============
    
    async def cache_performance_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Cache real-time performance metrics"""
        try:
            if not self.redis_client:
                return False
                
            key = f"{self.ANALYTICS_PREFIX}:metrics:{datetime.utcnow().strftime('%Y%m%d_%H%M')}"
            
            await self.redis_client.setex(
                key,
                timedelta(hours=2),  # Keep metrics for 2 hours
                json.dumps(metrics)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache performance metrics: {e}")
            return False
    
    async def get_recent_performance_metrics(self, hours: int = 2) -> List[Dict[str, Any]]:
        """Get recent performance metrics for dashboard"""
        try:
            if not self.redis_client:
                return []
                
            # Generate time-based keys for the last N hours
            metrics = []
            current_time = datetime.utcnow()
            
            for hour_offset in range(hours):
                time_key = (current_time - timedelta(hours=hour_offset)).strftime('%Y%m%d_%H*')
                pattern = f"{self.ANALYTICS_PREFIX}:metrics:{time_key}"
                
                keys = await self.redis_client.keys(pattern)
                if keys:
                    metric_data = await self.redis_client.mget(keys)
                    for data in metric_data:
                        if data:
                            try:
                                metrics.append(json.loads(data))
                            except json.JSONDecodeError:
                                continue
            
            # Sort by timestamp
            metrics.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return metrics[:50]  # Return last 50 metrics
            
        except Exception as e:
            logger.error(f"Failed to get recent performance metrics: {e}")
            return []
    
    # ============= HEALTH AND MAINTENANCE METHODS =============
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive Redis health check"""
        try:
            if not self.redis_client:
                return {
                    "status": "unhealthy",
                    "error": "Redis client not initialized",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            start_time = datetime.utcnow()
            
            # Basic connectivity
            await self.redis_client.ping()
            
            # Memory usage
            memory_info = await self.redis_client.info('memory')
            
            # Key count
            db_info = await self.redis_client.info('keyspace')
            
            # Connection info
            client_info = await self.redis_client.info('clients')
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "memory_used_mb": memory_info.get('used_memory', 0) / (1024 * 1024),
                "total_keys": sum(info.get('keys', 0) for info in db_info.values() if isinstance(info, dict)),
                "connected_clients": client_info.get('connected_clients', 0),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def cleanup_expired_keys(self) -> int:
        """Clean up expired keys and perform maintenance"""
        try:
            if not self.redis_client:
                return 0
                
            # Get keys that should be cleaned up
            patterns = [
                f"{self.STATS_PREFIX}:*",
                f"{self.SESSION_PREFIX}:*",
                f"{self.ANALYTICS_PREFIX}:*"
            ]
            
            cleaned_count = 0
            cutoff_date = datetime.utcnow() - timedelta(days=30)  # Clean keys older than 30 days
            
            for pattern in patterns:
                keys = await self.redis_client.keys(pattern)
                
                for key in keys:
                    try:
                        ttl = await self.redis_client.ttl(key)
                        if ttl == -1:  # Key without expiration
                            # Check if it's old data
                            data = await self.redis_client.get(key)
                            if data:
                                try:
                                    parsed_data = json.loads(data)
                                    if 'cached_at' in parsed_data:
                                        cached_time = datetime.fromisoformat(parsed_data['cached_at'])
                                        if cached_time < cutoff_date:
                                            await self.redis_client.delete(key)
                                            cleaned_count += 1
                                except:
                                    continue
                    except:
                        continue
            
            logger.info(f"🧹 Cleaned up {cleaned_count} expired keys from Redis")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired keys: {e}")
            return 0
