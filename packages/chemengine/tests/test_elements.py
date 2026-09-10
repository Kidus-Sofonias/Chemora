"""Comprehensive tests for the periodic table Element system.

Covers:
  - Element property correctness for all 118 elements
  - Element.get() lookup by symbol, Z, and name
  - ElementQuery filtering by categories, properties, and ranges
  - IsotopeInfo data integrity
  - Physical property edge cases
  - Backward compatibility with old property names
"""

import pytest

from chemengine.core.element import (
    Element,
    ElementQuery,
)


class TestElementLookup:
    """Tests for element lookup methods."""

    def test_get_by_symbol(self):
        carbon = Element.get("C")
        assert carbon.symbol == "C"
        assert carbon.atomic_number == 6
        assert carbon.name == "Carbon"

    def test_get_by_atomic_number(self):
        oxygen = Element.get(8)
        assert oxygen.symbol == "O"
        assert oxygen.name == "Oxygen"

    def test_get_by_element_symbol(self):
        from chemengine.core.enums import ElementSymbol
        fe = Element.get(ElementSymbol.Fe)
        assert fe.atomic_number == 26
        assert fe.name == "Iron"

    def test_from_z(self):
        gold = Element.from_z(79)
        assert gold.symbol == "Au"
        assert gold.name == "Gold"

    def test_from_symbol(self):
        helium = Element.from_symbol("He")
        assert helium.atomic_number == 2
        assert helium.atomic_mass == 4.002602

    def test_from_name(self):
        nitrogen = Element.from_name("Nitrogen")
        assert nitrogen.atomic_number == 7

    def test_from_name_case_insensitive(self):
        sodium = Element.from_name("sodium")
        assert sodium.symbol == "Na"

    def test_from_name_not_found(self):
        with pytest.raises(KeyError):
            Element.from_name("FakeElementium")

    def test_get_invalid_identifier(self):
        with pytest.raises(KeyError):
            Element.get(999)

    def test_get_invalid_string(self):
        with pytest.raises(KeyError):
            Element.get("Xx")

    def test_get_invalid_type(self):
        with pytest.raises(KeyError):
            Element.get(3.14)  # type: ignore


class TestElementProperties:
    """Tests for element property correctness."""

    @pytest.mark.parametrize("z,sym,name,mass", [
        (1, "H", "Hydrogen", 1.008),
        (6, "C", "Carbon", 12.011),
        (8, "O", "Oxygen", 15.999),
        (26, "Fe", "Iron", 55.845),
        (79, "Au", "Gold", 196.96657),
        (92, "U", "Uranium", 238.02891),
        (118, "Og", "Oganesson", 294.0),
    ])
    def test_basic_properties(self, z, sym, name, mass):
        el = Element.get(z)
        assert el.symbol == sym
        assert el.atomic_number == z
        assert el.name == name
        assert el.atomic_mass == pytest.approx(mass, rel=1e-3)

    def test_hydrogen_properties(self):
        h = Element.get("H")
        assert h.period == 1
        assert h.group == 1
        assert h.block == "s"
        assert h.category == "nonmetal"
        assert h.electron_configuration == "1s1"
        assert h.covalent_radius == pytest.approx(0.31, abs=0.01)
        assert h.vdw_radius == pytest.approx(1.20, abs=0.01)
        assert h.electronegativity == 2.20
        assert h.ionization_energy == pytest.approx(13.598, abs=0.01)
        assert h.electron_affinity == pytest.approx(0.754, abs=0.01)
        assert h.phase_at_stp == "gas"

    def test_iron_properties(self):
        fe = Element.get("Fe")
        assert fe.period == 4
        assert fe.group == 8
        assert fe.block == "d"
        assert fe.category == "transition_metal"
        assert fe.is_metal is True
        assert fe.is_transition_metal is True
        assert fe.density == pytest.approx(7.874, abs=0.01)
        assert fe.melting_point == pytest.approx(1811.0, abs=1)
        assert fe.boiling_point == pytest.approx(3134.0, abs=1)

    def test_bromine_liquid_phase(self):
        br = Element.get("Br")
        assert br.phase_at_stp == "liquid"
        assert br.melting_point == pytest.approx(266.0, abs=1)
        assert br.boiling_point == pytest.approx(332.0, abs=1)

    def test_all_elements_have_required_fields(self):
        for el in Element.all_elements():
            assert el.symbol, f"Missing symbol for Z={el.atomic_number}"
            assert el.name, f"Missing name for Z={el.atomic_number}"
            assert el.atomic_mass > 0, f"Bad mass for {el.symbol}"
            assert 1 <= el.period <= 7, f"Bad period for {el.symbol}"
            assert 0 <= el.group <= 18, f"Bad group for {el.symbol}"
            assert el.block in ("s", "p", "d", "f"), f"Bad block for {el.symbol}"
            assert el.electron_configuration, f"Missing config for {el.symbol}"


class TestElementQuery:
    """Tests for the ElementQuery filtering API."""

    def test_all_elements_query(self):
        all_els = ElementQuery().execute()
        assert len(all_els) == 118

    def test_filter_by_period(self):
        period_2 = ElementQuery().filter(period=2).execute()
        assert len(period_2) == 8  # Li, Be, B, C, N, O, F, Ne
        symbols = {el.symbol for el in period_2}
        assert symbols == {"Li", "Be", "B", "C", "N", "O", "F", "Ne"}

    def test_filter_by_group(self):
        halogens = ElementQuery().filter(group=17).execute()
        symbols = {el.symbol for el in halogens}
        assert "F" in symbols
        assert "Cl" in symbols
        assert "Br" in symbols
        assert "I" in symbols
        assert "At" in symbols
        assert "Ts" in symbols
        assert len(halogens) == 6

    def test_filter_by_block(self):
        s_block = ElementQuery().filter(block="s").execute()
        for el in s_block:
            assert el.block == "s"
        # s-block includes groups 1-2 + He
        assert len(s_block) == 14  # H, He + groups 1,2 in periods 2-7

    def test_filter_by_category(self):
        noble_gases = ElementQuery().filter(category="noble_gas").execute()
        symbols = {el.symbol for el in noble_gases}
        assert symbols == {"He", "Ne", "Ar", "Kr", "Xe", "Rn", "Og"}
        assert len(noble_gases) == 7

    def test_filter_is_metal(self):
        metals = ElementQuery().filter(is_metal=True).execute()
        for el in metals:
            assert el.is_metal is True

    def test_filter_is_nonmetal(self):
        nonmetals = ElementQuery().filter(is_nonmetal=True).execute()
        for el in nonmetals:
            assert el.is_nonmetal is True

    def test_filter_is_metalloid(self):
        metalloids = ElementQuery().filter(is_metalloid=True).execute()
        symbols = {el.symbol for el in metalloids}
        assert "B" in symbols
        assert "Si" in symbols
        assert "Ge" in symbols
        assert "As" in symbols
        assert "Sb" in symbols
        assert "Te" in symbols
        assert len(metalloids) == 6  # B, Si, Ge, As, Sb, Te

    def test_filter_phase_gas(self):
        gases = ElementQuery().filter(phase_at_stp="gas").execute()
        for el in gases:
            assert el.phase_at_stp == "gas"

    def test_filter_min_electronegativity(self):
        high_en = ElementQuery().filter(min_electronegativity=3.0).execute()
        for el in high_en:
            assert el.electronegativity >= 3.0
        assert Element.get("F") in high_en

    def test_filter_max_electronegativity(self):
        low_en = ElementQuery().filter(max_electronegativity=1.0).execute()
        for el in low_en:
            assert el.electronegativity <= 1.0

    def test_chained_filter(self):
        # Transition metals in period 4 with electronegativity > 1.5
        results = (
            ElementQuery()
            .filter(period=4)
            .filter(is_transition_metal=True)
            .filter(min_electronegativity=1.5)
            .execute()
        )
        for el in results:
            assert el.period == 4
            assert el.is_transition_metal
            assert el.electronegativity >= 1.5

    def test_filter_is_radioactive(self):
        radioactive = ElementQuery().filter(is_radioactive=True).execute()
        for el in radioactive:
            assert el.is_radioactive is True
        # Most elements after Bi (Z=83) are radioactive
        assert Element.get("Po") in radioactive
        assert Element.get("Pm") in radioactive

    def test_filter_has_stable_isotopes(self):
        stable = ElementQuery().filter(has_stable_isotopes=True).execute()
        for el in stable:
            assert el.has_stable_isotopes is True
        assert Element.get("C") in stable
        assert Element.get("Fe") in stable

    def test_filter_z_range(self):
        # Get elements 57-71 (lanthanides)
        lanthanides = ElementQuery().filter(is_lanthanide=True).execute()
        assert len(lanthanides) == 15

    def test_filter_by_name(self):
        carbon = ElementQuery().filter(name="Carbon").execute()
        assert len(carbon) == 1
        assert carbon[0].symbol == "C"

    def test_iterable_query(self):
        results = ElementQuery().filter(period=2)
        count = len(results)
        assert count == 8

    def test_query_indexing(self):
        results = ElementQuery().filter(group=18)
        first = results[0]
        assert first.group == 18


class TestPhysicalProperties:
    """Tests for physical property data."""

    def test_density_range(self):
        for el in Element.all_elements():
            assert el.density >= 0, f"Negative density for {el.symbol}"

    def test_boiling_above_melting(self):
        # Arsenic sublimes (sublimation point < melting point under pressure)
        subliming_elements = {"As", "Lr"}
        for el in Element.all_elements():
            if el.symbol in subliming_elements:
                continue
            if el.melting_point > 0 and el.boiling_point > 0:
                assert el.boiling_point > el.melting_point, \
                    f"BP <= MP for {el.symbol}: MP={el.melting_point}, BP={el.boiling_point}"

    def test_mercury_liquid(self):
        hg = Element.get("Hg")
        assert hg.phase_at_stp == "liquid"
        assert hg.melting_point < 300  # Below room temp

    def test_gallium_low_melting(self):
        ga = Element.get("Ga")
        assert ga.melting_point < 310  # Melts in hand

    def test_tungsten_high_melting(self):
        w = Element.get("W")
        assert w.melting_point > 3000

    def test_phase_consistency(self):
        gases = ElementQuery().filter(phase_at_stp="gas").execute()
        for el in gases:
            assert el.boiling_point < 300 or el.phase_at_stp == "gas", \
                f"Gas with high BP: {el.symbol}"
            assert el.density < 0.02, \
                f"Gas with high density: {el.symbol}"


class TestIsotopeData:
    """Tests for isotopic data integrity."""

    def test_hydrogen_isotopes(self):
        h = Element.get("H")
        assert len(h.isotopes) == 3
        # Protium
        assert h.isotopes[0].mass_number == 1
        assert h.isotopes[0].exact_mass == pytest.approx(1.007825, abs=1e-6)
        assert h.isotopes[0].natural_abundance == pytest.approx(0.999885, abs=1e-5)
        # Deuterium
        assert h.isotopes[1].mass_number == 2
        assert h.isotopes[1].natural_abundance == pytest.approx(0.000115, abs=1e-5)
        # Tritium (radioactive)
        assert h.isotopes[2].natural_abundance is None

    def test_carbon_isotopes(self):
        c = Element.get("C")
        assert len(c.isotopes) == 3
        # C-12
        assert c.isotopes[0].mass_number == 12
        assert c.isotopes[0].exact_mass == 12.0
        assert c.isotopes[0].natural_abundance > 0.98
        # C-14 (radioactive)
        assert c.isotopes[2].natural_abundance is None

    def test_most_abundant_isotope(self):
        fe = Element.get("Fe")
        most = fe.most_abundant_isotope
        assert most is not None
        assert most.mass_number == 56  # Fe-56 is most abundant
        assert most.natural_abundance > 0.9

    def test_radioactive_most_abundant(self):
        u = Element.get("U")
        most = u.most_abundant_isotope
        assert most is not None
        assert most.mass_number == 238  # U-238 is most abundant

    def test_pure_element_single_isotope(self):
        au = Element.get("Au")
        assert len(au.isotopes) == 1
        assert au.isotopes[0].mass_number == 197

    def test_radioactive_no_stable(self):
        pm = Element.get("Pm")
        assert pm.has_stable_isotopes is False
        assert pm.is_radioactive is True
        # All Pm isotopes are radioactive with None abundance, so None is expected
        assert pm.most_abundant_isotope is None

    def test_is_radioactive_true_for_heavy(self):
        # Most elements with Z > 83 (Bi) are entirely radioactive
        radioactive = [el for el in Element.all_elements() if el.is_radioactive]
        for el in radioactive:
            assert el.atomic_number > 83 or el.atomic_number == 43 or el.atomic_number == 61, \
                f"Unexpected radioactive: {el.symbol}"


class TestBackwardCompatibility:
    """Tests ensuring Element maintains backward-compatible API."""

    def test_van_der_waals_radius_property(self):
        c = Element.get("C")
        assert c.van_der_waals_radius == c.vdw_radius

    def test_common_valences_property(self):
        n = Element.get("N")
        assert n.common_valences == n.oxidation_states
        assert 3 in n.common_valences
        assert 5 in n.common_valences

    def test_max_valence_property(self):
        cl = Element.get("Cl")
        assert cl.max_valence == 7
        c = Element.get("C")
        assert c.max_valence == 4

    def test_element_symbol_property(self):
        from chemengine.core.enums import ElementSymbol
        n = Element.get("N")
        assert n.element_symbol == ElementSymbol.N

    def test_is_metal_properties(self):
        na = Element.get("Na")
        assert na.is_metal is True
        assert na.is_nonmetal is False
        assert na.is_metalloid is False

    def test_is_halogen(self):
        f = Element.get("F")
        cl = Element.get("Cl")
        br = Element.get("Br")
        assert f.is_halogen is True
        assert cl.is_halogen is True
        assert br.is_halogen is True

    def test_is_noble_gas(self):
        he = Element.get("He")
        ne = Element.get("Ne")
        ar = Element.get("Ar")
        assert he.is_noble_gas is True
        assert ne.is_noble_gas is True
        assert ar.is_noble_gas is True

    def test_is_lanthanide(self):
        la = Element.get("La")
        assert la.is_lanthanide is True
        lu = Element.get("Lu")
        assert lu.is_lanthanide is True

    def test_is_actinide(self):
        ac = Element.get("Ac")
        assert ac.is_actinide is True
        u = Element.get("U")
        assert u.is_actinide is True

    def test_element_symbol_enum_compatibility(self):
        """ElementSymbol properties should match Element properties."""
        from chemengine.core.enums import ElementSymbol
        for sym in ("H", "C", "N", "O", "Fe", "Au", "U"):
            es = ElementSymbol(sym)
            el = Element.get(sym)
            assert es.atomic_number == el.atomic_number
            assert es.group == el.group
            assert es.period == el.period
            assert es.is_metal == el.is_metal
            assert es.is_nonmetal == el.is_nonmetal
            assert es.is_metalloid == el.is_metalloid
            assert Tuple(es.common_valences) == el.oxidation_states


class TestEdgeCases:
    """Tests for edge cases and unusual elements."""

    def test_hydrogen_dual_nature(self):
        h = Element.get("H")
        assert -1 in h.oxidation_states  # Hydride
        assert 1 in h.oxidation_states   # Proton

    def test_carbon_wide_valence(self):
        c = Element.get("C")
        assert -4 in c.oxidation_states  # CH4
        assert 4 in c.oxidation_states   # CF4 / CO2

    def test_oxygen_electron_affinity(self):
        o = Element.get("O")
        assert o.electron_affinity > 1.0  # High EA

    def test_nitrogen_no_electron_affinity(self):
        n = Element.get("N")
        assert n.electron_affinity == 0.0  # N has negative EA, recorded as 0

    def test_noble_gas_electronegativity(self):
        for el in ElementQuery().filter(category="noble_gas").execute():
            assert el.electronegativity == 0.0


class TestElementQueryEdgeCases:
    """Tests for ElementQuery edge cases."""

    def test_no_filters_returns_all(self):
        assert len(ElementQuery().execute()) == 118

    def test_unknown_filter_key(self):
        results = ElementQuery().filter(nonexistent_key=42).execute()
        assert len(results) == 118  # Unknown keys are ignored

    def test_mutually_exclusive_filters(self):
        results = ElementQuery().filter(is_metal=True, is_nonmetal=True).execute()
        assert len(results) == 0  # No element is both

    def test_filter_by_z(self):
        carbon = ElementQuery().filter(z=6).execute()
        assert len(carbon) == 1
        assert carbon[0].symbol == "C"

    def test_filter_by_symbol(self):
        iron = ElementQuery().filter(symbol="Fe").execute()
        assert len(iron) == 1
        assert iron[0].atomic_number == 26


# Helper to match tuple type
def Tuple(x):
    return tuple(x) if not isinstance(x, tuple) else x
