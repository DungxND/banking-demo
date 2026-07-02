"""
API Producer — RPC edition
Receives HTTP from Kong, publishes to RabbitMQ, awaits response via Direct Reply-to.
"""
import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import aio_pika

from common.rabbitmq_utils import path_to_queue, publish_and_wait
from common.logging_utils import get_json_logger, log_event, log_error_event, setup_exception_logging, RequestLogMiddleware
from common.observability import instrument_fastapi

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
CORS_ORIGINS = "http://localhost:3000,https://npd-banking.co,http://npd-banking.co"

logger = get_json_logger("api-producer")

rmq_connection: aio_pika.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rmq_connection
    rmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
    log_event(logger, "rabbitmq_connected")
    yield
    if rmq_connection:
        await rmq_connection.close()


app = FastAPI(title="API Producer", lifespan=lifespan)
instrument_fastapi(app, "api-producer")
setup_exception_logging(app, logger, "api-producer")
app.add_middleware(RequestLogMiddleware, logger=logger, service_name="api-producer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    try:
        if rmq_connection and not rmq_connection.is_closed:
            return {"status": "healthy", "service": "api-producer", "rabbitmq": "ok"}
        return JSONResponse(status_code=503, content={"status": "unhealthy", "rabbitmq": "closed"})
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_queue(request: Request, path: str):
    """Forward all requests to appropriate queue based on path."""
    full_path = f"/{path}" if path else "/"
    if request.url.path:
        full_path = request.url.path

    queue_name = path_to_queue(full_path)
    if not queue_name:
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    # Parse body and headers
    body = {}
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = {}
    elif request.method == "GET":
        body = dict(request.query_params)

    headers = {
        "x-session": request.headers.get("X-Session", ""),
        "x-admin-secret": request.headers.get("X-Admin-Secret", ""),
    }

    # Determine action from path (e.g. /api/auth/register -> register)
    parts = full_path.rstrip("/").split("/")
    action = parts[-1] if parts else ""

    payload = {
        "action": action,
        "path": full_path,
        "method": request.method,
        "payload": body,
        "headers": headers,
    }

    try:
        async with rmq_connection.channel() as channel:
            result = await publish_and_wait(channel, queue_name, payload, headers, logger=logger)
    except TimeoutError as e:
        log_error_event(logger, "producer_timeout", exc=e, path=full_path, service="api-producer")
        return JSONResponse(status_code=504, content={"detail": "Gateway timeout"})
    except Exception as e:
        log_error_event(logger, "producer_error", exc=e, path=full_path, service="api-producer")
        return JSONResponse(status_code=502, content={"detail": str(e)})

    # Result format: { "status": 200, "body": {...} } or { "status": 401, "body": {"detail": "..."} }
    status = result.get("status", 200)
    resp_body = result.get("body", result)
    correlation_id = result.pop("_correlation_id", None)
    response = JSONResponse(status_code=status, content=resp_body)
    if correlation_id:
        response.headers["X-Correlation-Id"] = correlation_id
    return response
