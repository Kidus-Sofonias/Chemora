"""Double bond E/Z and cis/trans stereochemistry assignment."""

from __future__ import annotations

from chemengine.core.bonds import BondOrder
from chemengine.core.enums import BondStereo
from chemengine.core.graph import MolecularGraph
from chemengine.core.stereo import ChiralCenter, StereoCategory


def _effective_substituent_count(graph: MolecularGraph, atom_idx: int,
                                 partner: int) -> int:
    """Count effective substituents including implicit hydrogens.

    Each explicit non-partner neighbor counts as 1.
    Implicit hydrogens (if any) count as additional substituents.
    If implicit_hydrogens is None, compute from valence rules.
    """
    atom = graph.atoms[atom_idx]
    explicit = [n for n in graph.get_neighbors(atom_idx) if n != partner
                and graph.atoms[n].atomic_number != 1]  # exclude H neighbors too
    n_explicit = len(explicit)

    # Count implicit hydrogens
    implicit_h = 0
    if atom.implicit_hydrogens is not None:
        implicit_h = atom.implicit_hydrogens
    else:
        # Compute from valence rules
        from chemengine.parsing.smiles import _compute_implicit_h
        implicit_h = _compute_implicit_h(graph, atom_idx)

    return n_explicit + implicit_h


def _get_effective_substituents(graph: MolecularGraph, atom_idx: int,
                                partner: int) -> list[tuple[int, int]]:
    """Get effective substituents as list of (atomic_number, isotope).

    Returns a list of (atomic_number, isotope) tuples representing the
    effective substituents of an atom, including implicit hydrogens
    (atomic_number=1, isotope=0).
    """
    result: list[tuple[int, int]] = []

    # Explicit non-H, non-partner neighbors
    for n in graph.get_neighbors(atom_idx):
        if n == partner:
            continue
        a = graph.atoms[n]
        if a.atomic_number == 1:
            continue  # explicit H neighbors
        result.append((a.atomic_number, a.isotope))

    # Add implicit hydrogens
    atom = graph.atoms[atom_idx]
    implicit_h = 0
    if atom.implicit_hydrogens is not None:
        implicit_h = atom.implicit_hydrogens
    else:
        from chemengine.parsing.smiles import _compute_implicit_h
        implicit_h = _compute_implicit_h(graph, atom_idx)

    for _ in range(implicit_h):
        result.append((1, 0))  # implicit H

    return result


def is_stereogenic_double_bond(graph: MolecularGraph, bond_index: int) -> bool:
    """Check if a double bond is stereogenic (can have E/Z isomers).

    A double bond is stereogenic if each atom has two distinct substituents.
    Implicit hydrogens are included as substituents where applicable.

    Args:
        graph: The molecular graph.
        bond_index: The bond index to check.

    Returns:
        True if the double bond is stereogenic.
    """
    bond = graph.bonds[bond_index]
    if bond.order != BondOrder.DOUBLE:
        return False

    a1, a2 = bond.atom1, bond.atom2

    # Get effective substituents (including implicit H)
    subs1 = _get_effective_substituents(graph, a1, a2)
    subs2 = _get_effective_substituents(graph, a2, a1)

    # Each atom must have at least 2 effective substituents
    if len(subs1) < 2 or len(subs2) < 2:
        return False

    # Each atom must have distinct substituents
    def _has_distinct(subs: list[tuple[int, int]]) -> bool:
        for i in range(len(subs)):
            for j in range(i + 1, len(subs)):
                if subs[i] != subs[j]:
                    return True
        return False

    if not _has_distinct(subs1) or not _has_distinct(subs2):
        return False

    return True


def assign_double_bond_stereo(graph: MolecularGraph,
                               bond_index: int) -> ChiralCenter | None:
    """Assign E/Z configuration to a double bond.

    Args:
        graph: The molecular graph.
        bond_index: The bond index.

    Returns:
        A ChiralCenter with E/Z assigned, or None if not stereogenic.
    """
    if not is_stereogenic_double_bond(graph, bond_index):
        return None

    bond = graph.bonds[bond_index]
    a1, a2 = bond.atom1, bond.atom2

    # Get substituents on each carbon
    s1 = [n for n in graph.get_neighbors(a1) if n != a2]
    s2 = [n for n in graph.get_neighbors(a2) if n != a1]

    # Determine highest priority substituent on each carbon
    def _highest_priority(nbrs: list[int]) -> int:
        """Return the substituent with highest atomic number."""
        return max(nbrs, key=lambda n: graph.atoms[n].atomic_number)

    h1 = _highest_priority(s1)
    h2 = _highest_priority(s2)

    # Check if highest priority substituents are on same side (Z) or opposite (E)
    # Use deeper neighbor graph comparison (CIP-consistent heuristic)
    #
    # Strategy: find the low-priority substituent on each carbon (l1, l2).
    # If h1 and h2 are connected (directly or via short path), they're
    # on the same side (Z). Otherwise they're on opposite sides (E).
    # This is more robust than the previous shared-neighbor heuristic
    # which failed for conjugated systems.
    other_s1 = [n for n in s1 if n != h1]
    other_s2 = [n for n in s2 if n != h2]
    l1 = other_s1[0] if other_s1 else None  # low priority on carbon 1
    l2 = other_s2[0] if other_s2 else None  # low priority on carbon 2

    # Check connectivity between high-priority substituents
    same_side = False
    if l1 is not None and l2 is not None:
        # High priority on same side if h1 connected to h2 (directly or via one intermediate)
        h1_nbrs = set(graph.get_neighbors(h1))
        h2_nbrs = set(graph.get_neighbors(h2))
        if h1 in h2_nbrs or h2 in h1_nbrs:
            same_side = True  # Directly connected
        else:
            # Check if connected through the low-priority neighbor
            # (cis = h1-l1 not bonded and h2-l2 not bonded means same side)
            if l1 not in h2_nbrs and l2 not in h1_nbrs:
                same_side = True
            else:
                same_side = False

    stereo = BondStereo.Z if same_side else BondStereo.E

    return ChiralCenter(
        category=StereoCategory.DOUBLE_BOND,
        bond_index=bond_index,
        bond_stereo=stereo,
        substituents=(s1[0] if s1 else None, s1[1] if len(s1) > 1 else None,
                      s2[0] if s2 else None, s2[1] if len(s2) > 1 else None),
    )


def detect_double_bond_stereo(graph: MolecularGraph) -> list[ChiralCenter]:
    """Detect and assign all stereogenic double bonds.

    Args:
        graph: The molecular graph.

    Returns:
        List of ChiralCenter objects for stereogenic double bonds.
    """
    centers: list[ChiralCenter] = []
    for i in range(graph.num_bonds):
        center = assign_double_bond_stereo(graph, i)
        if center is not None:
            centers.append(center)
    return centers
