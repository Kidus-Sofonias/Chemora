"""Authentication API endpoints.

Endpoints:
    POST /api/v1/auth/google  — Google Sign-In
    POST /api/v1/auth/logout  — Logout (revoke session)
    GET  /api/v1/auth/me      — Get current user
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_service, get_current_user
from app.core.config import settings
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import AuthService
from app.services.google_auth import GoogleTokenError

router = APIRouter(prefix="/auth", tags=["authentication"])


# --- Request / Response Models ---


class GoogleLoginRequest(BaseModel):
    """Request body for Google authentication."""

    credential: str


class UserResponse(BaseModel):
    """User information returned to the client.

    Excludes sensitive internal fields.
    """

    id: str
    email: str
    display_name: str | None
    avatar_url: str | None
    created_at: str
    last_login_at: str | None

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Authentication response with session information."""

    user: UserResponse
    session_id: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str


# --- Helpers ---


def _user_to_response(user: User) -> UserResponse:
    """Convert a User model to a UserResponse.

    Args:
        user: The database User model.

    Returns:
        Safe UserResponse for the client.
    """
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        created_at=user.created_at.isoformat() if user.created_at else "",
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )


# --- Endpoints ---


@router.post(
    "/google",
    response_model=SessionResponse,
    summary="Authenticate with Google",
    description="Verify a Google ID token and create a Chemora session.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid Google credential"},
    },
)
async def google_login(
    request: GoogleLoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SessionResponse:
    """Authenticate a user via Google Sign-In.

    Accepts a Google ID token, verifies it server-side, finds or creates
    the user, and establishes a Chemora session via secure cookie.

    The Google token is verified cryptographically:
    - Signature checked against Google's public keys
    - Issuer validated
    - Audience (client ID) validated
    - Expiration checked
    - Subject extracted

    Args:
        request: Google login request with credential.
        response: FastAPI response for setting cookies.
        db: Database session.

    Returns:
        User information and session confirmation.

    Raises:
        401: If Google credential is invalid.
    """
    auth_service = AuthService(db=db)

    try:
        user, session = await auth_service.authenticate_with_google(request.credential)
    except GoogleTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Set secure session cookie
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=str(session.id),
        max_age=settings.SESSION_DURATION_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN or None,
        path="/",
    )

    return SessionResponse(
        user=_user_to_response(user),
        session_id=str(session.id),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Revoke the current session and clear the session cookie.",
)
async def logout(
    response: Response,
    session_token: Annotated[str | None, Cookie(alias="chemora_session")] = None,
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,  # type: ignore[assignment]
) -> None:
    """Log out the current user.

    Revokes the server-side session and clears the session cookie.
    The session cannot be used again after logout.

    Args:
        response: FastAPI response for clearing cookies.
        session_token: Session token from cookie.
        auth_service: Auth service for session revocation.
    """
    if session_token:
        try:
            import uuid

            session_id = uuid.UUID(session_token)
            await auth_service.revoke_session(session_id)
        except (ValueError, Exception):
            # Best effort — always clear cookie even if revocation fails
            pass

    # Clear the session cookie
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN or None,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Return the currently authenticated user.",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Get the currently authenticated user.

    Requires a valid session cookie. Returns user profile information.

    Args:
        user: Authenticated user from dependency.

    Returns:
        User profile information.
    """
    return _user_to_response(user)
