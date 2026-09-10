# ChemEngine — Format Specifications

This document provides formal specifications for all chemical formats supported by ChemEngine.

---

## 1. SMILES (Simplified Molecular Input Line Entry System)

### Supported Features

| Feature | Status | Notes |
|---------|--------|-------|
| Standard atoms (organic subset) | ✅ | B, C, N, O, P, S, F, Cl, Br, I |
| Bracket atoms `[X]` | ✅ | Any element, charge, isotope, stereo |
| Aromatic atoms (lowercase) | ✅ | b, c, n, o, p, s |
| Single/double/triple bonds | ✅ | `-`, `=`, `#` |
| Aromatic bonds | ✅ | `:` or implicit in aromatic atoms |
| Ring closures | ✅ | Single digit `C1CC1` and `%` digits `C%10CC%10` |
| Branches | ✅ | Parentheses `C(CC)C` |
| Disconnected components | ✅ | Dot `C.[Na+]` |
| Charges | ✅ | `+`, `-`, `+n`, `-n`, `++`, `--` |
| Isotopes | ✅ | `[13C]`, `[2H]`, `[15N]` |
| Implicit hydrogens | ✅ | Auto-calculated from valence |
| Explicit hydrogens | ✅ | `[H]`, `[nH]`, `[OH2]` |
| Stereochemistry | ✅ | `@`, `@@` for tetrahedral |
| Wildcard atoms | ✅ | `*`, `[*]` |
| Dot disconnected | ✅ | `CC.[Na+].[Cl-]` |

### Grammar (EBNF-like)

```
smiles       = chain_element { chain_element }
chain_element = atom [bond] { branch } [ring_closure]
branch       = '(' chain_element { chain_element } ')'
atom         = bracket_atom | organic_subset | aromatic_atom
bracket_atom = '[' [isotope] element [chirality] [hcount] [charge] ']'
organic_subset = 'B' | 'C' | 'N' | 'O' | 'P' | 'S' | 'F' | 'Cl' | 'Br' | 'I'
aromatic_atom = 'b' | 'c' | 'n' | 'o' | 'p' | 's'
bond         = '-' | '=' | '#' | ':' | '/' | '\\'
ring_closure = digit | '%' digit digit
isotope      = digit+
element      = uppercase [lowercase]
chirality    = '@' | '@@'
hcount       = 'H' [digit]
charge       = ('+' | '-') [digit] | '++' | '--'
digit        = '0'..'9'
```

### Edge Cases

- **Aromatic bonds**: Implicit between aromatic atoms, no explicit `:` needed
- **Branch ordering**: `C(C)C` vs `CC(C)` — order matters for serialization
- **Ring closure labels**: Must appear in pairs; spanning-tree pre-pass ensures correctness
- **Aromatic SMILES**: `c1ccccc1` for benzene; Kekulé form `C1=CC=CC=C1` also valid

---

## 2. InChI (IUPAC International Chemical Identifier)

### Supported Layers

| Layer | Prefix | Status | Description |
|-------|--------|--------|-------------|
| Formula | `/` | ✅ | Chemical formula (`/C6H6`) |
| Connections | `/c` | ✅ | Hydrogen-suppressed connectivity |
| Hydrogens | `/h` | ✅ | Hydrogen atom positions |
| Charge | `/q` | ✅ | Formal charge |
| Protons | `/p` | ⬜ | Not implemented |
| Fixed-H | `/f` | ⬜ | Not implemented |
| Reconnect | `/r` | ⬜ | Not implemented |
| Stereo | `/t`, `/m`, `/s` | ⬜ | Not implemented |

### Grammar

```
inchi         = "InChI=" version "/" formula_layer { '/' layer }
version       = "1S" | "1"
formula_layer = element { element }
element       = uppercase [lowercase] [digit]
layer         = connections_layer | hydrogens_layer | charge_layer
connections_layer = 'c' connection_path
connection_path   = number { '-' number }
hydrogens_layer   = 'h' hydrogen_spec
charge_layer      = 'q' charge_value
charge_value      = ['+' | '-'] digit
number            = digit+
```

### Atom Numbering

- InChI uses 1-based atom numbering in connections and hydrogens layers
- Atoms are numbered in formula order: C first, then H (if no hydrogens layer), then other elements
- When hydrogens layer is present, H atoms from formula are skipped (they're specified in the `/h` layer)

### Known Limitations

- No stereochemistry layers (`/t`, `/m`, `/s`)
- No fixed-H layer (`/f`)
- No protonation layer (`/p`)
- Branching in connections layer partially supported

---

## 3. Molecular Formula (Hill System)

### Hill System Ordering

1. **Carbon first** (if present)
2. **Hydrogen second** (if present)
3. **All other elements** in alphabetical order by symbol

### Examples

| Formula | Description |
|---------|-------------|
| `CH4` | Methane |
| `C2H6O` | Ethanol |
| `C6H6` | Benzene |
| `C8H10N4O2` | Caffeine |
| `NaCl` | Sodium chloride |
| `H2O` | Water |
| `CuSO4.5H2O` | Copper sulfate pentahydrate |

### Supported Features

| Feature | Status | Notes |
|---------|--------|-------|
| Hill system ordering | ✅ | C, H, then alphabetical |
| Hydrated formulas | ✅ | Dot notation `CuSO4.5H2O` (`*` also accepted) |
| Parenthesized groups | ✅ | `Mg(OH)2`, `Fe2(SO4)3`, `(NH4)2SO4` |
| Nested groups | ✅ | `Ca(Al(OH)4)2` |
| Charged formulas | ✅ | `NH4+`, `SO4^2-`, `SO4 2-`, `Fe+3`, `Ca 2+` |
| Multi-digit counts | ✅ | `C12H22O11` |
| Whitespace | ✅ | Between tokens; preserved counts |
| Isotope formulas | ❌ | Not implemented — rejected with FormulaParseError |

### Grammar

The parser is recursive and group-aware (`chemengine/parsing/formula.py`).
A simplified grammar:

```
formula        = component { ('.'|'*') [mult] component } [charge]
component      = ( element | group )+        # group: '(' component ')' [mult]
element        = symbol [count]              # count immediately follows the symbol
group          = '(' component ')' [count]
count          = digit+
charge         = '^' [sign] [count] | sign [count] | [count] sign
```

Examples of correct counts:

| Formula | Counts |
|---------|--------|
| `Mg(OH)2` | Mg 1, O 2, H 2 |
| `Fe2(SO4)3` | Fe 2, S 3, O 12 |
| `(NH4)2SO4` | N 2, H 8, S 1, O 4 |
| `CuSO4.5H2O` | Cu 1, S 1, O 9, H 10 |
| `Ca(Al(OH)4)2` | Ca 1, Al 2, O 8, H 8 |

Invalid formulas (unknown element, unclosed parentheses, stray `)`, dangling
dot, isotope prefix, invalid characters, empty input) raise
`chemengine.parsing.errors.FormulaParseError`. No syntax is silently
discarded.

---

## 4. IUPAC Nomenclature

### Supported Compound Classes

| Class | Status | Example |
|-------|--------|---------|
| Alkanes (C1-C20) | ✅ | methane, ethane, propane, ... |
| Alkenes | ✅ | ethene, propene |
| Alkynes | ✅ | ethyne, propyne |
| Alcohols | ✅ | ethanol, propan-1-ol |
| Aldehydes | ✅ | ethanal |
| Ketones | ✅ | propan-2-one |
| Carboxylic acids | ✅ | ethanoic acid |
| Esters | ✅ | ethanoate |
| Amides | ✅ | ethanamide |
| Amines | ✅ | ethanamine |
| Nitriles | ✅ | ethanenitrile |
| Cycloalkanes | ✅ | cyclopropane, cyclohexane |
| Heterocycles | ✅ | pyridine, furan, thiophene |
| Halides | ✅ | chloroethane |

### Functional Group Priority (highest to lowest)

1. Carboxylic acid (`-oic acid`)
2. Ester (`-oate`)
3. Amide (`-amide`)
4. Nitrile (`-nitrile`)
5. Aldehyde (`-al`)
6. Ketone (`-one`)
7. Alcohol (`-ol`)
8. Amine (`-amine`)

### Naming Rules

1. **Longest chain**: Find the longest carbon chain containing the principal functional group
2. **Numbering**: Number to give the principal functional group the lowest locant
3. **Substituents**: List alphabetically with locants
4. **Multipliers**: di, tri, tetra, penta, etc. for repeated substituents

---

## 5. SMARTS (SMiles ARbitrary Target Specification)

### Supported Features

| Feature | Status | Notes |
|---------|--------|-------|
| Simple atoms | ✅ | `C`, `N`, `O`, `S`, `P`, `F`, `Cl`, `Br`, `I` |
| Bracket atoms | ✅ | `[C]`, `[N+]`, `[O-]` |
| Aromatic atoms | ✅ | `c`, `n`, `o`, `s` |
| Bond types | ✅ | `-`, `=`, `#`, `:`, `/`, `\\` |
| Branches | ✅ | `C(CC)C` |
| Ring closures | ✅ | `C1CC1` |
| Logical NOT | ✅ | `[#6;!R]` (not implemented) |
| Logical OR | ✅ | `[C,N,O]` |
| Wildcard | ✅ | `*`, `[*]` |
| Degree query | ⬜ | `[D2]` — not implemented |
| Valence query | ⬜ | Not implemented |
| Connectivity query | ⬜ | Not implemented |
| Ring membership | ⬜ | Not implemented |
| Hybridization query | ⬜ | Not implemented |

### Grammar (subset)

```
pattern     = chain_element { chain_element }
chain_element = atom [bond] { branch } [ring_closure]
atom        = bracket_atom | simple_atom
simple_atom = 'C' | 'N' | 'O' | 'S' | 'P' | 'F' | 'Cl' | 'Br' | 'I' | '*'
bracket_atom = '[' atomic_query { '&' atomic_query } ']'
atomic_query = atomic_number | aromaticity | charge | 'D' digit | 'X' digit
bond        = '-' | '=' | '#' | ':' | '/' | '\\' | '~'
```

---

## 6. JSON Serialization

### MolecularGraph JSON Schema

```json
{
  "name": "string (optional)",
  "formula": "string",
  "exact_mass": "number",
  "atoms": [
    {
      "atomic_number": "integer (1-118)",
      "symbol": "string",
      "formal_charge": "integer (optional, default 0)",
      "radical_electrons": "integer (optional, default 0)",
      "isotope": {
        "mass_number": "integer",
        "exact_mass": "number"
      },
      "stereochemistry": "string (optional)",
      "hybridization": "string (optional)",
      "implicit_hydrogens": "integer (optional)",
      "is_aromatic": "boolean (optional, default false)"
    }
  ],
  "bonds": [
    {
      "atom1": "integer (0-based index)",
      "atom2": "integer (0-based index)",
      "order": "integer (1=single, 2=double, 3=triple, 1.5=aromatic)",
      "bond_type": "string (optional, default 'COVALENT')",
      "stereochemistry": "string (optional)",
      "topology": "string (optional)",
      "is_aromatic": "boolean (optional, default false)",
      "length": "number (optional)"
    }
  ],
  "coordinates_2d": [
    {"x": "number", "y": "number"}
  ],
  "coordinates_3d": [
    {"x": "number", "y": "number", "z": "number"}
  ],
  "conformers": [
    {
      "id": "integer",
      "coordinates": [{"x": "number", "y": "number", "z": "number"}],
      "energy": "number"
    }
  ]
}
```

### Supported Formats

| Format | Input | Output | Notes |
|--------|-------|--------|-------|
| SMILES | ✅ | ✅ | Full OpenSMILES |
| InChI | ✅ | ✅ | Formula + connections + H + charge layers |
| Formula | ✅ | ✅ | Hill system |
| IUPAC Name | ⬜ | ✅ | Graph → name only |
| Common Name | ✅ | ⬜ | Name → graph only (100+ aliases) |
| JSON | ✅ | ✅ | Full round-trip |
| Dict | ✅ | ✅ | Python dict round-trip |
| SMARTS | ✅ | ⬜ | Query pattern (not molecule) |

---

## 7. Coordinate Generation

### 2D Layout

- **Algorithm**: Fruchterman-Reingold force-directed
- **Ring templates**: Regular polygon placement for 3-8 membered rings
- **Bond length**: Default 1.5 Å, configurable
- **Collision avoidance**: Repulsive forces between all atom pairs
- **Determinism**: Reproducible with `seed` parameter

### 3D Conformer Generation

- **Algorithm**: Distance geometry with bounds matrix
- **Energy minimization**: Steepest descent (200 iterations max)
- **Bond lengths**: SINGLE=1.54Å, DOUBLE=1.34Å, TRIPLE=1.20Å, AROMATIC=1.40Å
- **VDW radii**: Element-specific (H=1.20, C=1.70, N=1.55, O=1.52, etc.)
- **Clustering**: RMSD-based greedy clustering (threshold=0.5Å)
- **Max conformers**: 50

---

## 8. SVG Rendering

### Supported Elements

| Element | Color | Notes |
|---------|-------|-------|
| H | #FFFFFF | White |
| C | #333333 | Dark gray |
| N | #3050F8 | Blue |
| O | #FF0D0D | Red |
| F | #90E050 | Green |
| P | #FF8000 | Orange |
| S | #FFFF30 | Yellow |
| Cl | #1FF01F | Green |
| Br | #A62929 | Dark red |
| I | #940094 | Violet |

### Bond Rendering

| Bond Type | Rendering |
|-----------|-----------|
| Single | Solid line |
| Double | Two parallel lines |
| Triple | Three parallel lines |
| Aromatic | Solid line + dashed inner line |
| Wedge | Solid triangle (toward viewer) |
| Dashed | Hatched lines (away from viewer) |

### Configuration

- `bond_length`: Bond length in SVG units (default 40.0)
- `show_hydrogens`: Whether to render H atoms (default False)
- `padding`: Padding around molecule (default 30.0)
- `title`: Optional title above molecule

---

## 9. Reaction Model

### Data Structures

```python
@dataclass(frozen=True)
class Reaction:
    reactants: tuple[ReactionComponent, ...]
    products: tuple[ReactionComponent, ...]
    agents: tuple[ReactionComponent, ...]      # solvents, catalysts
    conditions: tuple[ReactionCondition, ...]  # temp, pressure, etc.
    arrow: ReactionArrow                        # forward, reversible
    name: str                                   # e.g., "Diels-Alder"
    equation: str                               # SMILES equation

@dataclass(frozen=True)
class ReactionComponent:
    molecule: MolecularGraph
    coefficient: int = 1
    label: str = ""                            # "solvent", "catalyst"
    atom_map: dict[int, int] | None = None     # atom mapping
```

### Built-in Templates

| Template | Description | SMILES Patterns |
|----------|-------------|-----------------|
| Combustion | C + O₂ → CO₂ + H₂O | `C`, `O=O` → `O=C=O`, `O` |
| Acid-Base | HA + B → A⁻ + BH⁺ | `[H]O`, `[O-]` → `O` |
| Esterification | RCOOH + R'OH → RCOOR' + H₂O | `C(=O)O`, `CO` → `C(=O)OC`, `O` |
| Dehydration | ROH → alkene + H₂O | `CO` → `C=C`, `O` |
| Hydrogenation | alkene + H₂ → alkane | `C=C`, `[H][H]` → `CC` |

### Validation

- `is_balanced()`: Check atom conservation
- `atom_count_difference()`: Compute element imbalances
- `to_dict()`: JSON serialization
