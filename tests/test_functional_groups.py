"""Tests for the functional group detection engine (Phase 3).

Covers:
    - Individual functional group detectors (alcohol, ketone, amide, etc.)
    - Overlap detection and resolution
    - Hierarchy (parent/child relationships)
    - Integration with ChemEngineAPI
    - Dataset loading
    - Edge cases (no groups, multiple occurrences)
"""

from __future__ import annotations

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.detection.functional_groups import (
    FunctionalGroupMatch,
    _find_overlapping_groups,
    _resolve_overlap,
    detect_functional_groups,
    detect_functional_groups_dict,
    get_child_groups,
    get_functional_groups,
    get_parent_group,
    list_available_groups,
    load_group_definitions,
)

# ════════════════════════════════════════════════════════════════
#  Helper: build test molecules
# ════════════════════════════════════════════════════════════════


def _make_ethanol() -> MolecularGraphBuilder:
    """Build ethanol: CH3-CH2-OH"""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
    o = builder.add_atom(atomic_number=8, implicit_hydrogens=1)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o, BondOrder.SINGLE)
    return builder


def _make_phenol() -> MolecularGraphBuilder:
    """Build phenol: aromatic ring with -OH"""
    builder = MolecularGraphBuilder()
    # Aromatic ring
    c1 = builder.add_atom(atomic_number=6, is_aromatic=True, implicit_hydrogens=1)
    c2 = builder.add_atom(atomic_number=6, is_aromatic=True, implicit_hydrogens=1)
    c3 = builder.add_atom(atomic_number=6, is_aromatic=True, implicit_hydrogens=1)
    c4 = builder.add_atom(atomic_number=6, is_aromatic=True, implicit_hydrogens=1)
    c5 = builder.add_atom(atomic_number=6, is_aromatic=True, implicit_hydrogens=1)
    c6 = builder.add_atom(atomic_number=6, is_aromatic=True, implicit_hydrogens=1)
    # Ring bonds
    builder.add_bond(c1, c2, BondOrder.AROMATIC)
    builder.add_bond(c2, c3, BondOrder.AROMATIC)
    builder.add_bond(c3, c4, BondOrder.AROMATIC)
    builder.add_bond(c4, c5, BondOrder.AROMATIC)
    builder.add_bond(c5, c6, BondOrder.AROMATIC)
    builder.add_bond(c6, c1, BondOrder.AROMATIC)
    # OH group on c1
    o = builder.add_atom(atomic_number=8, implicit_hydrogens=1)
    builder.add_bond(c1, o, BondOrder.SINGLE)
    return builder


def _make_acetaldehyde() -> MolecularGraphBuilder:
    """Build acetaldehyde: CH3-CHO"""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=1)  # Carbonyl C
    o = builder.add_atom(atomic_number=8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o, BondOrder.DOUBLE)
    return builder


def _make_acetone() -> MolecularGraphBuilder:
    """Build acetone: CH3-CO-CH3"""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    c2 = builder.add_atom(atomic_number=6)  # Carbonyl C
    c3 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    o = builder.add_atom(atomic_number=8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, c3, BondOrder.SINGLE)
    builder.add_bond(c2, o, BondOrder.DOUBLE)
    return builder


def _make_acetic_acid() -> MolecularGraphBuilder:
    """Build acetic acid: CH3-COOH"""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    c2 = builder.add_atom(atomic_number=6)  # Carbonyl C
    o1 = builder.add_atom(atomic_number=8)  # Carbonyl O
    o2 = builder.add_atom(atomic_number=8, implicit_hydrogens=1)  # OH
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o1, BondOrder.DOUBLE)
    builder.add_bond(c2, o2, BondOrder.SINGLE)
    return builder


def _make_ethylamine() -> MolecularGraphBuilder:
    """Build ethylamine: CH3-CH2-NH2"""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
    n = builder.add_atom(atomic_number=7, implicit_hydrogens=2)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, n, BondOrder.SINGLE)
    return builder


def _make_formamide() -> MolecularGraphBuilder:
    """Build formamide: H-C(=O)-NH2"""
    builder = MolecularGraphBuilder()
    c = builder.add_atom(atomic_number=6, implicit_hydrogens=1)
    o = builder.add_atom(atomic_number=8)
    n = builder.add_atom(atomic_number=7, implicit_hydrogens=2)
    builder.add_bond(c, o, BondOrder.DOUBLE)
    builder.add_bond(c, n, BondOrder.SINGLE)
    return builder


def _make_nitrile() -> MolecularGraphBuilder:
    """Build acetonitrile: CH3-C≡N"""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    c2 = builder.add_atom(atomic_number=6)  # Nitrile C
    n = builder.add_atom(atomic_number=7)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, n, BondOrder.TRIPLE)
    return builder


def _make_nitrobenzene() -> MolecularGraphBuilder:
    """Build a simple nitro-containing molecule (simplified)."""
    builder = MolecularGraphBuilder()
    c = builder.add_atom(atomic_number=6)
    n = builder.add_atom(atomic_number=7)
    o1 = builder.add_atom(atomic_number=8)
    o2 = builder.add_atom(atomic_number=8)
    builder.add_bond(c, n, BondOrder.SINGLE)
    builder.add_bond(n, o1, BondOrder.DOUBLE)
    builder.add_bond(n, o2, BondOrder.DOUBLE)
    return builder


def _make_ether() -> MolecularGraphBuilder:
    """Build diethyl ether: CH3-CH2-O-CH2-CH3"""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
    o = builder.add_atom(atomic_number=8)
    c3 = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
    c4 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o, BondOrder.SINGLE)
    builder.add_bond(o, c3, BondOrder.SINGLE)
    builder.add_bond(c3, c4, BondOrder.SINGLE)
    return builder


def _make_thiol() -> MolecularGraphBuilder:
    """Build methanethiol: CH3-SH"""
    builder = MolecularGraphBuilder()
    c = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
    s = builder.add_atom(atomic_number=16, implicit_hydrogens=1)
    builder.add_bond(c, s, BondOrder.SINGLE)
    return builder


# ════════════════════════════════════════════════════════════════
#  Data Model Tests
# ════════════════════════════════════════════════════════════════


class TestFunctionalGroupMatch:
    """Test the FunctionalGroupMatch dataclass."""

    def test_create_match(self):
        match = FunctionalGroupMatch(
            name="Alcohol",
            smarts="[OX2H]",
            atom_indices=(0, 1),
            priority=10,
            categories=("oxygen", "hydroxy"),
        )
        assert match.name == "Alcohol"
        assert match.atom_indices == (0, 1)
        assert match.priority == 10

    def test_to_dict(self):
        match = FunctionalGroupMatch(
            name="Test",
            smarts="[test]",
            atom_indices=(0, 1, 2),
            priority=5,
            categories=("cat1",),
            parent="Parent",
        )
        d = match.to_dict()
        assert d["name"] == "Test"
        assert d["atom_indices"] == [0, 1, 2]
        assert d["parent"] == "Parent"

    def test_default_parent(self):
        match = FunctionalGroupMatch(
            name="Alcohol",
            smarts="[OX2H]",
            atom_indices=(0, 1),
        )
        assert match.parent is None
        assert match.priority == 0


# ════════════════════════════════════════════════════════════════
#  Individual Detector Tests
# ════════════════════════════════════════════════════════════════


class TestDetectAlcohol:
    """Test alcohol group detection."""

    def test_ethanol_has_alcohol(self):
        graph = _make_ethanol().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Alcohol" in names

    def test_alkane_no_alcohol(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Alcohol" not in names


class TestDetectPhenol:
    """Test phenol group detection."""

    def test_phenol_detected(self):
        graph = _make_phenol().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Phenol" in names


class TestDetectEther:
    """Test ether group detection."""

    def test_diethyl_ether(self):
        graph = _make_ether().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Ether" in names


class TestDetectAldehyde:
    """Test aldehyde group detection."""

    def test_acetaldehyde(self):
        graph = _make_acetaldehyde().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Aldehyde" in names, f"Expected aldehyde, got {names}"


class TestDetectKetone:
    """Test ketone group detection."""

    def test_acetone(self):
        graph = _make_acetone().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Ketone" in names, f"Expected ketone, got {names}"


class TestDetectCarboxylicAcid:
    """Test carboxylic acid detection."""

    def test_acetic_acid(self):
        graph = _make_acetic_acid().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Carboxylic Acid" in names, f"Expected carboxylic acid, got {names}"


class TestDetectAmine:
    """Test amine detection."""

    def test_primary_amine(self):
        graph = _make_ethylamine().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Amine Primary" in names, f"Expected primary amine, got {names}"

    def test_secondary_amine(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
        n = builder.add_atom(atomic_number=7, implicit_hydrogens=1)
        c3 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c2, n, BondOrder.SINGLE)
        builder.add_bond(n, c3, BondOrder.SINGLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Amine Secondary" in names, f"Expected secondary amine, got {names}"

    def test_tertiary_amine(self):
        builder = MolecularGraphBuilder()
        n = builder.add_atom(atomic_number=7, implicit_hydrogens=0)
        c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        c3 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        builder.add_bond(n, c1, BondOrder.SINGLE)
        builder.add_bond(n, c2, BondOrder.SINGLE)
        builder.add_bond(n, c3, BondOrder.SINGLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Amine Tertiary" in names, f"Expected tertiary amine, got {names}"


class TestDetectAmide:
    """Test amide detection."""

    def test_formamide(self):
        graph = _make_formamide().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Amide" in names, f"Expected amide, got {names}"


class TestDetectNitrile:
    """Test nitrile detection."""

    def test_acetonitrile(self):
        graph = _make_nitrile().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Nitrile" in names, f"Expected nitrile, got {names}"


class TestDetectNitro:
    """Test nitro detection."""

    def test_nitro_group(self):
        graph = _make_nitrobenzene().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Nitro" in names, f"Expected nitro, got {names}"


class TestDetectHalogen:
    """Test halogen detection."""

    def test_chlorine(self):
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        cl = builder.add_atom(atomic_number=17)
        builder.add_bond(c, cl, BondOrder.SINGLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Halogen" in names

    def test_fluorine(self):
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        f = builder.add_atom(atomic_number=9)
        builder.add_bond(c, f, BondOrder.SINGLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Halogen" in names

    def test_bromine(self):
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        br = builder.add_atom(atomic_number=35)
        builder.add_bond(c, br, BondOrder.SINGLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Halogen" in names


class TestDetectThiol:
    """Test thiol detection."""

    def test_methanethiol(self):
        graph = _make_thiol().build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Thiol" in names, f"Expected thiol, got {names}"


class TestDetectAlkene:
    """Test alkene detection."""

    def test_ethylene(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
        c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Alkene" in names, f"Expected alkene, got {names}"


class TestDetectAlkyne:
    """Test alkyne detection."""

    def test_acetylene(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=1)
        c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=1)
        builder.add_bond(c1, c2, BondOrder.TRIPLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        names = [m.name for m in matches]
        assert "Alkyne" in names, f"Expected alkyne, got {names}"


# ════════════════════════════════════════════════════════════════
#  Overlap Resolution Tests
# ════════════════════════════════════════════════════════════════


class TestOverlapResolution:
    """Test functional group overlap detection and resolution."""

    def test_ethanol_multiple_groups(self):
        """Ethanol has both Alcohol and Alkene should not overlap."""
        graph = _make_ethanol().build()
        matches = detect_functional_groups(graph, resolve_overlaps=True)
        names = {m.name for m in matches}
        assert "Alcohol" in names

    def test_no_overlap_no_removal(self):
        """Non-overlapping groups should all be kept."""
        matches = [
            FunctionalGroupMatch(name="A", smarts="", atom_indices=(0, 1), priority=10),
            FunctionalGroupMatch(name="B", smarts="", atom_indices=(2, 3), priority=10),
        ]
        resolved = _resolve_overlap(matches)
        assert len(resolved) == 2

    def test_overlap_keeps_highest_priority(self):
        """When two groups overlap, keep the higher priority one."""
        matches = [
            FunctionalGroupMatch(name="Low", smarts="", atom_indices=(0, 1), priority=5),
            FunctionalGroupMatch(name="High", smarts="", atom_indices=(0, 1, 2), priority=10),
        ]
        resolved = _resolve_overlap(matches)
        assert len(resolved) == 1
        assert resolved[0].name == "High"

    def test_overlap_tie_breaker(self):
        """Ties should be broken by number of atoms (more specific)."""
        matches = [
            FunctionalGroupMatch(name="Small", smarts="", atom_indices=(0,), priority=10),
            FunctionalGroupMatch(name="Large", smarts="", atom_indices=(0, 1, 2), priority=10),
        ]
        resolved = _resolve_overlap(matches)
        assert len(resolved) == 1
        assert resolved[0].name == "Large", "Should prefer more atoms"

    def test_complex_overlap_three_groups(self):
        """Three overlapping groups should resolve to the best one."""
        matches = [
            FunctionalGroupMatch(name="A", smarts="", atom_indices=(0,), priority=5),
            FunctionalGroupMatch(name="B", smarts="", atom_indices=(0, 1), priority=10),
            FunctionalGroupMatch(name="C", smarts="", atom_indices=(1, 2), priority=15),
        ]
        resolved = _resolve_overlap(matches)
        # All three overlap transitively, should keep only the best
        assert len(resolved) >= 1
        assert resolved[0].name == "C"

    def test_find_overlapping(self):
        matches = [
            FunctionalGroupMatch(name="A", smarts="", atom_indices=(0, 1)),
            FunctionalGroupMatch(name="B", smarts="", atom_indices=(1, 2)),
            FunctionalGroupMatch(name="C", smarts="", atom_indices=(3, 4)),
        ]
        clusters = _find_overlapping_groups(matches)
        assert len(clusters) == 2  # Two groups: {0,1} and {2}

    def test_empty_overlap(self):
        clusters = _find_overlapping_groups([])
        assert clusters == []


# ════════════════════════════════════════════════════════════════
#  Hierarchy Tests
# ════════════════════════════════════════════════════════════════


class TestHierarchy:
    """Test functional group hierarchy."""

    def test_phenol_parent_is_alcohol(self):
        assert get_parent_group("Phenol") == "Alcohol"

    def test_ketone_parent_is_carbonyl(self):
        assert get_parent_group("Ketone") == "Carbonyl"

    def test_no_parent(self):
        assert get_parent_group("Alcohol") is None

    def test_child_groups(self):
        children = get_child_groups("Carbonyl")
        assert "Aldehyde" in children
        assert "Ketone" in children
        assert "Carboxylic Acid" in children
        assert "Ester" in children
        assert "Amide" in children

    def test_amine_children(self):
        children = get_child_groups("Amine")
        assert "Amine Primary" in children
        assert "Amine Secondary" in children
        assert "Amine Tertiary" in children


# ════════════════════════════════════════════════════════════════
#  Dataset Tests
# ════════════════════════════════════════════════════════════════


class TestDatasetIntegration:
    """Test integration with functional_groups.toml dataset."""

    def test_load_definitions(self):
        definitions = load_group_definitions()
        assert len(definitions) >= 20, f"Expected >=20 groups, got {len(definitions)}"

    def test_known_groups_present(self):
        definitions = load_group_definitions()
        names = {g["name"] for g in definitions}
        for expected in ("Alcohol", "Ketone", "Amide", "Nitrile", "Ester", "Halogen"):
            assert expected in names, f"Expected {expected} in dataset"

    def test_list_available(self):
        available = list_available_groups()
        assert len(available) >= 20


# ════════════════════════════════════════════════════════════════
#  Full Molecule Integration Tests
# ════════════════════════════════════════════════════════════════


class TestMoleculeIntegration:
    """Test detection on real molecule examples."""

    def test_ethanol_detects_all_groups(self):
        graph = _make_ethanol().build()
        matches = detect_functional_groups(graph)
        assert len(matches) >= 1
        names = {m.name for m in matches}
        assert "Alcohol" in names

    def test_phenol_detects_both(self):
        """Phenol should detect Phenol and possibly Aromatic Ring."""
        graph = _make_phenol().build()
        matches = detect_functional_groups(graph)
        names = {m.name for m in matches}
        assert "Phenol" in names
        assert "Alcohol" not in names  # Phenol subsumes Alcohol via overlap

    def test_acetaldehyde_detects(self):
        graph = _make_acetaldehyde().build()
        matches = detect_functional_groups(graph)
        names = {m.name for m in matches}
        assert "Aldehyde" in names

    def test_acetone_detects(self):
        graph = _make_acetone().build()
        matches = detect_functional_groups(graph)
        names = {m.name for m in matches}
        assert "Ketone" in names

    def test_acetic_acid_detects(self):
        graph = _make_acetic_acid().build()
        matches = detect_functional_groups(graph)
        names = {m.name for m in matches}
        assert "Carboxylic Acid" in names

    def test_nitrile_detects(self):
        graph = _make_nitrile().build()
        matches = detect_functional_groups(graph)
        names = {m.name for m in matches}
        assert "Nitrile" in names

    def test_ether_no_overlap(self):
        graph = _make_ether().build()
        matches = detect_functional_groups(graph)
        names = {m.name for m in matches}
        assert "Ether" in names

    def test_to_dict_format(self):
        graph = _make_ethanol().build()
        groups = detect_functional_groups_dict(graph)
        assert isinstance(groups, list)
        if groups:
            g = groups[0]
            assert "name" in g
            assert "atom_indices" in g
            assert isinstance(g["atom_indices"], list)

    def test_no_groups_on_alkane(self):
        """Methane should have no functional groups."""
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6, implicit_hydrogens=4)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        assert len(matches) == 0

    def test_multiple_halogens(self):
        """CH2Cl2 should detect 2 halogen groups."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
        cl1 = builder.add_atom(atomic_number=17)
        cl2 = builder.add_atom(atomic_number=17)
        builder.add_bond(c, cl1, BondOrder.SINGLE)
        builder.add_bond(c, cl2, BondOrder.SINGLE)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        halogen_matches = [m for m in matches if m.name == "Halogen"]
        assert len(halogen_matches) == 2, f"Expected 2 halogens, got {len(halogen_matches)}"

    def test_get_functional_groups_alias(self):
        """get_functional_groups should be an alias for detect_functional_groups."""
        graph = _make_ethanol().build()
        matches1 = detect_functional_groups(graph)
        matches2 = get_functional_groups(graph)
        assert len(matches1) == len(matches2)


# ════════════════════════════════════════════════════════════════
#  ChemEngineAPI Integration Tests
# ════════════════════════════════════════════════════════════════


class TestChemEngineAPIIntegration:
    """Test FG detection through ChemEngineAPI."""

    def test_detect_functional_groups_api(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        builder = _make_ethanol()
        graph = builder.build()
        groups = api.detect_functional_groups(graph)
        assert isinstance(groups, list)

    def test_execute_detect_functional_groups_tool(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        result = api.execute_tool("detect_functional_groups", {"smiles": "CCO"})
        assert "functional_groups" in result
        assert isinstance(result["functional_groups"], list)

    def test_execute_tool_ethanol_groups(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        result = api.execute_tool("detect_functional_groups", {"smiles": "CCO"})
        group_names = {g["name"] for g in result["functional_groups"]}
        assert "Alcohol" in group_names, f"Expected Alcohol, got {group_names}"


# ════════════════════════════════════════════════════════════════
#  Edge Case Tests
# ════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases for FG detection."""

    def test_empty_graph(self):
        builder = MolecularGraphBuilder()
        graph = builder.build()
        matches = detect_functional_groups(graph)
        assert matches == []

    def test_single_atom(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        assert matches == []

    def test_water_no_groups(self):
        """Water (H2O) has no carbon, so no functional groups should match."""
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=8, implicit_hydrogens=2)
        graph = builder.build()
        matches = detect_functional_groups(graph)
        assert matches == []

    def test_overlap_resolution_preserves_correct_groups(self):
        """Acetic acid has Carboxylic Acid (priority 25) and Alkene should not interfere."""
        graph = _make_acetic_acid().build()
        matches = detect_functional_groups(graph, resolve_overlaps=True)
        names = {m.name for m in matches}
        assert "Carboxylic Acid" in names
