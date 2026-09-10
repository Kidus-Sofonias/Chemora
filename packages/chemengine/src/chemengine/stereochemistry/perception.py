"""Stereo perception pipeline — auto-detect all stereocenters in a molecule."""

from __future__ import annotations

from chemengine.core.graph import MolecularGraph
from chemengine.core.stereo import ChiralCenter, StereoConfig
from chemengine.stereochemistry.double_bond import detect_double_bond_stereo
from chemengine.stereochemistry.tetrahedral import detect_tetrahedral_centers


def perceive_stereochemistry(graph: MolecularGraph) -> StereoConfig:
    """Perceive all stereochemistry in a molecular graph.

    Detects and assigns tetrahedral centers (R/S) and double bond
    stereochemistry (E/Z) where possible.

    Args:
        graph: The molecular graph.

    Returns:
        A StereoConfig with all detected stereocenters.
    """
    centers: list[ChiralCenter] = []

    # Detect tetrahedral centers
    tetra_centers = detect_tetrahedral_centers(graph)
    centers.extend(tetra_centers)

    # Detect double bond stereochemistry
    db_centers = detect_double_bond_stereo(graph)
    centers.extend(db_centers)

    return StereoConfig(
        centers=tuple(centers),
        is_assigned=len(centers) > 0,
        assignment_method="cip",
    )
