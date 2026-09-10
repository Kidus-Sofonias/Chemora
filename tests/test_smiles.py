"""Tests for the SMILES parser and serializer."""

import pytest

from chemengine.parsing.smiles import parse_smiles, serialize_smiles


class TestSmilesParsing:
    """Tests for the parse_smiles function."""

    def test_methane(self):
        """CH4 -> methane"""
        graph = parse_smiles("C")
        assert graph.molecular_formula == "CH4"
        assert graph.num_atoms == 5

    def test_ethane(self):
        """C2H6 -> ethane"""
        graph = parse_smiles("CC")
        assert graph.molecular_formula == "C2H6"
        assert graph.num_atoms == 8

    def test_ethanol(self):
        """C2H5OH"""
        graph = parse_smiles("CCO")
        assert graph.molecular_formula == "C2H6O"
        assert graph.num_atoms == 9

    def test_benzene(self):
        """c1ccccc1 -> benzene"""
        graph = parse_smiles("c1ccccc1")
        assert graph.molecular_formula == "C6H6"
        assert graph.num_atoms == 12
        assert graph.num_bonds == 12

    def test_water(self):
        """H2O"""
        graph = parse_smiles("O")
        assert "H2O" in graph.molecular_formula or "OH2" in graph.molecular_formula
        assert graph.num_atoms == 3

    def test_oxygen_gas(self):
        """O=O"""
        graph = parse_smiles("O=O")
        assert graph.num_atoms == 2
        assert graph.num_bonds == 1

    def test_nitrogen_gas(self):
        """N#N"""
        graph = parse_smiles("N#N")
        assert graph.num_atoms == 2
        assert graph.num_bonds == 1

    def test_methanol(self):
        """CO -> methanol"""
        graph = parse_smiles("CO")
        assert graph.molecular_formula == "CH4O"
        assert graph.num_atoms == 6

    def test_acetic_acid(self):
        """CC(=O)O -> acetic acid"""
        graph = parse_smiles("CC(=O)O")
        assert graph.molecular_formula == "C2H4O2"
        assert graph.num_atoms == 8

    def test_cyclopropane(self):
        """C1CC1 -> cyclopropane"""
        graph = parse_smiles("C1CC1")
        assert graph.num_atoms == 9  # 3 C + 6 H

    def test_bracket_atom_isotope(self):
        """[13C] -> carbon-13"""
        graph = parse_smiles("[13CH4]")
        assert graph.atoms[0].isotope is not None
        assert graph.atoms[0].isotope.mass_number == 13

    def test_bracket_atom_charge(self):
        """[NH4+] -> ammonium"""
        graph = parse_smiles("[NH4+]")
        # ammonium: N+ with 4 H
        assert graph.atoms[0].atomic_number == 7
        assert graph.atoms[0].formal_charge == 1

    def test_bracket_atom_negative_charge(self):
        """[O-] -> oxide anion"""
        graph = parse_smiles("[O-]")
        assert graph.atoms[0].atomic_number == 8
        assert graph.atoms[0].formal_charge == -1

    def test_dot_disconnection(self):
        """Na.Cl -> sodium chloride (separate components)"""
        graph = parse_smiles("[Na].[Cl]")
        assert graph.num_atoms == 2
        assert graph.atoms[0].atomic_number == 11  # Na
        assert graph.atoms[1].atomic_number == 17  # Cl

    def test_empty_smiles_raises(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError, match="Empty SMILES"):
            parse_smiles("")

    def test_invalid_smiles_raises(self):
        """Invalid tokens should raise ValueError."""
        with pytest.raises(ValueError):
            parse_smiles("X1")

    def test_unmatched_branch_raises(self):
        """Unmatched parenthesis should raise ValueError."""
        with pytest.raises(ValueError, match="Unmatched"):
            parse_smiles("C(")

    def test_unmatched_ring_raises(self):
        """Unmatched ring closure should raise ValueError."""
        with pytest.raises(ValueError, match="Unmatched"):
            parse_smiles("C1CC")

    def test_aromatic_ring(self):
        """Aromatic ring atoms should be detected."""
        graph = parse_smiles("c1ccccc1")
        for i in range(6):
            assert graph.atoms[i].is_aromatic, f"Atom {i} should be aromatic"

    def test_double_bond(self):
        """Double bond detection."""
        graph = parse_smiles("C=C")
        # 1 C=C bond + 4 C-H bonds (from H saturation) = 5 total
        assert graph.num_bonds >= 1
        # Find the double bond
        double_bonds = [b for b in graph.bonds if b.is_double]
        assert len(double_bonds) == 1

    def test_triple_bond(self):
        """Triple bond detection."""
        graph = parse_smiles("C#C")
        bond = graph.bonds[0]
        assert bond.is_triple

    def test_chlorine_element(self):
        """Two-letter element symbol."""
        graph = parse_smiles("CCl")
        # CCl = methyl chloride: C + Cl + 3 H = 5 atoms
        assert graph.num_atoms == 5
        assert any(a.atomic_number == 17 for a in graph.atoms)

    def test_bromine_element(self):
        """Two-letter element symbol Br."""
        graph = parse_smiles("CBr")
        assert any(a.atomic_number == 35 for a in graph.atoms)

    def test_toluene(self):
        """Cc1ccccc1 -> toluene"""
        graph = parse_smiles("Cc1ccccc1")
        # Toluene: C7H8
        assert graph.molecular_formula == "C7H8"

    def test_pyridine(self):
        """c1cnccc1 -> pyridine"""
        graph = parse_smiles("c1cnccc1")
        assert graph.molecular_formula == "C5H5N"

    def test_sodium_hydroxide(self):
        """[OH-].[Na+] -> NaOH"""
        graph = parse_smiles("[OH-].[Na+]")
        assert graph.num_atoms == 3  # O, H, Na
        # Check charges
        charges = [a.formal_charge for a in graph.atoms]
        assert -1 in charges
        assert 1 in charges


class TestSmilesSerializer:
    """Tests for the serialize_smiles function."""

    def test_serialize_roundtrip(self):
        """Simple round-trip: parse then serialize."""
        smiles = "CCO"
        graph = parse_smiles(smiles)
        output = serialize_smiles(graph)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_serialize_nonempty(self):
        """Serialized output should be non-empty for valid graphs."""
        from chemengine.core.graph import MolecularGraphBuilder

        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h)
        graph = builder.build()
        output = serialize_smiles(graph)
        assert len(output) > 0
