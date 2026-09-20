# Deployment — ChemEngine & Chemora

"Deployment" means different things for the ChemEngine *library* and the
Chemora *product*. This document states exactly what exists today and how
each mode is used. Nothing here is aspirational: if a mode is not
described, it does not exist.

## 1. Library usage (pip install)

ChemEngine is an in-process Python library with no services, no database,
and no network access.

```bash
pip install chemengine              # runtime
pip install "chemengine[viz]"       # + matplotlib extras
pip install "chemengine[ml]"        # + numpy/scipy extras
```

```python
from chemengine import ChemEngineAPI

chem = ChemEngineAPI()
mol = chem.parse("CCO")
print(chem.compute(mol, "weight"))
```

Requirements: Python 3.10–3.13 (the CI matrix verifies all four). The
runtime dependency set is `structlog` only; `viz`/`ml` extras are optional.

Embedding in web services: import it like any library (the Chemora
backend does exactly this — see section 4). ChemEngine holds no global
mutable state that requires per-process isolation; instances of
`ChemEngineAPI` are cheap and not thread-shared by design.

## 2. Development

From the monorepo root:

```bash
python -m venv venv
venv/Scripts/activate            # Windows (bash: source venv/Scripts/activate)
pip install -e "packages/chemengine[dev]"
```

Everyday commands (run from `packages/chemengine/`):

| Purpose            | Command |
|--------------------|---------|
| Tests              | `python -m pytest tests -q` |
| Benchmarks         | `python -m pytest benchmarks -o python_files="benchmark_*.py" --benchmark-only` |
| Lint               | `python -m ruff check src --no-fix` |
| Type check         | `python -m mypy src/chemengine` |
| Docs (strict)      | `python -m sphinx -W -b html docs docs/_build/html` |
| Examples           | `python scripts/verify_examples.py` |
| Regenerate API pages | `python scripts/generate_api_docs.py` |

See `../CONTRIBUTING.md` for the full workflow and
`RELEASE_CHECKLIST.md` for releasing.

## 3. Library release (PyPI + GitHub Release)

The complete procedure lives in `RELEASE_CHECKLIST.md`. Summary:
bump version (pyproject + `__init__.py`) → changelog → full local
verification → `python -m build && python -m twine check dist/*` →
tag `vX.Y.Z` → GitHub Release → `twine upload` (credentials via
repository secrets, never the working tree).

## 4. Chemora product deployment (what actually exists)

The Chemora product is the monorepo's other half: a FastAPI backend
(`backend/`), a React web client (`apps/web/`), and an admin client
(`apps/admin/`). ChemEngine is consumed by the backend as the
deterministic chemistry authority (parsing, properties, explorer
endpoints, and the AI tutor's tool allowlist).

Verified components and their deployment-relevant facts:

- **Backend**: FastAPI + SQLAlchemy (PostgreSQL in production; the full
  Alembic migration chain is verified against real PostgreSQL by
  `backend/scripts/pg_verify.py`). Health endpoints: `GET /health`
  (liveness) and `GET /health/ready` (readiness: DB connectivity and
  AI-provider configuration state — no secrets in responses).
- **Frontends**: static production builds (`npm run build` in `apps/web`
  and `apps/admin`) served by any static host / CDN behind the API.
- **CI**: every push to `master` runs the full pipeline
  (`.github/workflows/ci.yml`): ChemEngine tests + static baselines +
  Python 3.10–3.13 matrix + benchmark regression + docs, backend
  tests/ruff/mypy, web and admin tests/tsc/builds.

There is **no** official Docker image, Kubernetes manifest, or hosted
deployment yet — production deployment procedures for the Chemora
product are part of future milestones, not this package.

## 5. Package artifacts (what ships)

`python -m build` produces:

- `chemengine-X.Y.Z.tar.gz` — sdist: source tree, README, LICENSE,
  `pyproject.toml`.
- `chemengine-X.Y.Z-py3-none-any.whl` — wheel: the `chemengine` package
  plus package metadata. `chemengine-1.0.0.dist-info/` carries the
  license text (`chemengine-1.0.0.dist-info/licenses/LICENSE`) and the
  README is included via the `readme` key.

Both artifacts pass `python -m twine check dist/*`. The wheel contains
only `chemengine/` — no tests, benchmarks, docs, or repository files.
