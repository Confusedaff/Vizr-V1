"""
Password hashing (bcrypt directly — not passlib, which has a known
incompatibility with bcrypt>=4.1's stricter backend that breaks passlib's
internal version-detection and 72-byte self-test hash; see the bcrypt
changelog around `__about__` removal) and JWT creation/verification
(python-jose).

Security notes for anyone hardening this beyond MVP scope:
  - JWT_SECRET_KEY MUST be overridden via environment variable in any
    real deployment; the default here is dev-only and intentionally
    obvious so it's never mistaken for a real secret.
  - Access tokens are short-lived (30 min default) with no refresh-token
    flow yet — re-login is required after expiry. A refresh-token
    rotation scheme is a reasonable next hardening step but adds
    meaningful complexity (rotation, revocation lists) that's out of
    scope for this pass.
  - bcrypt has a hard 72-byte input limit; passwords are truncated
    defensively (not silently — the signup endpoint rejects anything
    over 72 bytes with a clear 422 rather than truncating and letting a
    user's real password quietly not be what they typed).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(Exception):
    pass


def hash_password(plain_password: str) -> str:
    encoded = plain_password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes (bcrypt limit)."
        )
    hashed = bcrypt.hashpw(encoded, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen for hashes we generated) — fail
        # closed rather than raising a 500 into the login flow.
        return False


def create_access_token(*, subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


class InvalidTokenError(Exception):
    pass


def decode_access_token(token: str) -> str:
    """Returns the subject (user id) or raises InvalidTokenError."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise InvalidTokenError(str(e)) from e
    subject = payload.get("sub")
    if subject is None:
        raise InvalidTokenError("Token missing subject claim")
    return subject
