# Chemora

A chemistry education and research platform.

Chemora is a monorepo containing a production-grade chemistry engine, a backend API, and frontend applications (mobile, web, admin).

## Repository Structure

```
Chemora/
├── apps/
│   ├── mobile/          # React Native / Expo mobile app (reserved)
│   ├── web/             # Web application (reserved)
│   └── admin/           # Administrative CMS/dashboard (reserved)
│
├── backend/             # FastAPI + PostgreSQL backend API (M19 ✅ + M20 ✅)
│
├── packages/
│   └── chemengine/      # Standalone chemistry engine (Python package)
│       ├── src/chemengine/
│       ├── tests/
│       ├── benchmarks/
│       ├── scripts/
│       ├── docs/
│       └── pyproject.toml
│
├── infrastructure/      # CI/CD, Docker, deployment (reserved)
│
├── TODO.md
├── PROJECT_STATUS.md
├── gantt.html
├── LICENSE
├── CONTRIBUTING.md
├── DEVELOPMENT_RULES.md
└── .gitignore
```

## Architecture

The dependency direction is:

```
Frontend (mobile/web/admin)
        ↓
    Backend API
        ↓
    ChemEngine
```

ChemEngine is a standalone Python package. It does not depend on the backend or frontend. The backend consumes ChemEngine. The frontend consumes the backend.

## Backend (M19 Foundation ✅ + M20 Authentication ✅)

The FastAPI backend lives in [`backend/`](backend/). Milestone M20 adds secure
Google Sign-In authentication:

- **Google ID-token verification** server-side (`google-auth`): signature,
  issuer, audience, expiration, and subject.
- **User identity** keyed by Google `sub` (email is not the identity key).
- **Server-managed sessions** with expiration, inactivity timeout, renewal, and
  revocation, delivered via a secure `HttpOnly` cookie.
- **Endpoints**: `POST /api/v1/auth/google`, `GET /api/v1/auth/me`,
  `POST /api/v1/auth/logout`.
- **40 passing backend tests** (no live Google/PostgreSQL required).

Full setup, configuration, security model, and the frontend integration
contract are documented in [`backend/README.md`](backend/README.md).

## ChemEngine

ChemEngine is a production-grade chemistry engine built with the **Molecular Graph as the single source of truth**. It is independently installable, testable, and reusable.

- **Package name**: `chemengine`
- **Import**: `import chemengine`
- **Tests**: 1635 passed, 1 skipped
- **Coverage**: 80%

See [`packages/chemengine/`](packages/chemengine/) for full documentation.

## Quick Start

### Install ChemEngine

```bash
cd packages/chemengine
pip install -e ".[dev]"
```

### Run Tests

```bash
# From the monorepo root
pytest packages/chemengine/tests/ -v

# Or from the package directory
cd packages/chemengine
pytest tests/ -v
```

## License

MIT
