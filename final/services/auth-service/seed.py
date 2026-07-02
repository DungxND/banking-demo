"""
Seed script — runs once at container startup before uvicorn.
Idempotent: skips rows whose phone already exists.
Users are read from SEED_USERS env var (JSON array) so they can be
overridden at deploy time without rebuilding the image.

Default seeds (override via SEED_USERS env var):
  alice  / 0900000001 / Password1!  — regular user
  bob    / 0900000002 / Password1!  — regular user
  admin  / 0900000099 / Admin1234!  — admin (is_admin=true)

NOTE: this is a one-shot sync CLI script; it creates its own sync engine
so it does not depend on the async engine in common/db.py.
"""
import json
import os
import secrets
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from common.db import Base, DATABASE_URL
from common.models import User
from common.auth import hash_password

DEFAULT_SEEDS = [
    {"phone": "0900000001", "username": "alice", "password": "Password1!", "balance": 500000, "is_admin": False},
    {"phone": "0900000002", "username": "bob",   "password": "Password1!", "balance": 300000, "is_admin": False},
    {"phone": "0900000099", "username": "admin", "password": "Admin1234!", "balance": 999999, "is_admin": True},
]

# Build a sync URL from the async one (strip _async suffix from driver name)
_sync_url = (DATABASE_URL or "").replace("postgresql+psycopg_async://", "postgresql+psycopg://")
_sync_engine = create_engine(_sync_url, future=True, pool_pre_ping=True)
_SyncSession = sessionmaker(bind=_sync_engine, autoflush=False, autocommit=False)


def _gen_account_number(db) -> str | None:
    for _ in range(20):
        candidate = "".join(str(secrets.randbelow(10)) for _ in range(12))
        if not db.execute(select(User).where(User.account_number == candidate)).scalar_one_or_none():
            return candidate
    return None


def run_seed() -> None:
    # Ensure tables exist (safe no-op if already created by main.py)
    Base.metadata.create_all(bind=_sync_engine)

    raw = os.getenv("SEED_USERS")
    seeds = json.loads(raw) if raw else DEFAULT_SEEDS

    db = _SyncSession()
    try:
        for s in seeds:
            phone = s["phone"]
            if db.execute(select(User).where(User.phone == phone)).scalar_one_or_none():
                print(f"[seed] SKIP  {s['username']} ({phone}) — already exists", flush=True)
                continue
            acct = _gen_account_number(db)
            if not acct:
                print(f"[seed] ERROR cannot generate account number for {phone}", flush=True)
                sys.exit(1)
            u = User(
                phone=phone,
                username=s["username"],
                password_hash=hash_password(s["password"]),
                account_number=acct,
                balance=s.get("balance", 100000),
                is_admin=s.get("is_admin", False),
            )
            db.add(u)
            db.commit()
            db.refresh(u)
            role = "admin" if u.is_admin else "user"
            print(f"[seed] SEED  {u.username} ({role}) | phone={u.phone} | acct={u.account_number}", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
