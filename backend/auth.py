"""
Password hashing and token-based sessions.

Passwords are hashed with bcrypt, which is deliberately slow and salts every
digest, so two users with the same password get different hashes and a stolen
database cannot be reversed by lookup table. The plain password is never
stored, logged, or returned.

Sessions are stateless JWTs: the server signs a token containing the user id
and an expiry, and verifies that signature on each request instead of keeping
server-side session state. That is what lets the API scale horizontally and
survive the restarts a free hosting tier hands out.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_session
from models import User

ALGORITHM = "HS256"
TOKEN_DAYS = 14
# bcrypt truncates at 72 bytes; rejecting longer input is clearer than silently
# ignoring the tail, which would make two different passwords equivalent.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def secret_key() -> str:
    """
    The signing key, from the environment.

    A random fallback would silently invalidate every token on restart, and a
    hardcoded default would mean anyone reading this public repository could
    mint tokens for any account. So in production, absence is a hard error.
    """
    key = os.getenv("JWT_SECRET", "").strip()
    if key:
        return key
    if os.getenv("RADAR_ENV", "").lower() == "production":
        raise RuntimeError("JWT_SECRET must be set in production.")
    return "dev-only-insecure-key-do-not-deploy"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_credentials(email: str, password: str) -> tuple[str, str]:
    """Normalise and check a signup pair, raising 400 with a readable reason."""
    email = (email or "").strip().lower()
    password = password or ""

    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="That doesn't look like a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(status_code=400, detail="Password is too long (72 bytes maximum).")
    return email, password


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(days=TOKEN_DAYS)}
    return jwt.encode(payload, secret_key(), algorithm=ALGORITHM)


def _user_id_from_token(token: str) -> int:
    try:
        payload = jwt.decode(token, secret_key(), algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your session expired. Please sign in again.")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Not signed in.")


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Not signed in.")
    return token.strip()


def get_db() -> Session:
    """FastAPI dependency yielding a session that always closes."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency that resolves the signed-in user or rejects the request."""
    user = db.get(User, _user_id_from_token(_bearer_token(request)))
    if not user:
        # The account was deleted after the token was issued.
        raise HTTPException(status_code=401, detail="Not signed in.")
    return user


def find_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


# --------------------------------------------------------------------------
# Login throttling
# --------------------------------------------------------------------------
# Without this, an attacker can try passwords against a known email as fast as
# the network allows. bcrypt already makes each guess slow, but slow is not the
# same as limited.
#
# The counter is a plain dict, which is honest about its limits: it is per
# process, so a second instance would not share it, and it resets on restart.
# For a single free-tier container that is the right amount of machinery. Redis
# is the answer once there is more than one process, not before.
MAX_ATTEMPTS = 8
LOCKOUT_SECONDS = 900  # 15 minutes

_attempts: dict[str, list[float]] = {}


def _recent(key: str, now: float) -> list[float]:
    kept = [t for t in _attempts.get(key, []) if now - t < LOCKOUT_SECONDS]
    if kept:
        _attempts[key] = kept
    else:
        _attempts.pop(key, None)
    return kept


def check_not_locked_out(key: str) -> None:
    """Raise 429 if this identifier has failed too many times recently."""
    now = time.monotonic()
    if len(_recent(key, now)) >= MAX_ATTEMPTS:
        wait = int((LOCKOUT_SECONDS - (now - min(_recent(key, now)))) / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed sign-in attempts. Try again in about {wait} minutes.",
        )


def record_failure(key: str) -> None:
    now = time.monotonic()
    _attempts.setdefault(key, []).append(now)
    _recent(key, now)


def clear_failures(key: str) -> None:
    """A correct password wipes the slate, so a typo costs nothing later."""
    _attempts.pop(key, None)


def public_user(user: User) -> dict:
    """The safe subset of a user to send to the client — never the hash."""
    return {"id": user.id, "email": user.email, "name": user.name}
