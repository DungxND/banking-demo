import os
import uuid
from redis.asyncio import Redis
from fastapi import HTTPException

SESSION_TTL: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))


async def create_session(redis: Redis, user_id: int) -> str:
    """Create a new session and return the token."""
    sid = uuid.uuid4().hex
    await redis.setex(f"session:{sid}", SESSION_TTL, str(user_id))
    return sid


async def delete_session(redis: Redis, sid: str) -> None:
    """Invalidate an existing session token."""
    await redis.delete(f"session:{sid}")


async def get_user_id_from_session(redis: Redis, x_session: str | None) -> int:
    """Validate a session token and return the associated user ID.

    Refreshes the TTL on each successful access (sliding expiry) so that
    active users are never logged out unexpectedly.
    """
    if not x_session:
        raise HTTPException(401, "Missing session")
    key = f"session:{x_session}"
    v = await redis.get(key)
    if not v:
        raise HTTPException(401, "Invalid or expired session")
    # Slide the expiry forward on each use
    await redis.expire(key, SESSION_TTL)
    return int(v)


async def set_presence(redis: Redis, user_id: int, online: bool) -> None:
    """Set user online/offline presence."""
    key = f"presence:{user_id}"
    if online:
        await redis.setex(key, 60, "online")   # websocket should refresh before expiry
    else:
        await redis.delete(key)


async def publish_notify(redis: Redis, user_id: int, message: str) -> None:
    """Publish a notification to a user's pub/sub channel."""
    await redis.publish(f"notify:{user_id}", message)
