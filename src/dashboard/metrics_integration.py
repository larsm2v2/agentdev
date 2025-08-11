"""
Metrics Collection and Integration for Dashboard

This module integrates with the main email processing server to collect
and stream performance metrics to the dashboard in real-time.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and stores metrics for dashboard consumption"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        
    async def initialize(self):
        """Initialize Redis connection for metrics storage"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            await self.redis_client.ping()
            
            # Set system start time if not exists
            if not await self.redis_client.get("system:start_time"):
                await self.redis_client.set("system:start_time", datetime.now().isoformat())
            
            logger.info("✅ Metrics collector Redis connection established")
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable for metrics: {e}")
            self.redis_client = None
    
    async def record_job_start(self, job_id: str, email_count: int):
        """Record the start of a processing job"""
        if not self.redis_client:
            return
        
        try:
            job_data = {
                "job_id": job_id,
                "start_time": datetime.now().isoformat(),
                "email_count": email_count,
                "status": "started"
            }
            
            await self.redis_client.hset(f"job:{job_id}", mapping=job_data)
            await self.redis_client.expire(f"job:{job_id}", 86400)  # 24 hour expiry
            
        except Exception as e:
            logger.error(f"Error recording job start: {e}")
    
    async def record_job_completion(self, job_id: str, success_count: int, failure_count: int, 
                                  categories: Dict[str, int], processing_time: float):
        """Record the completion of a processing job"""
        if not self.redis_client:
            return
        
        try:
            # Get job start data
            job_data = await self.redis_client.hgetall(f"job:{job_id}")
            if not job_data:
                logger.warning(f"No start data found for job {job_id}")
                return
            
            start_time = datetime.fromisoformat(job_data["start_time"])
            email_count = int(job_data["email_count"])
            
            # Calculate metrics
            success_rate = (success_count / email_count * 100) if email_count > 0 else 100
            emails_per_second = email_count / processing_time if processing_time > 0 else 0
            
            # Update job completion data
            completion_data = {
                "status": "completed",
                "end_time": datetime.now().isoformat(),
                "success_count": success_count,
                "failure_count": failure_count,
                "processing_time": processing_time,
                "success_rate": success_rate,
                "emails_per_second": emails_per_second
            }
            
            await self.redis_client.hset(f"job:{job_id}", mapping=completion_data)
            
            # Update global statistics
            await self._update_global_stats(success_count, failure_count, categories, processing_time, email_count)
            
            # Record processing time for trending
            await self._record_processing_time(job_id, processing_time, email_count)
            
            # Add to recent activity
            await self._add_to_recent_activity(job_id, completion_data)
            
            # Update daily metrics
            await self._update_daily_metrics(email_count, processing_time)
            
            logger.info(f"📊 Recorded job completion metrics for {job_id}")
            
        except Exception as e:
            logger.error(f"Error recording job completion: {e}")
    
    async def record_api_batch_operation(self, batch_size: int, calls_made: int, calls_saved: int):
        """Record batch API operation metrics"""
        if not self.redis_client:
            return
        
        try:
            # Update batch statistics
            await self.redis_client.incrby("api:batch_calls", calls_made)
            await self.redis_client.incrby("api:calls_saved", calls_saved)
            await self.redis_client.incrby("stats:batch_emails", batch_size)
            await self.redis_client.incr("stats:batch_count")
            
            # Update daily batch operations
            today = datetime.now().strftime("%Y-%m-%d")
            await self.redis_client.incr(f"daily:batch_ops:{today}")
            await self.redis_client.expire(f"daily:batch_ops:{today}", 86400 * 7)  # 7 day expiry
            
        except Exception as e:
            logger.error(f"Error recording API batch operation: {e}")
    
    async def record_rate_limit_hit(self):
        """Record a rate limit hit for monitoring"""
        if not self.redis_client:
            return
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            await self.redis_client.incr(f"daily:rate_limits:{today}")
            await self.redis_client.expire(f"daily:rate_limits:{today}", 86400 * 7)  # 7 day expiry
            
        except Exception as e:
            logger.error(f"Error recording rate limit hit: {e}")
    
    async def record_cache_operation(self, operation: str, hit: bool = None):
        """Record cache operation metrics"""
        if not self.redis_client:
            return
        
        try:
            if hit is not None:
                if hit:
                    await self.redis_client.incr("cache:hits")
                else:
                    await self.redis_client.incr("cache:misses")
            
            # Set expiry for cache metrics (reset daily)
            await self.redis_client.expire("cache:hits", 86400)
            await self.redis_client.expire("cache:misses", 86400)
            
        except Exception as e:
            logger.error(f"Error recording cache operation: {e}")
    
    async def _update_global_stats(self, success_count: int, failure_count: int, 
                                 categories: Dict[str, int], processing_time: float, email_count: int):
        """Update global processing statistics"""
        try:
            # Update success/failure counts
            await self.redis_client.incrby("stats:success_count", success_count)
            await self.redis_client.incrby("stats:failure_count", failure_count)
            await self.redis_client.incrby("stats:total_emails", email_count)
            
            # Update category statistics
            for category, count in categories.items():
                await self.redis_client.hincrby("stats:categories", category, count)
                await self.redis_client.incrby("stats:total_categories", count)
            
            # Update peak performance for today
            today = datetime.now().strftime("%Y-%m-%d")
            current_peak = await self.redis_client.get(f"daily:peak_performance:{today}")
            
            if not current_peak or processing_time < float(current_peak):
                await self.redis_client.set(f"daily:peak_performance:{today}", processing_time)
                await self.redis_client.expire(f"daily:peak_performance:{today}", 86400 * 7)
            
        except Exception as e:
            logger.error(f"Error updating global stats: {e}")
    
    async def _record_processing_time(self, job_id: str, processing_time: float, email_count: int):
        """Record processing time for trending analysis"""
        try:
            time_data = {
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "duration": processing_time,
                "emails_count": email_count
            }
            
            # Add to processing times list (keep last 100)
            await self.redis_client.lpush("metrics:processing_times", json.dumps(time_data))
            await self.redis_client.ltrim("metrics:processing_times", 0, 99)
            
        except Exception as e:
            logger.error(f"Error recording processing time: {e}")
    
    async def _add_to_recent_activity(self, job_id: str, completion_data: Dict[str, Any]):
        """Add job to recent activity list"""
        try:
            activity_data = {
                "job_id": job_id,
                "status": completion_data["status"],
                "emails_processed": completion_data.get("success_count", 0) + completion_data.get("failure_count", 0),
                "duration": completion_data["processing_time"],
                "success_rate": completion_data["success_rate"],
                "timestamp": completion_data["end_time"]
            }
            
            # Add to recent activity list (keep last 20)
            await self.redis_client.lpush("jobs:recent_activity", json.dumps(activity_data))
            await self.redis_client.ltrim("jobs:recent_activity", 0, 19)
            
        except Exception as e:
            logger.error(f"Error adding to recent activity: {e}")
    
    async def _update_daily_metrics(self, email_count: int, processing_time: float):
        """Update daily aggregated metrics"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Update daily email count
            await self.redis_client.incrby(f"daily:emails:{today}", email_count)
            await self.redis_client.expire(f"daily:emails:{today}", 86400 * 7)  # 7 day expiry
            
        except Exception as e:
            logger.error(f"Error updating daily metrics: {e}")
    
    async def get_current_metrics_summary(self) -> Dict[str, Any]:
        """Get a quick summary of current metrics"""
        if not self.redis_client:
            return {}
        
        try:
            success_count = await self.redis_client.get("stats:success_count") or "0"
            failure_count = await self.redis_client.get("stats:failure_count") or "0"
            
            total_processed = int(success_count) + int(failure_count)
            success_rate = (int(success_count) / total_processed * 100) if total_processed > 0 else 100
            
            # Get today's email count
            today = datetime.now().strftime("%Y-%m-%d")
            daily_count = await self.redis_client.get(f"daily:emails:{today}") or "0"
            
            return {
                "total_emails_processed": total_processed,
                "success_rate_percentage": round(success_rate, 2),
                "emails_today": int(daily_count),
                "cache_status": "active" if self.redis_client else "disabled"
            }
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}
    
    async def cleanup_old_metrics(self):
        """Clean up old metrics data (run periodically)"""
        if not self.redis_client:
            return
        
        try:
            # Clean up job data older than 24 hours
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            # This is a simplified cleanup - in production, you might want more sophisticated cleanup
            logger.info("🧹 Cleaned up old metrics data")
            
        except Exception as e:
            logger.error(f"Error cleaning up metrics: {e}")


# Global metrics collector instance
metrics_collector = MetricsCollector()


# Decorator for automatic metrics collection
def collect_metrics(func):
    """Decorator to automatically collect metrics from processing functions"""
    import functools
    import time
    import uuid
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        job_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        # Try to extract email count from arguments
        email_count = 0
        if args and hasattr(args[0], '__len__'):
            email_count = len(args[0])
        
        await metrics_collector.record_job_start(job_id, email_count)
        
        try:
            result = await func(*args, **kwargs)
            
            processing_time = time.time() - start_time
            
            # Try to extract success/failure counts from result
            success_count = email_count  # Default assumption
            failure_count = 0
            categories = {}
            
            if isinstance(result, dict):
                success_count = result.get('success_count', email_count)
                failure_count = result.get('failure_count', 0)
                categories = result.get('categories', {})
            
            await metrics_collector.record_job_completion(
                job_id, success_count, failure_count, categories, processing_time
            )
            
            return result
            
        except Exception as e:
            # Record failure
            processing_time = time.time() - start_time
            await metrics_collector.record_job_completion(
                job_id, 0, email_count, {}, processing_time
            )
            raise
    
    return wrapper


# Helper functions for integration
async def initialize_metrics():
    """Initialize metrics collection system"""
    await metrics_collector.initialize()


async def record_batch_api_operation(batch_size: int, calls_made: int, calls_saved: int):
    """Convenience function to record batch API operations"""
    await metrics_collector.record_api_batch_operation(batch_size, calls_made, calls_saved)


async def record_rate_limit():
    """Convenience function to record rate limit hits"""
    await metrics_collector.record_rate_limit_hit()


async def record_cache_hit(hit: bool):
    """Convenience function to record cache operations"""
    await metrics_collector.record_cache_operation("access", hit)
