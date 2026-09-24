"""chemengine — A production-grade chemistry engine.

The Molecular Graph is the single source of truth for all chemistry operations.
Every atom, bond, charge, isotope, stereocenter, coordinate, and property
derives from this graph.

Architecture overview:
    - core/         : Immutable domain models (MolecularGraph, Atom, Bond, etc.)
                      and infrastructure (AlgorithmRegistry, EventBus, PluginManager)
    - parsing/      : Input parsers (SMILES, InChI, formula, IUPAC, aliases)
    - generation/   : Isomer and conformer enumeration
    - detection/    : Substructure, ring, aromaticity, functional group detection
    - stereochemistry/ : R/S, E/Z, cis/trans assignment
    - properties/   : Molecular property computation
    - coordinates/  : 2D and 3D coordinate generation
    - rendering/    : SVG/PNG molecular depiction and themes
    - reactions/    : Reaction models, mapping, validation, and templates
    - validation/   : Graph sanitization and validity rules
    - io/           : Serialization and format conversion
    - nomenclature/ : IUPAC naming (graph -> name), common names, tautomers
    - datasets/     : Reference data (elements, isotopes, forcefield params)
    - utils/        : Logging, benchmarking, caching

Public API is loaded lazily (PEP 562 ``__getattr__``) so that
``import chemengine`` stays lightweight (M33 Phase 15.6: first import
<100 ms measured as a plain ``import chemengine`` in a fresh process);
the chemistry machinery loads on first attribute access instead. All
names below are resolvable exactly as before::

    from chemengine import ChemEngineAPI, MolecularGraph
"""

from __future__ import annotations

from typing import Any

_LAZY_EXPORTS: dict[str, str] = {
    "ChemEngineAPI": "chemengine.core.tool_interface",
    "MolecularGraph": "chemengine.core.graph",
    "MolecularGraphBuilder": "chemengine.core.graph",
    "Atom": "chemengine.core.atoms",
    "Bond": "chemengine.core.bonds",
    "BondOrder": "chemengine.core.bonds",
    "ElementSymbol": "chemengine.core.enums",
    "ChiralTag": "chemengine.core.enums",
    "BondStereo": "chemengine.core.enums",
}

__all__ = sorted([*_LAZY_EXPORTS, "__version__"])

# Version stays module-level: Sphinx (docs/conf.py) and packaging tooling read
# it at import time without triggering the lazy machinery.
__version__ = "1.2.0"


def __getattr__(name: str) -> Any:
    """Resolve lazily-loaded public API names (PEP 562)."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_path)
    attr = getattr(module, name)
    globals()[name] = attr  # cache for subsequent accesses
    return attr


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
