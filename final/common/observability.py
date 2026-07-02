"""
Observability: OpenTelemetry tracing + Prometheus metrics.
- Tracing: OTLP/gRPC export. Endpoint from OTEL_EXPORTER_OTLP_ENDPOINT env var.
  http:// scheme is stripped — gRPC channel needs bare host:port.
  If env var is unset, tracing is silently skipped.
- Metrics: Prometheus /metrics endpoint via prometheus_client.
"""
import logging
import os
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry

_log = logging.getLogger(__name__)

_metrics_registry: CollectorRegistry | None = None
_request_count: Counter | None = None
_request_latency: Histogram | None = None


def init_tracing(service_name: str) -> None:
    """Initialize OTel tracer. No-op if OTEL_EXPORTER_OTLP_ENDPOINT is unset."""
    raw = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not raw:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        # Strip http:// or https:// — gRPC channel uses bare host:port.
        endpoint = raw.removeprefix("https://").removeprefix("http://")

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
        trace.set_tracer_provider(provider)

        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            RedisInstrumentor().instrument()
        except Exception:
            pass

        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            from common import db
            if getattr(db, "engine", None):
                SQLAlchemyInstrumentor().instrument(engine=db.engine)
        except Exception:
            pass

        _log.info("OTel tracing initialised: service=%s endpoint=%s", service_name, endpoint)
    except Exception:
        pass


def get_tracer(service_name: str):
    """Get tracer for manual spans. Returns None if tracing not initialised."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(service_name, "1.0")
    except Exception:
        return None


def setup_metrics(service_name: str) -> None:
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


def get_metrics_content() -> bytes:
    if _metrics_registry is None:
        return b""
    return generate_latest(_metrics_registry)


def instrument_fastapi(app, service_name: str) -> None:
    """Wire up OTel tracing + Prometheus metrics + /metrics route for a FastAPI app."""
    init_tracing(service_name)
    setup_metrics(service_name)

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass

    from fastapi import Response
    from starlette.middleware.base import BaseHTTPMiddleware
    import time

    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path in ("/metrics", "/health"):
                return await call_next(request)
            start = time.perf_counter()
            response = await call_next(request)
            duration = time.perf_counter() - start
            c, h = _request_count, _request_latency
            if c and h:
                endpoint = request.url.path or "/"
                c.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
                h.labels(method=request.method, endpoint=endpoint).observe(duration)
            return response

    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics")
    async def metrics():
        return Response(content=get_metrics_content(), media_type="text/plain; charset=utf-8")
