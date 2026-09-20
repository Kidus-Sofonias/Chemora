"""Chemora Backend API — FastAPI Application.

Main application entry point. Configures CORS, routing,
and middleware for the Chemora API.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Manages startup and shutdown events.
    """
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Chemora — Chemistry Education & Exploration Platform API",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # Register API routers
    from app.api.v1.admin import router as admin_router
    from app.api.v1.auth import router as auth_router
    from app.api.v1.chemistry import router as chemistry_router
    from app.api.v1.elements import router as elements_router
    from app.api.v1.learning import router as learning_router
    from app.api.v1.tutor import router as tutor_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(chemistry_router, prefix="/api/v1")
    app.include_router(elements_router, prefix="/api/v1")
    app.include_router(learning_router, prefix="/api/v1")
    app.include_router(tutor_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")


    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy", "version": settings.APP_VERSION}

    @app.get("/health/ready")
    async def readiness_check(
        db_session: AsyncSession = Depends(get_db_session),
    ) -> JSONResponse:
        """Readiness probe: can this process serve real traffic right now.

        Unlike ``/health`` (liveness), this verifies the runtime dependencies
        the application needs: database connectivity, schema presence, and
        AI provider configuration state.

        Diagnostics intentionally report *state*, never values: no credential
        strings, no connection URLs, and no raw exception text are returned.
        Returns 200 when ready, 503 when a required dependency is degraded.
        """
        from sqlalchemy import inspect as sa_inspect

        checks: dict[str, str | bool] = {}
        ready = True

        # Database connectivity + schema presence (migrations applied).
        # Uses the same session dependency as the API routes, so this probes
        # exactly the database path that serves real requests.
        try:
            await db_session.execute(text("SELECT 1"))

            def _schema_ready(sync_conn: Connection) -> bool:
                """Return whether the core schema exists (runs in a worker)."""
                return bool(sa_inspect(sync_conn).has_table("users"))

            conn = await db_session.connection()
            schema_ok = await conn.run_sync(_schema_ready)
            checks["database"] = "ok" if schema_ok else "schema-missing"
            if checks["database"] != "ok":
                ready = False
        except Exception:
            checks["database"] = "unavailable"
            ready = False

        # AI provider configuration state — booleans only, never secret values.
        provider = settings.AI_PROVIDER
        checks["ai_provider"] = provider
        checks["ai_provider_configured"] = provider in ("mock", "openai", "anthropic") and (
            provider == "mock" or bool(settings.AI_API_KEY) or bool(settings.AI_ANTHROPIC_API_KEY)
        )

        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not-ready", "checks": checks},
        )

    return app


app = create_app()
