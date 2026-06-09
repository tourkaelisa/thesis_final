"""Αυθεντικοποίηση: hashing κωδικών, JWT tokens και σχήματα (Pydantic) χρήστη."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pydantic import BaseModel, Field

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS


class UserRegistration(BaseModel):
    firstName: str = Field(min_length=2)
    lastName: str = Field(min_length=2)
    email: str
    phone: str | None = None
    password: str = Field(min_length=8)
    terms: bool


class UserLogin(BaseModel):
    email: str
    password: str = Field(min_length=8)


def create_token(user_id: int, role: int) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return f"{salt}${password_hash}"


def verify_password(password: str, stored_password: str) -> bool:
    try:
        salt, stored_hash = stored_password.split("$", 1)
    except ValueError:
        return False

    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return secrets.compare_digest(password_hash, stored_hash)
