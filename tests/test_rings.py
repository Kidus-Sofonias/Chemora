"""Tests for ring detection algorithms."""


from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.detection.rings import detect_rings


class TestRingDetection:
    """Tests for the detect_rings function."""

    def test_no_rings_linear_chain(self):
        """A linear chain of 4 carbons has no rings."""
        builder = MolecularGraphBuilder()
        prev = None
        atoms = []
        for _ in range(4):
            idx = builder.add_atom(atomic_number=6)
            atoms.append(idx)
            if prev is not None:
                builder.add_bond(prev, idx, BondOrder.SINGLE)
            prev = idx
        graph = builder.build()
        rings = detect_rings(graph)
        assert len(rings) == 0

    def test_no_rings_single_atom(self):
        """A single atom has no rings."""
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        graph = builder.build()
        rings = detect_rings(graph)
        assert len(rings) == 0

    def test_no_rings_two_atoms(self):
        """Two atoms cannot form a ring."""
        builder = MolecularGraphBuilder()
        a = builder.add_atom(atomic_number=6)
        b = builder.add_atom(atomic_number=6)
        builder.add_bond(a, b, BondOrder.SINGLE)
        graph = builder.build()
        rings = detect_rings(graph)
        assert len(rings) == 0

    def test_three_membered_ring(self):
        """Three atoms in a triangle form one ring."""
        builder = MolecularGraphBuilder()
        a = builder.add_atom(atomic_number=6)
        b = builder.add_atom(atomic_number=6)
        c = builder.add_atom(atomic_number=6)
        builder.add_bond(a, b, BondOrder.SINGLE)
        builder.add_bond(b, c, BondOrder.SINGLE)
        builder.add_bond(c, a, BondOrder.SINGLE)
        graph = builder.build()
        rings = detect_rings(graph)
        assert len(rings) >= 1
        # All rings should have size 3
        for ring in rings:
            assert ring.size >= 3

    def test_six_membered_ring(self):
        """Benzene-like ring (6 carbons in a cycle)."""
        builder = MolecularGraphBuilder()
        atoms = []
        for _ in range(6):
            atoms.append(builder.add_atom(atomic_number=6))
        for i in range(6):
            builder.add_bond(atoms[i], atoms[(i + 1) % 6], BondOrder.AROMATIC)
        graph = builder.build()
        rings = detect_rings(graph)
        assert len(rings) >= 1

    def test_bicyclic_system_rings(self):
        """A bicyclic system finds the expected rings.

        Structure: two fused 3-membered rings sharing edge a-c.
            Ring 1: a-b-c-a (atoms {0, 1, 2})
            Ring 2: a-c-d-a (atoms {0, 2, 3})
        The algorithm may also find the outer perimeter ring (a-b-c-d-a)
        as a 4-membered ring, which is also chemically valid.
        """
        builder = MolecularGraphBuilder()
        a = builder.add_atom(atomic_number=6)
        b = builder.add_atom(atomic_number=6)
        c = builder.add_atom(atomic_number=6)
        d = builder.add_atom(atomic_number=6)
        # Ring 1: a-b-c-a
        builder.add_bond(a, b, BondOrder.SINGLE)
        builder.add_bond(b, c, BondOrder.SINGLE)
        builder.add_bond(c, a, BondOrder.SINGLE)
        # Ring 2: a-c-d-a
        builder.add_bond(c, d, BondOrder.SINGLE)
        builder.add_bond(d, a, BondOrder.SINGLE)
        graph = builder.build()
        rings = detect_rings(graph)
        assert len(rings) >= 2, f"Expected at least 2 rings, got {len(rings)}"
        # Verify the two 3-membered rings are present
        ring_sets = [frozenset(r.atom_indices) for r in rings]
        expected = [frozenset({0, 1, 2}), frozenset({0, 2, 3})]
        for exp in expected:
            assert exp in ring_sets, f"Expected ring {set(exp)} not found in {[set(r) for r in ring_sets]}"
        # Verify all atoms in rings are correct
        all_ring_atoms = set().union(*ring_sets)
        assert all_ring_atoms == {0, 1, 2, 3}, (
            f"Ring atoms should be {{0,1,2,3}}, got {all_ring_atoms}"
        )

    def test_ring_count_property(self):
        """ring_count should match number of detected rings."""
        builder = MolecularGraphBuilder()
        atoms = []
        for _ in range(6):
            atoms.append(builder.add_atom(atomic_number=6))
        for i in range(6):
            builder.add_bond(atoms[i], atoms[(i + 1) % 6], BondOrder.AROMATIC)
        graph = builder.build()
        rings = detect_rings(graph)
        assert len(rings) >= 1

    def test_is_ring_atom(self):
        """is_ring_atom should identify atoms in rings."""
        builder = MolecularGraphBuilder()
        a = builder.add_atom(atomic_number=6)  # Ring atom
        b = builder.add_atom(atomic_number=6)  # Ring atom
        c = builder.add_atom(atomic_number=6)  # Ring atom
        d = builder.add_atom(atomic_number=6)  # Not in ring
        builder.add_bond(a, b, BondOrder.SINGLE)
        builder.add_bond(b, c, BondOrder.SINGLE)
        builder.add_bond(c, a, BondOrder.SINGLE)
        # Attach d as side chain
        builder.add_bond(a, d, BondOrder.SINGLE)
        graph = builder.build()
        rings = detect_rings(graph)
        # a should be in at least one ring
        a_in_ring = any(a in ring.atom_indices for ring in rings)
        assert a_in_ring, "a should be a ring atom"
        # d should not be in any ring (it's a side chain)
        d_in_ring = any(d in ring.atom_indices for ring in rings)
        assert not d_in_ring, "d should not be a ring atom"
