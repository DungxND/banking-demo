import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db import Base, SessionLocal, engine
from common.models import User
from common.observability import instrument_fastapi
from common.redis_utils import get_user_id_from_session

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

redis: Redis | None = None


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis

    # Schema — idempotent, safe on every restart (account-service owns no
    # migrations; auth-service creates the shared tables first, but
    # create_all is a no-op when the tables already exist)
    Base.metadata.create_all(bind=engine)

    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis.ping()

    log.info("account-service ready")
    yield

    await redis.aclose()
    log.info("account-service shut down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Account Service", lifespan=lifespan)
instrument_fastapi(app, "account-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> Redis:
    if redis is None:
        raise HTTPException(503, "Cache unavailable")
    return redis


async def current_user(
    x_session: str | None = Header(default=None),
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
) -> User:
    """Resolve the session header to a User ORM object."""
    user_id = await get_user_id_from_session(r, x_session)
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/me")
async def me(u: User = Depends(current_user)):
    """Get current user profile and balance."""
    return {"id": u.id, "username": u.username, "balance": u.balance}


@app.get("/balance")
async def balance(u: User = Depends(current_user)):
    """Get current user balance."""
    return {"balance": u.balance}


@app.get("/health")
async def health_check(db: Session = Depends(get_db), r: Redis = Depends(get_redis)):
    """Liveness / readiness probe."""
    try:
        await r.ping()
        db.execute(select(1))
    except Exception as exc:
        raise HTTPException(503, detail=f"Health check failed: {exc}")
    return {"status": "healthy", "service": "account-service"}
