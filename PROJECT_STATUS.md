# Chemora — Project Status Report

**Date:** September 23, 2026
**Version:** 1.2.0 (ChemEngine) / 0.1.0 (Chemora monorepo) / Backend M19–M31 complete / Web M21–M30 complete / Admin CMS M27 complete / M29 AI Chemistry Tutor + M30 AI Tutor Completion & Conversation Infrastructure + M31 Production Readiness & Release Engineering + M32 ChemEngine Release Completion + M33 ChemEngine v2.0 Feature Completion + M34 Full Reaction Mechanism Engine complete
**Status:** ✅ ChemEngine v1.2.0 complete · Monorepo migration complete · Backend Foundation (M19) + Authentication (M20) + Web Auth (M21) + Chemistry Explorer (M22) + Element Explorer (M23) + Chemistry Learning Core (M24) + Learning & Practice Expansion (M25) + Content Management Foundation (M26) + Production Content CMS (M27) + Chemistry Learning Experience Expansion (M28) + AI Chemistry Tutor (M29) + AI Tutor Completion & Conversation Infrastructure (M30) + Production Readiness & Release Engineering (M31) complete · Post-M26 corrective hardening pass complete

---

## Executive Summary

ChemEngine v1.2.0 is **complete** with all 1984 tests passing (0 failures, 4 skipped, every skip documented), including M34's bounded executable mechanism engine. All planned phases (0–15) are finished. The repository has been restructured from a ChemEngine-only layout into the Chemora monorepo layout. The FastAPI backend (M19), Google-authenticated sessions (M20), the web auth client (M21), the Chemistry Explorer (M22), the Element Explorer (M23), the Chemistry Learning Core (M24), the Learning & Practice Expansion (M25), the Content Management Foundation (M26), the Production Content CMS (M27), the Chemistry Learning Experience Expansion (M28), and the AI Chemistry Tutor (M29) are **complete** (199 backend tests, 71 web tests, 13 admin tests) — together they run real deterministic chemistry, element/electron-structure exploration, and a ChemEngine-backed learning experience with server-graded practice, a coherent, expanded curriculum, and a session-gated AI tutor whose deterministic chemistry always comes from ChemEngine end to end.

---

## Takeover Audit (2026-09-22)

An independent takeover audit re-verified M1-M33 against the repository
itself (code, tests, CI configuration, builds) rather than against prior
reports. Post-audit full-suite results: ChemEngine **1893 passed / 4
skipped** (every skip documented), backend **224**, web **74**, admin
**13**; ruff 302 src findings (<=342 baseline), mypy 43 findings (<=44
baseline witness), tsc clean, web/admin production builds green, Sphinx
`-W` green, 12/12 examples, 60/60 benchmark functions, package build +
twine check green, first import 18-30 ms (target <100 ms), 53-case
reaction reference set green, mechanism architecture boundary test green.

**Defects found and fixed (new corrective commits, history preserved):**

1. `canonical_tautomer()` was asymmetric - an enol and its keto form (an
   imidic acid and its amide) canonicalized to different representatives
   depending on which member was supplied. Fixed by detecting the reverse
   tautomer directions and searching the bounded tautomer closure.
2. The IUPAC parser built aromatic heterocycles as saturated graphs (ring
   atoms lacked the aromatic flag; template N-H counts were dropped), so
   pyridine serialized as piperidine (`C1CCCCN1`) and pyrrole lost its
   N-H (C4H4N instead of C4H5N).
3. The naming generator matched saturated heterocycles against the
   aromatic composition table - piperidine was named "pyridine".
4. `pyran` existed on both the generator and parser sides with no correct
   neutral representation; it now raises instead of mis-parsing.
5. `_name_hydrocarbon()` could return the literal placeholder
   "unknown"; out-of-coverage molecules now raise
   `UnsupportedNamingError` everywhere (ketone carbonyls without two
   carbon neighbours included).
6. Packaging declared version 1.0.0 while CHANGELOG declared 1.1.0;
   `pyproject.toml` and `__version__` now agree at 1.1.0, pinned by a
   version-consistency regression test.
7. Redundant module-level `pytestmark = pytest.mark.asyncio` removed
   from the M30 conversation suite (the backend runs `asyncio_mode =
   "auto"`, matching every other backend test module).

Regression tests for items 1-6 were added to
`packages/chemengine/tests/test_m33_naming.py`,
`test_rendering.py` (PNG optional-dependency degradation), and the new
`test_version_consistency.py`.

| Metric | Value |
|--------|-------|
| **Overall Completion** | ~87% of v1.0.0 scope |
| **Passing Tests** | 1984 / 1988 (100%) |
| **Skipped** | 4 (all documented: directional-bond round-trip; parse-guard determinism; 2 x cairosvg render extra absent) |
| **Source Files** | 81 Python files across 16 packages |
| **Test Files** | 46 |
| **Elements** | All 118 loaded from `elements.json` |
| **Packages Complete** | 16/16 (core, parsing, detection, generation, stereochemistry, properties, coordinates, rendering, reactions, validation, io, nomenclature, datasets, utils, compounds, education) |
| **Backend Tests** | 224 / 224 passing (M19 Foundation, M20 Authentication, M22 Chemistry API, M23 Elements API, M24+M25 Learning API, M26+M27 Admin Content API incl. preview & deletion, M28 curriculum & learning experience, M29 AI tutor, M30 conversations/streaming/cache, M31 health/readiness diagnostics) |
| **Web Tests** | 74 / 74 passing (M21 Auth integration, M22 Chemistry Explorer, M23 Element Explorer, M24+M25 Learning, M28 nav/resume, M29+M30 tutor UI) |
| **Admin Tests** | 13 / 13 passing (M27 Admin CMS: dashboard, lesson list, editor navigation, preview, answer-key safety, deletion flow; M28) |
| **Next Milestone** | None — M34 (Full Reaction Mechanism Engine) is complete (2026-09-23, v1.2.0); remaining v2.0/v3.0 Future Roadmap work is explicitly unordered and awaits scoping |

---

## Monorepo Migration (Complete — 2026-09-10)

The repository was restructured from a ChemEngine-only layout into the Chemora monorepo layout. All existing functionality is preserved.

**Repository structure:**
- `packages/chemengine/` — ChemEngine package (src layout preserved)
- `apps/web/` — React + Vite web client (M21 ✅; see below)
- `backend/` — FastAPI backend (M19 ✅ + M20 ✅; see below)
- `infrastructure/` — CI/CD, Docker (reserved)
- `TODO.md`, `PROJECT_STATUS.md`, `gantt.html` — Project tracking (updated)

**Verification:**
- 1635 tests passed, 1 skipped (baseline preserved)
- `import chemengine` works from installed package
- No duplicate ChemEngine implementation
- No chemistry functionality lost

---

## Backend Milestones

### ✅ M19: Backend Foundation (Complete)
- FastAPI application, CORS middleware, `/health` endpoint
- Async SQLAlchemy 2.0 engine + session factory (asyncpg)
- Alembic migrations scaffolding (repo-root `alembic/`)
- Backend `pyproject.toml`, pydantic-settings configuration, `.env.example`

### ✅ M20: Authentication (Complete)
- Google Sign-In / Identity Services — server-side ID-token verification via `google-auth` (`GoogleTokenVerifier`): signature, issuer, audience, expiry, subject
- User identity keyed by Google `sub`; email is **not** the identity key; unique constraint on `google_subject`
- Server-managed sessions with absolute expiration, inactivity timeout, and sliding renewal; revocation on logout
- Endpoints: `POST /api/v1/auth/google`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`
- Reusable `get_current_user` FastAPI dependency
- Alembic migration `001_initial_auth_tables` (users + sessions)
- 40 backend tests passing (in-memory SQLite + mock `GoogleTokenVerifier`)
- Architecture: `Endpoint → AuthService → GoogleTokenVerifier → User/Session models`

### ✅ M21: Frontend Authentication Integration (Complete)
- React 18 + Vite + TypeScript web app (`apps/web/`)
- Centralized `ApiClient` (fetch + `credentials: include`, JSON, typed base URL, 401-vs-network error classification)
- `AuthProvider` state machine: loading / unauthenticated / authenticated / error — never shows authenticated content before the session check finishes
- `AuthService`: `getCurrentUser()` / `exchangeCredential()` / `signOut()`
- `GoogleSignInProvider` port; production uses Google's official GIS client (`accounts.google.com/gsi/client`) — ID token sent to backend, never treated as a Chemora session
- 18 passing frontend tests (real ApiClient + AuthService vs. scriptable fake backend + mock Google provider)
- Mobile (`apps/mobile`) not yet configured — compatibility gap documented

### ✅ M22: Chemistry Explorer Foundation (Complete)
- Backend `POST /api/v1/chemistry/explore` + `ChemistryService` adapter over ChemEngine
- Identity for every input; structure (canonical SMILES, SVG, atoms/bonds) and bond-derived descriptors only for structure-bearing inputs
- Explorer UI with distinct chemistry/network/server error states
- 20 backend tests, 9 frontend tests

### ✅ M23: Element Explorer (Complete)
- Backend `GET /api/v1/elements` (118-element periodic table) + `GET /api/v1/elements/{identifier}` (symbol / name / atomic-number, case-insensitive) + `ElementService` adapter over `Element` / `ElectronConfigurator`
- Exposed structured electron data: full & noble-gas configurations, shell and subshell distributions, per-subshell orbital occupancy, valence/core/unpaired electron counts, and the engine's deterministic explanation
- Interactive periodic table (real 18-column grid, engine period/group/block placement, f-block rows, block colouring + text labels, accessible element cells, deliberate horizontal scroll on mobile)
- Element detail view: superscript configuration, orbital-box diagram from engine occupancy, shell distribution, counts, explanation; `prefers-reduced-motion` respected
- Client-side search (name / symbol / atomic number) over the engine-provided list — a UI index, not a second data source
- `unknown_element` / `invalid_identifier` 404 contract; network vs server errors distinguished
- 18 backend tests (incl. Cr/Cu Aufbau exceptions), 10 frontend tests

### ✅ M24: Chemistry Learning Core (Complete)
- Isolated content layer (`backend/app/learning/content.py`, 3 seeded lessons) — content is application data, NOT ChemEngine
- Learning API under `/api/v1/learning/` with explicit Pydantic models; answer keys never leave the server; deterministic (non-LLM) answer validation
- Progress persisted in `lesson_progress` (migration `002_lesson_progress`, FK → users CASCADE, unique per user/lesson): sections, per-question outcomes, derived percent, auto lesson completion, resume
- `chemistry_spotlight` sections render live engine-computed element data through the same component the Element Explorer uses
- Web Learn tab: catalog, section progression, progress bar, server-graded practice with immediate feedback, structured-errors only
- 17 backend tests, 10 frontend tests

### ✅ M25: Learning & Practice Expansion (Complete)
- Content expanded to 5 seeded lessons: *Chemical Formulas* and *Molecules and Their Properties* added to the M24 three — content still lives in the seed layer, outside ChemEngine
- `chemistry_spotlight` sections can now name a molecule (`molecule_input`) as well as an element; the client fetches live results from the existing M22 chemistry explore API and reuses the `ExplorerResult` component
- Two ChemEngine-backed answer kinds: `formula` (canonicalized via `formula_to_graph(...).molecular_formula`, so `H2O`/`HOH` both grade correct and `CO2` does not) and `element` (symbol / case-insensitive name / atomic number via `Element.from_symbol|from_name|from_z`)
- Grading remains deterministic and server-side; unparseable chemistry answers return `422 invalid_answer` rather than being marked wrong; answer keys never leave the server
- Defect fixed (found by testing, not by inspection): the in-progress `formula` kind used `parse_formula` (element counts) and read a non-existent `molecular_formula`, so no formula answer could ever be graded correct — corrected to the proper engine API with a regression guard over every seeded chemistry question
- Practice results view per practice section (attempted / correct / needs another look / accuracy); no gamification
- 11 new backend tests (106 total), 5 new frontend tests (52 total)

### ✅ M26: Content Management Foundation (Complete)
- Content tables (`lessons`, `lesson_sections`, `lesson_questions`) with Alembic migration `003_content_tables`
- `users.is_admin` flag for content-management authorization
- Admin CRUD API: list, get, create, update, publish, unpublish (`/api/v1/admin/lessons`)
- Content validation engine: metadata, sections, questions, chemistry references
- Content repository with eager-loaded lesson trees (no N+1)
- Database-backed content with idempotent seed/import (`app.learning.seed`)
- 31 admin API tests covering authorization, CRUD, publication, validation, answer-key exposure

### ✅ Post-M26 Corrective Hardening Pass (Complete)
- Fixed `ForeignKeyConstraint` missing import in `content.py`
- Fixed `LearningService` missing `await` on async `get_lesson` calls (3 methods)
- Fixed `upsert_lesson` UNIQUE constraint violation on section re-update
- Extracted shared chemistry validation into `chemistry_validate.py` (removed private-function coupling)
- Added production `SESSION_SECRET` validation (rejects missing secret in production)
- Added `IntegrityError` recovery for progress concurrency
- Updated `alembic/env.py` to import all models for autogenerate
- Added `.gitattributes` for consistent line endings
- 137 backend tests passing, 52 frontend tests, 1635 ChemEngine tests

### ✅ M27: Production Content & Admin CMS (Complete)
- Admin CMS web application (`apps/admin/`, React 18 + Vite + TypeScript, hash-routed SPA)
- Dashboard: total/published/draft lesson counts from the admin API (no fabricated analytics)
- Lesson list: title, status badge, difficulty, section/question counts, updated time, actions (edit / preview / publish / unpublish)
- Lesson editor: metadata (slug — immutable after creation, title, description, subject, difficulty, estimated minutes, ordering), section add/edit/remove, question add/edit/remove, multiple-choice option management
- Section types and question kinds in the UI match the backend constants exactly (`SECTION_KINDS`, `QUESTION_KINDS`) — no frontend-only types
- Admin-only preview endpoint `GET /api/v1/admin/lessons/{slug}/preview` returns the student-safe view (answer keys stripped) of draft or published lessons without changing publication state
- Admin DTOs now carry `created_at` / `updated_at` timestamps; admin list carries `updated_at`
- Publishing requires an explicit action; edits never auto-publish; slug changes are rejected server-side (slug immutability protects `lesson_progress`)
- Chemistry validation remains server-side and deterministic: formula questions via ChemEngine canonicalization, element questions via the element resolver (shared `chemistry_validate` service)
- Admin lesson deletion: `DELETE /api/v1/admin/lessons/{slug}` refuses (409 `lesson_has_progress`) when student progress references the lesson; `?force=true` deletes the lesson (progress rows cascade) after an explicit force confirm
- Lesson list Delete action with confirmation dialogs (first confirm, then a force confirm on 409)
- 11 frontend admin tests, 12 new backend tests (preview 200/401/403/404, answer-key stripping, timestamp fields, deletion lifecycle incl. progress-protected deletion and force delete)
- End-to-end browser verification of the admin CMS in Chrome (21/21 checks): auth gate, dashboard, lesson list, editor, preview without answer keys, delete with confirm + 409 force path, verified server-side (404 after delete)

### ✅ M29 — AI Chemistry Tutor (Complete — 2026-09-19)

The AI tutor milestone is complete: provider abstraction (mock / OpenAI /
Anthropic), authenticated `POST /api/v1/learning/tutor`, student-safe
retrieval (published lessons only, answer keys never serialized), an explicit
ChemEngine tool allowlist with schema validation, a bounded tool loop,
cost/abuse controls (token budget, output cap, timeout, per-user rate limit),
and a web chat tutor UI behind the existing auth gate. A mandatory regression
test proves a scripted provider's wrong chemistry is corrected by the
ChemEngine tool result. Backend tests: 199. Web tests: 71. Admin tests: 13.
Streaming and persistent conversations are documented as future enhancements
(neither is an M29 acceptance criterion).

### ✅ M28: Chemistry Learning Experience Expansion (Complete)
Formally scoped after auditing the pre-existing uncommitted M28 work against the roadmap, then implemented and completed.
- Six new lessons in a coherent curriculum after the five M24/M25 lessons: periodic-table, periodic-trends, chemical-bonding, molar-mass, stoichiometry, acids-bases
- Every lesson keeps the established structure (ordered sections, a ChemEngine-backed `chemistry_spotlight` section, practice, summary) and passes the strict publish validator
- Content remains in PostgreSQL via the M26/M27 CMS; `app/learning/content.py` is an idempotent seed/import source only (re-seeding never duplicates, never overrides edited drafts). No competing runtime content source.
- Previous/next section navigation with `aria-current` focus, position indicator, first-incomplete-section resume focus, and a catalog-level resume (`GET /api/v1/learning/progress`) with continue/review labels and per-lesson progress
- Chemistry authority stays in ChemEngine — no chemistry algorithms added in TypeScript; element/molecule spotlights come from the existing ChemEngine-backed APIs and molecule references are validated at authoring/publish time
- Backend +15 tests, Web +10 tests, Admin +2 tests (all meaningful, incl. failure paths); prior suites remain green
- Removed the generated `.browser-verify/chemora.db` runtime artifact and added a `.gitignore` rule for it.

### ✅ M29: AI Chemistry Tutor (Complete)

Implemented on top of the existing session/auth boundary and verified against
the formal M29 acceptance criteria. Recovered from an interrupted session:
the pre-existing uncommitted backend WIP was audited (not trusted), repaired,
completed with the missing pieces, and tested end to end.

- **Provider abstraction** (`backend/app/services/ai/provider.py`):
  `AIProvider` protocol with `MockAIProvider` (deterministic, no network),
  `OpenAIProvider` (OpenAI-compatible chat completions), and
  `AnthropicProvider` (Anthropic Messages API with OpenAI-shape tool-call
  translation) — all swappable via `AI_PROVIDER` settings without backend
  edits. Provider keys are server-side settings only, never logged, never
  returned to clients. Stable error categories (timeout / rate limit /
  auth failure / unavailable / provider error) map to controlled HTTP codes.
- **TutorService** (`service.py`): retrieval → provider → allowlisted tool
  call → validation → ChemEngine → tool result → provider → final answer.
  Bounded tool loop (`AI_MAX_TOOL_ITERATIONS`), input token budget enforced
  (`AI_MAX_INPUT_TOKENS`, history trimmed to fit), output token cap, per-user
  sliding-window rate limit, untrusted client history sanitized (only
  well-formed user/assistant turns survive), graceful fallback answer on
  provider/tool failure.
- **ChemEngine tool boundary** (`tools.py`): explicit student-safe allowlist
  (`parse_smiles`, `parse_formula`, `compute_property`, `validate`,
  `detect_functional_groups`, `calculate_electron_configuration`); unknown and
  disallowed tools rejected; arguments validated against the registered JSON
  schemas with length bounds; raw engine exceptions never reach model or client.
- **Student-safe retrieval** (`retrieval.py`): published lessons only via the
  existing `ContentRepository` rules (drafts are not even discoverable);
  serialized context carries section prose and question prompts only —
  answer keys are never included, so the tutor cannot leak what it was never
  given. Client-suggested `lesson_slug` is verified server-side. Bounded
  context (≤2 lessons, per-lesson char cap), deterministic keyword scoring.
- **Authenticated endpoint** (`backend/app/api/v1/tutor.py`):
  `POST /api/v1/learning/tutor` — 401 unauthenticated (identity from the
  server-side Chemora session; no client-supplied user ids), structured
  error codes, response carries only answer + opaque metadata.
- **Frontend tutor** (`apps/web`): `TutorPage` chat UI behind the existing
  auth gate (`Tutor` nav section), `useTutor` conversation hook, `askTutor`
  API client method, empty/loading/error/disabled states, conversation
  history sent as prior turns, no chemistry computation and no provider/tool
  payloads in the client.
- **Tests**: 35 backend tests (provider boundary, tool allowlist, mandatory
  chemistry-authority test where a scripted provider demands a tool and the
  ChemEngine result wins, auth, privacy, budget, rate limit, bounded loop),
  9 web tests (auth gating, round-trip, history, loading/error/empty states,
  metadata hygiene).
- **Deferred by design**: streaming (in scope prose, not in the M29
  acceptance criteria — documented as a future enhancement), persistent
  conversation storage (not required by any criterion; stateless per-request
  design), live provider verification (no API key in the environment; the
  OpenAI/Anthropic paths are exercised through the abstraction seam).

---

### ✅ M30: AI Tutor Completion & Conversation Infrastructure (Complete — 2026-09-19)

M30 takes the M29 tutor from a stateless request/response prototype to a
complete conversational system. Implemented and verified:

- **Persistent conversations:** `tutor_conversations` + `tutor_messages`
  tables (`backend/app/models/tutor.py`, migration `004_tutor_conversations`
  with FK CASCADE, composite indexes on `(user_id, updated_at)` and
  `(conversation_id, seq)`), `TutorConversationRepository` with limits
  (30 conversations/user, 200 messages/conversation) and **ownership on
  every query** (foreign ids return 404, never existence leakage),
  CRUD + messages endpoints under `/api/v1/learning/tutor/conversations`.
- **Server-side history:** `TutorService.ask_in_conversation` /
  `stream_in_conversation` load history from the owned conversation — the
  client cannot inject foreign or arbitrary history (the M29 client-supplied
  `history` field remains only on the legacy stateless endpoint).
- **Streaming:** `generate_stream` added to all three providers behind the
  unchanged `AIProvider` abstraction (`StreamEvent` text/tool_calls/final
  protocol; OpenAI delta accumulation, Anthropic content-block events, mock
  chunked streaming); `POST .../messages` streams SSE frames
  (`delta`/`done`/`error`); tool calls execute server-side through the same
  bounded allowlisted loop; partial answers persist even if the client
  disconnects; provider failures become one stable error frame.
- **Tool-result cache:** `ToolResultCache` (deterministic SHA-256 keys over
  sorted canonical arguments, lazy TTL sweep, insertion-order eviction,
  hit/miss/expiry counters) wired into `TutorToolbox` after argument
  validation; failures never cached; conversation content and LLM responses
  never cached; `AI_TOOL_CACHE_ENABLED/TTL/MAX_ENTRIES` settings.
- **Frontend:** `TutorPage` extended — new/switch/delete conversations,
  server-loaded history, incremental delta rendering with a streaming
  indicator, distinct loading/streaming/error/empty states; `useTutor`
  conversation state; `ApiClient.streamTutorMessage` + SSE frame parser.
- **Tests:** +21 backend (CRUD, ownership, cross-user isolation, server-side
  history, SSE well-formedness, streaming tool calls, provider failure,
  malformed/oversized/unauthorized requests, cache hit/miss/expiration/
  bounds, caps) and +3 net web (streaming round-trip, partial rendering,
  history loading, deletion, switching, metadata hygiene) — 220 backend,
  74 web, 13 admin, 1635 ChemEngine.

**Deferred:** live provider verification (no API key in the environment),
browser E2E (tooling unavailable — compensated with jsdom streaming tests),
distributed rate limiting, model-generated conversation titles.

---

### ✅ M31: Production Readiness & Release Engineering (Scoped 2026-09-19 → Complete 2026-09-20)

M31 is **complete**. It was deliberately **not**
a chemistry-feature milestone: it took the existing Chemora system through a
production-readiness and release-engineering pass — deployment verification,
real CI, reproducible release/build validation, environment/secrets hygiene,
critical browser E2E where feasible, accurate coverage/benchmark baselines,
release documentation, and production-critical diagnostics — while all
product functionality delivered through M30 remained intact.

**Objectives:** (1) verify the production database migration path against
real PostgreSQL (documented as blocked if no instance is available);
(2) perform real AI provider smoke verification only where valid credentials
exist (never fabricating a live test, never exposing keys); (3) add real CI
that runs the project's backend/ChemEngine/web/admin checks and fails when
they fail; (4) establish a reproducible release/build + environment/secrets
verification process; (5) add critical browser E2E coverage where reliable
automation is feasible; (6) measure the roadmap's existing documented
coverage/benchmark targets accurately; (7) complete the release-engineering
documentation already identified in the roadmap; (8) ensure adequate
failure diagnostics/health checks without exposing sensitive information;
(9) dispose of M30 deferred items correctly (live provider smoke in;
browser E2E where feasible; distributed rate limiting only if the deployment
architecture requires it; model-generated titles excluded as UX, not
release engineering).

**In scope:** production PostgreSQL migration verification (fresh apply,
upgrade path, schema agreement, constraints/indexes, tutor conversation
persistence on PostgreSQL, rollback assessment, failure behavior; SQLite
never substitutes for this); real provider smoke (initialization,
authenticated request, normal response, tool-call path, streaming path,
failure/timeout handling, observable usage; keys never printed/committed/
frontend-exposed; offline seam verification + documented blocker if no key);
CI running backend `pytest`/`ruff`/`mypy`, web tests/`tsc`/build, admin
tests/`tsc`/build, ChemEngine tests + relevant static checks, failing on
broken checks without weakening them; reproducible release validation (web/
admin builds, backend startup/import path, migration chain, environment
config, required env vars, no committed secrets, `.env` ignored,
`.env.example` complete, minimum run-environment documented); browser E2E
for critical flows only (auth shell, explorer load, learning navigation,
tutor create/stream/persist/reload/delete, logout boundary) if it integrates
cleanly, else the exact blocker documented; accurate measurement of the
Phase 1.6 benchmark baseline and Phase 1 DoD coverage targets plus backend/
web coverage where applicable, never inventing or weakening targets;
release-engineering documentation (API reference, developer setup, CI/CD,
release procedure, env vars, deployment prerequisites, migration procedure,
testing commands) that never claims nonexistent infrastructure; proportionate
structured logging, request/error identification, provider and database
failure diagnostics, startup validation, and health/readiness checks that
never log API keys, credentials, private conversation contents, answer keys,
or sensitive user data.

**Out of scope:** new ChemEngine chemistry domains (organometallics,
polymers, biomolecules, reaction mechanisms, GNN, WebAssembly,
crystallography, NMR, drug discovery, retrosynthesis, docking, quantum,
chemical database engine), mobile, offline sync, quizzes/exams, CMS rebuild,
speculative AI features, vector search, M32/M33 work. The ChemEngine v2.0/
v3.0 future roadmap remains separately labeled and is not relabeled as M31.

**Acceptance criteria:** production PostgreSQL migration path verified or an
explicit environment blocker documented; real provider smoke performed where
credentials exist or the lack is explicitly documented; CI executes the
required backend/ChemEngine/web/admin checks and fails on broken checks;
production builds reproducible; environment/secrets configuration documented
and safe; critical browser E2E exists if the environment supports reliable
automation, else the blocker + compensating tests documented; documented
coverage/benchmark targets measured accurately; API/developer/release docs
updated where required; diagnostics/health checks adequate without exposing
sensitive information; M29/M30 regression-safe; no new P0/P1 security
issues; full regression/static/builds pass; TODO.md, PROJECT_STATUS.md, and
gantt.html reconciled; focused commits pushed with HEAD == origin/master and
a clean working tree.

**All criteria satisfied — delivered (2026-09-20):**
- **PostgreSQL (live-verified, 33/33):** real PostgreSQL 18.6 via a portable
  binary in a temp directory (no system install); `backend/scripts/pg_verify.py`
  proves fresh `alembic upgrade head` from base, schema introspection (tables,
  columns, FKs, unique constraints, cascade), tutor conversation/message
  persistence with server-enforced ownership, cross-user isolation and
  unauthenticated rejection over real HTTP, downgrade-to-base and re-upgrade
  cycles, and idempotent re-runs.
- **AI provider (blocked → documented):** no credentials exist in the
  environment; live smoke NOT fabricated. `backend/scripts/ai_provider_verify.py`
  performs 17/17 offline verifications (factory selection, mock provider,
  missing-SDK fallback, real HTTP error mapping through the optional SDKs,
  key-never-logged). `infrastructure/RELEASE.md` §7 records the exact live
  command for when credentials exist.
- **CI:** `.github/workflows/ci.yml` — 12 blocking gates across ChemEngine
  (tests, ruff baseline ≤342, benchmark smoke ≥60), backend (ruff, mypy,
  pytest), web (vitest, tsc, build), admin (vitest, tsc, build); no `|| true`,
  no `continue-on-error` on required steps, `--no-fix` everywhere. Failure
  propagation proven by sabotage (broken file → ruff 1 / mypy 2 → green after
  restore). `infrastructure/ci_check.py` runs the same gates locally (12/12).
- **Release validation:** `backend/scripts/release_verify.py` 18/18 — clean
  web/admin `dist/` builds with expected artifacts, backend wheel + production
  import path, migration chain resolution, `.env` ignored, `.env.example`
  complete (incl. the M30 `AI_TOOL_CACHE_*` vars), production config refuses
  insecure defaults.
- **Browser E2E (executed):** Playwright + Chromium 147 against the real
  production bundle and real backend — `backend/scripts/e2e_verify.py`,
  10/10 flows (auth gate, login, learning catalog, Chemistry Explorer on real
  ChemEngine, tutor streaming, reload persistence, conversation switching,
  deletion, logout, clean console). Uncovered the missing favicon — fixed.
- **Coverage/benchmarks (measured):** ChemEngine 80% overall (matches the
  documented ~80%); backend 80% on `app/`; web 88.97% lines; admin 62.35%
  lines. Phase 1.6 baseline established: 60 benchmark functions pass (~63s),
  adding the SMILES/formula/alias parsing benchmarks the roadmap named
  (`benchmarks/benchmark_parsing.py`). Phase 1 DoD's 90%/95% coverage
  aspiration is NOT met (80%) — recorded as the exact gap, not hidden.
- **Diagnostics:** `GET /health/ready` — DB connectivity + schema presence via
  the same session dependency routes use, AI provider state as booleans, 503
  on degradation; never returns URLs, credentials, or exception text
  (`backend/tests/test_health.py`, 4 tests).
- **Documentation:** `infrastructure/RELEASE.md` (full release runbook),
  `infrastructure/README.md` (replaced stale placeholder), `backend/pyproject.toml`
  (`providers` + `e2e` extras), `backend/.env.example`.
- **Regression after M31:** ChemEngine 1635 passed / 1 skipped; backend **224**
  passed (220 + 4 health); web 74; admin 13; backend ruff/mypy clean;
  web/admin tsc + production builds clean.
- **Disposition of M30 deferred items:** live provider smoke — attempted,
  blocked (documented); browser E2E — delivered; distributed rate limiting —
  not required for the current single-instance deployment target (future work);
  model-generated titles — excluded (UX, not release engineering).
- **Known limitations:** CI has not yet executed on GitHub runners (workflow
  validated locally; first push triggers the real run); the 342 ruff findings
  + 44 mypy errors in ChemEngine src are a pre-existing baseline that CI now
  prevents from growing (fixing them is out of M31 scope); coverage sits at
  80% against the 90%/95% Phase 1 DoD aspiration.

---

### ✅ M32: ChemEngine Release Completion — API Reference, Tutorials & PyPI (Complete — 2026-09-21)

M32 is **complete**. Where M31 performed
production-readiness and release engineering for the Chemora *product*, M32
completes the equivalent release work for the ChemEngine *library*: the
remainder of Phase 15 ("Release") tagged "Planned (v2.0)" plus the one
Phase 1 DoD delta M31 proved unrealized. The roadmap's Phase 15 purpose is
the objective: "Ship ChemEngine as a professional open-source library on
PyPI. 100% documentation coverage, tutorials, CI/CD, semantic versioning,
and a trusted release."

**Why this is next (repository evidence):** after M31 the only explicitly
enumerated, milestone-shaped remaining work is Phase 15.2 (Sphinx API
reference ⬜), 15.3 (tutorials + examples ⬜), 15.5 (PyPI publication ⬜),
the 15.4 matrix delta (CI exists via M31 but runs Python 3.12 only), and
Phase 1 DoD's "benchmark regression tests (compare against baselines in
CI)" — marked done but proven unrealized by M31 (no saved baselines; CI
asserts collectability only). Rejected alternatives: v2.0 chemistry domains
are an explicitly unordered Future Roadmap (no selection signal); the mobile
milestone has one scopeless sentence; v3.0 is longer-term; M30/M31 deferred
items are already dispositioned.

**In scope:** Sphinx project in `packages/chemengine/docs/` (conf.py, index,
autodoc/napoleon over the existing Google-style docstrings) with a
warning-free docs build as a CI gate; docstring completeness audit for the
public API; the six roadmap-named tutorials (quickstart, SMILES,
substructure, properties, rendering, AI/tool integration); 10+ runnable
scripts in `packages/chemengine/examples/`; SECURITY.md, CODE_OF_CONDUCT.md,
RELEASE_CHECKLIST.md, DEPLOYMENT.md (roadmap-named, currently absent);
metadata/license/security audit with `twine check`; changelog-anchored
GitHub Release + tag; PyPI/TestPyPI publication where credentials exist,
else documented blocker with exact steps; CI Python 3.10–3.13 matrix within
the existing workflow; benchmark-baseline regression comparison in CI
(saved baselines, documented thresholds, demonstrable failure on injected
regression); Phase 15 table reconciliation.

**Out of scope:** new chemistry domains (they remain the separately labeled
Future Roadmap v2.0/v3.0); the remaining v2.0 feature rows (atropisomers,
PNG output, substructure highlighting, themes, preferred IUPAC, name
parser, tautomer, atom-atom mapping); the mobile milestone; distributed
rate limiting; model-generated conversation titles; product feature work in
backend/web/admin; ChemEngine algorithm changes; M33+ work.

**Acceptance criteria:** Sphinx API reference builds warning-free and is a
CI gate; docstring audit recorded with public-API gaps closed or
documented; six tutorials exist and are accurate; 10+ examples executed
successfully; the four roadmap-named community/release files exist;
`twine check` passes on built distributions; GitHub Release + tag created
or blocker documented; PyPI/TestPyPI published where credentials exist or
blocker documented with exact steps; CI verifies Python 3.10–3.13 (or the
documented supported set); benchmark baselines saved and compared in CI,
failing on documented-threshold regressions; Phase 15 table reconciled;
M19–M31 regression-safe with exact totals; no new P0/P1 security issues;
no credentials committed or printed; TODO/PROJECT_STATUS/gantt
reconciled; focused commits pushed with HEAD == origin/master and a clean
tree.

**Dependencies:** M31 CI infrastructure; Phase 15.1 docstrings (✅);
existing CHANGELOG.md and CONTRIBUTING.md; the M31-verified benchmark
suite. **Testing requirements:** `sphinx-build -W`, example execution,
`twine check`, full regression with exact totals, ruff/mypy/tsc/builds,
benchmark-comparison failure demonstrated on an injected regression.
**Known limitations to record at completion:** whichever of PyPI/TestPyPI
publication, GitHub Release, and ReadTheDocs hosting lacked external
accounts/credentials, with exact completion steps.

**Completion record (2026-09-21).** All 14 acceptance criteria satisfied
(12 PASS, 2 BLOCKED-but-prepared):

- **Sphinx API reference (15.2):** `packages/chemengine/docs/` — conf.py
  (napoleon/autodoc/autosummary), index, 17 generated API pages
  (`scripts/generate_api_docs.py`, checked in for deterministic builds),
  tutorials section. `sphinx-build -W` exits 0 with zero warnings from a
  clean `_build`. CI gate in `ci.yml`; local gate in `ci_check.py`.
- **Docstring audit:** mechanical AST audit — 71 modules, 224 top-level
  public defs (0 missing), 480 public functions/methods/properties total;
  103 gaps closed, 1 UTF-8 BOM removed (`compounds/__init__.py`), 3
  docstrings reformatted for napoleon, 1 inaccurate InChIKey docstring
  corrected. ChemEngine src ruff findings reduced 342 → 288 as a
  side-effect of the documentation work.
- **Tutorials (15.3):** the six roadmap-named tutorials in
  `docs/tutorials/` (quickstart, smiles, substructure, properties,
  rendering, ai_integration); all code verified against the current API;
  examples literalincluded so they cannot drift.
- **Examples:** 12 scripts under `packages/chemengine/examples/`,
  executed via `scripts/verify_examples.py` (12/12 pass; CI gate).
- **Release surface:** SECURITY.md, CODE_OF_CONDUCT.md,
  RELEASE_CHECKLIST.md, DEPLOYMENT.md, LICENSE added under
  `packages/chemengine/`; publish workflow (`.github/workflows/publish.yml`)
  triggers on `v*.*.*` tags and uses the `PYPI_API_TOKEN` secret.
- **Package audit/build:** metadata fixes (Production/Stable classifier,
  keywords, URLs, Typing::Typed, license-files, sdist include list);
  `tomli>=2.0.0; python_version < '3.11'` declared — a real missing-
  dependency bug found by the clean-venv wheel test; a TOML
  section-ordering bug that dropped all core Requires-Dist fields fixed.
  `python -m build` + `twine check`: PASSED. Wheel install verified in a
  clean venv on 3.10 and 3.13. Sizes: 216 KB wheel / 334 KB sdist
  (target <5 MB met). First import measured: 492.9 ms warm-cache
  (Phase 1.6 target <100 ms — genuine gap, recorded).
- **CI matrix (15.4):** `chemengine-matrix` job for 3.10–3.13;
  verified locally on real interpreters 3.10.11/3.11.16/3.12.14/3.13.15
  → 1635 passed, 1 skipped on each.
- **Benchmark regression (Phase 1 DoD):** `benchmark-regression` CI job
  with rolling baseline (actions/cache + artifact),
  `--benchmark-compare-fail=mean:60%`; sabotage-proven — an injected
  2 ms/parse slowdown failed both the comparison gate (4 regressions)
  and the absolute-threshold layer in `tests/test_benchmark_baselines.py`
  (2 failures); reverted and green. 60 benchmarks pass in ~62–72 s.
- **Regression totals (unchanged baselines):** ChemEngine 1635 passed /
  1 skipped; backend 224 passed (ruff+mypy clean); web 74 passed
  (tsc+build OK); admin 13 passed (tsc+build OK); 16/16 `ci_check.py`
  gates green.
- **Blocked (documented, never fabricated):** PyPI/TestPyPI upload and
  GitHub Release creation — no `gh` CLI, no GitHub/PyPI tokens in the
  environment. Exact completion steps: RELEASE_CHECKLIST.md §4–§5;
  automation ready in the publish workflow.
- **Known new limitations recorded:** first-import time exceeds the
  Phase 1.6 <100 ms target (~493 ms warm; dominated by module-init and
  importlib.metadata); tetrahedral CIP descriptor assignment reports R
  for both `@`/`@@` of 2-butanol (storage preserves the distinct tags;
  perception-layer limitation documented in example 07, algorithm change
  out of M32 scope).

---

### ✅ M33: ChemEngine v2.0 Feature Completion — Rendering, Nomenclature & Reaction Mapping (Complete — 2026-09-21)

M33 is **complete**. M32 closed the
ChemEngine *release* surface; M33 closed the remaining **itemized**
Phase 10–12 feature rows — formerly tagged "Planned (v2.0)" in the roadmap —
as one coherent milestone: rendering (10.2 PNG output, 10.3 substructure
highlighting, 10.5 dark mode + themes), nomenclature (11.3 preferred IUPAC
+ common names, 11.4 IUPAC name parser, 11.5 tautomer handling), and
reactions (12.2 atom-atom mapping, 12.5 the
mechanism *architecture* interfaces the completed Phase 12 explicitly
anticipated). It also met the Phase 15 performance
target M32 recorded (first import 490 → ~19–27 ms vs the <100 ms target).

**Delivered:**
- **Rendering:** `rendering/png.py` (cairosvg optional `render` extra,
  2x/4x HiDPI, documented `PNGUnavailableError` graceful degradation);
  deterministic substructure highlighting on `render()` + tool surface;
  `RenderTheme` objects (dark, CPK, monochrome, accessibility) with
  per-theme deterministic output (43 rendering tests).
- **Nomenclature:** generator correctness pass (longest-chain selection
  through functional groups, substituent-locant minimization, nitro
  recognition, ring hydroxyl/amine suffixes, locant-omission rule);
  `parsing/iupac/{tokenizer,parser}.py` round-tripping the supported
  grammar (38-case InChIKey-verified round-trips, structured
  `UnsupportedNamingError` for unsupported grammar); curated 63-name
  common-names dictionary with integrity tests; bounded keto-enol +
  amide-imidic tautomer detection/canonicalization
  (`MAX_TAUTOMER_FORMS=8`).
- **Reactions:** `reactions/mapping.py` deterministic skeleton-based
  atom-atom mapping (element equality + bond-existence consistency;
  bond orders reported as changed/formed/broken), branch-and-bound with
  signature ordering, node budget with explicit failure, one-tree
  ambiguity enumeration for full correspondences (bijecting the smaller
  side) + forced-seed probe for partial ones, conservative
  ambiguity-on-exhaustion; 53-case reviewed reference oracle
  (`tests/data/reaction_mapping_reference.json`, each case annotated);
  mapping ~1–7 ms on small molecules (Phase 12 <10 ms target met);
  `reactions/mechanisms.py` interfaces only (ElectronMovement,
  MechanismStep/Trace, MechanismRule protocol) — no engine, enforced by
  a boundary test.
- **Performance:** first import 490 → ~19–27 ms via PEP 562 lazy public
  API + lazy element/dataset tables + lazy plugin discovery; regression
  gate `tests/test_import_performance.py` (100 ms target + 150 ms guard,
  documented cold `-X importtime` median-of-3 methodology).
- **Correctness fixes required by the naming acceptance criteria:**
  saturated ring-closure SMILES silently dropped by formula
  misclassification (`C1CCCCC1` parsed as hexane — fixed in
  `parsing/protocol.py` + organic-subset strictness in `parsing/smiles.py`);
  InChI/InChIKey serializers were atom-order-dependent — now canonical
  (order-independent), matching official standard InChI for propane.

**Test totals:** ChemEngine **1851 passed, 2 skipped** (both skips
documented; baseline was 1635/1 at M32 start of M33 window), backend
**224**, web **74**, admin **13**; backend ruff+mypy clean; web/admin tsc
+ builds green; ChemEngine package build + twine check green; Sphinx `-W`
green; Python 3.10 verified locally, 3.11–3.13 via the CI matrix job.

**Known limitations (recorded honestly):** the IUPAC parser covers exactly
the generator's supported grammar subset (ethers and aromatic ethers raise
`UnsupportedNamingError` rather than guessing); the common-names dictionary
is a curated 63 names (roadmap's 1000+ aspiration recorded as future work);
the InChI serializer remains a simplified implementation (canonical
numbering now, full standard-InChI feature parity not claimed); the
mechanism module contains no executable chemistry by design; GitHub
Release/PyPI upload remain credential-blocked from M32.

**Why this is next (repository evidence):** after M32 the remaining
explicitly itemized feature work in the roadmap is exactly the rows above,
each with named atomic tasks and benchmarks. Discovery verified the other
remaining "Planned" markers (Phases 1/6/7) were stale — atropisomer
placeholders, ambiguous/conflict stereo validation, isomer filtering, and
property-based tests are already implemented — and reconciled them. The
Future Roadmap v2.0 *domains* (organometallics, polymers, biomolecules,
full mechanism engine, GNN, WebAssembly, crystallography, NMR) remain an
explicitly unordered future list and are NOT part of M33; v3.0 stays
longer-term; the M32 credential-blocked GitHub Release/PyPI upload remain
documented blockers, not M33 work.

**Out of scope:** all Future Roadmap v2.0 domains; v3.0 items; mobile;
M32's external release blockers; AI tutor redesign; backend/web/admin
product feature work; M34+ work.

**Acceptance criteria (summary — full list in TODO.md M33 section):** PNG
output via the roadmap-named optional dependency with HiDPI and graceful
degradation; deterministic substructure highlighting exposed on the
tool surface; dark/CPK/monochrome/accessibility themes; preferred IUPAC
names + a tested common-names dictionary; `parsing/iupac/` tokenizer+parser
round-tripping the supported grammar with documented coverage; keto-enol
and amide-imidic tautomer detection + canonicalization; `ReactionGraph`
with MCS-based atom-atom mapping validated on a 50+ reaction reference set
meeting the Phase 12 benchmark targets; the mechanism architecture
placeholder (not an engine); first import <100 ms with the benchmark gate
green; Phase 10/11/12 tables reconciled; full regression with exact
totals; no new P0/P1 security issues; docs synchronized; focused commits
pushed with HEAD == origin/master and a clean tree.

---

### ✅ M34: Full Reaction Mechanism Engine (Complete — 2026-09-23)

**Status: COMPLETE.** The executable engine, curated rule catalogue,
reference oracle, validation, serialization, registry integration, version
1.2.0, and full regression are delivered.

**Objective.** Implement the executable step-by-step mechanism engine that
Phase 12 anticipated and M33 staged interfaces for: curated electron-pushing
rules applying to M33 `ReactionGraph`s, producing validated,
conservation-checked `MechanismTrace` sequences, bounded to supported
chemistry ("full" = end-to-end executable, not universal coverage).

**Why this is next (repository evidence).** It is the only Future Roadmap
item with a staged dependency edge from completed work: M33 shipped
`reactions/mechanisms.py` as *interfaces only*, whose docstring states the
module "deliberately contains no mechanism engine" and that concrete
electron-pushing logic "belongs to a future, separately-scoped milestone …
so that the broader roadmap (12.x) can be scheduled against concrete
interfaces"; Phase 12's purpose repeats "full implementation deferred to
v2.0"; and M33 delivered every runtime dependency (`ReactionGraph`, MCS
mapping + 53-case oracle, conservation validators, tautomer
canonicalization, template matching, <100 ms import gate). The other v2.0
bullets (organometallics, polymers, biomolecules, GNN, WebAssembly,
crystallography, NMR) have zero partial implementation and remain
explicitly unordered; mobile has one scopeless sentence ("a future mobile
milestone will define the compatibility path"); v3.0 stays longer-term;
M32's PyPI/GitHub Release steps remain credential-blocked (not milestone
work); advanced-stereochemistry, visualization, 1000+ names, and
InChI-parity items are recorded gaps without milestone-shaped rows.

**In scope.** `MechanismEngine` implementing the frozen `MechanismRule`
protocol with validated proposals (no in-place mutation); rules for the
`MovementKind` vocabulary; ≥10 named mechanisms (SN2, SN1, E2, E1, E1cB,
electrophilic addition/Markovnikov, carbonyl addition–elimination, …);
per-step atom+charge conservation, deterministic ordering, structured
unsupported/illegal errors; ≥25-scenario curated reference oracle;
`AlgorithmRegistry` registration; lazy import (first import <100 ms);
trace serialization; CHANGELOG [1.2.0] + version 1.2.0 on
completion.

**Out of scope.** All other v2.0 domains; all v3.0 items; mobile;
curved-arrow SVG annotation rendering; kinetics/thermodynamics;
yield/condition prediction; novel-mechanism inference for arbitrary
literature reactions; AI-tutor/backend/web/admin product work; M32's
credential-blocked release steps; M35+.

**Dependencies.** M33 (`reactions/mechanisms.py` interfaces,
`ReactionGraph` + MCS mapping, conservation validators, tautomer
canonicalization, nomenclature guards, perf gate); Phase 3 FG detection;
Phase 5 SMARTS matching; Phase 12.4 reaction templates;
`AlgorithmRegistry`; `io` serialization.

**Acceptance criteria (summary — full list in the TODO.md M34 section).**
Executable engine against the frozen M33 interfaces (M33 interface tests
unchanged and green); ≥10 named mechanisms / ≥25 reference scenarios green;
conservation + determinism + structured-error tests; registry + <100 ms
gate; full regression with exact totals and ruff/mypy within documented
baselines; version 1.2.0 consistent; docs + gantt synchronized (gantt →
complete only on satisfaction).

**Testing requirements.** New `tests/test_mechanism_engine.py` + checked-in
reference data: per-`MovementKind` rule units, per-mechanism trace oracles,
negative/illegal-step cases, determinism, serialization round-trip,
conservation invariants across the reference set; benchmark baseline
extended; `ci_check.py` gates green.

**Documentation requirements.** Sphinx engine page (+ worked example where
feasible); Phase 12 table reconciled; TODO.md/PROJECT_STATUS.md M34 records;
gantt.html status → complete on completion; CHANGELOG [1.2.0].

**Risks / blockers.** Chemical-correctness risk is high (M33 docstring:
"the most error-prone area of computational chemistry") — mitigated by
curated oracles, conservation validation, determinism tests and a bounded
rule vocabulary; scope explosion — mitigated by the ≥10/≥25 curated targets
and the explicit out-of-scope list; aromatic/tautomer edge cases — reuse M33
canonicalization; import-time creep — existing <100 ms gate; SMARTS gaps —
extend Phase 12.4 templates in-scope or drop with a recorded note. No
credential/external blockers.

---

## Completed Milestones

### ✅ Phase 0: Foundation (v0.1.0)
- Core domain models: `MolecularGraph`, `Atom`, `Bond`, `Isotope`, `Charge`, `Coordinate2D`, `Coordinate3D`, `Conformer`
- All enums: `ElementSymbol` (all 118), `BondOrder`, `BondType`, `BondTopology`, `ChiralTag`, `BondStereo`, `Hybridization`
- `AlgorithmRegistry`, `EventBus`, `PluginManager`, `ChemEngineAPI`, `DatasetRegistry`
- `MolecularGraphBuilder` — builder pattern for immutable graph construction

### ✅ Phase 1: Parsing (v0.2.0)
- SMILES parser — full OpenSMILES specification
- SMILES canonicalization — Morgan-like iterative atom invariant refinement
- SMILES serializer — spanning-tree-based deterministic output
- InChI parser — formula, connections, hydrogens, charge layers
- Common alias resolver — 100+ chemical names → SMILES
- Auto-detect format — SMILES, InChI, formula, name detection
- `parse_any()` — automatic format detection and dispatch

### ✅ Phase 2: Validation (v0.4.0)
- 9 built-in validation rules: valence, hypervalent, charge, total charge, isotope, graph structure, radical, valence saturation, aromaticity
- 3 rule set profiles: strict, standard (default), relaxed
- Graph sanitization: add implicit hydrogens, remove duplicate bonds, full sanitize pipeline

### ✅ Phase 3: Functional Group Engine (v0.5.0)
- Functional group detection engine with 21 detectors
- All standard groups: Alcohol, Phenol, Ether, Aldehyde, Ketone, Carboxylic Acid, Ester, Amine (1°/2°/3°), Amide, Nitrile, Nitro, Halogen, Sulfide, Thiol, Sulfoxide, Sulfone, Alkene, Alkyne, Aromatic Ring

### ✅ Phase 4: Ring & Aromaticity (v0.6.0)
- Enhanced ring detection, ring system analysis, Hückel aromaticity

### ✅ Phase 5: Substructure Search (v0.7.0)
- VF2 subgraph isomorphism: `has_subgraph_match()`, `find_subgraph_matches()`, `count_subgraph_matches()`
- Maximum common substructure (MCS) via backtracking
- SMARTS tokenizer/parser: `parse_smarts()`, `smarts_match()`, `smarts_findall()`, `smarts_count()`

### ✅ Phase 6: Stereochemistry (v0.8.0)
- CIP priority rules: `get_cip_priority()` with atomic number and isotope tie-breaking
- Tetrahedral detection: `is_chiral_center()`, `assign_tetrahedral()`, `detect_tetrahedral_centers()`
- Double bond stereochemistry: `is_stereogenic_double_bond()`, `assign_double_bond_stereo()`
- Perception pipeline: `perceive_stereochemistry()` combining tetrahedral and double bond detection

### ✅ Phase 7: Isomer Generation (v0.9.0)
- Alkane isomer enumeration: `generate_alkane_isomers(n)` for C1–C8 with canonical key dedup
- Alkane isomer counts: `alkane_isomer_count(n)` for known reference values
- Functional group variant enumeration: `enumerate_functional_group_isomers(n, element)`
- Stereoisomer enumeration: `enumerate_stereoisomers(graph)` with 2^N config generation

### ✅ Phase 8: Molecular Properties (v0.10.0)
- TPSA computation: fragment contributions for O, N, S polar groups
- logP computation: simplified atom-contribution model
- HBA/HBD counting: hydrogen bond acceptor/donor detection
- Rotatable bond counting, Fraction CSp3 computation

### ✅ Phase 9: Coordinate Generation (v0.11.0) — NEW
- **2D Force-Directed Layout**: Fruchterman-Reingold algorithm with ring template placement for 3–8 membered rings
- **Ring Detection**: DFS-based cycle detection for monocyclic and fused ring systems
- **3D Conformer Generation**: Distance geometry with bounds matrix, metric matrix embedding, and steepest descent energy minimization
- **Conformer Clustering**: RMSD-based greedy clustering with energy ranking
- **Bond Length Constraints**: C–C single/double/triple bond length enforcement in minimization
- **VDW Clash Avoidance**: Van der Waals radius-based non-bonded interaction penalties

### ✅ Phase 10: Rendering & Reactions (v0.12.0) — NEW
- **SVG Molecular Depiction**: Full SVG renderer with configurable bond length, atom colors, font sizes
- **Bond Rendering**: Single, double, triple, aromatic (dashed inner), wedge, and dashed wedge bonds
- **Atom Labels**: Element symbols with background circles, charge annotations, CPK-like element colors
- **Reaction Models**: `Reaction`, `ReactionComponent`, `ReactionCondition`, `ReactionArrow` dataclasses
- **Reaction Builder**: Fluent builder API for constructing reactions
- **Atom Balance Checking**: `is_balanced()` and `atom_count_difference()` methods
- **Reaction Templates**: 5 built-in templates (combustion, acid-base, esterification, dehydration, hydrogenation)
- **Reaction Serialization**: `to_dict()` for JSON export

### ✅ Phase 11: Nomenclature & IO (v0.13.0) — NEW
- **IUPAC Naming Engine**: Basic organic nomenclature for alkanes, alkenes, alkynes, alcohols, aldehydes, ketones, carboxylic acids, amines, nitriles, cycloalkanes, and halogenated compounds
- **Functional Group Detection**: Hydroxyl, carbonyl, carboxyl, amine, nitrile, halogen, alkene, alkyne detection
- **Longest Chain Detection**: DFS-based longest carbon chain finding for naming backbone
- **Substituent Naming**: Methyl, ethyl, propyl, butyl, halogen substituents with locants
- **JSON Serialization**: `graph_to_dict()`, `graph_to_json()`, `dict_to_graph()`, `json_to_graph()`
- **Format Conversion**: `convert_format()` supporting smiles, formula, json, name, dict targets
- **Coordinate Serialization**: 2D/3D coordinates and conformers included in serialized output

### ✅ Phase 12: Release (v1.0.0) — NEW
- **Comprehensive Test Suite**: 934 tests across 26 test files
- **AI Tool Interface**: 11 registered tools (parse_smiles, parse_formula, compute_property, validate, sanitize, detect_functional_groups, generate_2d_coordinates, generate_3d_conformer, render_svg, name_molecule, serialize)
- **Clean Package Structure**: All 15 packages complete with proper `__init__.py` exports
- **Version 1.0.0**: Production-ready release

---

## Test Suite Summary

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_core.py` | 22 | ✅ All pass |
| `test_formula.py` | 9 | ✅ All pass |
| `test_smiles.py` | 38 | ✅ All pass |
| `test_smiles_comprehensive.py` | 130 | ✅ All pass |
| `test_smiles_property.py` | 96 | ✅ 95 pass, 1 skip |
| `test_elements.py` | Multiple | ✅ All pass |
| `test_events.py` | 15 | ✅ All pass |
| `test_registry.py` | 14 | ✅ All pass |
| `test_plugin.py` | 8 | ✅ All pass |
| `test_datasets.py` | 14 | ✅ All pass |
| `test_api.py` | 21 | ✅ All pass |
| `test_rings.py` | 8 | ✅ All pass |
| `test_rings_enhanced.py` | 26 | ✅ All pass |
| `test_molecule.py` | 7 | ✅ All pass |
| `test_validation.py` | 59 | ✅ All pass |
| `test_functional_groups.py` | 55 | ✅ All pass |
| `test_substructure.py` | 24 | ✅ All pass |
| `test_stereochemistry.py` | 7 | ✅ All pass |
| `test_generation.py` | 9 | ✅ All pass |
| `test_properties.py` | 17 | ✅ All pass |
| `test_coordinates.py` | 31 | ✅ All pass |
| `test_rendering.py` | 28 | ✅ All pass |
| `test_reactions.py` | 28 | ✅ All pass |
| `test_nomenclature.py` | 26 | ✅ All pass |
| `test_io.py` | 26 | ✅ All pass |
| `test_coverage_low.py` | 143 | ✅ All pass |
| `test_coverage_critical.py` | 68 | ✅ All pass |
| `test_electron_config.py` | 47 | ✅ All pass |
| `test_smarts_comprehensive.py` + others | ~130 | ✅ All pass |
| **Total** | **1636** | **1635 pass, 1 skip** |

---

## Architecture Verification

| Principle | Status |
|-----------|--------|
| MolecularGraph is single source of truth | ✅ CONFIRMED |
| Domain models are immutable | ✅ CONFIRMED |
| Dependency direction (core → everything) | ✅ CONFIRMED |
| No circular imports | ✅ CONFIRMED |
| Plugin architecture | ✅ EXISTS |
| Event system | ✅ EXISTS |
| AI Tool interface | ✅ 13 tools registered (incl. `calculate_electron_configuration`) |

---

## Version 1.0.0 Scorecard

| Category | Status |
|----------|--------|
| Core Models | ✅ 100% |
| Infrastructure | ✅ 100% |
| Formula Parser | ✅ 100% |
| SMILES Parser | ✅ 100% |
| InChI Parser | ✅ 100% |
| Alias Resolver | ✅ 100% |
| Canonical SMILES | ✅ 85% |
| Ring Detection | ✅ 100% |
| Validation | ✅ 100% |
| Functional Groups | ✅ 100% |
| Ring Systems | ✅ 100% |
| Aromaticity | ✅ 100% |
| Substructure | ✅ 100% |
| Stereochemistry | ✅ 100% |
| Isomer Generation | ✅ 100% |
| Molecular Properties | ✅ 100% |
| Coordinate Generation | ✅ 100% |
| Rendering (SVG) | ✅ 100% |
| Reactions | ✅ 100% |
| Nomenclature (IUPAC) | ✅ 100% |
| IO (Serialization) | ✅ 100% |
| Atomic Chemistry (Electron Config) | ✅ 100% |
| **Overall** | **✅ 100%** |

```
Overall Health: ✅ EXCELLENT
  - Architecture:       ✅ Sound, well-documented
  - Core Implementation: ✅ Solid (all core modules complete)
  - Tests:              ✅ 1635 pass (1 skip)
  - All Packages:       ✅ 16/16 complete (no stubs)
  - Bug Status:         ✅ All pre-existing failures fixed
  - AI Interface:       ✅ 13 tools registered
  - New Features:       ✅ compounds/, education/ (electron config) modules added
  - Version:            ✅ 1.0.0
```
