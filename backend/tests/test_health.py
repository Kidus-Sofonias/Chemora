"""Production diagnostics endpoints (M31).

Covers the liveness (``/health``) and readiness (``/health/ready``) probes:
- readiness reflects real database connectivity and schema presence
- a degraded database yields HTTP 503 with ``not-ready`` status
- diagnostics expose configuration *state* but never secret *values*
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_health_liveness(api_client: AsyncClient) -> None:
    """``/health`` is a static liveness signal and always reports healthy."""
    response = await api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body


@pytest.mark.asyncio
async def test_readiness_reports_database_and_provider_state(api_client: AsyncClient) -> None:
    """With a migrated test database, readiness is 200 with structured checks."""
    response = await api_client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    checks = body["checks"]
    assert checks["database"] == "ok"
    # Provider name is configuration state (safe); the key itself must never appear.
    assert checks["ai_provider"] in ("mock", "openai", "anthropic")
    assert isinstance(checks["ai_provider_configured"], bool)


@pytest.mark.asyncio
async def test_readiness_never_exposes_secret_values(api_client: AsyncClient) -> None:
    """No credential material may leak through the readiness diagnostics."""
    response = await api_client.get("/health/ready")
    raw = response.text
    for fragment in ("sk-", "AI_API_KEY", "AI_ANTHROPIC_API_KEY", "postgresql", "sqlite"):
        assert fragment not in raw, f"readiness leaked sensitive fragment: {fragment}"


class _BrokenSession:
    """Session stand-in whose queries always fail (failure injection)."""

    async def execute(self, *args: object, **kwargs: object) -> object:
        """Raise immediately, simulating a database outage."""
        raise RuntimeError("simulated database outage")

    def connection(self) -> object:
        """Raise immediately for schema inspection calls."""
        raise RuntimeError("simulated database outage")


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_is_down(
    api_client: AsyncClient,
) -> None:
    """A database outage must degrade readiness to 503, not 200."""
    from app.db.session import get_db_session
    from app.main import app

    async def _broken_db() -> AsyncGenerator[AsyncSession, None]:
        yield cast(AsyncSession, _BrokenSession())

    saved = app.dependency_overrides.get(get_db_session)
    app.dependency_overrides[get_db_session] = _broken_db
    try:
        response = await api_client.get("/health/ready")
    finally:
        if saved is not None:
            app.dependency_overrides[get_db_session] = saved
        else:
            app.dependency_overrides.pop(get_db_session, None)
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not-ready"
    assert body["checks"]["database"] == "unavailable"
    # The simulated exception text must not be echoed to the caller.
    assert "simulated database outage" not in response.text
