"""Αυθεντικοποίηση: hashing κωδικών, JWT tokens και σχήματα (Pydantic) χρήστη."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pydantic import BaseModel, Field, field_validator

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS

# Πρακτικό regex εγκυρότητας email: local-part, @, domain με τουλάχιστον ένα label και TLD ≥ 2 γραμμάτων.
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$")


def normalize_email(value: str) -> str:
    """Κανονικοποιεί (trim + πεζά) και επικυρώνει το email· αλλιώς ρίχνει ValueError."""
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_REGEX.match(email):
        raise ValueError("Invalid email.")
    return email


class UserRegistration(BaseModel):
    firstName: str = Field(min_length=2)
    lastName: str = Field(min_length=2)
    email: str
    phone: str | None = None
    password: str = Field(min_length=8)
    terms: bool

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        phone = value.strip()
        digits = re.sub(r"\D", "", phone)
        if not re.fullmatch(r"[0-9+\s-]+", phone) or not (10 <= len(digits) <= 15):
            raise ValueError("Invalid phone.")
        return phone


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
