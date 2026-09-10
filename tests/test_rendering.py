"""Tests for Phase 10: SVG Rendering
- SVG generation for various molecules
- Bond rendering (single, double, triple, aromatic)
- Atom labels
- Empty graph handling
"""

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.geometry import Coordinate2D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.rendering.svg import (
    _escape_xml,
    _get_color,
    _render_aromatic_bond,
    _render_atom_label,
    _render_dashed_bond,
    _render_double_bond,
    _render_single_bond,
    _render_triple_bond,
    _render_wedge_bond,
    _should_show_label,
    render_svg,
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


def _make_ethene():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.DOUBLE)
    for c in (c1, c2):
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_ethyne():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.TRIPLE)
    for c in (c1, c2):
        h = builder.add_atom(1)
        builder.add_bond(c, h, BondOrder.SINGLE)
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


def _make_ethanol():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    o = builder.add_atom(8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o, BondOrder.SINGLE)
    for c in (c1, c2):
        for _ in range(3 if c == c1 else 2):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    h = builder.add_atom(1)
    builder.add_bond(o, h, BondOrder.SINGLE)
    return builder.build()


# ── SVG Rendering Tests ──

class TestSVGRendering:
    def test_empty_graph(self):
        graph = MolecularGraph(atoms=(), bonds=())
        svg = render_svg(graph)
        assert "<svg" in svg
        assert "Empty" in svg

    def test_single_atom(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(6)
        graph = builder.build()
        svg = render_svg(graph)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_methane_svg(self):
        graph = _make_methane()
        svg = render_svg(graph)
        assert "<svg" in svg
        assert "</svg>" in svg
        assert "C" in svg or "circle" in svg  # Carbon should appear

    def test_ethane_svg(self):
        graph = _make_ethane()
        svg = render_svg(graph)
        assert "<svg" in svg
        assert "line" in svg  # Should have bond lines

    def test_ethene_svg(self):
        graph = _make_ethene()
        svg = render_svg(graph)
        assert "<svg" in svg
        # Double bond should render
        assert "line" in svg

    def test_ethyne_svg(self):
        graph = _make_ethyne()
        svg = render_svg(graph)
        assert "<svg" in svg

    def test_benzene_svg(self):
        graph = _make_benzene()
        svg = render_svg(graph)
        assert "<svg" in svg
        assert "line" in svg

    def test_ethanol_svg_with_heteroatom(self):
        graph = _make_ethanol()
        svg = render_svg(graph)
        assert "<svg" in svg
        assert "O" in svg  # Oxygen should appear as label

    def test_custom_bond_length(self):
        graph = _make_ethane()
        svg = render_svg(graph, bond_length=60.0)
        assert "<svg" in svg

    def test_show_hydrogens(self):
        graph = _make_ethane()
        svg = render_svg(graph, show_hydrogens=True)
        assert "<svg" in svg

    def test_svg_with_title(self):
        graph = _make_ethane()
        svg = render_svg(graph, title="Ethane")
        assert "Ethane" in svg

    def test_svg_with_coordinates(self):
        graph = _make_ethane()
        # Ethane has 8 atoms (2C + 6H)
        coords = tuple(Coordinate2D(i * 0.5, 0.0) for i in range(graph.num_atoms))
        svg = render_svg(graph, coordinates=coords)
        assert "<svg" in svg

    def test_coordinate_count_mismatch_raises(self):
        graph = _make_ethane()
        coords = (Coordinate2D(0.0, 0.0), Coordinate2D(1.0, 0.0))
        with pytest.raises(ValueError, match="Coordinate count"):
            render_svg(graph, coordinates=coords)


# ── Bond Rendering Tests ──

class TestBondRendering:
    def test_single_bond(self):
        svg = _render_single_bond(0, 0, 10, 10)
        assert "<line" in svg
        assert 'x1="0.00"' in svg

    def test_double_bond(self):
        svg = _render_double_bond(0, 0, 10, 0)
        assert "<line" in svg
        # Should produce two lines
        assert svg.count("<line") == 2

    def test_triple_bond(self):
        svg = _render_triple_bond(0, 0, 10, 0)
        assert "<line" in svg
        assert svg.count("<line") == 3

    def test_wedge_bond(self):
        svg = _render_wedge_bond(0, 0, 10, 0)
        assert "<polygon" in svg

    def test_dashed_bond(self):
        svg = _render_dashed_bond(0, 0, 10, 0)
        assert "<line" in svg
        assert svg.count("<line") >= 3  # Multiple dash segments

    def test_aromatic_bond(self):
        svg = _render_aromatic_bond(0, 0, 10, 0)
        assert "<line" in svg
        assert "stroke-dasharray" in svg


# ── Atom Label Tests ──

class TestAtomLabel:
    def test_atom_label_without_charge(self):
        svg = _render_atom_label(50, 50, "C", "#333333")
        assert "<text" in svg
        assert "C" in svg
        assert "<circle" in svg  # Background circle

    def test_atom_label_with_positive_charge(self):
        svg = _render_atom_label(50, 50, "N", "#3050F8", charge=1)
        assert "+1" in svg

    def test_atom_label_with_negative_charge(self):
        svg = _render_atom_label(50, 50, "O", "#FF0D0D", charge=-1)
        assert "-1" in svg


# ── Helper Tests ──

class TestHelpers:
    def test_should_show_label_carbon_terminal(self):
        graph = _make_ethane()
        # Carbon bonded to 3 H + 1 C = degree 4, should show
        assert _should_show_label(0, graph)

    def test_should_show_label_heteroatom(self):
        graph = _make_ethanol()
        # Find oxygen
        for i, atom in enumerate(graph.atoms):
            if atom.atomic_number == 8:
                assert _should_show_label(i, graph)
                break

    def test_get_color_carbon(self):
        assert _get_color(6) == "#333333"

    def test_get_color_oxygen(self):
        assert _get_color(8) == "#FF0D0D"

    def test_get_color_nitrogen(self):
        assert _get_color(7) == "#3050F8"

    def test_get_color_unknown(self):
        # Unknown element gets default color
        color = _get_color(999)
        assert color == "#333333"

    def test_escape_xml(self):
        assert _escape_xml("<tag>") == "&lt;tag&gt;"
        assert _escape_xml("a & b") == "a &amp; b"
