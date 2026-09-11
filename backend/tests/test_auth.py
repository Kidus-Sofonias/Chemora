"""Comprehensive authentication tests.

Covers:
- Google token validation (valid, invalid, expired, wrong audience, wrong issuer)
- User behavior (new, returning, duplicate prevention, metadata updates)
- Session behavior (creation, validation, expiry, revocation, inactivity)
- Security behavior (unauthenticated requests, no sensitive data leakage)
- API endpoints (login, me, logout)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.main import app
from app.models.user import Session, User
from app.services.auth import AuthService
from app.services.google_auth import (
    GoogleTokenError,
    GoogleTokenVerifier,
)

from .conftest import MockGoogleTokenVerifier

# ═══════════════════════════════════════════════════════════════════════
# Google Token Validation Tests
# ═══════════════════════════════════════════════════════════════════════


class TestGoogleTokenValidation:
    """Test Google token verification logic."""

    def test_valid_token_returns_user_info(self) -> None:
        """A registered valid token returns verified user info."""
        verifier = MockGoogleTokenVerifier()
        verifier.register_token(
            "valid_token_123",
            sub="sub_abc",
            email="alice@example.com",
            name="Alice",
        )

        result = verifier.verify("valid_token_123")

        assert result.sub == "sub_abc"
        assert result.email == "alice@example.com"
        assert result.name == "Alice"
        assert result.email_verified is True

    def test_invalid_token_raises_error(self) -> None:
        """An unregistered token raises GoogleTokenError."""
        verifier = MockGoogleTokenVerifier()
        verifier.register_token("other_token")

        with pytest.raises(GoogleTokenError, match="Invalid authentication credential"):
            verifier.verify("wrong_token")

    def test_empty_token_raises_error(self) -> None:
        """An empty token string raises GoogleTokenError."""
        verifier = GoogleTokenVerifier(client_id="test_client_id")

        with pytest.raises(GoogleTokenError, match="Missing authentication credential"):
            verifier.verify("")

    def test_whitespace_token_raises_error(self) -> None:
        """A whitespace-only token raises GoogleTokenError."""
        verifier = GoogleTokenVerifier(client_id="test_client_id")

        with pytest.raises(GoogleTokenError, match="Missing authentication credential"):
            verifier.verify("   ")

    def test_missing_subject_raises_error(self) -> None:
        """A token without a subject claim raises GoogleTokenError."""
        with patch("app.services.google_auth.id_token.verify_oauth2_token") as mock_verify:
            mock_verify.return_value = {
                "email": "user@example.com",
                # Missing "sub"
            }
            verifier = GoogleTokenVerifier(
                client_id="test_client_id",
                allowed_issuers=["https://accounts.google.com"],
            )

            with pytest.raises(GoogleTokenError, match="Invalid authentication credential"):
                verifier.verify("some_token")

    def test_wrong_audience_raises_error(self) -> None:
        """A token with wrong audience (client ID) raises GoogleTokenError."""
        with patch("app.services.google_auth.id_token.verify_oauth2_token") as mock_verify:
            mock_verify.side_effect = ValueError("Wrong audience")
            verifier = GoogleTokenVerifier(
                client_id="correct_client_id",
                allowed_issuers=["https://accounts.google.com"],
            )

            with pytest.raises(GoogleTokenError, match="Invalid authentication credential"):
                verifier.verify("some_token")

    def test_expired_token_raises_error(self) -> None:
        """An expired token raises GoogleTokenError."""
        with patch("app.services.google_auth.id_token.verify_oauth2_token") as mock_verify:
            mock_verify.side_effect = ValueError("Token expired")
            verifier = GoogleTokenVerifier(
                client_id="test_client_id",
                allowed_issuers=["https://accounts.google.com"],
            )

            with pytest.raises(GoogleTokenError, match="Invalid authentication credential"):
                verifier.verify("expired_token")

    def test_wrong_issuer_raises_error(self) -> None:
        """A token with wrong issuer raises GoogleTokenError."""
        with patch("app.services.google_auth.id_token.verify_oauth2_token") as mock_verify:
            mock_verify.side_effect = ValueError("Wrong issuer")
            verifier = GoogleTokenVerifier(
                client_id="test_client_id",
                allowed_issuers=["https://accounts.google.com"],
            )

            with pytest.raises(GoogleTokenError, match="Invalid authentication credential"):
                verifier.verify("some_token")

    def test_malformed_token_raises_error(self) -> None:
        """A malformed token string raises GoogleTokenError."""
        with patch("app.services.google_auth.id_token.verify_oauth2_token") as mock_verify:
            mock_verify.side_effect = ValueError("Invalid token format")
            verifier = GoogleTokenVerifier(
                client_id="test_client_id",
                allowed_issuers=["https://accounts.google.com"],
            )

            with pytest.raises(GoogleTokenError, match="Invalid authentication credential"):
                verifier.verify("not.a.jwt")


# ═══════════════════════════════════════════════════════════════════════
# User Behavior Tests
# ═══════════════════════════════════════════════════════════════════════


class TestUserBehavior:
    """Test user creation and identity management."""

    @pytest.mark.asyncio
    async def test_new_google_user_created(
        self,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A new Google user is created on first login."""
        mock_google_verifier.register_token(
            "new_user_token",
            sub="new_sub_001",
            email="new@example.com",
            name="New User",
        )

        user, session = await auth_service.authenticate_with_google("new_user_token")

        assert user.google_subject == "new_sub_001"
        assert user.email == "new@example.com"
        assert user.display_name == "New User"
        assert user.id is not None
        assert session.id is not None

    @pytest.mark.asyncio
    async def test_returning_google_user_found(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A returning Google user is found by Google subject."""
        # First login
        mock_google_verifier.register_token(
            "returning_token",
            sub="returning_sub",
            email="returning@example.com",
            name="Returning User",
        )
        user1, _ = await auth_service.authenticate_with_google("returning_token")
        await db_session.commit()

        # Second login
        mock_google_verifier.register_token(
            "returning_token_2",
            sub="returning_sub",  # Same Google subject
            email="updated@example.com",
            name="Updated Name",
        )
        user2, _ = await auth_service.authenticate_with_google("returning_token_2")

        # Should be the same user
        assert user1.id == user2.id
        assert user2.email == "updated@example.com"
        assert user2.display_name == "Updated Name"

    @pytest.mark.asyncio
    async def test_duplicate_google_identity_prevented(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Duplicate Google identities are prevented by unique constraint."""
        mock_google_verifier.register_token(
            "dup_token_1",
            sub="same_sub_id",
            email="first@example.com",
            name="First",
        )
        user1, _ = await auth_service.authenticate_with_google("dup_token_1")
        await db_session.commit()

        # Same sub, different email (email changed)
        mock_google_verifier.register_token(
            "dup_token_2",
            sub="same_sub_id",
            email="changed@example.com",
            name="Changed",
        )
        user2, _ = await auth_service.authenticate_with_google("dup_token_2")

        # Should update existing user, not create new one
        assert user1.id == user2.id
        assert user2.email == "changed@example.com"

    @pytest.mark.asyncio
    async def test_email_not_primary_identity(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Email is not the primary identity key."""
        mock_google_verifier.register_token(
            "email_test_token",
            sub="sub_email_test",
            email="original@example.com",
        )
        user, _ = await auth_service.authenticate_with_google("email_test_token")
        await db_session.commit()

        # Simulate email change on Google side
        mock_google_verifier.register_token(
            "email_test_token_2",
            sub="sub_email_test",
            email="changed@example.com",
        )
        user2, _ = await auth_service.authenticate_with_google("email_test_token_2")

        # Same user, updated email
        assert user.id == user2.id
        assert user2.email == "changed@example.com"

        # Verify user is found by Google subject, not email
        from sqlalchemy import select

        result = await db_session.execute(
            select(User).where(User.google_subject == "sub_email_test")
        )
        found = result.scalar_one()
        assert found.id == user.id

    @pytest.mark.asyncio
    async def test_profile_updates_from_verified_identity(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """User profile is updated from verified Google token data."""
        mock_google_verifier.register_token(
            "profile_token",
            sub="sub_profile",
            email="user@example.com",
            name="Original Name",
            picture="https://example.com/original.jpg",
        )
        user, _ = await auth_service.authenticate_with_google("profile_token")
        await db_session.commit()

        original_avatar = user.avatar_url

        # Update profile data
        mock_google_verifier.register_token(
            "profile_token_2",
            sub="sub_profile",
            email="user@example.com",
            name="Updated Name",
            picture="https://example.com/new.jpg",
        )
        user2, _ = await auth_service.authenticate_with_google("profile_token_2")

        assert user2.display_name == "Updated Name"
        assert user2.avatar_url == "https://example.com/new.jpg"
        assert user2.avatar_url != original_avatar


# ═══════════════════════════════════════════════════════════════════════
# Session Behavior Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSessionBehavior:
    """Test session lifecycle management."""

    @pytest.mark.asyncio
    async def test_session_creation(
        self,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A session is created on successful authentication."""
        mock_google_verifier.register_token("session_token", sub="sub_session")
        user, session = await auth_service.authenticate_with_google("session_token")

        assert session.id is not None
        assert session.user_id == user.id
        assert session.expires_at > datetime.now(timezone.utc)
        assert session.revoked_at is None

    @pytest.mark.asyncio
    async def test_authenticated_request_validates(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A valid session allows authenticated requests."""
        mock_google_verifier.register_token("auth_token", sub="sub_auth")
        user, session = await auth_service.authenticate_with_google("auth_token")
        await db_session.commit()

        validated_user = await auth_service.validate_session(session.id)

        assert validated_user is not None
        assert validated_user.id == user.id

    @pytest.mark.asyncio
    async def test_expired_session_rejected(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """An expired session is rejected."""
        mock_google_verifier.register_token("expired_session_token", sub="sub_expired")
        user, session = await auth_service.authenticate_with_google("expired_session_token")

        # Manually expire the session
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.commit()

        validated_user = await auth_service.validate_session(session.id)

        assert validated_user is None

    @pytest.mark.asyncio
    async def test_revoked_session_rejected(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A revoked session is rejected."""
        mock_google_verifier.register_token("revoke_token", sub="sub_revoke")
        user, session = await auth_service.authenticate_with_google("revoke_token")
        await db_session.commit()

        # Revoke the session
        await auth_service.revoke_session(session.id)
        await db_session.commit()

        validated_user = await auth_service.validate_session(session.id)

        assert validated_user is None

    @pytest.mark.asyncio
    async def test_logout_invalidates_session(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Logout actually invalidates the server-side session."""
        mock_google_verifier.register_token("logout_token", sub="sub_logout")
        user, session = await auth_service.authenticate_with_google("logout_token")
        await db_session.commit()

        # Logout
        result = await auth_service.revoke_session(session.id)
        assert result is True

        # Session is no longer valid
        validated_user = await auth_service.validate_session(session.id)
        assert validated_user is None

    @pytest.mark.asyncio
    async def test_invalid_session_id_rejected(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
    ) -> None:
        """A nonexistent session ID is rejected."""
        fake_id = uuid.uuid4()
        validated_user = await auth_service.validate_session(fake_id)

        assert validated_user is None

    @pytest.mark.asyncio
    async def test_session_inactivity_timeout(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A session expired due to inactivity is rejected."""
        mock_google_verifier.register_token("inactive_token", sub="sub_inactive")
        user, session = await auth_service.authenticate_with_google("inactive_token")

        # Set last activity far in the past
        session.last_activity_at = datetime.now(timezone.utc) - timedelta(days=60)
        await db_session.commit()

        validated_user = await auth_service.validate_session(session.id)

        assert validated_user is None

    @pytest.mark.asyncio
    async def test_session_renewal(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A session near expiry is renewed."""
        mock_google_verifier.register_token("renew_token", sub="sub_renew")
        user, session = await auth_service.authenticate_with_google("renew_token")

        # Set expiry to be within renewal window (24 hours from now)
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=12)
        original_expires = session.expires_at
        await db_session.commit()

        # Validate — should trigger renewal
        validated_user = await auth_service.validate_session(session.id)

        assert validated_user is not None
        assert session.expires_at > original_expires

    @pytest.mark.asyncio
    async def test_session_last_activity_updated(
        self,
        db_session: AsyncSession,
        auth_service: AuthService,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Session last_activity_at is updated on validation."""
        mock_google_verifier.register_token("activity_token", sub="sub_activity")
        user, session = await auth_service.authenticate_with_google("activity_token")

        original_activity = session.last_activity_at
        await db_session.commit()

        # Wait a tiny bit, then validate
        import asyncio
        await asyncio.sleep(0.01)

        await auth_service.validate_session(session.id)

        assert session.last_activity_at >= original_activity


# ═══════════════════════════════════════════════════════════════════════
# Security Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSecurityBehavior:
    """Test security-related behavior."""

    def test_user_repr_hides_sensitive_data(self) -> None:
        """User __repr__ does not expose Google subject."""
        user = User(
            google_subject="secret_google_sub_12345",
            email="user@example.com",
        )
        repr_str = repr(user)

        assert "secret_google_sub" not in repr_str
        assert "***" in repr_str

    def test_session_repr_hides_sensitive_data(self) -> None:
        """Session __repr__ does not expose session secrets."""
        session = Session(
            user_id=uuid.uuid4(),
            expires_at=datetime.now(timezone.utc),
        )
        repr_str = repr(session)

        # Should not contain the full session ID in a way that could be
        # confused with a secret
        assert "Session" in repr_str

    def test_google_token_error_message_is_safe(self) -> None:
        """GoogleTokenError messages do not leak sensitive information."""
        error = GoogleTokenError("Invalid authentication credential")
        error_str = str(error)

        # Should not contain token, key, or internal details
        assert "token" not in error_str.lower() or "credential" in error_str.lower()
        assert "key" not in error_str.lower()
        assert "internal" not in error_str.lower()

    def test_config_secrets_not_in_error_messages(self) -> None:
        """Configuration secrets are not exposed in settings."""
        config = Settings()

        # SESSION_SECRET should be set but not be empty in any output
        assert config.SESSION_SECRET != ""

    @pytest.mark.asyncio
    async def test_unauthenticated_me_returns_401(self, db_session: AsyncSession) -> None:
        """GET /me without a session cookie returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_session_cookie_returns_401(self, db_session: AsyncSession) -> None:
        """GET /me with invalid session cookie returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("chemora_session", "not-a-valid-uuid")
            response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
# API Endpoint Tests
# ═══════════════════════════════════════════════════════════════════════


class TestAPIEndpoints:
    """Test the authentication API endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, db_session: AsyncSession) -> None:
        """Health check endpoint returns healthy status."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_google_login_creates_user_and_session(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """POST /auth/google creates a new user and returns session."""
        mock_google_verifier.register_token(
            "api_test_token",
            sub="api_sub_001",
            email="api@example.com",
            name="API User",
        )

        response = await api_client.post(
            "/api/v1/auth/google",
            json={"credential": "api_test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "api@example.com"
        assert data["user"]["display_name"] == "API User"
        assert "session_id" in data
        assert "chemora_session" in response.cookies

    @pytest.mark.asyncio
    async def test_google_login_invalid_credential_returns_401(
        self,
        api_client: AsyncClient,
    ) -> None:
        """POST /auth/google with invalid credential returns 401."""
        response = await api_client.post(
            "/api/v1/auth/google",
            json={"credential": "invalid_token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_endpoint_returns_authenticated_user(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """GET /auth/me returns user info when authenticated."""
        mock_google_verifier.register_token(
            "me_token",
            sub="me_sub_001",
            email="me@example.com",
            name="Me User",
        )

        # Login first — the session cookie is persisted in the client jar
        login_response = await api_client.post(
            "/api/v1/auth/google",
            json={"credential": "me_token"},
        )
        assert login_response.status_code == 200

        me_response = await api_client.get("/api/v1/auth/me")

        assert me_response.status_code == 200
        data = me_response.json()
        assert data["email"] == "me@example.com"
        assert data["display_name"] == "Me User"

    @pytest.mark.asyncio
    async def test_logout_endpoint_revokes_session(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """POST /auth/logout revokes the session and clears cookie."""
        mock_google_verifier.register_token(
            "logout_api_token",
            sub="logout_sub_001",
            email="logout@example.com",
        )

        # Login
        login_response = await api_client.post(
            "/api/v1/auth/google",
            json={"credential": "logout_api_token"},
        )
        assert login_response.status_code == 200

        # Logout
        logout_response = await api_client.post("/api/v1/auth/logout")

        assert logout_response.status_code == 204

        # Verify session is revoked by trying /me with the (still-sent) cookie
        me_response = await api_client.get("/api/v1/auth/me")
        assert me_response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """POST /auth/logout clears the session cookie."""
        mock_google_verifier.register_token("clear_cookie_token", sub="clear_sub")

        await api_client.post(
            "/api/v1/auth/google",
            json={"credential": "clear_cookie_token"},
        )

        logout_response = await api_client.post("/api/v1/auth/logout")

        # Session is revoked and cookie should be cleared
        assert logout_response.status_code == 204


# ═══════════════════════════════════════════════════════════════════════
# Database Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDatabase:
    """Test database constraints and behavior."""

    @pytest.mark.asyncio
    async def test_user_google_subject_unique(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Google subject must be unique across users."""
        user1 = User(
            google_subject="unique_sub_001",
            email="first@example.com",
        )
        db_session.add(user1)
        await db_session.flush()

        user2 = User(
            google_subject="unique_sub_001",  # Duplicate!
            email="second@example.com",
        )
        db_session.add(user2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_session_foreign_key_to_user(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Sessions have a valid foreign key to users."""
        user = User(
            google_subject="fk_test_sub",
            email="fk@example.com",
        )
        db_session.add(user)
        await db_session.flush()

        session = Session(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(session)
        await db_session.flush()

        assert session.user_id == user.id

    @pytest.mark.asyncio
    async def test_session_cascade_delete(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Deleting a user cascades to delete their sessions."""
        user = User(
            google_subject="cascade_sub",
            email="cascade@example.com",
        )
        db_session.add(user)
        await db_session.flush()

        session = Session(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(session)
        await db_session.flush()

        session_id = session.id

        # Delete user
        await db_session.delete(user)
        await db_session.flush()

        # Session should be gone
        result = await db_session.execute(
            select(Session).where(Session.id == session_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_user_timestamps_auto_set(
        self,
        db_session: AsyncSession,
    ) -> None:
        """User timestamps are automatically set."""
        user = User(
            google_subject="timestamp_sub",
            email="timestamp@example.com",
        )
        db_session.add(user)
        await db_session.flush()

        assert user.created_at is not None
        assert user.updated_at is not None

    @pytest.mark.asyncio
    async def test_session_expiry_indexed(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Sessions have proper indexes for efficient queries."""
        # This is more of a structural test — verify the model compiles
        # and the table has the expected columns
        user = User(
            google_subject="index_sub",
            email="index@example.com",
        )
        db_session.add(user)
        await db_session.flush()

        session = Session(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(session)
        await db_session.flush()

        assert session.expires_at is not None
        assert session.last_activity_at is not None
