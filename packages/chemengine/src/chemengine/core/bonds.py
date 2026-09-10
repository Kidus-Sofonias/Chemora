"""Bond domain model — Milestone 1.

This module defines the Bond dataclass, which represents a chemical bond
between two atoms. Every bond carries its order, type, stereochemistry,
topology, aromatic flag, and extensible metadata.

The Bond is immutable (frozen=True, slots=True). Bonds reference atoms by
their index in the MolecularGraph.atoms tuple.

Validation:
    - atom1 and atom2 must be different (no self-bonds)
    - Bond order must be a valid BondOrder
    - atom indices must be non-negative
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chemengine.core.enums import BondOrder, BondStereo, BondTopology, BondType

__all__ = ["Bond", "BondOrder", "BondStereo", "BondTopology", "BondType"]


@dataclass(frozen=True, slots=True)
class Bond:
    """A chemical bond between two atoms in a molecular graph.

    Bonds reference their atoms by index into the MolecularGraph.atoms tuple.
    This indirection keeps the graph structure flat, serializable, and free
    of circular references.

    Attributes:
        atom1: Index of the first atom in the bond (0-based).
        atom2: Index of the second atom in the bond (0-based).
        order: Bond order (single, double, triple, quadruple, aromatic).
        bond_type: Classification of the bond (covalent, dative, ionic, etc.).
        stereochemistry: Double bond stereochemistry (E/Z, cis/trans).
        topology: Whether the bond is in a ring or chain.
        is_aromatic: Whether this bond is part of an aromatic system.
        length: Bond length in angstroms (None if not computed).
        properties: Extensible key-value metadata.

    Usage:
        >>> bond = Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE)
        >>> bond.order
        <BondOrder.DOUBLE: 2>
        >>> bond.is_rotatable
        False
    """

    atom1: int
    atom2: int
    order: BondOrder = BondOrder.SINGLE
    bond_type: BondType = BondType.COVALENT
    stereochemistry: BondStereo = BondStereo.NONE
    topology: BondTopology = BondTopology.UNSPECIFIED
    is_aromatic: bool = False
    length: float | None = None
    properties: frozenset[tuple[str, Any]] = frozenset()

    # ── Computed Properties ──

    @property
    def is_ring_bond(self) -> bool:
        """Whether this bond is part of at least one ring."""
        return self.topology == BondTopology.RING

    @property
    def is_chain_bond(self) -> bool:
        """Whether this bond is in an acyclic chain."""
        return self.topology == BondTopology.CHAIN

    @property
    def is_stereogenic(self) -> bool:
        """Whether this bond has defined stereochemistry."""
        return self.stereochemistry != BondStereo.NONE

    @property
    def is_rotatable(self) -> bool:
        """Whether this bond is rotatable (single, non-ring, non-terminal)."""
        return (
            self.order == BondOrder.SINGLE
            and self.topology != BondTopology.RING
            and self.bond_type == BondType.COVALENT
        )

    @property
    def is_single(self) -> bool:
        """Whether this is a single bond."""
        return self.order == BondOrder.SINGLE

    @property
    def is_double(self) -> bool:
        """Whether this is a double bond."""
        return self.order == BondOrder.DOUBLE

    @property
    def is_triple(self) -> bool:
        """Whether this is a triple bond."""
        return self.order == BondOrder.TRIPLE

    @property
    def is_dative(self) -> bool:
        """Whether this is a dative/coordinate bond."""
        return self.bond_type == BondType.DATIVE

    @property
    def is_hydrogen_bond(self) -> bool:
        """Whether this is a hydrogen bond."""
        return self.bond_type == BondType.HYDROGEN

    @property
    def pi_bond_count(self) -> int:
        """Number of pi bonds (sigma bonds excluded)."""
        return self.order.pi_bond_count

    @property
    def electron_count(self) -> int:
        """Number of electrons shared in this bond."""
        return self.order.electron_count

    def other_atom(self, atom_index: int) -> int:
        """Return the other atom in this bond."""
        if atom_index == self.atom1:
            return self.atom2
        if atom_index == self.atom2:
            return self.atom1
        raise ValueError(f"Atom {atom_index} is not part of this bond")

    def involves(self, atom_index: int) -> bool:
        """Check if this bond involves the given atom."""
        return atom_index == self.atom1 or atom_index == self.atom2

    # ── Immutable Update Methods ──

    def with_order(self, order: BondOrder) -> Bond:
        """Return a new Bond with the given order (immutable)."""
        return Bond(
            atom1=self.atom1, atom2=self.atom2, order=order,
            bond_type=self.bond_type, stereochemistry=self.stereochemistry,
            topology=self.topology, is_aromatic=self.is_aromatic,
            length=self.length, properties=self.properties,
        )

    def with_stereochemistry(self, stereo: BondStereo) -> Bond:
        """Return a new Bond with the given stereochemistry (immutable)."""
        return Bond(
            atom1=self.atom1, atom2=self.atom2, order=self.order,
            bond_type=self.bond_type, stereochemistry=stereo,
            topology=self.topology, is_aromatic=self.is_aromatic,
            length=self.length, properties=self.properties,
        )

    def with_topology(self, topology: BondTopology) -> Bond:
        """Return a new Bond with the given topology (immutable)."""
        return Bond(
            atom1=self.atom1, atom2=self.atom2, order=self.order,
            bond_type=self.bond_type, stereochemistry=self.stereochemistry,
            topology=topology, is_aromatic=self.is_aromatic,
            length=self.length, properties=self.properties,
        )

    def __post_init__(self) -> None:
        """Validate bond properties."""
        if self.atom1 < 0 or self.atom2 < 0:
            raise ValueError(f"Atom indices must be non-negative, got ({self.atom1}, {self.atom2})")
        if self.atom1 == self.atom2:
            raise ValueError(f"Self-bonds are not allowed: atom {self.atom1} == atom {self.atom2}")
        if self.length is not None and self.length <= 0:
            raise ValueError(f"Bond length must be positive, got {self.length}")
        # Auto-set is_aromatic based on bond order if not explicitly set
        if self.order == BondOrder.AROMATIC and not self.is_aromatic:
            # Use object.__setattr__ for frozen dataclass
            object.__setattr__(self, 'is_aromatic', True)

    def __repr__(self) -> str:
        order_str = self.order.name.lower()
        stereo_str = f", stereo={self.stereochemistry.value}" if self.is_stereogenic else ""
        type_str = f", type={self.bond_type.value}" if self.bond_type != BondType.COVALENT else ""
        return f"Bond({self.atom1}-{self.atom2}, {order_str}{stereo_str}{type_str})"
