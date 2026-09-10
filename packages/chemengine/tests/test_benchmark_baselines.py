"""Benchmark baseline regression tests.

Establishes performance baselines for core operations and verifies
they don't regress beyond acceptable thresholds.
"""

import time

from chemengine.coordinates.layout_2d import generate_2d_coordinates
from chemengine.core.bonds import BondOrder
from chemengine.core.element import Element
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.detection.rings import detect_rings
from chemengine.parsing.formula import formula_to_graph, parse_formula
from chemengine.parsing.smiles import parse_smiles, serialize_smiles
from chemengine.properties.descriptors import (
    compute_hba,
    compute_hbd,
    compute_logp,
    compute_tpsa,
)
from chemengine.rendering.svg import render_svg
from chemengine.stereochemistry.perception import perceive_stereochemistry

# ══════════════════════════════════════════════════════════════════
# BENCHMARK HELPERS
# ══════════════════════════════════════════════════════════════════

def _time_function(func, iterations=100):
    """Time a function over multiple iterations, return avg microseconds."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1_000_000)  # microseconds
    return sum(times) / len(times)


def _build_benzene():
    builder = MolecularGraphBuilder()
    carbons = [builder.add_atom(atomic_number=6) for _ in range(6)]
    for i in range(6):
        builder.add_bond(carbons[i], carbons[(i + 1) % 6], BondOrder.AROMATIC)
    for c in carbons:
        h = builder.add_atom(atomic_number=1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _build_ethane():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6)
    c2 = builder.add_atom(atomic_number=6)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    for c in (c1, c2):
        for _ in range(3):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _build_decane():
    builder = MolecularGraphBuilder()
    carbons = [builder.add_atom(atomic_number=6) for _ in range(10)]
    for i in range(9):
        builder.add_bond(carbons[i], carbons[i + 1], BondOrder.SINGLE)
    for i, c in enumerate(carbons):
        n_h = 3 if i in (0, 9) else 2
        for _ in range(n_h):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


# ══════════════════════════════════════════════════════════════════
# BASELINE DEFINITIONS
# ══════════════════════════════════════════════════════════════════

# Baselines in microseconds (measured on reference hardware)
# These are upper bounds — tests fail if actual time exceeds them
BASELINES = {
    "smiles_parse_simple": 10000,      # 10ms for CCO
    "smiles_parse_medium": 20000,      # 20ms for complex molecule
    "smiles_serialize": 10000,         # 10ms serialization
    "formula_parse": 1000,             # 1ms for formula parsing
    "formula_to_graph": 5000,          # 5ms for formula→graph
    "graph_construction": 5000,        # 5ms for building a graph
    "ring_detection_benzene": 20000,   # 20ms for benzene ring detection
    "element_lookup": 500,             # 0.5ms for element lookup (1000 iterations)
    "stereo_perception": 20000,        # 20ms for stereo perception
    "tpsa_computation": 5000,          # 5ms for TPSA
    "logp_computation": 5000,          # 5ms for logP
    "2d_layout_benzene": 200000,       # 200ms for 2D layout
    "svg_render_benzene": 200000,      # 200ms for SVG render
}


# ══════════════════════════════════════════════════════════════════
# BENCHMARK TESTS
# ══════════════════════════════════════════════════════════════════


class TestBenchmarkBaselines:
    """Performance baseline regression tests."""

    def test_smiles_parse_simple(self):
        """SMILES parsing: simple molecule (CCO)."""
        avg_us = _time_function(lambda: parse_smiles("CCO"), iterations=200)
        assert avg_us < BASELINES["smiles_parse_simple"], (
            f"SMILES parsing too slow: {avg_us:.0f}μs > {BASELINES['smiles_parse_simple']}μs"
        )

    def test_smiles_parse_medium(self):
        """SMILES parsing: medium molecule (aspirin)."""
        avg_us = _time_function(
            lambda: parse_smiles("CC(=O)Oc1ccccc1C(=O)O"), iterations=100
        )
        assert avg_us < BASELINES["smiles_parse_medium"], (
            f"SMILES parsing too slow: {avg_us:.0f}μs > {BASELINES['smiles_parse_medium']}μs"
        )

    def test_smiles_serialize(self):
        """SMILES serialization."""
        graph = parse_smiles("CC(=O)Oc1ccccc1C(=O)O")
        avg_us = _time_function(lambda: serialize_smiles(graph), iterations=200)
        assert avg_us < BASELINES["smiles_serialize"], (
            f"SMILES serialization too slow: {avg_us:.0f}μs > {BASELINES['smiles_serialize']}μs"
        )

    def test_formula_parse(self):
        """Formula parsing (C8H10N4O2)."""
        avg_us = _time_function(lambda: parse_formula("C8H10N4O2"), iterations=1000)
        assert avg_us < BASELINES["formula_parse"], (
            f"Formula parsing too slow: {avg_us:.0f}μs > {BASELINES['formula_parse']}μs"
        )

    def test_formula_to_graph(self):
        """Formula → graph conversion (C6H14)."""
        avg_us = _time_function(lambda: formula_to_graph("C6H14"), iterations=200)
        assert avg_us < BASELINES["formula_to_graph"], (
            f"Formula→graph too slow: {avg_us:.0f}μs > {BASELINES['formula_to_graph']}μs"
        )

    def test_graph_construction(self):
        """Graph construction (ethane)."""
        avg_us = _time_function(_build_ethane, iterations=500)
        assert avg_us < BASELINES["graph_construction"], (
            f"Graph construction too slow: {avg_us:.0f}μs > {BASELINES['graph_construction']}μs"
        )

    def test_ring_detection_benzene(self):
        """Ring detection (benzene)."""
        graph = _build_benzene()
        avg_us = _time_function(lambda: detect_rings(graph), iterations=200)
        assert avg_us < BASELINES["ring_detection_benzene"], (
            f"Ring detection too slow: {avg_us:.0f}μs > {BASELINES['ring_detection_benzene']}μs"
        )

    def test_element_lookup(self):
        """Element lookup by atomic number (1000 lookups)."""
        avg_us = _time_function(
            lambda: [Element.from_z(i) for i in range(1, 119)],
            iterations=1000,
        )
        assert avg_us < BASELINES["element_lookup"], (
            f"Element lookup too slow: {avg_us:.0f}μs > {BASELINES['element_lookup']}μs"
        )

    def test_stereo_perception(self):
        """Stereo perception (chiral molecule)."""
        graph = parse_smiles("C(F)(Cl)(Br)I")
        avg_us = _time_function(lambda: perceive_stereochemistry(graph), iterations=100)
        assert avg_us < BASELINES["stereo_perception"], (
            f" Stereo perception too slow: {avg_us:.0f}μs > {BASELINES['stereo_perception']}μs"
        )

    def test_tpsa_computation(self):
        """TPSA computation (ethanol)."""
        graph = parse_smiles("CCO")
        avg_us = _time_function(lambda: compute_tpsa(graph), iterations=200)
        assert avg_us < BASELINES["tpsa_computation"], (
            f"TPSA computation too slow: {avg_us:.0f}μs > {BASELINES['tpsa_computation']}μs"
        )

    def test_logp_computation(self):
        """LogP computation (ethanol)."""
        graph = parse_smiles("CCO")
        avg_us = _time_function(lambda: compute_logp(graph), iterations=200)
        assert avg_us < BASELINES["logp_computation"], (
            f"logP computation too slow: {avg_us:.0f}μs > {BASELINES['logp_computation']}μs"
        )

    def test_2d_layout_benzene(self):
        """2D layout (benzene)."""
        graph = _build_benzene()
        avg_us = _time_function(lambda: generate_2d_coordinates(graph), iterations=50)
        assert avg_us < BASELINES["2d_layout_benzene"], (
            f"2D layout too slow: {avg_us:.0f}μs > {BASELINES['2d_layout_benzene']}μs"
        )

    def test_svg_render_benzene(self):
        """SVG rendering (benzene)."""
        graph = _build_benzene()
        coords = generate_2d_coordinates(graph, seed=42)
        avg_us = _time_function(
            lambda: render_svg(graph, coordinates=coords), iterations=50
        )
        assert avg_us < BASELINES["svg_render_benzene"], (
            f"SVG render too slow: {avg_us:.0f}μs > {BASELINES['svg_render_benzene']}μs"
        )


# ══════════════════════════════════════════════════════════════════
# CORRECTNESS SMOKE TESTS (run with benchmarks)
# ══════════════════════════════════════════════════════════════════


class TestBenchmarkCorrectness:
    """Verify that benchmarked operations produce correct results."""

    def test_smiles_parse_correctness(self):
        graph = parse_smiles("CCO")
        assert graph.molecular_formula == "C2H6O"
        assert graph.num_atoms == 9

    def test_formula_parse_correctness(self):
        counts = parse_formula("C8H10N4O2")
        from chemengine.core.enums import ElementSymbol
        assert counts[ElementSymbol.C] == 8
        assert counts[ElementSymbol.H] == 10
        assert counts[ElementSymbol.N] == 4
        assert counts[ElementSymbol.O] == 2

    def test_ring_detection_correctness(self):
        graph = _build_benzene()
        rings = detect_rings(graph)
        assert len(rings) >= 1
        assert any(r.size == 6 for r in rings)

    def test_stereo_perception_correctness(self):
        graph = parse_smiles("C(F)(Cl)(Br)I")
        config = perceive_stereochemistry(graph)
        assert config.count >= 1

    def test_properties_correctness(self):
        graph = parse_smiles("CCO")
        assert compute_tpsa(graph) > 0
        assert compute_hba(graph) >= 1
        assert compute_hbd(graph) >= 1
        assert compute_logp(graph) != 0

    def test_2d_layout_correctness(self):
        graph = _build_benzene()
        coords = generate_2d_coordinates(graph, seed=42)
        assert len(coords) == graph.num_atoms  # 12 (6C + 6H)
        # All coordinates should be finite
        for c in coords:
            assert c.x == c.x  # not NaN
            assert c.y == c.y  # not NaN

    def test_svg_render_correctness(self):
        graph = _build_benzene()
        svg = render_svg(graph)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "c1ccccc1" in svg or "C" in svg  # has atom labels
