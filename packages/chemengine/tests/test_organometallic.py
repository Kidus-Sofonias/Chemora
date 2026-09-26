"""Tests for the M37 organometallic chemistry engine.

Covers:
    - The 10-reference Complex catalogue (``REFERENCE_ORGANOMETALLIC_ORACLE``):
      geometry, coordination number, ligand count, dative-bond count, charge.
    - Dative (coordinate covalent) bond perception: directed donor->metal,
      metal-metal bonds excluded, round-trip annotation via serialization.
    - Ligand perception: ionic vs neutral, chelating vs monodentate.
    - Coordination-geometry classification: VSEPR from coordination number,
      the d8 square-planar exception, and the optional 3-D coplanarity
      refinement.
    - Metal-center classification edge cases (transition / lanthanide /
      actinide vs alkali vs wildcard).
    - ``AlgorithmRegistry`` idempotent registration + ``ChemEngineAPI``
      dispatch (tool registered, convenience method, ``execute_tool``).
    - Lazy-import gate: ``import chemengine`` must not pull in
      ``chemengine.organometallic``.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from chemengine.core.atoms import Atom
from chemengine.core.bonds import BondType
from chemengine.core.enums import BondOrder, StereoCategory
from chemengine.core.geometry import Coordinate3D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.core.registry import AlgorithmRegistry, reset_global_registry
from chemengine.core.tool_interface import ChemEngineAPI
from chemengine.organometallic import (
    REFERENCE_ORGANOMETALLIC_ORACLE,
    CoordinationComplex,
    DativeBond,
    Ligand,
    analyze,
    annotate_dative_bonds,
    classify_coordination_geometry,
    is_metal_center,
    perceive_dative_bonds,
    perceive_ligands,
    register_organometallic_algorithms,
)


def _coord_graph(
    metal_z: int,
    metal_fc: int,
    ligands: list[tuple[int, int, list[tuple[int, int]]]],
    coords: list[Coordinate3D] | None = None,
) -> tuple[MolecularGraph, int]:
    """Build a metal complex graph; the metal is always atom index 0.

    ``ligands`` is a list of ``(donor_z, donor_fc, extras)`` where ``extras``
    is a list of ``(z, fc)`` atoms bonded to the donor (e.g. the H's of NH3).
    """
    builder = MolecularGraphBuilder()
    metal = builder.add_atom(metal_z, formal_charge=metal_fc)
    for donor_z, donor_fc, extras in ligands:
        donor = builder.add_atom(donor_z, formal_charge=donor_fc)
        builder.add_bond(metal, donor, BondOrder.SINGLE)
        for z, fc in extras:
            extra = builder.add_atom(z, formal_charge=fc)
            builder.add_bond(donor, extra, BondOrder.SINGLE)
    if coords is not None:
        builder.set_coordinates_3d(coords)
    return builder.build(), metal


# (metal_z, metal_fc, ligands) describing each oracle complex.  The metal is
# always atom 0; each ligand is (donor_z, donor_fc, extra_atoms).
ORACLE_SPECS: dict[str, tuple[int, int, list]] = {
    "hexaamminecobalt(III)": (27, 3, [(7, 0, [(1, 0), (1, 0), (1, 0)]) for _ in range(6)]),
    "tetracyanonickelate(II)": (28, 2, [(6, -1, [(7, 0)]) for _ in range(4)]),
    "tetrachlorocobaltate(II)": (27, 2, [(17, -1, []) for _ in range(4)]),
    "hexacyanoferrate(II)": (26, 2, [(6, -1, [(7, 0)]) for _ in range(6)]),
    "hexacyanoferrate(III)": (26, 3, [(6, -1, [(7, 0)]) for _ in range(6)]),
    "tetraammineplatinum(II)": (78, 2, [(7, 0, [(1, 0), (1, 0), (1, 0)]) for _ in range(4)]),
    "diammineargent(I)": (47, 1, [(7, 0, [(1, 0), (1, 0), (1, 0)]) for _ in range(2)]),
    "hexaaquazinc(II)": (30, 2, [(8, 0, [(1, 0), (1, 0)]) for _ in range(6)]),
    "pentacarbonyliron(0)": (26, 0, [(6, 0, [(8, 0)]) for _ in range(5)]),
    "tetracarbonylnickel(0)": (28, 0, [(6, 0, [(8, 0)]) for _ in range(4)]),
}



@pytest.mark.parametrize("name", list(REFERENCE_ORGANOMETALLIC_ORACLE))
def test_oracle_complexes_match_reference(name: str) -> None:
    """Every curated oracle complex produces the documented perception."""
    oracle = REFERENCE_ORGANOMETALLIC_ORACLE[name]
    spec = ORACLE_SPECS[name]
    graph, center = _coord_graph(spec[0], spec[1], spec[2])
    complex = analyze(graph)[0]
    assert complex.metal == oracle["metal"]
    assert complex.metal_atomic_number == oracle["metal_atomic_number"]
    assert complex.oxidation_state == oracle["oxidation_state"]
    assert complex.coordination_number == oracle["coordination_number"]
    assert complex.geometry.name == oracle["geometry"]
    assert len(complex.ligands) == oracle["num_ligands"]
    assert len(complex.dative_bonds) == oracle["num_dative_bonds"]
    assert complex.charge == oracle["charge"]


def test_is_metal_center_classification() -> None:
    """Transition metals, lanthanides and actinides qualify; others do not."""
    assert is_metal_center(Atom(atomic_number=26))  # iron
    assert is_metal_center(Atom(atomic_number=30))  # zinc (d-block group 12)
    assert is_metal_center(Atom(atomic_number=47))  # silver (d-block group 11)
    assert is_metal_center(Atom(atomic_number=71))  # lutetium (lanthanide)
    assert is_metal_center(Atom(atomic_number=92))  # uranium (actinide)
    assert not is_metal_center(Atom(atomic_number=6))  # carbon
    assert not is_metal_center(Atom(atomic_number=11))  # sodium (alkali, excluded)
    assert not is_metal_center(Atom(atomic_number=1))  # hydrogen
    assert not is_metal_center(Atom(atomic_number=0))  # wildcard atom


def test_dative_bonds_directed_donor_to_metal() -> None:
    """Dative bonds point donor -> metal and are typed DATIVE."""
    graph, cobalt = _coord_graph(
        27, 3, [(7, 0, [(1, 0), (1, 0), (1, 0)]) for _ in range(6)]
    )
    dative = perceive_dative_bonds(graph)
    assert len(dative) == 6
    assert all(bond.acceptor_index == cobalt for bond in dative)
    assert all(bond.donor_index != cobalt for bond in dative)
    assert all(bond.bond_type == BondType.DATIVE for bond in dative)
    assert {graph.atoms[bond.donor_index].symbol for bond in dative} == {"N"}


def test_metal_metal_bond_is_not_dative() -> None:
    """A metal-metal bond is never perceived as a dative ligand bond."""
    builder = MolecularGraphBuilder()
    cobalt = builder.add_atom(27, formal_charge=2)
    nickel = builder.add_atom(28, formal_charge=2)
    builder.add_bond(cobalt, nickel, BondOrder.SINGLE)
    graph = builder.build()
    assert perceive_dative_bonds(graph) == ()
    complexes = analyze(graph)
    assert len(complexes) == 2
    assert {complex.metal for complex in complexes} == {"Co", "Ni"}


def test_annotate_dative_bonds_roundtrip() -> None:
    """annotate_dative_bonds tags donor->metal bonds and survives serialization."""
    graph, _ = _coord_graph(28, 2, [(6, -1, [(7, 0)]) for _ in range(4)])  # Ni(CN)4
    annotated = annotate_dative_bonds(graph)
    dative = [bond for bond in annotated.bonds if bond.bond_type == BondType.DATIVE]
    covalent = [bond for bond in annotated.bonds if bond.bond_type == BondType.COVALENT]
    assert len(dative) == 4
    assert len(covalent) == 4  # the four C-N internal ligand bonds
    # the original graph is left untouched (annotate returns a copy)
    assert all(bond.bond_type == BondType.COVALENT for bond in graph.bonds)
    from chemengine.io.serialization import dict_to_graph, graph_to_dict

    rebuilt = dict_to_graph(graph_to_dict(annotated))
    assert sum(1 for bond in rebuilt.bonds if bond.bond_type == BondType.DATIVE) == 4
    assert sum(1 for bond in rebuilt.bonds if bond.bond_type == BondType.COVALENT) == 4


def test_perceive_ligands_rejects_non_metal_center() -> None:
    """perceive_ligands raises ValueError when the atom is not a metal."""
    builder = MolecularGraphBuilder()
    carbon = builder.add_atom(6)
    hydrogen = builder.add_atom(1)
    builder.add_bond(carbon, hydrogen, BondOrder.SINGLE)
    graph = builder.build()
    with pytest.raises(ValueError, match="is not a metal centre"):
        perceive_ligands(graph, 0)


def test_perceive_dative_bonds_type_error() -> None:
    """Perceive a non-graph input raises TypeError."""
    with pytest.raises(TypeError):
        perceive_dative_bonds("not-a-graph")  # type: ignore[arg-type]


def test_complex_serialisation_round_trip() -> None:
    """A CoordinationComplex survives a to-dict / from-dict round-trip."""
    original: CoordinationComplex = analyze(
        _coord_graph(26, 2, [(6, -1, [(7, 0)]) for _ in range(6)])[0]
    )[0]
    from chemengine.organometallic import (
        dict_to_coordination_complex,
        organometallic_complex_to_dict,
    )

    restored = dict_to_coordination_complex(organometallic_complex_to_dict(original))
    assert restored.metal == original.metal
    assert restored.geometry.name == original.geometry.name
    assert restored.coordination_number == original.coordination_number
    assert len(restored.ligands) == len(original.ligands)
    assert len(restored.dative_bonds) == len(original.dative_bonds)



# ── Ligand perception ────────────────────────────────────────────────────────


def test_ligand_perception_ionic_monodentate() -> None:
    """CoCl4^2- : four anionic, monodentate chloride ligands."""
    graph, cobalt = _coord_graph(27, 2, [(17, -1, []) for _ in range(4)])
    ligands = perceive_ligands(graph, cobalt)
    assert len(ligands) == 4
    assert all(isinstance(ligand, Ligand) for ligand in ligands)
    assert all(ligand.is_ionic for ligand in ligands)
    assert all(ligand.charge == -1 for ligand in ligands)
    assert all(ligand.formula == "Cl" for ligand in ligands)
    assert all(not ligand.is_chelating for ligand in ligands)


def test_chelating_bidentate_ligand() -> None:
    """A single ethylenediamine fragment donating two nitrogens is chelating."""
    builder = MolecularGraphBuilder()
    cobalt = builder.add_atom(27, formal_charge=2)
    n1 = builder.add_atom(7, formal_charge=0)
    c1 = builder.add_atom(6, formal_charge=0)
    c2 = builder.add_atom(6, formal_charge=0)
    n2 = builder.add_atom(7, formal_charge=0)
    hydrogens = [builder.add_atom(1) for _ in range(8)]
    builder.add_bond(cobalt, n1, BondOrder.SINGLE)
    builder.add_bond(cobalt, n2, BondOrder.SINGLE)
    builder.add_bond(n1, c1, BondOrder.SINGLE)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, n2, BondOrder.SINGLE)
    for donor, start in ((n1, 0), (n2, 2), (c1, 4), (c2, 6)):
        builder.add_bond(donor, hydrogens[start])
        builder.add_bond(donor, hydrogens[start + 1])
    graph = builder.build()
    ligands = perceive_ligands(graph, cobalt)
    assert len(ligands) == 1
    assert ligands[0].is_chelating is True
    assert ligands[0].donor_element == "N"
    complex = analyze(graph)[0]
    assert complex.coordination_number == 2
    dative: tuple[DativeBond, ...] = perceive_dative_bonds(graph)
    assert len(dative) == 2


# ── Geometry classification ──────────────────────────────────────────────────


def test_geometry_d8_square_planar_exception() -> None:
    """Ni(II) d8 CN=4 is square-planar; Co(II) CN=4 is tetrahedral."""
    graph, nickel = _coord_graph(28, 2, [(6, 0, [(8, 0)]) for _ in range(4)])
    geometry = classify_coordination_geometry(graph, nickel)
    assert geometry.name == "square_planar"
    assert geometry.is_square_planar is True
    assert geometry.category == StereoCategory.SQUARE_PLANAR
    graph2, cobalt = _coord_graph(27, 2, [(17, -1, []) for _ in range(4)])
    geometry2 = classify_coordination_geometry(graph2, cobalt)
    assert geometry2.name == "tetrahedral"


def test_geometry_3d_coplanar_refinement() -> None:
    """A coplanar four-coordinate non-d8 centre upgrades to square-planar."""
    coords = [
        Coordinate3D(x=0.0, y=0.0, z=0.0),
        Coordinate3D(x=1.0, y=0.0, z=0.0),
        Coordinate3D(x=-1.0, y=0.0, z=0.0),
        Coordinate3D(x=0.0, y=1.0, z=0.0),
        Coordinate3D(x=0.0, y=-1.0, z=0.0),
    ]
    graph, titanium = _coord_graph(22, 4, [(7, 0, []) for _ in range(4)], coords=coords)
    base = classify_coordination_geometry(graph, titanium)
    assert base.name == "tetrahedral"
    refined = classify_coordination_geometry(graph, titanium, refine_3d=True)
    assert refined.name == "square_planar"
    assert refined.is_square_planar is True


def test_geometry_no_donor_center() -> None:
    """An isolated metal (coordination number 0) has unknown geometry."""
    graph, iron = _coord_graph(26, 2, [])
    geometry = classify_coordination_geometry(graph, iron)
    assert geometry.name == "unknown"
    assert geometry.coordination_number == 0
    assert analyze(graph)[0].geometry.name == "unknown"



# ── Registry + API wiring ────────────────────────────────────────────────────


def test_register_organometallic_algorithms_idempotent() -> None:
    """Registration is idempotent on an existing registry."""
    registry = AlgorithmRegistry()
    assert ("organometallic", "analyze") not in registry
    register_organometallic_algorithms(registry)
    register_organometallic_algorithms(registry)  # second call is a no-op
    assert ("organometallic", "analyze") in registry
    assert ("organometallic", "classify_geometry") in registry
    assert ("organometallic", "dative_bonds") in registry
    assert registry.get("organometallic", "dative_bonds").algorithm is perceive_dative_bonds


@pytest.fixture
def api() -> ChemEngineAPI:
    """A ChemEngineAPI with the builtin registry freshly reset and populated."""
    reset_global_registry()
    return ChemEngineAPI()


def test_api_tool_is_registered(api: ChemEngineAPI) -> None:
    """The analyze_organometallic tool is registered on the API."""
    names = {tool.name for tool in api.list_tools()}
    assert "analyze_organometallic" in names
    assert "analyze_organometallic" in {
        tool.name for tool in api.list_tools(category="organometallic")
    }


def test_api_convenience_method(api: ChemEngineAPI) -> None:
    """The convenience method returns serialized complexes for each center."""
    graph, _ = _coord_graph(27, 3, [(7, 0, [(1, 0), (1, 0), (1, 0)]) for _ in range(6)])
    result = api.analyze_organometallic(graph)
    assert len(result) == 1
    assert result[0]["metal"] == "Co"
    assert result[0]["geometry"]["name"] == "octahedral"
    assert result[0]["num_ligands"] == 6
    assert result[0]["num_dative_bonds"] == 6


def test_api_execute_tool_dispatches(api: ChemEngineAPI) -> None:
    """The analyze_organometallic tool round-trips through SMILES parse."""
    result = api.execute_tool("analyze_organometallic", {"smiles": "N[Fe+2]N"})
    assert "error" not in result
    assert result["num_complexes"] == 1
    assert result["complexes"][0]["geometry"]["name"] == "linear"


# ── Lazy-import gate ─────────────────────────────────────────────────────────


def test_organometallic_is_lazy_on_package_import() -> None:
    """``import chemengine`` must not eagerly import the organometallic module."""
    code = (
        "import sys; import chemengine; print("
        "'OMO_LAZY', 'chemengine.organometallic' not in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "OMO_LAZY True" in out.stdout
