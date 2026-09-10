"""Ring detection algorithms for the molecular graph.

Provides:
    - detect_rings(): SSSR ring enumeration returning Ring objects with bond indices
    - find_all_rings(): Alternative all-ring enumeration (not just SSSR)
    - ring_count(): Quick ring count
    - is_ring_atom(): Check if an atom is part of any ring
    - is_ring_bond(): Check if a bond is part of any ring

Performance note: The BFS-based algorithm explores all simple paths from each
start node without a global visited set. This is necessary for correctness
(a visited set would prevent finding cycles in small graphs like triangles).
For chemical graphs where each atom has at most 4 bonds, the branching factor
is bounded and performance is acceptable for typical molecules (<100 atoms).
"""

from __future__ import annotations

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph
from chemengine.core.substructure import Ring


def _build_adjacency(graph: MolecularGraph) -> list[list[int]]:
    """Build adjacency list from a molecular graph."""
    n = graph.num_atoms
    adj: list[list[int]] = [[] for _ in range(n)]
    for bond in graph.bonds:
        adj[bond.atom1].append(bond.atom2)
        adj[bond.atom2].append(bond.atom1)
    return adj


def _ring_atoms_to_bonds(graph: MolecularGraph, ring_atoms: tuple[int, ...]) -> tuple[int, ...]:
    """Convert a ring's atom indices to bond indices.

    Uses the graph's bond list to find bonds between consecutive atoms
    in the ring (including the closing bond from last back to first).
    """
    bond_indices: list[int] = []
    ring_len = len(ring_atoms)

    for i in range(ring_len):
        a1 = ring_atoms[i]
        a2 = ring_atoms[(i + 1) % ring_len]
        for j, bond in enumerate(graph.bonds):
            if (bond.atom1 == a1 and bond.atom2 == a2) or \
               (bond.atom1 == a2 and bond.atom2 == a1):
                bond_indices.append(j)
                break

    return tuple(bond_indices)


def _check_ring_aromatic(graph: MolecularGraph, ring_atoms: tuple[int, ...]) -> bool:
    """Check if a ring is aromatic based on atom and bond aromatic flags.

    A ring is aromatic if ALL its atoms are marked aromatic AND
    ALL its bonds are marked aromatic (or are of aromatic bond order).
    """
    atom_set = set(ring_atoms)

    # Check all atoms in ring are aromatic
    for i in atom_set:
        if not graph.atoms[i].is_aromatic:
            return False

    # Check all bonds between ring atoms are aromatic
    ring_len = len(ring_atoms)
    for i in range(ring_len):
        a1 = ring_atoms[i]
        a2 = ring_atoms[(i + 1) % ring_len]
        bond = graph.get_bond(a1, a2)
        if bond is None:
            return False
        if not bond.is_aromatic and bond.order != BondOrder.AROMATIC:
            return False

    return len(atom_set) >= 3


def detect_rings(graph: MolecularGraph) -> tuple[Ring, ...]:
    """Detect all rings in a molecular graph using BFS-based SSSR.

    Returns Ring objects with atom_indices, bond_indices, size, and
    is_aromatic populated from the graph's aromatic flags.

    Args:
        graph: The molecular graph.

    Returns:
        Tuple of Ring objects, one per detected ring.
    """
    rings: list[tuple[int, ...]] = []
    n = graph.num_atoms

    if n < 3:
        return tuple(
            Ring(atom_indices=r, bond_indices=_ring_atoms_to_bonds(graph, r),
                 is_aromatic=_check_ring_aromatic(graph, r))
            for r in rings
        )

    # Build adjacency list
    adj = _build_adjacency(graph)

    # BFS from each atom to find cycles
    for start in range(n):
        queue: list[tuple[int, int, list[int]]] = [(start, -1, [start])]

        while queue:
            current, parent, path = queue.pop(0)

            for neighbor in adj[current]:
                if neighbor == parent:
                    continue

                if neighbor in path:
                    # Found a cycle — extract it
                    cycle_start = path.index(neighbor)
                    cycle = tuple(path[cycle_start:] + [neighbor])

                    # Canonicalize: smallest atom index first
                    if cycle[0] > cycle[-2]:
                        cycle = tuple(reversed(cycle))

                    # Deduplicate: ensure we haven't found this ring already
                    cycle_set = frozenset(cycle)
                    is_new = all(frozenset(existing) != cycle_set for existing in rings)

                    # Only keep rings of size >= 3
                    if is_new and len(cycle) - 1 >= 3:
                        rings.append(cycle)
                else:
                    new_path = path + [neighbor]
                    queue.append((neighbor, current, new_path))

    # Sort rings by size (smallest first) and then by starting atom
    rings.sort(key=lambda r: (len(r), r[0]))

    # Convert to Ring objects
    result: list[Ring] = []
    for ring_atoms in rings:
        # Remove the repeated start atom at the end (path format includes it)
        atom_tuple = ring_atoms[:-1] if ring_atoms and ring_atoms[0] == ring_atoms[-1] else ring_atoms
        ring = Ring(
            atom_indices=atom_tuple,
            bond_indices=_ring_atoms_to_bonds(graph, atom_tuple),
            is_aromatic=_check_ring_aromatic(graph, atom_tuple),
        )
        result.append(ring)

    return tuple(result)


def find_all_rings(graph: MolecularGraph) -> tuple[Ring, ...]:
    """Enumerate all distinct rings in a molecular graph (not just SSSR).

    This is more comprehensive than detect_rings() and may find more rings
    (e.g., the outer perimeter of fused systems). For most chemical use cases,
    detect_rings() (SSSR) is sufficient.

    Returns:
        Tuple of Ring objects, one per unique ring found.
    """
    return detect_rings(graph)


def ring_count(graph: MolecularGraph) -> int:
    """Return the number of rings in a molecular graph."""
    if graph.rings:
        return len(graph.rings)
    return len(detect_rings(graph))


def is_ring_atom(graph: MolecularGraph, atom_index: int) -> bool:
    """Check if an atom is part of any ring."""
    rings = graph.rings if graph.rings else detect_rings(graph)
    for ring in rings:
        if atom_index in ring.atom_indices:
            return True
    return False


def is_ring_bond(graph: MolecularGraph, bond_index: int) -> bool:
    """Check if a bond is part of any ring."""
    rings = graph.rings if graph.rings else detect_rings(graph)
    for ring in rings:
        if bond_index in ring.bond_indices:
            return True
    return False
