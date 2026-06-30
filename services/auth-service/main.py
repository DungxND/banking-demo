import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.auth import hash_password, verify_password
from common.db import Base, SessionLocal, engine
from common.models import User
from common.observability import instrument_fastapi
from common.redis_utils import create_session, delete_session, get_user_id_from_session
from seed import seed_demo_users

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

    # Schema — idempotent, safe on every restart
    Base.metadata.create_all(bind=engine)

    # Connect to Redis early so we fail fast if it is unavailable
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis.ping()

    # Seed demo data — raises RuntimeError if the DB never becomes reachable
    try:
        seed_demo_users()
    except RuntimeError as exc:
        log.critical("Startup aborted: %s", exc)
        raise

    log.info("auth-service ready")
    yield

    await redis.aclose()
    log.info("auth-service shut down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Auth Service", lifespan=lifespan)
instrument_fastapi(app, "auth-service")
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


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterReq(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Username may only contain letters, digits, hyphens, and underscores"
            )
        return v.lower()


class LoginReq(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/register", status_code=201)
async def register(body: RegisterReq, db: Session = Depends(get_db)):
    """Register a new user."""
    exists = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Username already taken")

    u = User(username=body.username, password_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    db.refresh(u)
    log.info("register: new user id=%d username=%r", u.id, u.username)
    return {"id": u.id, "username": u.username, "balance": u.balance}


@app.post("/login")
async def login(
    body: LoginReq,
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
):
    """Authenticate and create a session."""
    u = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")

    sid = await create_session(r, u.id)
    log.info("login: user id=%d username=%r", u.id, u.username)
    return {"session": sid, "username": u.username, "balance": u.balance}


@app.post("/logout", status_code=204)
async def logout(
    x_session: str | None = Header(default=None),
    r: Redis = Depends(get_redis),
):
    """Invalidate the current session token."""
    if x_session:
        await delete_session(r, x_session)


@app.get("/health")
async def health_check(db: Session = Depends(get_db), r: Redis = Depends(get_redis)):
    """Liveness / readiness probe."""
    try:
        await r.ping()
        db.execute(select(1))
    except Exception as exc:
        raise HTTPException(503, detail=f"Health check failed: {exc}")
    return {"status": "healthy", "service": "auth-service"}
