"""Tests for the electron configuration subsystem (rule-driven, with ions)."""
import pytest

from chemengine.education.electron_config import (
    TRANSITION_METAL_EXCEPTIONS,
    ElectronConfiguration,
    ElectronConfigurator,
    OrbitalOccupancy,
    calculate_electron_configuration,
)


def _full(symbol: str, charge: int = 0) -> str:
    return ElectronConfigurator().configure(symbol=symbol, charge=charge).full


# ── Rule-driven neutral configurations (Madelung/Aufbau) ──
class TestAufbauNeutral:
    def test_hydrogen(self):
        c = ElectronConfigurator().configure(1)
        assert c.full == "1s1"
        assert c.shorthand == "1s1"
        assert c.valence_electrons == 1
        assert c.charge == 0
        assert c.electron_type == "neutral"

    def test_carbon(self):
        c = ElectronConfigurator().configure(symbol="C")
        assert c.full == "1s2 2s2 2p2"
        assert c.shorthand == "[He] 2s2 2p2"
        assert c.valence_electrons == 4
        assert c.unpaired_electrons == 2

    def test_oxygen(self):
        c = ElectronConfigurator().configure(symbol="O")
        assert c.full == "1s2 2s2 2p4"
        assert c.unpaired_electrons == 2  # 2p4 -> 2 unpaired (Hund)

    def test_nitrogen_unpaired(self):
        assert ElectronConfigurator().configure(symbol="N").unpaired_electrons == 3

    def test_neon_noble_gas(self):
        c = ElectronConfigurator().configure(symbol="Ne")
        assert c.full == "1s2 2s2 2p6"
        assert c.shorthand == "[He] 2s2 2p6"

    def test_argon(self):
        assert ElectronConfigurator().configure(symbol="Ar").shorthand == "[Ne] 3s2 3p6"

    def test_iron(self):
        c = ElectronConfigurator().configure(symbol="Fe")
        assert c.full == "1s2 2s2 2p6 3s2 3p6 3d6 4s2"
        assert c.shorthand == "[Ar] 3d6 4s2"

    def test_xenon(self):
        assert (
            ElectronConfigurator().configure(symbol="Xe").shorthand
            == "[Kr] 4d10 5s2 5p6"
        )

    def test_shell_and_subshell_distribution(self):
        c = ElectronConfigurator().configure(symbol="O")
        assert c.shell_distribution == {1: 2, 2: 6}
        assert c.subshell_distribution == {"1s": 2, "2s": 2, "2p": 4}


# ── Documented transition-metal exceptions ──
class TestTransitionMetalExceptions:
    @pytest.mark.parametrize(
        "symbol,z,expected_subshell",
        [
            ("Cr", 24, "3d5 4s1"),
            ("Cu", 29, "3d10 4s1"),
            ("Nb", 41, "4d4 5s1"),
            ("Mo", 42, "4d5 5s1"),
            ("Ru", 44, "4d7 5s1"),
            ("Rh", 45, "4d8 5s1"),
            ("Pd", 46, "4d10"),
            ("Ag", 47, "4d10 5s1"),
            ("Pt", 78, "5d9 6s1"),
            ("Au", 79, "5d10 6s1"),
        ],
    )
    def test_ground_state(self, symbol, z, expected_subshell):
        assert z in TRANSITION_METAL_EXCEPTIONS
        assert ElectronConfigurator().configure(z).full.endswith(expected_subshell)

    def test_non_exception_metal_unchanged(self):
        assert "Fe" not in TRANSITION_METAL_EXCEPTIONS
        assert _full("Fe") == "1s2 2s2 2p6 3s2 3p6 3d6 4s2"


# ── Ion / charged-species support ──
class TestIons:
    @pytest.mark.parametrize(
        "symbol,charge,expected",
        [
            ("Fe", 2, "1s2 2s2 2p6 3s2 3p6 3d6"),
            ("Fe", 3, "1s2 2s2 2p6 3s2 3p6 3d5"),
            ("Cu", 1, "1s2 2s2 2p6 3s2 3p6 3d10"),
            ("Cu", 2, "1s2 2s2 2p6 3s2 3p6 3d9"),
            ("Cr", 3, "1s2 2s2 2p6 3s2 3p6 3d3"),
            ("Na", 1, "1s2 2s2 2p6"),
            ("Ca", 2, "1s2 2s2 2p6 3s2 3p6"),
            ("O", -2, "1s2 2s2 2p6"),
            ("Cl", -1, "1s2 2s2 2p6 3s2 3p6"),
            ("S", 2, "1s2 2s2 2p6 3s2 3p2"),
        ],
    )
    def test_ion_config(self, symbol, charge, expected):
        assert _full(symbol, charge) == expected

    def test_iron_2plus_electron_type(self):
        c = ElectronConfigurator().configure(symbol="Fe", charge=2)
        assert c.electron_type == "cation"
        assert c.charge == 2
        assert c.unpaired_electrons == 4  # 3d6

    def test_oxide_anion(self):
        c = ElectronConfigurator().configure(symbol="O", charge=-2)
        assert c.electron_type == "anion"
        assert c.full == "1s2 2s2 2p6"  # [He]2s2 2p6 == Ne-like core

    def test_transition_metal_loses_ns_before_nd(self):
        # Mo neutral is 4d5 5s1; removing the ns electron leaves 4d5.
        assert _full("Mo", 1) == "1s2 2s2 2p6 3s2 3p6 3d10 4s2 4p6 4d5"


# ── Element lookup & facade ──
class TestElementLookup:
    def test_by_atomic_number(self):
        assert ElectronConfigurator().configure(6).symbol == "C"

    def test_by_symbol(self):
        c = ElectronConfigurator().configure(symbol="Fe")
        assert c.full.startswith("1s2 2s2 2p6 3s2 3p6")

    def test_by_name(self):
        assert ElectronConfigurator().configure(name="Iron").symbol == "Fe"

    def test_for_element_string(self):
        assert ElectronConfigurator().for_element("C").full == "1s2 2s2 2p2"

    def test_for_element_object(self):
        from chemengine.core.element import Element

        c = ElectronConfigurator().for_element(Element.from_z(6))
        assert c.full == "1s2 2s2 2p2"

    def test_module_function(self):
        c = calculate_electron_configuration("Fe", charge=3)
        assert c.full.endswith("3d5")
        assert isinstance(c, ElectronConfiguration)

    def test_no_identifier_raises(self):
        with pytest.raises(ValueError):
            ElectronConfigurator().configure()

    def test_conflicting_identifiers_raise(self):
        with pytest.raises(ValueError):
            ElectronConfigurator().configure(6, symbol="C")

    def test_invalid_atomic_number_raises(self):
        with pytest.raises(ValueError):
            ElectronConfigurator().configure(0)
        with pytest.raises(ValueError):
            ElectronConfigurator().configure(119)

    def test_invalid_symbol_raises(self):
        with pytest.raises(KeyError):
            ElectronConfigurator().configure(symbol="Zz")


# ── Orbital occupancy model ──
class TestOrbitalOccupancy:
    def test_derived_fields(self):
        occ = OrbitalOccupancy(orbital="2p", electrons=3, capacity=6)
        assert occ.subshell == "p"
        assert occ.shell == 2
        assert not occ.is_full
        assert not occ.is_empty

    def test_capacities(self):
        assert OrbitalOccupancy("2s", 2, 2).is_full
        assert OrbitalOccupancy("2s", 0, 2).is_empty


# ── Determinism ──
class TestDeterminism:
    def test_repeatable(self):
        ec = ElectronConfigurator()
        assert ec.configure(symbol="Mo", charge=1).full == ec.configure(
            symbol="Mo", charge=1
        ).full

    def test_all_elements_deterministic(self):
        ec = ElectronConfigurator()
        seen = set()
        for z in range(1, 119):
            key = ec.configure(z).full
            assert key not in seen
            seen.add(key)
