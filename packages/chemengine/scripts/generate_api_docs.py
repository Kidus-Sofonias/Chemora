"""Generate the autosummary API reference pages under docs/api/ (M32).

The pages are checked in so the Sphinx build is deterministic and works on
read-only checkouts. Re-run this script after adding public modules:

    python scripts/generate_api_docs.py

Subpackage pages include their public submodules automatically (excluding
``__init__`` indirection, which is merged into the package page).
"""

from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
API = DOCS / "api"
PKG = "chemengine"

# Subsystem -> human title (order matches docs/api/index.rst).
SUBSYSTEMS: dict[str, str] = {
    "": "Top-level package (facade exports)",
    "core": "Core — domain models, registry, events, plugins",
    "parsing": "Parsing — SMILES, InChI, formula, SMARTS, aliases",
    "detection": "Detection — rings, aromaticity, functional groups",
    "generation": "Generation — isomer and conformer enumeration",
    "stereochemistry": "Stereochemistry — CIP, R/S, E/Z perception",
    "properties": "Properties — molecular descriptors",
    "coordinates": "Coordinates — 2D layout and 3D conformers",
    "rendering": "Rendering — SVG depiction",
    "reactions": "Reactions — reaction models and validation",
    "validation": "Validation — rules, sanitize, reports",
    "io": "I/O — serialization and format conversion",
    "nomenclature": "Nomenclature — IUPAC name generation",
    "compounds": "Compounds — dynamic compound registry",
    "education": "Education — electron configurations, Lewis, stoichiometry",
    "datasets": "Datasets — reference element and isotope data",
    "utils": "Utils — caching, logging, benchmarking",
}


def public_submodules(subsystem: str) -> list[str]:
    """Public modules of a subsystem, discovered from the source tree."""
    src = DOCS.parents[1] / "src" / PKG
    base = src / subsystem if subsystem else src
    mods: list[str] = []
    for path in sorted(base.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        rel = path.with_suffix("").relative_to(src)
        mods.append(".".join(rel.parts))
    return mods


def page(subsystem: str, title: str) -> str:
    mod = f"{PKG}.{subsystem}" if subsystem else PKG
    lines = [title, "=" * len(title), ""]
    lines += [
        f"``{mod}``",
        "-" * (len(mod) + 4),
        "",
        # ``:no-index:`` keeps the autosummary stub pages (which document the
        # same objects) the canonical, indexed descriptions and avoids
        # duplicate-object warnings.
        ".. automodule:: " + mod,
        "   :members:",
        "   :show-inheritance:",
        "   :no-index:",
        "",
    ]
    if subsystem:
        subs = public_submodules(subsystem)
        if subs:
            lines += ["Submodules", "-----------", ""]
            lines += [".. autosummary::", "   :toctree: _autosum/" + subsystem, ""]
            lines += [f"   {PKG}.{m}" for m in subs]
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    API.mkdir(exist_ok=True)
    for subsystem, title in SUBSYSTEMS.items():
        mod = f"{PKG}.{subsystem}" if subsystem else PKG
        path = API / (mod + ".rst")
        path.write_text(page(subsystem, title), encoding="utf-8")
        print(f"wrote {path.relative_to(DOCS.parent)}")
    print(f"{len(SUBSYSTEMS)} API pages generated.")


if __name__ == "__main__":
    main()
