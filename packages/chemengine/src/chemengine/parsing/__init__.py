"""Parsing subsystem — converts chemical identifiers to MolecularGraph objects.

Architecture:
    - protocol.py: Parser Protocol, auto_detect_format, parse_any
    - smiles.py: SMILES parser and writer
    - canonical.py: Canonical SMILES generation
    - inchi.py: InChI parser
    - formula.py: Molecular formula parser
    - alias.py: Common name resolver
    - errors.py: Position-aware parsing errors
"""

from chemengine.parsing.alias import resolve_alias, resolve_alias_to_graph
from chemengine.parsing.canonical import canonical_smiles, is_canonical
from chemengine.parsing.errors import (
    SmilesError,
    SmilesSyntaxError,
    SmilesValidationError,
    UnclosedBracketError,
    UnmatchedBranchError,
    UnmatchedRingClosureError,
)
from chemengine.parsing.formula import formula_to_graph, parse_formula
from chemengine.parsing.inchi import parse_inchi
from chemengine.parsing.protocol import Parser, auto_detect_format, parse_any
from chemengine.parsing.smiles import parse_smiles, serialize_smiles

__all__ = [
    "Parser",
    "auto_detect_format",
    "parse_any",
    "parse_smiles",
    "serialize_smiles",
    "parse_formula",
    "formula_to_graph",
    "resolve_alias",
    "resolve_alias_to_graph",
    "parse_inchi",
    "canonical_smiles",
    "is_canonical",
    "SmilesError",
    "SmilesSyntaxError",
    "SmilesValidationError",
    "UnclosedBracketError",
    "UnmatchedRingClosureError",
    "UnmatchedBranchError",
]
