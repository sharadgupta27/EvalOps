"""Password hashing, JWTs and API-key generation."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
import jwt

from app.errors import Unauthorized

API_KEY_PREFIX = "eo_"
_JWT_ALG = "HS256"


@dataclass(frozen=True)
class Principal:
    """Who is calling. API keys carry a project scope; users do not."""

    kind: Literal["user", "api_key"]
    user_id: int
    project_id: int | None = None
    api_key_id: int | None = None

    @property
    def is_api_key(self) -> bool:
        return self.kind == "api_key"


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_jwt(user_id: int, secret: str, expire_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, secret, algorithm=_JWT_ALG)


def decode_jwt(token: str, secret: str) -> int:
    try:
        payload = jwt.decode(
            token, secret, algorithms=[_JWT_ALG], options={"require": ["exp", "sub"]}
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError) as e:
        raise Unauthorized("invalid or expired token") from e


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    # Keys are 256-bit random strings, so a fast unsalted hash is enough: there is
    # nothing to brute-force, and lookups by hash stay O(1).
    return hashlib.sha256(key.encode()).hexdigest()
