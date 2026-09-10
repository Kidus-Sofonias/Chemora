# API Design

## Conventions

1. All public APIs accept and return `MolecularGraph` or primitive types (str, int, float).
2. No mutation of input graphs — always return new graphs or raise exceptions.
3. All public functions are fully typed with type hints.
4. All domain models are frozen dataclasses with slots.
5. Errors are raised as ValueError or KeyError (never bare asserts).

## ChemEngineAPI (Facade)

```python
class ChemEngineAPI:
    # AI Tool Interface
    def list_tools(self, category=None, tags=None) -> list[ToolDefinition]
    def execute_tool(self, name, params, correlation_id=None) -> dict
    def execute_batch(self, calls) -> list[dict]

    # Type-Safe Convenience Methods
    def parse(self, text, fmt=None) -> MolecularGraph
    def convert(self, graph, target, **options) -> str
    def compute(self, graph, property_name) -> Any
    def detect_functional_groups(self, graph) -> list[dict]
    def render(self, graph, fmt="svg", **options) -> str

    # Plugin Management
    def load_plugin(self, name) -> None
    def load_all_plugins(self) -> list[Any]
    def list_plugins(self) -> list[dict]
```

## convert() — Supported Targets

`convert(graph, target)` supports only targets backed by real serializers:

| Target | Serializer |
|--------|------------|
| `smiles` | `parsing/smiles.py::serialize_smiles` |
| `inchi` | `parsing/inchi_serializer.py::serialize_inchi` |
| `inchikey` | `parsing/inchi_serializer.py::generate_inchi_key` |
| `formula` | `MolecularGraph.molecular_formula` |

Any other target (including `"name"`) raises `ValueError` listing the
supported targets. Unsupported targets never silently return an empty string.

## compute() — Supported Properties

`compute(graph, property)` supports:

| Property | Type | Backed by |
|----------|------|-----------|
| `mass` | float | `MolecularGraph.exact_mass` (monoisotopic) |
| `weight` | float | `MolecularGraph.molecular_weight` (average) |
| `formula` | str | `MolecularGraph.molecular_formula` |
| `heavy_atoms` | int | `MolecularGraph.num_heavy_atoms` |
| `logp` | float | `properties/descriptors.py::compute_logp` |
| `tpsa` | float | `properties/descriptors.py::compute_tpsa` |
| `fraction_csp3` | float | `properties/descriptors.py::compute_fraction_csp3` |
| `hba` | int | `properties/descriptors.py::compute_hba` |
| `hbd` | int | `properties/descriptors.py::compute_hbd` |
| `rotatable_bonds` | int | `properties/descriptors.py::compute_rotatable_bonds` |
| `num_rings` | int | ring detection |

Descriptor logic lives **only** in the properties subsystem
(`chemengine/properties/descriptors.py`). `ChemEngineAPI.compute()` delegates
there and never duplicates descriptor algorithms. Unsupported property names
raise `ValueError` listing the supported set.

## Tool Definition (JSON Schema)

```python
ToolDefinition(
    name="parse_smiles",
    description="Parse a SMILES string into a molecular graph",
    input_schema={
        "type": "object",
        "properties": {
            "smiles": {"type": "string"},
            "compute": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["smiles"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "canonical_smiles": {"type": "string"},
            "inchi": {"type": "string"},
            "formula": {"type": "string"},
            "exact_mass": {"type": "number"}
        }
    },
    category="parsing"
)
```

## Error Handling

- Parse failures: `ValueError` with descriptive message
- Missing algorithms: `KeyError` with available options
- Invalid parameters: `ValueError` with valid range
- All exceptions are logged via structlog

## Serialization

- All domain models can be serialized to JSON
- MolecularGraph serialization preserves atom and bond order
- Custom serializers can be registered via AlgorithmRegistry