"""
Performance benchmarks for the periodic table Element system.

Covers:
  - Element.get() lookup throughput
  - ElementQuery filtering performance
  - Property access overhead
  - Isotope data access
"""

import pytest
from chemengine.core.element import Element, ElementQuery


class TestElementLookupBenchmarks:
    """Benchmarks for element lookup operations."""

    def test_lookup_by_symbol(self, benchmark):
        """Benchmark Element.get() by symbol string."""
        result = benchmark(lambda: Element.get("Fe"))
        assert result.atomic_number == 26

    def test_lookup_by_atomic_number(self, benchmark):
        """Benchmark Element.get() by atomic number."""
        result = benchmark(lambda: Element.get(79))
        assert result.symbol == "Au"

    def test_lookup_all_elements_by_symbol(self, benchmark):
        """Benchmark looking up all 118 elements by symbol."""
        symbols = [el.symbol for el in Element.all_elements()]
        def lookup_all():
            return [Element.get(sym) for sym in symbols]
        results = benchmark(lookup_all)
        assert len(results) == 118

    def test_lookup_all_elements_by_z(self, benchmark):
        """Benchmark looking up all 118 elements by atomic number."""
        def lookup_all():
            return [Element.from_z(z) for z in range(1, 119)]
        results = benchmark(lookup_all)
        assert len(results) == 118

    def test_from_name_lookup(self, benchmark):
        """Benchmark name-based element lookup."""
        result = benchmark(lambda: Element.from_name("Carbon"))
        assert result.symbol == "C"


class TestPropertyAccessBenchmarks:
    """Benchmarks for element property access."""

    def test_basic_property_access(self, benchmark):
        """Benchmark accessing basic properties of Iron."""
        fe = Element.get("Fe")
        def access():
            _ = fe.atomic_number
            _ = fe.symbol
            _ = fe.name
            _ = fe.atomic_mass
            _ = fe.period
            _ = fe.group
        benchmark(access)

    def test_electronegativity_comparison(self, benchmark):
        """Benchmark accessing electronegativity for all elements."""
        def compare():
            results = []
            for z in range(1, 119):
                el = Element.from_z(z)
                if el.electronegativity > 2.0:
                    results.append(el.symbol)
            return results
        result = benchmark(compare)
        assert len(result) > 10

    def test_density_property(self, benchmark):
        """Benchmark density access for all elements."""
        def densities():
            return {el.symbol: el.density for el in Element.all_elements()}
        result = benchmark(densities)
        assert len(result) == 118
        assert result["Os"] > 20  # Osmium is the densest

    def test_isotope_data_access(self, benchmark):
        """Benchmark isotope data access for all elements."""
        def isotopes():
            return {el.symbol: len(el.isotopes) for el in Element.all_elements()}
        result = benchmark(isotopes)
        assert len(result) == 118
        assert result["H"] == 3


class TestQueryBenchmarks:
    """Benchmarks for ElementQuery operations."""

    def test_filter_period(self, benchmark):
        """Benchmark filtering elements by period."""
        result = benchmark(lambda: ElementQuery().filter(period=4).execute())
        assert len(result) == 18  # Period 4 has 18 elements

    def test_filter_category(self, benchmark):
        """Benchmark filtering elements by category."""
        result = benchmark(
            lambda: ElementQuery().filter(category="transition_metal").execute()
        )
        assert len(result) > 30

    def test_chained_filters(self, benchmark):
        """Benchmark chained filter operations."""
        def query():
            return (
                ElementQuery()
                .filter(is_metal=True)
                .filter(min_density=10.0)
                .filter(max_melting_point=2000)
                .execute()
            )
        result = benchmark(query)
        for el in result:
            assert el.is_metal
            assert el.density >= 10.0
            assert el.melting_point <= 2000

    def test_multiple_queries(self, benchmark):
        """Benchmark running multiple different queries."""
        def multi_query():
            results = {}
            for period in range(1, 8):
                results[period] = ElementQuery().filter(period=period).execute()
            return results
        result = benchmark(multi_query)
        assert len(result) == 7
        assert len(result[1]) == 2  # H, He
        assert len(result[7]) == 32  # All period 7 elements


class TestEdgeCaseBenchmarks:
    """Benchmarks for edge cases and extreme values."""

    def test_filter_all_metals(self, benchmark):
        """Benchmark filtering all metals."""
        result = benchmark(lambda: ElementQuery().filter(is_metal=True).execute())
        assert len(result) > 80  # Most elements are metals

    def test_filter_noble_gases_high_ie(self, benchmark):
        """Benchmark filtering noble gases with high ionization energy."""
        def query():
            return (
                ElementQuery()
                .filter(category="noble_gas")
                .filter(min_ionization_energy=20.0)
                .execute()
            )
        result = benchmark(query)
        assert len(result) > 0  # At least He and Ne

    def test_all_118_elements_iteration(self, benchmark):
        """Benchmark iterating all 118 elements and accessing multiple properties."""
        def iterate_all():
            data = {}
            for el in Element.all_elements():
                data[el.symbol] = {
                    "z": el.atomic_number,
                    "mass": el.atomic_mass,
                    "en": el.electronegativity,
                    "cat": el.category,
                    "phase": el.phase_at_stp,
                }
            return data
        result = benchmark(iterate_all)
        assert len(result) == 118
