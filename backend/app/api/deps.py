"""FastAPI authentication dependencies.

Provides a reusable `get_current_user` dependency that:
1. Extracts the session token from the request
2. Validates the session
3. Returns the authenticated user

Future endpoints can use:
    Depends(get_current_user)
without duplicating authentication logic.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import AuthService


async def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthService:
    """Dependency that provides an AuthService instance.

    Args:
        db: Async database session.

    Returns:
        Configured AuthService.
    """
    return AuthService(db=db)


async def get_current_user(
    session_token: Annotated[str | None, Cookie(alias="chemora_session")] = None,
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,  # type: ignore[assignment]
) -> User:
    """Dependency that returns the currently authenticated user.

    Extracts the session token from the cookie, validates it,
    and returns the User. Raises 401 if not authenticated.

    Usage in endpoints:
        @router.get("/protected")
        async def protected(user: Annotated[User, Depends(get_current_user)]):
            return {"user_id": user.id}

    Args:
        session_token: The session token from the cookie.
        auth_service: The auth service for session validation.

    Returns:
        The authenticated User.

    Raises:
        HTTPException: 401 if session is missing, invalid, or expired.
    """
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        session_id = uuid.UUID(session_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await auth_service.validate_session(session_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
