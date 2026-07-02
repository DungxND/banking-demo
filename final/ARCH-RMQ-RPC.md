# Architecture Change: Redis Polling → RabbitMQ RPC

## Problem

`api-producer` currently uses a busy-poll loop to wait for consumer responses:

```python
# common/rabbitmq_utils.py — current
for _ in range(RESPONSE_TIMEOUT * 10):   # up to 600 iterations
    raw = await redis.get(redis_key)
    if raw:
        ...
    await asyncio.sleep(0.1)             # 100 ms interval
```

Issues:
- **Latency floor of 100 ms** per request even when the consumer replies in < 5 ms.
- **600 Redis `GET` commands per request** at worst case. At 100 concurrent requests that is 6 000 Redis round-trips per second before any real work happens.
- **Redis carries three unrelated roles**: session store, user-data cache, and response bus. The response-bus role is the wrong one — Redis is not a message broker.
- Orphaned `response:{corr_id}` keys accumulate in Redis if the producer crashes after publishing but before reading the reply.

## Solution: RabbitMQ Direct Reply-to (RPC pattern)

RabbitMQ has a built-in pseudo-queue called `amq.rabbitmq.reply-to`. When a producer publishes a message with `reply_to="amq.rabbitmq.reply-to"`, RabbitMQ routes the consumer's reply back to the exact channel that sent the original message — with no queue creation, no cleanup, and no shared state.

```
Producer channel                Consumer
───────────────                 ────────
publish(
  routing_key = "auth.requests"
  reply_to    = "amq.rabbitmq.reply-to"
  corr_id     = "uuid-xyz"
)
                 ──────────────────────►
                                process message
                                reply(
                                  routing_key = message.reply_to
                                  corr_id     = "uuid-xyz"
                                  body        = {status, body}
                                )
                 ◄──────────────────────
await asyncio.Future  ← resolved by on_reply callback
```

The producer awaits an `asyncio.Future` that is resolved by an AMQP message callback. No polling loop, no Redis writes in the request path.

## What changes, what stays

```
                    BEFORE                          AFTER
                    ──────────────────────          ──────────────────────────────
Request path        RMQ publish → Redis poll        RMQ publish → Future.await
Response delivery   Consumer → redis.setex()        Consumer → rmq reply(reply_to)
Redis roles         session + cache + response bus  session + cache only  ✅
Polling loop        600× redis.get per request      zero
New dependencies    none                            none (aio_pika already present)
```

Redis is **not removed** from the project. It still owns:
- `session:{sid}` — user login sessions (auth-service reads, all consumers validate)
- `user_cache:phone:{phone}` — login user-data cache (auth-service)
- `notify:{user_id}` — pub/sub channel for WebSocket push (transfer-service publishes, notification-service subscribes)

## Files affected

| File | Change |
|------|--------|
| `common/rabbitmq_utils.py` | Rewrite `publish_and_wait` (remove `redis` param, replace poll with Future); replace `store_response` with `reply_rpc` |
| `producer/main.py` | Remove `redis` from `publish_and_wait` call; remove Redis init from lifespan |
| `services/auth-service/main.py` | `process_message` uses `reply_rpc` instead of `store_response`; pass `channel` into closure |
| `services/account-service/main.py` | Same as auth-service |
| `services/transfer-service/main.py` | Same as auth-service; Redis stays for `publish_notify` |
| `services/notification-service/main.py` | Same as auth-service |
| `docker-compose.yml` | Remove `REDIS_URL` from `api-producer` environment block |
| `final/helm/values.yaml` | Remove `redisUrl` from `api-producer.secretRef.keys` |

---

## Implementation

### Step 1 — `common/rabbitmq_utils.py`

Full replacement of the two public functions that touch the response path.

```python
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
```

> **Why `channel.get_queue` instead of `declare_queue`?**
> `amq.rabbitmq.reply-to` is a broker-internal pseudo-queue. Declaring it as a
> regular durable queue raises a channel error. `get_queue` / a passive declare
> fetches the existing queue object without trying to create it.

---

### Step 2 — `producer/main.py`

Two targeted changes only:

```python
# REMOVE from lifespan:
redis = await create_redis_client(REDIS_URL, logger=logger)   # ← delete
# ...
await redis.close()                                            # ← delete

# REMOVE global:
redis: Redis | None = None                                     # ← delete

# CHANGE publish_and_wait call (remove redis arg):
# BEFORE:
result = await publish_and_wait(redis, channel, queue_name, payload, headers, logger=logger)
# AFTER:
result = await publish_and_wait(channel, queue_name, payload, headers, logger=logger)
```

The `/health` endpoint currently pings Redis to confirm connectivity. After this
change remove the Redis ping or replace it with an RMQ connection check:

```python
@app.get("/health")
async def health():
    try:
        # Verify RabbitMQ connection is alive instead of Redis
        if rmq_connection and not rmq_connection.is_closed:
            return {"status": "healthy", "service": "api-producer", "rabbitmq": "ok"}
        return JSONResponse(status_code=503, content={"status": "unhealthy", "rabbitmq": "closed"})
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})
```

---

### Step 3 — Each consumer (same pattern for all four)

Two changes per consumer:

**a) Pass `channel` into `process_message` closure**

```python
# BEFORE — process_message is a top-level async def with redis in module scope:
async def process_message(message: IncomingMessage):
    ...
    await store_response(redis, correlation_id, result, logger=logger)

async def consume():
    ...
    await queue.consume(process_message)

# AFTER — process_message is a closure so it captures channel:
async def consume():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=5)
    queue = await channel.declare_queue("<service>.requests", durable=True)

    async def process_message(message: IncomingMessage):
        async with message.process():
            body = {}
            try:
                body = json.loads(message.body.decode())
                correlation_id = body.get("correlation_id")
                ...
                # CHANGED: reply via RMQ instead of writing to Redis
                await reply_rpc(message, channel, result, logger=logger)
            except Exception as e:
                log_error_event(logger, "consumer_error", exc=e, ...)
                await reply_rpc(
                    message, channel,
                    {"status": 500, "body": {"detail": str(e)}},
                    logger=logger,
                )

    await queue.consume(process_message)
    log_event(logger, "rabbitmq_connected")
    await asyncio.Future()
```

**b) Update imports**

```python
# REMOVE:
from common.rabbitmq_utils import store_response

# ADD:
from common.rabbitmq_utils import reply_rpc
```

**transfer-service note:** Redis stays in scope because `publish_notify` still
needs it for WebSocket push. Only the `store_response` call is replaced.

---

### Step 4 — Remove Redis from `api-producer` environment

**`docker-compose.yml`** — remove one line from the `api-producer` block:

```yaml
api-producer:
  environment:
    # REMOVE the line below:
    REDIS_URL: redis://redis:6379/0
    RABBITMQ_URL: amqp://banking:bankingpass@rabbitmq:5672/
```

**`final/helm/values.yaml`** — remove `redisUrl` from `api-producer.secretRef`:

```yaml
# BEFORE:
api-producer:
  secretRef:
    name: banking-db-secret
    keys:
      redisUrl: REDIS_URL       # ← remove this line
      # (no databaseUrl — api-producer is stateless)

# AFTER:
api-producer:
  secretRef:
    name: banking-db-secret
    keys: {}                    # or remove secretRef entirely if nothing remains
```

---

## Edge cases

### Producer pod restarts mid-request
The `asyncio.Future` lives in the pod's memory. If the pod restarts, the future
is lost and the client receives a 502. The consumer will deliver the reply to a
now-dead channel and RabbitMQ will silently drop it (the pseudo-queue binding is
gone). **This is the same observable behaviour as the polling approach** — the
client sees a 502 and retries.

### Consumer crash before replying
The message is NACK'd (via `message.process()` context manager on exception) and
requeued. The producer's `asyncio.wait_for` will timeout after `RESPONSE_TIMEOUT`
seconds and return a 504. No orphaned keys are left anywhere.

### Consumer reply arrives after producer timeout
`asyncio.wait_for` cancels the future. The reply message arrives on the
`amq.rabbitmq.reply-to` pseudo-queue but the consumer tag has already been
cancelled in the `finally` block. RabbitMQ drops the message. No side effects.

### Multi-replica Producer
`amq.rabbitmq.reply-to` routing is per-channel, not per-service-name. Each
channel gets a unique internal ID from the broker. The consumer echoes back the
`reply_to` from the original message, so the reply is routed to the exact channel
— and therefore the exact pod — that sent the request. No shared state required.

### Concurrent requests on the same Producer pod
Each call to `publish_and_wait` creates its own `correlation_id`, its own
`asyncio.Future`, and its own consumer tag on `amq.rabbitmq.reply-to`. The
`on_reply` callback checks `message.correlation_id == correlation_id` before
resolving the future. Concurrent requests are fully isolated.

---

## Testing

```bash
# 1. Bring the stack up
cd final
docker compose up --build

# 2. Register a user
curl -s -X POST http://localhost:3000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"phone":"0900000001","username":"alice","password":"pass123"}' | jq .

# 3. Login — verify session comes back (proves full RPC round-trip)
curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"0900000001","password":"pass123"}' | jq .

# 4. Confirm Redis has NO response: keys (should return empty)
docker exec banking-redis redis-cli keys "response:*"

# 5. Smoke-test latency — should be well under 50 ms for local Compose
time curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"0900000001","password":"pass123"}' > /dev/null

# 6. Verify producer logs show rpc_publish / rpc_reply_received (not redis_wait_start)
docker logs api-producer 2>&1 | grep -E '"event":"rpc_(publish|reply)"'
```

---

## Rollback

If the RPC change needs to be reverted:

1. Restore `common/rabbitmq_utils.py` from git (`store_response` + polling loop).
2. Restore `from common.rabbitmq_utils import store_response` in each consumer.
3. Restore `redis` init in `producer/main.py`.
4. Restore `REDIS_URL` in `api-producer` env blocks.

No data migration required — Redis keys for session and cache are unaffected.
