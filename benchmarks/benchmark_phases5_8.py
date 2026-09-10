"""
Performance benchmarks for substructure search, stereochemistry,
isomer generation, and molecular properties (Phases 5-8).
"""

import pytest
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.core.bonds import BondOrder
from chemengine.parsing.smiles import parse_smiles
from chemengine.detection.substructure import (
    has_subgraph_match, find_subgraph_matches, count_subgraph_matches
)
from chemengine.stereochemistry.cip import get_cip_priority, is_chiral_center
from chemengine.stereochemistry.perception import perceive_stereochemistry
from chemengine.generation.constitutional import generate_alkane_isomers
from chemengine.generation.stereoisomers import enumerate_stereoisomers
from chemengine.properties.descriptors import (
    compute_tpsa, compute_logp, compute_hba, compute_hbd,
    compute_rotatable_bonds, compute_property
)


# ── Fixtures ──

@pytest.fixture
def ethanol_graph():
    return parse_smiles("CCO")


@pytest.fixture
def propane_graph():
    builder = MolecularGraphBuilder()
    atoms = [builder.add_atom(atomic_number=6) for _ in range(3)]
    for i in range(2):
        builder.add_bond(atoms[i], atoms[i+1], BondOrder.SINGLE)
    for a in atoms:
        for _ in range(2):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(a, h, BondOrder.SINGLE)
    h1 = builder.add_atom(atomic_number=1)
    builder.add_bond(atoms[0], h1, BondOrder.SINGLE)
    h2 = builder.add_atom(atomic_number=1)
    builder.add_bond(atoms[2], h2, BondOrder.SINGLE)
    return builder.build()


@pytest.fixture
def chiral_graph():
    """Carbon with 4 distinct substituents (F, Cl, Br, I)."""
    builder = MolecularGraphBuilder()
    c = builder.add_atom(atomic_number=6)
    f = builder.add_atom(atomic_number=9)
    cl = builder.add_atom(atomic_number=17)
    br = builder.add_atom(atomic_number=35)
    i = builder.add_atom(atomic_number=53)
    for n in (f, cl, br, i):
        builder.add_bond(c, n, BondOrder.SINGLE)
    return builder.build()


# ── Phase 5: Substructure Search Benchmarks ──

class TestSubstructureBenchmarks:
    def test_vf2_match_ethanol_cc(self, benchmark, ethanol_graph):
        """VF2: Match C-C in ethanol."""
        query = MolecularGraph(
            atoms=(ethanol_graph.atoms[0], ethanol_graph.atoms[1]),
            bonds=(ethanol_graph.bonds[0],),
        )
        result = benchmark(lambda: has_subgraph_match(ethanol_graph, query))
        assert result is True

    def test_vf2_findall_ethanol(self, benchmark, ethanol_graph):
        """VF2: Find all C-C matches in ethanol."""
        query = MolecularGraph(
            atoms=(ethanol_graph.atoms[0], ethanol_graph.atoms[1]),
            bonds=(ethanol_graph.bonds[0],),
        )
        matches = benchmark(lambda: find_subgraph_matches(ethanol_graph, query))
        assert len(matches) >= 1

    def test_vf2_count_propane(self, benchmark, propane_graph):
        """VF2: Count C-C bonds in propane."""
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        query = builder.build()
        count = benchmark(lambda: count_subgraph_matches(propane_graph, query))
        assert count >= 2


# ── Phase 6: Stereochemistry Benchmarks ──

class TestStereochemistryBenchmarks:
    def test_cip_priority(self, benchmark, chiral_graph):
        """CIP: Rank substituents by priority."""
        result = benchmark(lambda: get_cip_priority(chiral_graph, 0, [1, 2, 3, 4]))
        assert len(result) == 4
        # Highest atomic number (I=53) should be first
        assert result[0] == 4

    def test_is_chiral_center(self, benchmark, chiral_graph):
        """Chiral center detection."""
        result = benchmark(lambda: is_chiral_center(chiral_graph, 0))
        assert result is True

    def test_perceive_stereo(self, benchmark, chiral_graph):
        """Full stereo perception."""
        config = benchmark(lambda: perceive_stereochemistry(chiral_graph))
        assert config.count >= 1


# ── Phase 7: Isomer Generation Benchmarks ──

class TestGenerationBenchmarks:
    def test_alkane_isomers_c4(self, benchmark):
        """Generate C4 alkane isomers."""
        isomers = benchmark(lambda: generate_alkane_isomers(4))
        assert len(isomers) == 2

    def test_alkane_isomers_c5(self, benchmark):
        """Generate C5 alkane isomers."""
        isomers = benchmark(lambda: generate_alkane_isomers(5))
        assert len(isomers) == 3

    def test_stereoisomers_ethane(self, benchmark, propane_graph):
        """Enumerate stereoisomers."""
        isomers = benchmark(lambda: enumerate_stereoisomers(propane_graph))
        assert len(isomers) >= 1


# ── Phase 8: Molecular Properties Benchmarks ──

class TestPropertiesBenchmarks:
    def test_compute_tpsa_methane(self, benchmark):
        """TPSA of methane (no polar atoms)."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        result = benchmark(lambda: compute_tpsa(graph))
        assert result == 0.0

    def test_compute_logp(self, benchmark):
        """logP of methane.

        The engine's Wildman-Crippen fragment table assigns
        H=0.0000 and sp3 C=0.1441, so methane (one sp3 carbon, four
        hydrogens) evaluates to 0.1441. This is a performance benchmark;
        the assertion guards against descriptor value regressions.
        """
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        result = benchmark(lambda: compute_logp(graph))
        assert result == 0.1441

    def test_compute_hba(self, benchmark):
        """HBA of water."""
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8)
        h1 = builder.add_atom(atomic_number=1)
        h2 = builder.add_atom(atomic_number=1)
        builder.add_bond(o, h1, BondOrder.SINGLE)
        builder.add_bond(o, h2, BondOrder.SINGLE)
        graph = builder.build()
        result = benchmark(lambda: compute_hba(graph))
        assert result == 1

    def test_compute_hbd(self, benchmark):
        """HBD of water."""
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8)
        h1 = builder.add_atom(atomic_number=1)
        h2 = builder.add_atom(atomic_number=1)
        builder.add_bond(o, h1, BondOrder.SINGLE)
        builder.add_bond(o, h2, BondOrder.SINGLE)
        graph = builder.build()
        result = benchmark(lambda: compute_hbd(graph))
        assert result == 1

    def test_rotatable_bonds_ethane(self, benchmark):
        """Rotatable bonds in ethane.

        By the standard rotatable-bond definition used here (and by RDKit's
        strict mode), a bond is rotatable only when BOTH atoms have at least
        2 heavy-atom neighbors. Each methyl carbon in ethane has only one
        heavy neighbor, so the C-C bond is NOT rotatable -> 0.
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
        result = benchmark(lambda: compute_rotatable_bonds(graph))
        assert result == 0

    def test_all_properties(self, benchmark):
        """Compute multiple properties on methane."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        for _ in range(4):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        graph = builder.build()
        def compute_all():
            return {
                "formula": compute_property(graph, "formula"),
                "mass": compute_property(graph, "mass"),
                "tpsa": compute_property(graph, "tpsa"),
                "logp": compute_property(graph, "logp"),
            }
        props = benchmark(compute_all)
        assert props["formula"] == "CH4"
