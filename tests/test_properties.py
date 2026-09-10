"""Tests for molecular property computation."""

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.properties.descriptors import (
    compute_fraction_csp3,
    compute_hba,
    compute_hbd,
    compute_logp,
    compute_property,
    compute_rotatable_bonds,
    compute_tpsa,
)

# ── HBA / HBD Tests ──

class TestHBAHBD:
    def test_water_hba(self):
        """Water has 1 HBA (oxygen)."""
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8)
        h1 = builder.add_atom(atomic_number=1)
        h2 = builder.add_atom(atomic_number=1)
        builder.add_bond(o, h1, BondOrder.SINGLE)
        builder.add_bond(o, h2, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_hba(graph) == 1

    def test_water_hbd(self):
        """Water has 1 HBD (2 O-H bonds → 1 group count)."""
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8)
        h1 = builder.add_atom(atomic_number=1)
        h2 = builder.add_atom(atomic_number=1)
        builder.add_bond(o, h1, BondOrder.SINGLE)
        builder.add_bond(o, h2, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_hbd(graph) == 1

    def test_methane_hba(self):
        """Methane has 0 HBA."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_hba(graph) == 0

    def test_methane_hbd(self):
        """Methane has 0 HBD."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_hbd(graph) == 0


# ── Rotatable Bonds Tests ──

class TestRotatableBonds:
    def test_ethane_rotatable(self):
        """Ethane: C-C bond has both terminal carbons, so 0 rotatable."""
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        for c in (c1, c2):
            for _ in range(3):
                h = builder.add_atom(atomic_number=1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_rotatable_bonds(graph) == 0


# ── logP Tests ──

class TestLogP:
    def test_methane_logp(self):
        """Methane should have positive logP (hydrophobic)."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        logp = compute_logp(graph)
        assert logp > 0  # Methane should be hydrophobic (positive logP)

    def test_water_logp(self):
        """Water should have negative logP (hydrophilic)."""
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8)
        h1 = builder.add_atom(atomic_number=1)
        h2 = builder.add_atom(atomic_number=1)
        builder.add_bond(o, h1, BondOrder.SINGLE)
        builder.add_bond(o, h2, BondOrder.SINGLE)
        graph = builder.build()
        logp = compute_logp(graph)
        assert logp < 0  # Water should be hydrophilic (negative logP)


# ── TPSA Tests ──

class TestTPSA:
    def test_methane_tpsa(self):
        """Methane has 0 TPSA (no polar atoms)."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_tpsa(graph) == 0.0

    def test_water_tpsa(self):
        """Water should have TPSA > 0."""
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8)
        h1 = builder.add_atom(atomic_number=1)
        h2 = builder.add_atom(atomic_number=1)
        builder.add_bond(o, h1, BondOrder.SINGLE)
        builder.add_bond(o, h2, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_tpsa(graph) > 0


# ── Fraction CSp3 Tests ──

class TestFractionCSp3:
    def test_methane_all_sp3(self):
        """Methane is 100% sp3."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_fraction_csp3(graph) == 1.0


# ── Property Registry Tests ──

class TestPropertyRegistry:
    def test_compute_formula(self):
        """Compute formula via registry."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_property(graph, "formula") == "CH4"

    def test_compute_mass(self):
        """Compute mass via registry."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert compute_property(graph, "mass") > 0

    def test_compute_unknown(self):
        """Unknown property should raise KeyError."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        with pytest.raises(KeyError):
            compute_property(graph, "unknown_property")
