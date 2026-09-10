"""Ring system analysis — fused, bridged, and spiro ring system detection.

A ring system is a set of rings that share atoms. The type of ring system
is determined by how the rings are connected:

    - **Fused rings**: Rings sharing 2+ adjacent atoms (share a bond).
      Examples: naphthalene (two 6-rings), decalin, indole.
    - **Spiro rings**: Rings sharing exactly 1 atom.
      Examples: spiro[3.3]heptane, spiro[4.5]decane.
    - **Bridged rings**: Rings sharing 2+ non-adjacent atoms, with at least
      one atom between the shared atoms. Examples: norbornane, adamantane.
    - **Isolated rings**: Rings that share no atoms with other rings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from chemengine.core.graph import MolecularGraph
from chemengine.core.substructure import Ring
from chemengine.detection.rings import detect_rings


class RingSystemType(Enum):
    """Classification of ring system connectivity."""

    ISOLATED = auto()
    """A single ring with no shared atoms."""

    FUSED = auto()
    """Two or more rings sharing 2+ adjacent atoms (a bond)."""

    SPIRO = auto()
    """Two or more rings sharing exactly 1 atom."""

    BRIDGED = auto()
    """Two or more rings sharing 2+ non-adjacent atoms."""

    COMPLEX = auto()
    """Multiple ring systems of mixed types."""


@dataclass(frozen=True, slots=True)
class RingSystem:
    """A connected set of rings forming a ring system.

    Attributes:
        rings: The rings in this system.
        system_type: Classification (fused, spiro, bridged, isolated, complex).
        atom_indices: All atoms that belong to this ring system.
        bond_indices: All bonds that belong to this ring system.
        num_rings: Number of rings in this system.
        num_atoms: Number of atoms in this system.
        properties: Extensible metadata.
    """

    rings: tuple[Ring, ...]
    system_type: RingSystemType = RingSystemType.ISOLATED
    atom_indices: tuple[int, ...] = ()
    bond_indices: tuple[int, ...] = ()
    properties: frozenset[tuple[str, Any]] = frozenset()

    @property
    def num_rings(self) -> int:
        return len(self.rings)

    @property
    def num_atoms(self) -> int:
        return len(self.atom_indices)

    @property
    def is_fused(self) -> bool:
        return self.system_type == RingSystemType.FUSED

    @property
    def is_spiro(self) -> bool:
        return self.system_type == RingSystemType.SPIRO

    @property
    def is_bridged(self) -> bool:
        return self.system_type == RingSystemType.BRIDGED

    @property
    def is_isolated(self) -> bool:
        return self.system_type == RingSystemType.ISOLATED

    @property
    def is_complex(self) -> bool:
        return self.system_type == RingSystemType.COMPLEX

    @property
    def is_aromatic(self) -> bool:
        """Whether all rings in this system are aromatic."""
        return all(r.is_aromatic for r in self.rings) if self.rings else False


def _shared_atom_count(ring_a: Ring, ring_b: Ring) -> int:
    """Count the number of atoms shared between two rings."""
    set_a = set(ring_a.atom_indices)
    set_b = set(ring_b.atom_indices)
    return len(set_a & set_b)


def _find_shared_bonds(graph: MolecularGraph, ring_a: Ring, ring_b: Ring) -> tuple[int, ...]:
    """Find bond indices shared between two rings."""
    atoms_a = set(ring_a.atom_indices)
    atoms_b = set(ring_b.atom_indices)
    shared_atoms = atoms_a & atoms_b

    if len(shared_atoms) < 2:
        return ()

    # Find bonds between shared atoms
    bond_indices: list[int] = []
    for j, bond in enumerate(graph.bonds):
        if bond.atom1 in shared_atoms and bond.atom2 in shared_atoms:
            bond_indices.append(j)

    return tuple(bond_indices)


def _determine_system_type(graph: MolecularGraph, rings: tuple[Ring, ...]) -> RingSystemType:
    """Determine the type of a ring system.

    Examines how rings are connected to classify the system.
    """
    if len(rings) == 1:
        return RingSystemType.ISOLATED

    # Check each pair of rings for shared atoms
    has_fused = False
    has_spiro = False
    has_bridged = False

    for i in range(len(rings)):
        for j in range(i + 1, len(rings)):
            shared = _shared_atom_count(rings[i], rings[j])

            if shared == 1:
                has_spiro = True
            elif shared >= 2:
                # Check if shared atoms are adjacent (fused) or non-adjacent (bridged)
                shared_bonds = _find_shared_bonds(graph, rings[i], rings[j])
                if shared_bonds:
                    has_fused = True
                else:
                    has_bridged = True

    # Determine the primary type (most specific first)
    if has_bridged and has_fused and has_spiro:
        return RingSystemType.COMPLEX
    if has_bridged:
        return RingSystemType.BRIDGED
    if has_fused:
        return RingSystemType.FUSED
    if has_spiro:
        return RingSystemType.SPIRO
    return RingSystemType.ISOLATED


def detect_ring_systems(graph: MolecularGraph) -> tuple[RingSystem, ...]:
    """Detect all ring systems in a molecular graph.

    Groups rings into connected systems (fused, spiro, bridged) and
    classifies each system.

    Args:
        graph: The molecular graph.

    Returns:
        Tuple of RingSystem objects, one per independent ring system.
    """
    rings = graph.rings if graph.rings else detect_rings(graph)
    if not rings:
        return ()

    # Build ring adjacency graph: two rings are adjacent if they share atoms
    n_rings = len(rings)
    ring_adj: list[list[int]] = [[] for _ in range(n_rings)]

    for i in range(n_rings):
        for j in range(i + 1, n_rings):
            if _shared_atom_count(rings[i], rings[j]) >= 1:
                ring_adj[i].append(j)
                ring_adj[j].append(i)

    # Find connected components in ring adjacency graph (ring systems)
    visited: set[int] = set()
    systems: list[RingSystem] = []

    for i in range(n_rings):
        if i in visited:
            continue

        # BFS to find all rings in this system
        component_rings: list[Ring] = []
        stack = [i]
        while stack:
            idx = stack.pop()
            if idx not in visited:
                visited.add(idx)
                component_rings.append(rings[idx])
                for neighbor in ring_adj[idx]:
                    if neighbor not in visited:
                        stack.append(neighbor)

        # Collect atoms and bonds for this system
        atoms: set[int] = set()
        bonds: set[int] = set()
        for ring in component_rings:
            atoms.update(ring.atom_indices)
            bonds.update(ring.bond_indices)

        components_tuple = tuple(component_rings)
        system_type = _determine_system_type(graph, components_tuple)

        systems.append(RingSystem(
            rings=components_tuple,
            system_type=system_type,
            atom_indices=tuple(sorted(atoms)),
            bond_indices=tuple(sorted(bonds)),
        ))

    return tuple(systems)


def is_spiro_center(graph: MolecularGraph, atom_index: int) -> bool:
    """Check if an atom is a spiro center (shared by two rings that share no
    other atoms).

    Args:
        graph: The molecular graph.
        atom_index: The atom index to check.

    Returns:
        True if the atom is a spiro center.
    """
    rings = graph.rings if graph.rings else detect_rings(graph)
    containing_rings: list[Ring] = []

    for ring in rings:
        if atom_index in ring.atom_indices:
            containing_rings.append(ring)

    if len(containing_rings) < 2:
        return False

    # Check that no two containing rings share any other atoms
    for i in range(len(containing_rings)):
        for j in range(i + 1, len(containing_rings)):
            shared = (set(containing_rings[i].atom_indices) &
                      set(containing_rings[j].atom_indices))
            if shared == {atom_index}:
                return True

    return False


def is_bridgehead_atom(graph: MolecularGraph, atom_index: int) -> bool:
    """Check if an atom is a bridgehead atom (shared by at least 3 rings in a
    bridged system, e.g., the tertiary carbons in norbornane).

    Args:
        graph: The molecular graph.
        atom_index: The atom index to check.

    Returns:
        True if the atom is a bridgehead atom.
    """
    rings = graph.rings if graph.rings else detect_rings(graph)
    count = sum(1 for ring in rings if atom_index in ring.atom_indices)
    return count >= 3
