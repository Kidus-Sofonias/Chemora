"""Cahn-Ingold-Prelog priority rules for stereochemistry assignment."""

from __future__ import annotations

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph


def _get_pi_count(graph: MolecularGraph, center: int, substituent: int) -> int:
    """Count the effective pi-bond attachments for a substituent (Rule 3).

    Multiple bonds count as multiple attachments to the same atom.
    E.g., a carbonyl oxygen =O counts as 3 attachments (one sigma + two pi).
    """
    pi_count = 0
    for nbr in graph.get_neighbors(substituent):
        if nbr == center:
            continue
        bond = graph.get_bond(substituent, nbr)
        if bond is not None:
            if bond.order == BondOrder.DOUBLE:
                pi_count += 1
            elif bond.order == BondOrder.TRIPLE:
                pi_count += 2
    return pi_count


def get_cip_priority(graph: MolecularGraph, center: int,
                     substituents: list[int]) -> list[int]:
    """Rank substituents around a stereocenter by CIP priority (highest = first).

    Priority rules (applied in order):
    1. Higher atomic number = higher priority
    2. Higher isotope mass = higher priority (if atomic numbers equal)
    3. Pi-bond connectivity: multiple bonds count as additional attachments
       (e.g., =O has higher priority than -OH at the same atomic number)
    4. Ring membership (fallback for complete tie-breaking)

    Args:
        graph: The molecular graph.
        center: The stereocenter atom index.
        substituents: List of substituent atom indices.

    Returns:
        Substituent indices sorted by priority (highest first).
    """
    if len(substituents) <= 1:
        return list(substituents)

    # Assign initial priorities
    scored: list[tuple[int, int, int, int, int, int]] = []
    for s in substituents:
        z = graph.atoms[s].atomic_number
        mass = int(graph.atoms[s].mass)
        pi = _get_pi_count(graph, center, s)
        # Ring membership: check if substituent is in a ring
        is_ring = 0
        for nbr in graph.get_neighbors(s):
            bond = graph.get_bond(s, nbr)
            if bond is not None and hasattr(bond, 'topology') and bond.topology == "ring":
                is_ring = 1
                break
        scored.append((0, z, mass, pi, is_ring, s))

    # Sort by: higher z first, then higher mass, then higher pi, then ring vs acyclic, then index
    scored.sort(key=lambda x: (-x[1], -x[2], -x[3], -x[4], x[5]))
    return [s[5] for s in scored]


def is_chiral_center(graph: MolecularGraph, atom_index: int) -> bool:
    """Check if an atom is a potential tetrahedral stereocenter.

    Criteria: sp3 carbon with 4 distinct substituents.

    Args:
        graph: The molecular graph.
        atom_index: The atom to check.

    Returns:
        True if the atom is a potential chiral center.
    """
    atom = graph.atoms[atom_index]
    # Must be carbon
    if atom.atomic_number != 6:
        return False
    # Must have 4 substituents
    neighbors = list(graph.get_neighbors(atom_index))
    if len(neighbors) != 4:
        return False
    # Must have distinct substituents (check for symmetry)
    # Count by element
    symbols = {graph.atoms[n].symbol for n in neighbors}
    if len(symbols) < 2:
        return False  # All same — cannot be chiral
    # Check for duplicate neighbors (same element, same environment)
    for i in range(len(neighbors)):
        for j in range(i + 1, len(neighbors)):
            n1, n2 = neighbors[i], neighbors[j]
            a1, a2 = graph.atoms[n1], graph.atoms[n2]
            if a1.atomic_number == a2.atomic_number:
                # Could still be distinct (different isotopes or environment)
                if a1.mass == a2.mass:
                    # Same element and mass — check deeper environment
                    n1_nbrs = set(graph.get_neighbors(n1)) - {atom_index}
                    n2_nbrs = set(graph.get_neighbors(n2)) - {atom_index}
                    n1_syms = {graph.atoms[x].symbol for x in n1_nbrs}
                    n2_syms = {graph.atoms[x].symbol for x in n2_nbrs}
                    if n1_syms == n2_syms:
                        return False  # Symmetric environment
    return True
