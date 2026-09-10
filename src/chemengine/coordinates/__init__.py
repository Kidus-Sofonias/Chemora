"""Coordinate generation — 2D layout and 3D conformer generation.

Modules:
    layout_2d: Force-directed 2D layout with ring template placement
    conformer_3d: Distance geometry 3D conformer generation and clustering
"""

from chemengine.coordinates.conformer_3d import (
    compute_conformer_energy,
    generate_conformer,
    generate_conformers,
)
from chemengine.coordinates.layout_2d import (
    force_directed_layout,
    generate_2d_coordinates,
)

__all__ = [
    "generate_2d_coordinates",
    "force_directed_layout",
    "generate_conformer",
    "generate_conformers",
    "compute_conformer_energy",
]
