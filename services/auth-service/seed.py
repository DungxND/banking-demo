import sys
import time
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from common.db import SessionLocal
from common.models import User
from common.auth import hash_password

DEMO_USERS = [
    {"username": "alice", "password": "password123"},
    {"username": "bob", "password": "password123"},
    {"username": "charlie", "password": "password123"},
]


def seed_demo_users():
    for attempt in range(10):
        try:
            db = SessionLocal()
            try:
                for u in DEMO_USERS:
                    exists = db.execute(
                        select(User).where(User.username == u["username"])
                    ).scalar_one_or_none()
                    if exists:
                        print(f"[seed] user already exists: {u['username']}", file=sys.stderr)
                        continue
                    db.add(User(
                        username=u["username"],
                        password_hash=hash_password(u["password"]),
                    ))
                    print(f"[seed] created user: {u['username']}", file=sys.stderr)
                db.commit()
                print("[seed] done", file=sys.stderr)
            finally:
                db.close()
            return
        except OperationalError as e:
            print(f"[seed] DB not ready (attempt {attempt + 1}/10): {e}", file=sys.stderr)
            time.sleep(2)
    print("[seed] gave up after 10 attempts", file=sys.stderr)
