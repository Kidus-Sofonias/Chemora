"""Version-consistency guard (takeover audit, 2026-09-22).

The M33 CHANGELOG entry declared release 1.1.0 while ``pyproject.toml``
and ``chemengine.__version__`` still said 1.0.0, so the package built as
a version that contradicted its own changelog. These tests pin the three
published version surfaces together so they cannot drift apart again.
"""

from __future__ import annotations

import re
from pathlib import Path

import chemengine

_PKG_ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    """Return the version declared by pyproject.toml."""
    text = (_PKG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml must declare a project version"
    return match.group(1)


def _changelog_head_version() -> str:
    """Return the newest release heading in CHANGELOG.md."""
    text = (_PKG_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r'^## \[(\d+\.\d+\.\d+)\]', text, re.MULTILINE)
    assert match, "CHANGELOG.md must start with a release heading"
    return match.group(1)


def test_dunder_version_matches_pyproject() -> None:
    """chemengine.__version__ must equal the packaged version."""
    assert chemengine.__version__ == _pyproject_version()


def test_changelog_newest_release_matches_package_version() -> None:
    """The newest CHANGELOG release heading must match the package version."""
    assert _changelog_head_version() == chemengine.__version__
