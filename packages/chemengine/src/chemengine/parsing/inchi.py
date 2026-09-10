"""InChI parser — parses IUPAC International Chemical Identifier strings
into MolecularGraph objects.

Supports the main InChI layers:
    - Chemical formula (/C6H6, /C2H6O, etc.)
    - Connections (/c1:2:3:4:5:6:1, /c1-2(3)-4, etc.)
    - Hydrogens (/h1-3H,4H2, etc.)
    - Charge (/q1+2, etc.)
    - Stereochemical (/t, /b) — recognized but not fully decoded
    - Bond topology (/m) — recognized but not fully decoded

This implementation focuses on the standard InChI format:
    InChI=1S/C6H6/c1:2:3:4:5:6:1/h1-6H
    InChI=1S/C2H6O/c1-2-3/h1H3,2H2,3H
"""

from __future__ import annotations

import re
from typing import Any

from chemengine.core.bonds import BondOrder
from chemengine.core.enums import ElementSymbol
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.parsing.protocol import Parser


def _parse_formula_layer(layer: str) -> dict[int, int]:
    """Parse the formula layer (e.g., 'C6H6' or 'C2H6O').

    Returns:
        Dict mapping atomic number to count.
    """
    counts: dict[int, int] = {}
    pattern = re.compile(r'([A-Z][a-z]?)(\d*)')
    for match in pattern.finditer(layer):
        symbol = match.group(1)
        count_str = match.group(2)
        count = int(count_str) if count_str else 1
        try:
            el = ElementSymbol(symbol)
            z = el.atomic_number
            counts[z] = counts.get(z, 0) + count
        except ValueError:
            raise ValueError(f"Unknown element in InChI formula: {symbol}")
    return counts


def _parse_formula_order(layer: str) -> list[tuple[str, int]]:
    """Parse formula layer preserving element order for InChI numbering.

    Returns:
        List of (symbol, count) in order of appearance.
    """
    result: list[tuple[str, int]] = []
    pattern = re.compile(r'([A-Z][a-z]?)(\d*)')
    for match in pattern.finditer(layer):
        symbol = match.group(1)
        count_str = match.group(2)
        count = int(count_str) if count_str else 1
        result.append((symbol, count))
    return result


def _parse_connections_layer(layer: str) -> list[tuple[int, int, bool]]:
    """Parse the connections layer (e.g., '1:2:3:4:5:6:1' or '1-2(3)-4').

    Handles:
    - Chain bonds: 1-2-3
    - Ring bonds: 1:2:3
    - Branches: 1-2(3)4
    - Ring closures: 1:2:3:4:5:6:1

    Returns:
        List of (atom1_num, atom2_num, is_ring) tuples.
        Atom numbers are 1-based (InChI convention).
    """
    if not layer:
        return []
    connections, _ = _parse_connections_recursive(layer, 0)
    return connections


def _parse_connections_recursive(
    text: str, start: int
) -> tuple[list[tuple[int, int, bool]], int]:
    """Parse connections recursively, handling branches.

    Returns (connections_list, end_position).
    """
    connections: list[tuple[int, int, bool]] = []
    i = start

    # Parse first atom
    num, i = _parse_number(text, i)
    if num is None:
        return connections, i

    prev_atom = num

    # Check for branch(es) immediately after the first atom
    while i < len(text) and text[i] == '(':
        branch_conns, i = _parse_branch(text, i, prev_atom, False)
        connections.extend(branch_conns)

    while i < len(text):
        c = text[i]

        if c == ')':
            return connections, i + 1

        if c in ('-', ':'):
            is_ring = (c == ':')
            i += 1

            # First parse the atom number after the separator
            num, i = _parse_number(text, i)
            if num is not None:
                connections.append((prev_atom, num, is_ring))
                prev_atom = num

            # Then check for branch group(s) after the atom
            while i < len(text) and text[i] == '(':
                branch_conns, i = _parse_branch(text, i, prev_atom, is_ring)
                connections.extend(branch_conns)
        else:
            i += 1

    return connections, i


def _parse_branch(
    text: str, start: int, parent: int, is_ring_to_parent: bool
) -> tuple[list[tuple[int, int, bool]], int]:
    """Parse a branch group like (3) or (3-4).

    Returns (connections, end_position).
    """
    i = start + 1  # skip '('
    connections: list[tuple[int, int, bool]] = []

    # Parse first atom in branch
    num, i = _parse_number(text, i)
    if num is None:
        return connections, i

    # Connect parent to branch atom
    connections.append((parent, num, is_ring_to_parent))
    prev_atom = num

    # Parse rest of branch
    while i < len(text):
        c = text[i]

        if c == ')':
            return connections, i + 1

        if c in ('-', ':'):
            is_ring = (c == ':')
            i += 1
            num, i = _parse_number(text, i)
            if num is not None:
                connections.append((prev_atom, num, is_ring))
                prev_atom = num
        else:
            i += 1

    return connections, i


def _parse_number(text: str, start: int) -> tuple[int | None, int]:
    """Parse an integer from text starting at position start.

    Returns (number, next_position) or (None, position) if no number found.
    """
    i = start
    while i < len(text) and text[i].isspace():
        i += 1

    if i >= len(text) or not text[i].isdigit():
        return None, i

    j = i
    while j < len(text) and text[j].isdigit():
        j += 1

    return int(text[i:j]), j


def _parse_hydrogens_layer(
    layer: str,
) -> dict[int, int]:
    """Parse the hydrogens layer (e.g., '1-3H,4H2').

    Format: comma-separated entries:
    - Range: 1-3H (atoms 1-3 each have 1 H)
    - Range with count: 1-3H2 (atoms 1-3 each have 2 H)
    - Single: 4H2 (atom 4 has 2 H)
    - Single with count: 4H (atom 4 has 1 H)

    Returns:
        Dict mapping 1-based InChI atom number to number of hydrogens.
    """
    h_counts: dict[int, int] = {}
    if not layer:
        return h_counts

    entries = layer.split(',') if ',' in layer else [layer]

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # Try range format: "1-3H" or "1-3H2"
        range_match = re.match(r'(\d+)-(\d+)H(\d*)', entry)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            h_str = range_match.group(3)
            h = int(h_str) if h_str else 1
            for idx in range(start, end + 1):
                h_counts[idx] = h
            continue

        # Try single atom: "4H2" or "4H"
        single_match = re.match(r'(\d+)H(\d*)', entry)
        if single_match:
            idx = int(single_match.group(1))
            h_str = single_match.group(2)
            h = int(h_str) if h_str else 1
            h_counts[idx] = h
            continue

    return h_counts


def _parse_charge_layer(layer: str) -> dict[int, int]:
    """Parse the charge layer (e.g., '1+2,3-1').

    Returns dict mapping 1-based atom number to charge.
    """
    charges: dict[int, int] = {}
    if not layer:
        return charges

    entries = layer.split(',') if ',' in layer else [layer]
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        charge_match = re.match(r'(\d+)([+-]\d+)', entry)
        if charge_match:
            idx = int(charge_match.group(1))
            charge = int(charge_match.group(2))
            charges[idx] = charge

    return charges


def parse_inchi(inchi: str) -> MolecularGraph:
    """Parse an InChI string into a MolecularGraph.

    Args:
        inchi: The InChI string.

    Returns:
        A MolecularGraph representing the molecule.

    Raises:
        ValueError: If parsing fails.
    """
    text = inchi.strip()
    if not text.startswith('InChI=') and not text.startswith('1/'):
        raise ValueError(f"Invalid InChI format: '{inchi}'")

    parts = text.split('/')
    if len(parts) < 2:
        raise ValueError(f"InChI too short: '{inchi}'")

    formula_layer = parts[1]

    # Parse layers by prefix character
    connections_layer = None
    hydrogens_layer = None
    charge_layer = None

    for part in parts[2:]:
        if part.startswith('c'):
            connections_layer = part[1:]
        elif part.startswith('h'):
            hydrogens_layer = part[1:]
        elif part.startswith('q'):
            charge_layer = part[1:]
        # Recognize but skip stereo/topology layers
        elif part.startswith('t') or part.startswith('b') or part.startswith('m'):
            pass

    # Parse formula and connections
    formula_order = _parse_formula_order(formula_layer)
    has_hydrogens_layer = hydrogens_layer is not None

    connections = []
    if connections_layer:
        connections = _parse_connections_layer(connections_layer)

    h_counts = _parse_hydrogens_layer(hydrogens_layer) if hydrogens_layer else {}
    charges = _parse_charge_layer(charge_layer) if charge_layer else {}

    # Collect all connection atom numbers from the connections layer
    conn_atom_nums: set[int] = set()
    for a1, a2, _ in connections:
        conn_atom_nums.add(a1)
        conn_atom_nums.add(a2)

    # Build graph: map InChI atom numbers to builder atom indices.
    # InChI numbering: non-H atoms are numbered 1, 2, 3... in order of
    # appearance in the formula layer. When hydrogens layer is present,
    # H atoms from the formula are NOT added to the graph (they're implicit).
    builder = MolecularGraphBuilder()
    atom_indices: dict[int, int] = {}  # InChI 1-based -> builder index
    inchi_num = 1  # InChI connection number counter

    for symbol, count in formula_order:
        try:
            el = ElementSymbol(symbol)
            z = el.atomic_number
        except ValueError:
            continue

        if has_hydrogens_layer and z == 1:
            # Skip H atoms — they'll be added from the hydrogens layer
            continue

        for _ in range(count):
            idx = builder.add_atom(atomic_number=z)
            atom_indices[inchi_num] = idx
            inchi_num += 1

    # Add bonds from connections layer
    for atom_num, nbr_num, is_ring in connections:
        if atom_num in atom_indices and nbr_num in atom_indices:
            a1 = atom_indices[atom_num]
            a2 = atom_indices[nbr_num]
            builder.add_bond(a1, a2, BondOrder.SINGLE)

    # Add hydrogens from hydrogens layer
    for inchi_atom_num, h_count in h_counts.items():
        if inchi_atom_num in atom_indices:
            parent_idx = atom_indices[inchi_atom_num]
            for _ in range(h_count):
                h_idx = builder.add_atom(atomic_number=1)
                builder.add_bond(parent_idx, h_idx, BondOrder.SINGLE)

    # Set charges
    for inchi_atom_num, charge in charges.items():
        if inchi_atom_num in atom_indices:
            idx = atom_indices[inchi_atom_num]
            old = builder._atoms[idx]
            builder._atoms[idx] = old.with_charge(charge)

    return builder.build()


class InChIParser(Parser):
    """Parser for InChI strings."""

    def parse(self, text: str, /, **options: Any) -> MolecularGraph:
        return parse_inchi(text)

    def serialize(self, graph: MolecularGraph, /, **options: Any) -> str:
        from chemengine.parsing.inchi_serializer import serialize_inchi
        return serialize_inchi(graph)


def register_inchi_parser(registry: Any) -> None:
    """Register the InChI parser with the AlgorithmRegistry."""
    from chemengine.core.registry import AlgorithmEntry

    parser = InChIParser()
    registry.register(AlgorithmEntry(
        domain="parsing.inchi",
        name="default",
        version="1.0.0",
        algorithm=parser.parse,
        input_type=str,
        output_type=MolecularGraph,
        tags=frozenset({"inchi", "parsing", "fast"}),
    ))
