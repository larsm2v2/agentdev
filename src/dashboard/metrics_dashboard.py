"""
Real-time Metrics Dashboard for Gmail AI Processing System

Features:
- Live performance monitoring with WebSocket streaming
- Redis analytics integration
- Real-time job tracking
- Performance trend visualization
- System health monitoring
"""

from typing import Dict, List, Any, Optional
import asyncio
import json
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import redis.asyncio as redis
from contextlib import asynccontextmanager
import os

logger = logging.getLogger(__name__)


class MetricsDashboard:
    """Real-time metrics dashboard with WebSocket streaming"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.active_connections: List[WebSocket] = []
        self.metrics_cache = {}
        self.last_update = datetime.now()
        
    async def initialize(self):
        """Initialize Redis connection for metrics"""
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
            logger.info("✅ Metrics Dashboard Redis connection established")
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable for metrics: {e}")
            self.redis_client = None
    
    async def get_live_metrics(self) -> Dict[str, Any]:
        """Get comprehensive live system metrics"""
        current_time = datetime.now()
        
        try:
            # Core performance metrics
            performance_data = await self._get_performance_metrics()
            
            # System health metrics
            health_data = await self._get_system_health()
            
            # Processing statistics
            processing_stats = await self._get_processing_statistics()
            
            # API efficiency metrics
            api_metrics = await self._get_api_efficiency_metrics()
            
            # Recent job activity
            recent_jobs = await self._get_recent_job_activity()
            
            metrics = {
                "timestamp": current_time.isoformat(),
                "performance": performance_data,
                "health": health_data,
                "processing": processing_stats,
                "api_efficiency": api_metrics,
                "recent_jobs": recent_jobs,
                "cache_status": await self._get_cache_status()
            }
            
            self.metrics_cache = metrics
            self.last_update = current_time
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting live metrics: {e}")
            return self._get_fallback_metrics()
    
    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics"""
        if not self.redis_client:
            return self._fallback_performance_metrics()
        
        try:
            # Get processing times from last 24 hours
            processing_times = await self.redis_client.lrange("metrics:processing_times", 0, -1)
            processing_data = [json.loads(pt) for pt in processing_times] if processing_times else []
            
            # Calculate averages and trends
            recent_times = [p["duration"] for p in processing_data if 
                          datetime.fromisoformat(p["timestamp"]) > datetime.now() - timedelta(hours=24)]
            
            avg_processing_time = sum(recent_times) / len(recent_times) if recent_times else 0
            
            # Get throughput data
            hourly_throughput = await self._calculate_hourly_throughput()
            
            return {
                "avg_processing_time_seconds": round(avg_processing_time, 2),
                "emails_processed_last_hour": hourly_throughput,
                "total_emails_processed_today": await self._get_daily_email_count(),
                "processing_speed_trend": await self._get_processing_trend(),
                "peak_performance_today": await self._get_peak_performance()
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return self._fallback_performance_metrics()
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health and status metrics"""
        health = {
            "status": "healthy",
            "uptime_hours": await self._get_system_uptime(),
            "redis_status": "connected" if self.redis_client else "disconnected",
            "active_websocket_connections": len(self.active_connections)
        }
        
        if self.redis_client:
            try:
                # Redis health check
                redis_info = await self.redis_client.info()
                health.update({
                    "redis_memory_usage_mb": round(redis_info.get("used_memory", 0) / (1024 * 1024), 2),
                    "redis_connected_clients": redis_info.get("connected_clients", 0),
                    "redis_uptime_hours": round(redis_info.get("uptime_in_seconds", 0) / 3600, 2)
                })
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")
                health["redis_status"] = "error"
        
        return health
    
    async def _get_processing_statistics(self) -> Dict[str, Any]:
        """Get email processing statistics"""
        if not self.redis_client:
            return self._fallback_processing_stats()
        
        try:
            # Get success/failure rates
            success_count = await self.redis_client.get("stats:success_count") or "0"
            failure_count = await self.redis_client.get("stats:failure_count") or "0"
            
            total_processed = int(success_count) + int(failure_count)
            success_rate = (int(success_count) / total_processed * 100) if total_processed > 0 else 100
            
            # Get category distribution
            category_stats = await self._get_category_distribution()
            
            return {
                "total_emails_processed": total_processed,
                "success_rate_percentage": round(success_rate, 2),
                "successful_categorizations": int(success_count),
                "failed_categorizations": int(failure_count),
                "category_distribution": category_stats,
                "average_categories_per_email": await self._get_avg_categories_per_email()
            }
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {e}")
            return self._fallback_processing_stats()
    
    async def _get_api_efficiency_metrics(self) -> Dict[str, Any]:
        """Get Gmail API efficiency metrics"""
        if not self.redis_client:
            return self._fallback_api_metrics()
        
        try:
            # Get API call savings
            batch_calls = await self.redis_client.get("api:batch_calls") or "0"
            individual_calls_saved = await self.redis_client.get("api:calls_saved") or "0"
            
            # Calculate efficiency
            total_calls_would_be = int(batch_calls) + int(individual_calls_saved)
            efficiency_percentage = (int(individual_calls_saved) / total_calls_would_be * 100) if total_calls_would_be > 0 else 0
            
            return {
                "api_calls_made": int(batch_calls),
                "api_calls_saved": int(individual_calls_saved),
                "efficiency_percentage": round(efficiency_percentage, 2),
                "batch_operations_today": await self._get_batch_operations_count(),
                "rate_limit_hits": await self._get_rate_limit_hits(),
                "average_batch_size": await self._get_average_batch_size()
            }
            
        except Exception as e:
            logger.error(f"Error getting API efficiency metrics: {e}")
            return self._fallback_api_metrics()
    
    async def _get_recent_job_activity(self) -> List[Dict[str, Any]]:
        """Get recent job activity for monitoring"""
        if not self.redis_client:
            return []
        
        try:
            # Get last 10 job activities
            recent_activities = await self.redis_client.lrange("jobs:recent_activity", 0, 9)
            activities = []
            
            for activity in recent_activities:
                job_data = json.loads(activity)
                activities.append({
                    "job_id": job_data.get("job_id", "unknown"),
                    "status": job_data.get("status", "unknown"),
                    "emails_processed": job_data.get("emails_processed", 0),
                    "duration_seconds": job_data.get("duration", 0),
                    "timestamp": job_data.get("timestamp", datetime.now().isoformat()),
                    "success_rate": job_data.get("success_rate", 0)
                })
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting recent job activity: {e}")
            return []
    
    async def _get_cache_status(self) -> Dict[str, Any]:
        """Get cache system status"""
        if not self.redis_client:
            return {"status": "disabled", "label_cache_size": 0}
        
        try:
            # Check cache sizes and status
            label_cache_size = await self.redis_client.hlen("gmail:labels")
            session_cache_size = await self.redis_client.dbsize()
            
            # Get cache hit rates
            cache_hits = await self.redis_client.get("cache:hits") or "0"
            cache_misses = await self.redis_client.get("cache:misses") or "0"
            
            total_requests = int(cache_hits) + int(cache_misses)
            hit_rate = (int(cache_hits) / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "status": "active",
                "label_cache_size": label_cache_size,
                "total_cached_items": session_cache_size,
                "cache_hit_rate_percentage": round(hit_rate, 2),
                "memory_usage_mb": await self._get_cache_memory_usage()
            }
            
        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {"status": "error", "error": str(e)}
    
    # Helper methods for calculations
    async def _calculate_hourly_throughput(self) -> int:
        """Calculate emails processed in the last hour"""
        if not self.redis_client:
            return 0
        
        try:
            hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            processing_times = await self.redis_client.lrange("metrics:processing_times", 0, -1)
            
            recent_count = 0
            for pt in processing_times:
                data = json.loads(pt)
                if data["timestamp"] > hour_ago:
                    recent_count += data.get("emails_count", 1)
            
            return recent_count
        except:
            return 0
    
    async def _get_daily_email_count(self) -> int:
        """Get total emails processed today"""
        if not self.redis_client:
            return 0
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            daily_count = await self.redis_client.get(f"daily:emails:{today}")
            return int(daily_count) if daily_count else 0
        except:
            return 0
    
    async def _get_processing_trend(self) -> str:
        """Get processing speed trend (improving/declining/stable)"""
        if not self.redis_client:
            return "unknown"
        
        try:
            processing_times = await self.redis_client.lrange("metrics:processing_times", 0, 19)  # Last 20
            if len(processing_times) < 10:
                return "insufficient_data"
            
            recent_avg = sum(json.loads(pt)["duration"] for pt in processing_times[:10]) / 10
            older_avg = sum(json.loads(pt)["duration"] for pt in processing_times[10:]) / len(processing_times[10:])
            
            if recent_avg < older_avg * 0.9:
                return "improving"
            elif recent_avg > older_avg * 1.1:
                return "declining"
            else:
                return "stable"
        except:
            return "unknown"
    
    # WebSocket connection management
    async def connect_websocket(self, websocket: WebSocket):
        """Add new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✅ New dashboard connection. Total: {len(self.active_connections)}")
    
    async def disconnect_websocket(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"❌ Dashboard connection closed. Total: {len(self.active_connections)}")
    
    async def broadcast_metrics(self, metrics: Dict[str, Any]):
        """Broadcast metrics to all connected WebSocket clients"""
        if not self.active_connections:
            return
        
        message = json.dumps({
            "type": "metrics_update",
            "data": metrics
        })
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            await self.disconnect_websocket(conn)
    
    async def start_metrics_streaming(self):
        """Start continuous metrics streaming"""
        logger.info("🚀 Starting metrics streaming...")
        
        while True:
            try:
                # Update metrics every 5 seconds
                metrics = await self.get_live_metrics()
                await self.broadcast_metrics(metrics)
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                logger.info("📊 Metrics streaming stopped")
                break
            except Exception as e:
                logger.error(f"Error in metrics streaming: {e}")
                await asyncio.sleep(10)  # Wait longer on error
    
    # Fallback methods for when Redis is unavailable
    def _fallback_performance_metrics(self) -> Dict[str, Any]:
        return {
            "avg_processing_time_seconds": 0,
            "emails_processed_last_hour": 0,
            "total_emails_processed_today": 0,
            "processing_speed_trend": "unknown",
            "peak_performance_today": 0
        }
    
    def _fallback_processing_stats(self) -> Dict[str, Any]:
        return {
            "total_emails_processed": 0,
            "success_rate_percentage": 100,
            "successful_categorizations": 0,
            "failed_categorizations": 0,
            "category_distribution": {},
            "average_categories_per_email": 0
        }
    
    def _fallback_api_metrics(self) -> Dict[str, Any]:
        return {
            "api_calls_made": 0,
            "api_calls_saved": 0,
            "efficiency_percentage": 0,
            "batch_operations_today": 0,
            "rate_limit_hits": 0,
            "average_batch_size": 0
        }
    
    def _get_fallback_metrics(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now().isoformat(),
            "performance": self._fallback_performance_metrics(),
            "health": {"status": "degraded", "redis_status": "disconnected"},
            "processing": self._fallback_processing_stats(),
            "api_efficiency": self._fallback_api_metrics(),
            "recent_jobs": [],
            "cache_status": {"status": "disabled"}
        }

    # Additional helper methods for comprehensive metrics
    async def _get_peak_performance(self) -> float:
        """Get peak performance (fastest processing time today)"""
        if not self.redis_client:
            return 0.0
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            peak_time = await self.redis_client.get(f"daily:peak_performance:{today}")
            return float(peak_time) if peak_time else 0.0
        except:
            return 0.0
    
    async def _get_system_uptime(self) -> float:
        """Get system uptime in hours"""
        if not self.redis_client:
            return 0.0
        
        try:
            start_time = await self.redis_client.get("system:start_time")
            if start_time:
                start = datetime.fromisoformat(start_time)
                uptime = (datetime.now() - start).total_seconds() / 3600
                return round(uptime, 2)
        except:
            pass
        return 0.0
    
    async def _get_category_distribution(self) -> Dict[str, int]:
        """Get distribution of email categories"""
        if not self.redis_client:
            return {}
        
        try:
            categories = await self.redis_client.hgetall("stats:categories")
            return {k: int(v) for k, v in categories.items()} if categories else {}
        except:
            return {}
    
    async def _get_avg_categories_per_email(self) -> float:
        """Get average number of categories per email"""
        if not self.redis_client:
            return 0.0
        
        try:
            total_categories = await self.redis_client.get("stats:total_categories") or "0"
            total_emails = await self.redis_client.get("stats:total_emails") or "0"
            
            if int(total_emails) > 0:
                return round(int(total_categories) / int(total_emails), 2)
        except:
            pass
        return 0.0
    
    async def _get_batch_operations_count(self) -> int:
        """Get number of batch operations today"""
        if not self.redis_client:
            return 0
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            count = await self.redis_client.get(f"daily:batch_ops:{today}")
            return int(count) if count else 0
        except:
            return 0
    
    async def _get_rate_limit_hits(self) -> int:
        """Get number of rate limit hits today"""
        if not self.redis_client:
            return 0
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            hits = await self.redis_client.get(f"daily:rate_limits:{today}")
            return int(hits) if hits else 0
        except:
            return 0
    
    async def _get_average_batch_size(self) -> float:
        """Get average batch size"""
        if not self.redis_client:
            return 0.0
        
        try:
            total_emails = await self.redis_client.get("stats:batch_emails") or "0"
            total_batches = await self.redis_client.get("stats:batch_count") or "0"
            
            if int(total_batches) > 0:
                return round(int(total_emails) / int(total_batches), 2)
        except:
            pass
        return 0.0
    
    async def _get_cache_memory_usage(self) -> float:
        """Get cache memory usage in MB"""
        if not self.redis_client:
            return 0.0
        
        try:
            info = await self.redis_client.info()
            return round(info.get("used_memory", 0) / (1024 * 1024), 2)
        except:
            return 0.0


# Global dashboard instance
dashboard = MetricsDashboard()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    # Startup
    await dashboard.initialize()
    
    # Start metrics streaming task
    streaming_task = asyncio.create_task(dashboard.start_metrics_streaming())
    
    yield
    
    # Shutdown
    streaming_task.cancel()
    try:
        await streaming_task
    except asyncio.CancelledError:
        pass
    
    if dashboard.redis_client:
        await dashboard.redis_client.close()


# Create FastAPI app with lifespan
app = FastAPI(
    title="Gmail AI Metrics Dashboard",
    description="Real-time performance monitoring for Gmail AI processing system",
    version="1.0.0",
    lifespan=lifespan
)

# Setup templates and static files
templates = Jinja2Templates(directory="src/dashboard/templates")

# API Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Serve the main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/metrics/live")
async def get_live_metrics():
    """Get current live metrics"""
    return await dashboard.get_live_metrics()

@app.get("/api/metrics/summary")
async def get_metrics_summary():
    """Get summarized metrics for quick overview"""
    full_metrics = await dashboard.get_live_metrics()
    
    return {
        "status": full_metrics["health"]["status"],
        "emails_processed_today": full_metrics["processing"]["total_emails_processed"],
        "success_rate": full_metrics["processing"]["success_rate_percentage"],
        "avg_processing_time": full_metrics["performance"]["avg_processing_time_seconds"],
        "api_efficiency": full_metrics["api_efficiency"]["efficiency_percentage"],
        "cache_status": full_metrics["cache_status"]["status"]
    }

@app.websocket("/ws/metrics")
async def websocket_metrics_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics streaming"""
    await dashboard.connect_websocket(websocket)
    
    try:
        # Send initial metrics
        initial_metrics = await dashboard.get_live_metrics()
        await websocket.send_text(json.dumps({
            "type": "initial_metrics",
            "data": initial_metrics
        }))
        
        # Keep connection alive
        while True:
            # Wait for client messages (ping/pong)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_text(json.dumps({"type": "ping"}))
                
    except WebSocketDisconnect:
        await dashboard.disconnect_websocket(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await dashboard.disconnect_websocket(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
