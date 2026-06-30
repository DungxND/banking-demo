"""
Seed demo users into the database on service startup.

Configuration (all optional, via environment variables):
  SEED_USERS      – comma-separated "username:password" pairs
                    default: alice:password123,bob:password123,charlie:password123
  SEED_BALANCE    – initial balance for every seeded user (integer cents)
                    default: 100000
  SEED_MAX_TRIES  – maximum DB-connection attempts before giving up
                    default: 10
  SEED_RETRY_BASE – base seconds for exponential back-off between attempts
                    default: 1
"""

import logging
import os
import time
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from common.db import SessionLocal
from common.models import User
from common.auth import hash_password

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _parse_demo_users() -> list[dict]:
    """Parse SEED_USERS env var into a list of {username, password} dicts."""
    raw = os.getenv(
        "SEED_USERS",
        "alice:password123,bob:password123,charlie:password123",
    )
    users = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            log.warning("seed: skipping malformed SEED_USERS entry %r (expected 'user:pass')", entry)
            continue
        username, _, password = entry.partition(":")
        users.append({"username": username.strip(), "password": password.strip()})
    return users


SEED_BALANCE: int = int(os.getenv("SEED_BALANCE", "100000"))
SEED_MAX_TRIES: int = int(os.getenv("SEED_MAX_TRIES", "10"))
SEED_RETRY_BASE: float = float(os.getenv("SEED_RETRY_BASE", "1"))


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def seed_demo_users() -> None:
    """Upsert demo users, retrying on transient DB errors.

    Each user is committed individually so a partial run is still useful.
    Raises ``RuntimeError`` if the DB never becomes reachable.
    """
    demo_users = _parse_demo_users()
    if not demo_users:
        log.info("seed: no users configured — skipping")
        return

    for attempt in range(1, SEED_MAX_TRIES + 1):
        try:
            _run_seed(demo_users)
            return
        except OperationalError as exc:
            wait = SEED_RETRY_BASE * (2 ** (attempt - 1))   # exponential back-off
            log.warning(
                "seed: DB not ready (attempt %d/%d) — retrying in %.1fs: %s",
                attempt, SEED_MAX_TRIES, wait, exc,
            )
            time.sleep(wait)

    raise RuntimeError(f"seed: DB unreachable after {SEED_MAX_TRIES} attempts — aborting startup")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_seed(demo_users: list[dict]) -> None:
    """Execute one full seed pass inside a fresh session."""
    db = SessionLocal()
    try:
        for u in demo_users:
            existing = db.execute(
                select(User).where(User.username == u["username"])
            ).scalar_one_or_none()

            if existing is not None:
                log.debug("seed: user already exists — skipping: %s", u["username"])
                continue

            db.add(User(
                username=u["username"],
                password_hash=hash_password(u["password"]),
                balance=SEED_BALANCE,
            ))
            db.commit()          # commit per-user so partial runs are durable
            log.info("seed: created user %r with balance %d", u["username"], SEED_BALANCE)

        log.info("seed: finished — %d user(s) processed", len(demo_users))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
