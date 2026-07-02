import os
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

# Configurable rounds — increase for production, lower for test speed.
# bcrypt default is 12; 10 is faster for high-throughput demo.
_rounds = int(os.getenv("BCRYPT_ROUNDS", "10"))
pwd = PasswordHash((BcryptHasher(rounds=_rounds),))


def hash_password(pw: str) -> str:
    return pwd.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    return pwd.verify(pw, hashed)
