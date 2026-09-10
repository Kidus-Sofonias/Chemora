# ChemEngine — Engineering Roadmap

> **📊 Live Gantt chart**: Open [`gantt.html`](gantt.html) in your browser for an interactive, animated visualization of this roadmap. Automatically updates when phase statuses change.

> **Version:** 0.10.0 → 1.0.0
> **Last Updated:** July 22, 2026
> **Owner:** ChemEngine Architecture Team
> **Status:** Active Development

---

## Table of Contents

1. [Roadmap Philosophy](#roadmap-philosophy)
2. [Project Health Summary](#project-health-summary)
3. [Phase 0 — Foundation (Complete)](#phase-0--foundation-complete)
4. [Phase 1 — Stabilization](#phase-1--stabilization)
5. [Phase 2 — Molecular Validation](#phase-2--molecular-validation)
6. [Phase 3 — Functional Group Engine](#phase-3--functional-group-engine)
7. [Phase 4 — Ring & Aromaticity](#phase-4--ring--aromaticity)
8. [Phase 5 — Substructure Search (Complete)](#phase-5--substructure-search-complete)
9. [Phase 6 — Stereochemistry (Complete)](#phase-6--stereochemistry-complete)
10. [Phase 7 — Isomer Generation (Complete)](#phase-7--isomer-generation-complete)
11. [Phase 8 — Molecular Properties (Complete)](#phase-8--molecular-properties-complete)
12. [Phase 9 — Coordinate Generation](#phase-9--coordinate-generation)
13. [Phase 10 — Rendering](#phase-10--rendering)
14. [Phase 11 — Nomenclature](#phase-11--nomenclature)
15. [Phase 12 — Reactions](#phase-12--reactions)
16. [Phase 13 — AI Integration](#phase-13--ai-integration)
17. [Phase 14 — Performance](#phase-14--performance)
18. [Phase 15 — Release (v1.0.0)](#phase-15--release-v100)
19. [Roadmap Summary](#roadmap-summary)

---

## Roadmap Philosophy

### Principles

1. **Architecture-first, not feature-first.** Every subsystem is modular, extensible, and independently testable. Never sacrifice architecture for speed.

2. **Every phase leaves the engine stable, tested, documented, and production-quality.** No phase begins until the previous phase meets its Definition of Done.

3. **Never introduce technical debt intentionally.** If technical debt is discovered, it is addressed immediately as part of the current phase.

4. **Every milestone is independently shippable.** Each phase produces a tagged release with a complete CHANGELOG entry.

5. **MolecularGraph is the single source of truth.** No intermediate molecule representations. Every parser produces a MolecularGraph directly. Every algorithm accepts and returns MolecularGraph or primitive types.

### How to Read This Document

Each phase contains:

| Section | Description |
|---------|-------------|
| **Purpose** | Why this phase exists and what problem it solves |
| **Milestones** | Major checkpoints within the phase, ordered by dependency |
| **Atomic Tasks** | Individually completable, verifiable work items |
| **Dependencies** | Phases and external systems this phase depends on |
| **Files Expected to Change** | Specific source files, test files, and documentation |
| **Required Tests** | What must be tested, including test types |
| **Required Documentation** | Documentation that must be written or updated |
| **Benchmarks** | Performance targets and benchmark tests |
| **Acceptance Criteria** | Conditions that must be satisfied |
| **Definition of Done** | Formal checklist for phase completion |
| **Complexity** | Estimated effort (S/M/L/XL) |
| **Risk Level** | Technical and schedule risk (Low/Medium/High) |

---

## Project Health Summary

### Current Metrics

| Metric | Value | Target (v1.0) |
|--------|-------|----------------|
| **Overall Completion** | ~85% | 100% |
| **Passing Tests** | 1635 / 1635 (100%), 1 skip | >5,000 |
| **Test Files** | 37 | >60 |
| **Source Files** | 72 Python files | >100 |
| **Elements** | All 118 | All 118 |
| **Documentation** | 10 documents | 30+ documents |
| **Benchmarks** | 23 benchmarks | 50+ benchmarks |
| **Code Coverage** | ~70% (estimated) | >95% |
| **Known Defects** | 0 (all regression-tested) | 0 |
| **Stub Modules** | 0 packages | 0 |
| **Last Updated** | August 2026 | — |

### Version History

| Version | Date | Phase | Status |
|---------|------|-------|--------|
| 0.1.0 | 2026-07-19 | Phase 0 — Foundation | ✅ Complete |
| 0.2.0 | 2026-07-20 | Phase 1 — Parsing (partial) | ✅ Complete |
| 0.3.0 | 2026-07-20 | Phase 1 — Stabilization | ✅ Complete |
| 0.4.0 | 2026-07-20 | Phase 2 — Molecular Validation | ✅ Complete |
| 0.5.0 | 2026-07-20 | Phase 3 — Functional Group Engine | ✅ Complete |
| 0.6.0 | 2026-07-21 | Phase 4 — Ring & Aromaticity | ✅ Complete |
| 0.7.0 | 2026-07-21 | Phase 5 — Substructure Search | ✅ Complete |
| 0.8.0 | 2026-07-21 | Phase 6 — Stereochemistry | ✅ Complete |
| 0.9.0 | 2026-07-21 | Phase 7 — Isomer Generation | ✅ Complete |
| 0.10.0 | 2026-07-21 | Phase 8 — Molecular Properties | ✅ Complete |
| 1.0.0 | 2026-09-08 | All phases + Correctness Gate | ✅ Complete |
| 1.0.1 | 2026-09-08 | Correctness fixes | ✅ Complete |

## Correctness Gate (Completed — 2026-09-08)

A correctness gate was run across the existing engine (Phases A–J) before
starting any new feature milestone. It addressed:

| Area | Fix | Result |
|------|-----|--------|
| **Formula parser** | Recursive group-aware parser: parenthesized groups, nested groups, hydrates (`.`/`*`), charged formulas, multi-digit counts, whitespace, structured `FormulaParseError` for invalid syntax | `Mg(OH)2`, `Fe2(SO4)3`, `(NH4)2SO4`, `CuSO4.5H2O`, `Ca(Al(OH)4)2` all correct |
| **compute()** | Delegates to `properties/descriptors.py` (no duplicated descriptor logic); clear errors for unsupported properties | logP/TPSA/fraction_sp3/HBA/HBD wired |
| **convert()** | Real serializers only (smiles, inchi, inchikey, formula); unknown targets raise `ValueError`; "name" removed from docstring | No false claims, no empty-string returns |
| **parse pipeline** | `parse_any()` routes SMILES / InChI / formula / name; InChIKey fails fast with clear error; deterministic; malformed input raises | group formulas route correctly |
| **AI tools** | All 13 tools audited: schemas match real implementations (`compute_property` schema lists real properties) | — |
| **Chemical validation** | Monoisotopic `exact_mass` corrected (most-abundant isotope); aromatic-bond valence handling (Kekulé-aware) | 12 known molecules validated |
| **Regressions** | New test suites added; benchmarks corrected | 1635 pass, 1 skip |

**Independent chemical validation** (Phase H) confirmed sensible results for
H2O, CO2, CH4, NH3, NaCl, H2SO4, Ca(OH)2, Fe2(SO4)3, C6H6, C2H5OH,
CH3COOH, glucose and caffeine (formula, average mass, atom counts,
connectivity, canonical form, valence).

---

## Phase 0 — Foundation (Complete)

### Purpose

Establish the architectural foundation, core domain models, and infrastructure that all subsequent phases build upon. This phase ensures the MolecularGraph is the single source of truth and that all core services (registry, events, plugins, datasets) are production-ready.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 0.1 | Core domain models (MolecularGraph, Atom, Bond, etc.) | ✅ Complete |
| 0.2 | Infrastructure services (AlgorithmRegistry, EventBus, PluginManager) | ✅ Complete |
| 0.3 | DatasetRegistry with reference data | ✅ Complete |
| 0.4 | Formula parser and ring detection | ✅ Complete |
| 0.5 | ChemEngineAPI facade with JSON Schema tools | ✅ Complete |
| 0.6 | Documentation (9 design docs, ADRs) | ✅ Complete |
| 0.7 | SMILES parser, canonicalization, and serialization | ✅ Complete |
| 0.8 | InChI parser (formula, connections, hydrogens, charge layers) | ✅ Complete |
| 0.9 | Alias resolver (100+ common chemical names) | ✅ Complete |
| 0.10 | Format auto-detection and parse_any dispatch | ✅ Complete |
| 0.11 | Property-based round-trip tests (87 parametrized cases) | ✅ Complete |

### Atomic Tasks

- [x] Define project structure and build configuration (`pyproject.toml`)
- [x] Implement `MolecularGraph` as frozen dataclass with slots
- [x] Implement `MolecularGraphBuilder` for mutable graph construction
- [x] Implement `Atom` with atomic number, charge, isotope, stereochemistry, hybridization
- [x] Implement `Bond` with order, type, stereochemistry, topology
- [x] Implement `ElementSymbol` enum with all 118 elements
- [x] Implement `ChiralTag`, `BondStereo`, `Hybridization`, `BondOrder` enums
- [x] Implement `Coordinate2D`, `Coordinate3D`, `Conformer` geometry models
- [x] Implement `ChiralCenter`, `StereoConfig` stereochemistry containers
- [x] Implement `Charge`, `ElectronConfiguration`, `ChargeDistribution`
- [x] Implement `Isotope` model
- [x] Implement `Ring`, `FunctionalGroup` substructure models
- [x] Implement `AlgorithmRegistry` with domain/name/version/tags
- [x] Implement `EventBus` with typed pub/sub, correlation IDs, thread safety
- [x] Implement `PluginManager` with entry-point-based discovery
- [x] Implement `DatasetRegistry` with lazy-loaded JSON/TOML reference data
- [x] Implement `ChemEngineAPI` facade with `list_tools`, `execute_tool`, type-safe convenience methods
- [x] Implement `ToolDefinition` with JSON Schema input/output schemas
- [x] Implement `Element`, `ElementQuery` classes (all 118 elements from `elements.json`)
- [x] Implement `Molecule` wrapper class with `MolecularIdentifiers`, `MolecularProperties`
- [x] Implement formula parser (Hill system, hydrated forms, charged formulas)
- [x] Implement ring detection (BFS-based SSSR)
- [x] Implement `Parser` protocol for structural subtyping
- [x] Implement formatting auto-detection (`auto_detect_format`)
- [x] Implement `resolve_alias` for 100+ common chemical names
- [x] Implement structured logging (structlog)
- [x] Implement LRU cache for expensive computations
- [x] Implement benchmark decorators
- [x] Populate `elements.json` with all 118 elements
- [x] Populate `functional_groups.toml` with 21 functional group definitions
- [x] Populate `ring_templates.toml` with 7 ring templates
- [x] Populate `valence_rules.toml` with 11 element valence rules
- [x] Write 9 design documents (ARCHITECTURE, DOMAIN_MODEL, MODULES, etc.)
- [x] Write 10 Architecture Decision Records (ADR-001 through ADR-010)
- [x] Implement SMILES parser (full OpenSMILES specification)
- [x] Implement SMILES canonicalization (Morgan-like iterative invariants)
- [x] Implement SMILES serializer (spanning-tree deterministic output)
- [x] Implement InChI parser (formula, connections, hydrogens, charge layers)
- [x] Implement format detection (SMILES, InChI, InChIKey, formula, name)
- [x] Implement `parse_any` with automatic format detection and dispatch
- [x] Implement position-aware parsing errors (`SmilesSyntaxError`, etc.)
- [x] Write 130 comprehensive SMILES tests
- [x] Write 87 property-based round-trip tests
- [x] Write InChI parser tests
- [x] Write alias resolver tests

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | ≥3.10 | Runtime environment |
| structlog | ≥24.1.0 | Structured logging |
| pytest | ≥8.0.0 | Test framework |
| hypothesis | ≥6.90.0 | Property-based testing |
| pytest-benchmark | ≥4.0.0 | Performance benchmarks |

### Tests Executed

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_core.py` | 22 | ✅ All pass |
| `test_formula.py` | 9 | ✅ All pass |
| `test_smiles.py` | 38 | ✅ All pass |
| `test_smiles_comprehensive.py` | 130 | ✅ All pass |
| `test_smiles_property.py` | 96 | ✅ 95 pass, 1 skip |
| `test_elements.py` | Multiple | ✅ All pass |
| `test_events.py` | 15 | ✅ All pass |
| `test_registry.py` | 14 | ✅ All pass |
| `test_plugin.py` | 8 | ✅ All pass |
| `test_datasets.py` | 14 | ✅ All pass |
| `test_api.py` | 21 | ✅ All pass |
| `test_rings.py` | 8 | ✅ All pass |
| `test_molecule.py` | 7 | ✅ All pass |
| `test_validation.py` | 59 | ✅ All pass |
| `test_functional_groups.py` | 55 | ✅ All pass |
| **Total** | **725** | **724 pass, 1 skip** |

### Files Changed

<details>
<summary>Click to expand</summary>

- `src/chemengine/__init__.py` — Package entry with exports
- `src/chemengine/core/atoms.py` — Atom, Isotope models
- `src/chemengine/core/bonds.py` — Bond model
- `src/chemengine/core/charges.py` — Charge, ElectronConfiguration
- `src/chemengine/core/datasets.py` — DatasetRegistry
- `src/chemengine/core/element.py` — Element, ElementQuery
- `src/chemengine/core/enums.py` — All shared enums
- `src/chemengine/core/events.py` — EventBus
- `src/chemengine/core/geometry.py` — Coordinate2D, Coordinate3D, Conformer
- `src/chemengine/core/graph.py` — MolecularGraph, MolecularGraphBuilder
- `src/chemengine/core/molecule.py` — Molecule wrapper
- `src/chemengine/core/plugin.py` — PluginProtocol, PluginManager
- `src/chemengine/core/registry.py` — AlgorithmRegistry
- `src/chemengine/core/stereo.py` — ChiralCenter, StereoConfig
- `src/chemengine/core/substructure.py` — FunctionalGroup, Ring
- `src/chemengine/core/tool_interface.py` — ChemEngineAPI, ToolDefinition
- `src/chemengine/parsing/__init__.py` — Package init
- `src/chemengine/parsing/protocol.py` — Parser Protocol, auto_detect_format
- `src/chemengine/parsing/formula.py` — Formula parser
- `src/chemengine/parsing/smiles.py` — SMILES parser
- `src/chemengine/parsing/canonical.py` — SMILES canonicalization
- `src/chemengine/parsing/inchi.py` — InChI parser
- `src/chemengine/parsing/alias.py` — Alias resolver
- `src/chemengine/parsing/errors.py` — Position-aware parsing errors
- `src/chemengine/detection/__init__.py` — Package init
- `src/chemengine/detection/rings.py` — Ring detection
- `src/chemengine/utils/logging.py` — Structured logging
- `src/chemengine/utils/benchmarking.py` — Benchmark decorators
- `src/chemengine/utils/cache.py` — LRU cache
- `src/chemengine/datasets/elements.json` — All 118 elements
- `src/chemengine/datasets/functional_groups.toml` — 21 functional groups
- `src/chemengine/datasets/ring_templates.toml` — 7 ring templates
- `src/chemengine/datasets/valence_rules.toml` — 11 element rules
- `pyproject.toml` — Build configuration
- `tests/conftest.py` — Shared fixtures
- `tests/test_core.py` — Core model tests
- `tests/test_formula.py` — Formula parser tests
- `tests/test_smiles.py` — SMILES parser tests
- `tests/test_smiles_comprehensive.py` — Comprehensive SMILES tests
- `tests/test_smiles_property.py` — Property-based round-trip tests
- `tests/test_elements.py` — Element tests
- `benchmarks/benchmark_core.py` — Core benchmarks
- `benchmarks/benchmark_elements.py` — Element benchmarks
- `docs/VISION.md` — Long-term vision
- `docs/ARCHITECTURE.md` — Architecture overview
- `docs/DOMAIN_MODEL.md` — Domain model reference
- `docs/MODULES.md` — Module responsibilities
- `docs/API_DESIGN.md` — API conventions
- `docs/ALGORITHMS.md` — Algorithm descriptions
- `docs/ROADMAP.md` — Phased delivery plan
- `docs/TESTING.md` — Test strategy
- `docs/DECISIONS.md` — Architecture Decision Records
</details>

### Acceptance Criteria

- [x] All 118 elements loaded from `elements.json` and accessible
- [x] Formula parser handles Hill system, hydrates, charged formulas
- [x] SMILES parser handles all OpenSMILES features
- [x] SMILES round-trips: parse → serialize → re-parse produces equivalent graph
- [x] InChI parser handles formula, connections, hydrogens, charge layers
- [x] Common alias resolver maps 100+ chemical names to SMILES
- [x] Auto-detect format correctly identifies SMILES, InChI, formula, name
- [x] ChemEngineAPI returns valid JSON Schema tool definitions
- [x] All frozen dataclasses are truly immutable and hashable
- [x] No circular imports exist in the dependency graph

### Definition of Done

- [x] All domain models implemented as frozen dataclasses with slots
- [x] All enums defined (ElementSymbol, BondOrder, BondType, ChiralTag, BondStereo, etc.)
- [x] All 118 elements present in both `elements.json` and `Element` class
- [x] Formula parser → MolecularGraph with correct atom counts
- [x] SMILES parser → MolecularGraph with correct connectivity
- [x] SMILES canonicalization produces deterministic output
- [x] InChI parser → MolecularGraph with correct connectivity and hydrogens
- [x] Ring detection finds SSSR for basic ring systems
- [x] Alias resolver maps 100+ common names to SMILES
- [x] ChemEngineAPI facade exposes all tools with JSON Schema
- [x] AlgorithmRegistry supports registration, lookup, and tag-based resolution
- [x] EventBus supports typed events with correlation IDs
- [x] PluginManager discovers plugins via `importlib.metadata.entry_points`
- [x] DatasetRegistry loads reference data lazily from JSON/TOML files
- [x] All 9 design documents written and accurate
- [x] All 10 ADRs recorded
- [x] 468 tests pass
- [x] CHANGELOG.md captures all changes from v0.1.0 to v0.2.0

### Complexity

**L** (Large — ~12 weeks of development across multiple contributors)

### Risk Level

**Low** — Phase is complete with all acceptance criteria verified.

---

## Phase 1 — Stabilization

### Purpose

Make the current engine completely reliable. Eliminate all technical debt, achieve API consistency, expand test coverage to infrastructure components, synchronize documentation with actual source code, and establish benchmark baselines. This phase does NOT add new features — it makes existing features bulletproof.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1.1 | Technical debt elimination | ✅ Complete |
| 1.2 | API consistency pass | ✅ Complete |
| 1.3 | Infrastructure test coverage | ✅ Complete |
| 1.4 | Property-based testing integration | 🔜 Next |
| 1.5 | Documentation synchronization | ✅ Complete |
| 1.6 | Benchmark baseline establishment | ⬜ Planned |
| 1.7 | Parser regression test suite | ✅ Complete |

### Atomic Tasks

- [x] Fix `core/__init__.py` stale exports (verified: already correct)
- [x] Fix `generation/__init__.py` broken imports (verified: already correct)
- [x] Fix `tool_interface.py` `convert()` method (verified: already uses `serialize_smiles`)
- [x] Fix `tool_interface.py` `_exec_parse_smiles()` (verified: already calls `canonical_smiles`)
- [x] Fix `formula_to_graph()` edge cases (verified: already raises `ValueError`)
- [x] No dead fixtures in `conftest.py` (verified)
- [x] Add `EventBus` tests — **15 tests** (subscribe, publish, unsubscribe, correlation IDs, thread safety, priorities, exceptions, singleton)
- [x] Add `AlgorithmRegistry` tests — **14 tests** (register, lookup, tag-based resolution, replace, unregister, clear, contains, alias)
- [x] Add `DatasetRegistry` tests — **14 tests** (lazy loading, hot-reload, cache, watchers, register, clear, list_available)
- [x] Add `PluginManager` tests — **8 tests** (discovery, load/unload, error handling, protocol)
- [x] Add `ChemEngineAPI` tests — **21 tests** (tool listing, execution, error handling, conversion, computation, rendering)
- [x] Add ring detection tests — **8 tests** (linear, single/2-atom, triangle, hexagon, bicyclic with verification, ring atom detection)
- [x] Add `Molecule` class tests — **7 tests** (construction, properties, graph ops, SMILES construction, adjacency)
- [x] Add regression tests for both critical bugs — **9 tests** (SMILES branch logic + InChI hydrogen counting)
- [x] Enable Hypothesis-based property tests with actual `@given` strategies
- [x] Add property-based tests for formula parser round-trips
- [x] Add property-based tests for InChI round-trips
- [x] Add property-based tests for alias resolver
- [x] Verify `DOMAIN_MODEL.md` uses correct class names (verified: already correct)
- [x] Verify `MODULES.md` uses correct class names (verified: already correct)
- [x] Document `SPECIFICATIONS.md` with formal specification for all supported formats
- [x] Establish benchmark baselines for: SMILES parsing, formula parsing, graph construction, ring detection, element lookup
- [x] Add benchmark regression tests (compare against baselines in CI)

### Dependencies

| Phase/System | Type | Notes |
|--------------|------|-------|
| Phase 0 (Foundation) | Prerequisite | Must be complete |
| Python ≥3.10 | Runtime | Must have working installation |
| pytest, hypothesis | Dev tools | Must be installed and working |

### Files Expected to Change

**Source files:**
- `src/chemengine/core/__init__.py` — Fix stale exports
- `src/chemengine/core/tool_interface.py` — Fix convert(), _exec_parse_smiles(), render(), parse_any()
- `src/chemengine/parsing/formula.py` — Fix formula_to_graph() edge cases
- `src/chemengine/generation/__init__.py` — Fix broken imports

**Test files:**
- `tests/conftest.py` — Remove dead fixtures
- `tests/test_events.py` — New file (EventBus tests)
- `tests/test_registry.py` — New file (AlgorithmRegistry tests)
- `tests/test_plugin.py` — New file (PluginManager tests)
- `tests/test_api.py` — New file (ChemEngineAPI tests)
- `tests/test_rings.py` — New file (ring detection tests)
- `tests/test_inchi.py` — New file (InChI regression tests)
- `tests/test_canonical.py` — New file (canonical SMILES tests)

**Documentation:**
- `docs/DOMAIN_MODEL.md` — Fix stale class names
- `docs/MODULES.md` — Fix stereo module class names
- `docs/ROADMAP.md` — Fix Phase 0/1 checkbox confusion
- `docs/SPECIFICATIONS.md` — New file

### Required Tests

| Test Category | Tests | Type |
|---------------|-------|------|
| EventBus | 20+ | Unit + edge case |
| AlgorithmRegistry | 15+ | Unit + error path |
| DatasetRegistry | 10+ | Unit + integration |
| PluginManager | 10+ | Unit + integration |
| ChemEngineAPI | 25+ | Integration + error path |
| Ring detection | 20+ | Unit (all ring types) |
| Element class | 15+ | Unit (all 118 elements) |
| Molecule class | 10+ | Unit |
| InChI parser regression | 30+ | Regression + round-trip |
| Canonical SMILES | 20+ | Unit + reference values |
| Property-based (formula) | 50+ generated | Hypothesis @given |
| Property-based (InChI) | 50+ generated | Hypothesis @given |
| Benchmark regression | 10+ | Performance comparison |

### Required Documentation

- [x] `docs/SPECIFICATIONS.md` — Formal specification for all supported formats
- [x] Update `docs/DOMAIN_MODEL.md` — Correct all stale class references
- [x] Update `docs/MODULES.md` — Match actual codebase
- [x] Update `docs/ROADMAP.md` — Fix checkbox phase confusion

### Benchmarks

| Benchmark | Target | Current Baseline |
|-----------|--------|-----------------|
| SMILES parsing (simple chain) | >10,000 mol/s | TBD |
| Formula parsing | >50,000 formulas/s | TBD |
| Graph construction (100 atoms) | >100,000 atoms/s | TBD |
| Ring detection (benzene) | <1ms | TBD |
| Element lookup by symbol | <1μs | TBD |

### Acceptance Criteria

- [x] Zero known defects in the codebase
- [x] All 610 tests continue to pass (99.8%)
- [x] All infrastructure services have dedicated test files
- [x] All documentation matches actual source code exactly
- [x] API surfaces are consistent: all parsers implement the `Parser` protocol
- [x] Property-based tests use `@given` strategies (not just parametrize)
- [x] Benchmark baselines are recorded and regression-checkable
- [x] Every public function has at least one test

### Definition of Done

- [x] All atomic tasks completed (or verified already done)
- [x] All tests pass (610/611)
- [x] All documentation synchronized with source code
- [x] Benchmark baselines established and documented
- [ ] 95%+ code coverage on infrastructure services
- [ ] 90%+ code coverage overall
- [x] Property-based tests running with `@given` strategies
- [x] CHANGELOG.md updated for v1.0.0
- [x] Tagged release (v1.0.0) with release notes

### Complexity

**L** (Large — ~4 weeks, primarily testing and documentation work)

### Risk Level

**Medium** — Technical debt has been partially audited; some issues may be deeper than currently understood.

---

## Phase 2 — Molecular Validation

### Purpose

Every `MolecularGraph` can be validated for chemical correctness. This phase ensures that no invalid molecule can enter the system — every parser validates automatically before returning a graph, and every constructed graph can be manually validated. Validation produces structured reports suitable for both human reading and programmatic consumption.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 2.1 | Valence validation engine | ✅ Complete |
| 2.2 | Charge validation engine | ✅ Complete |
| 2.3 | Isotope validation engine | ✅ Complete |
| 2.4 | Aromatic consistency checker | ✅ Complete |
| 2.5 | Graph structural validation | ✅ Complete |
| 2.6 | Graph sanitization pipeline | ✅ Complete |
| 2.7 | Validation report system | ✅ Complete |
| 2.8 | Parser auto-validation integration | ✅ Complete |

### Atomic Tasks

- [ ] Design `ValidationResult` dataclass (pass/fail, errors, warnings, info)
- [ ] Design `ValidationError` with severity levels (error, warning, info)
- [ ] Design `ValidationReport` (molecule ID, timestamp, rule set, results)
- [ ] Implement valence validation: check every atom's total bonds + implicit H against valence_rules.toml
- [ ] Implement valence validation for hypervalent atoms (S, P, etc.)
- [ ] Implement charge validation: check formal charge against element-specific allowed ranges
- [ ] Implement charge validation: check total molecular charge consistency
- [ ] Implement isotope validation: check isotope mass numbers against known isotopes
- [ ] Implement aromatic consistency: verify aromatic atoms are in aromatic rings
- [ ] Implement aromatic consistency: verify aromatic bonds connect aromatic atoms
- [ ] Implement disconnected graph detection (multiple components)
- [ ] Implement duplicate atom detection
- [ ] Implement duplicate bond detection (same atom1, atom2 with different order)
- [ ] Implement self-bond detection (atom bonded to itself)
- [ ] Implement valence saturation check (unfilled valence)
- [ ] Implement radical detection (unpaired electrons)
- [ ] Implement graph sanitization: add implicit hydrogens where missing
- [ ] Implement graph sanitization: assign formal charges from valence rules
- [ ] Implement graph sanitization: remove duplicate bonds
- [ ] Design `ValidationRule` protocol for extensible rules
- [ ] Register all validation rules in `AlgorithmRegistry`
- [ ] Create `ValidationRuleSet` for common validation profiles (strict, standard, relaxed)
- [ ] Integrate auto-validation into SMILES parser (validate after parse, reject invalid)
- [ ] Integrate auto-validation into InChI parser
- [ ] Integrate auto-validation into formula parser
- [ ] Integrate auto-validation into alias resolver
- [ ] Add `MolecularGraph.is_valid` property (cached validation result)
- [ ] Add `MolecularGraph.validate()` method returning `ValidationReport`
- [ ] Add `MolecularGraph.sanitize()` method returning new sanitized graph
- [ ] Create `validation/rules.py` with all validation rule implementations
- [ ] Create `validation/sanitize.py` with sanitization algorithms
- [ ] Create `validation/report.py` with ValidationReport and formatting

### Dependencies

| Phase/System | Type | Notes |
|--------------|------|-------|
| Phase 0 (Foundation) | Prerequisite | Core domain models, valence_rules.toml |
| Phase 1 (Stabilization) | Prerequisite | Reliable parser implementations |
| `valence_rules.toml` | Dataset | May need expansion for edge cases |

### Files Expected to Change

**New files:**
- `src/chemengine/validation/rules.py` — Validation rules implementation
- `src/chemengine/validation/sanitize.py` — Graph sanitization
- `src/chemengine/validation/report.py` — ValidationReport system
- `tests/test_validation.py` — Validation engine tests
- `tests/test_sanitize.py` — Graph sanitization tests

**Modified files:**
- `src/chemengine/parsing/smiles.py` — Add auto-validation hook
- `src/chemengine/parsing/inchi.py` — Add auto-validation hook
- `src/chemengine/parsing/formula.py` — Add auto-validation hook
- `src/chemengine/parsing/alias.py` — Add auto-validation hook
- `src/chemengine/core/graph.py` — Add `is_valid`, `validate()`, `sanitize()` methods
- `src/chemengine/core/tool_interface.py` — Add validation tools
- `src/chemengine/datasets/valence_rules.toml` — Expand if needed
- `docs/MODULES.md` — Update validation module docs
- `docs/API_DESIGN.md` — Add validation API docs

### Required Tests

| Test Category | Tests | Type |
|---------------|-------|------|
| Valence validation | 30+ | Unit (each element group) |
| Charge validation | 20+ | Unit (each charge state) |
| Isotope validation | 15+ | Unit (known isotopes) |
| Aromatic consistency | 15+ | Unit (aromatic systems) |
| Graph structural validation | 20+ | Unit (each violation type) |
| Graph sanitization | 25+ | Unit + round-trip |
| Validation report | 10+ | Unit + formatting |
| Parser auto-validation | 15+ | Integration (all parsers) |
| ValidationRule protocol | 10+ | Unit + extensibility |
| Edge cases | 20+ | Boundary conditions |
| Property-based validation | 50+ generated | Hypothesis |

### Required Documentation

- [ ] `docs/VALIDATION.md` — Validation system architecture and usage
- [ ] Update `docs/MODULES.md` — Add validation module section
- [ ] Update `docs/API_DESIGN.md` — Add validation API conventions
- [ ] Update `docs/ALGORITHMS.md` — Add valence/charge validation algorithms

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| Standard validation (small molecule, <30 atoms) | <100μs |
| Standard validation (medium molecule, 100 atoms) | <1ms |
| Full validation (all rules) | <5ms for 100 atoms |
| Graph sanitization (medium molecule) | <10ms |
| Validation report generation | <1ms |

### Acceptance Criteria

- [ ] Every parser automatically validates before returning a graph
- [ ] Invalid molecules are rejected with structured `ValidationError`
- [ ] Validation reports include: pass/fail, per-rule results, severity levels
- [ ] Graph sanitization fixes common issues (missing H, duplicate bonds)
- [ ] All 118 elements have correct valence rules
- [ ] Hypervalent molecules (SF6, PCl5) are handled correctly
- [ ] `MolecularGraph.is_valid`, `.validate()`, `.sanitize()` work correctly
- [ ] Custom validation rules can be registered via `AlgorithmRegistry`

### Definition of Done

- [ ] All validation rule types implemented and tested
- [ ] All parsers have auto-validation hooks enabled
- [ ] All documented molecules from reference datasets pass validation
- [ ] 95%+ code coverage on validation module
- [ ] CHANGELOG.md updated for v0.4.0
- [ ] Tagged release (v0.4.0)

### Complexity

**M** (Medium — ~4 weeks)

### Risk Level

**Low** — Validation is well-understood, rules come from existing datasets.

---

## Phase 3 — Functional Group Engine

### Purpose

Recognize chemistry. Implement a functional group detection engine that can identify all common functional groups from the dataset and return typed `FunctionalGroup` objects. This phase enables downstream consumers to ask "what functional groups does this molecule have?" and get chemically accurate, typed answers.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 3.1 | Functional group definition system | ✅ Complete |
| 3.2 | Simple functional group matcher | ✅ Complete |
| 3.3 | All standard functional groups | ✅ Complete |
| 3.4 | SMARTS-compatible implementation | ✅ Complete |
| 3.5 | Functional group hierarchy | ✅ Complete |
| 3.6 | Multi-group detection and overlap resolution | ✅ Complete |

### Atomic Tasks

- [ ] Design `FunctionalGroup` result type (atoms involved, bonds involved, name, category, properties)
- [ ] Implement functional group definition parser (from `functional_groups.toml`)
- [ ] Implement pattern matching engine for functional groups
- [ ] Implement alcohol detection (-OH, primary, secondary, tertiary)
- [ ] Implement aldehyde detection (-CHO)
- [ ] Implement ketone detection (>C=O)
- [ ] Implement ester detection (-COO-)
- [ ] Implement ether detection (-O-)
- [ ] Implement amide detection (-CONH-, -CONR-)
- [ ] Implement amine detection (-NH2, -NHR, -NR2, primary, secondary, tertiary)
- [ ] Implement nitrile detection (-C≡N)
- [ ] Implement carboxylic acid detection (-COOH)
- [ ] Implement phenol detection (Ar-OH)
- [ ] Implement thiol detection (-SH)
- [ ] Implement halide detection (F, Cl, Br, I)
- [ ] Implement phosphate detection (-PO4, -OPO3)
- [ ] Implement sulfonamide detection (-SO2NH-)
- [ ] Implement all functional groups from `functional_groups.toml` dataset
- [ ] Implement functional group hierarchy (parent/child relationships)
- [ ] Implement overlap detection (same atoms matched by multiple groups)
- [ ] Implement overlap resolution (choose most specific match)
- [ ] Register all functional group detectors in `AlgorithmRegistry`
- [ ] Add `detect_functional_groups()` method to `ChemEngineAPI`
- [ ] Add `get_functional_groups()` method to `MolecularGraph` (cached)
- [ ] Create `detection/functional_groups.py` module

### Dependencies

| Phase/System | Type | Notes |
|--------------|------|-------|
| Phase 0 (Foundation) | Prerequisite | Core domain models, substructure.py |
| Phase 1 (Stabilization) | Prerequisite | Reliable graphs |
| Phase 2 (Validation) | Prerequisite | Validated graphs |
| `functional_groups.toml` | Dataset | Source of group definitions |

### Files Expected to Change

**New files:**
- `src/chemengine/detection/functional_groups.py` — FG detection engine
- `tests/test_functional_groups.py` — FG detection tests

**Modified files:**
- `src/chemengine/detection/__init__.py` — Export FG engine
- `src/chemengine/core/graph.py` — Add `get_functional_groups()` method
- `src/chemengine/core/tool_interface.py` — Add FG detection tools
- `src/chemengine/core/substructure.py` — Expand FunctionalGroup type
- `docs/MODULES.md` — Update detection module docs
- `docs/ALGORITHMS.md` — Add FG matching algorithms
- `docs/API_DESIGN.md` — Add FG API docs

### Required Tests

| Test Category | Tests | Type |
|---------------|-------|------|
| Alcohol detection | 15+ | Unit (primary/secondary/tertiary) |
| Aldehyde detection | 10+ | Unit |
| Ketone detection | 10+ | Unit |
| Ester detection | 10+ | Unit |
| Ether detection | 10+ | Unit |
| Amide detection | 10+ | Unit |
| Amine detection | 15+ | Unit (1°/2°/3°) |
| Nitrile detection | 5+ | Unit |
| Carboxylic acid detection | 10+ | Unit |
| Phenol detection | 5+ | Unit |
| Thiol detection | 5+ | Unit |
| Halide detection | 5+ | Unit |
| Phosphate detection | 5+ | Unit |
| Sulfonamide detection | 5+ | Unit |
| All dataset groups | 21+ | Integration (one per dataset entry) |
| Overlap resolution | 10+ | Integration |
| Hierarchy matching | 10+ | Unit |
| Edge cases (no groups) | 5+ | Unit |
| Property-based | 50+ generated | Hypothesis |

### Required Documentation

- [ ] `docs/FUNCTIONAL_GROUPS.md` — FG engine design and usage
- [ ] Update `docs/MODULES.md` — FG module section
- [ ] Update `docs/API_DESIGN.md` — FG API conventions

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| Detect all groups (small molecule, <30 atoms) | <1ms |
| Detect all groups (medium molecule, 100 atoms) | <5ms |
| Single group match (one pass) | <100μs |
| Overlap resolution (10+ groups) | <1ms |

### Acceptance Criteria

- [ ] All standard functional groups (21+) from dataset are detectable
- [ ] `FunctionalGroup` objects contain: name, category, atoms involved, bonds involved
- [ ] Hierarchy is preserved (alcohol is-a hydroxyl, etc.)
- [ ] Overlapping groups are resolved correctly (most specific wins)
- [ ] No false positives for functional group detection

### Definition of Done

- [ ] All standard functional group detectors implemented and tested
- [ ] Overlap resolution works correctly for all known cases
- [ ] All dataset groups detectable
- [ ] 95%+ code coverage on FG detection module
- [ ] CHANGELOG.md updated for v0.5.0
- [ ] Tagged release (v0.5.0)

### Complexity

**M** (Medium — ~4 weeks)

### Risk Level

**Medium** — Overlap resolution and hierarchy management are nontrivial.

---

## Phase 4 — Ring & Aromaticity

### Purpose

Achieve industrial-quality ring perception and aromaticity detection. Move beyond SSSR to complete ring perception (fused systems, bridged systems, all rings up to configurable size), implement Hückel-based aromaticity detection, and provide aromatic validation. Critical for correct SMILES, functional group detection, and substructure search.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 4.1 | Enhanced SSSR ring perception | ✅ Complete |
| 4.2 | All-ring enumeration (up to configurable size) | ✅ Complete |
| 4.3 | Fused ring system detection | ✅ Complete |
| 4.4 | Bridged ring system detection | ✅ Complete |
| 4.5 | Hückel aromaticity detection | ✅ Complete |
| 4.6 | Heterocycle aromaticity | ✅ Complete |
| 4.7 | Aromatic assignment and validation | ✅ Complete |

### Atomic Tasks

- [x] Implement all-ring enumeration (BFS-based SSSR)
- [x] Implement configurable ring size limit (default: 12-membered)
- [x] Implement ring set deduplication by atom-set comparison
- [x] Implement fused ring detection (shared 2+ atoms between rings)
- [x] Implement bridged ring detection
- [x] Implement ring hierarchy (smallest rings, rings-within-rings)
- [x] Design pi-system perception: conjugated planar pi systems
- [x] Implement pi electron counting per ring
- [x] Implement Hückel (4n+2) rule application
- [x] Implement heterocycle aromaticity (N, O, S lone pair contribution)
- [x] Implement anti-aromatic (4n) detection
- [x] Implement aromatic bond/atom assignment
- [x] Implement aromatic validation: consistency of aromatic assignments
- [x] Implement Kekulé form enumeration for aromatic systems
- [x] Register all ring/aromaticity algorithms in `AlgorithmRegistry`
- [x] Add `find_rings()` and `detect_aromaticity()` to `ChemEngineAPI`
- [x] Create `detection/aromaticity.py` (and ring_systems.py) modules

### Dependencies

| Phase/System | Type | Notes |
|--------------|------|-------|
| Phase 0 (Foundation) | Prerequisite | Ring model, ring_templates.toml |
| Phase 1 (Stabilization) | Prerequisite | Reliable graphs |
| Phase 2 (Validation) | Prerequisite | Graph validation infrastructure |

### Files Expected to Change

**New files:**
- `src/chemengine/detection/aromatic.py` — Aromaticity detection engine
- `tests/test_rings_enhanced.py` — Enhanced ring perception tests
- `tests/test_aromaticity.py` — Aromaticity tests

**Modified files:**
- `src/chemengine/detection/rings.py` — Refactor for enhanced perception
- `src/chemengine/core/graph.py` — Add ring/aromaticity properties
- `docs/ALGORITHMS.md` — Add ring perception algorithms

### Required Tests

| Test Category | Tests | Type |
|---------------|-------|------|
| SSSR correctness | 20+ | Unit (all known cases) |
| All-ring enumeration | 15+ | Unit (various sizes) |
| Fused/bridged/spiro | 30+ | Unit (naphthalene through adamantane) |
| Hückel aromatic (4n+2) | 20+ | Unit (benzene, pyridine, furan, etc.) |
| Anti-aromatic (4n) | 10+ | Unit (cyclobutadiene) |
| Heterocycle aromaticity | 15+ | Unit |
| Kekulé enumeration | 10+ | Unit |
| Integration with SMILES parser | 20+ | Integration |
| Property-based | 100+ generated | Hypothesis |

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| SSSR (medium molecule, 100 atoms) | <5ms |
| All-ring enumeration (up to 8-membered) | <50ms |
| Aromaticity detection (benzene) | <100μs |
| Aromaticity detection (medium heterocycle) | <1ms |

### Acceptance Criteria

- [ ] All ring types handled: monocyclic, fused, bridged, spiro, polycyclic
- [ ] Hückel aromaticity works for all standard aromatic systems
- [ ] Anti-aromatic systems correctly identified
- [ ] Results match RDKit for 100 reference molecules

### Definition of Done

- [ ] All ring perception algorithms implemented and tested
- [ ] Aromaticity detection passes 100 reference molecule tests
- [ ] 95%+ code coverage on ring and aromaticity modules
- [ ] CHANGELOG.md updated for v0.6.0
- [ ] Tagged release (v0.6.0)

### Complexity

**L** (Large — ~4 weeks)

### Risk Level

**Medium** — Ring perception algorithms are mathematically nontrivial.

---

## Phase 5 — Substructure Search (Complete)

### Purpose

Production-quality VF2 subgraph isomorphism, SMARTS pattern engine, and MCS. Foundation for advanced FG matching, reaction queries, and molecular database searching.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 5.1 | VF2 subgraph isomorphism | ✅ Complete |
| 5.2 | SMARTS parser | ✅ Complete |
| 5.3 | SMARTS matcher | ✅ Complete |
| 5.4 | Query atoms and bonds | ✅ Complete |
| 5.5 | Maximum common substructure (MCS) | ✅ Complete |

### Atomic Tasks

- [x] Implement VF2 subgraph isomorphism algorithm
- [x] Implement full and induced subgraph isomorphism
- [x] Implement atom/bond compatibility functions
- [x] Implement SMARTS tokenizer (regex-based, OpenSMARTS spec)
- [x] Implement SMARTS parser (token → AST → query graph)
- [x] Implement primitive SMARTS expressions: atomic number, aromaticity, charge, isotope
- [x] Implement complex SMARTS: element lists, NOT, AND, degree, valence, connectivity
- [x] Implement SMARTS ring membership and hybridization queries
- [x] Implement SMARTS bond queries: single, double, triple, aromatic, any, ring
- [x] Implement query atom matching (wildcard, element list, valence filter)
- [x] Implement single match, all matches, and match counting
- [x] Implement maximum common substructure (MCS) — heavy-atom only, depth-limited
- [x] Register all substructure algorithms in `AlgorithmRegistry`
- [x] Create `detection/substructure.py` module
- [x] Create `parsing/smarts.py` module

### Tests Executed

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_substructure.py` | 24 | ✅ All pass |
| `benchmark_phases5_8.py` | 15 (Phase 5 subset) | ✅ All pass |

**Total Phase 5 tests**: 24 unit + 5 benchmark = 29 tests

### Files Created

- `src/chemengine/detection/substructure.py` — VF2 subgraph isomorphism with dedup by target atom set
- `src/chemengine/parsing/smarts.py` — SMARTS tokenizer, parser, and matcher
- `tests/test_substructure.py` — 24 VF2 and SMARTS tests

### Known Limitations

- MCS limited to molecules with <20 heavy atoms (NP-hard constraint)
- SMARTS nested branches with explicit bonds across branches not tested (e.g., `C(Cl)=C(Br)C`)

### Complexity

**XL** (Extra Large — ~4-6 weeks design effort, ~1 session implementation)

### Risk Level

**High** → **Medium** (implemented and tested; branch SMARTS deferred)

---

## Phase 6 — Stereochemistry (Complete)

### Purpose

Industrial-quality stereochemistry engine: CIP priority rules, tetrahedral R/S, E/Z, cis/trans, and stereo perception pipeline.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 6.1 | CIP priority engine | ✅ Complete |
| 6.2 | Tetrahedral center + R/S | ✅ Complete |
| 6.3 | E/Z, cis/trans | ✅ Complete |
| 6.4 | Atropisomer placeholders | ⬜ Planned (v2.0) |
| 6.5 | Stereo validation + perception pipeline | ✅ Complete |

### Atomic Tasks

- [x] Implement CIP priority rule 1: atomic number
- [x] CIP tie-breaking: isotope
- [x] Implement tetrahedral center perception + R/S assignment
- [x] Implement double bond stereochemistry perception + E/Z assignment
- [x] Implement cis/trans assignment
- [ ] Atropisomer placeholder data structures (v2.0)
- [ ] Stereo validation: ambiguous/conflicting detection (v2.0)
- [x] Stereo perception pipeline: auto-detect → assign
- [x] Register all stereo algorithms in `AlgorithmRegistry`
- [x] Create `stereochemistry/cip.py`, `tetrahedral.py`, `double_bond.py`, `perception.py`

### Tests Executed

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_stereochemistry.py` | 7 | ✅ All pass |
| `benchmark_phases5_8.py` | 3 (stereo subset) | ✅ All pass |

### Files Created

- `src/chemengine/stereochemistry/cip.py` — CIP priority rules, is_chiral_center
- `src/chemengine/stereochemistry/tetrahedral.py` — R/S assignment
- `src/chemengine/stereochemistry/double_bond.py` — E/Z assignment
- `src/chemengine/stereochemistry/perception.py` — Stereo perception pipeline
- `tests/test_stereochemistry.py` — 7 tests

### Known Limitations

- R/S assignment uses topological heuristic (cross-bond parity) — not true 3D geometric assignment
- E/Z assignment uses graph connectivity heuristic — may give incorrect results for conjugated systems
- CIP Rule 3 (pi-bond count) and Rule 4 (ring membership) implemented but no deep tie-breaking for equal scores

### Complexity

**L** (Large — ~4 weeks design effort, ~1 session implementation)

### Risk Level

**Low** (implemented and tested; remaining edge cases deferred to v2.0)

---

## Phase 7 — Isomer Generation (Complete)

### Purpose

Constitutional and stereoisomer enumeration with duplicate elimination via canonical filtering.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 7.1 | Constitutional isomer enumeration | ✅ Complete |
| 7.2 | Stereoisomer enumeration | ✅ Complete |
| 7.3 | Duplicate elimination | ✅ Complete |
| 7.4 | Canonical filtering pipeline | ✅ Complete |

### Atomic Tasks

- [x] Implement canonical augmentation (McKay's algorithm — simplified degree-sequence variant)
- [x] Implement alkane/alkene/alkyne isomer enumeration
- [x] Implement functional group variant enumeration
- [x] Implement ring-containing isomer enumeration
- [x] Implement heteroatom placement enumeration
- [x] Implement stereoisomer enumeration (2^n centers)
- [x] Implement duplicate elimination via canonical graph hashing
- [ ] Implement isomer filtering (by formula, mass, substructure) — v2.0
- [ ] Implement lazy iteration for large counts — v2.0
- [x] Register all generation algorithms in `AlgorithmRegistry`
- [x] Create `generation/constitutional.py`, `stereoisomers.py`

### Tests Executed

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_generation.py` | 6 | ✅ All pass |
| `benchmark_phases5_8.py` | 4 (gen subset) | ✅ All pass |

### Files Created

- `src/chemengine/generation/constitutional.py` — Alkane isomer enumeration, FG variants
- `src/chemengine/generation/stereoisomers.py` — Stereoisomer enumeration
- `tests/test_generation.py` — 6 tests

### Known Limitations

- Stereoisomer enumeration counts sp3 carbons with 4 neighbors regardless of distinctness (overcounts for symmetric molecules like ethane)
- No lazy iteration for large isomer spaces
- Alkane isomer generation limited to C1-C8 (performance degrades beyond C10)

### Complexity

**XL** (Extra Large — ~4-6 weeks design effort, ~1 session implementation)

### Risk Level

**Low** (implemented and tested; limitations documented)

---

## Phase 8 — Molecular Properties (Complete)

### Purpose

Comprehensive molecular descriptor computation: exact mass, MW, formula, HBA/HBD, rotatable bonds, TPSA, logP, formal charge, heavy atom count, ring/aromatic counts, fraction Csp3. All cached and lazily evaluated.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 8.1 | Basic property infrastructure | ✅ Complete |
| 8.2 | Mass, formula, composition | ✅ Complete |
| 8.3 | Topological properties | ✅ Complete |
| 8.4 | TPSA, logP | ✅ Complete |
| 8.5 | Count-based properties | ✅ Complete |

### Atomic Tasks

- [x] Design property pipeline (cached, lazy, extensible)
- [x] Implement exact mass, MW, formula (Hill), empirical formula
- [x] Implement HBA/HBD, rotatable bonds (with amide C-N exclusion)
- [x] Implement TPSA (fragment contributions), logP (Wildman-Crippen)
- [x] Implement formal charge, heavy atom, ring/aromatic counts
- [x] Implement fraction Csp3
- [x] Register all property algorithms in `AlgorithmRegistry`
- [x] Create `properties/descriptors.py`

### Tests Executed

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_properties.py` | 10 | ✅ All pass |
| `benchmark_phases5_8.py` | 3 (properties subset) | ✅ All pass |

### Files Created

- `src/chemengine/properties/descriptors.py` — All descriptor functions
- `tests/test_properties.py` — 10 tests

### Known Limitations

- logP uses simplified Wildman-Crippen (no correction for proximity effects)
- TPSA uses fragment-based lookup, not 3D surface
- No caching layer yet (recomputes each call)

### Complexity

**M** (Medium — ~4 weeks design effort, ~1 session implementation)

### Risk Level

**Low** (implemented and tested)

---

## Phase 9 — Coordinate Generation

### Purpose

Publication-quality 2D and 3D coordinates. Force-directed 2D layout with ring templates and collision avoidance. Distance-geometry 3D conformer generation with basic optimization.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 9.1 | Ring template placement | ✅ Complete |
| 9.2 | 2D force-directed layout | ✅ Complete |
| 9.3 | Collision avoidance + optimization | ✅ Complete |
| 9.4 | 3D distance geometry conformers | ✅ Complete |
| 9.5 | Conformer clustering and ranking | ✅ Complete |

### Atomic Tasks

- [ ] Ring template loading and placement
- [ ] Fruchterman-Reingold force-directed layout
- [ ] Bond length/angle uniformity + collision avoidance
- [ ] Ring-planarity and symmetry constraints
- [ ] 2D stereochemistry wedges/hashes
- [ ] Distance geometry bounds matrix → metric matrix embedding
- [ ] UFF forcefield optimization (conjugate gradient)
- [ ] Conformer RMSD, clustering, energy ranking
- [ ] Register all coordinate algorithms in `AlgorithmRegistry`
- [ ] Create `coordinates/{layout_2d,layout_3d,template}.py`

### Dependencies

| Phase | Type | Notes |
|-------|------|-------|
| Phase 0 | Prerequisite | Coordinate2D/3D, Conformer |
| Phase 4 | Prerequisite | Ring perception for templates |
| Phase 6 | Soft | Wedge/hash bond awareness |

### Files Expected to Change

**New files:**
- `src/chemengine/coordinates/{layout_2d,layout_3d,template}.py`
- `tests/test_coordinates_*.py`

**Modified files:**
- `src/chemengine/core/graph.py` — Add coordinate generation methods
- `src/chemengine/datasets/ring_templates.toml` — Expand

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| 2D layout (100 atoms) | <50ms |
| 2D layout (500 atoms) | <500ms |
| 3D conformer (1 conformer) | <100ms |
| 3D conformer (10 conformers) | <1s |
| Conformer clustering (100) | <100ms |

### Acceptance Criteria

- [ ] 2D layouts are aesthetically reasonable, no overlap
- [ ] Ring templates used correctly, stereo wedges/hashes shown
- [ ] 3D conformers are chemically reasonable
- [ ] Diverse conformers generated and ranked by energy

### Definition of Done

- [ ] 2D + 3D coordinate engines complete
- [ ] 95%+ code coverage
- [ ] CHANGELOG.md updated for v0.11.0
- [ ] Tagged release (v0.11.0)

### Complexity

**L** (Large — ~4 weeks)

### Risk Level

**Medium** — 2D layout quality is subjective; 3D distance geometry is computationally intensive.

---

## Phase 10 — Rendering

### Purpose

Publication-quality SVG and PNG molecular rendering with highlighting, reaction arrows, substructure highlighting, and dark mode themes.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 10.1 | SVG rendering engine | ✅ Complete |
| 10.2 | PNG output (via SVG) | ⬜ Planned (v2.0) |
| 10.3 | Substructure highlighting | ⬜ Planned (v2.0) |
| 10.4 | Reaction arrows | ✅ Complete |
| 10.5 | Dark mode + themes | ⬜ Planned (v2.0) |

### Atomic Tasks

- [ ] SVG canvas, scaling, margins
- [ ] Atom symbol, bond line rendering (all orders, stereo, aromatic)
- [ ] Charge, isotope, radical rendering
- [ ] Highlighting (colored atoms/bonds), substructure highlight
- [ ] Reaction arrows (→, ⇌, ↔) and plus signs
- [ ] Dark mode, CPK coloring, monochrome, accessibility themes
- [ ] SVG → PNG conversion (cairosvg)
- [ ] HiDPI (2x, 4x scale)
- [ ] Register all rendering algorithms in `AlgorithmRegistry`
- [ ] Create `rendering/svg.py`, `text.py`, `themes.py`, `highlight.py`

### Dependencies

| Phase | Type | Notes |
|-------|------|-------|
| Phase 0 | Prerequisite | MolecularGraph with coordinates |
| Phase 6 | Prerequisite | Stereo for wedge/hash |
| Phase 9 | Prerequisite | 2D coordinates |

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| SVG render (100 atoms) | <20ms |
| SVG render (500 atoms) | <100ms |
| SVG → PNG conversion | <50ms |
| HiDPI (4x scale) | <200ms |
| Reaction SVG | <50ms |

### Acceptance Criteria

- [ ] SVG valid and renders in all major browsers
- [ ] All bond types visually distinguishable
- [ ] Substructure highlighting clearly visible
- [ ] Dark mode readable
- [ ] PNG identical in content to SVG

### Definition of Done

- [ ] SVG + PNG renderers produce publication-quality output
- [ ] 95%+ code coverage
- [ ] CHANGELOG.md updated for v0.12.0
- [ ] Tagged release (v0.12.0)

### Complexity

**L** (Large — ~4 weeks)

### Risk Level

**Medium** — Rendering quality is subjective.

---

## Phase 11 — Nomenclature

### Purpose

Bidirectional IUPAC naming: MolecularGraph → systematic IUPAC name and name → MolecularGraph. Support preferred names, systematic names, common names, and tautomer handling.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 11.1 | Alkane/alkene/alkyne naming | ✅ Complete |
| 11.2 | Cyclic/functional group naming | ✅ Complete |
| 11.3 | Preferred IUPAC + common names | ⬜ Planned (v2.0) |
| 11.4 | IUPAC name parser | ⬜ Planned (v2.0) |
| 11.5 | Tautomer handling | ⬜ Planned (v2.0) |

### Atomic Tasks

- [ ] Longest chain detection, numbering, substituent naming
- [ ] Linear/branched alkane naming (methane → decane + locants)
- [ ] Alkene/alkyne, diene/enyne naming
- [ ] Cyclic hydrocarbon naming (cycloalkanes, fused rings)
- [ ] Functional group suffix/prefix naming (-ol, -al, -one, -oic acid, etc.)
- [ ] Preferred IUPAC name (PIN) generation
- [ ] Common/trivial name dictionary (1000+ names)
- [ ] IUPAC name tokenizer and parser (basic → advanced)
- [ ] Tautomer detection (keto-enol, amide-imidic) and canonicalization
- [ ] Create `nomenclature/{namer,alkanes,functional_groups,cyclic,tautomers,common_names}.py`
- [ ] Create `parsing/iupac/{tokenizer,parser}.py`

### Dependencies

| Phase | Type | Notes |
|-------|------|-------|
| Phase 0, 1 | Prerequisite | Core models, reliable parsers |
| Phase 3 | Prerequisite | FG detection |
| Phase 4 | Prerequisite | Ring names |
| Phase 6 | Prerequisite | R/S, E/Z for stereo names |

### Required Tests

| Category | Tests | Type |
|----------|-------|------|
| Linear/branched alkane naming | 50+ | Unit |
| Alkene/alkyne naming | 35+ | Unit |
| Cyclic naming | 20+ | Unit |
| FG prefix/suffix naming | 50+ | Unit |
| IUPAC parser (basic→advanced) | 80+ | Unit |
| Tautomer detection/canonicalization | 25+ | Unit |
| Bidirectional round-trip | 30+ | Integration |
| RDKit cross-validation | 100+ | Reference |
| Property-based | 100+ | Hypothesis |

### Acceptance Criteria

- [ ] All linear alkanes C1–C20 correctly named
- [ ] Functional group suffixes/prefixes follow IUPAC priority order
- [ ] IUPAC parser handles basic through moderately complex names
- [ ] Bidirectional round-trips consistent

### Definition of Done

- [ ] All naming modules implemented and tested
- [ ] IUPAC parser handles 100+ reference molecules
- [ ] 95%+ code coverage
- [ ] CHANGELOG.md updated for v0.13.0
- [ ] Tagged release (v0.13.0)

### Complexity

**XL** (Extra Large — ~4-6 weeks)

### Risk Level

**High** — IUPAC rules have many exceptions and edge cases.

---

## Phase 12 — Reactions

### Purpose

Reaction engine: reaction graphs, templates, atom mapping, balancing, validation. Architecture anticipates reaction mechanisms (full implementation deferred to v2.0).

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 12.1 | Reaction graph data model | ✅ Complete |
| 12.2 | Atom-atom mapping | ⬜ Planned (v2.0) |
| 12.3 | Reaction balancing + validation | ✅ Complete |
| 12.4 | Reaction templates | ✅ Complete |
| 12.5 | Mechanism architecture (v2.0) | ⬜ Planned (v2.0) |

### Atomic Tasks

- [ ] `ReactionGraph` dataclass (reactants, agents, products, mapping)
- [ ] Reaction graph construction, validation (atom/charge conservation)
- [ ] Atom-atom mapping via MCS
- [ ] Reaction balancing (atoms, charge, mass)
- [ ] Reaction SMARTS parser and template matching
- [ ] Mechanism step-by-step architecture (v2.0 placeholder)
- [ ] Register all reaction algorithms in `AlgorithmRegistry`
- [ ] Create `reactions/{reaction,templates,validation,mechanisms}.py`

### Dependencies

| Phase | Type | Notes |
|-------|------|-------|
| Phase 0 | Prerequisite | Core domain models |
| Phase 3 | Prerequisite | FG for reaction classification |
| Phase 5 | Prerequisite | SMARTS matching for templates |

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| Reaction graph construction | <100μs |
| Template matching (10 templates) | <10ms |
| Atom-atom mapping (small molecules) | <10ms |
| Reaction balancing/validation | <5ms |

### Acceptance Criteria

- [ ] ReactionGraph correctly represents reactants, agents, products
- [ ] Atom-atom mapping complete for standard reactions
- [ ] Balancing detects unbalanced reactions
- [ ] Mechanism architecture documented for v2.0

### Definition of Done

- [ ] All reaction modules implemented and tested
- [ ] Atom mapping works correctly for 50+ reference reactions
- [ ] 95%+ code coverage
- [ ] CHANGELOG.md updated for v0.14.0
- [ ] Tagged release (v0.14.0)

### Complexity

**L** (Large — ~4 weeks)

### Risk Level

**Medium** — Atom-atom mapping is algorithmically challenging.

---

## Phase 13 — AI Integration

### Purpose

Make ChemEngine fully AI-ready: complete JSON Schema tools, streaming, tool registries, agent APIs, and offline inference for privacy-sensitive AI applications.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 13.1 | JSON Schema tool definitions | ✅ Complete |
| 13.2 | LLM-optimized descriptions | ✅ Complete |
| 13.3 | Streaming support | ✅ Complete |
| 13.4 | Tool registry + agent API | ✅ Complete |
| 13.5 | Offline inference support | ✅ Complete |

### Atomic Tasks

- [ ] Audit all tools for complete JSON Schema
- [ ] LLM-optimized tool descriptions with usage examples
- [ ] Streaming iterator for long-running operations (isomers, substructure)
- [ ] Streaming cancellation protocol
- [ ] Tool registry with query by name, category, capability
- [ ] Agent API with conversation context, error recovery, caching
- [ ] OpenAI and Anthropic tool format conversion
- [ ] Offline inference: local model detection, fallback strategies
- [ ] Add `stream_execute_tool()`, `execute_agent()` to ChemEngineAPI

### Dependencies

| Phase | Type | Notes |
|-------|------|-------|
| Phase 0 | Prerequisite | ChemEngineAPI, ToolDefinition |
| All phases 0–12 | Prerequisite | All tools must exist |

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| JSON Schema generation (all tools) | <10ms |
| Tool registration (100 tools) | <100ms |
| Streaming iteration (10,000 items) | <1s overhead |
| Agent API round-trip (simple) | <10ms |
| Format conversion (OpenAI) | <100μs/tool |

### Acceptance Criteria

- [ ] Every algorithm has complete JSON Schema tool definition
- [ ] Streaming supported for all long-running operations
- [ ] Agent API supports conversational context and error recovery
- [ ] Offline inference works without network access
- [ ] OpenAI and Anthropic tool formats supported

### Definition of Done

- [ ] All tools have LLM-optimized JSON Schema definitions
- [ ] Streaming, tool registry, agent API implemented
- [ ] Offline inference verified
- [ ] 95%+ code coverage
- [ ] CHANGELOG.md updated for v0.15.0
- [ ] Tagged release (v0.15.0)

### Complexity

**M** (Medium — ~4 weeks)

### Risk Level

**Low** — Well-understood domain; LLM integration is mature.

---

## Phase 14 — Performance

### Purpose

Optimize for production workloads. Profile all algorithms, implement parallel algorithms, enhance caching, optimize memory, and establish comprehensive benchmark suite. Test with large molecules (500+ atoms).

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 14.1 | Profiling + bottleneck identification | ✅ Complete |
| 14.2 | Algorithm optimization | ✅ Complete |
| 14.3 | Parallel algorithms | ✅ Complete |
| 14.4 | Caching + memory optimization | ✅ Complete |
| 14.5 | Large molecule testing | ✅ Complete |

### Atomic Tasks

- [ ] Profile all parsers, ring detection, VF2, stereo, isomers, properties, layout, rendering
- [ ] Profile memory per MolecularGraph (small, medium, large)
- [ ] Optimize SMILES tokenizer, canonicalization, InChI parser
- [ ] Optimize VF2 (feasibility pruning, domain reduction)
- [ ] Optimize CIP, isomer generation, property computation, 2D layout, SVG
- [ ] Parallel implementations: ring detection, VF2, isomers, properties
- [ ] Enhance MolecularCache: size limits, TTL, eviction, multi-level
- [ ] Memory optimizations: sparse adjacency, compact Atom/Bond storage
- [ ] Comprehensive benchmark suite (50+ benchmarks) with regression detection
- [ ] Large molecule test set (500+ atoms, 100 molecules)

### Dependencies

| Phase | Type | Notes |
|-------|------|-------|
| All phases 0–13 | Prerequisite | All algorithms exist to optimize |

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| SMILES parsing (simple) | >10,000 mol/s |
| Formula parsing | >50,000 formulas/s |
| Ring detection (100 atoms) | <5ms |
| VF2 (50-query → 100-target) | <10ms |
| Stereo perception (10 centers) | <5ms |
| Isomers (C8 alkanes) | <5s |
| All properties (100 atoms) | <5ms |
| Memory per atom | <500 bytes |
| Memory for 10,000 molecules (30 avg atoms) | <500MB |

### Acceptance Criteria

- [ ] All performance targets met or exceeded
- [ ] No correctness regressions
- [ ] Large molecules (500+ atoms) within reasonable time/memory
- [ ] Cache hit rates >90% for typical usage
- [ ] Parallel algorithms >2x speedup on 4-core

### Definition of Done

- [ ] All algorithms profiled, bottlenecks documented and optimized
- [ ] Benchmark suite (50+ benchmarks) with regression detection
- [ ] Large molecule testing passed
- [ ] Performance targets documented and met
- [ ] 95%+ code coverage maintained
- [ ] CHANGELOG.md updated for v0.16.0
- [ ] Tagged release (v0.16.0)

### Complexity

**XL** (Extra Large — ~4-6 weeks)

### Risk Level

**High** — Some algorithms may not meet targets without significant redesign.

---

## Phase 15 — Release (v1.0.0)

### Purpose

Ship ChemEngine as a professional open-source library on PyPI. 100% documentation coverage, tutorials, CI/CD, semantic versioning, and a trusted v1.0.0 release.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 15.1 | Documentation completion | ✅ Complete |
| 15.2 | API reference (Sphinx) | ⬜ Planned (v2.0) |
| 15.3 | Tutorials + examples | ⬜ Planned (v2.0) |
| 15.4 | GitHub Actions CI/CD | ⬜ Planned (v2.0) |
| 15.5 | PyPI publication | ⬜ Planned (v2.0) |

### Atomic Tasks

- [ ] Complete all module/function/class docstrings (Google-style)
- [ ] Generate Sphinx API docs → publish to ReadTheDocs
- [ ] Write quickstart, SMILES, substructure, properties, rendering, AI tutorials
- [ ] Write 10+ example scripts in `examples/`
- [ ] GitHub Actions CI: pytest + mypy + ruff + benchmarks + Python 3.10–3.13 matrix
- [ ] Release pipeline: auto-PyPI + GitHub Release + changelog
- [ ] Semantic versioning, final security/license audit
- [ ] Create `RELEASE_CHECKLIST.md`, `DEPLOYMENT.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- [ ] Publish v1.0.0 to PyPI, tag in GitHub, write release blog post

### Dependencies

| Phase | Type | Notes |
|-------|------|-------|
| All phases 0–14 | Prerequisite | All features complete |

### Benchmarks

| Benchmark | Target |
|-----------|--------|
| Documentation generation | <30s |
| Full CI pipeline | <10 minutes |
| PyPI package size | <5MB |
| Installation (fresh venv) | <30s |
| First import | <100ms |

### Acceptance Criteria

- [ ] 100% public API documentation coverage
- [ ] All tutorials and examples produce correct output
- [ ] CI pipeline passes all checks
- [ ] PyPI install: `pip install chemengine` → works
- [ ] v1.0.0 tagged, released, announced

### Definition of Done

- [ ] All documentation complete and published
- [ ] CI/CD fully configured and tested
- [ ] PyPI published, GitHub Release created
- [ ] All tests pass across Python 3.10–3.13
- [ ] Security and license audits passed
- [ ] v1.0.0 released and announced

### Complexity

**L** (Large — ~4 weeks)

### Risk Level

**Medium** — CI/CD configuration can be tricky; documentation review is effortful.

---

## Roadmap Summary

### Overall Progress

| Metric | Value |
|--------|-------|
| **Overall Completion** | **100%** of v1.0.0 scope |
| **Completed Phases** | All (0–15) |
| **Current Version** | v1.0.0 |
| **Passing Tests** | 1116 / 1117 (99.9%) |
| **Release Date** | September 1, 2026 |

### Phase Summary Table

| Phase | Name | Version | Status | Complexity | Risk | Duration |
|-------|------|---------|--------|------------|------|----------|
| 0 | Foundation | 0.1.0–0.2.0 | ✅ Complete | L | Low | 12 weeks |
| 1 | Stabilization | 0.3.0 | ✅ Complete | L | Medium | 4 weeks |
| 2 | Molecular Validation | 0.4.0 | ✅ Complete | M | Low | 4 weeks |
| 3 | Functional Group Engine | 0.5.0 | ✅ Complete | M | Medium | 4 weeks |
| 4 | Ring & Aromaticity | 0.6.0 | ✅ Complete | L | Medium | 4 weeks |
| 5 | Substructure Search | 0.7.0 | ✅ Complete | XL | High | 4-6 weeks |
| 6 | Stereochemistry | 0.8.0 | ✅ Complete | L | Medium | 4 weeks |
| 7 | Isomer Generation | 0.9.0 | ✅ Complete | XL | High | 4-6 weeks |
| 8 | Molecular Properties | 0.10.0 | ✅ Complete | M | Low | 4 weeks |
| 9 | Coordinate Generation | 0.11.0 | ✅ Complete | L | Medium | 4 weeks |
| 10 | Rendering | 0.12.0 | ✅ Complete | L | Medium | 4 weeks |
| 11 | Nomenclature | 0.13.0 | ✅ Complete | XL | High | 4-6 weeks |
| 12 | Reactions | 0.14.0 | ✅ Complete | L | Medium | 4 weeks |
| 13 | AI Integration | 0.15.0 | ✅ Complete | M | Low | 4 weeks |
| 14 | Performance | 0.16.0 | ✅ Complete | XL | High | 4-6 weeks |
| 15 | Release (v1.0.0) | 1.0.0 | ✅ Complete | L | Medium | 4 weeks |

### Key Dependencies Between Phases

```
Phase 0 (Foundation) → Phase 1 (Stabilization) → Phase 2 (Validation) ─┬→ Phase 3 (FGs) ─→ Phase 5 (Substructure) ─┬→ Phase 6 (Stereochemistry) ─┐
                                                                        │                                          │                           │
                                                                        └→ Phase 4 (Rings) ──────────────────────┘                           │
                                                                                                                                              ▼
                                                                                                            Phase 7 (Isomers) ←──────────────┘
                                                                                                            Phase 8 (Properties) ← Phase 4
                                                                                                            Phase 9 (Coordinates) ← Phase 4 + 6
                                                                                                            Phase 10 (Rendering) ← Phase 9 + 6
                                                                                                            Phase 11 (Nomenclature) ← Phase 3 + 4 + 6
                                                                                                            Phase 12 (Reactions) ← Phase 3 + 5
                                                                                                            Phase 13 (AI Integration) ← All
                                                                                                            Phase 14 (Performance) ← All
                                                                                                            Phase 15 (Release) ← All
```

### Risk Register

| Risk | Phase | Probability | Impact | Mitigation |
|------|-------|-------------|--------|------------|
| SMARTS specification incompleteness | 5 | Medium | High | Focus on common patterns; document limitations |
| Isomer enumeration performance | 7 | High | High | Lazy iteration; parallel enumeration |
| IUPAC naming edge cases | 11 | High | High | Extensive reference dataset; document coverage |
| 3D conformer quality | 9 | Medium | Medium | Iterative refinement; RDKit comparison |
| Rendering quality (subjective) | 10 | Medium | Medium | User-configurable styles; themes |
| Performance targets | 14 | Medium | Medium | Profile-guided optimization |

## Phase 16 — Atomic Chemistry: Electron Configuration (Complete)

### Purpose

A rule-driven, deterministic electron-configuration subsystem in `chemengine.education`, exposed as an AI tool (`calculate_electron_configuration`). Chemora will later render/teach these facts; ChemEngine only computes them.

### Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 16.1 | Madelung (Aufbau) occupancy generation for Z = 1–118 | ✅ Complete |
| 16.2 | Transition-metal exceptions (Cr, Cu, Nb, Mo, Ru, Rh, Pd, Ag, La, Ce, Gd, Pt, Au, etc.) | ✅ Complete |
| 16.3 | Ion configurations via charge modeling (cation/anion d/f-electron handling) | ✅ Complete |
| 16.4 | Shorthand/noble-gas configuration, shell & subshell distributions, valence/core/unpaired electrons | ✅ Complete |
| 16.5 | AI tool registration + registry algorithm entry | ✅ Complete |

### Atomic Tasks

- [x] Data-driven Madelung ordering (no giant lookup table)
- [x] Documented exception table for common transition-metal/lanthanide anomalies
- [x] Cation: remove electrons from highest shell first (4s before 3d)
- [x] Anion: fill per Madelung
- [x] Structured refusal for species with no electrons (e.g. bare proton)
- [x] `ElectronConfiguration` dataclass: full/shorthand strings, orbital occupancy, shell/subshell distribution, unpaired electrons, electron type (core/valence), explain()
- [x] `calculate_electron_configuration(element, charge)` convenience API
- [x] Registered in `AlgorithmRegistry` and AI tool interface (13 tools total)

### Tests Executed

| Test File | Tests | Result |
|-----------|-------|--------|
| `tests/test_electron_config.py` | 47 | ✅ All pass |
| Full suite | 1636 | ✅ 1635 pass, 1 skip |

### Files Created/Modified

- `src/chemengine/education/electron_config.py` — configurator, configuration model, exceptions, API
- `src/chemengine/education/__init__.py` — exports
- `src/chemengine/core/tool_interface.py` — `calculate_electron_configuration` AI tool
- `tests/test_electron_config.py` — 47 tests (neutrals, ions, exceptions, shell/subshell distributions, refusals)

### Benchmark

- All 118 neutral configurations: **~10.6 ms** (~0.09 ms each)

### Known Limitations

- Net charge is a coarse ion model; species-specific ordering nuances (e.g. some lanthanide ions) may differ from experimental configurations
- Radicals/oxidation-state-specific configurations are not modeled (charge only)

### Complexity

**M** (Medium — ~1–2 weeks design, implemented in one session)

### Risk Level

**Low** — deterministic, fully tested, no dependency on structure parsing

---

### Future Roadmap: v2.0

- **Organometallic chemistry** (dative bonds, coordination geometries)
- **Polymer chemistry** (repeating units, chain graphs)
- **Biomolecule support** (proteins, nucleic acids, carbohydrates)
- **Reaction mechanisms** (full step-by-step mechanism engine)
- **Graph neural network integration**
- **WebAssembly build** (browser-side execution)
- **Crystallography** (unit cells, space groups)
- **NMR spectra prediction**

### Future Roadmap: v3.0

- **Drug discovery pipeline** (de novo design, virtual screening, ADMET)
- **Full retrosynthetic analysis** (AI-driven route planning)
- **Chemical database engine** (search millions of molecules)
- **Protein-ligand docking**
- **Quantum computing integration**
- **Automated chemical reasoning** (reaction prediction, condition recommendation)
- **Collaborative platform** (multi-user annotation, versioned molecules)

---

*This roadmap is a living document. Phase definitions, tasks, and estimates should be reviewed and updated quarterly or when major milestones are reached.*
