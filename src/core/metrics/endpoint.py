"""
Prometheus metrics endpoint and middleware for the Email Librarian server.
"""
from typing import Optional
from fastapi import FastAPI, Request, Response
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram, Gauge

# use a dedicated registry so metrics are explicit and testable
_registry = CollectorRegistry()

# Basic HTTP request counter and latency histogram
REQUEST_COUNT = Counter(
    "email_librarian_http_requests_total",
    "Total HTTP requests",
    ["method", "path"],
    registry=_registry,
)

REQUEST_LATENCY = Histogram(
    "email_librarian_http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path"],
    registry=_registry,
)

# Optional gauges (example)
STORAGE_UP = Gauge(
    "email_librarian_storage_up",
    "Storage initialization status (1=up,0=down)",
    registry=_registry,
)

# Job system gauges
JOBS_IN_PROGRESS = Gauge(
    "email_librarian_jobs_in_progress",
    "Number of jobs currently in progress",
    registry=_registry,
)

JOB_QUEUE_SIZE = Gauge(
    "email_librarian_job_queue_size",
    "Number of jobs waiting in the queue",
    registry=_registry,
)


from typing import Any
import asyncio
import inspect
import logging

logger = logging.getLogger(__name__)


def _safe_call_maybe_async(func, *args, **kwargs):
    """Call func synchronously or await it if it's a coroutine function or returns an awaitable."""
    try:
        if inspect.iscoroutinefunction(func):
            return func(*args, **kwargs)
        res = func(*args, **kwargs)
        if inspect.isawaitable(res):
            return res
        return res
    except Exception:
        # re-raise; callers will handle logging
        raise


def register_metrics(app: FastAPI, metrics_collector: Optional[Any] = None, poll_interval: float = 5.0) -> None:
    """
    Install Prometheus middleware and /metrics route on the FastAPI app.
    Optionally accepts a metrics_collector (e.g. Redis-backed) to expose additional summary data.
    """
    @app.middleware("http")
    async def _prom_middleware(request: Request, call_next):
        path = request.url.path
        method = request.method
        REQUEST_COUNT.labels(method=method, path=path).inc()
        with REQUEST_LATENCY.labels(method=method, path=path).time():
            response = await call_next(request)
        return response

    @app.get("/metrics")
    async def _metrics():
        data = generate_latest(_registry)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    # optional human-friendly summary endpoint (not Prometheus) and poller
    if metrics_collector is not None:
        @app.get("/metrics/summary")
        async def _metrics_summary():
            try:
                result = _safe_call_maybe_async(metrics_collector.get_current_metrics_summary)
                # await if it's awaitable
                if inspect.isawaitable(result):
                    summary = await result
                else:
                    summary = result

                # expose storage status gauge
                STORAGE_UP.set(1 if summary else 0)

                # update job gauges if available
                if isinstance(summary, dict):
                    if "jobs_in_progress" in summary:
                        JOBS_IN_PROGRESS.set(float(summary.get("jobs_in_progress", 0)))
                    if "job_queue_size" in summary:
                        JOB_QUEUE_SIZE.set(float(summary.get("job_queue_size", 0)))

                return summary
            except Exception as e:
                logger.debug("metrics summary unavailable: %s", e)
                STORAGE_UP.set(0)
                return {"error": "metrics summary unavailable"}

        # background poller to keep gauges up-to-date
        async def _poll_metrics_loop():
            try:
                while True:
                    try:
                        result = _safe_call_maybe_async(metrics_collector.get_current_metrics_summary)
                        if inspect.isawaitable(result):
                            summary = await result
                        else:
                            summary = result

                        if isinstance(summary, dict):
                            if "jobs_in_progress" in summary:
                                JOBS_IN_PROGRESS.set(float(summary.get("jobs_in_progress", 0)))
                            if "job_queue_size" in summary:
                                JOB_QUEUE_SIZE.set(float(summary.get("job_queue_size", 0)))
                            STORAGE_UP.set(1)
                        else:
                            STORAGE_UP.set(0)
                    except Exception as e:
                        logger.debug("metrics poll failed: %s", e)
                        STORAGE_UP.set(0)
                    await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                return

        @app.on_event("startup")
        async def _start_metrics_poller():
            if getattr(app.state, "_metrics_poller", None) is None:
                app.state._metrics_poller = asyncio.create_task(_poll_metrics_loop())

        @app.on_event("shutdown")
        async def _stop_metrics_poller():
            task = getattr(app.state, "_metrics_poller", None)
            if task:
                task.cancel()
                try:
                    await task
                except Exception:
                    pass
                app.state._metrics_poller = None