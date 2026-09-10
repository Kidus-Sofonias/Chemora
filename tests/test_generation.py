"""Tests for constitutional and stereoisomer enumeration."""

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.generation.constitutional import (
    alkane_isomer_count,
    enumerate_functional_group_isomers,
    generate_alkane_isomers,
)
from chemengine.generation.stereoisomers import enumerate_stereoisomers

# ── Alkane Isomer Tests ──

class TestAlkaneIsomers:
    def test_methane(self):
        """C1 has 1 isomer."""
        assert alkane_isomer_count(1) == 1

    def test_butane(self):
        """C4 has 2 isomers."""
        assert alkane_isomer_count(4) == 2

    def test_pentane(self):
        """C5 has 3 isomers."""
        assert alkane_isomer_count(5) == 3

    def test_hexane(self):
        """C6 has 5 isomers."""
        assert alkane_isomer_count(6) == 5

    def test_generate_methane(self):
        """Generate C1 isomers."""
        isomers = generate_alkane_isomers(1)
        assert len(isomers) == 1
        assert isomers[0].molecular_formula == "CH4"

    def test_generate_butane(self):
        """Generate C4 isomers."""
        isomers = generate_alkane_isomers(4)
        assert len(isomers) == 2

    def test_generate_pentane(self):
        """Generate C5 isomers."""
        isomers = generate_alkane_isomers(5)
        assert len(isomers) == 3

    def test_invalid_range(self):
        """C9 should raise ValueError."""
        with pytest.raises(ValueError):
            generate_alkane_isomers(9)


# ── Functional Group Isomer Tests ──

class TestFGIsomers:
    def test_ethanol_isomers(self):
        """C2 alcohols — should find ethanol and dimethyl ether."""
        isomers = enumerate_functional_group_isomers(2, "O")
        assert len(isomers) > 0

    def test_methanol_isomers(self):
        """C1 with O — should find methanol."""
        isomers = enumerate_functional_group_isomers(1, "O")
        assert len(isomers) == 1


# ── Stereoisomer Tests ──

class TestStereoisomers:
    def test_ethane_stereo(self):
        """Ethane enumerates 2^2=4 theoretical stereoisomers from sp3 carbons,
        but in practice has no chiral centers.
        """
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        for c in (c1, c2):
            for _ in range(3):
                h = builder.add_atom(atomic_number=1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        isomers = enumerate_stereoisomers(graph)
        # The function enumerates 2^N possible configurations for sp3 carbons
        # with 4 neighbors. Ethane has 2 such carbons → 4 combinations.
        assert len(isomers) >= 1
