"""Parser protocol — the contract for all chemical identifier parsers.
"""

from __future__ import annotations

import re
from typing import Any, cast
from typing import Protocol as TypingProtocol

from chemengine.core.graph import MolecularGraph


class Parser(TypingProtocol):
    """Protocol for chemical identifier parsers."""

    def parse(self, text: str, /, **options: Any) -> MolecularGraph:
        ...

    def serialize(self, graph: MolecularGraph, /, **options: Any) -> str:
        ...


def auto_detect_format(text: str) -> str | None:
    """Auto-detect format of a chemical identifier string."""
    text = text.strip()
    if not text:
        return None

    # InChIKey detection
    if re.match(r'^[A-Z]{14}-[A-Z]{10}-[A-Z]$', text):
        return "inchikey"

    # InChI detection
    if text.startswith("InChI=") or text.startswith("1/") or text.startswith("/"):
        return "inchi"

    # SMILES-specific characters
    smiles_special = {"=", "#", "@", "(", ")", "[", "]", "\\", "/"}
    has_smiles_chars = any(c in text for c in smiles_special)
    has_digits = bool(re.search(r'\d', text))

    # Formula detection (must have digits, no SMILES chars)
    if has_digits and not has_smiles_chars:
        formula_pat = re.compile(r'^[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*(?:\.[A-Z][a-z]?\d*)*$')
        if formula_pat.match(text):
            return "formula"
        # Has digits but not a formula -> likely SMILES (e.g., "c1ccccc1")
        return "smiles"

    # SMILES detection: special chars
    if has_smiles_chars:
        return "smiles"

    # Short all-letter strings starting with uppercase -> likely SMILES chain
    if text[0].isupper() and not has_digits and len(text) <= 10:
        if re.match(r'^[A-Z][a-z]?(?:[A-Z][a-z]?)*$', text):
            return "smiles"

    # Name detection
    if re.match(r"^[A-Za-z\s'-]+$", text) and len(text) >= 2:
        return "name"

    return None


def _get_registered_parser(domain: str) -> Any | None:
    """Try to get a parser function from the AlgorithmRegistry or by direct import.

    First attempts to find the parser in the global AlgorithmRegistry
    (which is populated when ChemEngineAPI is created). If the registry
    is empty or the algorithm is not found, falls back to importing
    the parser function directly from its module.

    Note: the formula parser fallback uses formula_to_graph (returns
    MolecularGraph) rather than parse_formula (returns dict).
    """
    # Try AlgorithmRegistry first (populated by ChemEngineAPI)
    try:
        from chemengine.core.registry import get_global_registry
        registry = get_global_registry()
        if registry.count > 0:  # Only try if registry is populated
            algo = registry.get(domain, "default")
            return algo.algorithm
    except (KeyError, ImportError):
        pass

    # Fallback: import parser functions that return MolecularGraph
    from chemengine.parsing.formula import formula_to_graph as _formula_to_graph
    from chemengine.parsing.inchi import parse_inchi as _parse_inchi
    from chemengine.parsing.smiles import parse_smiles as _parse_smiles

    _FALLBACK_PARSERS = {
        "parsing.smiles": _parse_smiles,
        "parsing.formula": _formula_to_graph,
        "parsing.inchi": _parse_inchi,
    }

    return _FALLBACK_PARSERS.get(domain)


def _get_registered_alias_resolver() -> Any | None:
    """Try to get the registered alias resolver."""
    # The alias resolver is a single function, not registered as an algorithm
    try:
        from chemengine.parsing.alias import resolve_alias_to_graph
        return resolve_alias_to_graph
    except ImportError:
        return None


def parse_any(
    text: str,
    *,
    smiles_parser: Any = None,
    formula_parser: Any = None,
    alias_resolver: Any = None,
    inchi_parser: Any = None,
    **options: Any,
) -> MolecularGraph:
    """Parse a chemical identifier by auto-detecting its format.

    Detects the format of the input string (SMILES, InChI, formula, name)
    and dispatches to the appropriate parser. When explicit parser arguments
    are not provided, attempts to discover them from the global
    AlgorithmRegistry and built-in modules.

    Args:
        text: The chemical identifier string.
        smiles_parser: Optional SMILES parser function. Auto-discovered if None.
        formula_parser: Optional formula parser function. Auto-discovered if None.
        alias_resolver: Optional alias resolver function. Auto-discovered if None.
        inchi_parser: Optional InChI parser function. Auto-discovered if None.
        **options: Additional options passed to the parser.

    Returns:
        A MolecularGraph.

    Raises:
        ValueError: If parsing fails with all available parsers.
    """
    # Auto-discover parsers if not explicitly provided
    if smiles_parser is None:
        smiles_parser = _get_registered_parser("parsing.smiles")
    if formula_parser is None:
        formula_parser = _get_registered_parser("parsing.formula")
    if inchi_parser is None:
        inchi_parser = _get_registered_parser("parsing.inchi")
    if alias_resolver is None:
        alias_resolver = _get_registered_alias_resolver()

    fmt = auto_detect_format(text)

    # InChIKey detection is reliable, but there is no InChIKey → structure
    # lookup in the engine (it would require a structure database). Fail
    # fast with a clear, accurate error instead of pretending to parse.
    if fmt == "inchikey":
        raise ValueError(
            f"Cannot parse '{text}': InChIKey-to-structure lookup is not "
            "supported by this engine. Provide the InChI string, SMILES, "
            "molecular formula, or a known chemical name instead."
        )

    # Try the detected format first. If that parser rejects the input,
    # fall through to the remaining parsers — detection is heuristic and
    # some strings are ambiguous (e.g. "Mg(OH)2" contains '(' which is
    # also a SMILES character).
    if fmt == "smiles" and smiles_parser is not None:
        try:
            return cast("MolecularGraph", smiles_parser(text, **options))
        except Exception:
            pass
    elif fmt == "name" and alias_resolver is not None:
        try:
            result = cast("MolecularGraph | None", alias_resolver(text))
            if result is not None:
                return result
        except Exception:
            pass
    elif fmt == "formula" and formula_parser is not None:
        try:
            return cast("MolecularGraph", formula_parser(text, **options))
        except Exception:
            pass
    elif fmt == "inchi" and inchi_parser is not None:
        try:
            return cast("MolecularGraph", inchi_parser(text, **options))
        except Exception:
            pass

    errors: list[str] = []
    if smiles_parser is not None:
        try:
            return cast("MolecularGraph", smiles_parser(text, **options))
        except Exception as e:
            errors.append(f"SMILES: {e}")
    if alias_resolver is not None:
        try:
            result = cast("MolecularGraph | None", alias_resolver(text))
            if result is not None:
                return result
        except Exception as e:
            errors.append(f"alias: {e}")
    if formula_parser is not None:
        try:
            return cast("MolecularGraph", formula_parser(text, **options))
        except Exception as e:
            errors.append(f"formula: {e}")
    if inchi_parser is not None:
        try:
            return cast("MolecularGraph", inchi_parser(text, **options))
        except Exception as e:
            errors.append(f"InChI: {e}")
    raise ValueError(
        f"Could not parse '{text}'. "
        f"Detected format: {fmt}. "
        f"Errors: {'; '.join(errors)}"
    )
