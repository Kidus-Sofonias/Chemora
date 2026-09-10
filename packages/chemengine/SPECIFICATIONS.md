# ChemEngine Specifications

## Version: 0.1.0 (Alpha)

## 1. Molecular Representation

### 1.1 MolecularGraph
The single source of truth. A frozen dataclass containing:
- `atoms: tuple[Atom, ...]` — Atoms in the molecule
- `bonds: tuple[Bond, ...]` — Bonds between atoms
- `name: str | None` — Optional human-readable name
- `stereo_config: StereoConfig` — Complete stereochemistry
- `coordinates_2d: tuple[Coordinate2D, ...] | None` — 2D layout
- `coordinates_3d: tuple[Coordinate3D, ...] | None` — 3D structure
- `conformers: tuple[Conformer, ...]` — Additional conformers
- `rings: tuple[Ring, ...]` — Detected rings
- `properties: frozenset[tuple[str, Any]]` — Key-value metadata

### 1.2 Atom
| Field | Type | Range |
|-------|------|-------|
| atomic_number | int | 1-118 |
| formal_charge | int | -10 to +10 |
| radical_electrons | int | 0, 1, or 2 |
| isotope | Isotope \| None | Optional |
| stereochemistry | ChiralTag | R, S, r, s, @, @@, none |
| hybridization | Hybridization | s, sp, sp2, sp3, sp3d, sp3d2, unknown |
| implicit_hydrogens | int \| None | Auto-computed if None |
| is_aromatic | bool | Default False |

### 1.3 Bond
| Field | Type | Values |
|-------|------|--------|
| atom1, atom2 | int | Non-negative, different |
| order | BondOrder | SINGLE(1), DOUBLE(2), TRIPLE(3), QUADRUPLE(4), AROMATIC(5) |
| bond_type | BondType | covalent, dative, ionic, hydrogen, metallic, aromatic |
| stereochemistry | BondStereo | E, Z, cis, trans, none |
| topology | BondTopology | ring, chain, unspecified |

## 2. Supported Formats

### 2.1 SMILES (Phase 1 — v0.2.0)
- OpenSMILES specification
- Organic subset: B, C, N, O, P, S, F, Cl, Br, I
- Aromatic: b, c, n, o, p, s (lowercase)
- Bond types: -, =, #, $, : (explicit)
- Branches via parentheses
- Ring closures via digits 0-9 and %digits
- Tetrahedral stereo: @, @@
- Bracketed atoms: isotopes, charges, hydrogens

### 2.2 Molecular Formula (Phase 0 — v0.1.0)
- Hill system: C first, H second, then alphabetically
- Hydrates: CuSO4.5H2O
- Parenthesized groups: Mg(OH)2

## 3. Validation Rules

### 3.1 Atomic Number
- Must be 1-118
- Mapped via ElementSymbol enum

### 3.2 Valence Limits (per element)
- H: max 1
- C: max 4
- N: max 5
- O: max 2
- F, Cl, Br, I: max 1 (can exceed for higher oxidation states)
- S: max 6
- P: max 5
- Si: max 4

### 3.3 Charge Limits
- Formal charge: -10 to +10
- Element-specific allowed charges defined in valence_rules.toml

## 4. Algorithm Registry

All algorithms are registered with:
- `domain`: Namespace (e.g., "parsing.smiles")
- `name`: Algorithm name (e.g., "default")
- `version`: SemVer string
- `tags`: Capability tags for resolution (e.g., "fast", "exact")

## 5. API Compatibility

All parsers implement the `Parser` protocol:
```python
class Parser(Protocol):
    def parse(self, text: str, **options) -> MolecularGraph: ...
    def serialize(self, graph: MolecularGraph, **options) -> str: ...
```

## 6. Plugin Interface

Plugins implement `PluginProtocol`:
```python
class PluginProtocol(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    def on_load(self, engine: ChemEngineAPI) -> None: ...
    def on_unload(self) -> None: ...
```

Discovery via `importlib.metadata.entry_points(group="chemengine.plugins")`.

## 7. Performance Targets

- SMILES parsing: >10,000 molecules/second (simple linear chains)
- Formula parsing: >50,000 formulas/second
- Graph construction: >100,000 atoms/second
- Memory: <2KB per atom, <1KB per bond
