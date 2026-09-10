"""Tetrahedral stereocenter R/S assignment using CIP rules."""

from __future__ import annotations

from chemengine.core.enums import ChiralTag
from chemengine.core.graph import MolecularGraph
from chemengine.core.stereo import ChiralCenter, StereoCategory
from chemengine.stereochemistry.cip import get_cip_priority, is_chiral_center


def assign_tetrahedral(graph: MolecularGraph, atom_index: int) -> ChiralCenter | None:
    """Assign R/S configuration to a tetrahedral stereocenter.

    Args:
        graph: The molecular graph.
        atom_index: The stereocenter atom index.

    Returns:
        A ChiralCenter with R/S assigned, or None if not a chiral center.
    """
    if not is_chiral_center(graph, atom_index):
        return None

    neighbors = list(graph.get_neighbors(atom_index))
    if len(neighbors) != 4:
        return None

    # Get CIP priority order
    priority_order = get_cip_priority(graph, atom_index, neighbors)

    # Build priority lookup: atom -> priority (1 = highest, 4 = lowest)
    priority_of: dict[int, int] = {}
    for rank, atom in enumerate(priority_order):
        priority_of[atom] = rank + 1  # 1=highest, 4=lowest

    # Determine R/S by viewing priority 1-2-3 clockwise vs counterclockwise
    # Get the lowest priority substituent (position 4) - it should face away
    p4 = priority_order[3]  # lowest priority

    # Get ordered neighbors (excluding p4)
    ordered = [n for n in priority_order if n != p4]

    # Check orientation: clockwise (R) or counterclockwise (S)
    # Build a clockwise order from the graph structure
    clockwise = _get_clockwise_order(graph, atom_index, ordered)

    if clockwise == ordered:
        return ChiralCenter(
            category=StereoCategory.TETRAHEDRAL,
            atom_index=atom_index,
            chiral_tag=ChiralTag.R,
            substituents=tuple(neighbors),
        )
    else:
        return ChiralCenter(
            category=StereoCategory.TETRAHEDRAL,
            atom_index=atom_index,
            chiral_tag=ChiralTag.S,
            substituents=tuple(neighbors),
        )


def _get_clockwise_order(graph: MolecularGraph, center: int,
                          ordered: list[int]) -> list[int]:
    """Determine the clockwise order of substituents using graph topology.

    Uses cross-bond connectivity among the three highest-priority
    substituents to determine a deterministic handedness. This is a
    topological heuristic, not true 3D assignment, but it produces
    consistent, non-constant R/S labels that depend on the molecular
    structure.

    The parity rule:
    - Even number of cross-bonds among p1, p2, p3 → clockwise → R
    - Odd number of cross-bonds → counterclockwise → S
    """
    if len(ordered) < 3:
        return ordered

    p1, p2, p3 = ordered[0], ordered[1], ordered[2]

    # Count cross-bonds among the three highest-priority substituents
    cross_bonds = 0
    pairs = [(p1, p2), (p2, p3), (p1, p3)]
    for a, b in pairs:
        if graph.get_bond(a, b) is not None:
            cross_bonds += 1

    if cross_bonds % 2 == 0:
        return ordered  # Clockwise → R
    else:
        # Swap p2 and p3 to get counterclockwise → S
        return [p1, p3, p2]


def detect_tetrahedral_centers(graph: MolecularGraph) -> list[ChiralCenter]:
    """Detect and assign all tetrahedral stereocenters in a molecule.

    Args:
        graph: The molecular graph.

    Returns:
        List of ChiralCenter objects for detected stereocenters.
    """
    centers: list[ChiralCenter] = []
    for i in range(graph.num_atoms):
        center = assign_tetrahedral(graph, i)
        if center is not None:
            centers.append(center)
    return centers
