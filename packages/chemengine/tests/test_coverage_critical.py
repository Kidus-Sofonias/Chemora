"""Tests for modules with critically low coverage (<60%)."""

from unittest.mock import MagicMock

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.enums import BondStereo, ChiralTag, StereoCategory
from chemengine.core.graph import MolecularGraphBuilder

# ═══════════════════════════════════════════════════════════════════
# utils/cache.py (36%)
# ═══════════════════════════════════════════════════════════════════

class TestMolecularCache:
    def test_get_miss_returns_none(self):
        from chemengine.utils.cache import MolecularCache
        c = MolecularCache(maxsize=4)
        assert c.get("missing") is None

    def test_set_and_get(self):
        from chemengine.utils.cache import MolecularCache
        c = MolecularCache(maxsize=4)
        c.set("k1", "v1")
        assert c.get("k1") == "v1"

    def test_lru_eviction(self):
        from chemengine.utils.cache import MolecularCache
        c = MolecularCache(maxsize=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)  # evicts 'a'
        assert c.get("a") is None
        assert c.get("d") == 4

    def test_lru_get_moves_to_end(self):
        from chemengine.utils.cache import MolecularCache
        c = MolecularCache(maxsize=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.get("a")  # moves 'a' to end
        c.set("d", 4)  # evicts 'b' now
        assert c.get("a") == 1
        assert c.get("b") is None

    def test_clear(self):
        from chemengine.utils.cache import MolecularCache
        c = MolecularCache()
        c.set("x", 10)
        c.clear()
        assert c.size == 0
        assert c.get("x") is None

    def test_size_property(self):
        from chemengine.utils.cache import MolecularCache
        c = MolecularCache()
        assert c.size == 0
        c.set("a", 1)
        c.size == 1
        c.set("b", 2)
        assert c.size == 2

    def test_overwrite_existing_key(self):
        from chemengine.utils.cache import MolecularCache
        c = MolecularCache(maxsize=2)
        c.set("k", "old")
        c.set("k", "new")
        assert c.get("k") == "new"
        assert c.size == 1


# ═══════════════════════════════════════════════════════════════════
# utils/benchmarking.py (38%)
# ═══════════════════════════════════════════════════════════════════

class TestTimer:
    def test_context_manager(self):
        from chemengine.utils.benchmarking import Timer
        with Timer("test") as t:
            pass
        assert t.elapsed >= 0
        assert t.name == "test"

    def test_repr(self):
        from chemengine.utils.benchmarking import Timer
        with Timer("bench") as t:
            pass
        r = repr(t)
        assert "bench" in r
        assert "ms" in r

    def test_empty_name(self):
        from chemengine.utils.benchmarking import Timer
        with Timer() as t:
            pass
        assert t.name == ""


class TestBenchmarkDecorator:
    def test_benchmark_decorator(self):
        from chemengine.utils.benchmarking import benchmark

        @benchmark
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_benchmark_preserves_function_name(self):
        from chemengine.utils.benchmarking import benchmark

        @benchmark
        def my_func():
            """My docstring."""
            return 1

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."


# ═══════════════════════════════════════════════════════════════════
# utils/logging.py (62%)
# ═══════════════════════════════════════════════════════════════════

class TestLogging:
    def test_setup_logging(self):
        import logging

        from chemengine.utils.logging import setup_logging
        setup_logging(level=logging.DEBUG)
        # Should not raise

    def test_get_logger(self):
        from chemengine.utils.logging import get_logger
        logger = get_logger("test_module")
        assert logger is not None

    def test_get_logger_with_initial_values(self):
        from chemengine.utils.logging import get_logger
        logger = get_logger("test_ctx", key="value")
        assert logger is not None


# ═══════════════════════════════════════════════════════════════════
# core/plugin.py (51%)
# ═══════════════════════════════════════════════════════════════════

class _MockPlugin:
    @property
    def name(self):
        return "mock-plugin"

    @property
    def version(self):
        return "0.1.0"

    @property
    def dependencies(self):
        return []

    def on_load(self, engine):
        self._engine = engine

    def on_unload(self):
        pass


class _FailingLoadPlugin:
    @property
    def name(self):
        return "failing-plugin"

    @property
    def version(self):
        return "0.0.1"

    @property
    def dependencies(self):
        return []

    def on_load(self, engine):
        raise RuntimeError("on_load failed")

    def on_unload(self):
        pass


class TestPluginManagerExtended:
    def setup_method(self):
        from chemengine.core.events import reset_global_bus
        from chemengine.core.plugin import PluginManager
        reset_global_bus()
        self.mgr = PluginManager()

    def test_load_not_found_raises_key_error(self):
        with pytest.raises(KeyError, match="not found"):
            self.mgr.load("nonexistent", None)

    def test_load_already_loaded_returns_same(self):
        from chemengine.core.plugin import PluginInfo
        plugin = _MockPlugin()
        self.mgr._plugins["mock-plugin"] = PluginInfo(
            name="mock-plugin", version="0.1.0",
            entry_point=None, instance=plugin,
        )
        result = self.mgr.load("mock-plugin", None)
        assert result is plugin

    def test_load_import_error(self):
        """Test load with entry point whose load() raises ImportError."""
        mock_ep = MagicMock()
        mock_ep.name = "bad-module"
        mock_ep.load.side_effect = ImportError("No module")
        self.mgr._entry_points = [mock_ep]
        with pytest.raises(ImportError, match="Failed to load"):
            self.mgr.load("bad-module", None)

    def test_load_plugin_class(self):
        """Test load when entry point returns a class (not instance)."""
        mock_ep = MagicMock()
        mock_ep.name = "cls-plugin"
        mock_ep.load.return_value = _MockPlugin  # return the class itself
        self.mgr._entry_points = [mock_ep]
        instance = self.mgr.load("cls-plugin", None)
        assert isinstance(instance, _MockPlugin)

    def test_load_on_load_failure(self):
        """Test load when on_load raises."""
        mock_ep = MagicMock()
        mock_ep.name = "failing"
        mock_ep.load.return_value = _FailingLoadPlugin
        self.mgr._entry_points = [mock_ep]
        with pytest.raises(RuntimeError, match="on_load failed"):
            self.mgr.load("failing", None)

    def test_load_all_with_entry_points(self):
        """Test load_all discovers and loads."""
        mock_ep = MagicMock()
        mock_ep.name = "mock-plugin"
        mock_ep.load.return_value = _MockPlugin
        self.mgr._entry_points = [mock_ep]
        loaded = self.mgr.load_all(None)
        assert len(loaded) == 1

    def test_load_all_failing_plugin_skipped(self):
        """Test load_all skips failing plugins."""
        ep1 = MagicMock()
        ep1.name = "good"
        ep1.load.return_value = _MockPlugin

        ep2 = MagicMock()
        ep2.name = "bad"
        ep2.load.side_effect = ImportError("fail")

        self.mgr._entry_points = [ep1, ep2]
        loaded = self.mgr.load_all(None)
        assert len(loaded) == 1

    def test_load_all_no_entry_points_discovers(self):
        """Test load_all calls discover() if entry_points is empty."""
        result = self.mgr.load_all(None)
        assert result == []

    def test_unload_with_on_unload_error(self):
        """Unload should not raise even if on_unload fails."""
        class BadUnloadPlugin:
            @property
            def name(self):
                return "bad-unload"
            @property
            def version(self):
                return "0.0.1"
            @property
            def dependencies(self):
                return []
            def on_load(self, engine):
                pass
            def on_unload(self):
                raise RuntimeError("unload failed")

        from chemengine.core.plugin import PluginInfo
        plugin = BadUnloadPlugin()
        self.mgr._plugins["bad-unload"] = PluginInfo(
            name="bad-unload", version="0.0.1",
            entry_point=None, instance=plugin,
        )
        self.mgr.unload("bad-unload")  # should not raise
        assert not self.mgr.is_loaded("bad-unload")

    def test_find_entry_point_not_found(self):
        self.mgr._entry_points = []
        result = self.mgr._find_entry_point("missing")
        assert result is None

    def test_repr_loaded(self):
        from chemengine.core.plugin import PluginInfo
        plugin = _MockPlugin()
        self.mgr._plugins["mock-plugin"] = PluginInfo(
            name="mock-plugin", version="0.1.0",
            entry_point=None, instance=plugin,
        )
        r = repr(self.mgr)
        assert "1 loaded" in r


# ═══════════════════════════════════════════════════════════════════
# parsing/smarts.py (52%)
# ═══════════════════════════════════════════════════════════════════

class TestSmartTokenizer:
    def test_tokenize_simple(self):
        from chemengine.parsing.smarts import _tokenize_smarts
        tokens = _tokenize_smarts("CC")
        assert len(tokens) == 2

    def test_tokenize_bonds(self):
        from chemengine.parsing.smarts import _tokenize_smarts
        tokens = _tokenize_smarts("C=C")
        assert any("bond" in t for t in tokens)

    def test_tokenize_bracket_atom(self):
        from chemengine.parsing.smarts import _tokenize_smarts
        tokens = _tokenize_smarts("[O-]")
        assert len(tokens) == 1
        assert "charge" in tokens[0]

    def test_tokenize_wildcard(self):
        from chemengine.parsing.smarts import _tokenize_smarts
        tokens = _tokenize_smarts("[*]")
        assert len(tokens) == 1
        assert "wildcard" in tokens[0]

    def test_tokenize_ring(self):
        from chemengine.parsing.smarts import _tokenize_smarts
        tokens = _tokenize_smarts("C1CC1")
        assert any("ring" in t for t in tokens)

    def test_tokenize_branches(self):
        from chemengine.parsing.smarts import _tokenize_smarts
        tokens = _tokenize_smarts("C(C)C")
        assert any("branch" in t for t in tokens)

    def test_tokenize_dot(self):
        from chemengine.parsing.smarts import _tokenize_smarts
        tokens = _tokenize_smarts("C.C")
        assert any("dot" in t for t in tokens)


class TestBracketAtomParsing:
    def test_charge_plus(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"charge": "+"})
        assert spec["formal_charge"] == 1

    def test_charge_minus(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"charge": "-"})
        assert spec["formal_charge"] == -1

    def test_charge_plus_plus(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"charge": "++"})
        assert spec["formal_charge"] == 2

    def test_charge_minus_minus(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"charge": "--"})
        assert spec["formal_charge"] == -2

    def test_charge_plus3(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"charge": "+3"})
        assert spec["formal_charge"] == 3

    def test_charge_minus2(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"charge": "-2"})
        assert spec["formal_charge"] == -2

    def test_isotope(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"element": "C", "isotope": "13"})
        assert spec["isotope"] == 13

    def test_hcount_h(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"element": "C", "hcount": "H"})
        assert spec["implicit_hydrogens"] == 1

    def test_hcount_h2(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"element": "N", "hcount": "H2"})
        assert spec["implicit_hydrogens"] == 2

    def test_chiral_at(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"element": "C", "chiral": "@"})
        assert spec["stereochemistry"] == ChiralTag.TH1

    def test_chiral_at_at(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"element": "C", "chiral": "@@"})
        assert spec["stereochemistry"] == ChiralTag.TH2

    def test_wildcard(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"wildcard": "*"})
        assert spec["atomic_number"] == 0

    def test_aromatic_bracket(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"aromatic": "c"})
        assert spec["is_aromatic"] is True
        assert spec["atomic_number"] == 6

    def test_unknown_element_in_bracket(self):
        from chemengine.parsing.smarts import _parse_bracket_atom
        spec = _parse_bracket_atom({"element": "Xx"})
        assert spec["atomic_number"] == 0


class TestParseSmarts:
    def test_simple_chain(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("CCO")
        assert g.num_atoms == 3
        assert g.num_bonds == 2

    def test_branch(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("C(C)C")
        assert g.num_atoms == 3
        assert g.num_bonds == 2

    def test_nested_branch(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("C(C(C)C)C")
        assert g.num_atoms == 5
        assert g.num_bonds == 4

    def test_ring_closure(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("C1CC1")
        assert g.num_atoms == 3
        assert g.num_bonds == 3

    def test_double_bond(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("C=O")
        assert g.num_atoms == 2
        assert g.num_bonds == 1
        assert g.bonds[0].order == BondOrder.DOUBLE

    def test_triple_bond(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("C#N")
        assert g.bonds[0].order == BondOrder.TRIPLE

    def test_dot_disconnected(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("C.C")
        assert g.num_atoms == 2
        assert g.num_bonds == 0

    def test_wildcard_atom(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("[*]C")
        assert g.num_atoms == 2

    def test_bracket_atom_with_charge(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("[O-]C")
        assert g.num_atoms == 2

    def test_ring_num_zero_ignored(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("C0C")
        assert g.num_atoms == 2

    def test_ring_num_large_ignored(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("C101C")
        assert g.num_atoms == 2

    def test_aromatic_bond(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("c:c")
        assert g.num_atoms == 2
        assert g.bonds[0].order == BondOrder.AROMATIC

    def test_empty_tokens(self):
        from chemengine.parsing.smarts import parse_smarts
        g = parse_smarts("")
        assert g.num_atoms == 0


class TestSmartsMatch:
    def test_smarts_match_ethanol(self):
        from chemengine.parsing.smarts import smarts_match
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert smarts_match("CCO", g) is True

    def test_smarts_no_match(self):
        from chemengine.parsing.smarts import smarts_match
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCO")
        assert smarts_match("C#C", g) is False

    def test_smarts_findall(self):
        from chemengine.parsing.smarts import smarts_findall
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCCO")
        matches = smarts_findall("CC", g)
        assert len(matches) >= 1

    def test_smarts_count(self):
        from chemengine.parsing.smarts import smarts_count
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("CCCO")
        count = smarts_count("C", g)
        assert count == 3


# ═══════════════════════════════════════════════════════════════════
# stereochemistry/double_bond.py (53%)
# ═══════════════════════════════════════════════════════════════════

class TestDoubleBondStereo:
    def _build_2butene(self, bond_stereo):
        """Build 2-butene: CH3-CH=CH-CH3."""
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        c3 = builder.add_atom(atomic_number=6)
        c4 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c2, c3, BondOrder.DOUBLE)
        builder.add_bond(c3, c4, BondOrder.SINGLE)
        return builder.build()

    def test_is_stereogenic_double_bond(self):
        from chemengine.stereochemistry.double_bond import is_stereogenic_double_bond
        g = self._build_2butene(BondStereo.NONE)
        assert is_stereogenic_double_bond(g, 1) is True

    def test_not_stereogenic_single_bond(self):
        from chemengine.stereochemistry.double_bond import is_stereogenic_double_bond
        g = self._build_2butene(BondStereo.NONE)
        assert is_stereogenic_double_bond(g, 0) is False

    def test_assign_ez_stereo(self):
        from chemengine.stereochemistry.double_bond import assign_double_bond_stereo
        g = self._build_2butene(BondStereo.NONE)
        center = assign_double_bond_stereo(g, 1)
        assert center is not None
        assert center.category == StereoCategory.DOUBLE_BOND
        assert center.bond_stereo in (BondStereo.E, BondStereo.Z)

    def test_assign_none_for_non_stereogenic(self):
        from chemengine.stereochemistry.double_bond import assign_double_bond_stereo
        g = self._build_2butene(BondStereo.NONE)
        center = assign_double_bond_stereo(g, 0)
        assert center is None

    def test_detect_all_double_bonds(self):
        from chemengine.stereochemistry.double_bond import detect_double_bond_stereo
        g = self._build_2butene(BondStereo.NONE)
        centers = detect_double_bond_stereo(g)
        assert len(centers) == 1

    def test_ethylene_not_stereogenic(self):
        from chemengine.stereochemistry.double_bond import is_stereogenic_double_bond
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        g = builder.build()
        # Each C has 1 neighbor (the other C), but neighbors beyond
        # the double bond partner are none. len(n1)=0, len(n2)=0 → False
        assert is_stereogenic_double_bond(g, 0) is False

    def test_symmetric_substituents_with_implicit_h_are_stereogenic(self):
        """Cl-C=C-Cl with implicit H on each C IS stereogenic.

        Each carbon has Cl + implicit H as substituents, which are distinct.
        1,2-dichloroethene has E and Z isomers.
        """
        from chemengine.stereochemistry.double_bond import is_stereogenic_double_bond
        builder = MolecularGraphBuilder()
        cl1 = builder.add_atom(atomic_number=17)
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        cl2 = builder.add_atom(atomic_number=17)
        builder.add_bond(cl1, c1, BondOrder.SINGLE)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        builder.add_bond(c2, cl2, BondOrder.SINGLE)
        g = builder.build()
        # Each C has Cl + implicit H → stereogenic
        assert is_stereogenic_double_bond(g, 1) is True


# ═══════════════════════════════════════════════════════════════════
# detection/aromaticity.py (58%)
# ═══════════════════════════════════════════════════════════════════

class TestAromaticityDetection:
    def test_benzene_is_aromatic(self):
        from chemengine.detection.aromaticity import assess_all_rings
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("c1ccccc1")
        results = assess_all_rings(g)
        assert len(results) >= 1
        assert results[0].is_aromatic is True

    def test_cyclohexane_not_aromatic(self):
        from chemengine.detection.aromaticity import assess_all_rings
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("C1CCCCC1")
        results = assess_all_rings(g)
        assert len(results) >= 1
        assert results[0].is_aromatic is False

    def test_pyrrole_aromatic(self):
        from chemengine.detection.aromaticity import assess_all_rings
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("c1cc[nH]c1")
        results = assess_all_rings(g)
        assert len(results) >= 1
        assert results[0].is_aromatic is True

    def test_furan_aromatic(self):
        from chemengine.detection.aromaticity import assess_all_rings
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("c1ccoc1")
        results = assess_all_rings(g)
        assert len(results) >= 1
        assert results[0].is_aromatic is True

    def test_thiophene_aromatic(self):
        from chemengine.detection.aromaticity import assess_all_rings
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("c1ccsc1")
        results = assess_all_rings(g)
        assert len(results) >= 1
        assert results[0].is_aromatic is True

    def test_pyridine_aromatic(self):
        from chemengine.detection.aromaticity import assess_all_rings
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("c1ccncc1")
        results = assess_all_rings(g)
        assert len(results) >= 1
        assert results[0].is_aromatic is True

    def test_non_aromatic_pure_single_bonds(self):
        from chemengine.core.bonds import BondOrder
        from chemengine.core.graph import MolecularGraphBuilder
        from chemengine.core.substructure import Ring
        from chemengine.detection.aromaticity import _is_conjugated_ring
        builder = MolecularGraphBuilder()
        atoms = [builder.add_atom(atomic_number=6) for _ in range(3)]
        for i in range(3):
            builder.add_bond(atoms[i], atoms[(i + 1) % 3], BondOrder.SINGLE)
        g = builder.build()
        ring = Ring(atom_indices=tuple(atoms))
        assert _is_conjugated_ring(g, ring.atom_indices) is False

    def test_assess_ring_pre_marked_aromatic(self):
        from chemengine.core.substructure import Ring
        from chemengine.detection.aromaticity import AromaticityType, assess_ring_aromaticity
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("c1ccccc1")
        ring = Ring(atom_indices=(0, 1, 2, 3, 4, 5), is_aromatic=True)
        result = assess_ring_aromaticity(g, ring)
        assert result.result == AromaticityType.AROMATIC

    def test_assign_aromaticity_updates_flags(self):
        from chemengine.detection.aromaticity import assign_aromaticity
        from chemengine.parsing.smiles import parse_smiles
        g = parse_smiles("c1ccccc1")
        updated = assign_aromaticity(g)
        assert len(updated) >= 1

    def test_assess_anti_aromatic(self):
        """Test anti-aromatic detection (cyclobutadiene = 4π)."""
        from chemengine.core.bonds import BondOrder
        from chemengine.core.graph import MolecularGraphBuilder
        from chemengine.detection.aromaticity import _count_pi_electrons_ring
        # Build cyclobutadiene: 4 carbons with alternating double bonds
        builder = MolecularGraphBuilder()
        c = [builder.add_atom(atomic_number=6) for _ in range(4)]
        builder.add_bond(c[0], c[1], BondOrder.DOUBLE)
        builder.add_bond(c[1], c[2], BondOrder.SINGLE)
        builder.add_bond(c[2], c[3], BondOrder.DOUBLE)
        builder.add_bond(c[3], c[0], BondOrder.SINGLE)
        g = builder.build()
        pi = _count_pi_electrons_ring(g, tuple(c))
        assert pi == 4  # 4 π electrons → anti-aromatic

    def test_borole_non_aromatic(self):
        """Boron in ring → 0 pi electrons from B."""
        from chemengine.core.bonds import BondOrder
        from chemengine.core.graph import MolecularGraphBuilder
        from chemengine.detection.aromaticity import _count_pi_electrons_ring
        builder = MolecularGraphBuilder()
        b = builder.add_atom(atomic_number=5)
        c = [builder.add_atom(atomic_number=6) for _ in range(4)]
        # Ring: B-C=C-C=C
        builder.add_bond(b, c[0], BondOrder.SINGLE)
        builder.add_bond(c[0], c[1], BondOrder.DOUBLE)
        builder.add_bond(c[1], c[2], BondOrder.SINGLE)
        builder.add_bond(c[2], c[3], BondOrder.DOUBLE)
        builder.add_bond(c[3], b, BondOrder.SINGLE)
        g = builder.build()
        pi = _count_pi_electrons_ring(g, (b, c[0], c[1], c[2], c[3]))
        assert pi == 4  # 4 sp² carbons × 1 + B × 0 (c[0] has C=C double bond)

    def test_ring_too_small_not_conjugated(self):
        from chemengine.core.bonds import BondOrder
        from chemengine.core.graph import MolecularGraphBuilder
        from chemengine.detection.aromaticity import _is_conjugated_ring
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        g = builder.build()
        assert _is_conjugated_ring(g, (c1, c2)) is False  # only 2 atoms


# ═══════════════════════════════════════════════════════════════════
# properties/descriptors.py (58%)
# ═══════════════════════════════════════════════════════════════════

class TestPropertyDescriptors:
    def test_compute_property_dispatch(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_property
        g = parse_smiles("CCO")
        assert compute_property(g, "formula") == "C2H6O"
        assert isinstance(compute_property(g, "mass"), float)
        assert isinstance(compute_property(g, "weight"), float)
        assert compute_property(g, "heavy_atoms") == 3
        assert isinstance(compute_property(g, "num_rings"), int)

    def test_compute_property_unknown_raises(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_property
        g = parse_smiles("CCO")
        with pytest.raises(KeyError, match="Unknown property"):
            compute_property(g, "nonexistent")

    def test_tpsa_water(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_tpsa
        g = parse_smiles("O")
        tpsa = compute_tpsa(g)
        assert tpsa > 0

    def test_tpsa_carbonyl(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_tpsa
        g = parse_smiles("C=O")
        tpsa = compute_tpsa(g)
        assert tpsa > 0

    def test_tpsa_charged_oxygen(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_tpsa
        g = parse_smiles("[O-]")
        tpsa = compute_tpsa(g)
        assert tpsa > 0

    def test_tpsa_nplus(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_tpsa
        g = parse_smiles("[NH4+]")
        tpsa = compute_tpsa(g)
        assert tpsa > 0

    def test_tpsa_sulfoxide(self):
        from chemengine.core.bonds import BondOrder
        from chemengine.core.graph import MolecularGraphBuilder
        from chemengine.properties.descriptors import compute_tpsa
        builder = MolecularGraphBuilder()
        s = builder.add_atom(atomic_number=16)
        o = builder.add_atom(atomic_number=8)
        builder.add_bond(s, o, BondOrder.DOUBLE)
        g = builder.build()
        tpsa = compute_tpsa(g)
        assert tpsa > 0

    def test_tpsa_sulfone(self):
        from chemengine.core.bonds import BondOrder
        from chemengine.core.graph import MolecularGraphBuilder
        from chemengine.properties.descriptors import compute_tpsa
        builder = MolecularGraphBuilder()
        s = builder.add_atom(atomic_number=16)
        o1 = builder.add_atom(atomic_number=8)
        o2 = builder.add_atom(atomic_number=8)
        builder.add_bond(s, o1, BondOrder.DOUBLE)
        builder.add_bond(s, o2, BondOrder.DOUBLE)
        g = builder.build()
        tpsa = compute_tpsa(g)
        assert tpsa > 50  # sulfone

    def test_tpsa_amine_sp2(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_tpsa
        g = parse_smiles("C=NC")
        tpsa = compute_tpsa(g)
        assert tpsa > 0

    def test_tpsa_no_h_nitrogen(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_tpsa
        g = parse_smiles("C#N")
        tpsa = compute_tpsa(g)
        assert tpsa > 0

    def test_logp_simple(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_logp
        g = parse_smiles("CCCCCC")
        logp = compute_logp(g)
        assert logp > 0  # hydrocarbon → positive logP

    def test_logp_with_heteroatoms(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_logp
        g = parse_smiles("CCO")
        logp = compute_logp(g)
        assert isinstance(logp, float)

    def test_logp_halogen(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_logp
        g = parse_smiles("CCCl")
        logp_ccc = compute_logp(g)
        g2 = parse_smiles("CCBr")
        logp_ccbr = compute_logp(g2)
        assert logp_ccbr > logp_ccc  # Br > Cl

    def test_logp_iodine(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_logp
        g = parse_smiles("CI")
        logp = compute_logp(g)
        assert logp > 0

    def test_logp_sulfur(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_logp
        g = parse_smiles("CS")
        logp = compute_logp(g)
        assert isinstance(logp, float)

    def test_hba_basic(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_hba
        g = parse_smiles("CCO")
        assert compute_hba(g) == 1  # one O

    def test_hba_excludes_quaternary_nitrogen(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_hba
        g = parse_smiles("[NH4+]")
        # N+ with 4 H bonds → not HBA
        assert compute_hba(g) == 0

    def test_hba_fluorine(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_hba
        g = parse_smiles("F")
        assert compute_hba(g) == 1

    def test_hbd_basic(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_hbd
        g = parse_smiles("CCO")
        assert compute_hbd(g) == 1  # one O-H

    def test_hbd_amine(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_hbd
        g = parse_smiles("CN")
        assert compute_hbd(g) == 1

    def test_rotatable_bonds_ethane(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_rotatable_bonds
        g = parse_smiles("CC")
        # Both atoms are terminal (degree 1), so 0 rotatable
        assert compute_rotatable_bonds(g) == 0

    def test_rotatable_bonds_propane(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_rotatable_bonds
        g = parse_smiles("CCC")
        # C1-C2-C3: both C-C bonds have a terminal carbon, so 0 rotatable
        assert compute_rotatable_bonds(g) == 0

    def test_fraction_csp3_all_sp3(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_fraction_csp3
        g = parse_smiles("CCCC")
        assert compute_fraction_csp3(g) == 1.0

    def test_fraction_csp3_mixed(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_fraction_csp3
        g = parse_smiles("C=C")
        assert compute_fraction_csp3(g) == 0.0

    def test_fraction_csp3_no_carbon(self):
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_fraction_csp3
        g = parse_smiles("O")
        assert compute_fraction_csp3(g) == 0.0

    def test_property_registry_keys(self):
        from chemengine.properties.descriptors import PROPERTY_REGISTRY
        expected = {"tpsa", "logp", "hba", "hbd", "rotatable_bonds", "fraction_csp3"}
        assert set(PROPERTY_REGISTRY.keys()) == expected

    def test_tpsa_n_with_o_bond(self):
        """Test nitrogen bonded to oxygen (N-O fragment)."""
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_tpsa
        g = parse_smiles("C[N+](=O)[O-]")
        tpsa = compute_tpsa(g)
        assert tpsa > 0

    def test_hba_n_with_two_h(self):
        """Test NH2 as HBA."""
        from chemengine.parsing.smiles import parse_smiles
        from chemengine.properties.descriptors import compute_hba
        g = parse_smiles("N")
        assert compute_hba(g) == 1
