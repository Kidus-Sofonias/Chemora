# ChemEngine — Production-Grade Chemistry Engine

A modular, extensible chemistry engine built with the **Molecular Graph as the single source of truth**. Designed to power web apps, mobile apps, CLIs, AI agents, and APIs.

**Version 1.0.0** — All 13 phases complete, 980 tests passing.

## Architecture

```
chemengine/
├── core/              # Immutable domain models + infrastructure
│   ├── graph.py       # MolecularGraph (single source of truth)
│   ├── atoms.py       # Atom, Isotope
│   ├── bonds.py       # Bond, BondOrder, BondType
│   ├── stereo.py      # Stereocenter, TetrahedralStereo
│   ├── geometry.py    # Coordinate2D, Coordinate3D, Conformer
│   ├── enums.py       # ElementSymbol (all 118), ChiralTag, BondStereo
│   ├── registry.py    # AlgorithmRegistry
│   ├── events.py      # EventBus (typed pub/sub)
│   ├── plugin.py      # PluginProtocol, PluginManager
│   ├── tool_interface.py  # ChemEngineAPI (AI-ready facade)
│   └── datasets.py    # DatasetRegistry
├── parsing/           # SMILES, InChI, formula, alias parsers
├── generation/        # Constitutional, stereoisomer enumeration
├── detection/         # Ring perception, aromaticity, functional groups
├── stereochemistry/   # R/S, E/Z, cis/trans assignment
├── properties/        # Mass, logP, TPSA, HBA/HBD
├── coordinates/       # 2D layout, 3D conformer generation
├── rendering/         # SVG molecular depiction
├── reactions/         # Reaction models, templates, validation
├── validation/        # Graph sanitization, valence rules
├── io/                # JSON serialization, format conversion
├── nomenclature/      # IUPAC naming (graph → name)
├── datasets/          # Reference data (elements, isotopes, FGs)
└── utils/             # Logging, benchmarking, caching
```

## Key Design Decisions

- **Single Source of Truth**: `MolecularGraph` is the only molecule representation
- **Immutability**: All domain models are frozen dataclasses with slots
- **Plugin Architecture**: Discoverable via `importlib.metadata.entry_points`
- **Algorithm Registry**: Every algorithm is registered, resolvable by tags
- **Event System**: Typed pub/sub with correlation ID tracing
- **AI-Ready**: Self-describing tool definitions with JSON Schema

## Quick Start

```python
from chemengine import ChemEngineAPI

api = ChemEngineAPI()

# Parse a SMILES string
graph = api.parse("CCO", fmt="smiles")
print(graph.molecular_formula)  # C2H6O
print(graph.exact_mass)         # 46.041865

# List available AI tools
tools = api.list_tools()
for tool in tools:
    print(f"{tool.name}: {tool.description}")

# Execute a tool (AI agent interface)
result = api.execute_tool("parse_smiles", {"smiles": "CCO"})
print(result["formula"])  # C2H6O
```

## Features

### Parsing (SMILES, InChI, Formulas)

```python
graph = api.parse("CCO", fmt="smiles")
graph = api.parse("C2H6O", fmt="formula")

from chemengine.parsing.smiles import serialize_smiles
smiles = serialize_smiles(graph)  # Canonical SMILES
```

### 2D Coordinate Generation

```python
result = api.execute_tool("generate_2d_coordinates", {"smiles": "c1ccccc1"})
coords = result["coordinates"]  # [{"x": ..., "y": ...}, ...]
```

### 3D Conformer Generation

```python
result = api.execute_tool("generate_3d_conformer", {
    "smiles": "CCO",
    "num_conformers": 5
})
for conf in result["conformers"]:
    print(f"Energy: {conf['energy']:.2f}, Atoms: {len(conf['coordinates'])}")
```

### SVG Rendering

```python
result = api.execute_tool("render_svg", {"smiles": "c1ccccc1"})
svg = result["svg"]  # Complete SVG string
with open("molecule.svg", "w") as f:
    f.write(svg)
```

### IUPAC Naming

```python
result = api.execute_tool("name_molecule", {"smiles": "CCO"})
print(result["name"])  # "ethanol"

result = api.execute_tool("name_molecule", {"smiles": "C1CCCCC1"})
print(result["name"])  # "cyclohexane"
```

### Functional Group Detection

```python
result = api.execute_tool("detect_functional_groups", {"smiles": "CCO"})
for fg in result["functional_groups"]:
    print(f"{fg['name']}: atoms {fg['atom_indices']}")
```

### Validation & Sanitization

```python
result = api.execute_tool("validate", {"smiles": "CCO"})
print(result["is_valid"])  # True

result = api.execute_tool("sanitize", {"smiles": "CCO"})
print(result["sanitized_smiles"])
```

### Reactions

```python
from chemengine.reactions import ReactionBuilder, ReactionCondition

reaction = (
    ReactionBuilder()
    .add_reactant(methane, coefficient=1)
    .add_reactant(oxygen, coefficient=2)
    .add_product(co2, coefficient=1)
    .add_product(water, coefficient=2)
    .set_name("Combustion of methane")
    .build()
)
print(reaction.is_balanced())  # True
```

### Serialization

```python
result = api.execute_tool("serialize", {"smiles": "CCO", "format": "dict"})
data = result["data"]

from chemengine.io.serialization import dict_to_graph
graph2 = dict_to_graph(data)
assert graph2.molecular_formula == "C2H6O"
```

### Molecular Properties

```python
graph = api.parse("CCO", fmt="smiles")
print(graph.exact_mass)        # 46.041865
print(graph.molecular_weight)  # 46.069
print(graph.num_heavy_atoms)   # 3
```

## AI Tool Interface

11 self-describing tools for AI agent integration:

| Tool | Category | Description |
|------|----------|-------------|
| `parse_smiles` | parsing | Parse SMILES to molecular graph |
| `parse_formula` | parsing | Parse molecular formula |
| `compute_property` | properties | Compute molecular properties |
| `validate` | validation | Validate molecular structure |
| `sanitize` | validation | Sanitize molecular graph |
| `detect_functional_groups` | detection | Detect functional groups |
| `generate_2d_coordinates` | coordinates | Generate 2D layout |
| `generate_3d_conformer` | coordinates | Generate 3D conformers |
| `render_svg` | rendering | Render molecule as SVG |
| `name_molecule` | nomenclature | Generate IUPAC name |
| `serialize` | io | Serialize to JSON/dict |

## Installation

```bash
pip install chemengine
```

## Testing

```bash
pytest tests/ -v
```

980 tests covering all modules.

## License

MIT
