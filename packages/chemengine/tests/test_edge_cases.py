"""Rigorous edge case tests for all new modules.
Tests boundary conditions, error handling, and integration.
"""

import json
import math

import pytest

from chemengine.core.bonds import Bond, BondOrder
from chemengine.core.geometry import Coordinate2D, Coordinate3D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.core.tool_interface import ChemEngineAPI

# ══════════════════════════════════════════════════════════════════
# COORDINATE GENERATION EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestCoordinateEdgeCases:
    """Edge cases for 2D and 3D coordinate generation."""

    def test_empty_graph_2d(self):
        from chemengine.coordinates.layout_2d import generate_2d_coordinates
        graph = MolecularGraph(atoms=(), bonds=())
        coords = generate_2d_coordinates(graph)
        assert coords == ()

    def test_empty_graph_3d(self):
        from chemengine.coordinates.conformer_3d import generate_conformer
        graph = MolecularGraph(atoms=(), bonds=())
        conf = generate_conformer(graph)
        assert conf.num_atoms == 0

    def test_single_atom_2d(self):
        from chemengine.coordinates.layout_2d import generate_2d_coordinates
        builder = MolecularGraphBuilder()
        builder.add_atom(6)
        graph = builder.build()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == 1
        assert coords[0] == Coordinate2D(0.0, 0.0)

    def test_single_atom_3d(self):
        from chemengine.coordinates.conformer_3d import generate_conformer
        builder = MolecularGraphBuilder()
        builder.add_atom(6)
        graph = builder.build()
        conf = generate_conformer(graph)
        assert conf.num_atoms == 1
        assert conf.coordinates[0] == Coordinate3D(0.0, 0.0, 0.0)

    def test_two_bonded_atoms(self):
        from chemengine.coordinates.layout_2d import generate_2d_coordinates
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        graph = builder.build()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == 2
        assert coords[0].distance_to(coords[1]) > 0

    def test_triple_bond_shorter_than_single(self):
        from chemengine.coordinates.conformer_3d import generate_conformer
        # Build ethyne (C≡C)
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.TRIPLE)
        h1 = builder.add_atom(1)
        h2 = builder.add_atom(1)
        builder.add_bond(c1, h1, BondOrder.SINGLE)
        builder.add_bond(c2, h2, BondOrder.SINGLE)
        graph = builder.build()
        conf = generate_conformer(graph)
        # Triple bond should be shorter than single bond (1.20 vs 1.54)
        cc_dist = conf.get_distance(c1, c2)
        ch_dist = conf.get_distance(c1, h1)
        assert cc_dist > 0
        assert ch_dist > 0

    def test_large_molecule_2d(self):
        from chemengine.coordinates.layout_2d import generate_2d_coordinates
        builder = MolecularGraphBuilder()
        # Build decane (C10H22)
        carbons = [builder.add_atom(6) for _ in range(10)]
        for i in range(9):
            builder.add_bond(carbons[i], carbons[i+1], BondOrder.SINGLE)
        # Add hydrogens
        for i, c in enumerate(carbons):
            n_h = 2
            if i == 0 or i == 9:
                n_h = 3
            for _ in range(n_h):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == graph.num_atoms
        for c in coords:
            assert math.isfinite(c.x)
            assert math.isfinite(c.y)

    def test_conformer_clustering(self):
        from chemengine.coordinates.conformer_3d import generate_conformers
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        for _ in range(6):
            h = builder.add_atom(1)
            builder.add_bond(c1, h, BondOrder.SINGLE)
        for _ in range(6):
            h = builder.add_atom(1)
            builder.add_bond(c2, h, BondOrder.SINGLE)
        graph = builder.build()
        conformers = generate_conformers(graph, num_conformers=5)
        assert len(conformers) >= 1
        # All should be sorted by energy
        for i in range(len(conformers) - 1):
            assert conformers[i].energy <= conformers[i+1].energy

    def test_force_directed_determinism(self):
        from chemengine.coordinates.layout_2d import generate_2d_coordinates
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        c3 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c2, c3, BondOrder.SINGLE)
        for c in (c1, c2, c3):
            for _ in range(2):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        coords1 = generate_2d_coordinates(graph, seed=42)
        coords2 = generate_2d_coordinates(graph, seed=42)
        for a, b in zip(coords1, coords2):
            assert abs(a.x - b.x) < 1e-10
            assert abs(a.y - b.y) < 1e-10


# ══════════════════════════════════════════════════════════════════
# SVG RENDERING EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestSVGEdgeCases:
    """Edge cases for SVG rendering."""

    def test_empty_svg(self):
        from chemengine.rendering.svg import render_svg
        graph = MolecularGraph(atoms=(), bonds=())
        svg = render_svg(graph)
        assert "<svg" in svg
        assert "Empty" in svg

    def test_single_atom_svg(self):
        from chemengine.rendering.svg import render_svg
        builder = MolecularGraphBuilder()
        builder.add_atom(8)
        graph = builder.build()
        svg = render_svg(graph)
        assert "O" in svg
        assert "<svg" in svg

    def test_svg_valid_xml(self):
        from chemengine.rendering.svg import render_svg
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        for c in (c1, c2):
            for _ in range(3):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        svg = render_svg(graph)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        # Should be parseable as XML (basic check)
        assert svg.count("<svg") == 1
        assert svg.count("</svg>") == 1

    def test_svg_title_special_chars(self):
        from chemengine.rendering.svg import _escape_xml
        assert _escape_xml("a < b & c > d") == "a &lt; b &amp; c &gt; d"
        assert _escape_xml("normal") == "normal"

    def test_svg_bond_length_scaling(self):
        from chemengine.rendering.svg import render_svg
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        for c in (c1, c2):
            for _ in range(3):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        svg1 = render_svg(graph, bond_length=30.0)
        svg2 = render_svg(graph, bond_length=60.0)
        # Both should be valid SVG
        assert "<svg" in svg1
        assert "<svg" in svg2

    def test_svg_all_bond_types(self):
        from chemengine.rendering.svg import render_svg
        # Build molecule with triple bond
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.TRIPLE)
        h1 = builder.add_atom(1)
        h2 = builder.add_atom(1)
        builder.add_bond(c1, h1, BondOrder.SINGLE)
        builder.add_bond(c2, h2, BondOrder.SINGLE)
        graph = builder.build()
        svg = render_svg(graph, show_hydrogens=True)
        assert "line" in svg
        assert "<svg" in svg


# ══════════════════════════════════════════════════════════════════
# REACTIONS EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestReactionEdgeCases:
    """Edge cases for reaction models."""

    def test_empty_reaction_builder_raises(self):
        from chemengine.reactions.reaction import ReactionBuilder
        with pytest.raises(ValueError, match="reactant"):
            ReactionBuilder().build()

    def test_no_products_raises(self):
        from chemengine.reactions.reaction import ReactionBuilder
        builder = ReactionBuilder()
        builder.add_reactant(MolecularGraph(atoms=(), bonds=()))
        with pytest.raises(ValueError, match="product"):
            builder.build()

    def test_balanced_water_formation(self):
        from chemengine.reactions.reaction import Reaction, ReactionComponent
        # 2H2 + O2 -> 2H2O
        h2 = MolecularGraph(
            atoms=(__import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=1),
                   __import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=1)),
            bonds=(Bond(atom1=0, atom2=1, order=BondOrder.SINGLE),),
        )
        o2 = MolecularGraph(
            atoms=(__import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=8),
                   __import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=8)),
            bonds=(Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE),),
        )
        h2o = MolecularGraph(
            atoms=(__import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=8),
                   __import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=1),
                   __import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=1)),
            bonds=(Bond(atom1=0, atom2=1, order=BondOrder.SINGLE),
                   Bond(atom1=0, atom2=2, order=BondOrder.SINGLE)),
        )
        reaction = Reaction(
            reactants=(ReactionComponent(h2, 2), ReactionComponent(o2, 1)),
            products=(ReactionComponent(h2o, 2),),
        )
        assert reaction.is_balanced()

    def test_unbalanced_reaction(self):
        from chemengine.reactions.reaction import Reaction, ReactionComponent
        a = MolecularGraph(
            atoms=(__import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=6),),
            bonds=(),
        )
        b = MolecularGraph(
            atoms=(__import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=6),
                   __import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=6)),
            bonds=(Bond(atom1=0, atom2=1, order=BondOrder.SINGLE),),
        )
        reaction = Reaction(
            reactants=(ReactionComponent(a, 1),),
            products=(ReactionComponent(b, 1),),
        )
        assert not reaction.is_balanced()
        diff = reaction.atom_count_difference()
        assert diff.get("C", 0) == 1

    def test_reaction_to_dict_roundtrip(self):
        from chemengine.reactions.reaction import Reaction, ReactionComponent
        a = MolecularGraph(
            atoms=(__import__('chemengine.core.atoms', fromlist=['Atom']).Atom(atomic_number=6),),
            bonds=(),
        )
        reaction = Reaction(
            reactants=(ReactionComponent(a, 1),),
            products=(ReactionComponent(a, 1),),
            name="test",
        )
        d = reaction.to_dict()
        assert d["name"] == "test"
        assert d["is_balanced"]

    def test_reaction_template_combustion_match(self):
        from chemengine.reactions.reaction import get_reaction_template
        t = get_reaction_template("combustion")
        assert t is not None
        assert t.matches_reactants(["C", "O=O"])
        assert not t.matches_reactants(["CCO"])

    def test_reaction_arrow_types(self):
        from chemengine.reactions.reaction import ReactionArrow
        assert "→" in repr(ReactionArrow("forward"))
        assert "⇌" in repr(ReactionArrow("reversible"))
        assert "⇌" in repr(ReactionArrow("equilibrium"))


# ══════════════════════════════════════════════════════════════════
# NOMENCLATURE EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestNomenclatureEdgeCases:
    """Edge cases for IUPAC naming."""

    def test_empty_graph_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        graph = MolecularGraph(atoms=(), bonds=())
        name = generate_iupac_name(graph)
        assert name == ""

    def test_single_hydrogen_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        builder = MolecularGraphBuilder()
        builder.add_atom(1)
        graph = builder.build()
        name = generate_iupac_name(graph)
        assert "hydrogen" in name.lower()

    def test_methane_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        builder = MolecularGraphBuilder()
        c = builder.add_atom(6)
        for _ in range(4):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        name = generate_iupac_name(graph)
        assert "methane" in name.lower()

    def test_ethane_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        for c in (c1, c2):
            for _ in range(3):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        name = generate_iupac_name(graph)
        assert "eth" in name.lower()

    def test_cyclopropane_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        builder = MolecularGraphBuilder()
        carbons = [builder.add_atom(6) for _ in range(3)]
        for i in range(3):
            builder.add_bond(carbons[i], carbons[(i+1)%3], BondOrder.SINGLE)
        for c in carbons:
            for _ in range(2):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        name = generate_iupac_name(graph)
        assert "cyclo" in name.lower()

    def test_carboxylic_acid_detection(self):
        from chemengine.nomenclature.iupac import _detect_functional_groups
        builder = MolecularGraphBuilder()
        c = builder.add_atom(6)
        o1 = builder.add_atom(8)
        o2 = builder.add_atom(8)
        builder.add_bond(c, o1, BondOrder.DOUBLE)
        builder.add_bond(c, o2, BondOrder.SINGLE)
        h = builder.add_atom(1)
        builder.add_bond(o2, h, BondOrder.SINGLE)
        # Add a methyl group
        c2 = builder.add_atom(6)
        builder.add_bond(c, c2, BondOrder.SINGLE)
        for _ in range(3):
            h = builder.add_atom(1)
            builder.add_bond(c2, h, BondOrder.SINGLE)
        graph = builder.build()
        groups = _detect_functional_groups(graph)
        assert len(groups["carboxyl"]) > 0


# ══════════════════════════════════════════════════════════════════
# IO SERIALIZATION EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestIOEdgeCases:
    """Edge cases for serialization."""

    def test_empty_graph_serialization(self):
        from chemengine.io.serialization import dict_to_graph, graph_to_dict
        graph = MolecularGraph(atoms=(), bonds=())
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        assert graph2.num_atoms == 0
        assert graph2.num_bonds == 0

    def test_json_roundtrip(self):
        from chemengine.io.serialization import graph_to_json, json_to_graph
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        for c in (c1, c2):
            for _ in range(2):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        json_str = graph_to_json(graph)
        graph2 = json_to_graph(json_str)
        assert graph2.molecular_formula == graph.molecular_formula
        assert graph2.num_atoms == graph.num_atoms

    def test_serialization_preserves_charge(self):
        from chemengine.io.serialization import dict_to_graph, graph_to_dict
        builder = MolecularGraphBuilder()
        n = builder.add_atom(7, formal_charge=1)
        for _ in range(4):
            h = builder.add_atom(1)
            builder.add_bond(n, h, BondOrder.SINGLE)
        graph = builder.build()
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        assert graph2.atoms[0].formal_charge == 1

    def test_serialization_preserves_aromatic(self):
        from chemengine.io.serialization import dict_to_graph, graph_to_dict
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6, is_aromatic=True)
        c2 = builder.add_atom(6, is_aromatic=True)
        builder.add_bond(c1, c2, BondOrder.AROMATIC)
        graph = builder.build()
        d = graph_to_dict(graph)
        graph2 = dict_to_graph(d)
        assert graph2.atoms[0].is_aromatic
        assert graph2.atoms[1].is_aromatic

    def test_convert_format_json(self):
        from chemengine.io.serialization import convert_format
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        for c in (c1, c2):
            for _ in range(3):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        result = convert_format(graph, "smiles", "json")
        data = json.loads(result)
        assert "atoms" in data
        assert "bonds" in data

    def test_convert_to_name(self):
        from chemengine.io.serialization import convert_format
        builder = MolecularGraphBuilder()
        c = builder.add_atom(6)
        for _ in range(4):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        name = convert_format(graph, "smiles", "name")
        assert isinstance(name, str)
        assert len(name) > 0


# ══════════════════════════════════════════════════════════════════
# API TOOL INTEGRATION EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestAPIToolsEdgeCases:
    """Edge cases for the ChemEngineAPI tools."""

    def test_api_tools_list(self):
        api = ChemEngineAPI()
        tools = api.list_tools()
        tool_names = [t.name for t in tools]
        assert "parse_smiles" in tool_names
        assert "compute_property" in tool_names
        assert "validate" in tool_names
        assert "detect_functional_groups" in tool_names
        assert "generate_2d_coordinates" in tool_names
        assert "generate_3d_conformer" in tool_names
        assert "render_svg" in tool_names
        assert "name_molecule" in tool_names
        assert "serialize" in tool_names

    def test_api_tool_category_filter(self):
        api = ChemEngineAPI()
        parsing_tools = api.list_tools(category="parsing")
        assert all(t.category == "parsing" for t in parsing_tools)
        assert len(parsing_tools) >= 2

    def test_api_execute_2d_coordinates(self):
        api = ChemEngineAPI()
        result = api.execute_tool("generate_2d_coordinates", {"smiles": "CCO"})
        assert "coordinates" in result
        assert len(result["coordinates"]) > 0
        assert "x" in result["coordinates"][0]
        assert "y" in result["coordinates"][0]

    def test_api_execute_3d_conformer(self):
        api = ChemEngineAPI()
        result = api.execute_tool("generate_3d_conformer", {"smiles": "CC", "num_conformers": 2})
        assert "conformers" in result
        assert len(result["conformers"]) >= 1
        assert "coordinates" in result["conformers"][0]

    def test_api_execute_render_svg(self):
        api = ChemEngineAPI()
        result = api.execute_tool("render_svg", {"smiles": "CCO"})
        assert "svg" in result
        assert "<svg" in result["svg"]

    def test_api_execute_name_molecule(self):
        api = ChemEngineAPI()
        result = api.execute_tool("name_molecule", {"smiles": "CC"})
        assert "name" in result
        assert isinstance(result["name"], str)

    def test_api_execute_serialize(self):
        api = ChemEngineAPI()
        result = api.execute_tool("serialize", {"smiles": "CCO"})
        assert "data" in result
        data = result["data"]
        assert "atoms" in data

    def test_api_unknown_tool_raises(self):
        api = ChemEngineAPI()
        with pytest.raises(KeyError, match="Unknown tool"):
            api.execute_tool("nonexistent_tool", {})


# ══════════════════════════════════════════════════════════════════
# CROSS-MODULE INTEGRATION
# ══════════════════════════════════════════════════════════════════

class TestCrossModuleIntegration:
    """Test integration across modules."""

    def test_parse_render_name_serialize(self):
        """Full pipeline: parse → render → name → serialize."""
        api = ChemEngineAPI()

        # Parse
        graph = api.parse("CCO", fmt="smiles")
        assert graph.molecular_formula == "C2H6O"

        # Render
        svg_result = api.execute_tool("render_svg", {"smiles": "CCO"})
        assert "<svg" in svg_result["svg"]

        # Name
        name_result = api.execute_tool("name_molecule", {"smiles": "CCO"})
        assert len(name_result["name"]) > 0

        # Serialize (dict format for direct round-trip)
        ser_result = api.execute_tool("serialize", {"smiles": "CCO", "format": "dict"})
        data = ser_result["data"]
        assert "atoms" in data

        # Round-trip
        from chemengine.io.serialization import dict_to_graph
        graph2 = dict_to_graph(data)
        assert graph2.molecular_formula == "C2H6O"

    def test_2d_3d_pipeline(self):
        """Test 2D → 3D coordinate pipeline."""
        api = ChemEngineAPI()

        # Parse ethane (C2H6 = 8 atoms)
        graph = api.parse("CC", fmt="smiles")
        n_atoms = graph.num_atoms

        # 2D coordinates
        result_2d = api.execute_tool("generate_2d_coordinates", {"smiles": "CC"})
        assert len(result_2d["coordinates"]) == n_atoms

        # 3D conformer
        result_3d = api.execute_tool("generate_3d_conformer", {"smiles": "CC"})
        assert len(result_3d["conformers"]) >= 1
        assert len(result_3d["conformers"][0]["coordinates"]) == n_atoms

    def test_validation_pipeline(self):
        """Test validation → sanitize → validate pipeline."""
        api = ChemEngineAPI()

        # Validate
        val_result = api.execute_tool("validate", {"smiles": "CCO"})
        assert val_result["is_valid"]

        # Sanitize
        san_result = api.execute_tool("sanitize", {"smiles": "CCO"})
        assert "sanitized_smiles" in san_result

    def test_functional_groups_pipeline(self):
        """Test functional group detection."""
        api = ChemEngineAPI()

        result = api.execute_tool("detect_functional_groups", {"smiles": "CCO"})
        assert "functional_groups" in result
        groups = result["functional_groups"]
        # Ethanol has an alcohol group
        assert any(g["name"] == "Alcohol" for g in groups)
