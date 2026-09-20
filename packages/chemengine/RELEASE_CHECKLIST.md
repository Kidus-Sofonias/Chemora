# Release Checklist — ChemEngine

Step-by-step procedure for cutting a ChemEngine release. The repository
convention is trunk-based: every push to `master` runs the CI pipeline
(`.github/workflows/ci.yml`), and releases are tagged from `master` after
the full suite is green.

## 1. Pre-flight

- [ ] All planned changes are merged to `master`; working tree clean.
- [ ] CI is green on the release commit (all jobs: chemengine, backend,
      web, admin, chemengine-matrix, benchmark-regression, docs).
- [ ] No open P0/P1 issues against the package.

## 2. Version and changelog

- [ ] Update `version` in `packages/chemengine/pyproject.toml` and
      `__version__` in `packages/chemengine/src/chemengine/__init__.py`
      — the two must match (SemVer: MAJOR.MINOR.PATCH).
- [ ] Add a `CHANGELOG.md` entry under the new version heading
      (Keep-a-Changelog sections: Added / Changed / Fixed / Removed).
- [ ] If the API changed incompatibly, update the migration notes in the
      changelog entry.

## 3. Local verification (must all pass before tagging)

```bash
cd packages/chemengine

# Full test suite
python -m pytest tests -q

# Static checks (documented baselines in .github/workflows/ci.yml)
python -m ruff check src --no-fix
python -m mypy src/chemengine

# Documentation — warnings are errors
python -m sphinx -W -b html docs docs/_build/html

# Examples (all 12 must execute)
python scripts/verify_examples.py

# Benchmarks — compare against the saved baseline
python -m pytest benchmarks -o python_files="benchmark_*.py" \
    --benchmark-only --benchmark-save=release-check

# Build distributions
python -m build

# Metadata sanity
python -m twine check dist/*
```

Inspect `dist/` contents (sdist must contain README/LICENSE/docs sources;
wheel must contain only `chemengine/`) — see `DEPLOYMENT.md` section 5.

## 4. Tag and GitHub Release

- [ ] Commit the version bump: `build: bump chemengine to X.Y.Z`.
- [ ] Tag: `git tag -a vX.Y.Z -m "ChemEngine X.Y.Z" && git push origin vX.Y.Z`.
- [ ] Create the GitHub Release from the tag with the changelog section as
      the body (GitHub → Releases → Draft new release → choose tag → copy
      section → publish).
- [ ] Attach `dist/*` artifacts to the release.

## 5. Publish to PyPI

Prerequisite: a maintainer account on pypi.org (and test.pypi.org for
dry runs) with the `chemengine` name; store the API token as the
repository secret `PYPI_API_TOKEN` (TestPyPI: `TESTPYPI_API_TOKEN`).
**Never** put tokens in the repo, the CLI, or logs.

Dry run (TestPyPI):

```bash
python -m twine upload --repository testpypi dist/*
pip index versions --index-url https://test.pypi.org/simple/ chemengine
pip install --index-url https://test.pypi.org/simple/ chemengine==X.Y.Z
```

Production:

```bash
python -m twine upload dist/*
pip install chemengine==X.Y.Z   # verify from a fresh venv
```

Or trigger the `publish` workflow (`.github/workflows/publish.yml`) on the
release tag; it runs `twine check` + `twine upload` using
`PYPI_API_TOKEN`.

## 6. Post-release

- [ ] Verify `pip install chemengine==X.Y.Z` in a clean venv; run
      `python -c "import chemengine; print(chemengine.__version__)"`.
- [ ] Verify the docs build published for the new version.
- [ ] Announce (release notes link) and close the release issue.
- [ ] Record the release in `PROJECT_STATUS.md`.
