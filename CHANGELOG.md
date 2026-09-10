# Changelog

All notable changes to ChemEngine are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-09-01

### Added

#### Phase 1: Stabilization (Completed)
- **Hypothesis Property-Based Tests** (`tests/test_property_based.py`) — 19 new `@given` tests
  - Formula parser round-trips: `parse_formula` → `formula_to_graph` → `molecular_formula`
  - InChI parser correctness: `_parse_formula_layer`, connections, hydrogens
  - Alias resolver consistency: case-insensitive lookup, graph generation
  - SMILES round-trips: element preservation, bond preservation, formula preservation
  - Alkane chain and branched alkane round-trips
- **SPECIFICATIONS.md** (`docs/SPECIFICATIONS.md`) — Formal specs for all supported formats
  - SMILES grammar (EBNF), supported features, edge cases
  - InChI layers, atom numbering, known limitations
  - Molecular formula (Hill system), SMARTS, JSON schema
  - Coordinate generation, SVG rendering, reaction model
- **Benchmark Baselines** (`tests/test_benchmark_baselines.py`) — 13 baseline + 7 correctness tests
  - SMILES parsing, formula parsing, graph construction
  - Ring detection, element lookup, stereo perception
  - TPSA/logP computation, 2D layout, SVG rendering

#### Phase 6 v2.0: Enhanced Stereochemistry
- **Atropisomer Detection** (`stereochemistry/stereo_validation.py`)
  - `Atropisomer` dataclass: bond, priority groups, rotation barrier, chirality label
  - `detect_atropisomer_candidates(graph)` — biaryl systems with ortho substituents
  - Amide C-N restricted rotation detection
- **Stereo Validation** (`stereochemistry/stereo_validation.py`)
  - `StereoValidationResult` with issues, atropisomers, counts
  - `StereoIssue` with type, severity, message, atom/bond indices
  - `StereoIssueType` enum: CONFLICT, AMBIGUOUS, MISSING, ATROPOISOMER, INCONSISTENT
  - `validate_stereochemistry(graph)` — full validation pipeline
  - Missing assignment detection (stereocenter without stereo tag)
  - Legacy cis/trans notation warning
- **9 new tests** in `tests/test_stereo_v2.py`

#### Phase 7 v2.0: Enhanced Isomer Generation
- **Isomer Filtering** (`generation/filtering.py`)
  - `IsomerFilter` composable filter class
  - Filters: by formula, mass range, heavy atom count, element, bonds, custom predicate
  - `apply(isomers)` for list processing, `apply_lazy(iterator)` for streaming
- **Lazy Iteration** (`generation/filtering.py`)
  - `lazy_alkane_isomers(n)` — generator-based isomer enumeration
  - `lazy_filtered_isomers(isomers, filter, max_results)` — lazy filtered iteration
  - `count_isomers_lazy(isomers)` — count without storing
- **12 new tests** in `tests/test_generation_v2.py`

#### Phase 13: AI Integration
- **Streaming Support** (`core/ai_integration.py`)
  - `StreamingIterator` — chunked streaming with cancel support
  - `StreamChunk` dataclass: chunk_id, data, is_final, metadata
  - `stream_isomers()`, `stream_substructure_matches()` convenience functions
- **Enhanced Tool Registry** (`core/ai_integration.py`)
  - `ToolRegistry` with query by name, category, capability
  - `to_openai_format()` — OpenAI function-calling format conversion
  - `to_anthropic_format()` — Anthropic tool-use format conversion
  - `to_json_schema()` — full JSON Schema export
  - `create_tool_registry()` — pre-populated with 11 tools
- **Offline Inference** (`core/ai_integration.py`)
  - `OfflineInference` class with local model and fallback strategy support
  - `register_local_model()`, `register_fallback()`, `execute_inference()`
- **25 new tests** in `tests/test_ai_integration.py`

#### Phase 14: Performance
- **Profiler** (`utils/performance.py`)
  - `Profiler` class with decorator and manual timing
  - `ProfileResult` with call count, avg/min/max/total timing
  - `summary()` for human-readable output
- **Enhanced Cache** (`utils/performance.py`)
  - `EnhancedCache` with LRU eviction, TTL expiration, thread safety
  - Hit/miss statistics, `hit_rate` property
- **Batch Processing** (`utils/performance.py`)
  - `batch_process()` with progress callbacks
  - `parallel_batch_process()` with ThreadPoolExecutor
- **18 new tests** in `tests/test_performance.py`

### Test Suite
- **Total**: 1116 passing, 1 skipped
- **New test files**: test_property_based.py, test_benchmark_baselines.py, test_stereo_v2.py, test_generation_v2.py, test_ai_integration.py, test_performance.py
- **New source modules**: stereochemistry/stereo_validation.py, generation/filtering.py, core/ai_integration.py, utils/performance.py

---

## [0.10.0] — 2026-07-21

### Added

#### Molecular Properties (`properties/descriptors.py`) — NEW MODULE
- `compute_mass(graph)` — exact mass and molecular weight
- `compute_formula(graph)` — Hill system formula
- `compute_empirical_formula(graph)` — empirical formula
- `compute_hba(graph) / compute_hbd(graph)` — H-bond acceptor/donor counts
- `compute_rotatable_bonds(graph)` — rotatable bond count (excludes amide C-N, ring bonds, terminal bonds)
- `compute_tpsa(graph)` — topological polar surface area (fragment contributions)
- `compute_logp(graph)` — Wildman-Crippen logP
- `compute_fraction_csp3(graph)` — fraction of sp3 carbons
- `compute_heavy_atom_count(graph)` — heavy (non-hydrogen) atom count
- `compute_ring_count(graph) / compute_aromatic_ring_count(graph)` — ring statistics
- `compute_all_descriptors(graph)` — batch computation of all properties
- `properties/__init__.py` exports all descriptor functions

#### Tests
- **17 new tests** in `tests/test_properties.py`:
  - Mass, MW, formula for water, ethanol, benzene
  - HBA/HBD for water, ethanol, diethyl ether
  - TPSA, logP, rotatable bonds for reference molecules
  - Fraction Csp3, heavy atom count, ring counts

#### Benchmarks
- **15 new benchmarks** in `benchmarks/benchmark_phases5_8.py` (Phases 5-8 combined)

**Total**: 807 passing (was 750), 1 pre-existing skip

### Fixed

#### SMARTS Branch Handling (`parsing/smarts.py`)
- Replaced `NotImplementedError` for `(` `)` tokens with full branch parsing
- Uses `attachment_point` + `branch_stack` approach: `(` pushes current attachment, `)` pops and restores
- Supports: simple branches `C(C)C`, multiple branches `C(C)(C)C`, bonded branches `CC(=O)O`, nested branches `C(C(C)C)C`
- Ring closures with bounds checks

#### CIP Priority Rules (stereochemistry/cip.py)
- Added CIP Rule 3 (pi-bond connectivity): `_get_pi_count()` counts double/triple bonds as multiple attachments
- Added CIP Rule 4 (ring membership): ring atoms get priority tie-break
- Score tuple expanded to `(z, mass, pi, ring, idx)`
- Fixed missing `BondOrder` import causing `NameError`

#### R/S Tetrahedral Assignment (stereochemistry/tetrahedral.py)
- `_get_clockwise_order` now uses cross-bond parity among top-3 substituents
- Even cross-bonds → clockwise → R; Odd → counterclockwise → S
- No longer always returns R — structure-dependent deterministic assignment

#### E/Z Double Bond Stereochemistry (stereochemistry/double_bond.py)
- Improved E/Z heuristic: three-tier connectivity check
- Direct h1↔h2 connectivity → same side (Z), cross-check via low-priority substituents
- More robust than previous shared-neighbor heuristic

#### Isomer Canonicalization (generation/constitutional.py)
- Replaced degree-sequence canonicalization with sorted atomic signatures
- Each atom signature: `(degree, sorted_neighbor_degrees)`
- Eliminates collisions for C6+ alkanes (e.g., 2,2-dimethylbutane vs 3-methylpentane)
- All C1-C8 isomer counts verified correct

#### HBA Counting (properties/descriptors.py)
- `compute_hba` now excludes quaternary N⁺ with 4 bonds (no lone pair)
- O always counted as HBA; F counted only if degree < 1

#### Benchmark Fixtures (benchmarks/benchmark_core.py)
- Fixed 2 pre-existing fixture errors (`ethane_graph`, `benzene_graph`)
- Tests now build graphs inline instead of depending on missing fixtures

---

## [0.9.0] — 2026-07-21

### Added

#### Isomer Generation (`generation/`) — NEW MODULE

**Constitutional Isomers** (`generation/constitutional.py`):
- `generate_alkane_isomers(carbon_count)` — enumerates alkane constitutional isomers
- `alkane_isomer_count(carbon_count)` — returns known isomer counts for C1-C8
- `enumerate_functional_group_isomers(carbon_count, functional_group)` — FG variant enumeration

**Stereoisomers** (`generation/stereoisomers.py`):
- `enumerate_stereoisomers(graph)` — 2^n enumeration of tetrahedral centers
- Tetrahedral center detection (sp3 carbon with 4 distinct neighbors)
- Duplicate elimination via graph hashing
- `generation/__init__.py` properly exports all generation functions

#### Tests
- **9 new tests** in `tests/test_generation.py`:
  - Alkane isomer counts for C1-C8 (6 tests)
  - Stereoisomer detection and enumeration (3 tests)

**Total**: 790 passing (was 781), 1 pre-existing skip

---

## [0.8.0] — 2026-07-21

### Added

#### Stereochemistry Engine (`stereochemistry/`) — NEW MODULE

**CIP Priority Rules** (`stereochemistry/cip.py`):
- `get_cip_priority(graph, center_atom, neighbor_atom) -> int` — assigns CIP priority by atomic number then isotope
- `_get_neighbor_graph(graph, center_atom, neighbor_atom)` — builds subgraph for tie-breaking
- `is_chiral_center(graph, atom_index) -> bool` — checks if an atom is a stereocenter
- Handles non-metals, hydrogen, and standard organic elements

**Tetrahedral R/S** (`stereochemistry/tetrahedral.py`):
- `assign_tetrahedral(graph, center) -> ChiralTag` — R/S assignment
- `_get_clockwise_order(graph, center, neighbors)` — neighbor ordering heuristic
- `detect_tetrahedral_centers(graph) -> list[ChiralCenter]` — finds all tetrahedral centers

**Double Bond E/Z** (`stereochemistry/double_bond.py`):
- `assign_double_bond_stereo(graph, bond) -> BondStereo` — E/Z assignment
- `is_stereogenic_double_bond(graph, bond) -> bool` — checks if a double bond has stereochemistry
- `detect_stereogenic_double_bonds(graph) -> list[tuple[int, int, BondStereo]]` — finds all stereo double bonds

**Perception Pipeline** (`stereochemistry/perception.py`):
- `perceive_stereochemistry(graph) -> tuple[list[ChiralCenter], list[tuple[int, int, BondStereo]]]` — full pipeline

#### Module Integration
- `stereochemistry/__init__.py` exports all module functions
- `stereochemistry/cip.py` with `get_cip_priority`, `is_chiral_center`
- `stereochemistry/tetrahedral.py` with R/S assignment
- `stereochemistry/double_bond.py` with E/Z assignment

#### Tests
- **7 new tests** in `tests/test_stereochemistry.py`:
  - CIP priority for chiral centers
  - Tetrahedral center detection (alanine, lactic acid)
  - Double bond E/Z assignment (2-butene, 2-pentene)
  - Full stereo perception pipeline integration

**Total**: 781 passing (was 774), 1 pre-existing skip

---

## [0.7.0] — 2026-07-21

### Added

#### Substructure Search (`detection/substructure.py`) — NEW MODULE
- `has_subgraph_match(graph, query_graph, atom_compatible=None, bond_compatible=None) -> bool` — VF2 subgraph isomorphism
- `find_subgraph_matches(graph, query_graph, atom_compatible=None, bond_compatible=None) -> list[dict[int, int]]` — all matches with dedup by target atom set
- `count_subgraph_matches(graph, query_graph, ...) -> int` — match counting
- `maximum_common_substructure(graph1, graph2, atom_compatible=None, bond_compatible=None) -> dict[int, int] | None` — MCS (heavy-atom only, depth-limited)
- `_default_atom_compatible` — handles wildcard (atomic_number=0), atomic number matching
- `_default_bond_compatible` — handles wildcard, bond order matching
- VF2 deduplication uses `frozenset(target_atoms)` for correct handling of symmetric matches

#### SMARTS Engine (`parsing/smarts.py`) — NEW MODULE
- `parse_smarts(pattern) -> MolecularGraph` — SMARTS pattern parser
- `smarts_match(graph, pattern) -> bool` — check if a SMARTS pattern matches
- `find_smarts_matches(graph, pattern) -> list[dict[int, int]]` — find all SMARTS matches
- `count_smarts_matches(graph, pattern) -> int` — count SMARTS matches
- Tokenizer with regex groups: `simple_atom`, `bracket_atom`, `bond`, `ring_closure`, `branch`, `dot`
- Bracket atom parsing: atomic number, aromaticity, charge, isotope
- Default single bond between adjacent atoms
- Simple atom support: `C`, `N`, `O`, `S`, `P`, `F`, `Cl`, `Br`, `I`
- SMARTS matching delegates to VF2 with appropriate compatibility functions

#### Module Integration
- `detection/__init__.py` exports VF2 functions (`has_subgraph_match`, `find_subgraph_matches`, `count_subgraph_matches`, `maximum_common_substructure`)
- `parsing/smarts.py` exports `parse_smarts`, `smarts_match`, `find_smarts_matches`, `count_smarts_matches`

#### Tests
- **24 new tests** in `tests/test_substructure.py`:
  - VF2 basic matching: ethyl vs ethanol, CC vs propane
  - VF2 ring matching: benzene vs ethanol (no match), benzene in napthalene
  - VF2 aromatic matching: [c] in ethanol/smiles
  - SMARTS matching: C=O match, [O] matching
  - MCS: carbon chain matching, ethanol match
  - Edge cases: empty query, singleton query, tautomer-not-detected

**Total**: 774 passing (was 750), 1 pre-existing skip

---

## [0.6.0] — 2026-07-21

### Added

#### Enhanced Ring Detection (`detection/rings.py`)
- `detect_rings()` now returns `tuple[Ring, ...]` with `Ring` dataclass objects containing `atom_indices`, `bond_indices`, and `size` — replaces old `tuple[tuple[int, ...], ...]` return type
- `find_all_rings(graph, max_size=12)` — enumerates all simple cycles up to configurable size
- `is_ring_bond(graph, a1, a2)` — checks if a bond is part of any ring (complements existing `is_ring_atom`)
- `ring_count(graph)` — quick count of detected rings
- Internal helpers: `_build_adjacency()`, `_ring_atoms_to_bonds()`, `_check_ring_aromatic()`
- `Ring` dataclass expanded with `bond_indices` field for bond-level ring queries

#### Ring System Analysis (`detection/ring_systems.py`) — NEW MODULE
- `RingSystem` dataclass: `ring_indices`, `atom_indices`, `system_type`
- `RingSystemType` enum: `ISOLATED`, `FUSED`, `SPIRO`, `BRIDGED`, `COMPLEX`
- `detect_ring_systems(graph, rings) -> tuple[RingSystem, ...]` — classifies all ring systems via ring adjacency graph and connected components
- `is_spiro_center(graph, atom_index) -> bool` — detects atoms shared by 2+ rings with no other shared atoms
- `is_bridgehead_atom(graph, atom_index) -> bool` — detects atoms belonging to 3+ rings (bridgehead positions)
- Internal helpers: `_build_ring_adjacency()`, `_determine_system_type()`, `_find_connected_components()`

#### Hückel Aromaticity Detection (`detection/aromaticity.py`) — NEW MODULE
- `AromaticityType` enum: `AROMATIC`, `ANTI_AROMATIC`, `NON_AROMATIC`
- `AromaticityResult` dataclass: `ring`, `pi_electrons`, `result`, `reason`
- `assess_ring_aromaticity(graph, ring) -> AromaticityResult` — evaluates a single ring
- `assess_all_rings(graph) -> tuple[AromaticityResult, ...]` — evaluates all detected rings
- `assign_aromaticity(graph)` — bulk-assigns `is_aromatic` flags to atoms and bonds
- `_is_conjugated_ring(graph, ring_atoms)` — checks alternating double/aromatic bond pattern
- `_count_pi_electrons_ring(graph, ring_atoms)` — counts π electrons per atom:
  - C (=CH— sp²): 1 electron
  - C (-C⁻ carbanion): 2 electrons
  - N (=N— pyridine-like): 1 electron
  - N (—NH— pyrrole-like): 2 electrons
  - O (—O— furan-like): 2 electrons
  - S (—S— thiophene-like): 2 electrons
- Hückel rule: 4n+2 = aromatic, 4n = anti-aromatic, otherwise non-aromatic

#### Detection Module Exports (`detection/__init__.py`)
- Exports all new symbols: `RingSystem`, `RingSystemType`, `detect_ring_systems`, `is_spiro_center`, `is_bridgehead_atom`, `AromaticityResult`, `AromaticityType`, `assess_ring_aromaticity`, `assess_all_rings`, `assign_aromaticity`, `find_all_rings`, `is_ring_bond`

### Changed

- `detect_rings()` return type changed from `tuple[tuple[int, ...], ...]` to `tuple[Ring, ...]` — **breaking change**; all callers updated to use `ring.atom_indices`, `ring.size`, `ring.bond_indices`
- `test_rings.py` updated to use new `Ring` object API (8 tests)

### Fixed

- Ring traversal now preserves atom ordering via ordered `tuple` (not unordered `frozenset`) for correct aromaticity conjugation checks
- `_is_conjugated_ring` parameter corrected from `set[int]` to `tuple[int, ...]` to preserve traversal order
- Removed dead code in `_is_conjugated_ring` (unused `all_sp2_or_aromatic` variable and empty conditional)
- `is_spiro_center()` now correctly accepts both `graph` and `atom_index` positional arguments

### Tests

- **26 new tests** in `tests/test_rings_enhanced.py`:
  - Enhanced ring detection: single ring, fused (naphthalene), bicyclic, ring atom/bond queries (8 tests)
  - Ring system analysis: isolated, fused, spiro, bridged, empty graph, mixed systems (8 tests)
  - Aromaticity assessment: benzene (aromatic 6π), cyclobutadiene (anti-aromatic 4π), cyclohexene (non-aromatic 2π), pyridine (aromatic 6π w/ N), furan (aromatic 6π w/ O), integration (7 tests)
  - Spiro center detection: spiro vs non-spiro (2 tests)
  - Bridgehead detection: adamantane-like (1 test)

- **Total**: 750 passing (was 724), 1 pre-existing skip

---

## [0.5.0] — 2026-07-20

### Added

#### Functional Group Engine (`detection/functional_groups.py`) — NEW MODULE
- `FunctionalGroupMatch` dataclass: `name`, `category`, `atom_indices`, attributes for overlap resolution
- `detect_functional_groups(graph) -> list[FunctionalGroupMatch]` — detects all 21+ functional groups
- `detect_functional_groups_dict(graph) -> dict[str, list[dict]]` — dict-based API compatible with `ChemEngineAPI`
- 21 functional group detectors with dedicated functions:
  - Oxygen groups: Alcohol, Phenol, Ether, Aldehyde, Ketone, Carboxylic Acid, Ester (7)
  - Nitrogen groups: Amine (1°/2°/3°), Amide, Nitrile, Nitro (6)
  - Sulfur groups: Thiol, Sulfide, Sulfoxide, Sulfone (4)
  - Halogen: F, Cl, Br, I (1)
  - Hydrocarbon: Alkene, Alkyne, Aromatic Ring (3)
- Priority-based overlap resolution (highest-priority group wins when atoms overlap)
- Category hierarchy: Phenol → Alcohol, Aldehyde → Carbonyl, Ketone → Carbonyl, Carboxylic Acid → Carbonyl, Ester → Carbonyl, Amide → Carbonyl, Amine (hierarchical by substitution)
- `_heavy_neighbors(graph, atom)` helper — filters out explicit hydrogen atoms (SMILES parser compatibility)
- Fallback to hardcoded detectors if dataset-driven approach fails

#### Detection Module Integration
- `detection/__init__.py` expanded with FG exports
- `ChemEngineAPI._exec_detect_functional_groups()` — real FG detection (replaced placeholder)
- Tool definition for `detect_functional_groups` with JSON Schema

#### Tests
- **55 new tests** in `tests/test_functional_groups.py`:
  - All 21 group detectors tested with reference molecules
  - Overlap resolution with priority-based conflict detection
  - Hierarchy inheritance (e.g., Phenol resolving from Alcohol)
  - Edge cases: methane (no groups), water (no groups), complex multi-group molecules
  - Integration with `ChemEngineAPI`

- **Total**: 724 passing (was 669), 1 pre-existing skip

### Changed

- `test_api.py` `test_detect_functional_groups` — now expects real FG results instead of empty `[]`

---

## [0.4.0] — 2026-07-20

### Added

#### Molecular Validation (`validation/`) — NEW MODULE
- `ValidationError` dataclass: `rule`, `severity` (ERROR, WARNING, INFO), `message`, `atom_indices`, `bond_indices`
- `ValidationResult` dataclass: `passed`, `errors`, `warnings`, `infos`, per-rule breakdown
- `ValidationReport` dataclass: `molecule_id`, `timestamp`, `profile`, `results`, `overall_passed`
- `ValidationRule` protocol with `name`, `description`, `severity`, `__call__(graph) -> list[ValidationError]`
- 9 built-in validation rules:
  - Valence check: total bonds + implicit H against valence_rules.toml
  - Hypervalent check: max valence exceptions for S, P, etc.
  - Charge check: formal charge against element-specific allowed ranges
  - Total charge consistency check
  - Isotope check: mass numbers against known isotopes
  - Graph structure: disconnected components, duplicate bonds, self-bonds
  - Valence saturation: unfilled valence detection
  - Radical detection: unpaired electrons
  - Aromatic consistency: aromatic atoms/bonds consistency
- `ValidationRuleSet` with 3 profiles: `strict`, `standard` (default), `relaxed`
- `ValidationEngine` for running profiles with rule ordering
- Graph sanitization: `add_implicit_hydrogens()`, `remove_duplicate_bonds()`, `sanitize()` in `validation/sanitize.py`

### Changed

- `MolecularGraph` now has `is_valid` property (cached), `validate()` method, `sanitize()` method
- `MolecularGraphBuilder.build()` accepts `validate=True` with configurable profile
- `ChemEngineAPI` has `validate()` and `sanitize()` tool definitions

#### Tests
- **59 new tests** in `tests/test_validation.py`
- **Total**: 669 passing (was 610), 1 pre-existing skip

---

## [0.3.0] — 2026-07-20

### Added

#### Infrastructure Tests (5 new test files)
- `tests/test_events.py` — 15 tests: EventBus subscribe, publish, unsubscribe, correlation IDs, thread safety, priorities, exceptions, singleton
- `tests/test_registry.py` — 14 tests: AlgorithmRegistry register, lookup, tag-based resolution, replace, unregister, clear, contains, alias
- `tests/test_datasets.py` — 14 tests: DatasetRegistry lazy loading, hot-reload, cache, watchers, register, clear, list_available
- `tests/test_plugin.py` — 8 tests: PluginManager discovery, load/unload, error handling, protocol
- `tests/test_api.py` — 21 tests: ChemEngineAPI tool listing, execution, error handling, conversion, computation, rendering
- `tests/test_molecule.py` — 7 tests: Molecule class construction, properties, graph ops, SMILES construction, adjacency
- Ring detection tests expanded to 8 tests

#### Regression Tests
- SMILES branch logic: 4 tests (simple, nested, complex/diamond, stress test with 10 branches)
- InChI hydrogen counting: 5 tests (H₂O, CH₄, NH₃, CO₂, C₂H₆ — all verify implicit H vs explicit H parity)

#### Documentation
- `docs/DOMAIN_MODEL.md` — Verified correct: uses `Coordinate2D`, `Coordinate3D`, `Charge`, `Isotope` (class names match source code)
- `docs/MODULES.md` — Verified correct: uses `ChiralCenter`, `StereoConfig`, `Coordinate2D`, `Coordinate3D` (all module-to-class mappings verified)

### Fixed

- **SMILES branch parsing**: Fixed bug where input `C(Cl)(Br)I` was parsed as `C(I)(Br)Cl` by adding branch count tracking and proper branch position restoration
- **InChI hydrogen double-counting**: Fixed by removing `_add_implicit_hydrogens_from_valence()` call from `parse_inchi()` — InChI provides explicit hydrogen positions in the `/h` layer; no additional implicit H should be computed

### Changed

- `tests/test_rings.py` — enhanced to verify ring atom membership (`is_ring_atom`) after detection

---

## [0.2.0] — 2026-07-20

### Added

#### SMILES Parser (`parsing/smiles.py`)
- Full production-quality SMILES tokenizer with regex-based tokenization
- `parse_smiles(smiles: str, *, validate: bool = True) -> MolecularGraph`
- `serialize_smiles(graph: MolecularGraph) -> str` — deterministic spanning-tree serializer
- Supports: standard atoms, organic subset, bracket atoms, aromatic atoms, single/double/triple/aromatic bonds, branches (parenthesized), ring closures (single and %-digits), disconnected components (`.`), charges (`+`, `-`, `++`, `--`, `+n`, `-n`), isotopes (`[13C]`), implicit hydrogens (`[nH]`, `[OH2]`), stereochemistry (`@`, `@@`), and wildcard atoms (`[*]`)
- Detailed parser errors with position information via `SmilesSyntaxError`
- Spanning-tree pre-pass for correct ring closure label emission
- Subtree-size branch ordering heuristic for canonical-like serialization
- Module separation: tokenization, parsing, validation, and graph construction are independent functions

#### SMILES Canonicalization (`parsing/canonical.py`)
- `canonical_smiles(graph: MolecularGraph) -> str` — Morgan-like iterative atom invariant refinement (extended connectivity)
- Initial invariants: atomic number, degree, heavy degree, charge, isotope, aromaticity, implicit H, stereochemistry, metallic character
- Iterative refinement using SHA-256 hashing of (current_invariant, sorted_neighbor_invariants)
- Convergence detection when all invariants become unique (max 10 iterations)
- Deterministic canonical ordering by (invariant, original_index)
- `is_canonical(graph, smiles) -> bool` — verifies a SMILES is canonical via graph equivalence

#### InChI Parser (`parsing/inchi.py`)
- `parse_inchi(inchi: str) -> MolecularGraph` — parses standard InChI strings into MolecularGraph
- Supports: formula layer (`/C6H6`, `/C2H6O`), connections layer (`/c1-2-4-6-5-3-1`), hydrogens layer (`/h1-6H`, `/h2H3`), charge layer (`/q+1`, `/q-2`)
- Handles branched connection paths with parenthesized side chains
- `InChIParser` class conforming to the `Parser` protocol
- `register_inchi_parser(registry)` for AlgorithmRegistry integration

#### Common Alias Resolver (`parsing/alias.py`)
- `resolve_alias(name: str) -> str | None` — maps 100+ common chemical names to SMILES
- Coverage: small molecules (water, ammonia, methane), solvents (benzene, ethanol, acetone), pharmaceuticals (aspirin, paracetamol, caffeine), amino acids (glycine, alanine, cysteine), simple ions (sodium, chloride), functional group patterns
- Case-insensitive lookup
- `resolve_alias_to_graph(name: str) -> MolecularGraph | None` — resolves and parses in one step
- `AliasParser` class conforming to the `Parser` protocol for `parse_any` integration

#### Format Auto-Detection (`parsing/protocol.py`)
- `auto_detect_format(text: str) -> str | None` — detects `'smiles'`, `'inchi'`, `'inchikey'`, `'formula'`, `'name'`, or `None`
- InChIKey detection (27-char format `XXXXXXXXXXXXXX-XXXXXXXXXXX-X`)
- Improved SMILES vs formula discrimination (digits required for formula)
- `parse_any(text, smiles_parser=..., formula_parser=..., alias_resolver=..., inchi_parser=...) -> MolecularGraph` — auto-detects format and dispatches to correct parser, with fallback chain

#### Property-Based Round-Trip Tests (`tests/test_smiles_property.py`)
- 87 parametrized SMILES round-trip tests covering diverse molecules (alkanes, aromatics, heterocycles, organometallics, sugars, pharmaceuticals, charged species, isotopes)
- `test_canonical_equivalent_inputs` — equivalent SMILES produce same canonical form
- `test_auto_detect_*` — format detection for SMILES, formulas, InChI, names, empty strings
- `test_alias_resolver_*` — alias resolution and parsing
- `test_inchi_*` — InChI parsing for water, benzene, ethanol
- `test_parse_any_*` — integrated multi-parser dispatch

### Infrastructure
- 468 total tests (342 pre-existing + 126 new), 1 skipped
- Test markers: `property` for hypothesis-based tests
- `hypothesis` added as dev dependency in `pyproject.toml`

### Fixed
- `_compute_implied_h(atom, graph)` — computes implicit hydrogens from valence rules for organic subset check during serialization, fixing pyrrole `[nH]` round-trip
- `_write_atom_smiles` — checks `stereochemistry == ChiralTag.NONE` before using organic subset shortcut; preserves `[C@@H]` and `[C@H]` in output
- Integer vs Enum comparison in `BondOrder` — uses `order_val == 1` instead of `order == BondOrder.SINGLE` for tuple sorting
- Ring label emission — spanning-tree pre-pass ensures both endpoints get ring closure labels
- Aromatic bond serialization — returns `""` (implicit) instead of `":"`
- Unclosed bracket detection — tokenizer regex catches `[C` without closing `]`
- `_reindex_graph` — now preserves all graph metadata (name, coordinates, stereo config, conformers, rings, properties)

---

## [0.1.0] — 2026-07-19

### Added

#### Core Domain Models (`core/`)
- `MolecularGraph` — immutable, self-contained graph with atoms, bonds, coordinates, stereochemistry, and computed properties. Single source of truth for all chemistry operations.
- `MolecularGraphBuilder` — mutable builder pattern for constructing graphs
- `Atom` — immutable atom model with charge, isotope, stereochemistry, hybridization, valence, implicit hydrogens, aromaticity
- `Bond` — immutable bond model with order, type, stereochemistry, topology, aromaticity, length
- `BondOrder` — enum: SINGLE, DOUBLE, TRIPLE, QUADRUPLE, AROMATIC, ZERO, UNSPECIFIED
- `ElementSymbol` — enum for all 118 elements with atomic number, symbol, name, period, group, block, category
- `ChiralTag` — NONE, TETRAHEDRAL_CW, TETRAHEDRAL_CCW
- `BondStereo` — NONE, CIS, TRANS, E, Z
- `Hybridization` — SP, SP2, SP3, SP3D, SP3D2, UNKNOWN
- `Coordinate2D`, `Coordinate3D`, `Conformer` — geometry models
- `ChiralCenter`, `StereoConfig` — stereochemistry container
- `Ring` — substructure ring representation
- `Isotope` — isotopic composition info

#### Periodic Table Dataset (`datasets/elements.json`)
- All 118 known elements with authoritative IUPAC data
- Fields: symbol, name, atomic number, atomic mass, period, group, block, category, electron configuration, oxidation states, covalent radius, van der Waals radius, electronegativity (Pauling), ionization energies, electron affinity, density, melting point, boiling point, phase at STP, isotopic mass number and abundance

#### Infrastructure
- `AlgorithmRegistry` — centralized algorithm discovery with domain/name/version/tags, hot-swappable at runtime
- `EventBus` — typed pub/sub with synchronous dispatch, correlation IDs, thread safety
- `PluginManager` — entry-point-based plugin discovery
- `DatasetRegistry` — lazy-loaded reference datasets from JSON/TOML files
- `ChemEngineAPI` — unified facade for AI/CLI/web consumers with JSON Schema tool definitions

#### Parsing (`parsing/`)
- `FormulaParser` — molecular formula parser (Hill system, hydrated forms, charged formulas)
- `Parser` protocol — structural subtyping for all chemical identifier parsers
- `auto_detect_format` — basic format detection (SMILES, InChI, formula, name)

#### Validation (`validation/`)
- Graph sanitization and valence rule checks
- Atom validity (atomic numbers 1-118), bond validity (no self-bonds, no duplicates)
- Valence limit checking against max valence per element

#### Configuration & Build
- `pyproject.toml` with hatchling build system, pytest config, mypy strict mode, ruff linter
- Dev dependencies: pytest, hypothesis, mypy, ruff, pytest-cov, sphinx, pre-commit

#### Documentation
- `VISION.md` — long-term vision, scope, core principles
- `ARCHITECTURE.md` — complete architecture overview
- `DOMAIN_MODEL.md` — all domain models documented
- `MODULES.md` — module responsibilities and interfaces
- `API_DESIGN.md` — public API conventions
- `ALGORITHMS.md` — algorithm descriptions with citations
- `ROADMAP.md` — phased delivery plan
- `TESTING.md` — test infrastructure and strategy
- `DECISIONS.md` — Architecture Decision Records (ADR-001 through ADR-010)
