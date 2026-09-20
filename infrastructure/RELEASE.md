# Chemora Release Engineering (M31)

This runbook is the single source of truth for building, verifying, and releasing
Chemora. It reflects the actual repository tooling as of M31 — every command
here is executed by `infrastructure/ci_check.py` locally and by
`.github/workflows/ci.yml` in CI.

---

## 1. Repository layout relevant to release

| Path | Purpose |
|---|---|
| `packages/chemengine/` | Deterministic chemistry engine (the chemistry authority) |
| `backend/` | FastAPI service (`app/`), Alembic migrations (`alembic/`), tests (`tests/`) |
| `apps/web/` | Student web client (Vite + React) |
| `apps/admin/` | Admin console (Vite + React) |
| `infrastructure/` | CI gate runner (`ci_check.py`), this document |
| `.github/workflows/ci.yml` | CI pipeline (push/PR to `master`) |

---

## 2. Prerequisites

- Python 3.12 (CI pins `actions/setup-python` to 3.12)
- Node 22 (CI pins `actions/setup-node` to 22)
- A virtualenv at the repository root (`venv/`) for local Python work, or any
  environment with the packages below installed
- No PostgreSQL or Google credentials are required for the default test
  suites; see sections 6 and 7 for what those credentials unlock

---

## 3. Development setup

```bash
# Python side (from repository root)
python -m venv venv
venv/Scripts/python -m pip install -e "backend[dev]"
venv/Scripts/python -m pip install -e "packages/chemengine[dev]"

# Web + admin
cd apps/web && npm ci
cd ../admin && npm ci
```

Backend configuration: copy `backend/.env.example` to `backend/.env` and fill in
`GOOGLE_CLIENT_ID`, `DATABASE_URL`, `DATABASE_URL_SYNC`, `SESSION_SECRET`.
`backend/README.md` documents every variable; `.env` is git-ignored and must
never be committed.

---

## 4. Required checks (what CI runs)

CI executes these exact commands; every one is a blocking gate:

| Area | Command | Working directory |
|---|---|---|
| ChemEngine tests | `python -m pytest tests -q` | `packages/chemengine` |
| ChemEngine ruff baseline | `ruff check src --no-fix` (fails if > 342 findings) | `packages/chemengine` |
| ChemEngine mypy baseline | `mypy src/chemengine` (witness job, non-blocking) | `packages/chemengine` |
| ChemEngine benchmark smoke | `pytest benchmarks --collect-only -q -o python_files="benchmark_*.py"` (fails if < 60) | `packages/chemengine` |
| Backend ruff | `python -m ruff check app scripts --no-fix` | `backend` |
| Backend mypy | `python -m mypy app` | `backend` |
| Backend tests | `DATABASE_URL=sqlite+aiosqlite:///:memory: python -m pytest tests -q` | `backend` |
| Web tests | `npx vitest run` | `apps/web` |
| Web tsc | `npx tsc --noEmit` | `apps/web` |
| Web build | `npm run build` | `apps/web` |
| Admin tests | `npx vitest run` | `apps/admin` |
| Admin tsc | `npx tsc --noEmit` | `apps/admin` |
| Admin build | `npm run build` | `apps/admin` |

Run the same gates locally without GitHub:

```bash
venv/Scripts/python infrastructure/ci_check.py
```

The script exits non-zero when any gate fails — it is the local equivalent of
the CI pipeline and is used for release verification.

**ChemEngine static baseline:** `packages/chemengine/src` carries 342 pre-existing
ruff findings and 44 pre-existing mypy errors (21 files) inherited from earlier
milestones. M31 does not modify ChemEngine, so CI treats these as a baseline:
the ruff job fails only if the count **increases** beyond 342, and the mypy job
runs as a labeled non-blocking witness. Fixing them is ChemEngine work outside
M31 scope.

---

## 5. Benchmarks

ChemEngine benchmarks live in `packages/chemengine/benchmarks/` and use
`benchmark_*.py` filenames, while the project pytest config sets
`python_files = ["test_*.py"]`. Collection therefore requires the documented
override:

```bash
cd packages/chemengine
../../venv/Scripts/python -m pytest benchmarks -o python_files="benchmark_*.py"
```

**Baseline (M31, measured):** 60 benchmark functions, all passing in ~63s on the
development machine. M31 added the parsing benchmarks named by Phase 1.6
(`benchmark_parsing.py`: SMILES parsing, formula parsing, round-trip parse →
render, alias parsing) — before M31 only 55 benchmarks existed and the parsing
targets named in the roadmap were missing.

Timing thresholds are deliberately **not** CI gates: measurement is recorded in
`PROJECT_STATUS.md`, and the CI smoke only asserts that the benchmark suite
stays collectable (≥ 60 functions).

---

## 6. PostgreSQL migration verification

CI runs backend tests on SQLite by design (the suite is written for
`aiosqlite` in-memory). The **production** database path — the real Alembic
chain against real PostgreSQL — is verified separately by
`backend/scripts/pg_verify.py`, which M31 used to produce the recorded result
(33/33 checks pass; see `PROJECT_STATUS.md`).

The script needs a reachable PostgreSQL server; it does not need Docker. M31
verified against a portable PostgreSQL 18.6 binary (Zonky embedded distribution)
run entirely inside a temporary directory — no system installation, no changes
outside the repo/temp dirs:

```bash
# 1. Obtain a portable PostgreSQL (example: Zonky embedded distribution)
#    https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/
# 2. Initialize and start it on a local port
./bin/initdb.exe -D pgdata -U chemora --pwfile=pwfile.txt -E UTF8 -A scram-sha-256
./bin/pg_ctl.exe -D pgdata -o "-p 5544" -l pg.log start

# 3. Run the verification (backend venv)
cd backend
DATABASE_URL="postgresql+asyncpg://chemora:PW@127.0.0.1:5544/chemora" \
DATABASE_URL_SYNC="postgresql://chemora:PW@127.0.0.1:5544/chemora" \
../venv/Scripts/python scripts/pg_verify.py
```

What it verifies (33 checks): migration discovery/ordering, fresh `upgrade head`
from base, final schema (tables, columns, FKs, unique constraints, cascade
behavior), tutor conversation/message persistence with ownership enforcement,
cross-user isolation through the real HTTP API, unauthenticated access blocked,
downgrade → re-upgrade cycles, and idempotent re-runs.

**Rollback/downgrade assessment:** the full chain downgrades to base and
re-upgrades cleanly (verified in the same run). One caveat is recorded in
`PROJECT_STATUS.md`: the conversation tables' downgrade drops tables with data
loss by design — downgrade is a schema operation, not a data-preservation
guarantee.

---

## 7. AI provider verification

Providers are configured entirely server-side via `backend/.env`
(`AI_PROVIDER`, `AI_API_KEY`, `AI_ANTHROPIC_API_KEY`, `AI_TIMEOUT_SECONDS`).
Keys are never sent to the client and never logged.

**Offline/runtime verification (no credentials needed):**

```bash
cd backend
../venv/Scripts/python scripts/ai_provider_verify.py
```

This exercises the real provider seam: factory selection, mock provider
behavior, missing-SDK fallback, real HTTP error mapping (timeout/refused →
stable `provider_error`/`timeout` categories via the installed optional SDKs),
and asserts no key material ever reaches responses or logs. M31 result: 17/17
pass.

**Live smoke test (requires a real API key):** M31 could not run this — no
provider credential exists in the environment. When credentials become
available, run:

```bash
cd backend
AI_PROVIDER=openai AI_API_KEY="$OPENAI_API_KEY" \
  ../venv/Scripts/python scripts/ai_provider_verify.py --live
```

(If `--live` is not yet wired into the script, perform a single
`POST /api/v1/learning/tutor` request against a running server configured with
the real provider, then delete the key from the environment. Never print the
key.)

---

## 8. Browser E2E

M31 introduced real browser E2E using Playwright + Chromium against the real
production bundle and the real backend:

```bash
cd backend
../venv/Scripts/python scripts/e2e_verify.py
```

The harness starts the real FastAPI app (with two documented, test-only seams:
a fake Google verifier and a mock AI provider — mirroring `tests/conftest.py`),
builds `apps/web` with the E2E API URL baked in, and drives real Chromium
through 10 flows: unauthenticated gate, login, learning catalog, Chemistry
Explorer (real ChemEngine), tutor streaming, persistence across reload,
conversation switching, deletion, logout, and a clean-console check.

Prerequisites: `pip install playwright` plus a Chromium binary (the local
machine already has Playwright browsers under `%LOCALAPPDATA%/ms-playwright`;
`python -m playwright install chromium` fetches them on fresh machines).
`playwright` is an M31-added dev dependency of the backend extras.

---

## 9. Environment variables (release checklist)

Required for production startup (all documented in `backend/README.md` and
`backend/.env.example`):

- `DATABASE_URL` / `DATABASE_URL_SYNC` — PostgreSQL URLs (`postgresql+asyncpg://`,
  `postgresql://`). SQLite is the dev/demo profile only.
- `SESSION_SECRET` — **required in production** (`ENVIRONMENT=production`
  refuses to start without it; `COOKIE_SECURE` is forced on in production).
- `GOOGLE_CLIENT_ID` — Google ID-token audience.
- `CORS_ALLOW_ORIGINS` — explicit production origins; never `*` with credentials.
- AI (optional, server-side only): `AI_PROVIDER` (`mock` default, `openai`,
  `anthropic`), `AI_API_KEY`, `AI_ANTHROPIC_API_KEY`, `AI_TIMEOUT_SECONDS`,
  `AI_TOOL_CACHE_*` (M30 deterministic tool-result cache bounds).

Safety properties verified by `backend/scripts/release_verify.py` (18/18 pass):
`.env` is git-ignored; `.env.example` contains placeholders only; production
mode refuses insecure defaults; the wheel builds; the app imports with
production settings; the migration chain resolves; both frontend builds emit
their expected artifacts.

---

## 10. Release procedure

1. `venv/Scripts/python infrastructure/ci_check.py` — all gates green locally
2. `cd backend && ../venv/Scripts/python scripts/pg_verify.py` — PostgreSQL
   migration path verified (requires a PostgreSQL server; see section 6)
3. `cd backend && ../venv/Scripts/python scripts/ai_provider_verify.py` —
   provider seam verified (live smoke only if credentials exist)
4. `cd backend && ../venv/Scripts/python scripts/e2e_verify.py` — browser E2E
   (requires Playwright + Chromium; see section 8)
5. Review `git status` — no `.env`, no artifacts, no coverage output committed
6. Tag the release commit (project convention: milestone completion commits)

---

## 11. Known limitations (recorded honestly)

- **Live AI provider smoke:** blocked — no API key in the environment. Offline
  seam verification (17/17) is the compensating evidence.
- **CI on GitHub:** the workflow is validated locally (YAML parse, gate
  semantics, failure propagation proven by sabotage test), but has not executed
  on GitHub runners — first push will trigger the real run.
- **ChemEngine static baseline:** 342 ruff findings + 44 mypy errors are
  pre-existing and intentionally not fixed in M31 (ChemEngine is out of scope);
  CI prevents regression beyond the baseline.
- **Distributed rate limiting:** not implemented — single-process in-memory
  limiter is adequate for the current single-instance deployment target;
  documented as future work if deployment becomes multi-instance.
- **Model-generated conversation titles:** out of M31 scope (UX enhancement,
  not release engineering).
