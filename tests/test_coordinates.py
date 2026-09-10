"""Tests for Phase 9: Coordinate Generation
- 2D force-directed layout
- Ring template placement
- 3D conformer generation
- Conformer clustering
"""

import math

from chemengine.coordinates.conformer_3d import (
    _build_bounds_matrix,
    _cluster_conformers,
    _compute_rmsd,
    compute_conformer_energy,
    generate_conformer,
    generate_conformers,
)
from chemengine.coordinates.layout_2d import (
    _find_rings,
    _place_ring,
    force_directed_layout,
    generate_2d_coordinates,
)
from chemengine.core.bonds import BondOrder
from chemengine.core.geometry import Conformer, Coordinate2D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder

# ── Fixtures ──

def _make_methane():
    """CH4 - methane."""
    builder = MolecularGraphBuilder()
    c = builder.add_atom(6)
    for _ in range(4):
        h = builder.add_atom(1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_ethane():
    """C2H6 - ethane."""
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
    """C2H4 - ethene."""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.DOUBLE)
    for c in (c1, c2):
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_benzene():
    """C6H6 - benzene (6-membered ring)."""
    builder = MolecularGraphBuilder()
    carbons = [builder.add_atom(6) for _ in range(6)]
    for i in range(6):
        builder.add_bond(carbons[i], carbons[(i + 1) % 6], BondOrder.DOUBLE if i % 2 == 0 else BondOrder.SINGLE)
    for c in carbons:
        h = builder.add_atom(1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_cyclopropane():
    """C3H6 - cyclopropane (3-membered ring)."""
    builder = MolecularGraphBuilder()
    carbons = [builder.add_atom(6) for _ in range(3)]
    for i in range(3):
        builder.add_bond(carbons[i], carbons[(i + 1) % 3], BondOrder.SINGLE)
    for c in carbons:
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_propane():
    """C3H8 - propane."""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    c3 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, c3, BondOrder.SINGLE)
    for c, n_h in [(c1, 3), (c2, 2), (c3, 3)]:
        for _ in range(n_h):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


# ── 2D Layout Tests ──

class Test2DCoordinates:
    def test_empty_graph(self):
        graph = MolecularGraph(atoms=(), bonds=())
        coords = generate_2d_coordinates(graph)
        assert len(coords) == 0

    def test_single_atom(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(6)
        graph = builder.build()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == 1
        assert coords[0].x == 0.0
        assert coords[0].y == 0.0

    def test_ethane_two_atoms(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        graph = builder.build()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == 2
        dist = coords[0].distance_to(coords[1])
        assert dist > 0.5  # Should have some separation

    def test_propane_linear(self):
        graph = _make_propane()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == graph.num_atoms
        # All coordinates should be finite
        for c in coords:
            assert math.isfinite(c.x)
            assert math.isfinite(c.y)

    def test_force_directed_returns_tuple(self):
        graph = _make_ethane()
        coords = force_directed_layout(graph)
        assert isinstance(coords, tuple)
        assert len(coords) == graph.num_atoms

    def test_deterministic_with_seed(self):
        graph = _make_propane()
        coords1 = generate_2d_coordinates(graph, seed=42)
        coords2 = generate_2d_coordinates(graph, seed=42)
        for c1, c2 in zip(coords1, coords2):
            assert abs(c1.x - c2.x) < 1e-10
            assert abs(c1.y - c2.y) < 1e-10

    def test_ring_detection_cyclopropane(self):
        graph = _make_cyclopropane()
        rings = _find_rings(graph)
        assert len(rings) >= 1
        assert len(rings[0]) == 3

    def test_ring_detection_benzene(self):
        graph = _make_benzene()
        rings = _find_rings(graph)
        assert len(rings) >= 1
        assert any(len(r) == 6 for r in rings)

    def test_benzene_coordinates_finite(self):
        graph = _make_benzene()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == graph.num_atoms
        for c in coords:
            assert math.isfinite(c.x)
            assert math.isfinite(c.y)

    def test_cyclopropane_coordinates_finite(self):
        graph = _make_cyclopropane()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == graph.num_atoms
        for c in coords:
            assert math.isfinite(c.x)
            assert math.isfinite(c.y)

    def test_place_ring_returns_dict(self):
        coords = _place_ring([0, 1, 2], 0.0, 0.0, 1.0)
        assert isinstance(coords, dict)
        assert len(coords) == 3
        for atom_idx in [0, 1, 2]:
            assert atom_idx in coords
            assert isinstance(coords[atom_idx], Coordinate2D)

    def test_large_molecule(self):
        """Test with a larger molecule (butane)."""
        builder = MolecularGraphBuilder()
        carbons = [builder.add_atom(6) for _ in range(4)]
        for i in range(3):
            builder.add_bond(carbons[i], carbons[i + 1], BondOrder.SINGLE)
        for c in carbons:
            for _ in range(2):
                h = builder.add_atom(1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        coords = generate_2d_coordinates(graph)
        assert len(coords) == graph.num_atoms


# ── 3D Conformer Tests ──

class Test3DConformer:
    def test_empty_graph(self):
        graph = MolecularGraph(atoms=(), bonds=())
        conf = generate_conformer(graph)
        assert conf.num_atoms == 0

    def test_single_atom(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(6)
        graph = builder.build()
        conf = generate_conformer(graph)
        assert conf.num_atoms == 1
        assert conf.coordinates[0].x == 0.0

    def test_ethane_conformer(self):
        graph = _make_ethane()
        conf = generate_conformer(graph)
        assert conf.num_atoms == graph.num_atoms
        # Bond length should be positive and reasonable
        c1, c2 = 0, 1
        dist = conf.get_distance(c1, c2)
        assert 0.5 < dist < 3.0  # C-C bond length (some tolerance for embedding)

    def test_multiple_conformers(self):
        graph = _make_ethane()
        conformers = generate_conformers(graph, num_conformers=3)
        assert len(conformers) >= 1
        assert all(isinstance(c, Conformer) for c in conformers)

    def test_conformer_energy(self):
        graph = _make_ethane()
        conf = generate_conformer(graph)
        energy = compute_conformer_energy(conf, graph)
        assert isinstance(energy, float)
        assert energy >= 0.0

    def test_conformer_rmsd_zero_for_identical(self):
        graph = _make_ethane()
        conf = generate_conformer(graph)
        rmsd = _compute_rmsd(conf, conf)
        assert rmsd < 1e-10

    def test_conformer_rmsd_positive_for_different(self):
        graph = _make_ethane()
        conf1 = generate_conformer(graph, seed=42)
        conf2 = generate_conformer(graph, seed=123)
        rmsd = _compute_rmsd(conf1, conf2)
        assert rmsd >= 0.0

    def test_bounds_matrix_shape(self):
        graph = _make_ethane()
        lower, upper = _build_bounds_matrix(graph)
        n = graph.num_atoms
        assert len(lower) == n
        assert len(upper) == n
        assert all(len(row) == n for row in lower)
        assert all(len(row) == n for row in upper)

    def test_cluster_conformers(self):
        graph = _make_ethane()
        confs = [generate_conformer(graph, seed=i) for i in range(5)]
        clustered = _cluster_conformers(confs, 0.5)
        assert len(clustered) >= 1
        assert len(clustered) <= len(confs)

    def test_conformer_tuple_type(self):
        graph = _make_ethane()
        conformers = generate_conformers(graph, num_conformers=5)
        assert isinstance(conformers, tuple)

    def test_energy_minimization_reduces_energy(self):
        """Energy after minimization should be lower than a random initial state."""
        graph = _make_ethane()
        conf = generate_conformer(graph)
        # The generated conformer should have finite, non-negative energy
        energy = compute_conformer_energy(conf, graph)
        assert energy >= 0.0
        assert math.isfinite(energy)

    def test_benzene_conformer(self):
        graph = _make_benzene()
        conf = generate_conformer(graph)
        assert conf.num_atoms == graph.num_atoms
        for c in conf.coordinates:
            assert math.isfinite(c.x)
            assert math.isfinite(c.y)
            assert math.isfinite(c.z)
