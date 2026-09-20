# Infrastructure

Release engineering for the Chemora monorepo.

- **`ci_check.py`** — local CI gate runner: executes the exact commands the
  GitHub workflow (`.github/workflows/ci.yml`) runs and exits non-zero when any
  required gate fails. Run with `venv/Scripts/python infrastructure/ci_check.py`.
- **`RELEASE.md`** — the release runbook: setup, required checks, PostgreSQL
  migration verification, AI provider verification, browser E2E, environment
  checklist, and the release procedure.

CI configuration itself lives in `.github/workflows/ci.yml` (push/PR to
`master`); this directory holds the local equivalents and documentation.
