"""Stereochemistry domain models — Milestone 1.

This module defines the data structures for representing stereochemical
information in molecular graphs. It covers tetrahedral (sp3) stereocenters,
double bond (E/Z) stereochemistry, and provides a unified container.

Models:
    - ChiralCenter: A single tetrahedral or double-bond stereocenter.
    - StereoConfig: Complete stereochemical configuration for a molecule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chemengine.core.enums import BondStereo, ChiralTag, StereoCategory


@dataclass(frozen=True, slots=True)
class ChiralCenter:
    """A single stereocenter in a molecule.

    Can represent either a tetrahedral center (sp3) or a double-bond
    stereocenter (E/Z). The category field determines which type.

    Attributes:
        category: Type of stereocenter (tetrahedral, double_bond, etc.).
        atom_index: The atom index this center refers to (for tetrahedral).
        bond_index: The bond index this center refers to (for double bonds).
        chiral_tag: The R/S/r/s descriptor (for tetrahedral).
        bond_stereo: The E/Z/cis/trans descriptor (for double bonds).
        substituents: Ordered tuple of substituent atom indices or None.
            For tetrahedral: 4 substituents in CIP priority order.
            For double bonds: 4 substituents (a1_sub1, a1_sub2, a2_sub1, a2_sub2).
        properties: Extensible metadata.

    Usage:
        >>> center = ChiralCenter(
        ...     category=StereoCategory.TETRAHEDRAL,
        ...     atom_index=1,
        ...     chiral_tag=ChiralTag.R,
        ...     substituents=(0, 2, 3, None),
        ... )
        >>> center.is_tetrahedral
        True
    """

    category: StereoCategory
    atom_index: int | None = None
    bond_index: int | None = None
    chiral_tag: ChiralTag = ChiralTag.NONE
    bond_stereo: BondStereo = BondStereo.NONE
    substituents: tuple[int | None, ...] = ()
    properties: frozenset[tuple[str, Any]] = frozenset()

    @property
    def is_tetrahedral(self) -> bool:
        """Whether this is a tetrahedral stereocenter."""
        return self.category == StereoCategory.TETRAHEDRAL

    @property
    def is_double_bond(self) -> bool:
        """Whether this is a double-bond stereocenter."""
        return self.category == StereoCategory.DOUBLE_BOND

    @property
    def is_assigned(self) -> bool:
        """Whether stereochemistry has been assigned."""
        return self.chiral_tag != ChiralTag.NONE or self.bond_stereo != BondStereo.NONE


@dataclass(frozen=True, slots=True)
class StereoConfig:
    """Complete stereochemical configuration of a molecule.

    Stores all stereocenters and metadata about the assignment state.

    Attributes:
        centers: All stereocenters in the molecule.
        is_assigned: Whether stereochemistry has been fully assigned.
        assignment_method: Method used for assignment (e.g., 'cip', 'template').
    """

    centers: tuple[ChiralCenter, ...] = ()
    is_assigned: bool = False
    assignment_method: str = "unassigned"

    @property
    def count(self) -> int:
        """Total number of stereocenters."""
        return len(self.centers)

    @property
    def tetrahedral_centers(self) -> tuple[ChiralCenter, ...]:
        """All tetrahedral stereocenters."""
        return tuple(c for c in self.centers if c.is_tetrahedral)

    @property
    def double_bond_centers(self) -> tuple[ChiralCenter, ...]:
        """All double-bond stereocenters."""
        return tuple(c for c in self.centers if c.is_double_bond)

    @property
    def assigned_centers(self) -> tuple[ChiralCenter, ...]:
        """All assigned stereocenters."""
        return tuple(c for c in self.centers if c.is_assigned)

    @property
    def unassigned_centers(self) -> tuple[ChiralCenter, ...]:
        """All unassigned stereocenters."""
        return tuple(c for c in self.centers if not c.is_assigned)
