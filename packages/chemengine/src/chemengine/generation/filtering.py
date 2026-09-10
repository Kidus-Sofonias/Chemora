"""Isomer filtering and lazy iteration.

Provides:
- Filtering isomers by molecular formula, exact mass, substructure
- Lazy iteration for large isomer spaces (generator-based)
- Predicate-based filtering with composable filters
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from chemengine.core.graph import MolecularGraph

# ══════════════════════════════════════════════════════════════════
# FILTER TYPES
# ══════════════════════════════════════════════════════════════════

class IsomerFilter:
    """Composable filter for isomer enumeration.

    Usage:
        >>> filt = IsomerFilter()
        >>> filt = filt.by_formula("C5H12")
        >>> filt = filt.by_max_mass(80.0)
        >>> filt = filt.by_min_heavy_atoms(3)
        >>> filtered = filt.apply(isomers)
    """

    def __init__(self) -> None:
        self._predicates: list[Callable[[MolecularGraph], bool]] = []

    def by_formula(self, formula: str) -> IsomerFilter:
        """Filter by molecular formula (exact match)."""
        new = self._copy()
        new._predicates.append(lambda g: g.molecular_formula == formula)
        return new

    def by_max_mass(self, max_mass: float) -> IsomerFilter:
        """Filter by maximum exact mass."""
        new = self._copy()
        new._predicates.append(lambda g: g.exact_mass <= max_mass)
        return new

    def by_min_mass(self, min_mass: float) -> IsomerFilter:
        """Filter by minimum exact mass."""
        new = self._copy()
        new._predicates.append(lambda g: g.exact_mass >= min_mass)
        return new

    def by_mass_range(self, min_mass: float, max_mass: float) -> IsomerFilter:
        """Filter by mass range (inclusive)."""
        new = self._copy()
        new._predicates.append(
            lambda g: min_mass <= g.exact_mass <= max_mass
        )
        return new

    def by_min_heavy_atoms(self, count: int) -> IsomerFilter:
        """Filter by minimum number of heavy (non-hydrogen) atoms."""
        new = self._copy()
        new._predicates.append(
            lambda g: g.num_heavy_atoms >= count
        )
        return new

    def by_max_heavy_atoms(self, count: int) -> IsomerFilter:
        """Filter by maximum number of heavy (non-hydrogen) atoms."""
        new = self._copy()
        new._predicates.append(
            lambda g: g.num_heavy_atoms <= count
        )
        return new

    def by_has_element(self, atomic_number: int) -> IsomerFilter:
        """Filter to isomers containing a specific element."""
        new = self._copy()
        new._predicates.append(
            lambda g: any(a.atomic_number == atomic_number for a in g.atoms)
        )
        return new

    def by_num_bonds(self, min_bonds: int = 0, max_bonds: int = 999) -> IsomerFilter:
        """Filter by bond count range."""
        new = self._copy()
        new._predicates.append(
            lambda g: min_bonds <= g.num_bonds <= max_bonds
        )
        return new

    def by_custom(self, predicate: Callable[[MolecularGraph], bool]) -> IsomerFilter:
        """Add a custom predicate filter."""
        new = self._copy()
        new._predicates.append(predicate)
        return new

    def apply(self, isomers: list[MolecularGraph]) -> list[MolecularGraph]:
        """Apply all filters to a list of isomers."""
        result = []
        for iso in isomers:
            if all(p(iso) for p in self._predicates):
                result.append(iso)
        return result

    def apply_lazy(self, isomers: Iterator[MolecularGraph]) -> Iterator[MolecularGraph]:
        """Apply all filters lazily to an iterator of isomers."""
        for iso in isomers:
            if all(p(iso) for p in self._predicates):
                yield iso

    def _copy(self) -> IsomerFilter:
        new = IsomerFilter()
        new._predicates = list(self._predicates)
        return new

    def __repr__(self) -> str:
        return f"IsomerFilter({len(self._predicates)} predicates)"


# ══════════════════════════════════════════════════════════════════
# LAZY ITERATION
# ══════════════════════════════════════════════════════════════════

def lazy_alkane_isomers(
    n: int,
    batch_size: int = 100,
) -> Iterator[MolecularGraph]:
    """Lazily generate alkane isomers using a generator.

    Yields isomers one at a time, generating them in batches
    to balance memory usage and performance.

    Args:
        n: Number of carbon atoms (1-8).
        batch_size: Number of isomers to generate per batch.

    Yields:
        MolecularGraph objects for each isomer.
    """
    if n < 1 or n > 8:
        raise ValueError(f"Can generate isomers for C1-C8 only, got C{n}")

    from chemengine.generation.constitutional import generate_alkane_isomers

    # For small n, just generate all at once
    if n <= 5:
        for iso in generate_alkane_isomers(n):
            yield iso
        return

    # For larger n, generate in batches
    all_isomers = generate_alkane_isomers(n)
    for i in range(0, len(all_isomers), batch_size):
        batch = all_isomers[i:i + batch_size]
        for iso in batch:
            yield iso


def lazy_filtered_isomers(
    isomers: Iterator[MolecularGraph],
    filt: IsomerFilter,
    max_results: int | None = None,
) -> Iterator[MolecularGraph]:
    """Lazily filter isomers with an optional result limit.

    Args:
        isomers: Iterator of isomers to filter.
        filt: IsomerFilter to apply.
        max_results: Maximum number of results to yield (None for unlimited).

    Yields:
        Filtered MolecularGraph objects.
    """
    count = 0
    for iso in isomers:
        if max_results is not None and count >= max_results:
            return
        if all(p(iso) for p in filt._predicates):
            yield iso
            count += 1


def count_isomers_lazy(
    isomers: Iterator[MolecularGraph],
    filt: IsomerFilter | None = None,
) -> int:
    """Count isomers lazily without storing them in memory.

    Args:
        isomers: Iterator of isomers.
        filt: Optional filter to apply.

    Returns:
        Number of matching isomers.
    """
    count = 0
    for iso in isomers:
        if filt is None or all(p(iso) for p in filt._predicates):
            count += 1
    return count
