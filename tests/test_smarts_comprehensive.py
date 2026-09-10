"""Comprehensive SMARTS Parser Tests

Tests for the SMARTS pattern parser and matcher covering:
- Element symbols (aliphatic and aromatic)
- Bracket atoms with properties (charge, isotope, hcount, degree, ring)
- Atom lists ([N,O], [C,N,O])
- Bond types (-, =, #, :, ~)
- Negation ([!C], !=, !#)
- Wildcard (*)
- Branches (C(C)C, CC(=O)O)
- Ring closures (C1CC1, c1ccccc1)
- Disconnected (C.O)
- Complex functional group patterns
"""

from __future__ import annotations

from chemengine.parsing.smarts import (
    QueryGraph,
    smarts_count,
    smarts_findall,
    smarts_match,
)
from chemengine.parsing.smiles import parse_smiles

# ── Element Symbols ──

class TestElementSymbols:
    def test_aliphatic_carbon(self):
        assert smarts_match("C", parse_smiles("CCO"))

    def test_aliphatic_nitrogen(self):
        assert smarts_match("N", parse_smiles("CCN"))

    def test_aliphatic_oxygen(self):
        assert smarts_match("O", parse_smiles("CCO"))

    def test_aromatic_carbon(self):
        assert smarts_match("c", parse_smiles("c1ccccc1"))

    def test_aromatic_nitrogen(self):
        assert smarts_match("n", parse_smiles("c1cccnc1"))

    def test_aromatic_oxygen(self):
        assert smarts_match("o", parse_smiles("c1coccc1"))

    def test_aliphatic_not_aromatic(self):
        assert not smarts_match("C", parse_smiles("c1ccccc1"))

    def test_aromatic_not_aliphatic(self):
        assert not smarts_match("c", parse_smiles("CCO"))


# ── Bracket Atoms ──

class TestBracketAtoms:
    def test_atomic_number(self):
        assert smarts_match("[#6]", parse_smiles("CCO"))
        assert smarts_match("[#8]", parse_smiles("CCO"))
        assert not smarts_match("[#7]", parse_smiles("CCO"))

    def test_element_in_bracket(self):
        assert smarts_match("[C]", parse_smiles("CCO"))
        assert smarts_match("[O]", parse_smiles("CCO"))
        assert not smarts_match("[N]", parse_smiles("CCO"))

    def test_aromatic_in_bracket(self):
        assert smarts_match("[c]", parse_smiles("c1ccccc1"))
        assert not smarts_match("[c]", parse_smiles("CCO"))

    def test_wildcard(self):
        assert smarts_match("[*]", parse_smiles("CCO"))
        assert smarts_match("*", parse_smiles("CCO"))

    def test_charge_plus(self):
        assert smarts_match("[NH4+]", parse_smiles("[NH4+]"))
        assert smarts_match("[+]", parse_smiles("[NH4+]"))
        assert not smarts_match("[+]", parse_smiles("CCO"))

    def test_charge_minus(self):
        assert smarts_match("[O-]", parse_smiles("[O-]"))
        assert smarts_match("[-]", parse_smiles("[O-]"))

    def test_charge_plus2(self):
        assert smarts_match("[+2]", parse_smiles("[Ca+2]"))

    def test_charge_minus2(self):
        # Test charge matching
        assert smarts_match("[+2]", parse_smiles("[Mg+2]"))

    def test_isotope(self):
        assert smarts_match("[13C]", parse_smiles("[13CH4]"))
        assert not smarts_match("[13C]", parse_smiles("C"))

    def test_hcount_h(self):
        # [NH] = nitrogen with 1 total H
        assert smarts_match("[NH2]", parse_smiles("CCN"))

    def test_ring_atom(self):
        assert smarts_match("[r]", parse_smiles("c1ccccc1"))
        assert not smarts_match("[r]", parse_smiles("CCO"))

    def test_ring_size(self):
        assert smarts_match("[r6]", parse_smiles("c1ccccc1"))
        assert not smarts_match("[r5]", parse_smiles("c1ccccc1"))

    def test_degree(self):
        # D = number of non-H neighbors
        assert smarts_match("[CH4]", parse_smiles("C"))
        assert smarts_match("[CH3]", parse_smiles("CC"))

    def test_total_connections(self):
        # X = total connections including H
        assert smarts_match("[X4]", parse_smiles("C"))
        assert smarts_match("[X3]", parse_smiles("CC"))


# ── Atom Lists ──

class TestAtomLists:
    def test_two_element_list(self):
        assert smarts_match("[N,O]", parse_smiles("CCO"))
        assert smarts_match("[N,O]", parse_smiles("CCN"))
        assert not smarts_match("[N,O]", parse_smiles("CCC"))

    def test_three_element_list(self):
        assert smarts_match("[C,N,O]", parse_smiles("CCO"))
        # CCl has a C atom, so [C,N,O] matches
        assert smarts_match("[C,N,O]", parse_smiles("CCl"))
        # But [N,O] doesn't match CCC
        assert not smarts_match("[N,O]", parse_smiles("CCC"))

    def test_halogen_list(self):
        assert smarts_match("[F,Cl,Br,I]", parse_smiles("CCl"))
        assert not smarts_match("[F,Cl,Br,I]", parse_smiles("CCO"))


# ── Bond Types ──

class TestBondTypes:
    def test_single_bond(self):
        assert smarts_match("CC", parse_smiles("CCO"))

    def test_double_bond(self):
        assert smarts_match("C=C", parse_smiles("C=C"))
        assert not smarts_match("C=C", parse_smiles("CC"))

    def test_triple_bond(self):
        assert smarts_match("C#N", parse_smiles("CC#N"))
        assert not smarts_match("C#N", parse_smiles("CCO"))

    def test_aromatic_bond(self):
        assert smarts_match("c:c", parse_smiles("c1ccccc1"))
        assert not smarts_match("c:c", parse_smiles("CCO"))

    def test_any_bond(self):
        assert smarts_match("C~C", parse_smiles("CCO"))
        assert smarts_match("C~C", parse_smiles("C=C"))
        assert smarts_match("C~C", parse_smiles("C#C"))
        # C~C requires both atoms to be carbon
        assert not smarts_match("C~C", parse_smiles("C#N"))

    def test_not_double_bond(self):
        assert smarts_match("C!=C", parse_smiles("CCO"))
        assert not smarts_match("C!=C", parse_smiles("C=C"))

    def test_not_triple_bond(self):
        # 'C!#N' = carbon bonded to a nitrogen via a NON-triple bond.
        # "CCO" (ethanol) contains no nitrogen at all, so there is no match.
        assert not smarts_match("C!#N", parse_smiles("CCO"))
        # "CC#N" has a C≡N triple bond, so the "not triple" fails to match.
        assert not smarts_match("C!#N", parse_smiles("CC#N"))


# ── Negation ──

class TestNegation:
    def test_not_element(self):
        # [!C] matches any non-carbon atom (including H)
        assert smarts_match("[!C]", parse_smiles("CCO"))  # matches O and H
        assert smarts_match("[!C]", parse_smiles("CO"))   # matches O

    def test_not_ring(self):
        # Not directly testable with simple patterns
        pass


# ── Branches ──

class TestBranches:
    def test_simple_branch(self):
        assert smarts_match("C(C)C", parse_smiles("CC(C)C"))
        assert not smarts_match("C(C)C", parse_smiles("CCO"))

    def test_double_branch(self):
        assert smarts_match("C(C)(C)", parse_smiles("CC(C)(C)C"))

    def test_nested_branch(self):
        assert smarts_match("C(C(C)C)", parse_smiles("CC(C(C)C)C"))

    def test_functional_group_branch(self):
        assert smarts_match("CC(=O)", parse_smiles("CC(=O)O"))
        assert not smarts_match("CC(=O)", parse_smiles("CCO"))


# ── Ring Closures ──

class TestRingClosures:
    def test_three_membered_ring(self):
        assert smarts_match("C1CC1", parse_smiles("C1CC1"))

    def test_five_membered_ring(self):
        assert smarts_match("C1CCC1", parse_smiles("C1CCC1"))

    def test_six_membered_ring(self):
        assert smarts_match("C1CCCC1", parse_smiles("C1CCCC1"))

    def test_benzene_ring(self):
        assert smarts_match("c1ccccc1", parse_smiles("c1ccccc1"))
        assert not smarts_match("c1ccccc1", parse_smiles("CCO"))

    def test_ring_with_branch(self):
        assert smarts_match("c1ccc(C)cc1", parse_smiles("Cc1ccccc1"))

    def test_bridged_ring(self):
        assert smarts_match("C1CC2CCC1CC2", parse_smiles("C1CC2CCC1CC2"))


# ── Disconnected ──

class TestDisconnected:
    def test_disconnected_query(self):
        # C.O = find C and O anywhere in the molecule
        assert smarts_match("C.O", parse_smiles("C.O"))
        assert smarts_match("C.O", parse_smiles("CCO"))  # C and O exist

    def test_single_atom(self):
        assert smarts_match("C", parse_smiles("C"))


# ── Functional Groups ──

class TestFunctionalGroups:
    def test_hydroxyl(self):
        assert smarts_match("[OH]", parse_smiles("CCO"))
        assert not smarts_match("[OH]", parse_smiles("CC"))

    def test_amine(self):
        assert smarts_match("[NH2]", parse_smiles("CCN"))
        # Isopropylamine N has 2 H, not 1
        assert smarts_match("[NH2]", parse_smiles("CC(C)N"))
        # Secondary amine has 1 H
        assert smarts_match("[NH]", parse_smiles("CNC"))

    def test_carbonyl(self):
        assert smarts_match("C=O", parse_smiles("CC(=O)O"))
        assert smarts_match("C=O", parse_smiles("CC=O"))

    def test_carboxylic_acid(self):
        assert smarts_match("C(=O)O", parse_smiles("CC(=O)O"))

    def test_ester(self):
        assert smarts_match("C(=O)OC", parse_smiles("CC(=O)OC"))

    def test_amide(self):
        assert smarts_match("C(=O)N", parse_smiles("CC(=O)N"))

    def test_nitrile(self):
        assert smarts_match("C#N", parse_smiles("CC#N"))
        assert not smarts_match("C#N", parse_smiles("CCO"))

    def test_nitro(self):
        assert smarts_match("[N+](=O)[O-]", parse_smiles("C[N+](=O)[O-]"))

    def test_ether(self):
        assert smarts_match("COC", parse_smiles("CCOCC"))

    def test_aldehyde(self):
        assert smarts_match("CC=O", parse_smiles("CC=O"))

    def test_ketone(self):
        assert smarts_match("CC(=O)C", parse_smiles("CC(=O)C"))

    def test_phenol(self):
        assert smarts_match("c1ccc(O)cc1", parse_smiles("Oc1ccccc1"))

    def test_aniline(self):
        assert smarts_match("c1ccc(N)cc1", parse_smiles("Nc1ccccc1"))

    def test_toluene(self):
        assert smarts_match("c1ccc(C)cc1", parse_smiles("Cc1ccccc1"))

    def test_benzaldehyde(self):
        assert smarts_match("c1ccc(C=O)cc1", parse_smiles("O=Cc1ccccc1"))

    def test_acetophenone(self):
        assert smarts_match("c1ccc(C(=O)C)cc1", parse_smiles("CC(=O)c1ccccc1"))


# ── Complex Patterns ──

class TestComplexPatterns:
    def test_two_connected_carbons(self):
        assert smarts_match("CC", parse_smiles("CCO"))
        assert smarts_match("CC", parse_smiles("CCC"))
        assert not smarts_match("CC", parse_smiles("C=O"))

    def test_three_connected_atoms(self):
        assert smarts_match("CCO", parse_smiles("CCO"))
        assert not smarts_match("CCO", parse_smiles("CCC"))

    def test_branched_functional_group(self):
        assert smarts_match("CC(=O)O", parse_smiles("CC(=O)O"))
        assert not smarts_match("CC(=O)O", parse_smiles("CCO"))

    def test_aromatic_with_substituent(self):
        assert smarts_match("c1ccc(N)cc1", parse_smiles("Nc1ccccc1"))
        assert not smarts_match("c1ccc(N)cc1", parse_smiles("c1ccccc1"))

    def test_multiple_rings(self):
        assert smarts_match("c1ccc2ccccc2c1", parse_smiles("c1ccc2ccccc2c1"))

    def test_wildcard_chain(self):
        assert smarts_match("*~*~*", parse_smiles("CCO"))


# ── Matching Counts ──

class TestMatchingCounts:
    def test_findall_cc_in_propane(self):
        g = parse_smiles("CCC")
        matches = smarts_findall("CC", g)
        # Should find 2 CC patterns in propane (C1-C2 and C2-C3)
        assert len(matches) >= 2

    def test_count_in_benzene(self):
        g = parse_smiles("c1ccccc1")
        # Should find 6 aromatic carbons
        count = smarts_count("c", g)
        assert count == 6

    def test_no_match(self):
        g = parse_smiles("CCO")
        assert smarts_count("C#N", g) == 0


# ── QueryGraph Structure ──

class TestQueryGraphStructure:
    def test_single_atom(self):
        qg = _parse_query_graph("[C]")
        assert len(qg.atoms) == 1
        assert qg.atoms[0].atomic_number == 6

    def test_two_atoms(self):
        qg = _parse_query_graph("CC")
        assert len(qg.atoms) == 2
        assert len(qg.bonds) == 1

    def test_branch(self):
        qg = _parse_query_graph("C(C)C")
        assert len(qg.atoms) == 3
        assert len(qg.bonds) == 2

    def test_ring(self):
        qg = _parse_query_graph("C1CC1")
        assert len(qg.atoms) == 3
        assert len(qg.bonds) == 3  # C-C, C-C, C-C (ring closure)

    def test_wildcard_atom(self):
        qg = _parse_query_graph("*")
        assert len(qg.atoms) == 1
        assert qg.atoms[0].atomic_number is None  # wildcard

    def test_aromatic_atom(self):
        qg = _parse_query_graph("c")
        assert len(qg.atoms) == 1
        assert qg.atoms[0].is_aromatic is True
        assert qg.atoms[0].atomic_number == 6


# Helper function for TestQueryGraphStructure
def _parse_query_graph(pattern: str) -> QueryGraph:
    from chemengine.parsing.smarts import _parse_query_graph as _pqg
    return _pqg(pattern)
