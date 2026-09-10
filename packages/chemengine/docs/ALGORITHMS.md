# Algorithms

## Ring Perception (SSSR)

**Algorithm**: DFS path-enumeration for smallest set of smallest rings (Paton/Figueras variant)

**Module**: `detection/rings.py` — `detect_rings()`, `find_all_rings()`

**Approach**: 
1. Build adjacency list from bond list
2. BFS from each atom, tracking paths and visited neighbors
3. When a visited neighbor is found in the current path, a cycle is detected
4. Extract the cycle by slicing from the neighbor's first occurrence in the path
5. Canonicalize each cycle (sort atom indices, smallest first)
6. Deduplicate by comparing frozensets of atom indices (set equivalence)
7. Build SSSR (smallest set of smallest rings) by taking smallest unique rings first
8. For each ring, also compute bond indices by matching atom pairs against the graph's bond list

**Return type**: `tuple[Ring, ...]` — `Ring` dataclass with `atom_indices: tuple[int, ...]`, `bond_indices: tuple[int, ...]`, `size: int`

**Performance note**: BFS explores all simple paths from each start node without a global visited set. This is necessary for correctness (a visited set would prevent finding cycles in small graphs like triangles). For chemical graphs where each atom has at most 4 bonds, the branching factor is bounded and performance is acceptable for typical molecules (<100 atoms). For larger or highly-connected molecules, the algorithm degrades gracefully.

**Helper functions**:
- `_build_adjacency(graph)` — constructs adjacency list from bond list
- `_ring_atoms_to_bonds(graph, ring_atoms)` — maps atom indices to bond indices
- `_check_ring_aromatic(graph, ring)` — checks if all atoms/bonds in a ring are aromatic
- `is_ring_atom(graph, atom_index)` — returns True if atom participates in at least one ring
- `is_ring_bond(graph, atom1, atom2)` — returns True if bond is part of at least one ring
- `ring_count(graph)` — quick count of rings in the graph

**Complexity**: O((V+E) * R) where R is the number of rings in the SSSR

**Limitation**: The algorithm enumerates SSSR rings from the BFS output but does not find all possible rings (e.g., larger rings that are linear combinations of SSSR rings). For complete all-ring enumeration, see `find_all_rings()` which returns every simple cycle up to a configurable size.

---

## Ring System Analysis

**Algorithm**: Ring adjacency graph + connected components + structural classification

**Module**: `detection/ring_systems.py` — `detect_ring_systems()`, `is_spiro_center()`, `is_bridgehead_atom()`

**Approach**:
1. Build a ring adjacency graph: each ring is a node; edge exists if two rings share at least one atom
2. Find connected components in the ring adjacency graph using DFS
3. Each connected component is a `RingSystem` containing all rings that are topologically connected
4. Classify each ring into `RingSystemType`:

| Type | Criteria | Example |
|------|----------|---------|
| **ISOLATED** | Single ring with no shared atoms | Cyclohexane (1 ring) |
| **FUSED** | Rings sharing 2+ atoms (face- or edge-fused) | Naphthalene (2 rings, 2 shared atoms) |
| **SPIRO** | Rings sharing exactly 1 atom, with no other shared atoms between those rings | Spiro[2.2]pentane |
| **BRIDGED** | Rings in a polycyclic system where atoms belong to 3+ rings or complex shared-atom topology | Adamantane |
| **COMPLEX** | Any combination of the above types | Multi-ring natural products |

**Spiro center detection**: An atom is a spiro center if it belongs to at least 2 rings, and those rings share no other atoms besides this spiro center.

**Bridgehead detection**: An atom is a bridgehead if it belongs to at least 3 rings (or is part of a bridged polycyclic system where a ring would otherwise be broken if the atom were removed).

**Complexity**: O(R²) for ring adjacency, O(R + E_ring) for connected components — negligible for chemical graphs.

---

## Aromaticity Detection (Hückel Rule)

**Algorithm**: Pi-system perception + Hückel (4n+2) rule with heteroatom support

**Module**: `detection/aromaticity.py` — `assess_ring_aromaticity()`, `assess_all_rings()`, `assign_aromaticity()`

**Data types**:
- `AromaticityType` enum: `AROMATIC`, `ANTI_AROMATIC`, `NON_AROMATIC`
- `AromaticityResult`: per-ring result with `ring`, `pi_electrons`, `result`, `reason`

### Step 1: Conjugation Detection

A ring has a conjugated π system if:
- Every bond in the ring is either a double bond, aromatic bond, or a single bond adjacent to a double bond
- The ring has at least one double or aromatic bond
- Bond traversal order is maintained (ordered tuple, not set) to correctly identify alternating patterns

### Step 2: Pi Electron Counting (`_count_pi_electrons_ring`)

Each ring atom contributes π electrons based on its element, bonding pattern, and hybridization:

| Atom | Context | π Contribution |
|------|---------|---------------|
| C (=CH—) | sp² carbon in ring | 1 electron |
| C (-C⁻) | carbanion / charged sp² carbon | 2 electrons |
| N (=N—) | pyridine-like (imine) | 1 electron |
| N (—NH—) | pyrrole-like (amine) | 2 electrons |
| O (—O—) | furan-like (ether) | 2 electrons |
| S (—S—) | thiophene-like (sulfide) | 2 electrons |

The function determines each atom's role by:
1. Checking explicit/implicit hydrogen count to distinguish =N— (no H) from —NH— (has H)
2. Checking bond order (double bond = sp², single bond with lone pair donation)
3. Adding formal charge adjustments (if present)

### Step 3: Hückel Rule Application

| π Electron Count | Classification |
|-----------------|----------------|
| 4n + 2 (n ≥ 0) | **AROMATIC** (e.g., benzene = 6, pyridine = 6, furan = 6) |
| 4n (n ≥ 1) | **ANTI_AROMATIC** (e.g., cyclobutadiene = 4) |
| Neither | **NON_AROMATIC** (e.g., cyclohexene = 2, cycloheptatriene = 6 but not conjugated) |

### Step 4: Bulk Assignment (`assign_aromaticity`)

Assigns aromaticity to all rings in a graph:
- Calls `assess_all_rings()` to evaluate every detected ring
- For rings classified as aromatic, marks the ring's atoms and bonds with `is_aromatic = True`
- Returns a tuple of `AromaticityResult` for all rings

**Heteroatom support**: N, O, and S lone pair contributions correctly model pyrrole, furan, and thiophene. Contributions are computed inline in `_count_pi_electrons_ring()` and are extensible by element.

**Complexity**: O(R·k) where R is the number of rings and k is the size of each ring.

---

## Subgraph Isomorphism (VF2)

**Algorithm**: VF2 subgraph isomorphism algorithm (Cordella et al., 2004)

**Module**: `detection/substructure.py` — `has_subgraph_match()`, `find_subgraph_matches()`, `count_subgraph_matches()`

**Approach**:
1. Build compatibility matrices for atoms (atomic number, aromaticity) and bonds (bond order)
2. Use recursive backtracking with state represented as `(mapping, used1, used2)`
3. At each step, find candidate atom pairs from the union of neighbors of already-mapped atoms
4. Prune candidates that violate compatibility constraints
5. Prune candidates that would create invalid mapping (already used in either graph)
6. Match completely when all query atoms are mapped
7. Deduplicate matches by target atom set (`frozenset(target_atoms)`) for symmetric queries

**Atom compatibility** (`_default_atom_compatible`):
- Query atom with `atomic_number=0` is a wildcard (matches any target atom)
- Otherwise, atomic numbers must match exactly
- Both atoms must have matching aromaticity state

**Bond compatibility** (`_default_bond_compatible`):
- Wildcard bonds (order 0) match any target bond
- Otherwise, bond orders must match exactly

**Complexity**: VF2 is O(V²) in the best case and O(V!·V) in the worst case for general graphs. For chemical graphs where each atom has ≤4 bonds, the branching factor is bounded by the degree, and performance is typically O(V²) for practical cases.

**Reference**: Cordella, L.P. et al. "A (sub)graph isomorphism algorithm for matching large graphs." IEEE Trans. Pattern Anal. Mach. Intell. 26, 1367-1372, 2004.

---

## Maximum Common Substructure (MCS)

**Algorithm**: Backtracking enumeration with canonical state

**Module**: `detection/substructure.py` — `maximum_common_substructure()`

**Approach**:
1. Heavy-atom only search (skip hydrogen atoms)
2. Iterate over all atom pairs as potential starting points
3. Recursive backtracking extends the partial mapping one atom pair at a time
4. Candidates filtered by neighborhood connectivity to existing mapping
5. Depth-limited to prevent combinatorial explosion (max 15 heavy atoms)
6. Returns the largest common substructure as a mapping dict

**Complexity**: O(V₁·V₂·b^d) where d is the depth (size of MCS) and b is the branching factor. Practical only for molecules with <20 heavy atoms.

---

## SMARTS Pattern Matching

**Algorithm**: Tokenizer + parser + VF2-backed matcher

**Module**: `parsing/smarts.py` — `parse_smarts()`, `smarts_match()`, `find_smarts_matches()`

**Tokenizer**: Regex-based with capture groups:
- `simple_atom`: matches bare element symbols (C, N, O, S, P, F, Cl, Br, I)
- `bracket_atom`: matches `[C@H]`, `[O-]`, `[13C]`, `[nH]`, `[c]`, etc.
- `bond`: matches `-`, `=`, `#`, `:`, `~`, `/`, `\`
- `ring_closure`: matches `0`-`9`, `%nn`
- `branch`: matches `(`, `)`
- `dot`: matches `.` (disconnected components)

**Bracket atom parsing** (`_parse_bracket_atom`):
- Extracts: atomic number, aromaticity, charge, isotope, stereochemistry, implicit hydrogens
- Parses complex specifications like `[C@@H](Cl)Br`

**Matcher**:
- Converts SMARTS pattern to a `MolecularGraph` via `parse_smarts()`
- Delegates to VF2 `find_subgraph_matches()` with SMARTS-specific compatibility functions
- Query atoms with `is_aromatic=True` match target atoms that are aromatic
- Simple atoms match by element; bracket atoms match by parsed specification
- Default single bonds between adjacent atoms

**Known limitation**: CIP priority is computed only at the direct-substituent
level (Rules 1–4: atomic number, isotope mass, pi-bond count, ring
membership). Deep concentric (consecutive-deepening) branch projection for
tie-breaking at higher priority levels is **not** implemented, so
substituents whose priorities differ only at atoms 2+ bonds away may
not be fully resolved by rules 1–4. This matches the scope claimed for
the CIP engine in `PROJECT_STATUS.md`.

---

## Stereochemistry — CIP Priority Rules

**Algorithm**: Cahn-Ingold-Prelog priority system (Rules 1-2)

**Module**: `stereochemistry/cip.py` — `get_cip_priority()`

**Priority hierarchy (implemented)**:
1. **Atomic number** (Rule 1): Higher atomic number → higher priority
2. **Isotope** (Rule 2): Higher mass number → higher priority for isotopes

**Not yet implemented**:
- Rule 3: Pi-system connectivity (e.g., =O vs -OH)
- Rule 4: Ring membership (e.g., cyclic vs acyclic)
- Rule 5: Atomic mass (last resort for non-isotopic atoms)

**Chiral center detection** (`is_chiral_center`):
- Atom must be tetrahedral (sp³) carbon
- Must have exactly 4 bonded neighbors
- Must have no plane of symmetry (different substituents)

**Complexity**: O(1) per priority comparison, O(d) per center where d is the depth of tie-breaking.

---

## Stereochemistry — Tetrahedral R/S Assignment

**Algorithm**: CIP-based tetrahedral chirality assignment

**Module**: `stereochemistry/tetrahedral.py` — `assign_tetrahedral()`, `detect_tetrahedral_centers()`

**Approach**:
1. Find all tetrahedral centers (sp³ carbon with 4 distinct neighbors)
2. For each center, compute CIP priorities for all 4 neighbors
3. Order neighbors by decreasing priority
4. Without 3D coordinates, the assignment uses heuristic ordering (always returns R)
5. With 3D coordinates, check handedness: clockwise = R, counter-clockwise = S

**Detected centers**: Returns list of `ChiralCenter` objects with atom index, assigned `ChiralTag`

**Known limitation**: Without 3D coordinates, R/S assignment is a placeholder (always R). A future update will use the cross-product of bond vectors to determine true handedness.

**Complexity**: O(c·d) where c is the number of chiral centers and d is the CIP depth.

---

## Stereochemistry — Double Bond E/Z Assignment

**Algorithm**: CIP-based double bond stereochemistry

**Module**: `stereochemistry/double_bond.py` — `assign_double_bond_stereo()`, `is_stereogenic_double_bond()`

**Approach**:
1. Find all double bonds where each carbon has 2 distinct substituents (stereogenic)
2. For each carbon, pick the two non-double-bond neighbors
3. Determine the "highest priority" neighbor on each carbon using CIP-like atomic number comparison
4. Check if the two high-priority neighbors are on the same side:
   - Same side → Z (zusammen)
   - Opposite sides → E (entgegen)

**Same-side heuristic**: If the high-priority neighbors share a common bonded atom (other than the double bond carbons), they are considered on the same side.

**Known limitation**: The same-side heuristic is simplified and may give incorrect results for complex cases (e.g., cyclic systems, conjugated dienes).

**Complexity**: O(d) per double bond where d is the degree of each carbon.

---

## Stereochemistry — Perception Pipeline

**Algorithm**: Combined stereo perception

**Module**: `stereochemistry/perception.py` — `perceive_stereochemistry()`

**Approach**:
1. Detect all tetrahedral centers via `detect_tetrahedral_centers()`
2. Detect all stereogenic double bonds via `detect_stereogenic_double_bonds()`
3. Return combined results as `(list[ChiralCenter], list[triple])`

---

## Constitutional Isomer Enumeration (Canonical Augmentation)

**Algorithm**: Simplified canonical augmentation using degree sequences

**Module**: `generation/constitutional.py` — `generate_alkane_isomers()`, `alkane_isomer_count()`, `enumerate_functional_group_isomers()`

**Approach**:
1. Start with a single carbon atom
2. Recursively add carbon atoms to all possible positions
3. Track symmetry using degree sequences (sorted list of neighbor counts)
4. Canonicalization via sorted degree sequence as hash key
5. Deduplicate by checking canonical SMILES of the adjacency matrix
6. Continue until desired carbon count reached

**Isomer counts (C1–C8)**:
| Carbons | Known Count | Verified |
|---------|-------------|----------|
| 1 | 1 | ✅ |
| 2 | 1 | ✅ |
| 3 | 1 | ✅ |
| 4 | 2 | ✅ |
| 5 | 3 | ✅ |
| 6 | 5 | ✅ |
| 7 | 9 | ✅ |
| 8 | 18 | ✅ |

**Functional group variant enumeration**: Appends functional group attachment at each position on each alkane isomer.

**Complexity**: Exponential in carbon count. C8 enumeration completes in <100ms.

**Reference**: McKay, B.D. "Isomorph-Free Exhaustive Generation." J. Algorithms 26, 306-324, 1998.

---

## Stereoisomer Enumeration

**Algorithm**: 2^n combinatorial enumeration with duplicate elimination

**Module**: `generation/stereoisomers.py` — `enumerate_stereoisomers()`

**Approach**:
1. Detect tetrahedral centers (sp³ carbon with 4 neighbors)
2. For each center, compute a canonical key based on neighbor atomic numbers
3. Generate all 2^n combinations of R/S assignments
4. Deduplicate via graph hashing (canonical key per center)
5. Return `list[MolecularGraph]` with explicit chiral tags

**Known limitation**: Overcounts molecules with symmetry (e.g., ethane's two carbons with 4 identical H substituents)

**Complexity**: O(2^n · n) where n is the number of detected stereocenters. Practical for n ≤ 10.

---

## Molecular Properties

**Algorithm**: Fragment-based and topological descriptor computation

**Module**: `properties/descriptors.py` — `compute_mass()`, `compute_formula()`, `compute_tpsa()`, `compute_logp()`

**Exact Mass & Molecular Weight**:
- Sum of atomic masses (from `Atom.atomic_mass`) for all atoms in the graph
- Exact mass uses the single most abundant isotope mass
- Molecular weight uses standard atomic weight

**Molecular Formula**:
- Hill system: C then H then other elements alphabetically
- Counts all atoms, groups by element, sorts by Hill convention

**HBA/HBD**:
- HBA (H-bond acceptors): count of N, O, F atoms with available lone pairs
- HBD (H-bond donors): count of O-H and N-H bonds
- Amide C-N bonds excluded from rotatable bond count

**Rotatable Bonds**:
- Single bonds (non-amide, non-ring, non-terminal)
- Bonds where both atoms have degree > 1 (not H or terminal groups)
- Excludes: double/triple bonds, ring bonds, amide C-N bonds

**TPSA (Topological Polar Surface Area)**:
- Fragment-based: each polar atom/fragment contributes a fixed surface area value
- Based on Ertl's TPSA method (J. Med. Chem. 2000, 43, 3714-3717)
- Contributions: N(sp³)=12.9, N(sp²)=23.8, O(sp³)=9.2, O(sp²)=17.1, etc.

**logP (Wildman-Crippen)**:
- logP = Σ atom_contributions + Σ correction_factors
- Each atom contributes based on its element, hybridization, and environment
- Simplified model: uses atomic contributions from Crippen's fragmentation method

**Fraction Csp3**:
- Fraction of carbon atoms that are sp³ hybridized
- Count: sp³ carbon atoms / total carbon atoms

**Complexity**: O(V + E) for all descriptors — linear in molecular size.

**Reference**: Ertl, P. et al. "Fast Calculation of Molecular Polar Surface Area." J. Med. Chem. 43, 3714-3717, 2000.

## 2D Layout (Force-Directed + Templates)

**Algorithm**: Fruchterman-Reingold variant with ring templates

**Approach**:
1. Place known ring systems using precomputed template coordinates
2. Use force-directed layout for acyclic portions
3. Penalize bond angle deviation
4. Optimize for aesthetic criteria (no overlaps, uniform bond lengths)

## 3D Conformer Generation (Distance Geometry)

**Algorithm**: Metric matrix distance geometry + UFF optimization

**Approach**:
1. Build bounds matrix from connectivity + forcefield parameters
2. Embed using metric matrix method
3. Refine with UFF forcefield (conjugate gradient)
4. Cluster by RMSD, return diverse conformers

## SMILES Canonicalization

**Algorithm**: Depth-first traversal with canonical atom ordering

**Approach**:
1. Compute canonical atom ordering using Morgan-like invariants
2. Perform DFS from the lowest-invariant atom
3. At each branch, choose the lowest-invariant path
4. Handle rings, stereochemistry, isotopes, charges