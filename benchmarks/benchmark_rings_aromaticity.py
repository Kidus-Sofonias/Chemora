"""
Performance benchmarks for ring detection, ring system analysis, and aromaticity.

Covers:
  - SSSR ring detection on small and fused ring systems
  - All-ring enumeration
  - Ring atom/bond queries
  - Ring system classification (fused, spiro, bridged)
  - Hückel aromaticity assessment
  - Bulk aromaticity assignment
"""

import pytest
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.core.bonds import BondOrder
from chemengine.detection.rings import detect_rings, find_all_rings, is_ring_atom, is_ring_bond, ring_count
from chemengine.detection.ring_systems import detect_ring_systems, is_spiro_center, is_bridgehead_atom
from chemengine.detection.aromaticity import AromaticityType, assess_ring_aromaticity, assess_all_rings


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def benzene_graph():
    """Benzene C6H6 — single aromatic ring."""
    builder = MolecularGraphBuilder()
    carbons = [builder.add_atom(atomic_number=6) for _ in range(6)]
    for i in range(6):
        builder.add_bond(carbons[i], carbons[(i + 1) % 6], BondOrder.AROMATIC)
    for c in carbons:
        h = builder.add_atom(atomic_number=1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


@pytest.fixture
def naphthalene_graph():
    """Naphthalene C10H8 — two fused aromatic rings."""
    builder = MolecularGraphBuilder()
    # Ring 1: C0 C1 C2 C3 C4 C5
    # Ring 2: C5 C4 C6 C7 C8 C9 (fused along C4-C5)
    carbons = [builder.add_atom(atomic_number=6) for _ in range(10)]
    # Ring 1 bonds
    for idx in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)]:
        builder.add_bond(carbons[idx[0]], carbons[idx[1]], BondOrder.AROMATIC)
    # Ring 2 bonds (fused edge 4-5 already exists)
    for idx in [(5, 9), (9, 8), (8, 7), (7, 6), (6, 4)]:
        builder.add_bond(carbons[idx[0]], carbons[idx[1]], BondOrder.AROMATIC)
    # Hydrogens (2 per carbon for most, but fused carbons only get 1)
    # Simplification: add 1 H per carbon
    for c in carbons:
        h = builder.add_atom(atomic_number=1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


@pytest.fixture
def spiro_graph():
    """Spiro[2.2]pentane — two rings sharing 1 spiro carbon."""
    builder = MolecularGraphBuilder()
    atoms = [builder.add_atom(atomic_number=6) for _ in range(5)]
    # Ring 1: 0-1-2-0
    builder.add_bond(atoms[0], atoms[1], BondOrder.SINGLE)
    builder.add_bond(atoms[1], atoms[2], BondOrder.SINGLE)
    builder.add_bond(atoms[2], atoms[0], BondOrder.SINGLE)
    # Ring 2: 0-3-4-0 (shares atom 0)
    builder.add_bond(atoms[0], atoms[3], BondOrder.SINGLE)
    builder.add_bond(atoms[3], atoms[4], BondOrder.SINGLE)
    builder.add_bond(atoms[4], atoms[0], BondOrder.SINGLE)
    # Saturated hydrogens (2 per carbon except 0 which has 0)
    for i, a in enumerate(atoms):
        h_count = 0 if i == 0 else 2
        for _ in range(h_count):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(a, h, BondOrder.SINGLE)
    return builder.build()


@pytest.fixture
def propellane_graph():
    """[1.1.1]Propellane — 2 bridgehead atoms each in 3 rings.

    Structure:
      C0 and C1 are bridgeheads (each in all 3 rings).
      C2, C3, C4 are bridge carbons.
      Rings: C0-C2-C1, C0-C3-C1, C0-C4-C1
    """
    builder = MolecularGraphBuilder()
    atoms = [builder.add_atom(atomic_number=6) for _ in range(5)]
    # Three bridges: 0-2-1, 0-3-1, 0-4-1
    for bridge in [(0, 2, 1), (0, 3, 1), (0, 4, 1)]:
        builder.add_bond(atoms[bridge[0]], atoms[bridge[1]], BondOrder.SINGLE)
        builder.add_bond(atoms[bridge[1]], atoms[bridge[2]], BondOrder.SINGLE)
    # Hydrogens: bridgeheads get 0, bridge carbons get 2 each
    for i, a in enumerate(atoms):
        h_count = 0 if i in (0, 1) else 2
        for _ in range(h_count):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(a, h, BondOrder.SINGLE)
    return builder.build()


# ── Ring Detection Benchmarks ─────────────────────────────────────────

class TestRingDetectionBenchmarks:
    """Benchmarks for SSSR ring detection."""

    def test_detect_rings_benzene(self, benchmark, benzene_graph):
        """Benchmark SSSR detection on benzene (6 atoms, 1 ring)."""
        result = benchmark(lambda: detect_rings(benzene_graph))
        assert len(result) >= 1
        assert result[0].size == 6

    def test_detect_rings_naphthalene(self, benchmark, naphthalene_graph):
        """Benchmark SSSR detection on naphthalene (10 atoms, 2 fused rings)."""
        result = benchmark(lambda: detect_rings(naphthalene_graph))
        assert len(result) >= 2

    def test_detect_rings_spiro(self, benchmark, spiro_graph):
        """Benchmark SSSR detection on spiro[2.2]pentane (2 rings, 1 shared atom)."""
        result = benchmark(lambda: detect_rings(spiro_graph))
        assert len(result) >= 2

    def test_detect_rings_propellane(self, benchmark, propellane_graph):
        """Benchmark SSSR detection on [1.1.1]propellane (3 rings, bridged)."""
        result = benchmark(lambda: detect_rings(propellane_graph))
        assert len(result) >= 3

    def test_find_all_rings_benzene(self, benchmark, benzene_graph):
        """Benchmark all-ring enumeration on benzene."""
        result = benchmark(lambda: find_all_rings(benzene_graph))
        assert len(result) >= 1

    def test_ring_count_benzene(self, benchmark, benzene_graph):
        """Benchmark ring_count call on benzene."""
        result = benchmark(lambda: ring_count(benzene_graph))
        assert result >= 1

    def test_is_ring_atom_benzene(self, benchmark, benzene_graph):
        """Benchmark is_ring_atom on all atoms of benzene."""
        def check_all():
            return [is_ring_atom(benzene_graph, i) for i in range(6)]
        result = benchmark(check_all)
        assert all(result)

    def test_is_ring_bond_benzene(self, benchmark, benzene_graph):
        """Benchmark is_ring_bond on bonds of benzene (checks bond index 0)."""
        detect_rings(benzene_graph)  # Ensure rings are cached on the graph
        result = benchmark(lambda: is_ring_bond(benzene_graph, 0))
        assert result is True


# ── Ring System Analysis Benchmarks ───────────────────────────────────

class TestRingSystemBenchmarks:
    """Benchmarks for ring system classification."""

    def test_detect_ring_systems_naphthalene(self, benchmark, naphthalene_graph):
        """Benchmark ring system detection on naphthalene (fused)."""
        detect_rings(naphthalene_graph)  # Pre-cache rings
        result = benchmark(lambda: detect_ring_systems(naphthalene_graph))
        assert len(result) >= 1

    def test_detect_ring_systems_spiro(self, benchmark, spiro_graph):
        """Benchmark ring system detection on spiro compound."""
        detect_rings(spiro_graph)  # Pre-cache rings
        result = benchmark(lambda: detect_ring_systems(spiro_graph))
        assert len(result) >= 1

    def test_is_spiro_center_true(self, benchmark, spiro_graph):
        """Benchmark is_spiro_center on a spiro carbon."""
        detect_rings(spiro_graph)  # Pre-cache rings
        result = benchmark(lambda: is_spiro_center(spiro_graph, 0))
        assert result is True

    def test_is_spiro_center_false(self, benchmark, benzene_graph):
        """Benchmark is_spiro_center on a non-spiro carbon."""
        detect_rings(benzene_graph)  # Pre-cache rings
        result = benchmark(lambda: is_spiro_center(benzene_graph, 0))
        assert result is False

    def test_is_bridgehead_true(self, benchmark, propellane_graph):
        """Benchmark is_bridgehead_atom on a propellane bridgehead (in 3 rings)."""
        detect_rings(propellane_graph)  # Pre-cache rings
        result = benchmark(lambda: is_bridgehead_atom(propellane_graph, 0))
        assert result is True

    def test_is_bridgehead_false(self, benchmark, benzene_graph):
        """Benchmark is_bridgehead_atom on a non-bridgehead carbon."""
        detect_rings(benzene_graph)  # Pre-cache rings
        result = benchmark(lambda: is_bridgehead_atom(benzene_graph, 0))
        assert result is False


# ── Aromaticity Detection Benchmarks ──────────────────────────────────

class TestAromaticityBenchmarks:
    """Benchmarks for Hückel aromaticity detection."""

    def test_assess_ring_aromaticity_benzene(self, benchmark, benzene_graph):
        """Benchmark aromaticity assessment on benzene (6π, aromatic)."""
        rings = detect_rings(benzene_graph)
        result = benchmark(lambda: assess_ring_aromaticity(benzene_graph, rings[0]))
        assert result.result == AromaticityType.AROMATIC
        assert result.pi_electrons == 6

    def test_assess_ring_aromaticity_naphthalene(self, benchmark, naphthalene_graph):
        """Benchmark aromaticity assessment on naphthalene (both rings)."""
        rings = detect_rings(naphthalene_graph)
        def assess_both():
            return [assess_ring_aromaticity(naphthalene_graph, r) for r in rings]
        results = benchmark(assess_both)
        assert all(r.result == AromaticityType.AROMATIC for r in results)

    def test_assess_all_rings_benzene(self, benchmark, benzene_graph):
        """Benchmark assess_all_rings on benzene."""
        result = benchmark(lambda: assess_all_rings(benzene_graph))
        assert len(result) >= 1
        assert result[0].result == AromaticityType.AROMATIC

    def test_assess_all_rings_naphthalene(self, benchmark, naphthalene_graph):
        """Benchmark assess_all_rings on naphthalene."""
        detect_rings(naphthalene_graph)  # Pre-cache rings
        result = benchmark(lambda: assess_all_rings(naphthalene_graph))
        assert len(result) >= 2
        assert all(r.result == AromaticityType.AROMATIC for r in result)


# ── Mixed / Integration Benchmarks ────────────────────────────────────

class TestIntegrationBenchmarks:
    """Benchmarks for combined ring + aromaticity pipelines."""

    def test_full_pipeline_benzene(self, benchmark, benzene_graph):
        """Benchmark full pipeline: detect_rings → assess_all_rings on benzene."""
        def pipeline():
            rings = detect_rings(benzene_graph)
            return assess_all_rings(benzene_graph)
        results = benchmark(pipeline)
        assert len(results) >= 1
        assert results[0].result == AromaticityType.AROMATIC

    def test_full_pipeline_naphthalene(self, benchmark, naphthalene_graph):
        """Benchmark full pipeline: detect_rings → detect_ring_systems → assess on naphthalene."""
        def pipeline():
            rings = detect_rings(naphthalene_graph)
            systems = detect_ring_systems(naphthalene_graph)
            arom = assess_all_rings(naphthalene_graph)
            return len(systems), len(arom)
        systems_count, arom_count = benchmark(pipeline)
        assert systems_count >= 1
        assert arom_count >= 2
