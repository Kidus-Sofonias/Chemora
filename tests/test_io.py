"""Tests for Phase 11: IO Serialization
- JSON serialization/deserialization
- Dictionary serialization
- Format conversion
"""

import json

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.geometry import Coordinate2D, Coordinate3D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.io.serialization import (
    convert_format,
    dict_to_graph,
    graph_to_dict,
    graph_to_json,
    json_to_graph,
)

# ── Fixtures ──

def _make_methane():
    builder = MolecularGraphBuilder()
    c = builder.add_atom(6)
    for _ in range(4):
        h = builder.add_atom(1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_ethane():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    for c in (c1, c2):
        for _ in range(3):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_ethanol():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    o = builder.add_atom(8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o, BondOrder.SINGLE)
    for c, n in [(c1, 3), (c2, 2)]:
        for _ in range(n):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    h = builder.add_atom(1)
    builder.add_bond(o, h, BondOrder.SINGLE)
    builder.set_name("ethanol")
    return builder.build()


def _make_with_coordinates():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.set_coordinates_2d([
        Coordinate2D(0.0, 0.0),
        Coordinate2D(1.5, 0.0),
    ])
    builder.set_coordinates_3d([
        Coordinate3D(0.0, 0.0, 0.0),
        Coordinate3D(1.5, 0.0, 0.0),
    ])
    return builder.build()


# ── Serialization Tests ──

class TestGraphSerialization:
    def test_graph_to_dict(self):
        graph = _make_methane()
        d = graph_to_dict(graph)
        assert "atoms" in d
        assert "bonds" in d
        assert "formula" in d
        assert len(d["atoms"]) == 5  # C + 4H
        assert len(d["bonds"]) == 4

    def test_graph_to_dict_formula(self):
        graph = _make_ethane()
        d = graph_to_dict(graph)
        assert d["formula"] == "C2H6"

    def test_graph_to_dict_exact_mass(self):
        graph = _make_ethane()
        d = graph_to_dict(graph)
        assert "exact_mass" in d
        assert isinstance(d["exact_mass"], float)

    def test_graph_to_dict_name(self):
        graph = _make_ethanol()
        d = graph_to_dict(graph)
        assert d["name"] == "ethanol"

    def test_graph_to_json(self):
        graph = _make_ethane()
        json_str = graph_to_json(graph)
        data = json.loads(json_str)
        assert "atoms" in data
        assert "bonds" in data

    def test_graph_to_json_pretty(self):
        graph = _make_ethane()
        json_str = graph_to_json(graph, indent=2)
        assert "\n" in json_str  # Should be indented

    def test_atom_fields_in_dict(self):
        graph = _make_methane()
        d = graph_to_dict(graph)
        carbon = d["atoms"][0]
        assert carbon["atomic_number"] == 6
        assert carbon["symbol"] == "C"

    def test_bond_fields_in_dict(self):
        graph = _make_ethane()
        d = graph_to_dict(graph)
        bond = d["bonds"][0]
        assert "atom1" in bond
        assert "atom2" in bond
        assert "order" in bond

    def test_coordinates_in_dict(self):
        graph = _make_with_coordinates()
        d = graph_to_dict(graph)
        assert "coordinates_2d" in d
        assert len(d["coordinates_2d"]) == 2
        assert "coordinates_3d" in d
        assert len(d["coordinates_3d"]) == 2


# ── Deserialization Tests ──

class TestGraphDeserialization:
    def test_dict_roundtrip(self):
        graph = _make_ethane()
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        assert graph2.molecular_formula == graph.molecular_formula
        assert graph2.num_atoms == graph.num_atoms
        assert graph2.num_bonds == graph.num_bonds

    def test_json_roundtrip(self):
        graph = _make_ethanol()
        json_str = graph_to_json(graph)
        graph2 = json_to_graph(json_str)
        assert graph2.molecular_formula == graph.molecular_formula
        assert graph2.num_atoms == graph.num_atoms
        assert graph2.name == graph.name

    def test_coordinates_roundtrip(self):
        graph = _make_with_coordinates()
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        assert graph2.coordinates_2d is not None
        assert len(graph2.coordinates_2d) == 2
        assert abs(graph2.coordinates_2d[0].x - 0.0) < 1e-6
        assert abs(graph2.coordinates_2d[1].x - 1.5) < 1e-6

    def test_3d_coordinates_roundtrip(self):
        graph = _make_with_coordinates()
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        assert graph2.coordinates_3d is not None
        assert len(graph2.coordinates_3d) == 2

    def test_empty_graph_roundtrip(self):
        graph = MolecularGraph(atoms=(), bonds=())
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        assert graph2.num_atoms == 0

    def test_charged_atom_roundtrip(self):
        builder = MolecularGraphBuilder()
        n = builder.add_atom(7, formal_charge=1)
        for _ in range(4):
            h = builder.add_atom(1)
            builder.add_bond(n, h, BondOrder.SINGLE)
        graph = builder.build()
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        assert graph2.atoms[0].formal_charge == 1

    def test_heteroatom_roundtrip(self):
        graph = _make_ethanol()
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        # Check that oxygen is preserved
        has_oxygen = any(a.atomic_number == 8 for a in graph2.atoms)
        assert has_oxygen


# ── Format Conversion Tests ──

class TestFormatConversion:
    def test_convert_to_formula(self):
        graph = _make_ethane()
        result = convert_format(graph, "smiles", "formula")
        assert result == "C2H6"

    def test_convert_to_json(self):
        graph = _make_ethane()
        result = convert_format(graph, "smiles", "json")
        data = json.loads(result)
        assert "atoms" in data

    def test_convert_to_name(self):
        graph = _make_ethane()
        result = convert_format(graph, "smiles", "name")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_convert_unknown_format(self):
        graph = _make_ethane()
        with pytest.raises(ValueError, match="Unknown target format"):
            convert_format(graph, "smiles", "unknown_format")

    def test_convert_to_inchikey(self):
        graph = _make_ethane()
        result = convert_format(graph, "smiles", "inchikey")
        assert isinstance(result, str)
        assert len(result) == 27
        assert result.count("-") == 2

    def test_convert_to_inchi(self):
        graph = _make_ethane()
        result = convert_format(graph, "smiles", "inchi")
        assert isinstance(result, str)
        assert result.startswith("InChI=")


# ── API Integration Tests ──

class TestAPISerialization:
    def test_api_serialize_tool(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        result = api.execute_tool("serialize", {"smiles": "CCO"})
        assert "data" in result
        data = result["data"]
        assert "atoms" in data

    def test_api_serialize_json_format(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        result = api.execute_tool("serialize", {"smiles": "CC", "format": "json"})
        assert "data" in result
        data = json.loads(result["data"])
        assert "atoms" in data

    def test_api_name_molecule(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        result = api.execute_tool("name_molecule", {"smiles": "CC"})
        assert "name" in result
        assert isinstance(result["name"], str)
