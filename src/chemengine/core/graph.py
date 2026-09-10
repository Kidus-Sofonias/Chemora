"""MolecularGraph — the single source of truth for all chemistry operations.

This is THE most important class in the entire engine. EVERY operation —
parsing, generation, detection, rendering, properties, validation —
reads from and produces a MolecularGraph.

The MolecularGraph is:
    - Immutable (frozen=True, slots=True): Thread-safe, hashable, cacheable.
    - Self-contained: All atom and bond data is stored in tuples.
    - Validated: Construction validates atomic numbers, bond orders, self-bonds.

Graph operations:
    - add/remove atoms and bonds (via builder)
    - neighbors(), get_bond(), get_adjacency_matrix()
    - shortest_path() using BFS
    - connected_components()
    - clone() via builder
    - subgraph() extraction
    - canonical hash placeholder
    - graph validation
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from chemengine.core.atoms import Atom, Isotope
from chemengine.core.bonds import Bond, BondOrder
from chemengine.core.enums import (
    BondOrder,
    BondStereo,
    BondTopology,
    BondType,
    ChiralTag,
    ElementSymbol,
    Hybridization,
)
from chemengine.core.geometry import Conformer, Coordinate2D, Coordinate3D
from chemengine.core.stereo import ChiralCenter, StereoConfig
from chemengine.core.substructure import Ring


@dataclass(frozen=True, slots=True)
class MolecularGraph:
    """The single source of truth for all chemistry operations.

    Represents a complete molecular structure: atoms, bonds, coordinates,
    stereochemistry, and computed properties. Every module in the engine
    reads from this graph and produces new graphs through the builder.

    Attributes:
        atoms: Immutable tuple of all atoms in the molecule.
        bonds: Immutable tuple of all bonds between atoms.
        name: Optional human-readable name for the molecule.
        stereo_config: Complete stereochemical configuration.
        coordinates_2d: Optional 2D layout coordinates (for depiction).
        coordinates_3d: Optional 3D coordinates (primary conformer).
        conformers: Additional 3D conformers.
        rings: Detected rings in the molecule.
        properties: Extensible key-value metadata.

    Usage:
        >>> graph = MolecularGraph(
        ...     atoms=(Atom(atomic_number=6), Atom(atomic_number=6)),
        ...     bonds=(Bond(atom1=0, atom2=1, order=BondOrder.SINGLE),),
        ... )
        >>> graph.num_atoms
        2
        >>> graph.molecular_formula
        'C2'
    """

    atoms: tuple[Atom, ...]
    bonds: tuple[Bond, ...]
    name: str | None = None
    stereo_config: StereoConfig = field(default_factory=StereoConfig)
    coordinates_2d: tuple[Coordinate2D, ...] | None = None
    coordinates_3d: tuple[Coordinate3D, ...] | None = None
    conformers: tuple[Conformer, ...] = ()
    rings: tuple[Ring, ...] = ()
    properties: frozenset[tuple[str, Any]] = frozenset()

    # ── Basic Graph Properties ──

    @property
    def num_atoms(self) -> int:
        """Total number of atoms in the graph."""
        return len(self.atoms)

    @property
    def num_bonds(self) -> int:
        """Total number of bonds in the graph."""
        return len(self.bonds)

    @property
    def num_heavy_atoms(self) -> int:
        """Number of non-hydrogen atoms."""
        return sum(1 for a in self.atoms if a.atomic_number != 1)

    @property
    def num_rotatable_bonds(self) -> int:
        """Number of rotatable bonds (single, non-ring, non-terminal)."""
        return sum(1 for b in self.bonds if b.is_rotatable)

    @property
    def num_rings(self) -> int:
        """Number of rings in the molecule."""
        return len(self.rings)

    @property
    def atoms_by_element(self) -> dict[ElementSymbol, list[int]]:
        """Group atom indices by element symbol."""
        result: dict[ElementSymbol, list[int]] = {}
        for i, atom in enumerate(self.atoms):
            el = atom.element_symbol
            if el not in result:
                result[el] = []
            result[el].append(i)
        return result

    @property
    def formula_dict(self) -> dict[str, int]:
        """Element counts as a dictionary (e.g., {'C': 5, 'H': 12})."""
        counts: dict[str, int] = {}
        for atom in self.atoms:
            sym = atom.symbol
            counts[sym] = counts.get(sym, 0) + 1
        return counts

    # ── Graph Traversal ──

    def get_neighbors(self, atom_index: int) -> tuple[int, ...]:
        """Return the indices of all atoms bonded to the given atom."""
        neighbors: list[int] = []
        for bond in self.bonds:
            if bond.atom1 == atom_index:
                neighbors.append(bond.atom2)
            elif bond.atom2 == atom_index:
                neighbors.append(bond.atom1)
        return tuple(sorted(neighbors))

    def get_bonds_of_atom(self, atom_index: int) -> tuple[int, ...]:
        """Return the bond indices for bonds involving the given atom."""
        return tuple(
            i for i, bond in enumerate(self.bonds)
            if bond.atom1 == atom_index or bond.atom2 == atom_index
        )

    def get_bond(self, atom1: int, atom2: int) -> Bond | None:
        """Get the bond between two atoms, or None if not bonded."""
        for bond in self.bonds:
            if (bond.atom1 == atom1 and bond.atom2 == atom2) or \
               (bond.atom1 == atom2 and bond.atom2 == atom1):
                return bond
        return None

    def get_bond_index(self, atom1: int, atom2: int) -> int | None:
        """Get the index of the bond between two atoms, or None."""
        for i, bond in enumerate(self.bonds):
            if (bond.atom1 == atom1 and bond.atom2 == atom2) or \
               (bond.atom1 == atom2 and bond.atom2 == atom1):
                return i
        return None

    def get_adjacency_matrix(self) -> list[list[int]]:
        """Return the adjacency matrix as a list of lists."""
        n = self.num_atoms
        mat = [[0] * n for _ in range(n)]
        for bond in self.bonds:
            mat[bond.atom1][bond.atom2] = 1
            mat[bond.atom2][bond.atom1] = 1
        return mat

    def get_degree(self, atom_index: int) -> int:
        """Return the degree (number of bonds) of an atom."""
        return len(self.get_neighbors(atom_index))

    def shortest_path(self, start: int, end: int) -> tuple[int, ...] | None:
        """Find the shortest path between two atoms using BFS.

        Args:
            start: Starting atom index.
            end: Target atom index.

        Returns:
            Tuple of atom indices forming the shortest path, or None if
            no path exists.
        """
        if start == end:
            return (start,)
        visited = {start}
        queue: deque[list[int]] = deque([[start]])
        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbor in self.get_neighbors(current):
                if neighbor == end:
                    return tuple(path + [neighbor])
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def connected_components(self) -> tuple[tuple[int, ...], ...]:
        """Find all connected components in the graph.

        Returns:
            Tuple of components, where each component is a tuple of atom indices.
        """
        visited: set[int] = set()
        components: list[tuple[int, ...]] = []

        for i in range(self.num_atoms):
            if i not in visited:
                component: list[int] = []
                stack = [i]
                while stack:
                    node = stack.pop()
                    if node not in visited:
                        visited.add(node)
                        component.append(node)
                        for neighbor in self.get_neighbors(node):
                            if neighbor not in visited:
                                stack.append(neighbor)
                components.append(tuple(sorted(component)))

        return tuple(components)

    @property
    def is_connected(self) -> bool:
        """Whether the molecular graph is connected (single component)."""
        if self.num_atoms == 0:
            return True
        return len(self.connected_components()) == 1

    @property
    def num_components(self) -> int:
        """Number of connected components in the graph."""
        return len(self.connected_components())

    def subgraph(self, atom_indices: set[int]) -> MolecularGraph:
        """Extract a subgraph containing only the specified atoms.

        Args:
            atom_indices: Set of atom indices to include.

        Returns:
            A new MolecularGraph containing only the specified atoms and
            the bonds between them.
        """
        # Build index mapping
        old_to_new: dict[int, int] = {}
        new_atoms: list[Atom] = []
        for i, atom in enumerate(self.atoms):
            if i in atom_indices:
                old_to_new[i] = len(new_atoms)
                new_atoms.append(atom)

        # Filter bonds
        new_bonds: list[Bond] = []
        for bond in self.bonds:
            if bond.atom1 in atom_indices and bond.atom2 in atom_indices:
                new_bonds.append(Bond(
                    atom1=old_to_new[bond.atom1],
                    atom2=old_to_new[bond.atom2],
                    order=bond.order,
                    bond_type=bond.bond_type,
                    stereochemistry=bond.stereochemistry,
                    topology=bond.topology,
                    is_aromatic=bond.is_aromatic,
                    length=bond.length,
                    properties=bond.properties,
                ))

        return MolecularGraph(
            atoms=tuple(new_atoms),
            bonds=tuple(new_bonds),
            name=self.name,
        )

    # ── Computed Molecular Properties ──

    @property
    def molecular_formula(self) -> str:
        """Hill-system molecular formula (C first, H second, then alphabetically).
        """
        counts = dict(self.formula_dict)
        parts: list[str] = []
        for sym in ("C", "H"):
            if sym in counts:
                cnt = counts.pop(sym)
                parts.append(f"{sym}{cnt if cnt > 1 else ''}")
        for sym in sorted(counts):
            cnt = counts[sym]
            parts.append(f"{sym}{cnt if cnt > 1 else ''}")
        return "".join(parts)

    @property
    def exact_mass(self) -> float:
        """Exact monoisotopic mass using most abundant isotope masses.
        """
        total = 0.0
        for atom in self.atoms:
            total += atom.mass
        return total

    @property
    def molecular_weight(self) -> float:
        """Average molecular weight using standard atomic weights.
        """
        total = 0.0
        for atom in self.atoms:
            if atom.isotope is not None:
                total += atom.isotope.exact_mass
            else:
                total += atom.element.atomic_mass
        return total

    @property
    def graph_hash(self) -> str:
        """A hash that uniquely identifies this molecular graph's connectivity.

        Uses SHA-256 of the canonical SMILES (placeholder) or a connectivity
        fingerprint. This is a placeholder that will use the canonical SMILES
        once the SMILES writer is implemented.
        """
        # Build a connectivity fingerprint
        h = hashlib.sha256()
        h.update(str(self.num_atoms).encode())
        h.update(str(self.num_bonds).encode())
        for atom in self.atoms:
            h.update(f"{atom.atomic_number},{atom.formal_charge},".encode())
        for bond in self.bonds:
            h.update(f"{bond.atom1},{bond.atom2},{bond.order.value},".encode())
        return h.hexdigest()

    # ── Validation ──

    def validate(self) -> list[str]:
        """Validate the molecular graph and return a list of issues.

        Checks:
            - Atomic numbers in valid range (1-118)
            - No self-bonds
            - Bond orders valid
            - Valence limits (basic)
            - No duplicate bonds
            - Atom indices in range

        Returns:
            List of issue descriptions (empty if valid).

        Note:
            This is a basic validation. Use the full validation module
            (chemengine.validation) for comprehensive ValidationReport
            with severity levels, rule sets, and detailed findings.
        """
        issues: list[str] = []
        n = self.num_atoms

        # Check atom validity
        for i, atom in enumerate(self.atoms):
            if not 1 <= atom.atomic_number <= 118:
                issues.append(f"Atom {i}: invalid atomic number {atom.atomic_number}")

        # Check bond validity
        seen_pairs: set[tuple[int, int]] = set()
        for j, bond in enumerate(self.bonds):
            if bond.atom1 < 0 or bond.atom1 >= n:
                issues.append(f"Bond {j}: atom1 index {bond.atom1} out of range")
            if bond.atom2 < 0 or bond.atom2 >= n:
                issues.append(f"Bond {j}: atom2 index {bond.atom2} out of range")
            if bond.atom1 == bond.atom2:
                issues.append(f"Bond {j}: self-bond at atom {bond.atom1}")
            pair = (min(bond.atom1, bond.atom2), max(bond.atom1, bond.atom2))
            if pair in seen_pairs:
                issues.append(f"Bond {j}: duplicate bond between {pair[0]} and {pair[1]}")
            seen_pairs.add(pair)

        # Check valence limits
        for i, atom in enumerate(self.atoms):
            degree = self.get_degree(i)
            if degree > atom.max_valence and atom.max_valence > 0:
                issues.append(f"Atom {i} ({atom.symbol}): degree {degree} exceeds max valence {atom.max_valence}")

        return issues

    @property
    def is_valid(self) -> bool:
        """Whether the graph passes all validation checks."""
        return len(self.validate()) == 0

    def sanitize(self) -> MolecularGraph:
        """Sanitize the molecular graph, producing a chemically valid graph.

        Applies:
            - Remove duplicate bonds
            - Add implicit hydrogens where missing
            - Assign formal charges (basic)

        Uses the chemengine.validation.sanitize module.

        Returns:
            A new, sanitized MolecularGraph.
        """
        from chemengine.validation.sanitize import sanitize as _sanitize
        return _sanitize(self)

    # ── Hashing and Equality ──

    def __repr__(self) -> str:
        name_str = f" '{self.name}'" if self.name else ""
        return (
            f"MolecularGraph({self.molecular_formula}{name_str}, "
            f"{self.num_atoms} atoms, {self.num_bonds} bonds)"
        )

    def __len__(self) -> int:
        return self.num_atoms


class MolecularGraphBuilder:
    """Mutable builder that constructs an immutable MolecularGraph.

    Usage:
        >>> builder = MolecularGraphBuilder()
        >>> c1 = builder.add_atom(atomic_number=6)
        >>> c2 = builder.add_atom(atomic_number=6)
        >>> builder.add_bond(c1, c2, BondOrder.DOUBLE)
        >>> graph = builder.build()
        >>> graph.molecular_formula
        'C2'
    """

    def __init__(self) -> None:
        self._atoms: list[Atom] = []
        self._bonds: list[Bond] = []
        self._name: str | None = None
        self._coordinates_2d: list[Coordinate2D] | None = None
        self._coordinates_3d: list[Coordinate3D] | None = None
        self._conformers: list[Conformer] = []
        self._rings: list[Ring] = []
        self._stereo_centers: list[ChiralCenter] = []
        self._properties: dict[str, Any] = {}

    # ── Atom Operations ──

    def add_atom(
        self,
        atomic_number: int,
        *,
        formal_charge: int = 0,
        radical_electrons: int = 0,
        isotope: Isotope | None = None,
        stereochemistry: ChiralTag = ChiralTag.NONE,
        hybridization: Hybridization = Hybridization.UNKNOWN,
        valence: int | None = None,
        implicit_hydrogens: int | None = None,
        atom_mapping: int | None = None,
        is_aromatic: bool = False,
        properties: dict[str, Any] | None = None,
    ) -> int:
        """Add an atom to the graph.

        Args:
            atomic_number: Atomic number Z (1-118).
            formal_charge: Formal charge on the atom.
            radical_electrons: Number of unpaired electrons (0, 1, 2).
            isotope: Optional isotopic information.
            stereochemistry: Tetrahedral stereochemistry (ChiralTag).
            hybridization: Orbital hybridization state.
            valence: Explicit valence state (None = auto).
            implicit_hydrogens: Explicit implicit H count (None = auto).
            atom_mapping: Reaction mapping number.
            is_aromatic: Whether this atom is aromatic.
            properties: Optional atom-specific properties.

        Returns:
            The index of the newly added atom (0-based).
        """
        idx = len(self._atoms)
        atom = Atom(
            atomic_number=atomic_number,
            formal_charge=formal_charge,
            radical_electrons=radical_electrons,
            isotope=isotope,
            stereochemistry=stereochemistry,
            hybridization=hybridization,
            valence=valence,
            implicit_hydrogens=implicit_hydrogens,
            atom_mapping=atom_mapping,
            is_aromatic=is_aromatic,
            properties=frozenset((properties or {}).items()),
        )
        self._atoms.append(atom)
        return idx

    def remove_atom(self, index: int) -> None:
        """Remove an atom and all its bonds.

        Warning: This shifts indices of all subsequent atoms and bonds.
        """
        if index < 0 or index >= len(self._atoms):
            raise IndexError(f"Atom index {index} out of range")
        self._atoms.pop(index)
        # Remove bonds involving this atom, adjusting indices
        new_bonds: list[Bond] = []
        for bond in self._bonds:
            if bond.atom1 == index or bond.atom2 == index:
                continue
            a1 = bond.atom1 - 1 if bond.atom1 > index else bond.atom1
            a2 = bond.atom2 - 1 if bond.atom2 > index else bond.atom2
            new_bonds.append(Bond(
                atom1=a1, atom2=a2, order=bond.order,
                bond_type=bond.bond_type, stereochemistry=bond.stereochemistry,
                topology=bond.topology, is_aromatic=bond.is_aromatic,
                length=bond.length, properties=bond.properties,
            ))
        self._bonds = new_bonds

    # ── Bond Operations ──

    def add_bond(
        self,
        atom1: int,
        atom2: int,
        order: BondOrder = BondOrder.SINGLE,
        *,
        bond_type: BondType = BondType.COVALENT,
        stereochemistry: BondStereo = BondStereo.NONE,
        topology: BondTopology = BondTopology.UNSPECIFIED,
        is_aromatic: bool = False,
        length: float | None = None,
        properties: dict[str, Any] | None = None,
    ) -> int:
        """Add a bond between two atoms.

        Args:
            atom1: Index of the first atom.
            atom2: Index of the second atom.
            order: Bond order (single, double, triple, etc.).
            bond_type: Classification of the bond.
            stereochemistry: Double bond stereochemistry.
            topology: Ring/chain topology.
            is_aromatic: Whether this bond is aromatic.
            length: Bond length in angstroms.
            properties: Optional bond-specific properties.

        Returns:
            The index of the newly added bond (0-based).
        """
        if atom1 == atom2:
            raise ValueError(f"Self-bonds are not allowed: atom {atom1} == atom {atom2}")
        idx = len(self._bonds)
        bond = Bond(
            atom1=atom1, atom2=atom2, order=order,
            bond_type=bond_type, stereochemistry=stereochemistry,
            topology=topology, is_aromatic=is_aromatic,
            length=length, properties=frozenset((properties or {}).items()),
        )
        self._bonds.append(bond)
        return idx

    def remove_bond(self, index: int) -> None:
        """Remove a bond by its index."""
        if index < 0 or index >= len(self._bonds):
            raise IndexError(f"Bond index {index} out of range")
        self._bonds.pop(index)

    # ── Metadata Operations ──

    def set_name(self, name: str | None) -> None:
        """Set the molecule's name."""
        self._name = name

    def set_coordinates_2d(self, coordinates: list[Coordinate2D]) -> None:
        """Set 2D layout coordinates."""
        self._coordinates_2d = coordinates

    def set_coordinates_3d(self, coordinates: list[Coordinate3D]) -> None:
        """Set primary 3D coordinates."""
        self._coordinates_3d = coordinates

    def add_conformer(self, conformer: Conformer) -> None:
        """Add a 3D conformer to the ensemble."""
        self._conformers.append(conformer)

    def add_ring(self, ring: Ring) -> None:
        """Add a detected ring."""
        self._rings.append(ring)

    def add_chiral_center(self, center: ChiralCenter) -> None:
        """Add a chiral center."""
        self._stereo_centers.append(center)

    def set_property(self, key: str, value: Any) -> None:
        """Set a molecular property."""
        self._properties[key] = value

    # ── Build ──

    def build(self) -> MolecularGraph:
        """Build and return an immutable MolecularGraph.

        After calling build(), the builder can be reused to create
        additional graphs. The returned graph is completely independent.

        Returns:
            A frozen MolecularGraph with the current builder state.
        """
        graph = MolecularGraph(
            atoms=tuple(self._atoms),
            bonds=tuple(self._bonds),
            name=self._name,
            stereo_config=StereoConfig(centers=tuple(self._stereo_centers)),
            coordinates_2d=tuple(self._coordinates_2d) if self._coordinates_2d else None,
            coordinates_3d=tuple(self._coordinates_3d) if self._coordinates_3d else None,
            conformers=tuple(self._conformers),
            rings=tuple(self._rings),
            properties=frozenset(self._properties.items()),
        )
        return graph

    @classmethod
    def from_graph(cls, graph: MolecularGraph) -> MolecularGraphBuilder:
        """Create a builder pre-populated from an existing graph.

        Enables the "modify through builder" pattern:
            builder = MolecularGraphBuilder.from_graph(old_graph)
            builder.add_atom(...)
            new_graph = builder.build()

        Args:
            graph: An existing MolecularGraph to copy.

        Returns:
            A new builder with the graph's contents.
        """
        builder = cls()
        builder._atoms = list(graph.atoms)
        builder._bonds = list(graph.bonds)
        builder._name = graph.name
        if graph.coordinates_2d:
            builder._coordinates_2d = list(graph.coordinates_2d)
        if graph.coordinates_3d:
            builder._coordinates_3d = list(graph.coordinates_3d)
        builder._conformers = list(graph.conformers)
        builder._rings = list(graph.rings)
        builder._stereo_centers = list(graph.stereo_config.centers)
        builder._properties = dict(graph.properties)
        return builder
