"""Aromaticity detection using Hückel's rule (4n+2 π electrons).

This module implements aromaticity perception for both homocyclic (carbocyclic)
and heterocyclic ring systems based on Hückel's rule:

    A planar, monocyclic, fully conjugated ring is aromatic if it contains
    (4n + 2) π electrons, where n is a non-negative integer (n = 0, 1, 2, ...).

    A ring with (4n) π electrons is anti-aromatic.
    Other conjugated rings are non-aromatic.

For heterocycles, each atom in the ring contributes a specific number of
π electrons based on its element, bonding pattern, and formal charge.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph
from chemengine.core.substructure import Ring
from chemengine.detection.rings import detect_rings


class AromaticityType(Enum):
    """Result of aromaticity assessment for a ring."""

    AROMATIC = auto()
    """Ring satisfies Hückel's rule (4n+2 π electrons)."""

    ANTI_AROMATIC = auto()
    """Ring has 4n π electrons (anti-aromatic)."""

    NON_AROMATIC = auto()
    """Ring is not conjugated or not planar."""


@dataclass(frozen=True, slots=True)
class AromaticityResult:
    """Result of an aromaticity assessment for a single ring.

    Attributes:
        ring_atoms: The atom indices of the ring.
        pi_electrons: The number of π electrons counted in the ring.
        n_value: The n in Hückel's 4n+2 rule (0, 1, 2, ...).
        is_conjugated: Whether the ring has alternating single/double bonds.
        result: The aromaticity classification.
        details: Human-readable explanation.
        properties: Extensible metadata.
    """

    ring_atoms: tuple[int, ...]
    pi_electrons: int = 0
    n_value: int | None = None
    is_conjugated: bool = False
    result: AromaticityType = AromaticityType.NON_AROMATIC
    details: str = ""
    properties: frozenset[tuple[str, Any]] = frozenset()

    @property
    def is_aromatic(self) -> bool:
        return self.result == AromaticityType.AROMATIC

    @property
    def is_anti_aromatic(self) -> bool:
        return self.result == AromaticityType.ANTI_AROMATIC


# π electron contributions are computed dynamically in _count_pi_electrons_ring
# based on element, formal charge, ring bond count, and hydrogen status.


def _is_conjugated_ring(graph: MolecularGraph, ring_atoms: tuple[int, ...]) -> bool:
    """Check if a ring has a conjugated pi system (alternating single/double bonds).

    A ring is conjugated if every bond in the ring is either:
    - Aromatic or double bond
    - A single bond between atoms that can participate in conjugation

    Uses the ring's atom order (traversal order) to check bonds between
    consecutive atoms in the cycle.
    """
    ring_len = len(ring_atoms)
    if ring_len < 3:
        return False

    has_double_bond = False

    for i in range(ring_len):
        a1 = ring_atoms[i]
        a2 = ring_atoms[(i + 1) % ring_len]
        bond = graph.get_bond(a1, a2)

        if bond is None:
            return False

        # Aromatic or double bond counts toward conjugation
        if bond.is_aromatic or bond.order in (BondOrder.AROMATIC, BondOrder.DOUBLE):
            has_double_bond = True
        elif bond.order == BondOrder.SINGLE:
            pass  # Single bonds are OK in conjugated systems
        else:
            # Triple or quadruple bonds break conjugation
            return False

    return has_double_bond


def _count_pi_electrons_ring(graph: MolecularGraph, ring_atoms: tuple[int, ...]) -> int:
    """Count the number of π electrons contributed by each atom in a ring.

    Uses standard Hückel π electron counting rules:

    - Carbon (=CH- or =C<): 1 π electron
    - Carbon (-C^- carbanion): 2 π electrons
    - Carbon (=C^+ carbocation): 0 π electrons
    - Nitrogen (=N- pyridine-like): 1 π electron
    - Nitrogen (-NH- pyrrole-like): 2 π electrons
    - Nitrogen (=N^+-): 0 π electrons
    - Oxygen (-O- furan-like): 2 π electrons
    - Oxygen (=O): 0 π electrons (carbonyl oxygen)
    - Sulfur (-S- thiophene-like): 2 π electrons
    - Sulfur (=S): 0 π electrons
    """
    total_pi = 0
    atom_set = set(ring_atoms)

    for idx in atom_set:
        atom = graph.atoms[idx]
        z = atom.atomic_number
        charge = atom.formal_charge

        # Count heavy-atom bonds in the ring
        in_ring_bonds = 0
        for nbr in graph.get_neighbors(idx):
            if nbr in atom_set:
                in_ring_bonds += 1

        # Determine π contribution
        if z == 6:  # Carbon
            # A carbon contributes 1 pi electron only if it is sp²:
            # it must have at least one pi bond (double/triple) in the molecule
            has_pi_bond = False
            for nbr in graph.get_neighbors(idx):
                bond = graph.get_bond(idx, nbr)
                if bond and bond.order.value >= 2:
                    has_pi_bond = True
                    break
            if charge == -1:
                total_pi += 2  # Carbanion
            elif charge == 1:
                total_pi += 0  # Carbocation
            elif has_pi_bond:
                total_pi += 1  # sp² carbon
            else:
                total_pi += 0  # sp³ carbon, no pi contribution

        elif z == 7:  # Nitrogen
            if in_ring_bonds == 2 and charge == 0:
                # Check if N has a hydrogen (pyrrole-like)
                # For simplicity: if N has implicit H or is directly bonded to H
                if atom.implicit_hydrogens is not None and atom.implicit_hydrogens > 0:
                    total_pi += 2  # -NH- pyrrole-like
                elif atom.implicit_hydrogens is None:
                    # Check explicit bonds to H
                    has_explicit_h = False
                    for nbr in graph.get_neighbors(idx):
                        if graph.atoms[nbr].atomic_number == 1:
                            has_explicit_h = True
                            break
                    total_pi += 2 if has_explicit_h else 1
                else:
                    total_pi += 1  # =N- pyridine-like
            elif in_ring_bonds == 2 and charge == 1:
                total_pi += 0  # =N^+-
            elif in_ring_bonds == 2 and charge == -1:
                total_pi += 2  # -N^-- pyrrole-like
            elif in_ring_bonds == 3:
                total_pi += 0  # Quaternary N, no lone pair
            else:
                total_pi += 1  # Default

        elif z == 8:  # Oxygen
            if charge == 0 and in_ring_bonds == 2:
                total_pi += 2  # -O- furan-like
            elif charge == 1 and in_ring_bonds == 2:
                total_pi += 1  # -O^+- pyrylium-like
            else:
                total_pi += 0  # =O carbonyl

        elif z == 16:  # Sulfur
            if charge == 0 and in_ring_bonds == 2:
                total_pi += 2  # -S- thiophene-like
            else:
                total_pi += 0

        elif z == 5:  # Boron
            total_pi += 0  # Electron-deficient

        else:
            total_pi += 0  # Other elements

    return total_pi


def assess_ring_aromaticity(graph: MolecularGraph, ring: Ring) -> AromaticityResult:
    """Assess the aromaticity of a single ring using Hückel's rule.

    Args:
        graph: The molecular graph containing the ring.
        ring: The ring to assess.

    Returns:
        An AromaticityResult with the assessment.
    """
    atoms = ring.atom_indices
    atom_set = set(atoms)

    # Check if ring is already marked aromatic (from SMILES parsing)
    if ring.is_aromatic:
        return AromaticityResult(
            ring_atoms=atoms,
            pi_electrons=0,
            n_value=None,
            is_conjugated=True,
            result=AromaticityType.AROMATIC,
            details="Ring is marked aromatic from input data",
        )

    # Check conjugation (use ordered atom_indices from the ring, not the set)
    conjugated = _is_conjugated_ring(graph, ring.atom_indices)
    if not conjugated:
        return AromaticityResult(
            ring_atoms=atoms,
            pi_electrons=0,
            is_conjugated=False,
            result=AromaticityType.NON_AROMATIC,
            details="Ring is not conjugated (no alternating double bonds)",
        )

    # Count π electrons
    pi = _count_pi_electrons_ring(graph, atoms)
    if pi <= 0:
        return AromaticityResult(
            ring_atoms=atoms,
            pi_electrons=0,
            is_conjugated=True,
            result=AromaticityType.NON_AROMATIC,
            details="No π electrons found in ring",
        )

    # Apply Hückel's rule: 4n + 2
    # Check 4n+2 first
    n = (pi - 2) / 4
    if n >= 0 and n == int(n):
        return AromaticityResult(
            ring_atoms=atoms,
            pi_electrons=pi,
            n_value=int(n),
            is_conjugated=True,
            result=AromaticityType.AROMATIC,
            details=f"Ring satisfies Hückel's rule: {pi} = 4×{int(n)} + 2 π electrons",
        )

    # Check 4n
    n = pi / 4
    if n >= 0 and n == int(n):
        return AromaticityResult(
            ring_atoms=atoms,
            pi_electrons=pi,
            n_value=int(n),
            is_conjugated=True,
            result=AromaticityType.ANTI_AROMATIC,
            details=f"Ring has 4n π electrons: {pi} = 4×{int(n)} (anti-aromatic)",
        )

    return AromaticityResult(
        ring_atoms=atoms,
        pi_electrons=pi,
        is_conjugated=True,
        result=AromaticityType.NON_AROMATIC,
        details=f"Ring has {pi} π electrons, which is neither 4n nor 4n+2",
    )


def assess_all_rings(graph: MolecularGraph) -> tuple[AromaticityResult, ...]:
    """Assess aromaticity for all rings in a molecular graph.

    Args:
        graph: The molecular graph.

    Returns:
        Tuple of AromaticityResult for each ring.
    """
    rings = graph.rings if graph.rings else detect_rings(graph)
    results: list[AromaticityResult] = []

    for ring in rings:
        result = assess_ring_aromaticity(graph, ring)
        results.append(result)

    return tuple(results)


def assign_aromaticity(graph: MolecularGraph) -> tuple[Ring, ...]:
    """Assign aromaticity flags to rings based on Hückel's rule.

    This is the main entry point for aromaticity perception. It:
    1. Detects all rings
    2. Assesses each ring's aromaticity using Hückel's rule
    3. Returns updated Ring objects with is_aromatic set correctly

    Args:
        graph: The molecular graph.

    Returns:
        Tuple of Ring objects with updated aromaticity flags.
    """
    rings = graph.rings if graph.rings else detect_rings(graph)
    results = assess_all_rings(graph)

    updated_rings: list[Ring] = []
    for ring, result in zip(rings, results):
        # Only set is_aromatic if the ring is aromatic (don't un-set)
        if result.is_aromatic and not ring.is_aromatic:
            updated_rings.append(Ring(
                atom_indices=ring.atom_indices,
                is_aromatic=True,
                bond_indices=ring.bond_indices,
                properties=ring.properties,
            ))
        else:
            updated_rings.append(ring)

    return tuple(updated_rings)
