"""Performance benchmarks for the parsers (Phase 1.6 baseline).

Covers the parsing targets named by the Phase 1.6 task list: SMILES parsing,
formula parsing, and format auto-detection. These complement the graph,
element, ring/stereochemistry, and property benchmarks in the other
``benchmark_*`` modules.
"""

import pytest

from chemengine.parsing.formula import parse_formula
from chemengine.parsing.protocol import parse_any
from chemengine.parsing.smiles import parse_smiles


class TestParsingBenchmarks:
    """Benchmarks for SMILES / formula parsing and auto-detection."""

    def test_parse_smiles_small(self, benchmark):
        """Benchmark SMILES parsing of a small molecule (ethanol)."""
        result = benchmark(parse_smiles, "CCO")
        assert result.num_atoms == 9

    def test_parse_smiles_medium(self, benchmark):
        """Benchmark SMILES parsing of a mid-size molecule (aspirin)."""
        smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
        result = benchmark(parse_smiles, smiles)
        assert result.num_atoms == 21

    def test_parse_smiles_rings(self, benchmark):
        """Benchmark SMILES parsing with ring closures (naphthalene)."""
        result = benchmark(parse_smiles, "c1ccc2ccccc2c1")
        assert result.num_atoms == 18

    def test_parse_formula(self, benchmark):
        """Benchmark molecular formula parsing."""
        result = benchmark(parse_formula, "C9H8O4")
        assert result["C"] == 9

    def test_parse_any_auto_detect(self, benchmark):
        """Benchmark automatic format detection and dispatch."""
        result = benchmark(parse_any, "CCO")
        assert result.num_atoms == 9
