"""Geometry domain models — Milestone 1.

This module defines coordinate and conformer data structures used
for molecular coordinate representation. Coordinates are stored separately
from atoms in the MolecularGraph, enabling multiple conformers per molecule.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Coordinate2D:
    """A 2D coordinate in the molecular depiction plane.

    Attributes:
        x: X coordinate in angstroms.
        y: Y coordinate in angstroms.
    """

    x: float
    y: float

    def distance_to(self, other: Coordinate2D) -> float:
        """Euclidean distance to another 2D point."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def midpoint(self, other: Coordinate2D) -> Coordinate2D:
        """Midpoint between this point and another."""
        return Coordinate2D(
            (self.x + other.x) / 2.0,
            (self.y + other.y) / 2.0,
        )


@dataclass(frozen=True, slots=True)
class Coordinate3D:
    """A 3D coordinate in space.

    Attributes:
        x: X coordinate in angstroms.
        y: Y coordinate in angstroms.
        z: Z coordinate in angstroms.
    """

    x: float
    y: float
    z: float

    def distance_to(self, other: Coordinate3D) -> float:
        """Euclidean distance to another 3D point."""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def midpoint(self, other: Coordinate3D) -> Coordinate3D:
        """Midpoint between this point and another."""
        return Coordinate3D(
            (self.x + other.x) / 2.0,
            (self.y + other.y) / 2.0,
            (self.z + other.z) / 2.0,
        )

    def to_2d(self) -> Coordinate2D:
        """Project to 2D by dropping z-coordinate."""
        return Coordinate2D(self.x, self.y)


@dataclass(frozen=True, slots=True)
class Conformer:
    """A single 3D conformer (3D structure) of a molecule.

    Attributes:
        id: Unique identifier for this conformer within the molecule.
        coordinates: 3D coordinates for each atom (same order as MolecularGraph.atoms).
        energy: Potential energy of this conformer (kcal/mol).
        properties: Extensible metadata (RMSD, dihedrals, etc.).
    """

    id: int
    coordinates: tuple[Coordinate3D, ...]
    energy: float = 0.0
    properties: frozenset[tuple[str, Any]] = frozenset()

    @property
    def num_atoms(self) -> int:
        """Number of atoms with coordinates."""
        return len(self.coordinates)

    def get_distance(self, atom1: int, atom2: int) -> float:
        """Distance between two atoms in this conformer."""
        return self.coordinates[atom1].distance_to(self.coordinates[atom2])

    def rmsd(self, other: Conformer) -> float:
        """RMSD between this conformer and another (same number of atoms)."""
        if self.num_atoms != other.num_atoms:
            raise ValueError(f"Atom count mismatch: {self.num_atoms} vs {other.num_atoms}")
        sum_sq = sum(
            self.coordinates[i].distance_to(other.coordinates[i]) ** 2
            for i in range(self.num_atoms)
        )
        return math.sqrt(sum_sq / self.num_atoms)
