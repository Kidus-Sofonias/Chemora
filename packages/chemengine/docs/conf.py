"""Sphinx configuration for the ChemEngine API reference (M32 / Phase 15.2).

The reference is generated from the codebase's Google-style docstrings via
autodoc + napoleon. CI builds with ``sphinx-build -W`` so any documentation
warning breaks the build.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────
# Make ``chemengine`` importable when autodoc pulls docstrings. In the
# monorepo the package lives at src/chemengine; when installed
# (pip install -e packages/chemengine) sys.path is already correct and this
# entry is redundant but harmless.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# ── Project information ───────────────────────────────────────────────────
project = "ChemEngine"
copyright = "2026, Kidus Sofonias"
author = "Kidus Sofonias"

import chemengine  # noqa: E402  (path ensured above)

release = chemengine.__version__
version = ".".join(release.split(".")[:2])

# ── General configuration ─────────────────────────────────────────────────
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

# Note: sphinx.ext.intersphinx is intentionally NOT enabled. It requires
# network access to fetch remote inventories (docs.python.org), which the
# build environment may not have; with warnings-as-errors that would fail
# the build. Re-enable only if the build host is known to have network
# access and the mapping below is restored:
# intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The public API surface documented by this reference. Private helpers
# (leading underscore) are intentionally excluded.
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"
autodoc_typehints = "signature"

# Google-style docstrings (Phase 15.1 convention).
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_ivar = True

# Generate autosummary stub pages into the source tree (checked in so the
# build is deterministic and works on read-only checkouts).
autosummary_generate = True

# ── HTML output ───────────────────────────────────────────────────────────
html_theme = "sphinx_rtd_theme"
html_static_path = []
html_title = f"ChemEngine {release}"
html_show_sourcelink = False
