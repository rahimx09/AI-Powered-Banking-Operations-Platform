from pwdlib import PasswordHash

import os
from dotenv import load_dotenv

from datetime import datetime, timedelta, timezone


from jose import jwt
from jose.exceptions import JWTError
from typing import Any, Optional

from fastapi.security import OAuth2PasswordBearer

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

load_dotenv()


def hash_password(password: str) -> str:
    """ Convert a plaintext password into a secure hash"""
    return password_hash.hash(password)


def verify_password(
        plain_password: str,
        hashed_password: str
) -> bool:
    """Check whether a password matches its stored hash"""
    return password_hash.verify(plain_password, hashed_password)


JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)


def create_access_token(
    subject: str, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT for a subject."""
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT."""
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
