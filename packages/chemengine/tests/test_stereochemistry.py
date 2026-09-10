"""Tests for stereochemistry perception and assignment."""

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.stereochemistry.cip import get_cip_priority, is_chiral_center
from chemengine.stereochemistry.double_bond import is_stereogenic_double_bond
from chemengine.stereochemistry.perception import perceive_stereochemistry
from chemengine.stereochemistry.tetrahedral import detect_tetrahedral_centers

# ── CIP Priority Tests ──

class TestCIPPriority:
    def test_single_substituent(self):
        """Single substituent gets priority 1."""
        graph = MolecularGraph(atoms=[], bonds=[])
        result = get_cip_priority(graph, 0, [1])
        assert result == [1]

    def test_two_substituents(self):
        """Higher atomic number should have higher priority."""
        # Use a simple builder
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        o = builder.add_atom(atomic_number=8)
        builder.add_bond(c, o, BondOrder.SINGLE)
        graph = builder.build()
        result = get_cip_priority(graph, c, [o, c])  # o has higher Z
        assert result == [o, c]  # O first (higher priority)


# ── Tetrahedral Center Tests ──

class TestTetrahedral:
    def test_is_chiral_center_true(self):
        """A carbon with 4 distinct neighbors should be chiral."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        n1 = builder.add_atom(atomic_number=8)  # O
        n2 = builder.add_atom(atomic_number=9)  # F
        n3 = builder.add_atom(atomic_number=17)  # Cl
        n4 = builder.add_atom(atomic_number=35)  # Br
        for n in (n1, n2, n3, n4):
            builder.add_bond(c, n, BondOrder.SINGLE)
        graph = builder.build()
        assert is_chiral_center(graph, c) is True

    def test_is_chiral_center_false_no_sp3(self):
        """Carbon with 3 neighbors is not a chiral center."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        n1 = builder.add_atom(atomic_number=8)
        n2 = builder.add_atom(atomic_number=8)
        n3 = builder.add_atom(atomic_number=8)
        for n in (n1, n2, n3):
            builder.add_bond(c, n, BondOrder.SINGLE)
        graph = builder.build()
        assert is_chiral_center(graph, c) is False

    def test_detect_tetrahedral_centers_none(self):
        """Methane has no chiral center (all H are same)."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        centers = detect_tetrahedral_centers(graph)
        assert len(centers) == 0  # All substituents are H — not distinct


# ── Double Bond Tests ──

class TestDoubleBond:
    def test_ethylene_not_stereogenic(self):
        """C=C (ethylene) has no stereogenic double bond."""
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        for c in (c1, c2):
            for _ in range(2):
                h = builder.add_atom(atomic_number=1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert is_stereogenic_double_bond(graph, 0) is False


# ── Stereo Perception Tests ──

class TestStereoPerception:
    def test_perceive_stereo_empty(self):
        """Empty graph returns empty config."""
        graph = MolecularGraph(atoms=(), bonds=())
        config = perceive_stereochemistry(graph)
        assert config.count == 0

    def test_perceive_stereo_methane(self):
        """Methane has no stereocenters."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        config = perceive_stereochemistry(graph)
        assert config.count == 0

    def test_perceive_stereo_chiral(self):
        """A carbon with 4 distinct substituents should be detected."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        n1 = builder.add_atom(atomic_number=9)  # F
        n2 = builder.add_atom(atomic_number=17)  # Cl
        n3 = builder.add_atom(atomic_number=35)  # Br
        n4 = builder.add_atom(atomic_number=53)  # I
        for n in (n1, n2, n3, n4):
            builder.add_bond(c, n, BondOrder.SINGLE)
        graph = builder.build()
        config = perceive_stereochemistry(graph)
        assert config.count >= 1
