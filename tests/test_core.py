"""Tests for core domain models."""

import pytest

from chemengine.core.atoms import Atom, Isotope
from chemengine.core.bonds import Bond, BondOrder, BondTopology
from chemengine.core.charges import Charge
from chemengine.core.enums import BondStereo
from chemengine.core.geometry import Conformer, Coordinate2D, Coordinate3D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder


class TestAtom:
    """Tests for the Atom domain model."""

    def test_create_carbon(self):
        atom = Atom(atomic_number=6)
        assert atom.atomic_number == 6
        assert atom.atomic_number == 6
        assert atom.symbol == "C"
        assert atom.formal_charge == 0
        assert atom.is_metal is False
        assert atom.is_halogen is False

    def test_create_oxygen(self):
        atom = Atom(atomic_number=8)
        assert atom.symbol == "O"
        assert atom.is_chalcogen is True

    def test_create_iron(self):
        atom = Atom(atomic_number=26)
        assert atom.symbol == "Fe"
        assert atom.is_metal is True

    def test_with_charge(self):
        atom = Atom(atomic_number=6)
        charged = atom.with_charge(1)
        assert charged.formal_charge == 1
        assert atom.formal_charge == 0  # Original unchanged

    def test_with_isotope(self):
        atom = Atom(atomic_number=6)
        iso = Isotope(mass_number=13, exact_mass=13.003355, abundance=0.0107)
        labeled = atom.with_isotope(iso)
        assert labeled.isotope is not None
        assert labeled.isotope.mass_number == 13

    def test_radical_type(self):
        atom = Atom(atomic_number=6, radical_electrons=1)
        assert atom.radical_electrons == 1
        assert atom.radical_type.value == "monoradical"

    def test_immutable(self):
        atom = Atom(atomic_number=6)
        with pytest.raises(AttributeError):
            atom.atomic_number = 8  # type: ignore


class TestBond:
    """Tests for the Bond domain model."""

    def test_create_single_bond(self):
        bond = Bond(atom1=0, atom2=1, order=BondOrder.SINGLE)
        assert bond.atom1 == 0
        assert bond.atom2 == 1
        assert bond.order == BondOrder.SINGLE
        assert bond.is_rotatable is True

    def test_create_double_bond(self):
        bond = Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE)
        assert bond.is_rotatable is False

    def test_aromatic_bond(self):
        bond = Bond(atom1=0, atom2=1, order=BondOrder.AROMATIC)
        assert bond.is_aromatic is True

    def test_with_stereochemistry(self):
        bond = Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE)
        stereo = bond.with_stereochemistry(BondStereo.E)
        assert stereo.is_stereogenic is True
        assert stereo.stereochemistry == BondStereo.E

    def test_ring_bond(self):
        bond = Bond(atom1=0, atom2=1, topology=BondTopology.RING)
        assert bond.is_ring_bond is True
        assert bond.is_rotatable is False


class TestMolecularGraph:
    """Tests for the MolecularGraph domain model."""

    def test_empty_graph(self):
        graph = MolecularGraph(atoms=(), bonds=())
        assert graph.num_atoms == 0
        assert graph.num_bonds == 0

    def test_methane_formula(self, methane_graph):
        assert methane_graph.molecular_formula == "CH4"
        assert methane_graph.num_atoms == 5
        assert methane_graph.num_bonds == 4

    def test_ethane_formula(self, ethane_graph):
        assert ethane_graph.molecular_formula == "C2H6"
        assert ethane_graph.num_atoms == 8
        assert ethane_graph.num_bonds == 7

    def test_benzene_formula(self, benzene_graph):
        assert benzene_graph.molecular_formula == "C6H6"
        assert benzene_graph.num_atoms == 12
        assert benzene_graph.num_bonds == 12

    def test_get_neighbors(self, ethane_graph):
        neighbors = ethane_graph.get_neighbors(0)
        assert len(neighbors) == 4  # 1 carbon + 3 hydrogens

    def test_is_connected(self, ethane_graph):
        assert ethane_graph.is_connected is True

    def test_heavy_atoms(self, ethane_graph):
        assert ethane_graph.num_heavy_atoms == 2

    def test_graph_hash(self, methane_graph):
        h = methane_graph.graph_hash
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256

    def test_immutable(self, methane_graph):
        with pytest.raises(AttributeError):
            methane_graph.name = "test"  # type: ignore


class TestMolecularGraphBuilder:
    """Tests for the MolecularGraphBuilder."""

    def test_build_methane(self):
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        assert graph.molecular_formula == "CH4"

    def test_build_water(self):
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8)
        h1 = builder.add_atom(atomic_number=1)
        h2 = builder.add_atom(atomic_number=1)
        builder.add_bond(o, h1, BondOrder.SINGLE)
        builder.add_bond(o, h2, BondOrder.SINGLE)
        graph = builder.build()
        assert graph.molecular_formula == "H2O"

    def test_from_graph(self, methane_graph):
        builder = MolecularGraphBuilder.from_graph(methane_graph)
        # Add another carbon
        c2 = builder.add_atom(atomic_number=6)
        graph = builder.build()
        assert graph.num_atoms == methane_graph.num_atoms + 1

    def test_set_name(self):
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        builder.set_name("methane")
        graph = builder.build()
        assert graph.name == "methane"


class TestGeometry:
    """Tests for geometry domain models."""

    def test_coordinate2d_distance(self):
        p1 = Coordinate2D(0.0, 0.0)
        p2 = Coordinate2D(3.0, 4.0)
        assert p1.distance_to(p2) == 5.0

    def test_coordinate3d_distance(self):
        p1 = Coordinate3D(0.0, 0.0, 0.0)
        p2 = Coordinate3D(1.0, 2.0, 2.0)
        assert p1.distance_to(p2) == 3.0

    def test_conformer(self):
        conf = Conformer(
            id=0,
            coordinates=(Coordinate3D(0.0, 0.0, 0.0), Coordinate3D(1.5, 0.0, 0.0)),
            energy=0.0,
        )
        assert conf.num_atoms == 2
        assert conf.get_distance(0, 1) == 1.5


class TestCharges:
    """Tests for charge domain models."""

    def test_charge_positive(self):
        fc = Charge(value=1, atom_index=0)
        assert fc.is_positive is True
        assert fc.is_neutral is False

    def test_radical_electron(self):
        # Test Charge with atom_index (used for radical context tracking)
        fc = Charge(value=0, atom_index=0)
        assert fc.is_neutral is True
