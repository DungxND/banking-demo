"""
Observability: Instana tracing + Prometheus metrics.
- Tracing: Instana Python sensor (auto-instruments FastAPI, SQLAlchemy, Redis, etc.).
- Metrics: Prometheus /metrics endpoint (prometheus_client).
"""
import os
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry

try:
    import instana  # noqa: F401 — auto-instruments the application
except Exception:
    pass

_metrics_registry: CollectorRegistry | None = None
_request_count: Counter | None = None
_request_latency: Histogram | None = None


def setup_metrics(service_name: str) -> None:
    """Initialize Prometheus metrics for this service."""
    global _metrics_registry, _request_count, _request_latency
    _metrics_registry = CollectorRegistry()
    _request_count = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
        registry=_metrics_registry,
    )
    _request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
        registry=_metrics_registry,
    )


def get_request_counter():
    return _request_count


def get_request_latency():
    return _request_latency


def get_metrics_content() -> bytes:
    """Return Prometheus text format for /metrics endpoint."""
    if _metrics_registry is None:
        return b""
    return generate_latest(_metrics_registry)


def instrument_fastapi(app, service_name: str) -> None:
    """Add Instana tracing, Prometheus metrics middleware, and /metrics route."""
    setup_metrics(service_name)

    from fastapi import Response
    from starlette.middleware.base import BaseHTTPMiddleware
    import time

    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path == "/metrics":
                return await call_next(request)
            start = time.perf_counter()
            response = await call_next(request)
            duration = time.perf_counter() - start
            c, h = get_request_counter(), get_request_latency()
            if c and h:
                endpoint = request.url.path or "/"
                c.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
                h.labels(method=request.method, endpoint=endpoint).observe(duration)
            return response

    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics")
    async def metrics():
        return Response(content=get_metrics_content(), media_type="text/plain; charset=utf-8")
