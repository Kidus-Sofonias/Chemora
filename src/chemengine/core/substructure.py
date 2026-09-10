"""Substructure domain models — FunctionalGroup and Ring.

These models are used by the detection subsystem for representing detected
structural features in a molecular graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FunctionalGroup:
    """A detected functional group in a molecule.

    Attributes:
        name: Group name (e.g., 'Alcohol', 'Ketone').
        smarts: SMARTS pattern that matched.
        atom_indices: Indices of atoms in the matching.
        priority: Match priority (higher = more specific).
        categories: Categories this group belongs to.
    """

    name: str
    smarts: str
    atom_indices: tuple[int, ...]
    priority: int = 0
    categories: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Ring:
    """A detected ring in a molecular graph.

    Attributes:
        atom_indices: Indices of atoms forming the ring (in traversal order).
        size: Number of atoms in the ring.
        is_aromatic: Whether the ring is aromatic.
        bond_indices: Indices of bonds forming the ring.
        properties: Extensible metadata.
    """

    atom_indices: tuple[int, ...]
    is_aromatic: bool = False
    bond_indices: tuple[int, ...] = ()
    properties: frozenset[tuple[str, Any]] = frozenset()

    @property
    def size(self) -> int:
        return len(self.atom_indices)

    @property
    def is_three_membered(self) -> bool:
        return self.size == 3

    @property
    def is_four_membered(self) -> bool:
        return self.size == 4

    @property
    def is_five_membered(self) -> bool:
        return self.size == 5

    @property
    def is_six_membered(self) -> bool:
        return self.size == 6
