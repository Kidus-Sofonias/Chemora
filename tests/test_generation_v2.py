"""Tests for Phase 7 v2.0: Isomer filtering and lazy iteration.
"""

import pytest

from chemengine.core.graph import MolecularGraph
from chemengine.generation.constitutional import generate_alkane_isomers
from chemengine.generation.filtering import (
    IsomerFilter,
    count_isomers_lazy,
    lazy_alkane_isomers,
    lazy_filtered_isomers,
)

# ══════════════════════════════════════════════════════════════════
# ISOMER FILTER TESTS
# ══════════════════════════════════════════════════════════════════


class TestIsomerFilter:
    """Tests for IsomerFilter composable filtering."""

    def test_filter_by_formula(self):
        """Filter isomers by molecular formula."""
        isomers = generate_alkane_isomers(4)  # Butane + isobutane
        filt = IsomerFilter().by_formula("C4H10")
        filtered = filt.apply(isomers)
        assert len(filtered) == 2  # Both have C4H10

    def test_filter_by_max_mass(self):
        """Filter isomers by maximum mass."""
        isomers = generate_alkane_isomers(5)  # C5H12, mass ~72
        filt = IsomerFilter().by_max_mass(73.0)
        filtered = filt.apply(isomers)
        assert len(filtered) == 3  # All C5 alkanes

    def test_filter_by_min_heavy_atoms(self):
        """Filter by minimum heavy atom count."""
        isomers = generate_alkane_isomers(4)  # C4H10, 4 heavy atoms
        filt = IsomerFilter().by_min_heavy_atoms(4)
        filtered = filt.apply(isomers)
        assert len(filtered) == 2

        filt2 = IsomerFilter().by_min_heavy_atoms(5)
        filtered2 = filt2.apply(isomers)
        assert len(filtered2) == 0  # No isomer has 5+ heavy atoms

    def test_filter_composition(self):
        """Multiple filters compose correctly."""
        isomers = generate_alkane_isomers(5)
        filt = (
            IsomerFilter()
            .by_min_heavy_atoms(5)
            .by_max_mass(73.0)
        )
        filtered = filt.apply(isomers)
        assert len(filtered) == 3  # All C5 alkanes match both criteria

    def test_filter_by_custom_predicate(self):
        """Custom predicate filter works."""
        isomers = generate_alkane_isomers(4)
        # Filter: isomers with at least 2 bonds
        filt = IsomerFilter().by_custom(lambda g: g.num_bonds >= 2)
        filtered = filt.apply(isomers)
        assert len(filtered) == 2  # Both have >= 2 bonds

    def test_empty_filter_returns_all(self):
        """Empty filter returns all isomers."""
        isomers = generate_alkane_isomers(4)
        filt = IsomerFilter()
        filtered = filt.apply(isomers)
        assert len(filtered) == len(isomers)

    def test_filter_repr(self):
        """Filter repr shows predicate count."""
        filt = IsomerFilter().by_formula("C4H10").by_max_mass(73.0)
        assert "2 predicates" in repr(filt)


# ══════════════════════════════════════════════════════════════════
# LAZY ITERATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestLazyIteration:
    """Tests for lazy isomer generation and filtering."""

    def test_lazy_alkane_isomers_small(self):
        """Lazy generation for small n produces correct count."""
        isomers = list(lazy_alkane_isomers(4))
        assert len(isomers) == 2

    def test_lazy_alkane_isomers_medium(self):
        """Lazy generation for medium n works."""
        isomers = list(lazy_alkane_isomers(6))
        assert len(isomers) == 5

    def test_lazy_alkane_isomers_large(self):
        """Lazy generation for large n works without memory issues."""
        count = 0
        for iso in lazy_alkane_isomers(8):
            count += 1
            assert iso.num_atoms > 0
        assert count == 18  # C8 has 18 isomers

    def test_lazy_alkane_isomers_invalid(self):
        """Lazy generation raises for invalid n."""
        with pytest.raises(ValueError):
            list(lazy_alkane_isomers(0))
        with pytest.raises(ValueError):
            list(lazy_alkane_isomers(9))

    def test_lazy_filtered_isomers(self):
        """Lazy filtering works with iterator."""
        isomers = lazy_alkane_isomers(5)
        filt = IsomerFilter().by_min_heavy_atoms(5)
        filtered = list(lazy_filtered_isomers(isomers, filt))
        assert len(filtered) == 3  # All C5 alkanes have 5 heavy atoms

    def test_lazy_filtered_with_max_results(self):
        """Lazy filtering with result limit."""
        isomers = lazy_alkane_isomers(6)
        filt = IsomerFilter()
        filtered = list(lazy_filtered_isomers(isomers, filt, max_results=3))
        assert len(filtered) == 3

    def test_count_isomers_lazy(self):
        """Count isomers without storing them."""
        isomers = lazy_alkane_isomers(7)
        count = count_isomers_lazy(isomers)
        assert count == 9

    def test_count_isomers_lazy_with_filter(self):
        """Count isomers with filter."""
        isomers = lazy_alkane_isomers(6)
        filt = IsomerFilter().by_min_heavy_atoms(6)
        count = count_isomers_lazy(isomers, filt)
        assert count == 5  # All C6 alkanes have 6 heavy atoms

    def test_lazy_isomers_are_valid_graphs(self):
        """All lazily generated isomers are valid MolecularGraph objects."""
        for iso in lazy_alkane_isomers(5):
            assert isinstance(iso, MolecularGraph)
            assert iso.num_atoms > 0
            assert iso.num_bonds > 0
            assert iso.molecular_formula == "C5H12"
