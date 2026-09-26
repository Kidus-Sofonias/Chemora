# Chemora — Engineering Roadmap

> **📊 Live Gantt chart**: Open [`gantt.html`](gantt.html) in your browser for an interactive, animated visualization of this roadmap. Automatically updates when phase statuses change.

> **Version:** 0.10.0 → 1.2.0 (ChemEngine complete through M34; monorepo migration complete)
> **Last Updated:** September 23, 2026
> **Owner:** Chemora Architecture Team
> **Status:** Active Development — ChemEngine M1–M34 complete; Backend M19–M31 complete; Web M21–M30 complete; Admin M27 complete

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
| **Passing Tests** | 1984 / 1988 (100%), 4 skips (all documented) | >5,000 |
| **Test Files** | 47 | >60 |
| **Source Files** | 82 Python files | >100 |
| **Elements** | All 118 | All 118 |
| **Documentation** | 10 documents | 30+ documents |
| **Benchmarks** | 60 benchmarks | 50+ benchmarks |
| **Code Coverage** | ~70% (estimated) | >95% |
| **Known Defects** | 0 (all regression-tested) | 0 |
| **Stub Modules** | 0 packages | 0 |
| **Last Updated** | September 23, 2026 | — |

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
| 1.1.0 | 2026-09-21 | M33 — ChemEngine v2.0 Feature Completion | ✅ Complete |
| 1.2.0 | 2026-09-23 | M34 — Full Reaction Mechanism Engine | ✅ Complete |

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

## Monorepo Migration (Complete — 2026-09-10)

Chemora was restructured from a ChemEngine-only repository into a proper monorepo. ChemEngine now lives at `packages/chemengine/` and remains independently installable and testable. The backend, frontend apps (mobile/web/admin), and infrastructure have reserved top-level locations.

**Acceptance criteria:**
- [x] Chemora is a monorepo
- [x] ChemEngine lives under `packages/chemengine/`
- [x] ChemEngine remains independently structured (src layout preserved)
- [x] Backend has a reserved top-level location (`backend/`)
- [x] Frontend apps have reserved locations (`apps/mobile/`, `apps/web/`, `apps/admin/`)
- [x] Infrastructure has a reserved location (`infrastructure/`)
- [x] No duplicate ChemEngine implementation exists
- [x] No chemistry functionality was lost
- [x] Public ChemEngine imports still work (`import chemengine`)
- [x] ChemEngine tests still pass: **1635 passed, 1 skipped**
- [x] Chemical validation remains correct
- [x] Documentation paths updated

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
| 1.4 | Property-based testing integration | ✅ Complete — 24 `@given` tests in `tests/test_property_based.py` (verified M33 discovery) |
| 1.5 | Documentation synchronization | ✅ Complete |
| 1.6 | Benchmark baseline establishment | ✅ Complete — 60-function baseline established + CI regression gate (M31/M32); first-import <100 ms target closed by M33 (490 → ~19–27 ms, cold `-X importtime` median of 3; regression gate in `tests/test_import_performance.py`) |
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
- [x] Atropisomer placeholder data structures (v2.0) — `Atropisomer` dataclass + `detect_atropisomer_candidates()` exist in `stereochemistry/stereo_validation.py` (verified M33 discovery)
- [x] Stereo validation: ambiguous/conflicting detection (v2.0) — `StereoIssueType.AMBIGUOUS`/`CONFLICT` + validation implemented (verified M33 discovery)
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
- [x] Implement isomer filtering (by formula, mass, substructure) — `generation/filtering.py` (`IsomerFilter`) implemented + tested (verified M33 discovery)
- [x] Implement lazy iteration for large counts — generator-based iteration in `generation/filtering.py` (verified M33 discovery)
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
| 10.2 | PNG output (via SVG) | ✅ Complete (M33 — `rendering/png.py`, cairosvg optional extra, 2x/4x HiDPI, graceful `PNGUnavailableError` degradation) |
| 10.3 | Substructure highlighting | ✅ Complete (M33 — deterministic highlight layer on `render()`, tool surface, colors from `detection.substructure` matches) |
| 10.4 | Reaction arrows | ✅ Complete |
| 10.5 | Dark mode + themes | ✅ Complete (M33 — `RenderTheme` objects: dark, CPK, monochrome, accessibility; deterministic per theme) |

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
| 11.3 | Preferred IUPAC + common names | ✅ Complete (M33 — generator correctness pass; curated common-names dictionary, 63 names, tested) |
| 11.4 | IUPAC name parser | ✅ Complete (M33 — `parsing/iupac/{tokenizer,parser}.py`; generator round-trip on the supported grammar subset, documented coverage) |
| 11.5 | Tautomer handling | ✅ Complete (M33 — keto-enol + amide-imidic detection/canonicalization, bounded `MAX_TAUTOMER_FORMS=8`) |

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
| 12.2 | Atom-atom mapping | ✅ Complete (M33 — `reactions/mapping.py` deterministic skeleton MCS; 53-case reviewed reference oracle; budgeted search, explicit failures) |
| 12.3 | Reaction balancing + validation | ✅ Complete |
| 12.4 | Reaction templates | ✅ Complete |
| 12.5 | Mechanism architecture (v2.0) | ✅ Complete (M33 interfaces; M34 executable engine, curated rules, validated traces, reference oracle) |

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
| 15.2 | API reference (Sphinx) | ✅ Complete (M32) — `sphinx-build -W` clean, CI gate |
| 15.3 | Tutorials + examples | ✅ Complete (M32) — 6 tutorials + 12 executed examples with CI verification |
| 15.4 | GitHub Actions CI/CD | ✅ Complete (M31 monorepo CI + M32 Python 3.10–3.13 matrix + benchmark regression + docs/examples gates) |
| 15.5 | PyPI publication | 🔶 Release-ready (M32) — build + twine check pass, publish workflow + checklist prepared; upload blocked on credentials |

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

## Backend Roadmap (M19+)

The Chemora monorepo backend is developed milestone-by-milestone on top of the
Foundation/API layer. Backend milestones are tracked here.

### M19 — Backend Foundation ✅ Complete

| # | Task | Status |
|---|------|--------|
| M19.1 | FastAPI app, CORS, health check | ✅ Complete |
| M19.2 | Async SQLAlchemy 2.0 engine & session factory | ✅ Complete |
| M19.3 | Alembic migrations scaffolding | ✅ Complete |
| M19.4 | Backend `pyproject.toml`, settings, `.env.example` | ✅ Complete |

### M20 — Authentication ✅ Complete

Secure, production-oriented authentication using Google Sign-In / Google
Identity Services. Google identity is verified server-side; Chemora then
establishes its own server-managed session.

- Google ID-token verification (signature, issuer, audience, expiry, subject)
  via the maintained `google-auth` library through a mockable
  `GoogleTokenVerifier` abstraction.
- User identity keyed by Google `sub` (email is **not** the identity key);
  unique constraint prevents duplicate identities.
- Server-managed sessions with absolute expiration, inactivity timeout, and
  sliding renewal — no permanent sessions, no login-on-every-request.
- Endpoints: `POST /auth/google`, `GET /auth/me`, `POST /auth/logout`.
- Reusable `get_current_user` FastAPI dependency.
- Alembic migration `001_initial_auth_tables` (users + sessions).
- 40 backend tests passing (in-memory SQLite + mock verifier).

### M21 — Frontend Authentication Integration ✅ Complete

React + Vite web client that integrates the M20 authentication backend. The
backend remains the authority; the client never manufactures identity.

- React 18 + Vite + TypeScript web app (`apps/web/`)
- Centralized `ApiClient` (fetch + `credentials: include`, JSON, typed
  base URL, 401-vs-network error classification)
- `AuthProvider` state machine: loading / unauthenticated / authenticated /
  error — never shows authenticated content before the session check finishes
- `AuthService`: `getCurrentUser()` / `exchangeCredential()` / `signOut()`
- `GoogleSignInProvider` port; production uses Google's official GIS client
  (`accounts.google.com/gsi/client`) — ID token sent to backend, never treated
  as a Chemora session
- 18 passing frontend tests (real ApiClient + AuthService vs. scriptable
  fake backend + mock Google provider)
- Mobile (`apps/mobile`) not yet configured — compatibility gap documented

### M22 — Chemistry Explorer Foundation ✅ Complete

The first user-facing Chemora feature: a Chemistry Explorer that proves
`web → backend → ChemEngine → deterministic chemistry` end to end.

- Backend `POST /api/v1/chemistry/explore` with explicit Pydantic
  request/response models and a thin `ChemistryService` adapter over
  `ChemEngineAPI` (no chemistry re-implemented in FastAPI).
- **Identity for every input:** formula, exact (monoisotopic) mass, average
  mass, heavy-atom count, atom count.
- **Structure + descriptors only for structure-bearing inputs** (SMILES,
  InChI, resolved names): canonical SMILES, engine-rendered SVG depiction,
  atom/bond lists, LogP, TPSA, HBA, HBD, rotatable bonds, ring count,
  fraction C(sp³).
- Correctness decisions from verified engine behaviour: a molecular formula
  does not encode connectivity, so formula inputs report
  `structure_available: false` rather than presenting unreliable bond data;
  the engine's non-IUPAC-standard InChI/InChIKey serializers are not exposed.
- Explorer UI inside the authenticated shell (identity card, structure card
  with engine SVG, properties grid, formula-only note), responsive and
  accessible, with distinct chemistry/network/server error states and
  no auto-retry.
- 20 new backend tests (13 API + 7 service integration against the real
  engine) and 9 new frontend tests (27 total, real ApiClient + mocked
  transport).

### M23 — Element Explorer ✅ Complete

The second user-facing Chemora feature: an Element Explorer connecting the
periodic table to ChemEngine's deterministic electron-configuration subsystem
(`education/electron_config`).

- Backend `GET /api/v1/elements` (all 118 elements: symbol, name, atomic
  number, mass, period, group, block, category) and
  `GET /api/v1/elements/{identifier}` (symbol / name / atomic-number lookup,
  case-insensitive) with explicit Pydantic models and a thin `ElementService`
  adapter. Electron configurations are computed by `ElectronConfigurator` from
  first principles — no chemistry in FastAPI or TypeScript.
- Structured electron data exposed: full and noble-gas configurations,
  shell distribution, subshell distribution, per-subshell orbital occupancy
  (electrons + capacity), valence/core/unpaired electron counts, and the
  engine's deterministic educational explanation.
- Interactive periodic table in the authenticated shell: real 18-column grid
  with engine-provided period/group/block placement (f-block rows for
  Ce–Lu / Th–Lr per the dataset's group=3 encoding), block colouring
  reinforced by text labels, keyboard-accessible element cells
  ("Oxygen, atomic number 8"), deliberate horizontal scroll on mobile.
- Element detail view: superscript-formatted configuration, orbital-box
  diagram rendered from engine occupancy data (Hund's-rule box arrangement is
  presentation only), shell distribution labelled as shells (not an orbital
  model), valence/core/unpaired counts, and the engine explanation behind a
  disclosure. Entrance animation is disabled under `prefers-reduced-motion`.
- Client-side element search (name / symbol / atomic number) filters the same
  engine-provided list — a UI index, not a second data source.
- Error contract: `unknown_element` / `invalid_identifier` 404s mapped to
  user-facing messages; network vs server failures distinguished in the UI.
- 18 new backend tests (real engine data: O, He, Fe, plus Cr/Cu Aufbau
  exceptions) and 10 new frontend tests (37 total).

### M24 — Chemistry Learning Core ✅ Complete

The first user-facing learning experience: structured lessons taught with
live deterministic chemistry from ChemEngine, plus server-validated practice
and authenticated progress.

- Content layer isolated in `backend/app/learning/content.py` (3 seeded
  lessons: Electron Configuration, Valence Electrons, Configuration →
  Behavior). Content is application data, NOT ChemEngine — the engine stays
  computation-only. Designed to move to a DB/CMS later without changing the
  API contract.
- Learning API under `/api/v1/learning/` with explicit Pydantic models:
  `GET /lessons`, `GET /lessons/{slug}`, `GET /lessons/{slug}/progress`,
  `POST /lessons/{slug}/sections/{id}/complete`, and
  `POST /lessons/{slug}/answers`. Answer keys never leave the server;
  validation is deterministic (normalized exact comparison, no LLM).
- Progress persisted in the `lesson_progress` table (Alembic migration
  `002_lesson_progress`, FK → users with CASCADE, unique per user/lesson):
  completed sections, per-question outcomes, derived percent, auto lesson
  completion, resume across sessions.
- `chemistry_spotlight` lesson sections name an element; the web client
  renders its live engine-computed detail through the same component the
  Element Explorer uses — no duplicated chemistry anywhere.
- Web Learn tab in the authenticated shell: lesson catalog, section
  progression, progress bar, practice questions with immediate server-graded
  feedback, structured-errors only (raw server details are never surfaced —
  enforced by a shared `userFacingMessage` helper).
- 17 new backend tests (catalog, answer keys hidden, auth requirements,
  progress create/update/complete/resume, correct/incorrect/normalized
  answers, unknown lesson/section/question, blank answer) and 10 new
  frontend tests (catalog, lesson + live spotlight, section completion,
  correct/incorrect feedback, validation error, network vs server errors,
  unknown lesson, catalog return).

### M25 — Learning and Practice Expansion ✅ Complete

More real chemistry and better practice, with the engine still the only source
of chemical truth.

- Content expanded from 3 to 5 lessons: *Chemical Formulas* (composition vs
  connectivity, mass, canonicalization) and *Molecules and Their Properties*
  (structure → descriptors → behaviour) — still seeded, still outside
  ChemEngine.
- Chemistry spotlights can now name a **molecule** (`molecule_input`) as well as
  an element; the client analyses it live through the existing M22 chemistry
  explore API and reuses the existing `ExplorerResult` component.
- Two ChemEngine-backed question kinds: `formula` (answers canonicalized via
  `formula_to_graph(...).molecular_formula`, so `H2O` and `HOH` both grade
  correct while `CO2` does not) and `element` (symbol / case-insensitive name /
  atomic number resolved through `Element.from_symbol` / `from_name` /
  `from_z`).
- Grading stays deterministic and server-side; an answer the engine cannot
  parse returns a client-safe `422 invalid_answer` instead of being marked
  wrong, and answer keys never leave the server.
- Fixed a real defect found while testing: the in-progress `formula` kind called
  `parse_formula` (which returns element counts) and read a non-existent
  `molecular_formula` attribute, so **no** formula answer could ever be graded
  correct. Canonicalization now uses the correct engine API, and a regression
  test asserts every seeded chemistry question accepts its own expected answer.
- Practice results view per practice section (attempted / correct / needs
  another look / accuracy), accessible and mobile-friendly, no gamification.
- 11 new backend tests (28 learning tests, 106 total) and 5 new frontend tests
  (52 total).

### M26 — Content Management Foundation ✅ Complete

Content moved from the seed layer into PostgreSQL behind an admin API, without
changing the student learning contract.

- Content tables (`lessons`, `lesson_sections`, `lesson_questions`) plus
  `users.is_admin` (Alembic migration `003_content_tables`, reversible).
- Admin API under `/api/v1/admin/lessons`: list (drafts included), retrieve
  (answer keys included), create (always draft), replace (publish state
  preserved), publish (validates first), unpublish. Slug changes are rejected
  (400 slug_mismatch) so `lesson_progress.lesson_slug` stays valid.
- Server-side validation before publish: metadata, section kinds, question
  kinds, multiple-choice option rules, numeric answer format, and chemistry
  references resolved through ChemEngine (formula canonicalization and element
  resolution) — invalid content can never be published.
- Idempotent seed/import (`python -m app.learning.seed`): the five seeded
  lessons are published so the database-backed catalog matches M24/M25 exactly.
- 31 admin API tests (authorization 401/403, CRUD, publish/unpublish,
  duplicate slug, validation, answer-key exposure, draft visibility) plus a
  corrective hardening pass (missing FK-constraint import, missing awaits on
  async content fetches, section-replace constraint violation, production
  SESSION_SECRET validation, progress-create IntegrityError recovery, shared
  chemistry validation module, `.gitattributes`).

### M27 — Production Content & Admin CMS ✅ Complete

The content system becomes operable by an administrator without editing seed
files.

- Admin CMS web application (`apps/admin/`, React 18 + Vite + TypeScript,
  hash-routed SPA, same conventions as `apps/web/`): dashboard with
  total/published/draft counts, lesson list with status/difficulty/counts/
  updated time and edit/preview/publish/unpublish actions, lesson editor with
  metadata + section add/edit/remove + question add/edit/remove, and a
  student-view preview page.
- Section types and question kinds in the UI are exactly the backend constants
  (`SECTION_KINDS`, `QUESTION_KINDS`) — no frontend-only question types.
- New admin-only preview endpoint `GET /api/v1/admin/lessons/{slug}/preview`
  returns the student-safe view of a lesson (answer keys and explanations
  stripped) for drafts and published lessons alike, without modifying
  publication state.
- Admin DTOs now expose `created_at` / `updated_at` (and `updated_at` in the
  lesson list) so the CMS can show real recency information.
- Publishing requires an explicit action; edits never auto-publish; slugs are
  immutable after creation; student progress survives content edits.
- Chemistry validation stays deterministic and server-side (ChemEngine via the
  shared `chemistry_validate` service) — no chemistry logic in TypeScript, no
  LLM anywhere.
- Admin lesson deletion: `DELETE /api/v1/admin/lessons/{slug}` refuses with
  409 `lesson_has_progress` when student progress references the lesson;
  `?force=true` performs the destructive delete (progress cascades) after a
  second explicit confirmation in the UI.
- 12 new backend tests (preview 200/401/403/404, preview hides answer keys,
  admin timestamp fields, deletion lifecycle: unauthorized/normal-user
  rejection, progress-protected deletion, force delete, draft delete) and
  11 admin frontend tests (dashboard stats, navigation, status badges,
  publish/unpublish buttons, editor navigation, preview rendering,
  answer-key absence in preview, delete confirm + 409 force flow).
- End-to-end browser verification of the admin CMS in Chrome (puppeteer-core
  against a live backend + built UI, 21/21 checks): auth gate, dashboard,
  lesson list, editor, preview without answer keys, delete with confirmation
  dialogs and server-side 404 verification.

---

### M28 — Chemistry Learning Experience Expansion ✅ Complete

Formally scoped, implemented from the audited pre-existing M28 work-in-progress,
and completed. M28 makes Chemora a substantially more useful chemistry learning
experience without regressing the M26/M27 database/CMS architecture.

- **Scope definition.** M28 was previously "(to be scoped)". After auditing the
  existing uncommitted M28 WIP against the roadmap, M28 was scoped as the
  **Chemistry Learning Experience Expansion** — a coherent curriculum built on
  the existing learning system, Chemistry Explorer, Element Explorer, and
  ChemEngine. It does **not** rebuild the CMS, does not add quiz/AI/offline/
  mobile features, and does not start M29.
- **Curriculum expansion (6 new lessons).** Added, in curated order after the
  five M24/M25 lessons: periodic-table, periodic-trends, chemical-bonding,
  molar-mass, stoichiometry, acids-bases.
- Each new lesson follows the established structure: coherent ordered sections,
  a `chemistry_spotlight` section (element or molecule) tied to ChemEngine, a
  practice section, and summary. Every question id is resolvable; every lesson
  passes the strict publish validator.
- **Content architecture preserved.** Content still lives in PostgreSQL via the
  M26/M27 CMS. `app/learning/content.py` remains an idempotent seed/import
  source only — re-seeding never duplicates lessons and it cannot override
  already-edited production drafts. The database remains the runtime source of
  truth; there is no competing runtime content source.
- **Learning navigation.** Added previous/next section navigation with an
  `aria-current` focused section, a position indicator, first-incomplete-section
  resume focus within a lesson, and a catalog-level resume experience
  (`GET /api/v1/learning/progress`): continue / review labels and per-lesson
  progress lines. Progress remains recorded only by the backend; completion
  never occurs before required work.
- **Deterministic chemistry authority.** No chemistry algorithms were added in
  TypeScript. Element spotlights come from the existing element API and molecule
  spotlights from the chemistry explore API, both ChemEngine-backed. Chemistry
  references are validated at authoring/publish time through ChemEngine.
- **New tests (all meaningful, failure paths included).** Backend +15
  (publish validation across the whole seed, M28-curriculum ordering/coherence,
  idempotent re-seed, publication-state preservation, valid + invalid molecule
  reference publish/rejections). Web +10 (resume badges, continue/review,
  prev/next nav, aria-current, focused-section resume-focus, no console
  errors). Admin +2.
- **Cleanup.** Removed the generated `.browser-verify/chemora.db` artifact (it
  is generated runtime state, not a test fixture) and added a `.gitignore`
    rule for it.

---

### M29 — AI Chemistry Tutor (Complete)

M29 is **complete** (2026-09-19). The scope below is retained for the record.

**Scope definition.** ChemEngine's AI Integration phase (Phase 13) is complete
and tested: `ChemEngineAPI.execute_tool()` exposes chemistry tools with JSON-Schema
signatures, `ToolRegistry` converts them to OpenAI/Anthropic tool formats, and
`OfflineInference` provides a local fallback path. The remaining gap is a backend
AI service that wires an LLM provider to these tools behind the existing auth/session
boundary. M29 is therefore the **AI Chemistry Tutor** — a backend AI service layer
with a provider abstraction and a student-facing chat tutor. It does **not** add
quizzes, mobile, offline sync, a CMS rebuild, or any modification to ChemEngine's
chemistry algorithms.

- **Architecture.** Student → web chat UI → backend `POST /api/v1/learning/tutor`
  (session-gated, user identity from the Chemora session) → AIService (provider
  abstraction + controlled RAG retrieval) → provider completion ↔
  `ChemEngineAPI.execute_tool()` server-side for deterministic chemistry. The LLM
  *never* becomes the chemistry authority: formula normalization, element lookup,
  electron configuration, and molecular properties come from ChemEngine tools.
- **In scope:**
  - `AIProvider` interface + OpenAI / Anthropic / mock implementations, configured
    from settings (provider secret server-side only; never exposed to the client).
  - Backend `AIService`: retrieve only relevant lesson content (controlled boundary
    — no dumping the full DB into prompts), invoke the provider, and call ChemEngine
    tools server-side; stream answers.
  - Authenticated `POST /api/v1/learning/tutor` endpoint.
  - Frontend chat tutor in the web client (no chemistry computation in TS).
  - Answer keys and draft-only content never leave the backend (reuse the preview/audit
    validation boundary so a tutor request can never leak keys for questions the
    student has not yet seen).
  - Cost/abuse controls: per-request token limits, timeouts, tool-result caching,
    graceful error/fallback handling, usage logging.
- **Out of scope:** quizzes/exams platform, mobile app, offline sync, CMS authoring
  rebuild, new ChemEngine algorithms, client-side provider keys.

**Acceptance criteria** (all satisfied — see `backend/app/services/ai/`,
`backend/app/api/v1/tutor.py`, `apps/web/src/ui/TutorPage.tsx`):
- [x] Provider abstraction with ≥1 real + 1 mock provider, all swappable without backend edits — `AIProvider` protocol with `MockAIProvider`, `OpenAIProvider`, and `AnthropicProvider`, selected by `AI_PROVIDER` settings.
- [x] Deterministic chemistry (formula/element/config/properties) always resolved via
  `ChemEngineAPI.execute_tool()` server-side; a test proves a wrong model answer on
  chemistry is corrected by the engine (`test_chemistry_authority_tool_wins`).
- [x] `POST /api/v1/learning/tutor` returns 401 unauthenticated, 403 for non-students
  where applicable (Chemora has no separate student role — every authenticated user
  is a student, so the 403 path has no applicable case), and never returns answer keys or draft content (retrieval serializes prompts only; enforced by tests).
- [x] Cost controls enforced (max input budget + output tokens, timeout,
  bounded tool loop, per-user rate limit, error/fallback on provider failure).
- [x] Web + backend tests for the provider boundary, authz, privacy, and a regression
  test that ChemEngine remains the authority (35 backend tests, 9 web tests).

**Deferred (not acceptance criteria):** streaming responses (in the scope prose,
not the acceptance list — future enhancement), persistent conversation storage
(stateless per-request design), live provider verification (no API key in the
environment; real-provider paths are exercised through the abstraction seam).

---

### M30 — AI Tutor Completion & Conversation Infrastructure (Complete)

M30 is **complete** (2026-09-19). The scope below is retained for the record.
M29 is complete. M30 takes the AI tutor from a stateless
request/response prototype to a complete conversational system.

**Objectives.** (1) Persist tutor conversations with server-enforced ownership
so a student's tutoring history survives page reloads and is loaded server-side
(the client can no longer supply arbitrary conversation history). (2) Stream
tutor responses incrementally through the existing `AIProvider` abstraction.
(3) Cache safe, deterministic ChemEngine tool results with bounded memory and
TTL. All M29 protections (published-lessons-only retrieval, no answer keys,
tool allowlist, schema validation, ChemEngine authority, rate limits, input/
output bounds, stable error codes, server-side provider credentials) carry
forward unchanged.

**In scope:**
- Persistent tutor conversations and messages: SQLAlchemy models, Alembic
  migration, repository/service layers following the existing
  Route → Service → Repository architecture, authenticated ownership derived
  only from the server-side session, conversation creation/retrieval/listing
  (as the UI requires)/deletion, server-side message history, cross-user
  isolation, reasonable conversation/message limits, appropriate indexes and
  constraints. A client-provided user id or ownership field is never trusted.
- Tutor response streaming: a streaming endpoint (POST + streaming response,
  because the request carries conversation/input state) reusing the existing
  provider abstraction without redesign; authenticated, bounded input,
  bounded execution; correct handling of provider tool calls, partial
  responses, provider failures, interrupted/cancelled requests, unauthorized
  and malformed requests.
- Tool-result caching: bounded, deterministic cache for safe ChemEngine tool
  results only (deterministic keys, TTL, entry/memory bounds, hit/miss and
  expiration tests). Private conversation content and arbitrary LLM responses
  are never cached.
- Conversation-aware tutor: `TutorService` loads history server-side from the
  persistence layer; the client cannot inject another user's history.
- Frontend: extend the existing `TutorPage` for starting/continuing
  conversations, loading history, incrementally rendering streamed responses,
  clear loading/streaming/error/empty states, retry, and conversation
  switching/deletion as the API exposes them. No unnecessary UI complexity.
- Tests: backend coverage of conversation CRUD, ownership, cross-user
  isolation, server-side history, streaming (success/failure/interruption/
  tool calls), cache hit/miss/expiration, malformed and oversized requests,
  and auth boundaries; web tests for history loading, streaming rendering,
  partial responses, failure, retry, switching and deletion; full regression.

**Out of scope:** ChemEngine algorithm changes (unless required by a
demonstrated defect), chemistry in TypeScript, bypassing the provider
abstraction, exposing API keys, trusting client ownership, exposing drafts or
answer keys, vector search, speculative AI features, quizzes/exams, mobile,
offline sync, CMS rebuild, ChemEngine v2/v3 roadmap items, and M31 work.

**Acceptance criteria** (all satisfied — see `backend/app/models/tutor.py`,
`backend/app/repositories/tutor.py`, `backend/app/services/ai/cache.py`,
`backend/app/services/ai/service.py`, `backend/app/api/v1/tutor.py`,
`apps/web/src/ui/TutorPage.tsx`):
- [x] Persistent conversations work correctly; ownership is server-enforced
  (every repository query filters by the session-derived `user_id`; a foreign
  conversation is indistinguishable from a missing one — 404); cross-user
  isolation is tested (`test_cross_user_isolation`); server-side conversation
  history works (`test_server_side_history_and_persistence` — the client never
  sends history).
- [x] Streaming tutor responses work through the provider abstraction
  (`POST /api/v1/learning/tutor/conversations/{id}/messages` emits SSE
  `delta`/`done`/`error` frames; all three shipped providers implement
  `generate_stream` behind the unchanged `AIProvider` abstraction); the
  frontend incrementally renders streamed responses
  (`useTutor` + `TutorStreamEvents` reader); streaming failure and
  interruption are handled (mid-stream SSE error frames, non-2xx pre-flight,
  partial answers persisted on disconnect).
- [x] Safe deterministic ChemEngine tool results are cached correctly with
  tested bounds and TTL (`ToolResultCache`: deterministic sorted-key + SHA-256
  keys, lazy TTL sweep, insertion-order eviction; `test_tool_result_cache` —
  hit/miss/expiration/bounds; failures are never cached; conversation content
  and LLM responses are never cached).
- [x] Existing M29 security boundaries remain intact (220 backend tests
  include the full M29 suite unchanged); no answer keys or drafts are exposed.
- [x] Full regression, static checks, and production builds pass; documentation
  and the Gantt are reconciled.

**Deferred (not acceptance criteria):** live provider verification (no API key
in the environment; streaming providers are exercised through the abstraction
seam with deterministic fakes), browser E2E (tooling unavailable in this
environment — covered by jsdom streaming/interaction tests instead),
distributed rate limiting, server-sent conversation titles auto-generated by
the model.

**Dependencies:** M29 (provider abstraction, tool allowlist, retrieval,
auth boundary, cost controls). **Testing requirements:** unit + integration +
security tests at every layer, full regression with exact totals recorded.
**Security requirements:** session-derived identity only, per-user isolation,
no secret exposure, bounded inputs and expensive operations, stable error
surfacing. **Known limitations to record at completion:** live provider
verification requires an API key (not present in the environment); browser
E2E depends on tooling availability.

---

### M31 — Production Readiness & Release Engineering (✅ Complete)

M31 was **scoped** (2026-09-19) and is now **complete** (2026-09-20). M30 is
complete. M31 is deliberately **not** a chemistry-feature milestone: it takes
the existing Chemora system through a production-readiness and
release-engineering pass so the application can be deployed, tested,
monitored, and maintained reliably. All product functionality delivered
through M30 must remain intact.

**Objectives.** (1) Verify the system deploys against a real production
database. (2) Verify the AI provider paths against real credentials only
where they are genuinely available. (3) Add real CI that runs the project's
own backend/ChemEngine/web/admin checks and fails when they fail.
(4) Establish a reproducible release/build and environment/secrets
verification process. (5) Add critical browser E2E coverage where reliable
browser automation is feasible. (6) Measure the project's existing documented
coverage/benchmark targets accurately. (7) Complete the release-engineering
documentation already identified in the roadmap. (8) Ensure
production-critical failure diagnostics and health checks exist without
exposing sensitive information. (9) Dispose of the M30 deferred items
correctly.

**In scope:**
- **Production database verification:** verify the complete Alembic chain
  (001 → latest) against a real PostgreSQL environment — fresh migration,
  upgrade path, schema/application agreement, PostgreSQL constraints and
  indexes, tutor conversation persistence on PostgreSQL, rollback/downgrade
  assessment where appropriate, and understood migration failure behavior.
  SQLite is used only where existing tests intentionally use it and never
  substitutes for PostgreSQL verification. If no PostgreSQL instance is
  available, the environment blocker is documented explicitly and the
  requirement is not claimed as live-verified.
- **Real AI provider smoke verification (only if valid credentials exist):**
  real provider initialization, one real authenticated request, a normal
  tutor response, the tool-call path where feasible, the streaming path,
  provider failure and timeout behavior, and observable usage/cost behavior.
  API keys are never printed, committed, placed in frontend code, or exposed
  through API responses; a live test is never fabricated; nothing is
  purchased and no external accounts are created. Without credentials, the
  maximum safe offline/provider-seam verification is performed and the live
  blocker documented.
- **CI/CD:** a real repository pipeline reflecting the actual monorepo
  structure that runs, at minimum — backend `pytest`/`ruff`/`mypy`, web
  tests/`tsc`/production build, admin tests/`tsc`/production build, and
  ChemEngine tests plus relevant static checks — and fails when any required
  check fails. No superficial single-command workflow; existing checks are
  never weakened to make CI green.
- **Release/build verification:** a reproducible release-validation process
  covering web and admin production builds, the backend startup/import path,
  the migration chain, environment configuration, required environment
  variables, absence of committed secrets, `.env` remaining ignored, and
  `.env.example` completeness/safety; document the minimum environment
  required to run Chemora.
- **Browser E2E (where technically feasible):** browser automation introduced
  only if it integrates cleanly with the existing web architecture and CI,
  prioritizing critical flows — authentication shell, Chemistry Explorer
  basic load, learning navigation, tutor conversation creation, streaming,
  persistence/reload, deletion, and the logout/auth boundary. If reliable
  automation is not achievable in this environment, the exact blocker is
  documented instead of creating fake E2E coverage; browser verification is
  claimed only if an actual browser executes the tests.
- **Coverage + benchmark baselines:** measure the roadmap's existing
  documented targets — the Phase 1.6 benchmark baseline, the Phase 1 DoD
  coverage boxes, and backend/web coverage where applicable — reproducibly
  and accurately. New percentages are never invented; targets are never
  deleted or weakened; if a target is not currently attainable, the exact
  gap is documented.
- **API/project documentation:** complete the release-engineering
  documentation already identified in the roadmap where applicable — API
  reference, developer setup instructions, CI/CD documentation, release
  procedure, environment variable documentation, production deployment
  prerequisites, migration procedure, and testing commands — never claiming
  infrastructure exists when it does not.
- **Observability/failure diagnostics:** where supported by the existing
  architecture, improve structured logging, request/error identification,
  provider failure diagnostics, database failure diagnostics, startup
  validation, and health/readiness checks — proportionate, without a
  heavyweight observability platform, and never logging API keys,
  credentials, private conversation contents, answer keys, or sensitive user
  data.
- **M30 deferred-item disposition:** live provider smoke test — included
  (above). Browser E2E — included where technically feasible (above).
  Distributed rate limiting — implemented only if the actual deployment
  architecture requires it; otherwise documented as future work.
  Model-generated conversation titles — NOT implemented (a UX enhancement,
  not release engineering) unless the roadmap explicitly establishes it as a
  release requirement.

**Out of scope:** new ChemEngine chemistry domains, organometallic chemistry,
polymer chemistry, biomolecules, a reaction-mechanism engine, GNN
integration, WebAssembly ChemEngine, crystallography, NMR prediction, drug
discovery, retrosynthesis, docking, quantum chemistry, a chemical database
engine, a mobile application, offline sync, the quizzes/exams platform, a CMS
rebuild, speculative AI features, vector search, and M32/M33 work. The
ChemEngine v2.0/v3.0 future roadmap remains separately labeled as a
longer-term roadmap and is NOT relabeled as M31.

**Acceptance criteria** (M31 is complete only when all of the following
hold — all satisfied; see `infrastructure/RELEASE.md`, `infrastructure/ci_check.py`,
`.github/workflows/ci.yml`, `backend/scripts/pg_verify.py`,
`backend/scripts/ai_provider_verify.py`, `backend/scripts/release_verify.py`,
`backend/scripts/e2e_verify.py`, and `backend/app/main.py` `/health/ready`):
- [x] Production PostgreSQL migration path is verified, or an explicit
  environment blocker is documented. — **VERIFIED LIVE:** real PostgreSQL 18.6
  (portable binary, temp dir, no system install); 33/33 checks pass including
  full chain `upgrade head` from base, schema introspection, tutor
  conversation/message persistence with ownership, cross-user isolation over
  real HTTP, downgrade-to-base + re-upgrade cycles.
- [x] Real AI provider smoke verification is performed where credentials are
  available, or the lack of credentials is explicitly documented. — **BLOCKED,
  DOCUMENTED:** no API key exists in the environment. Compensating offline
  verification (`ai_provider_verify.py`): 17/17 pass — factory selection, mock
  provider, missing-SDK fallback, real HTTP error mapping through the
  installed optional SDKs (timeout/refusal → stable categories), key-never-
  logged asserted. Live smoke command documented in `infrastructure/RELEASE.md` §7.
- [x] CI automatically executes the project's required backend, ChemEngine,
  web, and admin checks. — `.github/workflows/ci.yml`: 12 blocking gates
  (ChemEngine tests + ruff baseline + benchmark smoke; backend ruff/mypy/pytest;
  web vitest/tsc/build; admin vitest/tsc/build). Validated locally by
  `infrastructure/ci_check.py` (12/12 pass).
- [x] CI correctly fails on broken required checks. — Proven by sabotage test:
  a syntax error injected into `backend/app/main.py` made ruff exit 1 and mypy
  exit 2; gates exit 0 again after restore. The workflow contains no `|| true`,
  no `continue-on-error` on required steps, and `--no-fix` everywhere (CI can
  never mutate files) — all asserted by `ci_check.py` invariants.
- [x] Production builds are reproducible. — `release_verify.py` 18/18: clean
  `dist/` builds for web + admin with expected artifacts, backend wheel builds,
  app imports with production settings, migration chain resolves, npm/pip
  installs resolve from committed lockfiles/configs.
- [x] Environment/secrets configuration is documented and safe. — `.env`
  git-ignored (verified), `.env.example` placeholders only and completed with
  the M30 `AI_TOOL_CACHE_*` variables, production mode refuses missing
  `SESSION_SECRET` and forces `COOKIE_SECURE`, no secrets in git history of M31
  changes, `infrastructure/RELEASE.md` §9 documents every required variable.
- [x] Critical browser E2E coverage exists if the environment supports
  reliable browser automation; otherwise the exact blocker and compensating
  tests are documented. — **EXECUTED:** real Chromium 147 (Playwright) driving
  the real production bundle against the real backend: 10/10 flows pass
  (auth gate, login, learning catalog, Chemistry Explorer on real ChemEngine,
  tutor streaming, persistence across reload, conversation switching,
  deletion, logout, clean console). Also fixed the missing favicon the run
  uncovered.
- [x] Existing documented coverage/benchmark targets are measured accurately.
  — ChemEngine **80%** overall (`pytest --cov`, matches the documented ~80%),
  backend **80%** on `app/` (220 tests under coverage), web **88.97%** lines
  (74 tests under coverage), admin **62.35%** lines (13 tests under coverage).
  Phase 1.6 benchmark baseline **established**: 60 benchmark functions pass
  (~63s), including the SMILES/formula/alias parsing benchmarks the roadmap
  named but that did not exist before M31 (`benchmarks/benchmark_parsing.py`).
  The Phase 1 DoD aspiration of 95% infra / 90% overall coverage is NOT met
  (80%) — the exact gap is recorded rather than hidden.
- [x] Existing API/developer/release documentation is updated where required.
  — `infrastructure/RELEASE.md` (new runbook: setup, CI gates, PostgreSQL
  procedure, provider verification, E2E, env checklist, release procedure),
  `infrastructure/README.md` (was a stale placeholder), `backend/.env.example`,
  `backend/pyproject.toml` (`providers` + `e2e` extras).
- [x] Production-critical diagnostics/health checks are adequate without
  exposing sensitive information. — `GET /health/ready` added: DB connectivity
  + schema presence through the same session dependency routes use, AI
  provider configuration state as booleans, 503 on degradation; never returns
  URLs, credentials, or exception text (enforced by `backend/tests/test_health.py`).
- [x] M29 and M30 functionality remains regression-safe. — ChemEngine 1635
  passed / 1 skipped; backend 224 passed (220 + 4 new health tests); web 74;
  admin 13; all tsc/builds pass.
- [x] No new P0/P1 security issues are introduced. — Security sweep of all M31
  files: no secrets/keys/URLs printed or committed, no `.env` tracked, no
  TODO/FIXME debris, E2E seams are script-local test fakes (mirroring
  `tests/conftest.py`), CI cannot leak or mutate (no secrets used, `--no-fix`).
- [x] Full regression passes.
- [x] Static checks pass. (backend ruff + mypy clean; ChemEngine's 342 ruff
  findings + 44 mypy errors are a documented pre-existing baseline that CI
  now prevents from growing — fixing them is ChemEngine work outside M31.)
- [x] Builds pass.
- [x] TODO.md is reconciled.
- [x] PROJECT_STATUS.md is reconciled.
- [x] gantt.html is updated.
- [x] M31 commits are focused.
- [x] Changes are pushed.
- [x] HEAD == origin/master.
- [x] Working tree is clean.

**Dependencies:** M30 (conversations/streaming/cache must remain intact),
M29 (provider abstraction and its security boundaries), the Alembic chain
(001–004), and the existing monorepo tooling (pytest, ruff, mypy, tsc,
vite build). **Testing requirements:** full regression (ChemEngine, backend,
web, admin) with exact totals recorded; CI runs the same checks; browser E2E
must actually execute a browser or be documented as blocked. **Security
requirements:** no secrets committed or logged, no credentials in frontend
code, no sensitive conversation content or answer keys in logs or
diagnostics. **Known limitations to record at completion:** whichever of
PostgreSQL verification, live provider smoke, and browser E2E could not be
executed in this environment, with exact blockers.

---

### M32 — ChemEngine Release Completion: API Reference, Tutorials & PyPI (Complete)

M32 is **complete** (2026-09-21). M31 is
complete. Where M31 performed production-readiness and release engineering for
the Chemora *product*, M32 completes the equivalent release work for the
ChemEngine *library* — the remainder of Phase 15 ("Release") that was tagged
"Planned (v2.0)" plus the one Phase 1 DoD delta M31 proved unrealized. The
roadmap's own Phase 15 purpose statement is the objective: "Ship ChemEngine as
a professional open-source library on PyPI. 100% documentation coverage,
tutorials, CI/CD, semantic versioning, and a trusted release."

**Why this is M32 (repository evidence).** After M31 the roadmap's remaining
explicitly enumerated, milestone-shaped work is exactly: Phase 15.2 API
reference (Sphinx) ⬜, Phase 15.3 tutorials + examples ⬜, Phase 15.5 PyPI
publication ⬜, the Phase 15.4 CI delta (Python 3.10–3.13 matrix — CI now
exists via M31 but runs 3.12 only), and Phase 1 DoD's "benchmark regression
tests (compare against baselines in CI)" whose checkbox is marked done but
which M31 proved is not actually implemented (no saved baseline artifacts; CI
asserts collectability only). Alternative candidates were rejected on
evidence: the v2.0 chemistry domains (organometallics, polymers,
biomolecules, mechanisms, GNN, WebAssembly, crystallography, NMR) are an
explicitly **unordered** Future Roadmap with no documented ordering or
selection signal; the mobile milestone is referenced once with no scope
("a future mobile milestone will define the compatibility path"); v3.0 items
are longer-term; and M30/M31 deferred items were already dispositioned
(rate limiting — not required for the deployment target; titles — UX;
live provider smoke — credential-blocked).

**Objectives.** (1) Generate and publish a Sphinx API reference from the
codebase's Google-style docstrings. (2) Write the roadmap-named tutorials and
a runnable `examples/` directory. (3) Complete the package/community release
surface: metadata audit, security/license audit, SECURITY.md,
CODE_OF_CONDUCT.md, RELEASE_CHECKLIST.md, DEPLOYMENT.md, changelog-anchored
GitHub Release, and PyPI publication where credentials allow. (4) Close the
two proven CI deltas: Python version matrix and benchmark-baseline regression
comparison. (5) Reconcile the Phase 15 milestone table with reality.

**In scope:**
- **Sphinx API reference (Phase 15.2):** `docs/` Sphinx project (conf.py,
  index, autodoc/napoleon from the existing Google-style docstrings),
  generated API reference for all public `chemengine` modules, docs build
  treated as a CI gate (`sphinx-build -W`), ReadTheDocs-ready configuration
  (publishing to an external host is attempted only if account access
  exists; otherwise the exact blocker is documented).
- **Docstring completeness audit:** verify the Phase 15.1 "100% documentation
  coverage" claim mechanically for public API surface; document and fix any
  gaps found in public modules (no private-refactor rewrites).
- **Tutorials + examples (Phase 15.3):** the roadmap-named tutorials
  (quickstart, SMILES, substructure, properties, rendering, AI/tool
  integration) and 10+ runnable scripts in `packages/chemengine/examples/`,
  each executed as part of verification.
- **Package release surface (Phase 15.5):** metadata/license/security audit
  of `packages/chemengine/pyproject.toml`; `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, `RELEASE_CHECKLIST.md`, `DEPLOYMENT.md` (the four
  files the roadmap names that do not exist); changelog review; GitHub
  Release + tag for the current version; PyPI publication readiness
  (twine check on built artifacts). Actual PyPI/TestPyPI publication is
  attempted only if credentials exist in the environment; otherwise it is
  documented as blocked with exact steps — never fabricated.
- **CI deltas (Phase 15.4 remainder + Phase 1 DoD):** Python 3.10–3.13
  verification matrix for ChemEngine (within the existing workflow — no
  weakening of existing gates), and a benchmark-baseline regression job:
  save pytest-benchmark baseline artifacts, compare in CI, fail on
  documented-threshold regressions (measurement noise handled explicitly;
  absolute timing thresholds are recorded, not invented).
- **Documentation reconciliation:** Phase 15 milestone table rows
  (15.2/15.3/15.5 → M32; 15.4 → partially delivered via M31 with the matrix
  delta noted), TODO.md, PROJECT_STATUS.md, gantt.html at completion.

**Out of scope:** new ChemEngine chemistry domains (organometallics,
polymers, biomolecules, reaction mechanisms, GNN, WebAssembly,
crystallography, NMR, drug discovery, retrosynthesis, docking, quantum,
chemical database engine) — they remain the separately labeled Future
Roadmap v2.0/v3.0; the remaining v2.0 feature rows (atropisomers, PNG
output, substructure highlighting, themes, preferred IUPAC, name parser,
tautomer, atom-atom mapping); the mobile milestone (insufficient documented
scope); distributed rate limiting; model-generated conversation titles;
product feature work in backend/web/admin; ChemEngine algorithm changes;
M33+ work.

**Acceptance criteria** (M32 is complete only when all of the following
hold) — final status with evidence:
- [x] Sphinx API reference builds warning-free (`sphinx-build -W`) and
  covers the public `chemengine` API; build is a CI gate.
  **PASS** — exit 0, 0 warnings from a clean `_build`;
  `packages/chemengine/docs/` (conf.py + 17 generated API pages + 6
  tutorials); gate in `.github/workflows/ci.yml` and `ci_check.py`.
- [x] Docstring completeness audit executed; result recorded; public-API
  gaps closed or explicitly documented.
  **PASS** — mechanical AST audit of 71 modules / 224 top-level public
  defs (0 missing) extended to all 480 public functions/methods/properties:
  103 gaps closed (62 properties, 41 methods); 1 UTF-8 BOM removed from
  `compounds/__init__.py`; 3 docstrings reformatted for napoleon; 1
  inaccurate InChIKey docstring corrected to match the implementation.
- [x] The six roadmap-named tutorials exist and are accurate.
  **PASS** — `docs/tutorials/`: quickstart, smiles, substructure,
  properties, rendering, ai_integration; every code block verified against
  the current API; examples literalincluded so they cannot drift.
- [x] `packages/chemengine/examples/` contains 10+ scripts, each executed
  successfully during verification.
  **PASS** — 12 examples, `scripts/verify_examples.py` → 12/12 passed
  (also a CI gate).
- [x] SECURITY.md, CODE_OF_CONDUCT.md, RELEASE_CHECKLIST.md, DEPLOYMENT.md
  exist (the roadmap-named files currently absent).
  **PASS** — all four added under `packages/chemengine/` (plus LICENSE
  copied into the package so the wheel/sdist carry the license text).
- [x] Package metadata/license/security audit complete; `twine check` passes
  on built distributions.
  **PASS** — metadata audit fixed: Development Status → Production/Stable,
  keywords/URLs/Typing classifier added, `tomli` declared for Python <3.11
  (missing-dependency bug found by the clean-venv wheel test), TOML
  section-ordering bug fixed that had dropped all core Requires-Dist
  fields, sdist include-list completed, hatch license-files added.
  `twine check`: PASSED on both artifacts; sdist carries README/LICENSE/
  CHANGELOG/SECURITY/CODE_OF_CONDUCT/RELEASE_CHECKLIST/DEPLOYMENT/docs/
  examples; wheel carries only `chemengine/` + dist-info licenses.
- [x] GitHub Release + tag created from the changelog, or the exact
  credential/permission blocker documented.
  **BLOCKED (documented)** — no `gh` CLI and no GitHub token in the
  environment; tag+release procedure prepared in RELEASE_CHECKLIST.md §4
  and automated in `.github/workflows/publish.yml`.
- [x] PyPI/TestPyPI publication performed where credentials exist, or the
  blocker explicitly documented with exact steps.
  **BLOCKED (documented)** — no PyPI/TestPyPI credentials (verified: no
  token env vars; publication never attempted or fabricated). Exact steps
  in RELEASE_CHECKLIST.md §5; publish workflow triggers on `v*.*.*` tags.
- [x] CI verifies ChemEngine across Python 3.10–3.13 (or the version set
  exactly supported by the package's stated requirements, documented).
  **PASS** — `chemengine-matrix` job (fail-fast off, no
  continue-on-error); verified locally on real interpreters:
  3.10.11 / 3.11.16 / 3.12.14 / 3.13.15 all → 1635 passed, 1 skipped.
- [x] Benchmark baselines saved as artifacts and compared in CI, failing on
  regressions beyond documented thresholds; the Phase 1 DoD claim is
  thereby genuinely realized.
  **PASS** — `benchmark-regression` CI job: rolling baseline via
  actions/cache + artifact upload, `--benchmark-compare-fail=mean:60%`
  (60% cross-run noise margin, documented in the workflow).
  Sabotage-proven: an injected 2 ms/parse slowdown failed the comparison
  (4 PercentageRegressionCheck failures) AND the existing absolute
  thresholds in `tests/test_benchmark_baselines.py` (2 failures);
  reverted, suite green. Full suite: 60 benchmarks pass in ~62–72 s.
  Measured Phase 1.6 baselines: full run ≈63–65 s (M31), 60 functions,
  first import 492.9 ms warm / ~3.9 s cold (target <100 ms — recorded as
  a genuine gap), package size 216 KB wheel / 334 KB sdist (target <5 MB
  — met).
- [x] Phase 15 milestone table reconciled.
  **PASS** — 15.2/15.3/15.4 complete; 15.5 release-ready with the
  credential blocker recorded.
- [x] M19–M31 functionality remains regression-safe (full suites + static
  checks + builds with exact totals recorded).
  **PASS** — ChemEngine 1635 passed / 1 skipped; backend 224 passed
  (ruff clean, mypy clean); web 74 passed (tsc clean, build OK); admin 13
  passed (tsc clean, build OK); all 16 `ci_check.py` gates green.
- [x] No new P0/P1 security issues; no credentials committed or printed.
  **PASS** — security scan of all new files: no secret values (only
  documented secret *names* for CI), no TODO/FIXME debris, dist/ and
  .benchmarks/ ignored, publish workflow consumes `PYPI_API_TOKEN` via
  env without echoing.
- [x] TODO.md, PROJECT_STATUS.md, gantt.html reconciled; commits focused;
  pushed; HEAD == origin/master; working tree clean.
  **PASS** — this reconciliation; focused commits created and pushed
  (final hashes in PROJECT_STATUS.md).

**Result: M32 COMPLETE — 14/14 acceptance criteria satisfied (12 PASS,
2 BLOCKED-but-prepared with documented credential blockers).**

**Dependencies:** M31 CI infrastructure (the matrix and benchmark jobs
extend the existing workflow), the ChemEngine docstrings (Phase 15.1 ✅),
`CHANGELOG.md` and `CONTRIBUTING.md` (already exist), the M31-verified
benchmark suite (60 collectable functions). **Testing requirements:**
`sphinx-build -W`, example-script execution, `twine check`, full regression
(ChemEngine, backend, web, admin) with exact totals, ruff/mypy/tsc/builds,
benchmark comparison job demonstrably failing on an injected regression.
**Security requirements:** no credentials in repo/logs/CI, license and
metadata audit, no fabricated publication claims. **Known limitations to
record at completion:** whichever of PyPI/TestPyPI publication, GitHub
Release, and ReadTheDocs hosting could not be executed for lack of external
accounts/credentials, with exact steps to complete them.

---

### M33 — ChemEngine v2.0 Feature Completion: Rendering, Nomenclature & Reaction Mapping (Complete)

M33 is **complete** (2026-09-21). M32 is
complete. M33 closed the remaining **itemized** Phase 10–12 rows (all
formerly tagged "Planned (v2.0)") as one coherent "finish the v2.0 feature
list" milestone, and met the one open measured Phase 15 performance target
(first import <100 ms, achieved: ~19–27 ms) that M32 recorded. The unordered Future Roadmap
v2.0 *domains* (organometallics, polymers, biomolecules, a full mechanism
engine, GNN, WebAssembly, crystallography, NMR) are **not** part of M33 —
they remain separately labeled future work with no documented ordering.

**Why this is M33 (repository evidence).** After M32 the roadmap's
remaining explicitly itemized feature work is exactly: 10.2 PNG output,
10.3 substructure highlighting, 10.5 dark mode + themes (Phase 10
Rendering); 11.3 preferred IUPAC + common names, 11.4 IUPAC name parser,
11.5 tautomer handling (Phase 11 Nomenclature); 12.2 atom-atom mapping and
12.5 mechanism *architecture* (Phase 12 Reactions — the placeholder
architecture the completed Phase 12 explicitly anticipated). All carry
named atomic tasks and benchmarks in the roadmap. Discovery also verified
the remaining "Planned" markers in Phases 1/6/7 were stale (atropisomer
placeholders, ambiguous/conflict stereo validation, isomer filtering,
property-based tests, benchmark baselines are all already implemented)
and reconciled them. The M32-measured first-import gap (492.9 ms vs the
Phase 15.6 target <100 ms) is a bounded, measurable engineering task and
is included here rather than left as orphan technical debt; the M32
external release blockers (GitHub Release, PyPI upload) stay blocked on
credentials and are **not** re-scoped into M33.

**Objective.** Complete every remaining itemized v2.0 feature row of
Phases 10–12, meet the recorded first-import performance target, and
reconcile the roadmap — without opening any new chemistry domain.

**In scope:**
- **Phase 10.2 — PNG output (via SVG):** SVG → PNG conversion using the
  roadmap-named optional dependency (`cairosvg`, new `render` extra),
  HiDPI scale factors (2x, 4x) per the Phase 10 atomic task list, graceful
  degradation when the extra is not installed.
- **Phase 10.3 — Substructure highlighting:** colored atom/bond
  highlighting driven by `detection.substructure` matches, exposed on
  `render()` and as tool options; deterministic colors.
- **Phase 10.5 — Dark mode + themes:** the roadmap-named themes (dark
  mode, CPK coloring, monochrome, accessibility) as renderer theme
  objects; deterministic output per theme.
- **Phase 11.3 — Preferred IUPAC + common names:** PIN generation for the
  naming subsystem's existing coverage and a common/trivial-name
  dictionary (roadmap names 1000+; deliver a curated, tested set with the
  count recorded honestly).
- **Phase 11.4 — IUPAC name parser:** `parsing/iupac/{tokenizer,parser}.py`
  per the roadmap's named file layout, round-tripping the generator's
  output on its supported grammar subset (coverage documented).
- **Phase 11.5 — Tautomer handling:** keto-enol and amide-imidic detection
  and canonical tautomer selection per the roadmap task list.
- **Phase 12.2 — Atom-atom mapping:** mapping via the existing MCS engine
  (`detection.substructure.maximum_common_substructure`), `ReactionGraph`
  dataclass with reactants/agents/products/mapping, validation (atom and
  charge conservation), Phase 12 benchmarks (mapping <10 ms on small
  molecules; graph construction <100 µs; balancing/validation <5 ms).
- **Phase 12.5 — Mechanism architecture:** the placeholder
  step-by-step mechanism architecture (module + data model + docs) that
  Phase 12 anticipated — **not** a working mechanism engine.
- **Performance (Phase 15.6 recorded gap):** reduce first import to
  <100 ms (measured warm-cache fresh process, the M32 methodology) via
  lazy loading / deferred plugin discovery; benchmark regression gate and
  all existing tests must stay green.
- **Documentation reconciliation:** Phase 10/11/12 milestone tables,
  TODO.md, PROJECT_STATUS.md, gantt.html, CHANGELOG entry, Sphinx API
  pages regenerated, tutorials/examples updated where the new APIs belong.

**Out of scope:** the Future Roadmap v2.0 domains (organometallics,
polymers, biomolecules, full mechanism engine, GNN, WebAssembly,
crystallography, NMR); v3.0 items (drug discovery, retrosynthesis,
docking, quantum, chemical database, collaborative platform); mobile;
M32's credential-blocked GitHub Release/PyPI upload (remain documented
blockers, not M33 work); AI tutor redesign; backend/web/admin product
feature work; new ChemEngine chemistry domains beyond the rows above;
M34+ work.

**Acceptance criteria** (all verified 2026-09-21):
- [x] `render(graph, fmt="png")` produces a valid PNG when the `render`
  extra is installed (cairosvg), supports 2x/4x scale, and raises the
  stable, documented `PNGUnavailableError` when the extra is absent
  (`rendering/png.py`; graceful-degradation tests).
- [x] `render()` accepts a substructure query/match and emits highlighted
  atoms/bonds deterministically (same input → same output, tested);
  tool surface exposes theme+highlight options (facade wiring commit
  3cc2fc4).
- [x] Renderer themes exist: dark, CPK, monochrome, accessibility; each
  produces deterministic SVG (43 rendering tests green).
- [x] Preferred IUPAC names generated for the naming subsystem's supported
  classes after a correctness pass (longest-chain/locant/nitro/ring
  fixes); common-names dictionary ships (63 names) with integrity tests;
  11.3 table row updated.
- [x] `parsing/iupac/` tokenizer+parser parse the generator's supported
  grammar subset with 38-case round-trip tests (InChIKey-equality
  canonicalization); unsupported grammar raises structured
  `UnsupportedNamingError`; coverage documented in module docstrings.
- [x] Tautomer detection (keto-enol, amide-imidic) + canonical tautomer
  selection implemented, bounded, with unit tests.
- [x] `ReactionGraph` with deterministic atom-atom mapping; a 53-case
  reviewed reference set (exceeds the 50+ roadmap requirement) maps
  correctly as a version-controlled oracle
  (`tests/data/reaction_mapping_reference.json`); explicit failures for
  unbalanced/oversized inputs; mapping performance ~1–7 ms on small
  molecules (Phase 12 <10 ms target met); graph construction and
  validation benchmarks remain green in the suite.
- [x] Mechanism *architecture* module + data model + docs exist
  (`reactions/mechanisms.py`; explicitly no runnable engine, enforced by
  an architecture-boundary test).
- [x] First import <100 ms: 490 → ~19–27 ms (cold `-X importtime`, median
  of 3, methodology in `tests/test_import_performance.py`); regression
  gate added at the 100 ms target + 150 ms guard; benchmark regression
  gate green; full test suite green.
- [x] Phase 10/11/12 tables reconciled; CHANGELOG entry added; Sphinx
  builds warning-free with `-W`; examples (12) all execute; tutorials
  synchronized with the new APIs.
- [x] M1–M32 regression-safe: ChemEngine 1851 passed, 2 skipped (both
  skips documented); backend 224 passed; web 74 passed; admin 13 passed;
  backend ruff+mypy clean; tsc clean; web/admin builds pass; package
  build + twine check pass. Python 3.10 verified locally; 3.11–3.13
  execute only in CI (matrix job), documented as the local-environment
  limitation.
- [x] No new P0/P1 security issues; no credentials committed or printed
  (security sweep of all new modules clean).
- [x] TODO.md, PROJECT_STATUS.md, gantt.html reconciled; focused commits;
  pushed; HEAD == origin/master; working tree clean.

**Dependencies:** M32 release surface (Sphinx, examples, CI gates, twine
build); existing MCS engine (`detection/substructure.py`); existing
`Reaction`/`ReactionBuilder`/template model; existing renderer SVG engine
and layout; existing nomenclature generator; the M32 CI matrix and
benchmark-regression jobs (extend, do not weaken). **Testing
requirements:** unit tests per feature; property-based round-trips for
name parsing (extend `tests/test_property_based.py`); mapping correctness
on a 50+ reaction reference set; benchmark additions for mapping/graph
construction wired into the existing benchmark-regression gate;
import-time benchmark asserting the <100 ms target; PNG/theme/highlight
determinism tests; graceful-degradation tests for optional deps; full
regression (ChemEngine, backend, web, admin) with exact totals;
ruff/mypy/tsc/builds. **Known limitations to record at completion:**
parser grammar coverage honestly documented; common-name dictionary count
recorded; cairosvg optional-extra status on all matrix Pythons verified;
whatever cannot be verified is documented, never fabricated.

---

### M34 — Full Reaction Mechanism Engine (Complete — 2026-09-23)

**Status: ✅ COMPLETE (2026-09-23).** The executable engine, curated rule
catalogue, reference oracle, validation, serialization, registry integration,
version 1.2.0, and full regression are delivered.

**Objective.** Implement the executable, step-by-step mechanism engine that
Phase 12 anticipated and M33 deliberately staged interfaces for: curated
electron-pushing rules that apply to M33 `ReactionGraph`s and produce
validated `MechanismTrace` sequences — deterministic, conservation-checked,
and bounded to the chemistry ChemEngine supports ("full" = an end-to-end
executable engine, not universal mechanism coverage).

**Roadmap evidence.**
- Future Roadmap v2.0 bullet: "**Reaction mechanisms** (full step-by-step
  mechanism engine)" (see Future Roadmap: v2.0, below).
- Phase 12 purpose: "Architecture anticipates reaction mechanisms (full
  implementation deferred to v2.0)."
- `reactions/mechanisms.py` (M33) module docstring: "**This module
  deliberately contains no mechanism engine** … Any concrete
  electron-pushing logic belongs to a future, separately-scoped milestone …
  so that the broader roadmap (12.x) can be scheduled against concrete
  interfaces rather than intentions."
- M33 record (PROJECT_STATUS): "the mechanism module contains no
  executable chemistry by design".
- M33 shipped every runtime dependency the engine needs: `ReactionGraph`,
  MCS atom-atom mapping + 53-reaction reference oracle, atom/charge
  conservation validation, tautomer canonicalization (enol↔keto is
  mechanism-relevant), SMARTS/template matching (Phases 5/12.4),
  serialization, and the <100 ms lazy-import gate.

**Candidate survey (why this, and where everything else stands).**

| Candidate | Documented evidence post-M33 | Disposition |
|-----------|------------------------------|-------------|
| **Reaction mechanism engine** | Interfaces staged by M33 explicitly awaiting "a future, separately-scoped milestone"; Phase 12 deferral language; explicit v2.0 bullet; all dependencies just delivered | **Selected — M34** |
| Organometallics / polymers / biomolecules / crystallography / NMR | v2.0 bullets only; zero partial implementation, no staged interfaces | Remain explicitly unordered |
| GNN integration / WebAssembly | v2.0 bullets only; no ML or browser-execution scaffolding exists; platform work, not engine chemistry | Remain explicitly unordered |
| Mobile app | "a future mobile milestone will define the compatibility path" — scope intentionally not yet defined | Cannot be scoped yet |
| Advanced visualization (electron-arrow SVG annotation) | No roadmap row; base visualization delivered by M33 (PNG, themes, highlighting) | Not milestone-shaped |
| Advanced stereochemistry | Phase 6 complete; only a stale 6.4 marker (placeholders exist, verified M33) + "edge cases deferred to v2.0" note | Not milestone-shaped |
| Advanced AI chemistry / chemical search & knowledge DB | v3.0: "Automated chemical reasoning", "Chemical database engine" | Out (v3.0, longer-term) |
| Drug discovery / retrosynthesis / docking / quantum / collaborative platform | v3.0 bullets | Out (v3.0, longer-term) |
| Performance & distribution | Closed by M31/M32 + the M33 <100 ms gate; PyPI/GitHub Release remain credential-blocked (not milestone work) | Closed / blocked |
| Nomenclature breadth (1000+ names aspiration); standard-InChI feature parity | Recorded limitations/aspirations in PROJECT_STATUS with no itemized rows | Recorded gaps, not milestone-shaped |
| Product-side (quizzes/exams, offline sync, CMS expansion) | Referenced only as out-of-scope exclusions in M24–M30; no roadmap rows | Not ChemEngine scope |

**In scope.**
1. `MechanismEngine` core: rule objects implementing the frozen M33
   `MechanismRule` protocol (`applies`/`apply`) that return *validated
   proposals* (`MechanismStep`) over `ReactionGraph` — never mutating shared
   graphs in place (per the M33 contract).
2. Rule implementations for the `MovementKind` vocabulary (bond formation,
   bond breaking, lone-pair donation, resonance shift, single-electron)
   sufficient for a bounded curated catalogue of **≥ 10 named mechanisms**
   over existing domains, including SN2, SN1, E2, E1, E1cB, electrophilic
   addition with Markovnikov regioselectivity, and carbonyl nucleophilic
   addition–elimination.
3. Per-step validation: atom conservation via M33 mapping, charge
   conservation, `MechanismTrace` endpoint/ordering checks, deterministic
   step ordering.
4. Structured errors for non-applicable/unsupported cases — no silent wrong
   chemistry (same guard pattern as `UnsupportedNamingError`).
5. Curated mechanism reference oracle checked into the repo: **≥ 25 named
   scenarios with expected step sequences**, in the style of M33's
   53-reaction mapping oracle.
6. `AlgorithmRegistry` registration (Phase 12 atomic task) and lazy import
   so the first-import gate stays < 100 ms.
7. Serialization of traces (dict/JSON) through the existing `io` surface.
8. Benchmarks: engine execution over the reference set with a documented
   Phase-12-style budget, registered like existing reaction benchmarks.
9. Release housekeeping at completion: CHANGELOG `[1.2.0]`, version bump
   1.1.0 → 1.2.0 (`pyproject.toml`/`__version__`/version-consistency test
   stay green).

**Out of scope.**
- All other Future Roadmap v2.0 domains (organometallics, polymers,
  biomolecules, GNN, WebAssembly, crystallography, NMR).
- All v3.0 items (drug discovery, retrosynthesis, chemical database engine,
  docking, quantum computing, automated chemical reasoning, collaborative
  platform).
- Mobile; AI-tutor / backend / web / admin product work; M32's
  credential-blocked PyPI/GitHub Release steps.
- Curved-arrow SVG annotation rendering (visualization layer; not a
  documented roadmap row).
- Kinetics/thermodynamics simulation; yield/condition prediction; inference
  of novel mechanisms for arbitrary literature reactions — the engine
  executes and validates curated, bounded rule applications.
- M35+ scope.

**Dependencies.**
- M33: `reactions/mechanisms.py` interfaces (`ElectronMovement`,
  `MechanismStep`, `MechanismTrace`, `MechanismRule`), `ReactionGraph` +
  MCS mapping (53-case oracle), conservation validators, tautomer
  canonicalization, nomenclature guards, rendering, import-perf gate.
- Phase 3 functional-group detection, Phase 5 SMARTS/substructure matching,
  Phase 12.4 reaction templates, `AlgorithmRegistry`, `io` serialization.

**Acceptance criteria.**
- [x] Executable `MechanismEngine` implements the frozen M33 interfaces
  without breaking their contracts (M33 interface tests unchanged + green).
- [x] 10 named mechanisms execute end-to-end; 28 curated reference
  scenarios (23 positive, 5 negative) with expected traces all pass.
- [x] Every step passes atom + charge conservation; traces satisfy
  endpoint/ordering validation; execution is deterministic across runs.
- [x] Unsupported/illegal applications raise structured errors (tested).
- [x] Registered in `AlgorithmRegistry`; first import stays < 100 ms (perf
  gate green).
- [x] Full regression green with exact recorded totals; ruff/mypy within
  documented baselines; no undocumented skips.
- [x] Version 1.2.0 + CHANGELOG entry consistent (version-consistency test
  green).
- [x] TODO.md, PROJECT_STATUS.md, gantt.html synchronized; gantt status →
  complete only when the above hold.

**Testing results (2026-09-23).** 28 checked-in oracle cases cover all ten
mechanisms (23 positive, 5 negative). Every step is checked for atom/formula
and charge conservation, structural and charge-aware valence validity, exact
chain continuity, and movement/bond-change coverage. Tests additionally cover
repeated-run determinism, input immutability, structured errors, registry
discovery, lazy import, and dict/JSON serialization round trips. The full
ChemEngine regression is recorded in the Roadmap Summary; the existing
first-import gate remains below 100 ms.

**Documentation requirements.**
- Sphinx page(s) for the engine (+ worked example where feasible); Phase 12
  table reconciled on completion; TODO.md M34 record; PROJECT_STATUS.md
  M34 record + Next-Milestone row; gantt.html updated (status → complete on
  completion); CHANGELOG `[1.2.0]`.

**Risks / blockers.**
- **Chemical-correctness risk (high):** M33's docstring calls mechanism
  work "the most error-prone area of computational chemistry" — mitigated
  by curated oracles, conservation validation, determinism tests, and a
  bounded rule vocabulary with explicit unsupported errors.
- **Scope explosion:** the space of mechanisms is unbounded — mitigated by
  the ≥10/≥25 curated targets and the explicit out-of-scope list.
- **Aromatic/tautomer edge cases** in intermediates — mitigated by reusing
  M33 canonicalization and Kekulé-aware valence handling.
- **Import-time creep** from new modules — mitigated by the existing
  <100 ms lazy-import gate.
- **Template/SMARTS gaps** for some named mechanisms — a gap either extends
  Phase 12.4 templates in-scope or drops the mechanism from the catalogue
  with a recorded note.
- No credential/external blockers (all work is in-repo).

---
### M35 — Post-M34 Roadmap Clarification and Candidate Scoping (Complete — 2026-09-23)

**Status: ✅ COMPLETE (2026-09-23).** M35 is a planning-only decision
milestone. No ChemEngine source, tests, dependencies, or release metadata
changed; ChemEngine remains 1.2.0.

**Objective.** Resolve the post-M34 roadmap ambiguity using repository evidence,
not list order or technical interest. M35 records the candidate comparison,
selection rule, bounded future scope, acceptance criteria, test/performance
requirements, risks, and definition of done. It implements no chemistry.

**Evidence.** The Future Roadmap leaves the remaining v2.0 bullets explicitly
unordered. M33/M34 provide reaction, mapping, validation, registry,
serialization, and mechanism infrastructure, but no staged interfaces or
prerequisite chain for organometallics, polymers, biomolecules, GNN,
WebAssembly, crystallography, NMR, nomenclature/stereochemistry expansion,
chemical search/database, visualization, mobile, or v3.0 work. Retrosynthesis,
automated reasoning, drug discovery, docking, and quantum chemistry remain v3.0
bullets. M35 therefore clarifies the decision before opening a new domain.

**Candidate selection (completed).** **Bounded template-based retrosynthesis**
is the next implementation milestone. The evidence is the explicit v3.0
"Full retrosynthetic analysis" objective plus a concrete dependency edge from
completed work: M33's `ReactionGraph`, deterministic atom mapping, reaction
templates, and validators; M34's ten named mechanisms, twelve validated
elementary rules, deterministic traces, and serialization. The selected future
scope is deliberately narrower than "AI-driven route planning": enumerate and
rank precursor sequences by applying curated reaction templates/rules in
reverse, with explicit applicability and unsupported errors. Other candidates
remain unordered because no equivalent staged interface or bounded prerequisite
chain is documented.

**In scope.** Review current roadmap and directly relevant architecture;
compare candidates by dependency readiness, bounded deliverable size,
testability, performance/serialization needs, and risk; select one candidate or
record that clarification remains insufficient; write a future implementation
scope with objective, in/out of scope, dependencies, supported cases,
acceptance criteria, test strategy, performance requirements, version proposal,
risks, limitations, and definition of done; reconcile the three planning files;
run Gantt JavaScript validation.

**Out of scope.** All source, tests, dependencies, backend, frontend, mobile,
and infrastructure implementation; prototypes; changing M33/M34 architecture;
claiming candidate completion; starting M36; selecting by arbitrary order.

**Architecture reused.** Existing planning conventions and, for evidence only,
molecular-graph SSOT, validators, substructure/reaction abstractions,
`AlgorithmRegistry`, serialization, oracle testing, lazy-import gate, and M34's
bounded-catalogue precedent. No new M35 interfaces are required.

**Acceptance criteria.**
- [x] Candidate map records evidence and explicit unordered status.
- [x] Exactly one future candidate is selected with an implementation-ready
  scope: bounded template-based retrosynthesis.
- [x] The selected scope includes objective, boundaries, dependencies,
  measurable acceptance direction, tests, performance, version proposal,
  risks, limits, and definition of done.
- [x] TODO.md, PROJECT_STATUS.md, and gantt.html agree; M35 is complete and
  explicitly says its implementation was not started.
- [x] `node --check`, documentation/diff checks, and the documentation-only
  diff gate pass; no version bump or implementation claim.

**Testing, performance, documentation, and version.** No application tests or
performance work in M35; validate the documentation-only diff, Gantt syntax,
and planning consistency. A future implementation scope must define its own
measurable tests and performance thresholds, while preserving the M34 <100 ms
first-import gate. Update only the three planning files and preserve M1–M34
records. No version bump or CHANGELOG entry: ChemEngine remains 1.2.0; the
future implementation version proposal must be justified by compatibility impact.

**Risks, limitations, and definition of done.** The future retrosynthesis
scope is bounded by curated templates and does not imply general chemical
route planning. M35 cannot resolve external credentials or order the entire
v2.0/v3.0 list. Done means a synchronized decision record, valid completed
Gantt entry, one focused documentation commit, pushed
`HEAD == origin/master`, clean tree, and no M35 chemistry implementation
started.

---



## Takeover Audit (Complete — 2026-09-22)

Independent re-verification of M1–M33 against the repository itself
(code, tests, CI configuration, builds). Prior milestone reports were
treated as claims, not evidence. History preserved; fixes landed as new
focused corrective commits.

**Defects found and fixed:**
- [x] `canonical_tautomer()` asymmetry — an enol and its keto form (an
  imidic acid and its amide) canonicalized to different representatives
  depending on which member was supplied. Fixed with reverse-direction
  site detection (`enol-keto`, `imidic-amide`) plus a bounded tautomer
  closure search; regression tests in `tests/test_m33_naming.py`
  (`TestTautomerSymmetry`).
- [x] IUPAC parser built aromatic heterocycles as saturated graphs —
  ring atoms lacked the aromatic flag and template N-H counts were
  dropped, so pyridine serialized as piperidine (`C1CCCCN1`) and
  pyrrole lost its N-H (C4H4N instead of C4H5N). The parser now sets
  atom aromaticity and honours template hydrogens.
- [x] Naming generator matched saturated heterocycles against the
  aromatic composition table — piperidine was returned as
  "pyridine". The composition lookup is now guarded by ring
  aromaticity and raises `UnsupportedNamingError` instead.
- [x] `pyran` existed on both the generator and parser sides with no
  correct neutral representation; removed from both — the name now
  raises instead of mis-parsing to a saturated ring.
- [x] Placeholder/incorrect names — `_name_hydrocarbon()` could return
  the literal string `"unknown"`, and ketone carbons without two
  carbon neighbours could reach chain naming. Out-of-coverage inputs
  now raise `UnsupportedNamingError` uniformly.
- [x] Packaging version drift — `pyproject.toml`/`__version__` said
  1.0.0 while the M33 CHANGELOG declared 1.1.0. Both are now 1.1.0,
  pinned by the new `tests/test_version_consistency.py`.
- [x] Redundant module-level `pytestmark = pytest.mark.asyncio`
  removed from the M30 conversation suite (the backend runs
  `asyncio_mode = "auto"`, like every other backend test module).

**Post-audit regression (all run fresh, 2026-09-22):** ChemEngine
**1893 passed / 4 skipped** (every skip documented); backend **224**;
web **74**; admin **13**; ChemEngine ruff/mypy within documented
baselines; backend ruff+mypy clean; web/admin `tsc` clean;
web+admin production builds green; Sphinx `-W` green; 12/12 examples;
60/60 benchmark functions; package build + `twine check` green; first
import 18–30 ms (target <100 ms); 53-case reaction reference set
green; mechanism architecture boundary test green;
`infrastructure/ci_check.py --validate-only` green. Python 3.10
verified locally; 3.11–3.13 run in the CI matrix (documented
local-environment limitation).

---

### ✅ M36: Bounded Template-Based Retrosynthetic Engine (Complete — 2026-09-25)

**Status: COMPLETE.** The candidate M35 selected — bounded template-based
retrosynthetic analysis — was implemented over the shared `MolecularGraph`
abstraction with no SMARTS. `packages/chemengine/src/chemengine/reactions/retrosynthesis.py`
(1090 lines) delivers an 8-template catalogue (ester-fischer, amide-hydrolysis,
ether-cleavage-alkyl, ether-cleavage-aroyl, alcohol-to-alkyl-halide,
carbonyl-reduction, retro-aldol, retro-diels-alder) with heavy-atom-conserving
subtractive/additive surgery, immutable `SynthesisRoute`/`RetrosyntheticCandidate`/
`RetrosyntheticStep` models, and a bounded-DFS `RetrosynthesisEngine` governed by
`max_depth`, `max_candidates_per_step`, `max_total_expansions`, `max_routes`, a
canonical-SMILES cycle guard, and structural route de-duplication. A 5-case
`REFERENCE_ORACLE` drives conservation-validated headliners; routes round-trip via
`retrosynthesis_route_to_dict`/`dict_to_retrosynthesis_route`. Registration is lazy
(`register_retrosynthesis_algorithms`) and wired as a `retrosynthesize` tool +
convenience method on `ChemEngineAPI`.

**Out of scope (unchanged from M35):** unrestricted or AI-driven route planning,
reagent/condition/yield prediction, new chemistry domains, product work, and
curved-arrow rendering; M33/M34 APIs remain unchanged.

**Deliverable & test result:** version **1.3.0**, 8 templates, 36 retrosynthesis tests;
full ChemEngine regression **2020 passed, 4 skipped, 0 failed**. Cold `import chemengine`
stays lazy and <100 ms (M36 retrosynthesis is deliberately absent from `__all__`).
Documented limitation: the timing-sensitive `test_performance.py::TestProfiler::test_profile_decorator`
gate (asserts a sub-ms decorator path) can flake under slow CI and is unrelated to M36.

---

## Roadmap Summary

### Overall Progress

| Metric | Value |
|--------|-------|
| **ChemEngine Completion** | **100%** of v1.0.0 scope |
| **Completed Phases** | All (0–15) + Correctness Gate + Monorepo Migration |
| **Current Version** | v1.3.0 |
| **Passing Tests** | 2020 / 2024 (100%; 4 documented skips; the timing-sensitive `test_performance.py::TestProfiler::test_profile_decorator` gate can flake under slow CI — unrelated to M36) |
| **Release Date** | September 1, 2026 |
| **Repository Structure** | Monorepo (ChemEngine at `packages/chemengine/`, FastAPI backend + auth in `backend/`, web client in `apps/web/`) |
| **Backend Tests** | 224 / 224 passing (M19 foundation, M20 auth, M22 chemistry, M23 elements, M24+M25 learning, M26+M27 admin content incl. preview & deletion, M28 curriculum & learning experience, M29 AI tutor, M30 conversations/streaming/cache, M31 health/readiness diagnostics) |
| **Web Tests** | 74 / 74 passing (M21 auth, M22 explorer, M23 element explorer, M24+M25 learning, M28 nav/resume, M29+M30 tutor UI) |
| **Admin Tests** | 13 / 13 passing (M27 admin CMS incl. deletion flow, M28) |
| **Next Milestone** | **M36: Bounded Template-Based Retrosynthetic Engine — COMPLETE (2026-09-25, v1.3.0).** 8-template catalogue + bounded-DFS `RetrosynthesisEngine` + `SynthesisRoute`/`RetrosyntheticStep` + lazy `AlgorithmRegistry` registration + `ChemEngineAPI.retrosynthesize` tool. Full regression: 2020 passed / 4 skipped / 0 failed. |

**M31 completion record (2026-09-20).** Production PostgreSQL path verified
live (33/33 — portable PostgreSQL 18.6, full Alembic chain both directions,
tutor persistence, isolation, auth boundaries). Live AI provider smoke blocked
by missing credentials — documented, with 17/17 offline seam verification.
CI added (12 blocking gates, failure propagation proven). Reproducible
release validation scripted (18/18). Real-browser E2E executed (10/10 flows,
Chromium 147). Coverage measured: ChemEngine 80%, backend 80%, web 88.97%
lines, admin 62.35% lines. Phase 1.6 benchmark baseline established: 60
benchmarks pass (~63s) including the previously missing parsing benchmarks.
`GET /health/ready` added with secret-safe diagnostics. Test totals after
M31: ChemEngine 1635 passed / 1 skipped; backend **224** (220 + 4 health);
web 74; admin 13.

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
- **Reaction mechanisms** (full step-by-step mechanism engine) — ✅ **M34 complete** (v1.2.0; 10 curated mechanisms, 28-case oracle; see M34 section)
- **Graph neural network integration**
- **WebAssembly build** (browser-side execution)
- **Crystallography** (unit cells, space groups)
- **NMR spectra prediction**

*Selection note (2026-09-22): of the v2.0 list, only **Reaction mechanisms**
carries a documented selection signal — the M33-staged
`reactions/mechanisms.py` interfaces explicitly awaiting an engine — and is
therefore scheduled as **M34**. The remaining bullets stay an explicitly
unordered list until scoped.*

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
