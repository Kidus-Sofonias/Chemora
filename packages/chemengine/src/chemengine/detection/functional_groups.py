"""Functional group detection engine.

Detects all standard functional groups from functional_groups.toml using
graph-based pattern matching on MolecularGraph. Supports:
    - 21+ functional group detectors (alcohol, ketone, amide, etc.)
    - Overlap detection and priority-based resolution
    - Category-based hierarchy (parent/child relationships)
    - Dataset-driven group definitions

Design:
    Each functional group has a detector function that examines the molecular
    graph's atoms, bonds, and connectivity to find matching substructures.
    Matches are scored by priority (higher = more specific). When multiple
    groups overlap on the same atoms, the highest-priority group wins.

    The detection is based on direct graph traversal rather than SMARTS
    pattern matching (the SMARTS engine is Phase 5). Each detector encodes
    its own structural logic using the MolecularGraph API.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
#  Result Types
# ════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class FunctionalGroupMatch:
    """A detected functional group match.

    Attributes:
        name: Group name (e.g., 'Alcohol', 'Ketone').
        smarts: SMARTS-like pattern string from the dataset.
        atom_indices: Indices of atoms involved in the group.
        priority: Match priority (higher = more specific).
        categories: Category tags for this group.
        parent: Optional parent group name (for hierarchy).
    """

    name: str
    smarts: str
    atom_indices: tuple[int, ...]
    priority: int = 0
    categories: tuple[str, ...] = ()
    parent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "smarts": self.smarts,
            "atom_indices": list(self.atom_indices),
            "priority": self.priority,
            "categories": list(self.categories),
            "parent": self.parent,
        }


# ════════════════════════════════════════════════════════════════
#  Hierarchy & Categories
# ════════════════════════════════════════════════════════════════

# Parent-child relationships for functional group hierarchy.
# When a child group is detected, the parent group is also considered
# detected (but may be suppressed in overlap resolution).
_FG_HIERARCHY: dict[str, str] = {
    "Phenol": "Alcohol",
    "Aldehyde": "Carbonyl",
    "Ketone": "Carbonyl",
    "Carboxylic Acid": "Carbonyl",
    "Ester": "Carbonyl",
    "Amide": "Carbonyl",
    "Amine Primary": "Amine",
    "Amine Secondary": "Amine",
    "Amine Tertiary": "Amine",
    # Sulfoxide and Sulfone are siblings (different oxidation states), not parent-child
    # so no hierarchy entry needed
}


def get_parent_group(name: str) -> str | None:
    """Get the parent group name for a functional group, if any."""
    return _FG_HIERARCHY.get(name)


def get_child_groups(name: str) -> list[str]:
    """Get all child groups that have this group as parent."""
    return [child for child, parent in _FG_HIERARCHY.items() if parent == name]


# ════════════════════════════════════════════════════════════════
#  Category-based helper functions
# ════════════════════════════════════════════════════════════════


def _get_categories(name: str) -> tuple[str, ...]:
    """Get the standard categories for a functional group name."""
    _CATEGORIES: dict[str, tuple[str, ...]] = {
        "Alcohol": ("oxygen", "hydroxy", "polar"),
        "Phenol": ("oxygen", "hydroxy", "aromatic"),
        "Ether": ("oxygen", "ether"),
        "Aldehyde": ("carbonyl", "oxygen"),
        "Ketone": ("carbonyl", "oxygen"),
        "Carboxylic Acid": ("carbonyl", "oxygen", "acid"),
        "Ester": ("carbonyl", "oxygen", "ester"),
        "Amine Primary": ("nitrogen", "amine", "basic"),
        "Amine Secondary": ("nitrogen", "amine", "basic"),
        "Amine Tertiary": ("nitrogen", "amine", "basic"),
        "Amide": ("carbonyl", "nitrogen", "amide"),
        "Nitrile": ("nitrogen", "nitrile"),
        "Nitro": ("nitrogen", "oxygen", "nitro"),
        "Halogen": ("halogen",),
        "Sulfide": ("sulfur", "sulfide"),
        "Thiol": ("sulfur", "thiol"),
        "Sulfoxide": ("sulfur", "oxygen", "sulfoxide"),
        "Sulfone": ("sulfur", "oxygen", "sulfone"),
        "Alkene": ("carbon", "unsaturated"),
        "Alkyne": ("carbon", "unsaturated"),
        "Aromatic Ring": ("aromatic", "ring"),
        "Carbonyl": ("carbonyl", "oxygen"),
        "Amine": ("nitrogen", "amine", "basic"),
    }
    return _CATEGORIES.get(name, ())


# ════════════════════════════════════════════════════════════════
#  Individual Detector Functions
#
#  Each detector is a function: (MolecularGraph) -> list[FunctionalGroupMatch]
#  that identifies occurrences of a specific functional group.
# ════════════════════════════════════════════════════════════════

# Type alias for detector functions
DetectorFn = Callable[[MolecularGraph], list[FunctionalGroupMatch]]


def _heavy_neighbors(graph: MolecularGraph, atom_index: int) -> list[int]:
    """Get neighbors of an atom, excluding hydrogen (Z=1).

    The SMILES parser creates explicit hydrogen atoms, so get_neighbors()
    includes H atoms. For functional group detection, we only care about
    heavy-atom connectivity.
    """
    return [
        n for n in graph.get_neighbors(atom_index)
        if graph.atoms[n].atomic_number != 1
    ]


def _detect_alcohol(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect alcohol groups: -OH bonded to sp3 carbon."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 8:  # Oxygen
            # Count only heavy-atom neighbors (ignore explicit H from SMILES parser)
            heavy_nbrs = _heavy_neighbors(graph, i)
            if len(heavy_nbrs) == 1:
                carbon_idx = heavy_nbrs[0]
                carbon = graph.atoms[carbon_idx]
                if carbon.atomic_number == 6 and not carbon.is_aromatic:
                    matches.append(FunctionalGroupMatch(
                        name="Alcohol",
                        smarts="[OX2H]",
                        atom_indices=(carbon_idx, i),
                        priority=10,
                        categories=_get_categories("Alcohol"),
                    ))
    return matches


def _detect_phenol(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect phenol groups: -OH directly bonded to aromatic ring."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 8:  # Oxygen
            heavy_nbrs = _heavy_neighbors(graph, i)
            if len(heavy_nbrs) == 1:
                carbon_idx = heavy_nbrs[0]
                carbon = graph.atoms[carbon_idx]
                if carbon.atomic_number == 6 and carbon.is_aromatic:
                    matches.append(FunctionalGroupMatch(
                        name="Phenol",
                        smarts="[OX2H][c]",
                        atom_indices=(carbon_idx, i),
                        priority=15,
                        categories=_get_categories("Phenol"),
                        parent="Alcohol",
                    ))
    return matches


def _detect_ether(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect ether groups: R-O-R' where both R are carbons."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 8:  # Oxygen
            heavy_nbrs = _heavy_neighbors(graph, i)
            if len(heavy_nbrs) == 2:
                n1, n2 = heavy_nbrs[0], heavy_nbrs[1]
                a1, a2 = graph.atoms[n1], graph.atoms[n2]
                if a1.atomic_number == 6 and a2.atomic_number == 6:
                    matches.append(FunctionalGroupMatch(
                        name="Ether",
                        smarts="[CX4][OX2][CX4]",
                        atom_indices=(n1, i, n2),
                        priority=10,
                        categories=_get_categories("Ether"),
                    ))
    return matches


def _detect_aldehyde(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect aldehyde groups: -C(=O)H."""
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 8:  # Carbonyl oxygen
            # O should be double-bonded to a carbon
            neighbors = graph.get_neighbors(i)
            for nbr in neighbors:
                bond = graph.get_bond(i, nbr)
                if (bond and bond.order == BondOrder.DOUBLE
                        and graph.atoms[nbr].atomic_number == 6):
                    carbon_idx = nbr
                    # The carbonyl carbon should have at least one hydrogen
                    # (check implicit or explicit)
                    carbon = graph.atoms[carbon_idx]
                    if (carbon.implicit_hydrogens is not None
                            and carbon.implicit_hydrogens >= 1):
                        # Check: carbon is terminal (degree <= 3 counting the double bond)
                        carbon_neighbors = graph.get_neighbors(carbon_idx)
                        # Filter out non-C neighbors (O, etc.)
                        carbon_carbon_neighbors = [
                            idx for idx in carbon_neighbors
                            if graph.atoms[idx].atomic_number == 6
                        ]
                        # Accept up to 2 carbon neighbors (supports glyoxal-like molecules)
                        if len(carbon_carbon_neighbors) <= 2:
                            return [FunctionalGroupMatch(
                                name="Aldehyde",
                                smarts="[CX3H1](=O)[#6]",
                                atom_indices=(carbon_idx, i),
                                priority=20,
                                categories=_get_categories("Aldehyde"),
                                parent="Carbonyl",
                            )]
    return []


def _detect_ketone(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect ketone groups: R-C(=O)-R'."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 8:  # Carbonyl oxygen
            for nbr in graph.get_neighbors(i):
                bond = graph.get_bond(i, nbr)
                if (bond and bond.order == BondOrder.DOUBLE
                        and graph.atoms[nbr].atomic_number == 6):
                    carbon_idx = nbr
                    # Carbonyl carbon should have two carbon neighbors
                    carbon_neighbors = graph.get_neighbors(carbon_idx)
                    carbon_carbon_neighbors = [
                        idx for idx in carbon_neighbors
                        if graph.atoms[idx].atomic_number == 6
                    ]
                    if len(carbon_carbon_neighbors) >= 2:
                        matches.append(FunctionalGroupMatch(
                            name="Ketone",
                            smarts="[#6][CX3](=O)[#6]",
                            atom_indices=tuple(carbon_carbon_neighbors[:2]) + (carbon_idx, i),
                            priority=15,
                            categories=_get_categories("Ketone"),
                            parent="Carbonyl",
                        ))
    return matches


def _detect_carboxylic_acid(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect carboxylic acid groups: -C(=O)OH."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 8:  # Could be carbonyl O or hydroxyl O
            neighbors = graph.get_neighbors(i)
            for nbr in neighbors:
                bond = graph.get_bond(i, nbr)
                if (bond and bond.order == BondOrder.DOUBLE
                        and graph.atoms[nbr].atomic_number == 6):
                    carbon_idx = nbr
                    # Check if this carbon also has a single-bonded OH
                    carbon_neighbors = graph.get_neighbors(carbon_idx)
                    oh_found = False
                    for cn in carbon_neighbors:
                        if graph.atoms[cn].atomic_number == 8:
                            cn_bond = graph.get_bond(carbon_idx, cn)
                            if cn_bond and cn_bond.order == BondOrder.SINGLE:
                                oh_found = True
                                break
                    if oh_found:
                        matches.append(FunctionalGroupMatch(
                            name="Carboxylic Acid",
                            smarts="[CX3](=O)[OX2H]",
                            atom_indices=(carbon_idx, i),
                            priority=25,
                            categories=_get_categories("Carboxylic Acid"),
                            parent="Carbonyl",
                        ))
    return matches


def _detect_ester(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect ester groups: R-C(=O)O-R'."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 8:  # Carbonyl oxygen
            for nbr in graph.get_neighbors(i):
                bond = graph.get_bond(i, nbr)
                if (bond and bond.order == BondOrder.DOUBLE
                        and graph.atoms[nbr].atomic_number == 6):
                    carbon_idx = nbr
                    carbon_neighbors = graph.get_neighbors(carbon_idx)
                    o_ester = None
                    for cn in carbon_neighbors:
                        if graph.atoms[cn].atomic_number == 8 and cn != i:
                            o_ester = cn
                            break
                    if o_ester is not None:
                        # The ester oxygen should be bonded to a carbon
                        o_neighbors = graph.get_neighbors(o_ester)
                        r_group = [on for on in o_neighbors if graph.atoms[on].atomic_number == 6 and on != carbon_idx]
                        if r_group:
                            matches.append(FunctionalGroupMatch(
                                name="Ester",
                                smarts="[#6][CX3](=O)[OX2][#6]",
                                atom_indices=(carbon_idx, i, o_ester, r_group[0]),
                                priority=20,
                                categories=_get_categories("Ester"),
                                parent="Carbonyl",
                            ))
    return matches


def _detect_amine_primary(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect primary amines: -NH2 bonded to carbon."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 7:  # Nitrogen
            heavy_nbrs = _heavy_neighbors(graph, i)
            carbon_neighbors = [n for n in heavy_nbrs if graph.atoms[n].atomic_number == 6]
            if len(carbon_neighbors) == 1 and len(heavy_nbrs) <= 2:
                matches.append(FunctionalGroupMatch(
                    name="Amine Primary",
                    smarts="[NX3H2][#6]",
                    atom_indices=(i, carbon_neighbors[0]),
                    priority=10,
                    categories=_get_categories("Amine Primary"),
                    parent="Amine",
                ))
    return matches


def _detect_amine_secondary(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect secondary amines: -NHR."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 7:  # Nitrogen
            heavy_nbrs = _heavy_neighbors(graph, i)
            carbon_neighbors = [n for n in heavy_nbrs if graph.atoms[n].atomic_number == 6]
            if len(carbon_neighbors) == 2:
                matches.append(FunctionalGroupMatch(
                    name="Amine Secondary",
                    smarts="[NX3H1]([#6])[#6]",
                    atom_indices=(i,) + tuple(carbon_neighbors),
                    priority=10,
                    categories=_get_categories("Amine Secondary"),
                    parent="Amine",
                ))
    return matches


def _detect_amine_tertiary(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect tertiary amines: -NR2."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 7:  # Nitrogen
            heavy_nbrs = _heavy_neighbors(graph, i)
            carbon_neighbors = [n for n in heavy_nbrs if graph.atoms[n].atomic_number == 6]
            if len(carbon_neighbors) >= 3:
                matches.append(FunctionalGroupMatch(
                    name="Amine Tertiary",
                    smarts="[NX3]([#6])([#6])[#6]",
                    atom_indices=(i,) + tuple(carbon_neighbors[:3]),
                    priority=10,
                    categories=_get_categories("Amine Tertiary"),
                    parent="Amine",
                ))
    return matches


def _detect_amide(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect amide groups: -C(=O)N<."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 8:  # Carbonyl oxygen
            for nbr in graph.get_neighbors(i):
                bond = graph.get_bond(i, nbr)
                if (bond and bond.order == BondOrder.DOUBLE
                        and graph.atoms[nbr].atomic_number == 6):
                    carbon_idx = nbr
                    # Check if carbon bonded to nitrogen
                    carbon_neighbors = graph.get_neighbors(carbon_idx)
                    for cn in carbon_neighbors:
                        if graph.atoms[cn].atomic_number == 7:
                            matches.append(FunctionalGroupMatch(
                                name="Amide",
                                smarts="[CX3](=O)[NX3]",
                                atom_indices=(carbon_idx, i, cn),
                                priority=20,
                                categories=_get_categories("Amide"),
                                parent="Carbonyl",
                            ))
                            break
    return matches


def _detect_nitrile(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect nitrile groups: -C≡N."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 7:  # Nitrogen
            neighbors = graph.get_neighbors(i)
            if len(neighbors) == 1:
                nbr = neighbors[0]
                bond = graph.get_bond(i, nbr)
                if (bond and bond.order == BondOrder.TRIPLE
                        and graph.atoms[nbr].atomic_number == 6):
                    matches.append(FunctionalGroupMatch(
                        name="Nitrile",
                        smarts="[NX1]#[CX2]",
                        atom_indices=(nbr, i),
                        priority=15,
                        categories=_get_categories("Nitrile"),
                    ))
    return matches


def _detect_nitro(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect nitro groups: -NO2."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 7:  # Nitrogen
            neighbors = graph.get_neighbors(i)
            double_bonded_oxygens = 0
            oxygen_indices: list[int] = []
            for nbr in neighbors:
                if graph.atoms[nbr].atomic_number == 8:
                    bond = graph.get_bond(i, nbr)
                    if bond and bond.order == BondOrder.DOUBLE:
                        double_bonded_oxygens += 1
                        oxygen_indices.append(nbr)
            if double_bonded_oxygens >= 2:
                matches.append(FunctionalGroupMatch(
                    name="Nitro",
                    smarts="[NX3](=O)=O",
                    atom_indices=(i,) + tuple(oxygen_indices),
                    priority=15,
                    categories=_get_categories("Nitro"),
                ))
    return matches


def _detect_halogen(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect halogen substituents: F, Cl, Br, I."""
    HALOGEN_Z: set[int] = {9, 17, 35, 53}
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number in HALOGEN_Z:
            matches.append(FunctionalGroupMatch(
                name="Halogen",
                smarts="[F,Cl,Br,I]",
                atom_indices=(i,),
                priority=5,
                categories=_get_categories("Halogen"),
            ))
    return matches


def _detect_sulfide(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect sulfide (thioether) groups: R-S-R'."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 16:  # Sulfur
            heavy_nbrs = _heavy_neighbors(graph, i)
            if len(heavy_nbrs) == 2:
                n1, n2 = heavy_nbrs[0], heavy_nbrs[1]
                if graph.atoms[n1].atomic_number == 6 and graph.atoms[n2].atomic_number == 6:
                    matches.append(FunctionalGroupMatch(
                        name="Sulfide",
                        smarts="[CX4][SX2][CX4]",
                        atom_indices=(n1, i, n2),
                        priority=10,
                        categories=_get_categories("Sulfide"),
                    ))
    return matches


def _detect_thiol(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect thiol groups: -SH."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 16:  # Sulfur
            heavy_nbrs = _heavy_neighbors(graph, i)
            if len(heavy_nbrs) == 1:
                nbr = heavy_nbrs[0]
                if graph.atoms[nbr].atomic_number == 6:
                    matches.append(FunctionalGroupMatch(
                        name="Thiol",
                        smarts="[SX2H]",
                        atom_indices=(nbr, i),
                        priority=10,
                        categories=_get_categories("Thiol"),
                    ))
    return matches


def _detect_sulfoxide(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect sulfoxide groups: R-S(=O)-R'."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 16:  # Sulfur
            neighbors = graph.get_neighbors(i)
            has_double_bonded_o = False
            carbon_neighbors: list[int] = []
            for nbr in neighbors:
                if graph.atoms[nbr].atomic_number == 8:
                    bond = graph.get_bond(i, nbr)
                    if bond and bond.order == BondOrder.DOUBLE:
                        has_double_bonded_o = True
                elif graph.atoms[nbr].atomic_number == 6:
                    carbon_neighbors.append(nbr)
            if has_double_bonded_o and len(carbon_neighbors) >= 2:
                matches.append(FunctionalGroupMatch(
                    name="Sulfoxide",
                    smarts="[#6][SX3](=O)[#6]",
                    atom_indices=(carbon_neighbors[0], i, carbon_neighbors[1]),
                    priority=15,
                    categories=_get_categories("Sulfoxide"),
                    parent="Sulfone",
                ))
    return matches


def _detect_sulfone(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect sulfone groups: R-S(=O)2-R'."""
    matches: list[FunctionalGroupMatch] = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 16:  # Sulfur
            neighbors = graph.get_neighbors(i)
            double_bonded_oxygens = 0
            carbon_neighbors: list[int] = []
            for nbr in neighbors:
                if graph.atoms[nbr].atomic_number == 8:
                    bond = graph.get_bond(i, nbr)
                    if bond and bond.order == BondOrder.DOUBLE:
                        double_bonded_oxygens += 1
                elif graph.atoms[nbr].atomic_number == 6:
                    carbon_neighbors.append(nbr)
            if double_bonded_oxygens >= 2 and len(carbon_neighbors) >= 2:
                matches.append(FunctionalGroupMatch(
                    name="Sulfone",
                    smarts="[#6][SX4](=O)(=O)[#6]",
                    atom_indices=(carbon_neighbors[0], i, carbon_neighbors[1]),
                    priority=15,
                    categories=_get_categories("Sulfone"),
                ))
    return matches


def _detect_alkene(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect carbon-carbon double bonds."""
    matches: list[FunctionalGroupMatch] = []
    seen_pairs: set[tuple[int, int]] = set()
    for j, bond in enumerate(graph.bonds):
        if bond.order == BondOrder.DOUBLE:
            a1, a2 = bond.atom1, bond.atom2
            if graph.atoms[a1].atomic_number == 6 and graph.atoms[a2].atomic_number == 6:
                pair = (min(a1, a2), max(a1, a2))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    matches.append(FunctionalGroupMatch(
                        name="Alkene",
                        smarts="[CX3]=[CX3]",
                        atom_indices=(a1, a2),
                        priority=5,
                        categories=_get_categories("Alkene"),
                    ))
    return matches


def _detect_alkyne(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect carbon-carbon triple bonds."""
    matches: list[FunctionalGroupMatch] = []
    for j, bond in enumerate(graph.bonds):
        if bond.order == BondOrder.TRIPLE:
            a1, a2 = bond.atom1, bond.atom2
            if graph.atoms[a1].atomic_number == 6 and graph.atoms[a2].atomic_number == 6:
                matches.append(FunctionalGroupMatch(
                    name="Alkyne",
                    smarts="[CX2]#[CX2]",
                    atom_indices=(a1, a2),
                    priority=5,
                    categories=_get_categories("Alkyne"),
                ))
    return matches


def _detect_aromatic_ring(graph: MolecularGraph) -> list[FunctionalGroupMatch]:
    """Detect aromatic ring atoms."""
    matches: list[FunctionalGroupMatch] = []
    aromatic_atoms: set[int] = set()
    for i, atom in enumerate(graph.atoms):
        if atom.is_aromatic:
            aromatic_atoms.add(i)
    if aromatic_atoms:
        matches.append(FunctionalGroupMatch(
            name="Aromatic Ring",
            smarts="[a]",
            atom_indices=tuple(sorted(aromatic_atoms)),
            priority=5,
            categories=_get_categories("Aromatic Ring"),
        ))
    return matches


# ════════════════════════════════════════════════════════════════
#  Detector Registry
# ════════════════════════════════════════════════════════════════

# All registered detector functions, ordered by priority (highest first)
_DETECTORS: list[tuple[str, int, DetectorFn]] = [
    # High priority (most specific)
    ("Carboxylic Acid", 25, _detect_carboxylic_acid),
    ("Aldehyde", 20, _detect_aldehyde),
    ("Ester", 20, _detect_ester),
    ("Amide", 20, _detect_amide),
    # Medium-high priority
    ("Phenol", 15, _detect_phenol),
    ("Ketone", 15, _detect_ketone),
    ("Nitrile", 15, _detect_nitrile),
    ("Nitro", 15, _detect_nitro),
    ("Sulfoxide", 15, _detect_sulfoxide),
    ("Sulfone", 15, _detect_sulfone),
    # Medium priority
    ("Alcohol", 10, _detect_alcohol),
    ("Ether", 10, _detect_ether),
    ("Amine Primary", 10, _detect_amine_primary),
    ("Amine Secondary", 10, _detect_amine_secondary),
    ("Amine Tertiary", 10, _detect_amine_tertiary),
    ("Sulfide", 10, _detect_sulfide),
    ("Thiol", 10, _detect_thiol),
    # Low priority (broad patterns)
    ("Halogen", 5, _detect_halogen),
    ("Alkene", 5, _detect_alkene),
    ("Alkyne", 5, _detect_alkyne),
    ("Aromatic Ring", 5, _detect_aromatic_ring),
]


# ════════════════════════════════════════════════════════════════
#  Dataset-driven Group Definitions (from functional_groups.toml)
# ════════════════════════════════════════════════════════════════

def load_group_definitions() -> list[dict[str, Any]]:
    """Load functional group definitions from the functional_groups.toml dataset.

    Returns:
        List of group definition dicts with name, smarts, priority, categories.

    Falls back to hardcoded definitions if the dataset is unavailable.
    """
    try:
        from chemengine.core.datasets import get_global_dataset_registry
        registry = get_global_dataset_registry()
        ds = registry.get("functional_groups")
        raw = ds.data
        groups = raw.get("group", [])
        if groups:
            return groups
        raise KeyError("No groups found in dataset")
    except (FileNotFoundError, KeyError, Exception) as e:
        logger.warning(f"Could not load functional groups from dataset: {e}")
        # Return hardcoded definitions matching the detector implementations
        return [
            {"name": "Alcohol", "smarts": "[OX2H]", "priority": 10,
             "categories": ["oxygen", "hydroxy", "polar"]},
            {"name": "Phenol", "smarts": "[OX2H][c]", "priority": 15,
             "categories": ["oxygen", "hydroxy", "aromatic"]},
            {"name": "Ether", "smarts": "[CX4][OX2][CX4]", "priority": 10,
             "categories": ["oxygen", "ether"]},
            {"name": "Aldehyde", "smarts": "[CX3H1](=O)[#6]", "priority": 20,
             "categories": ["carbonyl", "oxygen"]},
            {"name": "Ketone", "smarts": "[#6][CX3](=O)[#6]", "priority": 15,
             "categories": ["carbonyl", "oxygen"]},
            {"name": "Carboxylic Acid", "smarts": "[CX3](=O)[OX2H]", "priority": 25,
             "categories": ["carbonyl", "oxygen", "acid"]},
            {"name": "Ester", "smarts": "[#6][CX3](=O)[OX2][#6]", "priority": 20,
             "categories": ["carbonyl", "oxygen", "ester"]},
            {"name": "Amine Primary", "smarts": "[NX3H2][#6]", "priority": 10,
             "categories": ["nitrogen", "amine", "basic"]},
            {"name": "Amine Secondary", "smarts": "[NX3H1]([#6])[#6]", "priority": 10,
             "categories": ["nitrogen", "amine", "basic"]},
            {"name": "Amine Tertiary", "smarts": "[NX3]([#6])([#6])[#6]", "priority": 10,
             "categories": ["nitrogen", "amine", "basic"]},
            {"name": "Amide", "smarts": "[CX3](=O)[NX3]", "priority": 20,
             "categories": ["carbonyl", "nitrogen", "amide"]},
            {"name": "Nitrile", "smarts": "[NX1]#[CX2]", "priority": 15,
             "categories": ["nitrogen", "nitrile"]},
            {"name": "Nitro", "smarts": "[NX3](=O)=O", "priority": 15,
             "categories": ["nitrogen", "oxygen", "nitro"]},
            {"name": "Halogen", "smarts": "[F,Cl,Br,I]", "priority": 5,
             "categories": ["halogen"]},
            {"name": "Sulfide", "smarts": "[CX4][SX2][CX4]", "priority": 10,
             "categories": ["sulfur", "sulfide"]},
            {"name": "Thiol", "smarts": "[SX2H]", "priority": 10,
             "categories": ["sulfur", "thiol"]},
            {"name": "Sulfoxide", "smarts": "[#6][SX3](=O)[#6]", "priority": 15,
             "categories": ["sulfur", "oxygen", "sulfoxide"]},
            {"name": "Sulfone", "smarts": "[#6][SX4](=O)(=O)[#6]", "priority": 15,
             "categories": ["sulfur", "oxygen", "sulfone"]},
            {"name": "Alkene", "smarts": "[CX3]=[CX3]", "priority": 5,
             "categories": ["carbon", "unsaturated"]},
            {"name": "Alkyne", "smarts": "[CX2]#[CX2]", "priority": 5,
             "categories": ["carbon", "unsaturated"]},
            {"name": "Aromatic Ring", "smarts": "[a]", "priority": 5,
             "categories": ["aromatic", "ring"]},
        ]


# ════════════════════════════════════════════════════════════════
#  Overlap Detection & Resolution
# ════════════════════════════════════════════════════════════════


def _find_overlapping_groups(
    matches: list[FunctionalGroupMatch],
) -> list[set[int]]:
    """Find groups of overlapping matches (groups that share atoms).

    Args:
        matches: List of all detected matches.

    Returns:
        List of sets, where each set contains indices into the matches
        list for groups that overlap.
    """
    n = len(matches)
    # Build overlap graph
    overlap_adj: list[set[int]] = [set() for _ in range(n)]
    for i in range(n):
        atoms_i = set(matches[i].atom_indices)
        for j in range(i + 1, n):
            atoms_j = set(matches[j].atom_indices)
            if atoms_i & atoms_j:  # Share any atoms
                overlap_adj[i].add(j)
                overlap_adj[j].add(i)

    # Find connected components in overlap graph
    visited: set[int] = set()
    clusters: list[set[int]] = []
    for i in range(n):
        if i not in visited:
            cluster: set[int] = set()
            stack = [i]
            while stack:
                node = stack.pop()
                if node not in visited:
                    visited.add(node)
                    cluster.add(node)
                    stack.extend(overlap_adj[node] - visited)
            clusters.append(cluster)

    return clusters


def _resolve_overlap(
    matches: list[FunctionalGroupMatch],
) -> list[FunctionalGroupMatch]:
    """Resolve overlapping matches by keeping the highest-priority group.

    When multiple functional group matches share atoms, the match with
    the highest priority is kept. Ties are broken by preferring the
    more specific group (more atom indices).

    Args:
        matches: All detected matches (may have overlaps).

    Returns:
        Resolved list of matches with no overlapping atoms.
    """
    if not matches:
        return []

    clusters = _find_overlapping_groups(matches)
    resolved: set[int] = set()

    for cluster in clusters:
        if len(cluster) == 1:
            resolved.add(next(iter(cluster)))
        else:
            # Pick the best match from this cluster
            best_idx = max(
                cluster,
                key=lambda idx: (
                    matches[idx].priority,
                    len(matches[idx].atom_indices),  # More atoms = more specific
                    matches[idx].name,
                ),
            )
            resolved.add(best_idx)

    return [matches[i] for i in sorted(resolved)]


# ════════════════════════════════════════════════════════════════
#  Main Detection API
# ════════════════════════════════════════════════════════════════


def detect_functional_groups(
    graph: MolecularGraph,
    resolve_overlaps: bool = True,
) -> list[FunctionalGroupMatch]:
    """Detect all functional groups in a molecular graph.

    Runs all registered detectors and returns the matches, optionally
    resolving overlapping groups.

    Args:
        graph: The molecular graph to analyze.
        resolve_overlaps: Whether to resolve overlapping groups (default: True).

    Returns:
        List of FunctionalGroupMatch objects for each detected group.
    """
    all_matches: list[FunctionalGroupMatch] = []

    for name, priority, detector_fn in _DETECTORS:
        try:
            matches = detector_fn(graph)
            all_matches.extend(matches)
        except Exception as e:
            logger.warning(f"Detector '{name}' failed: {e}")

    if resolve_overlaps:
        all_matches = _resolve_overlap(all_matches)

    return all_matches


def detect_functional_groups_dict(
    graph: MolecularGraph,
    resolve_overlaps: bool = True,
) -> list[dict[str, Any]]:
    """Detect functional groups and return as list of dicts.

    Convenience wrapper for API output.

    Args:
        graph: The molecular graph to analyze.
        resolve_overlaps: Whether to resolve overlapping groups.

    Returns:
        List of dicts with name, smarts, atom_indices, priority, categories.
    """
    matches = detect_functional_groups(graph, resolve_overlaps=resolve_overlaps)
    return [m.to_dict() for m in matches]


# ════════════════════════════════════════════════════════════════
#  List Available Detectors
# ════════════════════════════════════════════════════════════════


def list_available_groups() -> list[dict[str, Any]]:
    """List all available functional group detectors.

    Returns:
        List of dicts with name, priority, categories, smarts, description.
    """
    groups = load_group_definitions()
    result: list[dict[str, Any]] = []
    for g in groups:
        entry = {
            "name": g.get("name", ""),
            "smarts": g.get("smarts", ""),
            "priority": g.get("priority", 0),
            "categories": g.get("categories", []),
            "description": g.get("description", ""),
            "parent": _FG_HIERARCHY.get(g.get("name", "")),
        }
        result.append(entry)
    return result


# ════════════════════════════════════════════════════════════════
#  Alias: get_functional_groups (convenience name)
# ════════════════════════════════════════════════════════════════

get_functional_groups = detect_functional_groups
