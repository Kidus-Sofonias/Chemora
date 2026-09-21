"""Common / trivial name dictionary (M33 Phase 11.3).

A curated, auditable mapping of common chemical names to structures. The
single source of truth is :data:`chemengine.parsing.alias._COMMON_ALIASES`
(the name-resolution table used by :func:`chemengine.parsing.alias.
resolve_alias_to_graph`); this module exposes it read-only, validates every
entry by round-tripping its target SMILES through the real SMILES parser,
and records the honest entry count.

The dictionary is deliberately **curated, not exhaustive**: the roadmap's
"1000+ names" is a long-term goal, and this module reports the actual
delivered count rather than padding the table to hit a number.
"""

from __future__ import annotations

from chemengine.parsing.alias import _COMMON_ALIASES

__all__ = ["COMMON_NAMES_COUNT", "common_names", "validate_common_names"]

# Honest, machine-checked count of curated entries (not a target).
COMMON_NAMES_COUNT: int = len(_COMMON_ALIASES)


def common_names() -> dict[str, str]:
    """Return a copy of the common-name dictionary (name -> SMILES)."""
    return dict(_COMMON_ALIASES)


def validate_common_names() -> list[str]:
    """Parse every dictionary target through the real SMILES parser.

    Returns:
        Names whose target SMILES failed to parse (expected to be empty;
        used by the test suite as an audit of dictionary integrity).
    """
    from chemengine.parsing.smiles import parse_smiles

    broken: list[str] = []
    for name, smiles in _COMMON_ALIASES.items():
        try:
            parse_smiles(smiles)
        except Exception:  # noqa: BLE001 - audit must survive bad entries
            broken.append(name)
    return broken
