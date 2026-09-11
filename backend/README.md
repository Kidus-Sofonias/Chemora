# Chemora Backend

FastAPI backend for the Chemora chemistry education & exploration platform.

```text
Frontend / Mobile / Admin
          ↓
     FastAPI Backend   ← you are here
          ↓
       ChemEngine
          ↓
  Deterministic Chemistry
```

The backend depends on ChemEngine. ChemEngine never depends on the backend,
database, authentication, or AI.

> **Milestone status:** Backend Foundation (M19) ✅ and Authentication (M20) ✅
> are complete. This document covers the authentication system built in M20.

---

## Table of Contents

- [Architecture](#architecture)
- [Authentication Architecture](#authentication-architecture)
- [Google Configuration](#google-configuration)
- [Local Development Setup](#local-development-setup)
- [Environment Variables](#environment-variables)
- [Session Model & Expiration Policy](#session-model--expiration-policy)
- [API Endpoints](#api-endpoints)
- [Security Considerations](#security-considerations)
- [Logout Behavior](#logout-behavior)
- [Frontend Integration Expectations](#frontend-integration-expectations)
- [Testing, Linting, Type Checking](#testing-linting-type-checking)
- [Database Migrations](#database-migrations)

---

## Architecture

- **FastAPI** application with async SQLAlchemy 2.0 and asyncpg.
- **PostgreSQL** as the database. Alembic manages migrations.
- API versioning under `/api/v1/`.
- Configuration via **environment variables** (pydantic-settings). No secrets
  are committed; see `.env.example` for safe placeholders.
- The backend is a **clean modular monolith** suitable for Chemora's beta
  (~500 users) target. No microservices, Redis, or Celery are used.

### Project layout

```text
backend/
  app/
    api/           # Routes & FastAPI dependencies
    core/          # Settings (environment configuration)
    db/            # Engine, sessions, declarative base
    models/        # SQLAlchemy ORM models (users, sessions)
    services/      # AuthService, GoogleTokenVerifier
  tests/           # pytest suite (async, aiosqlite in-memory)
  pyproject.toml
  .env.example
  README.md
alembic/           # Alembic migrations (repository root)
alembic.ini
```

---

## Authentication Architecture

Chemora uses **Google Sign-In / Google Identity Services** as its identity
provider. Google proves identity during authentication; Chemora then
establishes its own server-managed session that the client sends on
subsequent requests (no repeated Google token submission).

```text
Client
  ↓ Google Sign-In
Google ID Token
  ↓ POST /api/v1/auth/google
Chemora Backend
  ↓ GoogleTokenVerifier — cryptographic, server-side verification
  ↓ AuthService — find/create user by Google `sub`
  ↓ SessionService — create Chemora session
  ↓ Secure HttpOnly session cookie
```

The verification boundary is the `GoogleTokenVerifier` abstraction
(`app/services/google_auth.py`). It uses the maintained
[`google-auth`](https://googleapis.dev/python/google-auth/) library and:

- Verifies the **signature** against Google's public keys.
- Validates the **issuer** (allows `https://accounts.google.com` and
  `accounts.google.com`).
- Validates the **audience** (must equal our `GOOGLE_CLIENT_ID`).
- Validates **expiration** (`exp`).
- Validates the **subject** (`sub`).
- Performs temporal checks per the token's issued-at/expiry claims.

The backend **never trusts** user-supplied email, name, avatar, or subject ID
unless they come from the verified token. `GoogleUserInfo` is built only from
claims extracted after successful verification.

### User identity

- The Google `sub` is the **stable external identity key**, stored in
  `users.google_subject` with a **unique constraint**.
- Email is **not** the primary identity key (emails can change; Google `sub`
  is stable). Email is stored only as verified profile data.
- Duplicate Google identities are prevented by the database constraint and the
  find-by-subject lookup.

---

## Google Configuration

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. **APIs & Services → Credentials → Create Credentials → OAuth client ID.**
   Categorize it as a **Web application**.
3. Add your frontend origins (`http://localhost:3000`, `http://localhost:5173`,
   and your production domain) to **Authorized JavaScript origins**.
4. Copy the **Client ID** (a string ending in `.apps.googleusercontent.com`)
   into `GOOGLE_CLIENT_ID`.

No Google **client secret** is required for ID-token-only (Google Identity
Services) sign-in. Google *access/refresh tokens* are **not** requested,
stored, or used by this milestone, so no `client_secret` is configured.

The Google frontend library (GIS) returns an ID token in the `credential`
field; the client submits it to `POST /api/v1/auth/google`.

---

## Local Development Setup

Requires Python 3.10+ and PostgreSQL.

```bash
cd backend
python -m venv .venv            # or use the repo venv
pip install -e ".[dev]"

# Create your env file from the safe example
cp .env.example .env
# Edit .env — set GOOGLE_CLIENT_ID, DATABASE_URL, DATABASE_URL_SYNC, SESSION_SECRET

# Run migrations
alembic upgrade head

# Run the server
uvicorn app.main:app --reload
```

Health check: `GET /health` → `{"status": "healthy", ...}`.

> **Local vs production differences:**
> - Locally `COOKIE_SECURE=false` and CORS allows `localhost` origins so the
>   cookie works over plain `http`. In production, **set `COOKIE_SECURE=true`**
>   and configure CORS to your real origins only.
> - The app forces `COOKIE_SECURE=true` when `ENVIRONMENT=production`.

---

## Environment Variables

All secrets come from environment configuration. **Never commit `.env`.**
`.env.example` contains safe placeholders only.

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_NAME` / `APP_VERSION` | Chemora / 0.1.0 | App metadata |
| `ENVIRONMENT` | development | `development`/`staging`/`production` |
| `DEBUG` | false | Enables `/docs` and engine SQL echo |
| `DATABASE_URL` | (asyncpg URL) | Async DB connection |
| `DATABASE_URL_SYNC` | (postgresql URL) | Sync DB connection for Alembic |
| `GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID (audience) |
| `GOOGLE_ALLOWED_ISSUERS` | accounts.google.com | Allowed token issuers |
| `SESSION_SECRET` | *(auto-generated)* | Stable secret for multi-instance deployments |
| `SESSION_DURATION_MINUTES` | 10080 (7 days) | Absolute session lifetime |
| `SESSION_INACTIVITY_TIMEOUT_MINUTES` | 43200 (30 days) | Max inactivity before re-auth required |
| `SESSION_RENEWAL_WINDOW_MINUTES` | 1440 (24 h) | Renew expiry when approaching it |
| `COOKIE_SECURE` | false | Send cookie only over HTTPS (set true in prod) |
| `COOKIE_SAMESITE` | lax | `lax` (default and recommended) |
| `COOKIE_DOMAIN` | *(empty)* | Cookie domain (set in production) |
| `COOKIE_NAME` | chemora_session | Session cookie name |
| `CORS_ALLOW_ORIGINS` | localhost:3000/5173 | Allowed CORS origins |
| `CORS_ALLOW_CREDENTIALS` | true | Must be true when using cookies |

> `SESSION_SECRET` is auto-generated at runtime if left empty. Set a fixed,
> secure value for production so all instances share session behavior.

---

## Session Model & Expiration Policy

Chemora's product policy: a user should **not** be forced to re-authenticate
during normal use, but **inactive sessions must eventually expire**.

| Concept | Config | Behavior |
|---------|--------|----------|
| Absolute lifetime | `SESSION_DURATION_MINUTES` (7 days) | Session hard-expires after this, regardless of activity. |
| Inactivity timeout | `SESSION_INACTIVITY_TIMEOUT_MINUTES` (30 days) | If no request for this long, re-authentication is required. |
| Renewal window | `SESSION_RENEWAL_WINDOW_MINUTES` (24 h) | When a valid session is used within 24 h of its expiry, its absolute expiry is extended by the session duration. |

Mechanics:

- `GET /api/v1/auth/me` (via the reusable dependency) validates the session on
  every protected request: checked against **revocation**, **absolute expiry**,
  and **inactivity**, and `last_activity_at` is bumped.
- A session within the renewal window is extended (sliding absolute expiry) so
  an active user is not logged out mid-use — the renewal is bounded: a session
  is never made valid again once its absolute expiry or inactivity timeout has
  passed.
- **No permanent sessions.** Every session has an absolute `expires_at`.

The session is stored server-side in the `sessions` table. The client holds
only an opaque UUID cookie; the server controls revocation and validity.

---

## API Endpoints

All under `/api/v1`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/google` | — | Verify Google ID token, find/create user, establish session. |
| `GET` | `/auth/me` | ✅ | Return the current authenticated user. |
| `POST` | `/auth/logout` | — | Revoke the current server-side session and clear the cookie. |
| `GET` | `/health` | — | Health check. |

### `POST /auth/google`

Request body:

```json
{ "credential": "<google id token from GIS>" }
```

On success returns the user profile plus confirmation and sets the `chemora_session`
cookie:

```json
{
  "user": {
    "id": "<chemora internal user uuid>",
    "email": "user@example.com",
    "display_name": "Ada",
    "avatar_url": "https://...",
    "created_at": "...",
    "last_login_at": "..."
  },
  "session_id": "<chemora session uuid>"
}
```

On invalid credential → `401` with a **generic** message (no token/GC key details).

### `GET /auth/me`

Requires a valid session cookie. Returns the `user` profile object. Returns
`401` if the session is missing, invalid, revoked, or expired. Does **not**
expose the Google subject or any session secret.

### `POST /auth/logout`

Revokes the server-side session (sets `revoked_at`), so the session can never
be used again even if the cookie is replayed. Clears the session cookie. Idempotent.

---

## Security Considerations

- **Verification is server-side and cryptographic.** The Google ID token is
  verified with `google-auth` (signature, issuer, audience, expiry, subject).
- **No client-supplied identity.** Users cannot set their own `google_subject`,
  `email`, or verified identity; profile data is taken only from the verified token.
- **Cookie safety:** the session cookie is `HttpOnly`, `SameSite=lax`, and
  `Secure` (in production). `SameSite` and `Secure` are environment-configurable.
- **CSRF:** `SameSite=lax` mitigates cross-site request forgery for cookie-based
  requests. `SameSite=none` forces `Secure=true`. `allow_origins` never uses `"*"`
  with credentials; they are configured via environment.
- **Sensitive logging is avoided.** Google tokens, session tokens, cookies, and
  secrets are never logged. Error responses are generic and do not reveal
  internal diagnostics (failures are logged server-side with safe codes only).
- **Brute-force / replay:** sessions are opaque random UUIDs stored server-side
  with revocation; revoking/expiring them bounds replay windows. Logout
  invalidates server state.
- **Secret management:** all secrets come from environment variables; `.env`
  is git-ignored; `.env.example` holds placeholders only. No secrets appear in
  code, tests, README, or Docker config.
- **Wrong audience / issuer / expired tokens** all yield the same generic
  `401`, so an attacker cannot probe which check failed.

---

## Logout Behavior

Logout is **server-revocation**, not just client-side cookie deletion:

1. The endpoint reads the session id from the cookie.
2. `AuthService.revoke_session()` sets `revoked_at` on the server-side session.
3. The cookie is cleared.
4. Even if the old cookie is replayed later, `GET /me` returns `401` because
   the session is revoked.

If the session id is malformed, the endpoint still clears the cookie (best
effort) and returns `204`.

---

## Frontend Integration Expectations

This milestone deliberately implements **no frontend UI**; the contract below
is for later frontend/mobile work (planned around M21+). The frontend will:

1. Present Google Sign-In via Google Identity Services, obtaining an ID token
   in the `credential` field.
2. `POST /api/v1/auth/google` with `{ "credential": "<token>" }`.
3. Store the returned `chemora_session` cookie (browsers handle it
   automatically via `SameSite=Lax`; mobile clients must send the cookie or
   adopt the documented session-id flow).
4. For every authenticated request, send the session cookie (browser
   automatic; mobile must attach it). Keep `credentials: "include"` /
   `withCredentials: true` for cross-origin requests so the cookie is sent.
5. Show the user via `GET /api/v1/auth/me`.
6. Log out via `POST /api/v1/auth/logout`.

The `session_id` in the login response is informational and returned for
mobile clients; the canonical mechanism is the `chemora_session` cookie. Do
**not** store the Google ID token locally for reuse — Chemora uses its own
session for ongoing authentication.

---

## Testing, Linting, Type Checking

```bash
cd backend

# Tests (no PostgreSQL/Google required — aiosqlite in-memory + mock verifier)
python -m pytest

# Type checking (strict)
python -m mypy app

# Linting
python -m ruff check app tests
```

The test suite uses an in-memory aiosqlite database and a mock
`GoogleTokenVerifier` so it never depends on live Google accounts or
PostgreSQL. The app's `get_db_session` and `get_google_verifier` are overridden
in the `api_client` fixture to exercise the real endpoints end-to-end.

---

## Database Migrations

Migrations live in `alembic/` (repository root). To create/upgrade/downgrade:

```bash
alembic upgrade head      # apply all migrations
alembic downgrade -1      # roll back the most recent migration
```

The `001_initial_auth_tables` migration creates the `users` and `sessions`
tables with the required constraints and indexes (unique `google_subject`,
FK with `ON DELETE CASCADE`, activity/expiry indexes). Run `alembic upgrade
head` against PostgreSQL to apply.
