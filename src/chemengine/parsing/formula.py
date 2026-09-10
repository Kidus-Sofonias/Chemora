"""Molecular formula parser — converts molecular formulas to MolecularGraph.

Implements a recursive, group-aware parser supporting:
    - Element symbols and counts (single and multi-digit)
    - Parenthesized groups with multipliers: Mg(OH)2, Fe2(SO4)3
    - Nested parentheses where chemically valid: Ca(Al(OH)4)2
    - Hydrates with dot separators and leading multipliers: CuSO4.5H2O
    - Charged formulas: NH4+, SO4 2-, Fe2+ (also '^' style: SO4^2-)
    - Whitespace between tokens

Isotope-prefixed formulas (e.g. "13CO2") are NOT part of the current
specification (see docs/SPECIFICATIONS.md) and are rejected.

Invalid syntax always raises FormulaParseError — no tokens are silently
discarded.
"""

from __future__ import annotations

import re
from typing import Any

from chemengine.core.bonds import BondOrder
from chemengine.core.enums import ElementSymbol
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.parsing.errors import FormulaParseError
from chemengine.parsing.protocol import Parser

# Regex matching any character that can be valid inside a formula.
_VALID_CHARS_RE = re.compile(r"[A-Za-z0-9().+\-\s^*]")


def _add_counts(
    target: dict[ElementSymbol, int],
    source: dict[ElementSymbol, int],
    multiplier: int = 1,
) -> None:
    """Add (multiplied) element counts from source into target."""
    for symbol, count in source.items():
        target[symbol] = target.get(symbol, 0) + count * multiplier


class _FormulaScanner:
    """Character scanner with position tracking for error reporting."""

    def __init__(self, text: str, formula: str) -> None:
        self.s = text
        self.i = 0
        self.formula = formula

    def peek(self) -> str:
        if self.i < len(self.s):
            return self.s[self.i]
        return ""

    def error(self, message: str) -> FormulaParseError:
        return FormulaParseError(message, pos=self.i, formula=self.formula)

    def skip_whitespace(self) -> None:
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def at_end(self) -> bool:
        return self.i >= len(self.s)


def _parse_element_symbol(scanner: _FormulaScanner) -> str:
    """Parse one element symbol (uppercase + optional lowercase)."""
    start = scanner.i
    ch = scanner.peek()
    if not (ch.isalpha() and ch.isupper()):
        if ch:
            raise scanner.error(f"Expected an element symbol, got '{ch}'")
        raise scanner.error("Expected an element symbol but reached end of formula")
    scanner.i += 1
    if scanner.i < len(scanner.s) and scanner.s[scanner.i].islower():
        scanner.i += 1
    return scanner.s[start:scanner.i]


def _parse_count(scanner: _FormulaScanner) -> int:
    """Parse an optional integer count. Returns 1 when absent.

    Counts must immediately follow the element/group (no whitespace).
    """
    start = scanner.i
    while scanner.i < len(scanner.s) and scanner.s[scanner.i].isdigit():
        scanner.i += 1
    if scanner.i == start:
        return 1
    return int(scanner.s[start:scanner.i])


def _parse_group_sequence(scanner: _FormulaScanner) -> dict[ElementSymbol, int]:
    """Parse a sequence of element/group tokens.

    Stops at ')' or end of input. Raises FormulaParseError on invalid syntax.
    """
    counts: dict[ElementSymbol, int] = {}
    while True:
        scanner.skip_whitespace()
        ch = scanner.peek()
        if ch == "" or ch in (")", "+", "-", "^", ".", "*"):
            break
        if ch == "*":
            # Transparent separator (some hydrate styles write CuSO4*5H2O)
            scanner.i += 1
            continue
        if ch == "(":
            scanner.i += 1
            inner = _parse_group_sequence(scanner)
            scanner.skip_whitespace()
            if scanner.peek() != ")":
                raise scanner.error("Unmatched '(' — expected ')'")
            scanner.i += 1
            mult = _parse_count(scanner)
            _add_counts(counts, inner, mult)
        elif ch.isupper():
            start = scanner.i
            symbol_str = _parse_element_symbol(scanner)
            try:
                symbol = ElementSymbol(symbol_str)
            except ValueError:
                raise FormulaParseError(
                    f"Unknown element symbol: '{symbol_str}'",
                    pos=start,
                    formula=scanner.formula,
                ) from None
            mult = _parse_count(scanner)
            _add_counts(counts, {symbol: 1}, mult)
        elif ch.isdigit():
            # A digit run separated by whitespace that is followed by a
            # sign belongs to a trailing charge (e.g. "Ca 2+", "SO4 2-").
            had_ws = scanner.i > 0 and scanner.s[scanner.i - 1].isspace()
            j = scanner.i
            while j < len(scanner.s) and scanner.s[j].isdigit():
                j += 1
            if had_ws and j < len(scanner.s) and scanner.s[j] in ("+", "-"):
                break
            raise scanner.error(
                "A count must immediately follow an element symbol or ')'"
            )
        else:
            raise scanner.error(f"Invalid character in formula: '{ch}'")
    return counts


def _parse_charge(scanner: _FormulaScanner) -> int:
    """Parse an optional trailing charge.

    Accepted forms: '+', '-2', '^2-', '^+', ' 2-' (digits then sign, or
    sign then digits, optionally preceded by '^' or whitespace).

    Returns the net charge as an integer (0 when absent).
    """
    scanner.skip_whitespace()
    if scanner.peek() == "^":
        scanner.i += 1
        scanner.skip_whitespace()
    ch = scanner.peek()
    if ch in ("+", "-"):
        sign = 1 if ch == "+" else -1
        scanner.i += 1
        return sign * _parse_count(scanner)
    # Digits followed by a sign: '^2-' already consumed '^'; a bare
    # digit-run here must be followed by a sign to be a charge.
    if ch.isdigit():
        start = scanner.i
        while scanner.i < len(scanner.s) and scanner.s[scanner.i].isdigit():
            scanner.i += 1
        magnitude = int(scanner.s[start:scanner.i])
        if scanner.peek() in ("+", "-"):
            sign = 1 if scanner.peek() == "+" else -1
            scanner.i += 1
            return sign * magnitude
        # Digits not followed by a sign — leave them; caller reports
        # trailing input.
        scanner.i = start
    return 0


def parse_formula_parts(formula: str) -> tuple[dict[ElementSymbol, int], int]:
    """Parse a molecular formula string into element counts and net charge.

    Supports:
        - Hill system: C5H12, C2H5OH, NaCl
        - Parenthesized groups with multipliers: Mg(OH)2, Fe2(SO4)3
        - Nested groups: Ca(Al(OH)4)2
        - Hydrates: CuSO4.5H2O, MgSO4.7H2O
        - Charged formulas: NH4+, SO42-, Fe3+, SO4^2-
        - Whitespace between tokens

    Args:
        formula: The molecular formula string.

    Returns:
        Tuple of (element counts dict, net charge int).

    Raises:
        FormulaParseError: If the formula is empty or syntactically invalid
            (unknown element, unmatched parentheses, invalid characters).
            Nothing is silently discarded.
    """
    if not formula or not formula.strip():
        raise FormulaParseError("Empty formula", formula=formula)

    # Reject characters that can never be valid in a formula.
    for idx, ch in enumerate(formula):
        if not _VALID_CHARS_RE.match(ch):
            raise FormulaParseError(
                f"Invalid character in formula: '{ch}'",
                pos=idx,
                formula=formula,
            )

    # '*' is accepted as a transparent hydrate separator (consumed in the
    # sequence parser); '^' introduces a charge suffix (handled by the
    # charge parser — it must NOT be stripped, otherwise "SO4^2-" would
    # merge "42" into the oxygen count).
    scanner = _FormulaScanner(formula, formula)

    # ── First (main) component: no leading multiplier ──
    component_counts = _parse_group_sequence(scanner)
    if not component_counts:
        raise scanner.error("Expected an element or '(' in formula")
    counts: dict[ElementSymbol, int] = {}
    _add_counts(counts, component_counts)

    # ── Hydrate components: each may carry a leading integer multiplier ──
    while True:
        scanner.skip_whitespace()
        if scanner.peek() not in (".", "*"):
            break
        scanner.i += 1
        scanner.skip_whitespace()
        digit_start = scanner.i
        mult = 1
        while scanner.i < len(scanner.s) and scanner.s[scanner.i].isdigit():
            scanner.i += 1
        if scanner.i > digit_start:
            mult = int(scanner.s[digit_start:scanner.i])
        component_counts = _parse_group_sequence(scanner)
        if not component_counts:
            raise scanner.error(
                "Expected an element or '(' after '.' in hydrate component"
            )
        _add_counts(counts, component_counts, mult)

    # ── Optional trailing charge ──
    charge = _parse_charge(scanner)

    # ── Nothing may remain ──
    scanner.skip_whitespace()
    if not scanner.at_end():
        raise scanner.error(
            f"Unexpected trailing input: '{scanner.s[scanner.i:scanner.i + 10]}'"
        )

    return counts, charge


def parse_formula(formula: str) -> dict[ElementSymbol, int]:
    """Parse a molecular formula string into an element-count dictionary.

    Supports:
        - Hill system: C5H12, C2H5OH, NaCl
        - Parenthesized groups with multipliers: Mg(OH)2, Fe2(SO4)3
        - Nested groups: Ca(Al(OH)4)2
        - Hydrates: CuSO4.5H2O
        - Charged formulas: NH4+, SO42-, Fe3+
        - Whitespace between tokens

    Args:
        formula: The molecular formula string.

    Returns:
        Dictionary mapping ElementSymbol to atom count.

    Raises:
        FormulaParseError: If the formula cannot be parsed. The error is a
            structured ValueError subclass carrying position information.
    """
    counts, _charge = parse_formula_parts(formula)
    return counts


def formula_to_graph(formula: str, name: str | None = None) -> MolecularGraph:
    """Convert a molecular formula string to a MolecularGraph.

    The element counts are exact. Graph connectivity for a bare formula is
    inherently ambiguous (a formula does not encode bonds), so a documented
    deterministic heuristic is used:

        - Hydrocarbon formulas: carbon chain (single bonds) with hydrogens
          distributed round-robin to satisfy the remaining valence of each
          carbon as far as the total hydrogen count allows.
        - Other formulas: hydrogens are bonded to heteroatoms round-robin;
          remaining heavy atoms are left disconnected (e.g. ionic salts).

    Use SMILES (via parse_any) when unambiguous connectivity is required.

    Args:
        formula: The molecular formula string.
        name: Optional name for the molecule.

    Returns:
        A MolecularGraph representing the formula.

    Raises:
        FormulaParseError: If the formula cannot be parsed.
    """
    counts, charge = parse_formula_parts(formula)
    if not counts:
        raise FormulaParseError(
            f"Could not parse formula: '{formula}' — no valid elements found",
            formula=formula,
        )
    builder = MolecularGraphBuilder()
    builder.set_name(name or formula)

    carbon_count = counts.get(ElementSymbol.C, 0)
    hydrogen_count = counts.get(ElementSymbol.H, 0)
    heavy_non_h = {
        s: n for s, n in counts.items() if s != ElementSymbol.H
    }

    if carbon_count == 0:
        # Non-carbon formula: add heavy atoms, then attach hydrogens to
        # heteroatoms round-robin (deterministic heuristic).
        hetero_indices: list[int] = []
        for symbol, count in sorted(heavy_non_h.items(), key=lambda kv: kv[0].name):
            z = symbol.atomic_number
            for _ in range(count):
                hetero_indices.append(
                    builder.add_atom(atomic_number=z, formal_charge=charge if not hetero_indices else 0)
                )
        # Track neighbor counts locally (deterministic round-robin).
        h_counts: dict[int, int] = {idx: 0 for idx in hetero_indices}
        for _ in range(hydrogen_count):
            h_idx = builder.add_atom(atomic_number=1)
            if hetero_indices:
                # Bond H to the heteroatom with the fewest current neighbors
                # (ties broken by insertion order via min()).
                target = min(hetero_indices, key=lambda idx: h_counts[idx])
                builder.add_bond(target, h_idx, BondOrder.SINGLE)
                h_counts[target] += 1
        return builder.build()

    # Hydrocarbon-containing formula: carbon chain + explicit hydrogens.
    carbon_atoms: list[int] = []
    for _ in range(carbon_count):
        c_idx = builder.add_atom(atomic_number=6)
        carbon_atoms.append(c_idx)

    # Add remaining heavy atoms (deterministic alphabetical order).
    other_heavy: list[int] = []
    for symbol, count in sorted(heavy_non_h.items(), key=lambda kv: kv[0].name):
        if symbol == ElementSymbol.C:
            continue
        z = symbol.atomic_number
        for _ in range(count):
            other_heavy.append(builder.add_atom(atomic_number=z))

    # Connect carbons in a chain.
    for i in range(len(carbon_atoms) - 1):
        builder.add_bond(carbon_atoms[i], carbon_atoms[i + 1], BondOrder.SINGLE)

    # Distribute hydrogens round-robin over carbons: in each pass, give every
    # carbon one hydrogen until the carbon has 4 bonds or hydrogens run out.
    # This yields chemically sensible valences for exact-match formulas
    # (CH4, C2H6, C2H4, C3H8, ...) and never exceeds a carbon's valence.
    remaining_h = hydrogen_count
    progress = True
    while remaining_h > 0 and progress:
        progress = False
        for c_idx in carbon_atoms:
            if remaining_h == 0:
                break
            neighbor_count = len(builder._bonds and [
                b for b in builder._bonds
                if b.atom1 == c_idx or b.atom2 == c_idx
            ])
            if neighbor_count < 4:
                h_idx = builder.add_atom(atomic_number=1)
                builder.add_bond(c_idx, h_idx, BondOrder.SINGLE)
                remaining_h -= 1
                progress = True

    # Any remaining hydrogens bond to heteroatoms round-robin, then any still
    # left over are added as isolated atoms.
    for _ in range(remaining_h):
        h_idx = builder.add_atom(atomic_number=1)
        if other_heavy:
            target = other_heavy.pop(0)
            other_heavy.append(target)
            builder.add_bond(target, h_idx, BondOrder.SINGLE)

    return builder.build()


class FormulaParser(Parser):
    """Parser for molecular formulas."""

    def parse(self, text: str, /, **options: Any) -> MolecularGraph:
        return formula_to_graph(text, options.get("name"))

    def serialize(self, graph: MolecularGraph, /, **options: Any) -> str:
        return graph.molecular_formula


def register_formula_parser(registry: Any) -> None:
    """Register the formula parser with the AlgorithmRegistry."""
    from chemengine.core.registry import AlgorithmEntry

    parser = FormulaParser()
    registry.register(AlgorithmEntry(
        domain="parsing.formula",
        name="default",
        version="1.0.0",
        algorithm=parser.parse,
        input_type=str,
        output_type=MolecularGraph,
        tags=frozenset({"formula", "parsing", "fast"}),
    ))
    registry.register(AlgorithmEntry(
        domain="serialization.formula",
        name="default",
        version="1.0.0",
        algorithm=parser.serialize,
        input_type=MolecularGraph,
        output_type=str,
        tags=frozenset({"formula", "serialization", "fast"}),
    ))
