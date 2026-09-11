"""Test configuration and shared fixtures.

Uses aiosqlite for in-memory testing — no PostgreSQL required for tests.
Provides mocks for Google token verification.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.services.auth import AuthService
from app.services.google_auth import GoogleTokenError, GoogleUserInfo

# --- Database Fixtures ---


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite async engine for testing."""
    # StaticPool keeps a single shared connection so all sessions (including
    # those opened for separate API requests) see the same in-memory database.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# --- Mock Google Verifier ---


class MockGoogleTokenVerifier:
    """Mock Google token verifier for testing.

    Simulates Google token verification without calling external services.
    """

    def __init__(self) -> None:
        """Initialize with empty token map."""
        self._tokens: dict[str, GoogleUserInfo] = {}
        self._valid_sub = "google_sub_123456"

    def register_token(
        self,
        token: str,
        sub: str | None = None,
        email: str = "test@example.com",
        name: str = "Test User",
        picture: str | None = None,
    ) -> GoogleUserInfo:
        """Register a token for verification.

        Args:
            token: The token string to register.
            sub: Google subject ID. Auto-generated if None.
            email: User email.
            name: User display name.
            picture: Avatar URL.

        Returns:
            The GoogleUserInfo that will be returned for this token.
        """
        user_info = GoogleUserInfo(
            sub=sub or f"sub_{uuid.uuid4().hex[:12]}",
            email=email,
            email_verified=True,
            name=name,
            picture=picture,
            locale="en",
        )
        self._tokens[token] = user_info
        return user_info

    def verify(self, token: str) -> GoogleUserInfo:
        """Verify a registered token.

        Args:
            token: The token to verify.

        Returns:
            The registered GoogleUserInfo.

        Raises:
            GoogleTokenError: If token is not registered.
        """
        if token not in self._tokens:
            raise GoogleTokenError("Invalid authentication credential")
        return self._tokens[token]


@pytest.fixture
def mock_google_verifier() -> MockGoogleTokenVerifier:
    """Provide a fresh mock Google token verifier."""
    return MockGoogleTokenVerifier()


@pytest_asyncio.fixture
async def auth_service(
    db_session: AsyncSession,
    mock_google_verifier: MockGoogleTokenVerifier,
) -> AuthService:
    """Provide an AuthService with mocked Google verification."""
    return AuthService(db=db_session, google_verifier=mock_google_verifier)


# --- Test Data Fixtures ---


@pytest.fixture
def sample_google_token() -> str:
    """Provide a sample Google token for testing."""
    return "sample_google_id_token_abc123"


@pytest.fixture
def sample_user_info() -> GoogleUserInfo:
    """Provide sample verified Google user info."""
    return GoogleUserInfo(
        sub="google_sub_123456",
        email="user@example.com",
        email_verified=True,
        name="Test User",
        picture="https://example.com/avatar.jpg",
        locale="en",
    )


# --- API Client Fixture ---


@pytest_asyncio.fixture
async def api_client(
    db_engine: AsyncEngine,
    mock_google_verifier: MockGoogleTokenVerifier,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an API client with the app's auth overridden for testing.

    Overrides:
    - ``get_db_session`` → in-memory SQLite session (shared connection)
    - ``get_google_verifier`` → the mock Google verifier

    This lets the real FastAPI endpoints run without PostgreSQL or live
    Google services.
    """
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        """Yield a session bound to the shared in-memory test database."""
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db_session] = override_get_db
    monkeypatch.setattr(
        "app.services.google_auth.get_google_verifier",
        lambda: mock_google_verifier,
    )

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db_session, None)
