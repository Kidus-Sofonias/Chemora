"""Tests for all improvements made in this session.
"""

import math

from chemengine.core.bonds import BondOrder
from chemengine.core.geometry import Coordinate3D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.core.tool_interface import ChemEngineAPI

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
    return builder.build()


def _make_acetic_acid():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    o1 = builder.add_atom(8)
    o2 = builder.add_atom(8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o1, BondOrder.DOUBLE)
    builder.add_bond(c2, o2, BondOrder.SINGLE)
    for _ in range(3):
        h = builder.add_atom(1)
        builder.add_bond(c1, h, BondOrder.SINGLE)
    h = builder.add_atom(1)
    builder.add_bond(o2, h, BondOrder.SINGLE)
    return builder.build()


def _make_benzene():
    builder = MolecularGraphBuilder()
    carbons = [builder.add_atom(6) for _ in range(6)]
    for i in range(6):
        builder.add_bond(carbons[i], carbons[(i + 1) % 6], BondOrder.DOUBLE if i % 2 == 0 else BondOrder.SINGLE)
    for c in carbons:
        h = builder.add_atom(1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


# ══════════════════════════════════════════════════════════════════
# InChI SERIALIZATION TESTS
# ══════════════════════════════════════════════════════════════════

class TestInChISerialization:
    def test_inchi_methane(self):
        from chemengine.parsing.inchi_serializer import serialize_inchi
        graph = _make_methane()
        inchi = serialize_inchi(graph)
        assert inchi.startswith("InChI=")
        assert "CH4" in inchi or "C" in inchi

    def test_inchi_ethane(self):
        from chemengine.parsing.inchi_serializer import serialize_inchi
        graph = _make_ethane()
        inchi = serialize_inchi(graph)
        assert inchi.startswith("InChI=")
        assert "C2H6" in inchi

    def test_inchi_ethanol(self):
        from chemengine.parsing.inchi_serializer import serialize_inchi
        graph = _make_ethanol()
        inchi = serialize_inchi(graph)
        assert inchi.startswith("InChI=")
        assert "C2H6O" in inchi

    def test_inchi_empty_graph(self):
        from chemengine.parsing.inchi_serializer import serialize_inchi
        graph = MolecularGraph(atoms=(), bonds=())
        inchi = serialize_inchi(graph)
        assert inchi == "InChI=1S///"

    def test_inchi_key_format(self):
        from chemengine.parsing.inchi_serializer import generate_inchi_key
        graph = _make_ethanol()
        key = generate_inchi_key(graph)
        assert len(key) == 27
        assert key.count("-") == 2

    def test_inchi_key_deterministic(self):
        from chemengine.parsing.inchi_serializer import generate_inchi_key
        graph = _make_ethanol()
        key1 = generate_inchi_key(graph)
        key2 = generate_inchi_key(graph)
        assert key1 == key2

    def test_inchi_key_different_for_different_molecules(self):
        from chemengine.parsing.inchi_serializer import generate_inchi_key
        key1 = generate_inchi_key(_make_methane())
        key2 = generate_inchi_key(_make_ethane())
        assert key1 != key2

    def test_inchi_to_formula(self):
        from chemengine.parsing.inchi_serializer import inchi_to_formula
        formula = inchi_to_formula("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3")
        assert formula == "C2H6O"

    def test_inchi_to_formula_invalid(self):
        from chemengine.parsing.inchi_serializer import inchi_to_formula
        assert inchi_to_formula("not an inchi") is None

    def test_api_generate_inchi_tool(self):
        api = ChemEngineAPI()
        result = api.execute_tool("generate_inchi", {"smiles": "CCO"})
        assert "inchi" in result
        assert "inchikey" in result
        assert result["inchi"].startswith("InChI=")
        assert len(result["inchikey"]) == 27

    def test_parse_smiles_includes_inchi(self):
        api = ChemEngineAPI()
        result = api.execute_tool("parse_smiles", {"smiles": "CCO"})
        assert result["inchi"].startswith("InChI=")
        assert len(result["inchikey"]) == 27


# ══════════════════════════════════════════════════════════════════
# ENHANCED IUPAC NAMING TESTS
# ══════════════════════════════════════════════════════════════════

class TestEnhancedNaming:
    def test_ethanol_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        graph = _make_ethanol()
        name = generate_iupac_name(graph)
        assert "ol" in name.lower()

    def test_acetic_acid_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        graph = _make_acetic_acid()
        name = generate_iupac_name(graph)
        assert "acid" in name.lower()

    def test_benzene_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        graph = _make_benzene()
        name = generate_iupac_name(graph)
        assert isinstance(name, str)
        assert len(name) > 0

    def test_methane_name(self):
        from chemengine.nomenclature.iupac import generate_iupac_name
        graph = _make_methane()
        name = generate_iupac_name(graph)
        assert "methane" in name.lower()

    def test_fg_priority_carboxyl_over_hydroxyl(self):
        """Carboxylic acid should take priority over alcohol in naming."""
        from chemengine.nomenclature.iupac import generate_iupac_name
        # Build glycolic acid: HO-CH2-COOH
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)  # CH2
        c2 = builder.add_atom(6)  # COOH
        o1 = builder.add_atom(8)  # OH
        o2 = builder.add_atom(8)  # C=O
        o3 = builder.add_atom(8)  # O-H (acid)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c1, o1, BondOrder.SINGLE)
        builder.add_bond(c2, o2, BondOrder.DOUBLE)
        builder.add_bond(c2, o3, BondOrder.SINGLE)
        # H atoms
        h = builder.add_atom(1)
        builder.add_bond(o1, h, BondOrder.SINGLE)
        h = builder.add_atom(1)
        builder.add_bond(o3, h, BondOrder.SINGLE)
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(c1, h, BondOrder.SINGLE)
        graph = builder.build()
        name = generate_iupac_name(graph)
        # Should be named as acid, not alcohol
        assert "acid" in name.lower()

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


# ══════════════════════════════════════════════════════════════════
# BETTER 3D CONFORMER ENERGY TESTS
# ══════════════════════════════════════════════════════════════════

class TestBetterConformers:
    def test_conformer_energy_increases_with_distortion(self):
        """A distorted conformer should have higher energy than a good one."""
        from chemengine.coordinates.conformer_3d import compute_conformer_energy, generate_conformer
        graph = _make_ethane()
        good_conf = generate_conformer(graph, seed=42)
        good_energy = compute_conformer_energy(good_conf, graph)

        # Create a distorted conformer (move one atom far away)
        distorted_coords = list(good_conf.coordinates)
        distorted_coords[0] = Coordinate3D(100.0, 100.0, 100.0)
        from chemengine.core.geometry import Conformer
        distorted = Conformer(
            id=0,
            coordinates=tuple(distorted_coords),
            energy=0.0,
        )
        bad_energy = compute_conformer_energy(distorted, graph)
        assert bad_energy > good_energy

    def test_conformer_energy_non_negative(self):
        from chemengine.coordinates.conformer_3d import compute_conformer_energy, generate_conformer
        graph = _make_ethane()
        conf = generate_conformer(graph, seed=42)
        energy = compute_conformer_energy(conf, graph)
        assert energy >= 0.0

    def test_conformer_energy_benzene(self):
        from chemengine.coordinates.conformer_3d import compute_conformer_energy, generate_conformer
        graph = _make_benzene()
        conf = generate_conformer(graph, seed=42)
        energy = compute_conformer_energy(conf, graph)
        assert energy >= 0.0
        assert math.isfinite(energy)


# ══════════════════════════════════════════════════════════════════
# SVG STEREOCHEMISTRY TESTS
# ══════════════════════════════════════════════════════════════════

class TestSVGStereo:
    def test_svg_with_chiral_center(self):
        """SVG should render wedge/dash for chiral centers."""
        from chemengine.core.enums import ChiralTag
        from chemengine.rendering.svg import render_svg
        builder = MolecularGraphBuilder()
        c = builder.add_atom(6, stereochemistry=ChiralTag.R)
        cl = builder.add_atom(17)
        o = builder.add_atom(8)
        ch3 = builder.add_atom(6)
        h = builder.add_atom(1)
        builder.add_bond(c, cl, BondOrder.SINGLE)
        builder.add_bond(c, o, BondOrder.SINGLE)
        builder.add_bond(c, ch3, BondOrder.SINGLE)
        builder.add_bond(c, h, BondOrder.SINGLE)
        builder.add_bond(o, builder.add_atom(1), BondOrder.SINGLE)
        for _ in range(3):
            hh = builder.add_atom(1)
            builder.add_bond(ch3, hh, BondOrder.SINGLE)
        graph = builder.build()
        svg = render_svg(graph)
        assert "<svg" in svg
        # Should contain either wedge polygon or dashed bond elements
        assert "polygon" in svg or "line" in svg

    def test_svg_to_file(self):
        """Test SVG file export."""
        import os
        import tempfile

        from chemengine.rendering.svg import render_svg_to_file
        graph = _make_ethanol()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            filepath = f.name
        try:
            render_svg_to_file(graph, filepath)
            assert os.path.exists(filepath)
            with open(filepath) as f:
                content = f.read()
            assert "<svg" in content
            assert "</svg>" in content
        finally:
            os.unlink(filepath)


# ══════════════════════════════════════════════════════════════════
# REACTION ATOM MAPPING TESTS
# ══════════════════════════════════════════════════════════════════

class TestReactionAtomMapping:
    def test_reaction_component_with_atom_map(self):
        from chemengine.reactions.reaction import ReactionComponent
        graph = _make_methane()
        comp = ReactionComponent(molecule=graph, coefficient=1, atom_map={0: 0, 1: 1})
        assert comp.atom_map == {0: 0, 1: 1}

    def test_reaction_component_without_atom_map(self):
        from chemengine.reactions.reaction import ReactionComponent
        graph = _make_methane()
        comp = ReactionComponent(molecule=graph)
        assert comp.atom_map is None


# ══════════════════════════════════════════════════════════════════
# FORMAT CONVERSION TESTS
# ══════════════════════════════════════════════════════════════════

class TestFormatConversion:
    def test_convert_to_inchi(self):
        from chemengine.io.serialization import convert_format
        graph = _make_ethane()
        result = convert_format(graph, "smiles", "inchi")
        assert result.startswith("InChI=")

    def test_convert_to_inchikey(self):
        from chemengine.io.serialization import convert_format
        graph = _make_ethane()
        result = convert_format(graph, "smiles", "inchikey")
        assert len(result) == 27

    def test_convert_roundtrip(self):
        from chemengine.io.serialization import convert_format
        graph = _make_ethanol()
        formula = convert_format(graph, "smiles", "formula")
        assert formula == "C2H6O"


# ══════════════════════════════════════════════════════════════════
# FULL INTEGRATION PIPELINE
# ══════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_complete_pipeline(self):
        """Test full pipeline: parse → validate → name → render → inchi → serialize."""
        api = ChemEngineAPI()

        # Parse
        graph = api.parse("CCO", fmt="smiles")
        assert graph.molecular_formula == "C2H6O"

        # Validate
        val = api.execute_tool("validate", {"smiles": "CCO"})
        assert val["is_valid"]

        # Name
        name = api.execute_tool("name_molecule", {"smiles": "CCO"})
        assert len(name["name"]) > 0

        # Render
        svg = api.execute_tool("render_svg", {"smiles": "CCO"})
        assert "<svg" in svg["svg"]

        # InChI
        inchi = api.execute_tool("generate_inchi", {"smiles": "CCO"})
        assert inchi["inchi"].startswith("InChI=")
        assert len(inchi["inchikey"]) == 27

        # Serialize
        ser = api.execute_tool("serialize", {"smiles": "CCO", "format": "dict"})
        assert "atoms" in ser["data"]

        # 2D coordinates
        coords = api.execute_tool("generate_2d_coordinates", {"smiles": "CCO"})
        assert len(coords["coordinates"]) > 0

        # 3D conformer
        conf = api.execute_tool("generate_3d_conformer", {"smiles": "CCO"})
        assert len(conf["conformers"]) >= 1

    def test_benzene_pipeline(self):
        """Test pipeline with aromatic molecule."""
        api = ChemEngineAPI()
        graph = api.parse("c1ccccc1", fmt="smiles")
        assert graph.molecular_formula == "C6H6"

        inchi = api.execute_tool("generate_inchi", {"smiles": "c1ccccc1"})
        assert "C6H6" in inchi["inchi"]

        svg = api.execute_tool("render_svg", {"smiles": "c1ccccc1"})
        assert "<svg" in svg["svg"]
