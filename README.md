# Chemora

A chemistry education and research platform.

Chemora is a monorepo containing a production-grade chemistry engine, a backend API, and frontend applications (mobile, web, admin).

## Repository Structure

```
Chemora/
├── apps/
│   ├── web/             # React + Vite web client (M21 ✅) — Google Sign-In integration
│   ├── mobile/          # React Native / Expo mobile app (reserved)
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
- **Tests**: 1984 passed, 4 skipped (all documented)
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

## Learning Experience (M24-M43)

The Chemistry Learning Core (M24) provides catalog-driven lessons; M25 adds practice
and server-graded questions; M28 expands the curriculum; M41 refines the AI tutor; M42
adds gas-laws and chemical-nomenclature lessons with learning objectives. The **M43
Student Dashboard** (`GET /api/v1/learning/dashboard`) surfaces continue-learning,
recent lessons, progress-by-topic, a practice/needs-review summary, and a deterministic
next-lesson recommendation, with a mobile-responsive and accessible UI.

- **Backend:** dashboard endpoint composing `LessonProgress` + catalog into a
  `DashboardResponse` DTO; pure `recommend_next_lesson()` rule; auth-gated; 10 tests.
- **Web:** `DashboardPage`, `useDashboard` hook, dashboard routing/section nav, typed
  DTOs + `getDashboard()` client; 8 tests. `tsc --noEmit` clean; `vite build` green.

## License

MIT
