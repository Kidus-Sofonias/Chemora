"""IUPAC name parsing package (M33 Phase 11.4).

Modules:
    tokenizer: position-aware lexical tokenizer
    parser: grammar-subset parser producing molecular graphs
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chemengine.parsing.iupac.parser import NameParse, NameParseError, NameParser
from chemengine.parsing.iupac.tokenizer import TokenizationError, tokenize

if TYPE_CHECKING:
    from chemengine.core.graph import MolecularGraph


def parse_iupac_name(name: str) -> MolecularGraph:
    """Parse an IUPAC name of the supported grammar subset into a graph.

    Raises:
        NameParseError: position-aware error for malformed or unsupported
            names.
    """
    return NameParser().parse_to_graph(name)


__all__ = [
    "NameParse",
    "NameParseError",
    "NameParser",
    "TokenizationError",
    "parse_iupac_name",
    "tokenize",
]
