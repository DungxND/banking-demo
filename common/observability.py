"""
Observability: OpenTelemetry tracing → Instana agent OTLP + Prometheus metrics.

Tracing pipeline:
  FastAPI (OTel instrumentation) → OTLP gRPC → Instana agent :4317
  OTEL_EXPORTER_OTLP_ENDPOINT controls the target (default: http://host.docker.internal:4317)

Metrics:
  Prometheus /metrics endpoint via prometheus_client.
"""
import logging
import os
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

_log = logging.getLogger(__name__)

_metrics_registry: CollectorRegistry | None = None
_request_count: Counter | None = None
_request_latency: Histogram | None = None


def _setup_tracing(service_name: str) -> None:
    """Initialize OTel tracing with OTLP/gRPC export to the Instana agent.

    Resource attributes (service.name, service.namespace, deployment.environment)
    are injected via OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES env vars —
    Resource.create() merges env vars with the SDK default resource automatically.
    The service_name argument is used only as a fallback when OTEL_SERVICE_NAME is unset.

    Endpoint resolution (in priority order):
      1. OTEL_EXPORTER_OTLP_TRACES_ENDPOINT env var (traces-specific, no scheme needed for gRPC)
      2. OTEL_EXPORTER_OTLP_ENDPOINT env var (may include http:// — stripped below for gRPC)
      3. Hardcoded fallback for local Docker Compose

    The gRPC exporter (opentelemetry-exporter-otlp-proto-grpc) expects bare
    host:port — NOT http://host:port. When OTEL_EXPORTER_OTLP_ENDPOINT is set
    with an http:// prefix (as in the k8s Deployment env vars), the scheme is
    stripped here to keep gRPC channel creation clean.
    """
    raw = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://host.docker.internal:4317",
    )
    # Strip http:// or https:// scheme — gRPC channel uses bare host:port.
    # The insecure=True argument below handles plaintext; the scheme prefix
    # would otherwise conflict with gRPC channel security configuration.
    endpoint = raw.removeprefix("https://").removeprefix("http://")

    # SDK reads OTEL_SERVICE_NAME + OTEL_RESOURCE_ATTRIBUTES automatically.
    # Provide service_name as fallback only.
    resource = Resource.create({"service.name": service_name})
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument Redis client — spans for every command (GET, SET, PUBLISH…)
    RedisInstrumentor().instrument()

    _log.info("OTel tracing initialised: service=%s endpoint=%s", service_name, endpoint)


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
    """Wire up OTel tracing + Prometheus metrics + /metrics route for a FastAPI app."""
    _setup_tracing(service_name)
    setup_metrics(service_name)

    # OTel auto-instrumentation: spans for every HTTP request
    FastAPIInstrumentor.instrument_app(app)

    # SQLAlchemy — spans for every query with db.statement, db.table attributes
    from common.db import engine as _engine
    SQLAlchemyInstrumentor().instrument(engine=_engine)

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
