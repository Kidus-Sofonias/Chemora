"""Performance benchmarks for core domain models."""

import pytest
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.core.bonds import BondOrder


class TestGraphConstructionBenchmarks:
    """Benchmarks for graph construction performance."""

    def test_build_small_molecule(self, benchmark):
        """Benchmark building a small molecule (methane)."""
        def build():
            builder = MolecularGraphBuilder()
            c = builder.add_atom(atomic_number=6)
            for _ in range(4):
                h = builder.add_atom(atomic_number=1)
                builder.add_bond(c, h, BondOrder.SINGLE)
            return builder.build()
        result = benchmark(build)
        assert result.num_atoms == 5

    def test_build_medium_molecule(self, benchmark):
        """Benchmark building a medium molecule (decane, C10H22)."""
        def build():
            builder = MolecularGraphBuilder()
            carbons = []
            for i in range(10):
                c = builder.add_atom(atomic_number=6)
                carbons.append(c)
            for i in range(9):
                builder.add_bond(carbons[i], carbons[i+1], BondOrder.SINGLE)
            for c in carbons:
                for _ in range(2):
                    h = builder.add_atom(atomic_number=1)
                    builder.add_bond(c, h, BondOrder.SINGLE)
            # Add 2 more hydrogens for terminal carbons
            h1 = builder.add_atom(atomic_number=1)
            builder.add_bond(carbons[0], h1, BondOrder.SINGLE)
            h2 = builder.add_atom(atomic_number=1)
            builder.add_bond(carbons[9], h2, BondOrder.SINGLE)
            return builder.build()
        result = benchmark(build)
        assert result.num_atoms == 32

    def test_formula_computation(self, benchmark):
        """Benchmark molecular formula computation."""
        builder = MolecularGraphBuilder()
        carbons = [builder.add_atom(atomic_number=6) for _ in range(2)]
        builder.add_bond(carbons[0], carbons[1], BondOrder.SINGLE)
        for c in carbons:
            for _ in range(3):
                h = builder.add_atom(atomic_number=1)
                builder.add_bond(c, h, BondOrder.SINGLE)
        ethane = builder.build()
        result = benchmark(lambda: ethane.molecular_formula)
        assert result == "C2H6"

    def test_neighbor_query(self, benchmark):
        """Benchmark neighbor query on benzene."""
        builder = MolecularGraphBuilder()
        carbons = [builder.add_atom(atomic_number=6) for _ in range(6)]
        for i in range(6):
            builder.add_bond(carbons[i], carbons[(i + 1) % 6], BondOrder.AROMATIC)
        for c in carbons:
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(c, h, BondOrder.SINGLE)
        benzene = builder.build()
        result = benchmark(lambda: benzene.get_neighbors(0))
        assert len(result) == 3  # 2 carbons + 1 hydrogen