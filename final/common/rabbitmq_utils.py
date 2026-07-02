"""
RabbitMQ utilities — RPC edition.
publish_and_wait: uses an exclusive auto-delete callback queue per request.
reply_rpc:        consumer sends result back via message.reply_to.
"""
import asyncio
import json
import os
import uuid
from typing import TYPE_CHECKING

import aio_pika
from aio_pika import Message, DeliveryMode
from aio_pika.abc import AbstractIncomingMessage

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


async def create_connection(logger: "Logger | None" = None):
    """
    Connect to RabbitMQ with unlimited retries on the initial attempt.
    aio_pika.connect_robust retries reconnects after a drop, but raises
    immediately if the very first attempt fails (e.g. DNS not yet ready).
    This wrapper retries that first connect so services start cleanly
    regardless of pod startup order.
    """
    delay = 2
    attempt = 0
    while True:
        try:
            return await aio_pika.connect_robust(RABBITMQ_URL)
        except Exception as exc:
            attempt += 1
            if logger:
                from common.logging_utils import log_event
                log_event(logger, "rabbitmq_connecting",
                          attempt=attempt, delay=delay, error=str(exc))
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)  # cap at 30s


async def publish_and_wait(
    channel: aio_pika.Channel,
    queue_name: str,
    body: dict,
    headers: dict | None = None,
    timeout: float = RESPONSE_TIMEOUT,
    logger: "Logger | None" = None,
) -> dict:
    """
    Publish to queue and await response via an exclusive callback queue.

    Following the aio_pika RPC tutorial pattern:
      - Declare an exclusive, auto-delete reply queue (broker assigns the name).
      - Subscribe to it with no_ack=True BEFORE publishing.
      - Set reply_to=callback_queue.name on the outgoing message.
      - Await the Future; delete the queue in the finally block.

    This avoids the amq.rabbitmq.reply-to pseudo-queue, which aio_pika's
    high-level API cannot consume via get_queue() or declare_queue().
    """
    from common.logging_utils import log_event, should_log_request_flow

    correlation_id = str(uuid.uuid4())
    body["correlation_id"] = correlation_id

    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict] = loop.create_future()

    # Exclusive + auto_delete: broker names the queue, deletes it when we cancel.
    callback_queue = await channel.declare_queue(exclusive=True, auto_delete=True)

    async def on_reply(message: AbstractIncomingMessage) -> None:
        if message.correlation_id == correlation_id and not future.done():
            future.set_result(json.loads(message.body.decode()))

    consumer_tag = await callback_queue.consume(on_reply, no_ack=True)

    # Declare the work queue (idempotent) and publish.
    await channel.declare_queue(queue_name, durable=True)
    await channel.default_exchange.publish(
        Message(
            body=json.dumps(body).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            correlation_id=correlation_id,
            reply_to=callback_queue.name,
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
            await callback_queue.cancel(consumer_tag)
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
            # NOT_PERSISTENT — reply does not need to survive a broker restart.
            delivery_mode=DeliveryMode.NOT_PERSISTENT,
        ),
        routing_key=message.reply_to,
    )
    if logger and should_log_request_flow():
        log_event(logger, "rpc_reply_sent",
                  correlation_id=message.correlation_id,
                  status=result.get("status"))
