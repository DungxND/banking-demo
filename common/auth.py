from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

pwd = PasswordHash((BcryptHasher(),))

def hash_password(pw: str) -> str:
    return pwd.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return pwd.verify(pw, hashed)
