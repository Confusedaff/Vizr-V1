"""FastAPI dependencies for authentication. Two flavors:
  - get_current_user: required auth, raises 401 if missing/invalid
  - get_current_user_optional: allows anonymous access where a route
    should work for both logged-in and anonymous callers (none of the
    job-creation routes use this — jobs always require a user — but kept
    available for e.g. a future public read-only gallery endpoint)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.security import InvalidTokenError, decode_access_token
from apps.api.database import get_db
from apps.api.models.db import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User | None:
    if token is None:
        return None
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user
