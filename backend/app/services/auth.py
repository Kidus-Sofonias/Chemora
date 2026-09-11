"""Authentication service.

Handles the complete authentication flow:
1. Google token verification
2. User lookup/creation
3. Session creation
4. Session validation
5. Session revocation (logout)

The service depends on abstractions (GoogleTokenVerifier, database sessions)
to enable testing without external dependencies.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import Session, User
from app.services.google_auth import (
    GoogleTokenVerifierProtocol,
    GoogleUserInfo,
)

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    """Return a datetime normalized to UTC, treating naive values as UTC.

    PostgreSQL returns timezone-aware datetimes while SQLite returns naive
    ones. This helper makes comparisons consistent regardless of backend.

    Args:
        dt: The datetime to normalize.

    Returns:
        The same instant expressed as a timezone-aware UTC datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AuthService:
    """Authentication service for Chemora.

    Coordinates Google token verification, user identity management,
    and session lifecycle.
    """

    def __init__(
        self,
        db: AsyncSession,
        google_verifier: GoogleTokenVerifierProtocol | None = None,
    ) -> None:
        """Initialize the auth service.

        Args:
            db: Async database session.
            google_verifier: Token verifier instance. Uses default if None.
        """
        self._db = db
        self._google_verifier = google_verifier

    def _get_verifier(self) -> GoogleTokenVerifierProtocol:
        """Get the Google token verifier, lazily initialized."""
        if self._google_verifier is None:
            from app.services.google_auth import get_google_verifier

            self._google_verifier = get_google_verifier()
        return self._google_verifier

    async def authenticate_with_google(self, credential: str) -> tuple[User, Session]:
        """Authenticate a user with a Google ID token.

        Flow:
        1. Verify Google token cryptographically
        2. Find existing user by Google subject
        3. Create user if new
        4. Update user metadata from verified token
        5. Create Chemora session
        6. Return authenticated user and session

        Args:
            credential: The Google ID token / credential.

        Returns:
            Tuple of (User, Session) for the authenticated user.

        Raises:
            GoogleTokenError: If token verification fails.
        """
        # Step 1: Verify Google token
        verifier = self._get_verifier()
        google_user = verifier.verify(credential)

        # Step 2-4: Find or create user, update metadata
        user = await self._find_or_create_user(google_user)

        # Step 5: Create session
        session = await self._create_session(user)

        logger.info(
            "User authenticated via Google",
            extra={"user_id": str(user.id)},
        )

        return user, session

    async def _find_or_create_user(self, google_user: GoogleUserInfo) -> User:
        """Find existing user by Google subject or create new one.

        Uses Google `sub` as the identity key, NOT email.
        Duplicate Google identities are prevented by the unique constraint.

        Args:
            google_user: Verified Google user information.

        Returns:
            The existing or newly created User.
        """
        # Look up by Google subject (the stable identity key)
        result = await self._db.execute(
            select(User).where(User.google_subject == google_user.sub)
        )
        user = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if user is not None:
            # Returning user — update metadata from verified token
            user.email = google_user.email
            user.display_name = google_user.name or user.display_name
            user.avatar_url = google_user.picture or user.avatar_url
            user.last_login_at = now
            logger.info(
                "Returning user login",
                extra={"user_id": str(user.id)},
            )
        else:
            # New user — create account
            user = User(
                google_subject=google_user.sub,
                email=google_user.email,
                display_name=google_user.name,
                avatar_url=google_user.picture,
                last_login_at=now,
            )
            self._db.add(user)
            await self._db.flush()  # Get the generated ID
            logger.info(
                "New user created",
                extra={"user_id": str(user.id)},
            )

        return user

    async def _create_session(self, user: User) -> Session:
        """Create a new authentication session for a user.

        Session lifetime:
        - Absolute expiry: SESSION_DURATION_MINUTES from now
        - No inactivity check at creation (handled at validation time)

        Args:
            user: The user to create a session for.

        Returns:
            The newly created Session.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=settings.SESSION_DURATION_MINUTES)

        session = Session(
            user_id=user.id,
            expires_at=expires_at,
            last_activity_at=now,
        )
        self._db.add(session)
        await self._db.flush()

        logger.info(
            "Session created",
            extra={"session_id": str(session.id), "user_id": str(user.id)},
        )

        return session

    async def validate_session(self, session_id: uuid.UUID) -> User | None:
        """Validate a session and return the authenticated user.

        Checks:
        1. Session exists
        2. Session is not revoked
        3. Session is not expired (absolute expiry)
        4. Session is not expired (inactivity timeout)

        Also updates last_activity_at for active sessions.

        Args:
            session_id: The session UUID to validate.

        Returns:
            The authenticated User if session is valid, None otherwise.
        """
        result = await self._db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()

        if session is None:
            return None

        now = datetime.now(timezone.utc)

        # Normalize stored datetimes. PostgreSQL returns timezone-aware values,
        # but SQLite (used in tests) returns naive values; treat naive as UTC.
        expires_at = _ensure_utc(session.expires_at)
        last_activity_at = _ensure_utc(session.last_activity_at)

        # Check revoked
        if session.revoked_at is not None:
            logger.debug(
                "Session is revoked",
                extra={"session_id": str(session_id)},
            )
            return None

        # Check absolute expiry
        if expires_at <= now:
            logger.debug(
                "Session has expired",
                extra={"session_id": str(session_id)},
            )
            return None

        # Check inactivity timeout
        inactivity_cutoff = now - timedelta(
            minutes=settings.SESSION_INACTIVITY_TIMEOUT_MINUTES
        )
        if last_activity_at <= inactivity_cutoff:
            logger.debug(
                "Session expired due to inactivity",
                extra={"session_id": str(session_id)},
            )
            return None

        # Check if session is in renewal window and extend
        renewal_cutoff = expires_at - timedelta(
            minutes=settings.SESSION_RENEWAL_WINDOW_MINUTES
        )
        if now >= renewal_cutoff:
            # Extend session expiry
            new_expires = now + timedelta(minutes=settings.SESSION_DURATION_MINUTES)
            session.expires_at = new_expires
            logger.debug(
                "Session renewed",
                extra={"session_id": str(session_id)},
            )

        # Update last activity
        session.last_activity_at = now

        # Load and return the user
        user_result = await self._db.execute(
            select(User).where(User.id == session.user_id)
        )
        user = user_result.scalar_one_or_none()

        return user

    async def revoke_session(self, session_id: uuid.UUID) -> bool:
        """Revoke (invalidate) a session.

        This is the server-side logout mechanism. The session is marked as
        revoked and will no longer be accepted for authentication.

        Args:
            session_id: The session UUID to revoke.

        Returns:
            True if session was revoked, False if not found.
        """
        result = await self._db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()

        if session is None:
            return False

        session.revoked_at = datetime.now(timezone.utc)

        logger.info(
            "Session revoked",
            extra={"session_id": str(session_id), "user_id": str(session.user_id)},
        )

        return True

    async def revoke_all_user_sessions(self, user_id: uuid.UUID) -> int:
        """Revoke all active sessions for a user.

        Useful for security incidents or password changes.

        Args:
            user_id: The user whose sessions to revoke.

        Returns:
            Number of sessions revoked.
        """
        now = datetime.now(timezone.utc)
        result = await self._db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.revoked_at.is_(None),
            )
        )
        sessions = result.scalars().all()

        count = 0
        for session in sessions:
            session.revoked_at = now
            count += 1

        if count > 0:
            logger.info(
                "All user sessions revoked",
                extra={"user_id": str(user_id), "count": count},
            )

        return count
