from sqlalchemy.exc import IntegrityError

from common.db import SessionLocal
from common.models import User
from common.auth import hash_password

DEMO_USERS = [
    {"username": "alice", "password": "password123"},
    {"username": "bob", "password": "password123"},
    {"username": "charlie", "password": "password123"},
]


def seed_demo_users():
    db = SessionLocal()
    try:
        for u in DEMO_USERS:
            try:
                db.begin_nested()
                db.add(User(
                    username=u["username"],
                    password_hash=hash_password(u["password"]),
                ))
                db.flush()
            except IntegrityError:
                pass  # already exists, savepoint auto-rolled back
        db.commit()
    finally:
        db.close()
