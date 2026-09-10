"""Tests for Phase 11: IUPAC Nomenclature
- Alkane naming
- Functional group naming
- Ring naming
- Substituent naming
"""


from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.nomenclature.iupac import (
    _check_for_ring,
    _detect_functional_groups,
    _find_longest_chain,
    generate_iupac_name,
)

# ── Fixtures ──

def _make_methane():
    builder = MolecularGraphBuilder()
    c = builder.add_atom(6)
    for _ in range(4):
        h = builder.add_atom(1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_ethane():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    for c in (c1, c2):
        for _ in range(3):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_propane():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    c3 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, c3, BondOrder.SINGLE)
    for c, n in [(c1, 3), (c2, 2), (c3, 3)]:
        for _ in range(n):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_ethene():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    builder.add_bond(c1, c2, BondOrder.DOUBLE)
    for c in (c1, c2):
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_ethanol():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    o = builder.add_atom(8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o, BondOrder.SINGLE)
    for c, n in [(c1, 3), (c2, 2)]:
        for _ in range(n):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    h = builder.add_atom(1)
    builder.add_bond(o, h, BondOrder.SINGLE)
    return builder.build()


def _make_acetic_acid():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    o1 = builder.add_atom(8)
    o2 = builder.add_atom(8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o1, BondOrder.DOUBLE)
    builder.add_bond(c2, o2, BondOrder.SINGLE)
    for _ in range(3):
        h = builder.add_atom(1)
        builder.add_bond(c1, h, BondOrder.SINGLE)
    h = builder.add_atom(1)
    builder.add_bond(o2, h, BondOrder.SINGLE)
    return builder.build()


def _make_cyclopropane():
    builder = MolecularGraphBuilder()
    carbons = [builder.add_atom(6) for _ in range(3)]
    for i in range(3):
        builder.add_bond(carbons[i], carbons[(i + 1) % 3], BondOrder.SINGLE)
    for c in carbons:
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_chloromethane():
    builder = MolecularGraphBuilder()
    c = builder.add_atom(6)
    cl = builder.add_atom(17)
    builder.add_bond(c, cl, BondOrder.SINGLE)
    for _ in range(3):
        h = builder.add_atom(1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


# ── Naming Tests ──

class TestIUPACNaming:
    def test_empty_graph(self):
        graph = MolecularGraph(atoms=(), bonds=())
        name = generate_iupac_name(graph)
        assert name == ""

    def test_single_atom_hydrogen(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(1)
        graph = builder.build()
        name = generate_iupac_name(graph)
        assert "hydrogen" in name.lower()

    def test_single_atom_carbon(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(6)
        graph = builder.build()
        name = generate_iupac_name(graph)
        assert "methane" in name.lower()

    def test_methane(self):
        graph = _make_methane()
        name = generate_iupac_name(graph)
        assert "methane" in name.lower()

    def test_ethane(self):
        graph = _make_ethane()
        name = generate_iupac_name(graph)
        assert "eth" in name.lower()

    def test_propane(self):
        graph = _make_propane()
        name = generate_iupac_name(graph)
        assert "prop" in name.lower()

    def test_ethene(self):
        graph = _make_ethene()
        name = generate_iupac_name(graph)
        assert "eth" in name.lower()
        assert "ene" in name.lower()

    def test_ethanol(self):
        graph = _make_ethanol()
        name = generate_iupac_name(graph)
        assert "ol" in name.lower()  # Alcohol suffix

    def test_acetic_acid(self):
        graph = _make_acetic_acid()
        name = generate_iupac_name(graph)
        assert "acid" in name.lower()

    def test_cyclopropane(self):
        graph = _make_cyclopropane()
        name = generate_iupac_name(graph)
        assert "cyclo" in name.lower()
        assert "prop" in name.lower()

    def test_chloromethane(self):
        graph = _make_chloromethane()
        name = generate_iupac_name(graph)
        assert "chlor" in name.lower()

    def test_name_is_string(self):
        graph = _make_ethane()
        name = generate_iupac_name(graph)
        assert isinstance(name, str)
        assert len(name) > 0


# ── Functional Group Detection Tests ──

class TestFunctionalGroupDetection:
    def test_hydroxyl_detection(self):
        graph = _make_ethanol()
        groups = _detect_functional_groups(graph)
        assert len(groups["hydroxyl"]) > 0

    def test_carboxyl_detection(self):
        graph = _make_acetic_acid()
        groups = _detect_functional_groups(graph)
        assert len(groups["carboxyl"]) > 0

    def test_halogen_detection(self):
        graph = _make_chloromethane()
        groups = _detect_functional_groups(graph)
        assert len(groups["halogen"]) > 0

    def test_alkene_detection(self):
        graph = _make_ethene()
        groups = _detect_functional_groups(graph)
        assert len(groups["alkene"]) > 0

    def test_ethane_no_functional_groups(self):
        graph = _make_ethane()
        groups = _detect_functional_groups(graph)
        assert len(groups["hydroxyl"]) == 0
        assert len(groups["carbonyl"]) == 0
        assert len(groups["carboxyl"]) == 0


# ── Chain Detection Tests ──

class TestChainDetection:
    def test_ethane_chain(self):
        graph = _make_ethane()
        chain = _find_longest_chain(graph)
        assert len(chain) == 2

    def test_propane_chain(self):
        graph = _make_propane()
        chain = _find_longest_chain(graph)
        assert len(chain) == 3

    def test_cyclopropane_chain(self):
        graph = _make_cyclopropane()
        chain = _find_longest_chain(graph)
        assert len(chain) >= 3


# ── Ring Detection Tests ──

class TestRingDetection:
    def test_cyclopropane_is_ring(self):
        graph = _make_cyclopropane()
        result = _check_for_ring(graph)
        assert result is not None
        assert "cyclo" in result.lower()

    def test_ethane_not_ring(self):
        graph = _make_ethane()
        result = _check_for_ring(graph)
        assert result is None

    def test_propane_not_ring(self):
        graph = _make_propane()
        result = _check_for_ring(graph)
        assert result is None
