"""Organometallic chemistry engine (M37).

Provides deterministic, graph-based perception of organometallic
coordination chemistry:

* **Metal-center detection** — identifies transition metals, lanthanides and
  actinides (the elements that exhibit variable coordination) while excluding
  alkali/alkaline-earth metals, which form ionic salts rather than directional
  complexes.
* **Dative (coordinate covalent) bond perception** — locates bonds between a
  Lewis-base donor atom and a metal acceptor, where the donor retains its lone
  pair (N, O, P, S, C-donor ligands such as cyanide and carbonyl, and
  halides).
* **Coordination-geometry classification** — assigns a VSEPR-style geometry
  from the coordination number, with a *d8 square-planar* exception
  (Ni(II), Pd(II), Pt(II), Rh(I), Ir(I), Au(III)) and an optional 3D
  refinement that distinguishes square-planar from tetrahedral
  four-coordinate centres when 3-D coordinates are available.

The engine is **deterministic** (no RDKit, no force fields): every geometry is
derived from the molecular graph topology plus, optionally, an explicit
3-D coordinate check.  This is a Milestone 2 feature; it is lazily registered
and intentionally performs no SMILES parsing itself, so it composes with the
existing parsing pipeline via :class:`~chemengine.core.graph.MolecularGraph`.

Public API
----------
data models
    :class:`CoordinationGeometry`, :class:`DativeBond`, :class:`Ligand`,
    :class:`CoordinationComplex`
perception
    :func:`is_metal_center`, :func:`perceive_dative_bonds`,
    :func:`perceive_ligands`, :func:`classify_coordination_geometry`,
    :func:`analyze`
annotation / serialization
    :func:`annotate_dative_bonds`, :func:`organometallic_complex_to_dict`,
    :func:`dict_to_coordination_complex`
reference + registration
    :data:`REFERENCE_ORGANOMETALLIC_ORACLE`,
    :func:`register_organometallic_algorithms`
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from chemengine.core.atoms import Atom
from chemengine.core.bonds import Bond, BondType
from chemengine.core.enums import Hybridization, StereoCategory
from chemengine.core.geometry import Coordinate3D
from chemengine.core.graph import MolecularGraph

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from chemengine.core.registry import AlgorithmRegistry

__all__ = [
    "CoordinationGeometry",
    "DativeBond",
    "Ligand",
    "CoordinationComplex",
    "REFERENCE_ORGANOMETALLIC_ORACLE",
    "COORDINATION_CATALOGUE_VERSION",
    "is_metal_center",
    "perceive_dative_bonds",
    "perceive_ligands",
    "classify_coordination_geometry",
    "analyze",
    "annotate_dative_bonds",
    "organometallic_complex_to_dict",
    "dict_to_coordination_complex",
    "register_organometallic_algorithms",
]

logger = logging.getLogger(__name__)

# ── Catalogue metadata ───────────────────────────────────────────────────────

_COORDINATION_CATALOGUE_VERSION: Final[tuple[int, int, int]] = (1, 0, 0)
COORDINATION_CATALOGUE_VERSION: Final[str] = ".".join(
    str(part) for part in _COORDINATION_CATALOGUE_VERSION
)

# ── Chemical heuristics ──────────────────────────────────────────────────────

# Lewis-base donors capable of donating a lone pair to a metal centre.
# Atomic numbers are used for O(1) membership tests.  Hydrogen is deliberately
# excluded -- metal hydrides are out of scope for v1.
_DONOR_ATOMIC_NUMBERS: Final[frozenset[int]] = frozenset(
    {
        # Carbon (organometallic M-C sigma donation: alkyls / aryls)
        6,
        # Pnictogens: N, P, As, Sb
        7, 15, 33, 51,
        # Chalcogens: O, S, Se, Te
        8, 16, 34, 52,
        # Halogens: F, Cl, Br, I, At
        9, 17, 35, 53, 85,
    }
)

# d8 metals that adopt a square-planar geometry when four-coordinate and in
# their characteristic oxidation state.  Keyed by (symbol, formal charge).
_D8_SQUARE_PLANAR: Final[frozenset[tuple[str, int]]] = frozenset(
    {
        ("Ni", 2),
        ("Pd", 2),
        ("Pt", 2),
        ("Rh", 1),
        ("Ir", 1),
        ("Au", 3),
    }
)

# Coordination-number -> (name, hybridization, stereo category, planar?)
_GEOMETRY_BY_CN: Final[dict[int, tuple[str, Hybridization, StereoCategory, bool]]] = {
    0: ("unknown", Hybridization.UNKNOWN, StereoCategory.NONE, False),
    1: ("linear", Hybridization.SP, StereoCategory.PLANAR, True),
    2: ("linear", Hybridization.SP, StereoCategory.PLANAR, True),
    3: ("trigonal_planar", Hybridization.SP2, StereoCategory.PLANAR, True),
    4: ("tetrahedral", Hybridization.SP3, StereoCategory.TETRAHEDRAL, False),
    5: ("trigonal_bipyramidal", Hybridization.SP3D, StereoCategory.NONE, False),
    6: ("octahedral", Hybridization.SP3D2, StereoCategory.OCTAHEDRAL, False),
    7: ("pentagonal_bipyramidal", Hybridization.UNKNOWN, StereoCategory.NONE, False),
    8: ("square_antiprismatic", Hybridization.UNKNOWN, StereoCategory.NONE, False),
}
_DEFAULT_GEOMETRY: Final[tuple[str, Hybridization, StereoCategory, bool]] = (
    "polyhedral",
    Hybridization.UNKNOWN,
    StereoCategory.NONE,
    False,
)
_PLANARITY_TOLERANCE: Final[float] = 1.0e-6


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CoordinationGeometry:
    """VSEPR-style geometry surrounding a metal centre.

    Attributes:
        name: Canonical geometry name (e.g. ``"octahedral"``).
        hybridization: Expected orbital hybridization of the centre.
        coordination_number: Number of donor atoms bound to the centre.
        category: Stereo-electronic category from the engine enum.
        is_square_planar: True when the geometry is square-planar.
        is_planar: True when the donor set lies in a plane.
    """

    name: str
    hybridization: Hybridization
    coordination_number: int
    category: StereoCategory
    is_square_planar: bool = False
    is_planar: bool = False


@dataclass(frozen=True, slots=True)
class DativeBond:
    """A coordinate (dative) bond from a donor to a metal acceptor.

    Attributes:
        bond_index: Index of the bond in ``MolecularGraph.bonds``.
        donor_index: Index of the Lewis-base donor atom.
        acceptor_index: Index of the metal acceptor atom.
        direction: Human-readable direction ``"donor->acceptor"``.
        bond_type: Bond classification (always ``BondType.DATIVE``).
    """

    bond_index: int
    donor_index: int
    acceptor_index: int
    direction: str = "donor->acceptor"
    bond_type: BondType = BondType.DATIVE


@dataclass(frozen=True, slots=True)
class Ligand:
    """A ligand bound to a metal centre.

    Attributes:
        donor_index: Index of the donor atom directly bonded to the metal.
        donor_element: Symbol of the donor element (e.g. ``"N"``).
        atoms: Indices of all atoms belonging to the ligand fragment.
        formula: Hill-systematic formula of the ligand fragment.
        charge: Formal charge of the whole ligand fragment.
        is_ionic: True when the ligand carries a formal charge.
        is_chelating: True when the ligand donates more than one lone pair.
        name: Human-readable ligand name.
    """

    donor_index: int
    donor_element: str
    atoms: tuple[int, ...] = ()
    formula: str = ""
    charge: int = 0
    is_ionic: bool = False
    is_chelating: bool = False
    name: str = ""


@dataclass(frozen=True, slots=True)
class CoordinationComplex:
    """A single metal centre with its coordination environment.

    Attributes:
        center_index: Index of the metal atom in the graph.
        metal: Element symbol of the metal (e.g. ``"Co"``).
        metal_atomic_number: Atomic number of the metal.
        oxidation_state: Formal charge on the metal atom.
        charge: Net charge of the whole complex (metal + ligands).
        coordination_number: Number of donor atoms surrounding the metal.
        geometry: Perceived coordination geometry.
        ligands: Ligands bound to the centre, ordered by donor index.
        dative_bonds: Dative bonds with this centre as the acceptor.
    """

    center_index: int
    metal: str
    metal_atomic_number: int
    oxidation_state: int | None
    charge: int
    coordination_number: int
    geometry: CoordinationGeometry
    ligands: tuple[Ligand, ...] = field(default_factory=tuple)
    dative_bonds: tuple[DativeBond, ...] = field(default_factory=tuple)



# ── Reference catalogue ──────────────────────────────────────────────────────

# Curated, chemically-correct reference complexes.  Each entry maps a common
# name to the *expected* perception output.  Test fixtures build the
# corresponding molecular graphs and assert against these expectations, so the
# catalogue doubles as living documentation of the engine's contracts.
REFERENCE_ORGANOMETALLIC_ORACLE: Final[dict[str, dict[str, object]]] = {
    "hexaamminecobalt(III)": {
        "metal": "Co",
        "metal_atomic_number": 27,
        "oxidation_state": 3,
        "coordination_number": 6,
        "geometry": "octahedral",
        "num_ligands": 6,
        "num_dative_bonds": 6,
        "charge": 3,
    },
    "tetracyanonickelate(II)": {
        "metal": "Ni",
        "metal_atomic_number": 28,
        "oxidation_state": 2,
        "coordination_number": 4,
        "geometry": "square_planar",
        "num_ligands": 4,
        "num_dative_bonds": 4,
        "charge": -2,
    },
    "tetrachlorocobaltate(II)": {
        "metal": "Co",
        "metal_atomic_number": 27,
        "oxidation_state": 2,
        "coordination_number": 4,
        "geometry": "tetrahedral",
        "num_ligands": 4,
        "num_dative_bonds": 4,
        "charge": -2,
    },
    "hexacyanoferrate(II)": {
        "metal": "Fe",
        "metal_atomic_number": 26,
        "oxidation_state": 2,
        "coordination_number": 6,
        "geometry": "octahedral",
        "num_ligands": 6,
        "num_dative_bonds": 6,
        "charge": -4,
    },
    "hexacyanoferrate(III)": {
        "metal": "Fe",
        "metal_atomic_number": 26,
        "oxidation_state": 3,
        "coordination_number": 6,
        "geometry": "octahedral",
        "num_ligands": 6,
        "num_dative_bonds": 6,
        "charge": -3,
    },
    "tetraammineplatinum(II)": {
        "metal": "Pt",
        "metal_atomic_number": 78,
        "oxidation_state": 2,
        "coordination_number": 4,
        "geometry": "square_planar",
        "num_ligands": 4,
        "num_dative_bonds": 4,
        "charge": 2,
    },
    "diammineargent(I)": {
        "metal": "Ag",
        "metal_atomic_number": 47,
        "oxidation_state": 1,
        "coordination_number": 2,
        "geometry": "linear",
        "num_ligands": 2,
        "num_dative_bonds": 2,
        "charge": 1,
    },
    "hexaaquazinc(II)": {
        "metal": "Zn",
        "metal_atomic_number": 30,
        "oxidation_state": 2,
        "coordination_number": 6,
        "geometry": "octahedral",
        "num_ligands": 6,
        "num_dative_bonds": 6,
        "charge": 2,
    },
    "pentacarbonyliron(0)": {
        "metal": "Fe",
        "metal_atomic_number": 26,
        "oxidation_state": 0,
        "coordination_number": 5,
        "geometry": "trigonal_bipyramidal",
        "num_ligands": 5,
        "num_dative_bonds": 5,
        "charge": 0,
    },
    "tetracarbonylnickel(0)": {
        "metal": "Ni",
        "metal_atomic_number": 28,
        "oxidation_state": 0,
        "coordination_number": 4,
        "geometry": "tetrahedral",
        "num_ligands": 4,
        "num_dative_bonds": 4,
        "charge": 0,
    },
}



# ── Perception primitives ────────────────────────────────────────────────────


def is_metal_center(atom: Atom) -> bool:
    """Return True when the atom is a coordination-capable metal centre.

    A centre qualifies when it is a transition metal, lanthanide, or actinide.
    Alkali and alkaline-earth metals form ionic salts rather than directional
    complexes and are excluded.  Wildcard atoms (Z = 0) are not metals.
    """
    if atom.atomic_number == 0:
        return False
    try:
        element = atom.element
    except (AttributeError, KeyError, ValueError):
        return False
    return element.is_transition_metal or element.is_lanthanide or element.is_actinide


def _donor_neighbors(graph: MolecularGraph, center: int) -> list[int]:
    """Return donor-atom indices bonded to the metal center, ascending order.

    Metal-metal bonds are skipped and hydrogen is excluded (metal hydrides are
    out of scope for v1).
    """
    donors: list[int] = []
    for neighbor in graph.get_neighbors(center):
        neighbor_atom = graph.atoms[neighbor]
        if neighbor_atom.atomic_number == 1:
            continue
        if is_metal_center(neighbor_atom):
            continue
        if neighbor_atom.atomic_number in _DONOR_ATOMIC_NUMBERS:
            donors.append(neighbor)
    return donors


def perceive_dative_bonds(graph: MolecularGraph) -> tuple[DativeBond, ...]:
    """Perceive coordinate (dative) bonds in a molecular graph.

    A bond is dative when exactly one endpoint is a metal centre and the other
    is a Lewis-base donor atom (N, O, P, S, halogen, or a carbon donor).
    Metal-metal bonds are not treated as dative.  The graph is not mutated.

    Args:
        graph: The molecular graph to inspect.

    Returns:
        Dative bonds ordered by their position in ``graph.bonds``.

    Raises:
        TypeError: If *graph* is not a MolecularGraph.
    """
    if not isinstance(graph, MolecularGraph):
        raise TypeError(f"Expected MolecularGraph, got {type(graph).__name__}")
    dative: list[DativeBond] = []
    for bond_index, bond in enumerate(graph.bonds):
        acceptor, donor = _dative_endpoints(graph, bond)
        if acceptor is not None and donor is not None:
            dative.append(
                DativeBond(
                    bond_index=bond_index,
                    donor_index=donor,
                    acceptor_index=acceptor,
                )
            )
    return tuple(dative)


def _dative_endpoints(graph: MolecularGraph, bond: Bond) -> tuple[int | None, int | None]:
    """Return (acceptor, donor) indices for a dative bond, or (None, None).

    A bond qualifies only when one endpoint is a metal centre and the other is
    a donor atom that is not itself a metal.
    """
    a1 = graph.atoms[bond.atom1]
    a2 = graph.atoms[bond.atom2]
    left_metal = is_metal_center(a1)
    right_metal = is_metal_center(a2)
    if left_metal and not right_metal and a2.atomic_number in _DONOR_ATOMIC_NUMBERS:
        return bond.atom1, bond.atom2
    if right_metal and not left_metal and a1.atomic_number in _DONOR_ATOMIC_NUMBERS:
        return bond.atom2, bond.atom1
    return None, None



def _ligand_components(
    graph: MolecularGraph,
) -> tuple[list[int], dict[int, int]]:
    """Partition non-metal atoms into connected components.

    Metal centres act as separators between ligand fragments (a ligand never
    passes through a metal).  Returns (components, atom_to_component) where
    each component is a sorted list of atom indices and the map gives the
    component id for each non-metal atom.
    """
    metal_atoms = {i for i, a in enumerate(graph.atoms) if is_metal_center(a)}
    atom_to_component: dict[int, int] = {}
    components: list[int] = []
    seen: set[int] = set()
    for start in range(graph.num_atoms):
        if start in metal_atoms or start in seen:
            continue
        component: list[int] = []
        queue: deque[int] = deque([start])
        while queue:
            current = queue.popleft()
            if current in seen or current in metal_atoms:
                continue
            seen.add(current)
            component.append(current)
            for neighbor in graph.get_neighbors(current):
                if neighbor not in seen and neighbor not in metal_atoms:
                    queue.append(neighbor)
        components.append(sorted(component))
        component_id = len(components) - 1
        for atom_index in component:
            atom_to_component[atom_index] = component_id
    return components, atom_to_component


def _format_count(symbol: str, count: int) -> str:
    """Render an element symbol with its count (omitting a count of 1)."""
    return symbol if count == 1 else f"{symbol}{count}"


def _hill_formula(element_counts: dict[str, int]) -> str:
    """Format element counts as a Hill-systematic formula string.

    Carbon is ordered first (if present), then hydrogen, with the remaining
    elements in alphabetical order.
    """
    if not element_counts:
        return ""
    has_carbon = element_counts.get("C", 0) > 0
    parts: list[str] = []
    keys = sorted(element_counts)
    if has_carbon:
        keys.remove("C")
        parts.append(_format_count("C", element_counts["C"]))
        if element_counts.get("H", 0) > 0:
            keys.remove("H")
            parts.append(_format_count("H", element_counts["H"]))
    for key in keys:
        parts.append(_format_count(key, element_counts[key]))
    return "".join(parts)


def _ligand_name(symbol: str, charge: int, atom_count: int) -> str:
    """Derive a short human-readable name for a ligand fragment."""
    if atom_count == 1:
        sign = "-" if charge < 0 else ("+" if charge > 0 else "")
        return f"{symbol}{sign}"
    return symbol


def perceive_ligands(
    graph: MolecularGraph, center_index: int
) -> tuple[Ligand, ...]:
    """Perceive the ligands bound to a metal centre.

    Each ligand is the connected, non-metallic fragment containing a donor atom
    bonded to the centre.  Ligands are ordered by donor index for deterministic
    output.

    Args:
        graph: The molecular graph.
        center_index: Index of the metal centre.

    Returns:
        Ligands bound to the centre (possibly empty), ordered by donor index.

    Raises:
        TypeError: If *graph* is not a MolecularGraph.
        ValueError: If the atom is not a metal centre.
    """
    if not isinstance(graph, MolecularGraph):
        raise TypeError(f"Expected MolecularGraph, got {type(graph).__name__}")
    if not is_metal_center(graph.atoms[center_index]):
        raise ValueError(
            f"Atom {center_index} ({graph.atoms[center_index].symbol}) "
            "is not a metal centre"
        )
    donor_indices = _donor_neighbors(graph, center_index)
    if not donor_indices:
        return ()
    components, atom_to_component = _ligand_components(graph)
    donors_by_component: dict[int, list[int]] = {}
    for donor in donor_indices:
        comp_id = atom_to_component[donor]
        donors_by_component.setdefault(comp_id, []).append(donor)
    ligands: list[Ligand] = []
    for comp_id, donors in donors_by_component.items():
        atoms = tuple(components[comp_id])
        element_counts: dict[str, int] = {}
        charge = 0
        for atom_index in atoms:
            atom = graph.atoms[atom_index]
            symbol = atom.symbol
            element_counts[symbol] = element_counts.get(symbol, 0) + 1
            charge += atom.formal_charge
        primary_donor = donors[0]
        donor_element = graph.atoms[primary_donor].symbol
        ligands.append(
            Ligand(
                donor_index=primary_donor,
                donor_element=donor_element,
                atoms=atoms,
                formula=_hill_formula(element_counts),
                charge=charge,
                is_ionic=charge != 0,
                is_chelating=len(donors) > 1,
                name=_ligand_name(donor_element, charge, len(atoms)),
            )
        )
    ligands.sort(key=lambda ligand: ligand.donor_index)
    return tuple(ligands)



def _four_atoms_coplanar(
    a: Coordinate3D, b: Coordinate3D, c: Coordinate3D, d: Coordinate3D
) -> bool:
    """Return True when four 3-D points are coplanar (tetrahedron volume ~ 0)."""
    ab = (b.x - a.x, b.y - a.y, b.z - a.z)
    ac = (c.x - a.x, c.y - a.y, c.z - a.z)
    ad = (d.x - a.x, d.y - a.y, d.z - a.z)
    determinant = (
        ab[0] * (ac[1] * ad[2] - ac[2] * ad[1])
        - ab[1] * (ac[0] * ad[2] - ac[2] * ad[0])
        + ab[2] * (ac[0] * ad[1] - ac[1] * ad[0])
    )
    return abs(determinant) / 6.0 < _PLANARITY_TOLERANCE


def classify_coordination_geometry(
    graph: MolecularGraph, center_index: int, *, refine_3d: bool = False
) -> CoordinationGeometry:
    """Classify the coordination geometry around a metal centre.

    Geometry is derived primarily from the coordination number (VSEPR-style),
    with two refinements:

    * a d8 square-planar exception for Ni(II), Pd(II), Pt(II), Rh(I), Ir(I)
      and Au(III) when four-coordinate; and
    * an optional 3-D check (refine_3d=True) that upgrades a four-coordinate
      centre to square-planar when its four donor atoms are coplanar.

    Args:
        graph: The molecular graph.
        center_index: Index of the metal centre.
        refine_3d: When True, use 3-D coordinates to refine four-coordinate
            geometry (square-planar vs tetrahedral).

    Returns:
        The perceived CoordinationGeometry.

    Raises:
        TypeError: If *graph* is not a MolecularGraph.
        ValueError: If the atom is not a metal centre.
    """
    if not isinstance(graph, MolecularGraph):
        raise TypeError(f"Expected MolecularGraph, got {type(graph).__name__}")
    atom = graph.atoms[center_index]
    if not is_metal_center(atom):
        raise ValueError(f"Atom {center_index} ({atom.symbol}) is not a metal center")
    donor_indices = _donor_neighbors(graph, center_index)
    coordination_number = len(donor_indices)
    name, hybridization, category, planar = _GEOMETRY_BY_CN.get(
        coordination_number, _DEFAULT_GEOMETRY
    )
    is_square_planar = False
    element = atom.element
    if coordination_number == 4 and (element.symbol, atom.formal_charge) in _D8_SQUARE_PLANAR:
        name = "square_planar"
        hybridization = Hybridization.UNKNOWN
        category = StereoCategory.SQUARE_PLANAR
        is_square_planar = True
    elif (
        refine_3d
        and coordination_number == 4
        and not is_square_planar
        and graph.coordinates_3d is not None
    ):
        points = [graph.coordinates_3d[i] for i in donor_indices]
        if _four_atoms_coplanar(*points):
            name = "square_planar"
            hybridization = Hybridization.UNKNOWN
            category = StereoCategory.SQUARE_PLANAR
            is_square_planar = True
    return CoordinationGeometry(
        name=name,
        hybridization=hybridization,
        coordination_number=coordination_number,
        category=category,
        is_square_planar=is_square_planar,
        is_planar=planar or is_square_planar,
    )



def analyze(
    graph: MolecularGraph, *, refine_3d: bool = False
) -> tuple[CoordinationComplex, ...]:
    """Analyze organometallic coordination complexes in a molecular graph.

    Each metal centre is reported as a CoordinationComplex containing its
    oxidation state, ligands, dative bonds and geometry.  The input graph is
    never mutated.

    Args:
        graph: The molecular graph.
        refine_3d: Forwarded to classify_coordination_geometry.

    Returns:
        Complexes ordered by metal centre index (possibly empty).

    Raises:
        TypeError: If *graph* is not a MolecularGraph.
    """
    if not isinstance(graph, MolecularGraph):
        raise TypeError(f"Expected MolecularGraph, got {type(graph).__name__}")
    all_dative = perceive_dative_bonds(graph)
    complexes: list[CoordinationComplex] = []
    for center_index, atom in enumerate(graph.atoms):
        if not is_metal_center(atom):
            continue
        ligands = perceive_ligands(graph, center_index)
        dative = tuple(
            bond
            for bond in all_dative
            if bond.acceptor_index == center_index
        )
        geometry = classify_coordination_geometry(
            graph, center_index, refine_3d=refine_3d
        )
        ligands_charge = sum(ligand.charge for ligand in ligands)
        complexes.append(
            CoordinationComplex(
                center_index=center_index,
                metal=atom.symbol,
                metal_atomic_number=atom.atomic_number,
                oxidation_state=atom.formal_charge,
                charge=atom.formal_charge + ligands_charge,
                coordination_number=geometry.coordination_number,
                geometry=geometry,
                ligands=ligands,
                dative_bonds=dative,
            )
        )
    return tuple(complexes)



# ── Annotation / serialization ───────────────────────────────────────────────


def annotate_dative_bonds(graph: MolecularGraph) -> MolecularGraph:
    """Return a copy of the graph with dative bonds tagged BondType.DATIVE.

    Perception is performed and the donor-to-metal bonds of every perceived
    dative bond are rebuilt with bond_type = DATIVE.  All other atoms, bonds,
    coordinates and conformers are preserved.  The input graph is not mutated.

    Note:
        Rings and arbitrary properties metadata are not preserved by this
        round-trip, consistent with graph_to_dict / dict_to_graph behaviour.

    Args:
        graph: The molecular graph.

    Returns:
        A new graph with dative bonds annotated.

    Raises:
        TypeError: If *graph* is not a MolecularGraph.
    """
    if not isinstance(graph, MolecularGraph):
        raise TypeError(f"Expected MolecularGraph, got {type(graph).__name__}")
    from chemengine.io.serialization import dict_to_graph, graph_to_dict

    data = graph_to_dict(graph)
    dative_pairs = {
        (bond.donor_index, bond.acceptor_index)
        for bond in perceive_dative_bonds(graph)
    }
    for bond in data["bonds"]:
        pair = (bond["atom1"], bond["atom2"])
        reverse = (bond["atom2"], bond["atom1"])
        if pair in dative_pairs or reverse in dative_pairs:
            bond["bond_type"] = BondType.DATIVE.value
    return dict_to_graph(data)


def organometallic_complex_to_dict(complex: CoordinationComplex) -> dict[str, Any]:
    """Serialize a CoordinationComplex to a JSON-ready dictionary.

    Args:
        complex: The coordination complex to serialize.

    Returns:
        A dictionary with center_index, metal, charge, geometry, ligands and
        dative_bonds keys.
    """
    return {
        "center_index": complex.center_index,
        "metal": complex.metal,
        "metal_atomic_number": complex.metal_atomic_number,
        "oxidation_state": complex.oxidation_state,
        "charge": complex.charge,
        "coordination_number": complex.coordination_number,
        "geometry": {
            "name": complex.geometry.name,
            "hybridization": complex.geometry.hybridization.value,
            "coordination_number": complex.geometry.coordination_number,
            "category": complex.geometry.category.value,
            "is_square_planar": complex.geometry.is_square_planar,
            "is_planar": complex.geometry.is_planar,
        },
        "ligands": [
            {
                "donor_index": ligand.donor_index,
                "donor_element": ligand.donor_element,
                "atoms": list(ligand.atoms),
                "formula": ligand.formula,
                "charge": ligand.charge,
                "is_ionic": ligand.is_ionic,
                "is_chelating": ligand.is_chelating,
                "name": ligand.name,
            }
            for ligand in complex.ligands
        ],
        "dative_bonds": [
            {
                "bond_index": bond.bond_index,
                "donor_index": bond.donor_index,
                "acceptor_index": bond.acceptor_index,
                "direction": bond.direction,
                "bond_type": bond.bond_type.value,
            }
            for bond in complex.dative_bonds
        ],
        "num_ligands": len(complex.ligands),
        "num_dative_bonds": len(complex.dative_bonds),
    }


def dict_to_coordination_complex(data: dict[str, Any]) -> CoordinationComplex:
    """Deserialize a dictionary produced by organometallic_complex_to_dict.

    Args:
        data: Serialized complex dictionary.

    Returns:
        A reconstructed CoordinationComplex.
    """
    geometry_data = data["geometry"]
    ligands = tuple(
        Ligand(
            donor_index=item["donor_index"],
            donor_element=item["donor_element"],
            atoms=tuple(item["atoms"]),
            formula=item.get("formula", ""),
            charge=item.get("charge", 0),
            is_ionic=item.get("is_ionic", False),
            is_chelating=item.get("is_chelating", False),
            name=item.get("name", ""),
        )
        for item in data.get("ligands", [])
    )
    dative_bonds = tuple(
        DativeBond(
            bond_index=item["bond_index"],
            donor_index=item["donor_index"],
            acceptor_index=item["acceptor_index"],
            direction=item.get("direction", "donor->acceptor"),
            bond_type=(
                BondType(item["bond_type"])
                if "bond_type" in item
                else BondType.DATIVE
            ),
        )
        for item in data.get("dative_bonds", [])
    )
    return CoordinationComplex(
        center_index=data["center_index"],
        metal=data["metal"],
        metal_atomic_number=data["metal_atomic_number"],
        oxidation_state=data["oxidation_state"],
        charge=data["charge"],
        coordination_number=data["coordination_number"],
        geometry=CoordinationGeometry(
            name=geometry_data["name"],
            hybridization=Hybridization(geometry_data["hybridization"]),
            coordination_number=geometry_data["coordination_number"],
            category=StereoCategory(geometry_data["category"]),
            is_square_planar=geometry_data.get("is_square_planar", False),
            is_planar=geometry_data.get("is_planar", False),
        ),
        ligands=ligands,
        dative_bonds=dative_bonds,
    )



# ── Registry integration ─────────────────────────────────────────────────────


def register_organometallic_algorithms(
    registry: AlgorithmRegistry | None = None, *, replace: bool = False
) -> AlgorithmRegistry:
    """Register the M37 organometallic algorithms on a registry.

    The registration is idempotent: calling it repeatedly re-registers on a
    fresh registry but is a no-op (unless replace=True) on a registry that
    already contains the organometallic domain entries.  When registry is None
    the global registry is used.

    Args:
        registry: Target registry. Defaults to the global registry.
        replace: Overwrite existing entries when True.

    Returns:
        The registry that was registered on.
    """
    from chemengine.core.registry import AlgorithmEntry, get_global_registry

    target = registry if registry is not None else get_global_registry()
    version = f"m37.{COORDINATION_CATALOGUE_VERSION}"
    tags = frozenset(
        {"organometallic", "dative", "coordination", "deterministic"}
    )
    entries: tuple[AlgorithmEntry, ...] = (
        AlgorithmEntry(
            domain="organometallic",
            name="analyze",
            version=version,
            algorithm=analyze,
            input_type=MolecularGraph,
            output_type=tuple,
            tags=tags,
        ),
        AlgorithmEntry(
            domain="organometallic",
            name="classify_geometry",
            version=version,
            algorithm=classify_coordination_geometry,
            input_type=MolecularGraph,
            output_type=CoordinationGeometry,
            tags=tags,
        ),
        AlgorithmEntry(
            domain="organometallic",
            name="dative_bonds",
            version=version,
            algorithm=perceive_dative_bonds,
            input_type=MolecularGraph,
            output_type=tuple,
            tags=tags,
        ),
    )
    for entry in entries:
        key = (entry.domain, entry.name)
        if key in target and not replace:
            logger.debug(
                "Skipping registration of %s=%s (already registered)",
                key[0],
                key[1],
            )
            continue
        target.register(entry)
    return target
