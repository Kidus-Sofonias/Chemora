# Testing Strategy

## Test Layers

| Layer | Approach | Tools |
|-------|----------|-------|
| Unit tests | Every public function, edge cases, error paths | pytest |
| Round-trip | Parse → serialize → re-parse → compare | Hypothesis (property-based) |
| Golden suite | ~1000 molecules with known properties | pytest + data files |
| Regression | Known failures from development | pytest |
| Performance | Isomer enumeration timing, parsing throughput | pytest-benchmark |
| Cross-validation | Compare SMILES/InChI output against RDKit | Optional external check |

## Test Structure

Tests mirror the source structure:
```
tests/
├── conftest.py          # Shared fixtures
├── test_core.py         # Domain model tests
├── test_formula.py      # Formula parser tests
├── test_smiles.py       # SMILES parser tests
├── test_rings.py        # Ring detection tests
├── test_events.py       # Event bus tests
├── test_registry.py     # Algorithm registry tests
├── test_plugin.py       # Plugin system tests
├── test_api.py          # ChemEngineAPI tests
└── test_properties.py   # Property computation tests
```

## Property-Based Testing

Use Hypothesis for round-trip tests:
```python
@given(st.smiles())
def test_smiles_roundtrip(smiles_str):
    graph = smiles_parser.parse(smiles_str)
    output = smiles_parser.serialize(graph)
    graph2 = smiles_parser.parse(output)
    assert graph.graph_hash == graph2.graph_hash
```

## Coverage Targets

- Core domain models: 100%
- Parsing: >95%
- Detection: >90%
- Infrastructure (registry, events, plugin): >95%
- Overall: >90%

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=chemengine

# Property-based tests only
pytest -m property

# Slow tests excluded
pytest -m "not slow"

# Benchmarks
pytest benchmarks/ --benchmark-only