"""Tests for the Molecule wrapper class."""

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.enums import SpinMultiplicity
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.core.molecule import MolecularIdentifiers, MolecularProperties, Molecule
from chemengine.parsing.smiles import parse_smiles


class TestMolecularIdentifiers:
    """Tests for MolecularIdentifiers."""

    def test_default_identifiers(self):
        ids = MolecularIdentifiers()
        assert ids.smiles == ""
        assert ids.formula == ""
        assert ids.name == ""

    def test_identifiers_immutable(self):
        ids = MolecularIdentifiers()
        with pytest.raises((AttributeError, TypeError)):
            ids.smiles = "CCO"


class TestMolecularProperties:
    """Tests for MolecularProperties."""

    def test_default_properties(self):
        props = MolecularProperties()
        assert props.exact_mass == 0.0
        assert props.num_atoms == 0
        assert props.log_p is None
        assert props.spin_multiplicity == SpinMultiplicity.SINGLET

    def test_properties_immutable(self):
        props = MolecularProperties()
        with pytest.raises((AttributeError, TypeError)):
            props.exact_mass = 42.0


class TestMolecule:
    """Tests for the Molecule class."""

    def test_create_from_graph(self):
        """Create a Molecule from a MolecularGraph."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        mol = Molecule.from_graph(graph)
        assert mol.formula == "CH4"
        assert mol.exact_mass > 0
        assert mol.num_atoms == 5

    def test_molecule_from_smiles(self):
        """Create a Molecule from a parsed SMILES."""
        graph = parse_smiles("CCO")
        mol = Molecule.from_graph(graph)
        assert mol.formula == "C2H6O"
        assert mol.num_atoms == 9
        assert mol.num_bonds == 8

    def test_molecule_name(self):
        """Molecule should inherit name from graph."""
        builder = MolecularGraphBuilder()
        builder.set_name("ethanol")
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        o = builder.add_atom(atomic_number=8)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c2, o, BondOrder.SINGLE)
        graph = builder.build()
        mol = Molecule.from_graph(graph)
        assert mol.name == "ethanol"

    def test_molecular_weight(self):
        graph = parse_smiles("CCO")
        mol = Molecule.from_graph(graph)
        assert mol.molecular_weight > 0
        assert abs(mol.molecular_weight - 46.07) < 0.1

    def test_charge_properties(self):
        """Molecule should compute total charge."""
        graph = parse_smiles("[NH4+]")
        mol = Molecule.from_graph(graph)
        assert mol.properties.charge == 1

    def test_neutral_molecule_charge(self):
        graph = parse_smiles("CCO")
        mol = Molecule.from_graph(graph)
        assert mol.properties.charge == 0

    def test_hba_hbd_counts(self):
        """Ethanol should have 1 HBA (O) and 1 HBD (O-H)."""
        graph = parse_smiles("CCO")
        mol = Molecule.from_graph(graph)
        assert mol.properties.hba >= 1
        assert mol.properties.hbd >= 1

    def test_heavy_atom_count(self):
        """Ethanol has 3 heavy atoms: 2 C + 1 O."""
        graph = parse_smiles("CCO")
        mol = Molecule.from_graph(graph)
        assert mol.properties.num_heavy_atoms == 3  # 2 C + 1 O

    def test_repr(self):
        graph = parse_smiles("CCO")
        mol = Molecule.from_graph(graph)
        rep = repr(mol)
        assert "Molecule" in rep
        assert "C2H6O" in rep

    def test_spin_multiplicity_singlet(self):
        """Neutral, non-radical molecules should be singlet."""
        graph = parse_smiles("CCO")
        mol = Molecule.from_graph(graph)
        assert mol.properties.spin_multiplicity == SpinMultiplicity.SINGLET

    def test_identifiers_after_construction(self):
        """Molecule should set formula identifier."""
        graph = parse_smiles("c1ccccc1")
        mol = Molecule.from_graph(graph)
        assert mol.identifiers.formula == "C6H6"
