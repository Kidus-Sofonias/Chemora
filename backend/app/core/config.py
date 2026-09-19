"""Application configuration loaded from environment variables.

All secrets come from environment configuration. Never commit `.env`.
Ensure `.env.example` contains safe placeholder values only.
"""

from __future__ import annotations

import secrets
from enum import Enum
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Secrets are never logged or included in error messages.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "Chemora"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/chemora"
    # Synchronous URL for Alembic migrations
    DATABASE_URL_SYNC: str = "postgresql://localhost:5432/chemora"

    # --- Google Authentication ---
    GOOGLE_CLIENT_ID: str = ""
    # Retained for operator/documentation reference only. google-auth's
    # ``verify_oauth2_token`` hard-checks the issuer internally, so verification
    # (``app/services/google_auth.py``) never consults this list.
    GOOGLE_ALLOWED_ISSUERS: list[str] = [
        "https://accounts.google.com",
        "accounts.google.com",
    ]

    # --- Session Configuration ---
    SESSION_SECRET: str = ""
    SESSION_DURATION_MINUTES: int = 60 * 24 * 7  # 7 days
    SESSION_INACTIVITY_TIMEOUT_MINUTES: int = 60 * 24 * 30  # 30 days
    SESSION_RENEWAL_WINDOW_MINUTES: int = 60 * 24  # 24 hours before expiry

    # --- Cookie Configuration ---
    COOKIE_SECURE: bool = False  # Set True in production
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str = ""
    COOKIE_NAME: str = "chemora_session"

    # --- CORS ---
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # --- Content administration (M26) ---
    # Verified emails listed here are granted the admin flag at login time.
    # Provisioning is configuration-driven — no admin email is hardcoded in
    # application logic, and the flag is never auto-revoked here.
    ADMIN_EMAILS: list[str] = []

    # --- AI (M29: AI Chemistry Tutor) ---
    # AI is opt-in. When AI_PROVIDER is "mock" (the default) the tutor uses the
    # in-process MockAIProvider so the system is fully testable without any
    # external LLM or API key. Set to "openai" for an OpenAI-compatible HTTP
    # API or "anthropic" for the Anthropic Messages API.
    AI_PROVIDER: str = "mock"
    # OpenAI-compatible API base (override for providers like Ollama / proxies).
    AI_API_BASE: str = "https://api.openai.com/v1"
    AI_API_KEY: str = ""  # Server-side only. Never exposed to the client.
    AI_MODEL: str = "gpt-4o-mini"
    # Anthropic Messages API (used when AI_PROVIDER="anthropic").
    AI_ANTHROPIC_BASE: str = "https://api.anthropic.com"
    AI_ANTHROPIC_API_KEY: str = ""  # Server-side only. Never exposed to the client.
    AI_ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    # Cost/abuse controls (enforced per request).
    AI_TIMEOUT_SECONDS: float = 30.0
    # Approximate character budget for the assembled prompt (≈4 chars/token);
    # assembled inputs are trimmed to stay inside it.
    AI_MAX_INPUT_TOKENS: int = 4000
    AI_MAX_OUTPUT_TOKENS: int = 512
    AI_MAX_TOOL_ITERATIONS: int = 5
    # Optional per-user request cap (empty = unset / no fixed limit).
    AI_RATE_LIMIT_PER_MINUTE: int = 20

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == Environment.PRODUCTION

    def model_post_init(self, _context: Any) -> None:  # noqa: ANN401
        """Post-init validation and defaults."""
        if not self.SESSION_SECRET:
            if self.is_production:
                raise ValueError(
                    "SESSION_SECRET must be explicitly set in production. "
                    "A randomly generated secret would invalidate sessions "
                    "on restart and break multi-worker deployments."
                )
            self.SESSION_SECRET = secrets.token_hex(32)
        if self.is_production:
            self.COOKIE_SECURE = True
            if self.COOKIE_SAMESITE == "none":
                self.COOKIE_SECURE = True


settings = Settings()
