"""Molecule — high-level molecular container with all computed properties.

The Molecule wraps a MolecularGraph and provides computed properties:
formula, mass, charge, spin multiplicity, identifiers, and metadata.
It is the primary user-facing object for most operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chemengine.core.enums import SpinMultiplicity
from chemengine.core.graph import MolecularGraph


@dataclass(frozen=True, slots=True)
class MolecularIdentifiers:
    """Standard molecular identifiers.

    Attributes:
        smiles: SMILES string.
        canonical_smiles: Canonical (unique) SMILES.
        inchi: InChI string.
        inchikey: InChIKey (hashed).
        formula: Molecular formula (Hill system).
        name: Common or IUPAC name.
    """

    smiles: str = ""
    canonical_smiles: str = ""
    inchi: str = ""
    inchikey: str = ""
    formula: str = ""
    name: str = ""


@dataclass(frozen=True, slots=True)
class MolecularProperties:
    """Computed molecular properties.

    Attributes:
        exact_mass: Monoisotopic exact mass (Da).
        molecular_weight: Average molecular weight (Da).
        formula_weight: Formula weight alias for molecular_weight.
        num_atoms: Total number of atoms.
        num_heavy_atoms: Number of non-hydrogen atoms.
        num_bonds: Total number of bonds.
        num_rotatable_bonds: Number of rotatable bonds.
        num_rings: Number of rings.
        num_stereocenters: Number of stereocenters.
        log_p: Octanol-water partition coefficient (None if not computed).
        tpsa: Topological polar surface area (None if not computed).
        hbd: Hydrogen bond donor count.
        hba: Hydrogen bond acceptor count.
        charge: Total formal charge.
        spin_multiplicity: Spin multiplicity (2S+1).
    """

    exact_mass: float = 0.0
    molecular_weight: float = 0.0
    formula_weight: float = 0.0
    num_atoms: int = 0
    num_heavy_atoms: int = 0
    num_bonds: int = 0
    num_rotatable_bonds: int = 0
    num_rings: int = 0
    num_stereocenters: int = 0
    log_p: float | None = None
    tpsa: float | None = None
    hbd: int = 0
    hba: int = 0
    charge: int = 0
    spin_multiplicity: SpinMultiplicity = SpinMultiplicity.SINGLET


@dataclass(frozen=True, slots=True)
class Molecule:
    """A complete molecule with graph structure and computed properties.

    The Molecule wraps a MolecularGraph and provides computed properties
    such as formula, mass, charge, and identifiers. It is the primary
    user-facing container for most chemistry operations.

    Attributes:
        graph: The underlying MolecularGraph (single source of truth).
        identifiers: Standard molecular identifiers.
        properties: Computed molecular properties.
        metadata: Extensible key-value metadata.
    """

    graph: MolecularGraph
    identifiers: MolecularIdentifiers = field(default_factory=MolecularIdentifiers)
    properties: MolecularProperties = field(default_factory=MolecularProperties)
    metadata: frozenset[tuple[str, Any]] = frozenset()

    @property
    def formula(self) -> str:
        """Molecular formula (Hill system)."""
        return self.graph.molecular_formula

    @property
    def exact_mass(self) -> float:
        """Exact monoisotopic mass."""
        return self.graph.exact_mass

    @property
    def molecular_weight(self) -> float:
        """Average molecular weight."""
        return self.graph.molecular_weight

    @property
    def num_atoms(self) -> int:
        return self.graph.num_atoms

    @property
    def num_bonds(self) -> int:
        return self.graph.num_bonds

    @property
    def name(self) -> str | None:
        return self.graph.name

    @classmethod
    def from_graph(cls, graph: MolecularGraph) -> Molecule:
        """Create a Molecule from a MolecularGraph with auto-computed properties.

        Args:
            graph: The molecular graph.

        Returns:
            A Molecule with computed properties.
        """
        # Compute charge distribution
        total_charge = sum(a.formal_charge for a in graph.atoms)
        total_radicals = sum(a.radical_electrons for a in graph.atoms)
        spin = SpinMultiplicity.from_unpaired_electrons(total_radicals)

        # Count HBA/HBD
        hbd = 0
        hba = 0
        for i, atom in enumerate(graph.atoms):
            z = atom.atomic_number
            if z in (7, 8, 9):
                hba += 1
            if z in (7, 8):
                for nb in graph.get_neighbors(i):
                    if graph.atoms[nb].atomic_number == 1:
                        hbd += 1
                        break

        props = MolecularProperties(
            exact_mass=graph.exact_mass,
            molecular_weight=graph.molecular_weight,
            formula_weight=graph.molecular_weight,
            num_atoms=graph.num_atoms,
            num_heavy_atoms=graph.num_heavy_atoms,
            num_bonds=graph.num_bonds,
            num_rotatable_bonds=graph.num_rotatable_bonds,
            num_rings=graph.num_rings if hasattr(graph, 'rings') else 0,
            num_stereocenters=len(graph.stereo_config.centers) if hasattr(graph, 'stereo_config') else 0,
            hbd=hbd,
            hba=hba,
            charge=total_charge,
            spin_multiplicity=spin,
        )

        identifiers = MolecularIdentifiers(
            formula=graph.molecular_formula,
            name=graph.name or "",
        )

        return cls(
            graph=graph,
            identifiers=identifiers,
            properties=props,
        )

    def __repr__(self) -> str:
        name_str = f" '{self.name}'" if self.name else ""
        return (
            f"Molecule({self.formula}{name_str}, "
            f"{self.num_atoms} atoms, {self.num_bonds} bonds)"
        )
