"""
RabbitMQ utilities — RPC edition.
publish_and_wait: uses amq.rabbitmq.reply-to (Direct Reply-to), no Redis polling.
reply_rpc:        consumer sends result back via message.reply_to.
"""
import asyncio
import json
import os
import uuid
from typing import TYPE_CHECKING

import aio_pika
from aio_pika import Message, DeliveryMode

if TYPE_CHECKING:
    from logging import Logger

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
RESPONSE_TIMEOUT = int(os.getenv("RABBITMQ_RESPONSE_TIMEOUT", "60"))


def path_to_queue(path: str) -> str | None:
    """Map API path prefix to queue name. Unchanged."""
    if path.startswith("/api/auth"):
        return "auth.requests"
    if path.startswith("/api/account"):
        return "account.requests"
    if path.startswith("/api/transfer"):
        return "transfer.requests"
    if path.startswith("/api/notifications"):
        return "notification.requests"
    return None


async def create_connection():
    return await aio_pika.connect_robust(RABBITMQ_URL)


async def publish_and_wait(
    channel: aio_pika.Channel,
    queue_name: str,
    body: dict,
    headers: dict | None = None,
    timeout: float = RESPONSE_TIMEOUT,
    logger: "Logger | None" = None,
) -> dict:
    """
    Publish to queue and await response via RabbitMQ Direct Reply-to.

    The producer subscribes to amq.rabbitmq.reply-to BEFORE publishing so
    that no reply can arrive before the consumer tag is registered. The
    asyncio.Future is resolved by the on_reply callback and the consumer
    tag is cancelled in the finally block regardless of outcome.
    """
    from common.logging_utils import log_event, should_log_request_flow

    correlation_id = str(uuid.uuid4())
    body["correlation_id"] = correlation_id

    loop = asyncio.get_event_loop()
    future: asyncio.Future[dict] = loop.create_future()

    # amq.rabbitmq.reply-to is a pseudo-queue managed by the broker.
    # Consume it with no_ack=True — the broker requires this for Direct Reply-to.
    reply_queue = await channel.get_queue("amq.rabbitmq.reply-to")

    async def on_reply(message: aio_pika.IncomingMessage) -> None:
        if message.correlation_id == correlation_id and not future.done():
            future.set_result(json.loads(message.body.decode()))

    consumer_tag = await reply_queue.consume(on_reply, no_ack=True)

    # Declare the work queue (idempotent) and publish.
    await channel.declare_queue(queue_name, durable=True)
    await channel.default_exchange.publish(
        Message(
            body=json.dumps(body).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=correlation_id,
            reply_to="amq.rabbitmq.reply-to",
            headers=headers or {},
        ),
        routing_key=queue_name,
    )

    if logger and should_log_request_flow():
        log_event(logger, "rpc_publish", queue=queue_name, correlation_id=correlation_id)

    try:
        result = await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        result["_correlation_id"] = correlation_id
        if logger and should_log_request_flow():
            log_event(logger, "rpc_reply_received", correlation_id=correlation_id,
                      status=result.get("status"))
        return result
    except asyncio.TimeoutError:
        future.cancel()
        raise TimeoutError(f"No RPC reply for {correlation_id} within {timeout}s")
    finally:
        try:
            await reply_queue.cancel(consumer_tag)
        except Exception:
            pass


async def reply_rpc(
    message: aio_pika.IncomingMessage,
    channel: aio_pika.Channel,
    result: dict,
    logger: "Logger | None" = None,
) -> None:
    """
    Send result back to the producer via message.reply_to.
    No-op if the message has no reply_to (allows fire-and-forget callers).
    """
    from common.logging_utils import log_event, should_log_request_flow

    if not message.reply_to:
        return
    await channel.default_exchange.publish(
        Message(
            body=json.dumps(result).encode(),
            correlation_id=message.correlation_id,
            # TRANSIENT — reply does not need to survive a broker restart.
            delivery_mode=DeliveryMode.TRANSIENT,
        ),
        routing_key=message.reply_to,
    )
    if logger and should_log_request_flow():
        log_event(logger, "rpc_reply_sent",
                  correlation_id=message.correlation_id,
                  status=result.get("status"))
