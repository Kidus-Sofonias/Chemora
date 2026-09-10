"""Tests for modules with low coverage (60-79%)."""

import pytest

from chemengine.core.atoms import Atom, Isotope
from chemengine.core.bonds import Bond, BondOrder, BondTopology, BondType
from chemengine.core.enums import (
    BondStereo,
    BondType,
    ChiralTag,
    ElementSymbol,
    Hybridization,
    RadicalType,
    StereoCategory,
)
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.core.stereo import ChiralCenter
from chemengine.parsing.errors import SmilesSyntaxError

# ═══════════════════════════════════════════════════════════════════
# parsing/errors.py (65%)
# ═══════════════════════════════════════════════════════════════════

class TestSmilesErrors:
    def test_base_error_no_pos(self):
        from chemengine.parsing.errors import SmilesError
        e = SmilesError("bad input")
        assert str(e) == "bad input"
        assert e.pos is None
        assert e.context is None

    def test_base_error_with_pos(self):
        from chemengine.parsing.errors import SmilesError
        e = SmilesError("bad", pos=5)
        assert "position 5" in str(e)

    def test_base_error_with_context(self):
        from chemengine.parsing.errors import SmilesError
        e = SmilesError("bad", pos=3, context="found X")
        assert "position 3" in str(e)
        assert "found X" in str(e)

    def test_syntax_error_no_extra(self):
        from chemengine.parsing.errors import SmilesSyntaxError
        e = SmilesSyntaxError("unexpected char")
        assert "unexpected char" in str(e)
        assert e.token is None
        assert e.expected is None

    def test_syntax_error_with_token_and_expected(self):
        from chemengine.parsing.errors import SmilesSyntaxError
        e = SmilesSyntaxError("mismatch", pos=7, token="Z", expected="element")
        s = str(e)
        assert "Z" in s
        assert "element" in s
        assert "position 7" in s

    def test_syntax_error_with_context(self):
        from chemengine.parsing.errors import SmilesSyntaxError
        e = SmilesSyntaxError("err", context="extra info")
        assert "extra info" in str(e)

    def test_validation_error_no_atom_no_detail(self):
        from chemengine.parsing.errors import SmilesValidationError
        e = SmilesValidationError("valence exceeded")
        assert "valence exceeded" in str(e)
        assert e.atom is None
        assert e.detail is None

    def test_validation_error_with_atom_and_detail(self):
        from chemengine.parsing.errors import SmilesValidationError
        e = SmilesValidationError("valence exceeded", pos=2, atom="C", detail="5 bonds")
        s = str(e)
        assert "C" in s
        assert "5 bonds" in s

    def test_unclosed_bracket(self):
        from chemengine.parsing.errors import UnclosedBracketError
        e = UnclosedBracketError("unclosed", pos=4)
        assert isinstance(e, SmilesSyntaxError)
        assert "position 4" in str(e)

    def test_unmatched_ring_closure(self):
        from chemengine.parsing.errors import UnmatchedRingClosureError
        e = UnmatchedRingClosureError("ring", pos=1)
        assert isinstance(e, SmilesSyntaxError)

    def test_unmatched_branch(self):
        from chemengine.parsing.errors import UnmatchedBranchError
        e = UnmatchedBranchError("branch", pos=10)
        assert isinstance(e, SmilesSyntaxError)


# ═══════════════════════════════════════════════════════════════════
# core/bonds.py (71%)
# ═══════════════════════════════════════════════════════════════════

class TestBondValidation:
    def test_self_bond_raises(self):
        from chemengine.core.enums import BondOrder
        with pytest.raises(ValueError, match="Self-bonds"):
            Bond(atom1=0, atom2=0, order=BondOrder.SINGLE)

    def test_negative_index_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            Bond(atom1=-1, atom2=0)

    def test_negative_length_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Bond(atom1=0, atom2=1, length=-1.0)

    def test_zero_length_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Bond(atom1=0, atom2=1, length=0.0)

    def test_auto_aromatic_flag(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.AROMATIC)
        assert b.is_aromatic is True

    def test_explicit_length(self):
        b = Bond(atom1=0, atom2=1, length=1.54)
        assert b.length == 1.54


class TestBondProperties:
    def test_is_ring_bond(self):
        b = Bond(atom1=0, atom2=1, topology=BondTopology.RING)
        assert b.is_ring_bond is True
        assert b.is_chain_bond is False

    def test_is_chain_bond(self):
        b = Bond(atom1=0, atom2=1, topology=BondTopology.CHAIN)
        assert b.is_chain_bond is True

    def test_is_stereogenic(self):
        b = Bond(atom1=0, atom2=1, stereochemistry=BondStereo.E)
        assert b.is_stereogenic is True

    def test_not_stereogenic(self):
        b = Bond(atom1=0, atom2=1)
        assert b.is_stereogenic is False

    def test_is_rotatable(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.SINGLE,
                 topology=BondTopology.CHAIN, bond_type=BondType.COVALENT)
        assert b.is_rotatable is True

    def test_not_rotatable_double(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE)
        assert b.is_rotatable is False

    def test_not_rotatable_ring(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.SINGLE,
                 topology=BondTopology.RING)
        assert b.is_rotatable is False

    def test_not_rotatable_dative(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.SINGLE,
                 bond_type=BondType.DATIVE)
        assert b.is_rotatable is False

    def test_is_single(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.SINGLE)
        assert b.is_single is True

    def test_is_double(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE)
        assert b.is_double is True

    def test_is_triple(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.TRIPLE)
        assert b.is_triple is True

    def test_is_dative(self):
        b = Bond(atom1=0, atom2=1, bond_type=BondType.DATIVE)
        assert b.is_dative is True

    def test_is_hydrogen_bond(self):
        b = Bond(atom1=0, atom2=1, bond_type=BondType.HYDROGEN)
        assert b.is_hydrogen_bond is True

    def test_pi_bond_count(self):
        from chemengine.core.enums import BondOrder
        assert Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE).pi_bond_count == 1
        assert Bond(atom1=0, atom2=1, order=BondOrder.TRIPLE).pi_bond_count == 2
        assert Bond(atom1=0, atom2=1, order=BondOrder.SINGLE).pi_bond_count == 0

    def test_electron_count(self):
        from chemengine.core.enums import BondOrder
        assert Bond(atom1=0, atom2=1, order=BondOrder.SINGLE).electron_count == 2
        assert Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE).electron_count == 4
        assert Bond(atom1=0, atom2=1, order=BondOrder.AROMATIC).electron_count == 3

    def test_other_atom(self):
        b = Bond(atom1=0, atom2=1)
        assert b.other_atom(0) == 1
        assert b.other_atom(1) == 0
        with pytest.raises(ValueError):
            b.other_atom(2)

    def test_involves(self):
        b = Bond(atom1=0, atom2=1)
        assert b.involves(0) is True
        assert b.involves(1) is True
        assert b.involves(2) is False

    def test_with_order(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.SINGLE)
        b2 = b.with_order(BondOrder.DOUBLE)
        assert b2.order == BondOrder.DOUBLE
        assert b.order == BondOrder.SINGLE  # original unchanged

    def test_with_stereochemistry(self):
        b = Bond(atom1=0, atom2=1)
        b2 = b.with_stereochemistry(BondStereo.E)
        assert b2.stereochemistry == BondStereo.E
        assert b.stereochemistry == BondStereo.NONE

    def test_with_topology(self):
        b = Bond(atom1=0, atom2=1)
        b2 = b.with_topology(BondTopology.RING)
        assert b2.topology == BondTopology.RING

    def test_repr(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.SINGLE)
        assert "Bond(0-1" in repr(b)

    def test_repr_with_stereo(self):
        b = Bond(atom1=0, atom2=1, order=BondOrder.DOUBLE,
                 stereochemistry=BondStereo.E)
        r = repr(b)
        assert "stereo=" in r


# ═══════════════════════════════════════════════════════════════════
# core/charges.py (71%)
# ═══════════════════════════════════════════════════════════════════

class TestCharge:
    def test_positive(self):
        from chemengine.core.charges import Charge
        c = Charge(value=2, atom_index=0)
        assert c.is_positive is True
        assert c.is_negative is False
        assert c.is_neutral is False
        assert c.sign == 1

    def test_negative(self):
        from chemengine.core.charges import Charge
        c = Charge(value=-3, atom_index=1)
        assert c.is_negative is True
        assert c.is_positive is False
        assert c.sign == -1

    def test_neutral(self):
        from chemengine.core.charges import Charge
        c = Charge(value=0, atom_index=0)
        assert c.is_neutral is True
        assert c.sign == 0

    def test_out_of_range_raises(self):
        from chemengine.core.charges import Charge
        with pytest.raises(ValueError, match="out of reasonable range"):
            Charge(value=11, atom_index=0)

    def test_out_of_range_negative_raises(self):
        from chemengine.core.charges import Charge
        with pytest.raises(ValueError, match="out of reasonable range"):
            Charge(value=-11, atom_index=0)


class TestElectronConfiguration:
    def test_closed_shell(self):
        from chemengine.core.charges import ElectronConfiguration
        ec = ElectronConfiguration(configuration="[He]2s2", num_electrons=2,
                                   valence_electrons=2, unpaired_electrons=0)
        assert ec.is_closed_shell is True
        assert ec.is_open_shell is False

    def test_open_shell(self):
        from chemengine.core.charges import ElectronConfiguration
        ec = ElectronConfiguration(configuration="[He]2s1", num_electrons=3,
                                   valence_electrons=1, unpaired_electrons=1)
        assert ec.is_open_shell is True
        assert ec.is_closed_shell is False


class TestChargeDistribution:
    def test_neutral(self):
        from chemengine.core.charges import ChargeDistribution
        cd = ChargeDistribution(total_charge=0)
        assert cd.is_neutral is True

    def test_non_neutral(self):
        from chemengine.core.charges import ChargeDistribution
        cd = ChargeDistribution(total_charge=2)
        assert cd.is_neutral is False

    def test_is_radical(self):
        from chemengine.core.charges import ChargeDistribution
        cd = ChargeDistribution(total_radical_electrons=1)
        assert cd.is_radical_species is True

    def test_not_radical(self):
        from chemengine.core.charges import ChargeDistribution
        cd = ChargeDistribution(total_radical_electrons=0)
        assert cd.is_radical_species is False

    def test_num_charged_atoms(self):
        from chemengine.core.charges import Charge, ChargeDistribution
        charges = (Charge(value=0, atom_index=0), Charge(value=1, atom_index=1),
                   Charge(value=-1, atom_index=2))
        cd = ChargeDistribution(formal_charges=charges)
        assert cd.num_charged_atoms == 2


# ═══════════════════════════════════════════════════════════════════
# core/atoms.py (72%)
# ═══════════════════════════════════════════════════════════════════

class TestIsotopeValidation:
    def test_invalid_abundance_high(self):
        with pytest.raises(ValueError, match="Abundance"):
            Isotope(mass_number=12, exact_mass=12.0, abundance=1.5)

    def test_invalid_abundance_low(self):
        with pytest.raises(ValueError, match="Abundance"):
            Isotope(mass_number=12, exact_mass=12.0, abundance=-0.1)

    def test_mass_number_zero(self):
        with pytest.raises(ValueError, match="Mass number"):
            Isotope(mass_number=0, exact_mass=12.0)


class TestAtomExtended:
    def test_he_implicit_h_raises(self):
        with pytest.raises(ValueError, match="Helium"):
            Atom(atomic_number=2, implicit_hydrogens=1)

    def test_wildcard_symbol(self):
        a = Atom(atomic_number=0)
        assert a.symbol == "*"

    def test_wildcard_mass(self):
        a = Atom(atomic_number=0)
        assert a.mass == 0.0

    def test_wildcard_element_raises(self):
        a = Atom(atomic_number=0)
        with pytest.raises(AttributeError, match="Wildcard"):
            _ = a.element

    def test_with_charge(self):
        a = Atom(atomic_number=6)
        a2 = a.with_charge(-1)
        assert a2.formal_charge == -1
        assert a.formal_charge == 0

    def test_with_isotope(self):
        a = Atom(atomic_number=6)
        iso = Isotope(mass_number=13, exact_mass=13.003355)
        a2 = a.with_isotope(iso)
        assert a2.isotope is iso
        assert a.isotope is None

    def test_with_isotope_none(self):
        a = Atom(atomic_number=6, isotope=Isotope(mass_number=13, exact_mass=13.0))
        a2 = a.with_isotope(None)
        assert a2.isotope is None

    def test_with_stereochemistry(self):
        a = Atom(atomic_number=6)
        a2 = a.with_stereochemistry(ChiralTag.R)
        assert a2.stereochemistry == ChiralTag.R
        assert a.stereochemistry == ChiralTag.NONE

    def test_with_hybridization(self):
        a = Atom(atomic_number=6)
        a2 = a.with_hybridization(Hybridization.SP2)
        assert a2.hybridization == Hybridization.SP2

    def test_is_charged(self):
        a = Atom(atomic_number=6, formal_charge=1)
        assert a.is_charged is True

    def test_is_not_charged(self):
        a = Atom(atomic_number=6)
        assert a.is_charged is False

    def test_is_radical(self):
        a = Atom(atomic_number=6, radical_electrons=1)
        assert a.is_radical is True

    def test_is_not_radical(self):
        a = Atom(atomic_number=6)
        assert a.is_radical is False

    def test_is_chalcogen(self):
        a = Atom(atomic_number=8)
        assert a.is_chalcogen is True
        a2 = Atom(atomic_number=6)
        assert a2.is_chalcogen is False

    def test_is_pnictogen(self):
        a = Atom(atomic_number=7)
        assert a.is_pnictogen is True

    def test_is_hydrogen(self):
        a = Atom(atomic_number=1)
        assert a.is_hydrogen is True

    def test_is_carbon(self):
        a = Atom(atomic_number=6)
        assert a.is_carbon is True

    def test_is_nitrogen(self):
        a = Atom(atomic_number=7)
        assert a.is_nitrogen is True

    def test_is_oxygen(self):
        a = Atom(atomic_number=8)
        assert a.is_oxygen is True

    def test_is_sulfur(self):
        a = Atom(atomic_number=16)
        assert a.is_sulfur is True

    def test_is_phosphorus(self):
        a = Atom(atomic_number=15)
        assert a.is_phosphorus is True

    def test_element_symbol_enum(self):
        a = Atom(atomic_number=6)
        assert a.element_symbol == ElementSymbol.C

    def test_isotope_mass_used(self):
        iso = Isotope(mass_number=13, exact_mass=13.003355)
        a = Atom(atomic_number=6, isotope=iso)
        assert a.mass == 13.003355

    def test_symbol_unknown_element(self):
        """Atom with invalid Z should return '?' for symbol."""
        a = Atom(atomic_number=6)
        # Force an invalid state by directly checking the fallback path
        # We can test the property by mocking a broken element lookup
        from unittest.mock import PropertyMock, patch
        with patch.object(type(a), 'element', new_callable=PropertyMock, side_effect=KeyError("bad")):
            assert a.symbol == "?"

    def test_repr_with_charge_and_radical(self):
        a = Atom(atomic_number=6, formal_charge=-1, radical_electrons=1)
        r = repr(a)
        assert "C" in r
        assert "charge=-1" in r
        assert "radical=1" in r

    def test_repr_with_stereo(self):
        a = Atom(atomic_number=6, stereochemistry=ChiralTag.R)
        assert "stereo=R" in repr(a)

    def test_repr_with_hybridization(self):
        a = Atom(atomic_number=6, hybridization=Hybridization.SP2)
        assert "hyb=sp2" in repr(a)

    def test_repr_with_isotope(self):
        a = Atom(atomic_number=6, isotope=Isotope(mass_number=13, exact_mass=13.0))
        assert "iso=13" in repr(a)

    def test_invalid_atomic_number_raises(self):
        with pytest.raises(ValueError, match="Atomic number"):
            Atom(atomic_number=119)

    def test_invalid_charge_raises(self):
        with pytest.raises(ValueError, match="Formal charge"):
            Atom(atomic_number=6, formal_charge=11)

    def test_invalid_radical_raises(self):
        with pytest.raises(ValueError, match="Radical electrons"):
            Atom(atomic_number=6, radical_electrons=3)

    def test_negative_implicit_h_raises(self):
        with pytest.raises(ValueError, match="Implicit hydrogens"):
            Atom(atomic_number=6, implicit_hydrogens=-1)

    def test_radical_type_diradical(self):
        a = Atom(atomic_number=6, radical_electrons=2)
        assert a.radical_type == RadicalType.DIRADICAL

    def test_radical_type_none(self):
        a = Atom(atomic_number=6)
        assert a.radical_type == RadicalType.NONE


# ═══════════════════════════════════════════════════════════════════
# parsing/canonical.py (71%)
# ═══════════════════════════════════════════════════════════════════

class TestCanonicalSmiles:
    def test_canonical_deterministic(self):
        from chemengine.parsing.canonical import canonical_smiles
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        cs1 = canonical_smiles(g)
        cs2 = canonical_smiles(g)
        assert cs1 == cs2

    def test_canonical_empty_graph(self):
        from chemengine.parsing.canonical import _compute_canonical_order
        builder = MolecularGraphBuilder()
        g = builder.build()
        order = _compute_canonical_order(g)
        assert order == []

    def test_canonical_single_atom(self):
        from chemengine.parsing.canonical import canonical_smiles
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        g = builder.build()
        cs = canonical_smiles(g)
        assert len(cs) > 0

    def test_is_canonical(self):
        from chemengine.parsing.canonical import canonical_smiles, is_canonical
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        cs = canonical_smiles(g)
        assert is_canonical(g, cs) is True

    def test_is_canonical_wrong_smiles(self):
        from chemengine.parsing.canonical import is_canonical
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert is_canonical(g, "C=O") is False

    def test_reindex_preserves_bonds(self):
        from chemengine.parsing.canonical import _compute_canonical_order, _reindex_graph
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        order = _compute_canonical_order(g)
        g2 = _reindex_graph(g, order)
        assert g2.num_atoms == g.num_atoms
        assert g2.num_bonds == g.num_bonds


# ═══════════════════════════════════════════════════════════════════
# parsing/alias.py (69%)
# ═══════════════════════════════════════════════════════════════════

class TestAliasResolver:
    def test_resolve_water(self):
        from chemengine.parsing.alias import resolve_alias
        assert resolve_alias("water") == "O"

    def test_resolve_case_insensitive(self):
        from chemengine.parsing.alias import resolve_alias
        assert resolve_alias("Water") == "O"
        assert resolve_alias("  WATER  ") == "O"

    def test_resolve_unknown(self):
        from chemengine.parsing.alias import resolve_alias
        assert resolve_alias("xyznotreal") is None

    def test_resolve_to_graph(self):
        from chemengine.parsing.alias import resolve_alias_to_graph
        g = resolve_alias_to_graph("water")
        assert g is not None
        assert g.num_atoms == 3  # H2O has 3 atoms (O, H, H)

    def test_resolve_to_graph_unknown(self):
        from chemengine.parsing.alias import resolve_alias_to_graph
        assert resolve_alias_to_graph("xyznotreal") is None


class TestAliasParser:
    def test_parse(self):
        from chemengine.parsing.alias import AliasParser
        parser = AliasParser()
        g = parser.parse("water")
        assert g.num_atoms == 3  # H2O has 3 atoms (O, H, H)

    def test_parse_unknown_raises(self):
        from chemengine.parsing.alias import AliasParser
        parser = AliasParser()
        with pytest.raises(ValueError, match="Unknown chemical name"):
            parser.parse("xyznotreal")

    def test_serialize_raises(self):
        from chemengine.parsing.alias import AliasParser
        parser = AliasParser()
        with pytest.raises(NotImplementedError):
            parser.serialize(None)

    def test_register_alias_parser(self):
        from chemengine.core.registry import AlgorithmRegistry
        reg = AlgorithmRegistry()
        from chemengine.parsing.alias import register_alias_parser
        register_alias_parser(reg)
        assert reg.count >= 1


# ═══════════════════════════════════════════════════════════════════
# generation/filtering.py (78%)
# ═══════════════════════════════════════════════════════════════════

class TestIsomerFilter:
    def _get_isomers(self):
        from chemengine.generation.constitutional import generate_alkane_isomers
        return generate_alkane_isomers(4)  # C4H10: butane + isobutane

    def test_filter_by_formula(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_formula("C4H10")
        result = filt.apply(isomers)
        assert len(result) == 2

    def test_filter_by_max_mass(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_max_mass(50.0)
        result = filt.apply(isomers)
        assert all(g.exact_mass <= 50.0 for g in result)

    def test_filter_by_min_mass(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_min_mass(50.0)
        result = filt.apply(isomers)
        assert all(g.exact_mass >= 50.0 for g in result)

    def test_filter_by_mass_range(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_mass_range(50.0, 60.0)
        result = filt.apply(isomers)
        assert all(50.0 <= g.exact_mass <= 60.0 for g in result)

    def test_filter_by_min_heavy_atoms(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_min_heavy_atoms(4)
        result = filt.apply(isomers)
        assert len(result) == 2

    def test_filter_by_max_heavy_atoms(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_max_heavy_atoms(3)
        result = filt.apply(isomers)
        assert len(result) == 0

    def test_filter_by_has_element(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_has_element(6)
        result = filt.apply(isomers)
        assert len(result) == 2

    def test_filter_by_num_bonds(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        # Both butane and isobutane have the same total bond count (13)
        bonds = isomers[0].num_bonds
        filt = IsomerFilter().by_num_bonds(min_bonds=bonds, max_bonds=bonds)
        result = filt.apply(isomers)
        assert len(result) == 2

    def test_filter_by_custom(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_custom(lambda g: g.num_heavy_atoms == 4)
        result = filt.apply(isomers)
        assert len(result) == 2

    def test_filter_compose(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = (IsomerFilter()
                .by_formula("C4H10")
                .by_max_heavy_atoms(4))
        result = filt.apply(isomers)
        assert len(result) == 2

    def test_filter_repr(self):
        from chemengine.generation.filtering import IsomerFilter
        filt = IsomerFilter().by_formula("X")
        assert "1 predicates" in repr(filt)

    def test_apply_lazy(self):
        from chemengine.generation.filtering import IsomerFilter
        isomers = self._get_isomers()
        filt = IsomerFilter().by_formula("C4H10")
        result = list(filt.apply_lazy(iter(isomers)))
        assert len(result) == 2

    def test_lazy_alkane_isomers_small(self):
        from chemengine.generation.filtering import lazy_alkane_isomers
        isomers = list(lazy_alkane_isomers(4))
        assert len(isomers) == 2

    def test_lazy_alkane_isomers_large(self):
        from chemengine.generation.filtering import lazy_alkane_isomers
        isomers = list(lazy_alkane_isomers(7))
        assert len(isomers) > 0

    def test_lazy_alkane_invalid(self):
        from chemengine.generation.filtering import lazy_alkane_isomers
        with pytest.raises(ValueError, match="C1-C8"):
            list(lazy_alkane_isomers(0))

    def test_lazy_alkane_too_large(self):
        from chemengine.generation.filtering import lazy_alkane_isomers
        with pytest.raises(ValueError, match="C1-C8"):
            list(lazy_alkane_isomers(9))

    def test_lazy_filtered_isomers_max_results(self):
        from chemengine.generation.filtering import IsomerFilter, lazy_filtered_isomers
        isomers = self._get_isomers()
        filt = IsomerFilter().by_formula("C4H10")
        result = list(lazy_filtered_isomers(iter(isomers), filt, max_results=1))
        assert len(result) == 1

    def test_count_isomers_lazy(self):
        from chemengine.generation.filtering import count_isomers_lazy
        isomers = self._get_isomers()
        count = count_isomers_lazy(iter(isomers))
        assert count == 2

    def test_count_isomers_lazy_with_filter(self):
        from chemengine.generation.filtering import IsomerFilter, count_isomers_lazy
        isomers = self._get_isomers()
        filt = IsomerFilter().by_formula("C4H10")
        count = count_isomers_lazy(iter(isomers), filt)
        assert count == 2


# ═══════════════════════════════════════════════════════════════════
# generation/stereoisomers.py (78%)
# ═══════════════════════════════════════════════════════════════════

class TestStereoisomerEnumeration:
    def test_no_stereocenters(self):
        from chemengine.generation.stereoisomers import enumerate_stereoisomers
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCC")
        isomers = enumerate_stereoisomers(g)
        assert len(isomers) == 1  # no stereocenters → 1 isomer

    def test_one_tetrahedral_center(self):
        from chemengine.generation.stereoisomers import enumerate_stereoisomers
        # Build a chiral center: C with H, Cl, Br, F
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        h = builder.add_atom(atomic_number=1)
        cl = builder.add_atom(atomic_number=17)
        br = builder.add_atom(atomic_number=35)
        f = builder.add_atom(atomic_number=9)
        builder.add_bond(c, h, BondOrder.SINGLE)
        builder.add_bond(c, cl, BondOrder.SINGLE)
        builder.add_bond(c, br, BondOrder.SINGLE)
        builder.add_bond(c, f, BondOrder.SINGLE)
        g = builder.build()
        isomers = enumerate_stereoisomers(g)
        assert len(isomers) == 2  # R and S

    def test_benzene_no_stereoisomers(self):
        from chemengine.generation.stereoisomers import enumerate_stereoisomers
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("c1ccccc1")
        isomers = enumerate_stereoisomers(g)
        assert len(isomers) == 1


# ═══════════════════════════════════════════════════════════════════
# core/graph.py (68%) — cover untested methods
# ═══════════════════════════════════════════════════════════════════

class TestMolecularGraphExtended:
    def test_get_degree(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        # Parser adds explicit H: C has 4 neighbors (C + 3H), O has 2 neighbors (C + implicit H)
        assert g.get_degree(0) == 4  # terminal C (bonded to C + 3H)
        assert g.get_degree(2) == 2  # oxygen (bonded to C + H)

    def test_get_bond(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        b = g.get_bond(0, 1)
        assert b is not None
        b2 = g.get_bond(0, 2)
        assert b2 is None

    def test_get_bond_reverse(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        b = g.get_bond(1, 0)
        assert b is not None

    def test_num_heavy_atoms(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert g.num_heavy_atoms == 3

    def test_molecular_formula(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert g.molecular_formula == "C2H6O"

    def test_graph_hash_deterministic(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        h1 = g.graph_hash
        h2 = g.graph_hash
        assert h1 == h2

    def test_graph_properties(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert g.properties == frozenset()

    def test_set_property(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        builder.set_property("key", "val")
        g = builder.build()
        assert ("key", "val") in g.properties

    def test_add_conformer(self):
        from chemengine.core.geometry import Conformer, Coordinate3D
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        conf = Conformer(id=0, coordinates=(Coordinate3D(0, 0, 0),))
        builder.add_conformer(conf)
        g = builder.build()
        assert len(g.conformers) == 1

    def test_add_ring(self):
        from chemengine.core.substructure import Ring
        builder = MolecularGraphBuilder()
        idx = builder.add_atom(atomic_number=6)
        ring = Ring(atom_indices=(idx,))
        builder.add_ring(ring)
        g = builder.build()
        assert len(g.rings) == 1

    def test_add_chiral_center(self):
        center = ChiralCenter(category=StereoCategory.TETRAHEDRAL,
                              atom_index=0, chiral_tag=ChiralTag.R)
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        builder.add_chiral_center(center)
        g = builder.build()
        assert len(g.stereo_config.centers) == 1

    def test_set_coordinates_2d(self):
        from chemengine.core.geometry import Coordinate2D
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        builder.set_coordinates_2d([Coordinate2D(0, 0)])
        g = builder.build()
        assert len(g.coordinates_2d) == 1

    def test_set_coordinates_3d(self):
        from chemengine.core.geometry import Coordinate3D
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        builder.set_coordinates_3d([Coordinate3D(0, 0, 0)])
        g = builder.build()
        assert len(g.coordinates_3d) == 1

    def test_builder_from_graph(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        g2 = MolecularGraphBuilder.from_graph(g).build()
        assert g2.num_atoms == g.num_atoms

    def test_exact_mass(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert g.exact_mass > 0

    def test_molecular_weight(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert g.molecular_weight > 0

    def test_is_connected_true(self):
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert g.is_connected is True

    def test_is_connected_false(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        builder.add_atom(atomic_number=6)
        g = builder.build()
        assert g.is_connected is False
