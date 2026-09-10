"""Tests for VF2 subgraph isomorphism and SMARTS pattern matching."""

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.detection.substructure import (
    count_subgraph_matches,
    find_subgraph_matches,
    has_subgraph_match,
    maximum_common_substructure,
)
from chemengine.parsing.smarts import parse_smarts, smarts_count, smarts_findall, smarts_match

# ── Fixtures ──

@pytest.fixture
def ethanol_graph() -> MolecularGraph:
    """CCO — ethanol."""
    from chemengine.parsing.smiles import parse_smiles
    return parse_smiles("CCO")


@pytest.fixture
def propane_graph() -> MolecularGraph:
    """CCC — propane."""
    builder = MolecularGraphBuilder()
    atoms = [builder.add_atom(atomic_number=6) for _ in range(3)]
    builder.add_bond(atoms[0], atoms[1], BondOrder.SINGLE)
    builder.add_bond(atoms[1], atoms[2], BondOrder.SINGLE)
    for a in atoms:
        for _ in range(2):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(a, h, BondOrder.SINGLE)
    # Terminal H
    h1 = builder.add_atom(atomic_number=1)
    builder.add_bond(atoms[0], h1, BondOrder.SINGLE)
    h2 = builder.add_atom(atomic_number=1)
    builder.add_bond(atoms[2], h2, BondOrder.SINGLE)
    return builder.build()


@pytest.fixture
def cc_double_graph() -> MolecularGraph:
    """C=C — ethylene."""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6)
    c2 = builder.add_atom(atomic_number=6)
    builder.add_bond(c1, c2, BondOrder.DOUBLE)
    for c in (c1, c2):
        for _ in range(2):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


@pytest.fixture
def query_carbon() -> MolecularGraph:
    """Single carbon atom query."""
    return MolecularGraph(atoms=(type('Atom', (), {'atomic_number': 6, 'is_aromatic': False, 'formal_charge': 0, 'symbol': 'C', 'implicit_hydrogens': None, 'radical_electrons': 0, 'stereochemistry': None, 'element': None, 'mass': 12.0, 'max_valence': 4, 'default_valence': 4, 'element_symbol': 'C', 'isotope': None, 'hybridization': None, 'atom_mapping': None, 'properties': frozenset()})(),), bonds=())


# ── VF2 Subgraph Isomorphism Tests ──

class TestVF2SubgraphMatch:
    """Tests for VF2 subgraph isomorphism."""

    def test_single_atom_match(self, propane_graph):
        """A single carbon should match propane (has 3 carbons)."""
        query = MolecularGraph(
            atoms=(propane_graph.atoms[0],),
            bonds=(),
        )
        assert has_subgraph_match(propane_graph, query)

    def test_no_match_wrong_element(self, propane_graph):
        """Oxygen should not match propane."""
        from chemengine.core.atoms import Atom
        query = MolecularGraph(
            atoms=(Atom(atomic_number=8),),
            bonds=(),
        )
        assert not has_subgraph_match(propane_graph, query)

    def test_cc_bond_match(self, propane_graph):
        """C-C bond should match propane."""
        query = MolecularGraph(
            atoms=(propane_graph.atoms[0], propane_graph.atoms[1]),
            bonds=(propane_graph.bonds[0],),
        )
        assert has_subgraph_match(propane_graph, query)

    def test_carbon_chain_match(self, propane_graph):
        """C-C-C should match itself."""
        assert has_subgraph_match(propane_graph, propane_graph)

    def test_double_bond_match(self, cc_double_graph):
        """C=C should match itself."""
        assert has_subgraph_match(cc_double_graph, cc_double_graph)

    def test_no_match_different_bond(self, cc_double_graph):
        """Single bond query should not match double bond target."""
        query = MolecularGraph(
            atoms=(cc_double_graph.atoms[0], cc_double_graph.atoms[1]),
            bonds=(cc_double_graph.bonds[0],),
        )
        # Replace bond order with single
        from chemengine.core.bonds import Bond
        query_single = MolecularGraph(
            atoms=query.atoms,
            bonds=(Bond(atom1=0, atom2=1, order=BondOrder.SINGLE),),
        )
        assert not has_subgraph_match(cc_double_graph, query_single)

    def test_find_matches_ethanol(self, ethanol_graph):
        """Find C-C matches in ethanol (should find 1)."""
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        query = builder.build()
        matches = find_subgraph_matches(ethanol_graph, query)
        assert len(matches) == 1

    def test_count_matches_propane(self, propane_graph):
        """Count C-C bonds in propane (should be 2)."""
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        query = builder.build()
        count = count_subgraph_matches(propane_graph, query)
        assert count == 2

    def test_empty_query(self, propane_graph):
        """Empty query should match anything."""
        empty = MolecularGraph(atoms=(), bonds=())
        assert has_subgraph_match(propane_graph, empty)

    def test_large_query_no_match(self, propane_graph):
        """Query larger than target should return no match."""
        builder = MolecularGraphBuilder()
        atoms = [builder.add_atom(atomic_number=6) for _ in range(10)]
        for i in range(9):
            builder.add_bond(atoms[i], atoms[i+1], BondOrder.SINGLE)
        large = builder.build()
        assert not has_subgraph_match(propane_graph, large)

    def test_mcs_identical(self, propane_graph):
        """MCS of identical graphs should be whole graph."""
        result = maximum_common_substructure(propane_graph, propane_graph)
        assert result is not None
        atoms1, atoms2 = result
        assert len(atoms1) == propane_graph.num_heavy_atoms
        assert len(atoms2) == propane_graph.num_heavy_atoms

    def test_mcs_ethanol_propane(self, ethanol_graph, propane_graph):
        """MCS of ethanol and propane should find the C-C bond."""
        result = maximum_common_substructure(ethanol_graph, propane_graph)
        assert result is not None
        atoms1, atoms2 = result
        assert len(atoms1) >= 2  # At least the C-C bond


# ── SMARTS Tests ──

class TestSMARTS:
    """Tests for SMARTS pattern parsing and matching."""

    def test_parse_carbon_smarts(self):
        """Parse [C] — single carbon."""
        query = parse_smarts("[C]")
        assert query.num_atoms == 1
        assert query.atoms[0].atomic_number == 6

    def test_parse_cc_smarts(self):
        """Parse C-C."""
        query = parse_smarts("CC")
        assert query.num_atoms == 2
        bond = query.get_bond(0, 1)
        assert bond is not None

    def test_parse_wildcard(self):
        """Parse [*] — wildcard atom."""
        query = parse_smarts("[*]")
        assert query.num_atoms == 1
        assert query.atoms[0].atomic_number == 0

    def test_parse_aromatic_c(self):
        """Parse [c] — aromatic carbon."""
        query = parse_smarts("[c]")
        assert query.atoms[0].is_aromatic
        assert query.atoms[0].atomic_number == 6

    def test_smarts_match_cc(self, propane_graph):
        """CC SMARTS should match propane."""
        assert smarts_match("CC", propane_graph)

    def test_smarts_match_no(self, propane_graph):
        """NO SMARTS should not match propane."""
        assert not smarts_match("NO", propane_graph)

    def test_smarts_findall_cc(self, propane_graph):
        """Find all CC in propane (should be 2)."""
        matches = smarts_findall("CC", propane_graph)
        assert len(matches) == 2

    def test_smarts_count_cc(self, propane_graph):
        """Count CC in propane."""
        assert smarts_count("CC", propane_graph) == 2

    def test_smarts_double_bond(self, cc_double_graph):
        """C=C SMARTS should match ethylene."""
        assert smarts_match("C=C", cc_double_graph)

    def test_smarts_no_double_bond(self, propane_graph):
        """C=C should not match propane."""
        assert not smarts_match("C=C", propane_graph)

    def test_smarts_ethanol_oh(self, ethanol_graph):
        """Match oxygen in ethanol."""
        matches = smarts_findall("[O]", ethanol_graph)
        assert len(matches) == 1

    def test_smarts_ethanol_co_bond(self, ethanol_graph):
        """C-O bond should match ethanol."""
        assert smarts_match("CO", ethanol_graph)
