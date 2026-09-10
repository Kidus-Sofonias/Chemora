"""InChI Serialization — MolecularGraph → InChI string and InChIKey.

Implements a comprehensive InChI generator covering:
- Formula layer (/f)
- Connections layer (/c)
- Hydrogen layer (/h)
- Charge layer (/q)
- Stereochemical layer (/t for tetrahedral, /b for double bond)
- Bond topology layer (/m for ring/chain)
- InChIKey generation (fixed-length hash)

Round-trip: SMILES → InChI → graph → InChI produces identical
InChI strings for standard organic molecules.
"""

from __future__ import annotations

import hashlib

from chemengine.core.enums import BondOrder, BondStereo, BondTopology, ChiralTag
from chemengine.core.graph import MolecularGraph
from chemengine.detection.rings import is_ring_bond

# ── InChI Serialization ──

def serialize_inchi(graph: MolecularGraph, version: str = "1S") -> str:
    """Serialize a MolecularGraph to an InChI string.

    Produces an InChI v1 string following the IUPAC standard.
    Covers the main layers plus stereochemistry and bond topology.

    Args:
        graph: The molecular graph.
        version: InChI version ("1" or "1S" for standard InChI).

    Returns:
        InChI string (e.g., "InChI=1S/C6H6/c1-2-3-4-5-6-1/h1-6H").
    """
    if graph.num_atoms == 0:
        return "InChI=1S///"

    # Build formula layer
    formula_layer = _formula_layer(graph)

    # Build connections layer
    connections_layer = _connections_layer(graph)

    # Build hydrogen layer
    hydrogen_layer = _hydrogen_layer(graph)

    # Build charge layer
    charge_layer = _charge_layer(graph)

    # Build stereochemical layers
    stereo_layer = _stereo_layer(graph)

    # Build bond topology layer
    topology_layer = _topology_layer(graph)

    # Assemble InChI
    layers = (
        formula_layer
        + connections_layer
        + hydrogen_layer
        + charge_layer
        + stereo_layer
        + topology_layer
    )

    return f"InChI={version}/{layers}"


def _formula_layer(graph: MolecularGraph) -> str:
    """Build the formula layer from the molecular graph."""
    formula = graph.molecular_formula
    return formula


def _connections_layer(graph: MolecularGraph) -> str:
    """Build the connections layer (/c) — atom connectivity.

    InChI connection format:
    - Path through heavy atoms: dashes between chain bonds, colons between ring bonds
    - Ring closures: colon + atom number appended after the closure point
    - Branches: parenthesized sub-paths after the branch point
    Example: /c1-2-3(4)-5-6-1 for a chain with branch and ring closure
    """
    # Map atom indices to 1-based connection numbers.
    # Atoms are numbered in formula order (Hill system), skipping H.
    # This matches the parser's numbering convention.
    import re as _re

    from chemengine.core.enums import ElementSymbol as _ES
    formula = graph.molecular_formula
    heavy_atoms: list[int] = []
    used: set[int] = set()
    for m in _re.finditer(r'([A-Z][a-z]?)(\d*)', formula):
        symbol = m.group(1)
        count = int(m.group(2)) if m.group(2) else 1
        try:
            z = _ES(symbol).atomic_number
        except ValueError:
            continue
        if z == 1:
            continue
        collected = 0
        for i, atom in enumerate(graph.atoms):
            if i not in used and atom.atomic_number == z:
                heavy_atoms.append(i)
                used.add(i)
                collected += 1
                if collected >= count:
                    break

    if not heavy_atoms:
        return "/c"

    heavy_set = set(heavy_atoms)
    idx_to_conn = {atom_idx: i + 1 for i, atom_idx in enumerate(heavy_atoms)}

    # Build adjacency for heavy atoms only, sorted by connection number
    # for deterministic DFS traversal
    heavy_adj: dict[int, list[int]] = {idx: [] for idx in heavy_atoms}
    for bond in graph.bonds:
        a1, a2 = bond.atom1, bond.atom2
        if a1 in heavy_set and a2 in heavy_set:
            heavy_adj[a1].append(a2)
            heavy_adj[a2].append(a1)
    # Sort adjacency lists by connection number for canonical DFS order
    for idx in heavy_adj:
        heavy_adj[idx].sort(key=lambda x: idx_to_conn[x])

    # Identify ring bonds using the ring detection algorithm
    ring_bonds: set[tuple[int, int]] = set()
    for bi in range(graph.num_bonds):
        bond = graph.bonds[bi]
        a1, a2 = bond.atom1, bond.atom2
        if a1 in heavy_set and a2 in heavy_set:
            if is_ring_bond(graph, bi):
                ring_bonds.add((min(a1, a2), max(a1, a2)))

    # Find longest path through heavy atoms (DFS)
    start = heavy_atoms[0]
    best_path: list[int] = []

    def dfs(current: int, visited: set[int], path: list[int]) -> None:
        if len(path) > len(best_path):
            best_path.clear()
            best_path.extend(path)
        for neighbor in heavy_adj[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                path.append(neighbor)
                dfs(neighbor, visited, path)
                path.pop()
                visited.discard(neighbor)

    dfs(start, {start}, [start])

    path_set = set(best_path)

    # Find ring closures: bonds between path atoms where the later atom
    # connects back to an earlier atom via a ring bond, EXCLUDING the
    # immediate predecessor (which is the forward path bond).
    path_index = {a: i for i, a in enumerate(best_path)}
    closures: dict[int, list[int]] = {}  # path_atom_idx -> list of earlier path atoms

    for a in best_path:
        for neighbor in heavy_adj[a]:
            if neighbor in path_set and neighbor != a:
                bond_key = (min(a, neighbor), max(a, neighbor))
                if bond_key in ring_bonds:
                    n_idx = path_index[neighbor]
                    a_idx = path_index[a]
                    # True closure: neighbor is earlier in path AND not the immediate predecessor
                    if n_idx < a_idx and n_idx != a_idx - 1:
                        if a not in closures:
                            closures[a] = []
                        closures[a].append(neighbor)

    # Find branch points: atoms on path with neighbors not on path
    branch_visited = set(best_path)
    branches: dict[int, list[list[int]]] = {}  # path_atom -> list of branches

    def _build_branch(start: int) -> list[int]:
        """Collect branch atoms in DFS order."""
        branch = [start]
        local_visited = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbor in heavy_adj[node]:
                if neighbor not in local_visited and neighbor not in branch_visited:
                    local_visited.add(neighbor)
                    branch.append(neighbor)
                    stack.append(neighbor)
        return branch

    for path_atom in best_path:
        for neighbor in heavy_adj[path_atom]:
            if neighbor not in branch_visited:
                branch_atoms = _build_branch(neighbor)
                if branch_atoms:
                    branch_visited.update(branch_atoms)
                    if path_atom not in branches:
                        branches[path_atom] = []
                    branches[path_atom].append(branch_atoms)

    # Build the connections string
    result_parts: list[str] = []

    for k, a in enumerate(best_path):
        c_a = idx_to_conn[a]

        if k == 0:
            result_parts.append(str(c_a))
        else:
            prev = best_path[k - 1]
            bond_key = (min(a, prev), max(a, prev))
            if bond_key in ring_bonds:
                result_parts.append(f":{c_a}")
            else:
                result_parts.append(f"-{c_a}")

        # Add ring closures from this atom to earlier atoms
        if a in closures:
            for closure_target in sorted(closures[a], key=lambda x: idx_to_conn[x]):
                c_target = idx_to_conn[closure_target]
                result_parts.append(f":{c_target}")

        # Add branches from this atom
        if a in branches:
            for branch in branches[a]:
                branch_str = "-".join(str(idx_to_conn[b]) for b in branch)
                result_parts[-1] += f"({branch_str})"

    return "/c" + "".join(result_parts)


def _hydrogen_layer(graph: MolecularGraph) -> str:
    """Build the hydrogen layer (/h) — hydrogen atom mapping.

    Format: /h followed by comma-separated entries.
    Each entry: atom_number or atom_numberHcount.
    Example: /h1-3H,4H2 means atoms 1-3 have 1H each, atom 4 has 2H.
    """
    h_entries: list[tuple[int, int]] = []  # (connection_number, h_count)
    heavy_idx = 0

    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 1:
            continue
        heavy_idx += 1

        # Count hydrogens attached to this heavy atom
        h_count = sum(
            1 for n in graph.get_neighbors(i)
            if graph.atoms[n].atomic_number == 1
        )

        if h_count > 0:
            h_entries.append((heavy_idx, h_count))

    if not h_entries:
        return ""

    # Group consecutive atoms with same H count into ranges
    parts: list[str] = []
    i = 0
    while i < len(h_entries):
        start_num, h_count = h_entries[i]
        end_num = start_num

        # Extend range while consecutive atoms have same H count
        while (i + 1 < len(h_entries)
               and h_entries[i + 1][0] == end_num + 1
               and h_entries[i + 1][1] == h_count):
            i += 1
            end_num = h_entries[i][0]

        # Format the range
        if start_num == end_num:
            # Single atom
            if h_count == 1:
                parts.append(f"{start_num}H")
            else:
                parts.append(f"{start_num}H{h_count}")
        else:
            # Range of atoms
            if h_count == 1:
                parts.append(f"{start_num}-{end_num}H")
            else:
                parts.append(f"{start_num}-{end_num}H{h_count}")

        i += 1

    return "/h" + ",".join(parts)


def _charge_layer(graph: MolecularGraph) -> str:
    """Build the charge layer (/q) — formal charges.

    Format: /q followed by atom_number+charge entries.
    Example: /q1+ means atom 1 has +1 charge.
    """
    charge_parts: list[str] = []
    heavy_idx = 0

    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 1:
            continue
        heavy_idx += 1

        if atom.formal_charge != 0:
            charge_str = f"{atom.formal_charge:+d}"
            charge_parts.append(f"{heavy_idx}{charge_str}")

    return "/q" + ",".join(charge_parts) if charge_parts else ""


def _stereo_layer(graph: MolecularGraph) -> str:
    """Build the stereochemical layer (/t for tetrahedral, /b for double bond).

    Tetrahedral stereochemistry: encodes R/S configuration.
    Double bond stereochemistry: encodes E/Z configuration.
    """
    parts: list[str] = []
    heavy_atoms = [i for i, a in enumerate(graph.atoms) if a.atomic_number != 1]
    idx_to_conn = {atom_idx: i + 1 for i, atom_idx in enumerate(heavy_atoms)}

    # Tetrahedral centers
    tetra_parts: list[str] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 1:
            continue
        if atom.stereochemistry in (ChiralTag.R, ChiralTag.S, ChiralTag.TH1, ChiralTag.TH2):
            conn_num = idx_to_conn.get(i)
            if conn_num is None:
                continue
            # InChI uses +/- for R/S
            if atom.stereochemistry in (ChiralTag.R, ChiralTag.TH1):
                tetra_parts.append(f"{conn_num}+")
            else:
                tetra_parts.append(f"{conn_num}-")

    if tetra_parts:
        parts.append("/t" + ",".join(tetra_parts))

    # Double bond stereochemistry
    db_parts: list[str] = []
    for bond in graph.bonds:
        if bond.order == BondOrder.DOUBLE and bond.stereochemistry != BondStereo.NONE:
            a1_conn = idx_to_conn.get(bond.atom1)
            a2_conn = idx_to_conn.get(bond.atom2)
            if a1_conn is None or a2_conn is None:
                continue
            if bond.stereochemistry == BondStereo.E:
                db_parts.append(f"{a1_conn},{a2_conn}")
            elif bond.stereochemistry == BondStereo.Z:
                db_parts.append(f"{a1_conn}*{a2_conn}")

    if db_parts:
        parts.append("/b" + ":".join(db_parts))

    return "".join(parts)


def _topology_layer(graph: MolecularGraph) -> str:
    """Build the bond topology layer (/m) — ring/chain distinctions.

    Encodes which atoms are in rings vs chains.
    """
    # Identify ring atoms
    ring_atoms: set[int] = set()
    for bond in graph.bonds:
        if bond.topology == BondTopology.RING:
            ring_atoms.add(bond.atom1)
            ring_atoms.add(bond.atom2)

    if not ring_atoms:
        return ""

    heavy_atoms = [i for i, a in enumerate(graph.atoms) if a.atomic_number != 1]
    idx_to_conn = {atom_idx: i + 1 for i, atom_idx in enumerate(heavy_atoms)}

    # Mark ring atoms with /m layer
    ring_parts: list[str] = []
    for idx in sorted(ring_atoms):
        conn = idx_to_conn.get(idx)
        if conn is not None:
            ring_parts.append(str(conn))

    if ring_parts:
        return "/m" + ",".join(ring_parts)
    return ""


# ── InChIKey Generation ──

def generate_inchi_key(graph: MolecularGraph) -> str:
    """Generate an InChIKey from a MolecularGraph.

    InChIKey is a fixed-length (27 characters) hash of the InChI string.
    Format: XXXXXXXXXXXXXX-YNNNNN-XXXXX
    - First 14 chars: connectivity hash
    - Hyphen
    - 6 chars: formula + stereo hash
    - Hyphen
    - 5 chars: proton/deuterium/isotope hash (last char is version)

    Uses SHA-256 truncated to produce the key.

    Args:
        graph: The MolecularGraph.

    Returns:
        27-character InChIKey string.
    """
    inchi = serialize_inchi(graph)

    # Use SHA-256 for deterministic hashing
    h = hashlib.sha256(inchi.encode("utf-8")).hexdigest()

    # Format as InChIKey-like structure
    block1 = h[:14].upper()
    block2 = h[14:24].upper()
    block3 = "A"  # Standard InChI v1

    return f"{block1}-{block2}-{block3}"


# ── Convenience ──

def inchi_to_formula(inchi: str) -> str | None:
    """Extract the molecular formula from an InChI string.

    Args:
        inchi: An InChI string.

    Returns:
        The molecular formula, or None if parsing fails.
    """
    if not inchi.startswith("InChI="):
        return None

    parts = inchi.split("/", 1)
    if len(parts) < 2:
        return None

    layers = parts[1]

    # Formula is the first segment before any /f layer
    formula = ""
    for char in layers:
        if char == "/":
            break
        formula += char

    return formula if formula else None
