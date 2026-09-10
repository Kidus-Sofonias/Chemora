# ChemEngine — Engineering Audit Report

> ⚠️ **HISTORICAL DOCUMENT — SUPERSEDED**
>
> This audit report was produced **July 18, 2026** during early foundation
> work (Phase 0/1). Its findings and status assertions reflect that time
> and are **no longer current**. Nearly every "missing" or "not
> implemented" claim below has since been resolved.
>
> For current status see:
> - [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — up-to-date project status
>   and test summary
> - [`docs/SPECIFICATIONS.md`](docs/SPECIFICATIONS.md) — implemented
>   feature matrix (including the group-aware formula parser)
> - [`tests/`](tests/) — the live regression suite (1635 passing tests)
>
> This file is retained for historical context only.

**Date:** July 18, 2026  
**Auditor:** Buffy (Freebuff AI Agent)  
**Previous AI Agent:** Cline  
**Status (historical):** ⚠️ Foundation laid, several critical issues found

---

## 1. Project Structure

```
chemengine/
├── .gitignore                      # Python/IDE ignores (OK)
├── pyproject.toml                  # Build config (requires Python ≥3.13)
├── README.md                       # General overview
├── AUDIT_REPORT.md                 # THIS FILE
├── benchmarks/
│   ├── __init__.py                 # Empty marker
│   └── benchmark_core.py           # 4 benchmark tests
├── docs/
│   ├── ALGORITHMS.md               # Algorithm descriptions
│   ├── API_DESIGN.md               # API conventions
│   ├── ARCHITECTURE.md             # Architecture overview
│   ├── DECISIONS.md                # 10 ADR entries
│   ├── DOMAIN_MODEL.md             # Domain model reference
│   ├── MODULES.md                  # Module responsibilities
│   ├── ROADMAP.md                  # Phased delivery plan
│   ├── TESTING.md                  # Test strategy
│   └── VISION.md                   # Long-term vision
├── plugins/                        # EMPTY directory (no plugins)
├── src/chemengine/
│   ├── __init__.py                 # Package entry with exports
│   ├── coordinates/
│   │   └── __init__.py             # ✗ Empty (stub only)
│   ├── core/
│   │   ├── __init__.py             # Re-exports all core modules
│   │   ├── atoms.py                # Atom, Isotope models
│   │   ├── bonds.py                # Bond model
│   │   ├── charges.py              # Charge, ElectronConfiguration models
│   │   ├── datasets.py             # DatasetRegistry (lazy-loading)
│   │   ├── element.py              # Element class (ONLY 27/118 elements!)
│   │   ├── enums.py                # All shared enums (complete)
│   │   ├── events.py               # EventBus (typed pub/sub)
│   │   ├── geometry.py             # Coordinate2D, Coordinate3D, Conformer
│   │   ├── graph.py                # MolecularGraph + MolecularGraphBuilder
│   │   ├── molecule.py             # Molecule wrapper with computed properties
│   │   ├── plugin.py               # PluginProtocol + PluginManager
│   │   ├── registry.py             # AlgorithmRegistry
│   │   ├── stereo.py               # ChiralCenter, StereoConfig
│   │   ├── substructure.py         # FunctionalGroup, Ring models
│   │   └── tool_interface.py       # ChemEngineAPI (AI-ready facade)
│   ├── datasets/
│   │   ├── __init__.py             # Re-exports
│   │   ├── elements.json           # ⚠️ Only 20/118 elements!
│   │   ├── functional_groups.toml  # 21 functional group definitions
│   │   ├── ring_templates.toml     # 7 ring templates (3-7 membered)
│   │   └── valence_rules.toml      # 11 element valence rules
│   ├── detection/
│   │   ├── __init__.py             # Marker
│   │   └── rings.py                # Ring detection (BFS-based SSSR)
│   ├── generation/
│   │   └── __init__.py             # 🔴 BROKEN: imports non-existent modules
│   ├── io/
│   │   └── __init__.py             # ✗ Empty (stub only)
│   ├── nomenclature/
│   │   └── __init__.py             # ✗ Empty (stub only)
│   ├── parsing/
│   │   ├── __init__.py             # Package init
│   │   ├── formula.py              # Formula parser (complete)
│   │   └── protocol.py             # Parser Protocol (complete)
│   ├── properties/
│   │   └── __init__.py             # ✗ Empty (stub only)
│   ├── reactions/
│   │   └── __init__.py             # ✗ Empty (stub only)
│   ├── rendering/
│   │   └── __init__.py             # ✗ Empty (stub only)
│   ├── stereochemistry/
│   │   └── __init__.py             # ✗ Empty (stub only)
│   ├── utils/
│   │   ├── benchmarking.py         # Timer, benchmark decorator
│   │   ├── cache.py                # MolecularCache (LRU)
│   │   └── logging.py              # Structlog setup
│   └── validation/
│       └── __init__.py             # ✗ Empty (stub only)
└── tests/
    ├── __init__.py                 # Marker
    ├── conftest.py                 # Fixtures (methane, ethane, benzene)
    ├── test_core.py                # 🔴 Uses WRONG class names
    └── test_formula.py             # Formula parser tests
```

---

## 2. Missing Files

### Missing Documentation
| File | Status | Notes |
|------|--------|-------|
| LICENSE | ✗ Missing | Only mentioned in pyproject.toml (MIT), no actual file |
| CHANGELOG.md | ✗ Missing | Required for release tracking |
| CONTRIBUTING.md | ✗ Missing | Required for open-source contributions |
| DEVELOPMENT_RULES.md | ✗ Missing | No development guidelines |
| SPECIFICATIONS.md | ✗ Missing | No formal specifications document |
| TODO.md | ✗ Missing | No task tracking |

### Missing Source Modules (per MODULES.md)
| Module | Status | Notes |
|--------|--------|-------|
| parsing/smiles.py | ✗ Missing | Phase 1 milestone |
| parsing/inchi.py | ✗ Missing | Phase 1 milestone |
| parsing/iupac/ | ✗ Missing | Phase 1 milestone |
| parsing/alias.py | ✗ Missing | Phase 1 milestone |
| detection/aromatic.py | ✗ Missing | Phase 2 milestone |
| detection/functional_groups.py | ✗ Missing | Referenced by tool_interface.py! |
| detection/substructure.py | ✗ Missing | Phase 2 milestone |
| generation/constitutional.py | ✗ Missing | Referenced by broken __init__.py |
| generation/stereoisomers.py | ✗ Missing | Referenced by broken __init__.py |
| generation/conformers.py | ✗ Missing | Referenced by broken __init__.py |
| properties/*.py | ✗ All missing | Phase 5 milestone |
| coordinates/*.py | ✗ All missing | Phase 5 milestone |
| rendering/*.py | ✗ All missing | Phase 6 milestone |
| reactions/*.py | ✗ All missing | Phase 6 milestone |
| validation/*.py | ✗ All missing | Phase 4 milestone |
| io/*.py | ✗ All missing | Phase 7 milestone |
| nomenclature/*.py | ✗ All missing | Phase 7 milestone |
| stereochemistry/*.py | ✗ All missing | Phase 3 milestone |

---

## 3. Documentation Audit

| Document | Status | Verdict |
|----------|--------|---------|
| README.md | ✓ Complete | Good overview, some code references broken |
| VISION.md | ✓ Complete | Core principles, scope, future domains |
| ARCHITECTURE.md | ✓ Complete | Layered architecture diagram |
| DOMAIN_MODEL.md | ⚠️ Partial | Uses old class names (Point2D vs Coordinate2D, FormalCharge vs Charge) |
| MODULES.md | ✓ Complete | Lists all intended modules |
| API_DESIGN.md | ✓ Complete | Conventions and facade methods |
| ALGORITHMS.md | ✓ Complete | Algorithm descriptions with citations |
| ROADMAP.md | ✓ Complete | 8 phases with checkboxes |
| TESTING.md | ✓ Complete | Test layers and structure |
| DECISIONS.md | ✓ Complete | 10 ADRs |
| CONTRIBUTING.md | ✗ Missing | --- |
| DEVELOPMENT_RULES.md | ✗ Missing | --- |
| SPECIFICATIONS.md | ✗ Missing | --- |
| TODO.md | ✗ Missing | --- |
| CHANGELOG.md | ✗ Missing | --- |
| LICENSE | ✗ Missing | --- |

---

## 4. Source Code Audit

### Core Package (`core/`) — All modules IMPLEMENTED

| Module | Status | Lines | Notes |
|--------|--------|-------|-------|
| atoms.py | ✅ Implemented | ~250 | Atom, Isotope — complete with validation |
| bonds.py | ✅ Implemented | ~200 | Bond — complete with validation |
| charges.py | ✅ Implemented | ~100 | Charge, ElectronConfiguration, ChargeDistribution |
| datasets.py | ✅ Implemented | ~200 | DatasetRegistry with lazy loading, hot-reload |
| element.py | ⚠️ Incomplete | ~150 | Only 27/118 elements hardcoded |
| enums.py | ✅ Implemented | ~300 | All 118 ElementSymbols, BondOrder, ChiralTag, etc. |
| events.py | ✅ Implemented | ~200 | EventBus with threading, priority |
| geometry.py | ✅ Implemented | ~150 | Coordinate2D, Coordinate3D, Conformer |
| graph.py | ✅ Implemented | ~400 | MolecularGraph, MolecularGraphBuilder |
| molecule.py | ✅ Implemented | ~150 | Molecule wrapper |
| plugin.py | ✅ Implemented | ~200 | PluginProtocol, PluginManager |
| registry.py | ✅ Implemented | ~200 | AlgorithmRegistry |
| stereo.py | ✅ Implemented | ~100 | ChiralCenter, StereoConfig |
| substructure.py | ✅ Implemented | ~80 | FunctionalGroup, Ring |
| tool_interface.py | ✅ Implemented | ~350 | ChemEngineAPI, ToolDefinition |

### Parsing Package (`parsing/`) — PARTIALLY implemented

| Module | Status | Notes |
|--------|--------|-------|
| protocol.py | ✅ Implemented | Parser Protocol, auto_detect_format |
| formula.py | ✅ Implemented | Formula parser + FormulaParser class |
| smiles.py | ✗ Missing | Phase 1 |
| inchi.py | ✗ Missing | Phase 1 |
| iupac/ | ✗ Missing | Phase 1 |
| alias.py | ✗ Missing | Phase 1 |

### Detection Package (`detection/`) — PARTIALLY implemented

| Module | Status | Notes |
|--------|--------|-------|
| rings.py | ✅ Implemented | BFS-based SSSR ring detection |
| aromatic.py | ✗ Missing | Phase 2 |
| functional_groups.py | ✗ Missing | Phase 2 — **Referenced by tool_interface.py** |
| substructure.py | ✗ Missing | Phase 2 |

### Generation Package (`generation/`) — 🔴 BROKEN

| Module | Status | Notes |
|--------|--------|-------|
| __init__.py | 🔴 Broken | Imports 3 non-existent modules |

### Other Packages — All STUBS (empty __init__.py only)

| Package | Status | Notes |
|---------|--------|-------|
| coordinates/ | ✗ Stub | No implementation |
| io/ | ✗ Stub | No implementation |
| nomenclature/ | ✗ Stub | No implementation |
| properties/ | ✗ Stub | No implementation |
| reactions/ | ✗ Stub | No implementation |
| rendering/ | ✗ Stub | No implementation |
| stereochemistry/ | ✗ Stub | No implementation |
| validation/ | ✗ Stub | No implementation |

### Utils Package — All IMPLEMENTED

| Module | Status | Notes |
|--------|--------|-------|
| logging.py | ✅ Implemented | Structlog setup |
| benchmarking.py | ✅ Implemented | Timer, benchmark decorator |
| cache.py | ✅ Implemented | LRU MolecularCache |

---

## 5. Architecture Verification

| Principle | Status | Evidence |
|-----------|--------|---------|
| MolecularGraph is single source of truth | ✅ CONFIRMED | All modules import/use MolecularGraph |
| Domain models are immutable | ✅ CONFIRMED | All frozen dataclasses with slots |
| Dependency direction (core ← everything) | ✅ CONFIRMED | No reverse dependencies |
| No circular imports | ⚠️ UNVERIFIABLE | Cannot run Python to test |
| Plugin architecture | ✅ EXISTS | PluginProtocol + PluginManager + entry_points |
| Event system | ✅ EXISTS | EventBus with threading |
| Dataset registry | ✅ EXISTS | DatasetRegistry with lazy loading |
| Algorithm registry | ✅ EXISTS | AlgorithmRegistry with tagging |
| AI Tool interface | ✅ EXISTS | ChemEngineAPI + ToolDefinition + execute_tool |

### Architectural Violations Found

1. **correct/__init__.py has stale exports**: Exports `Point2D`, `Point3D`, `IsotopeInfo`, `FormalCharge`, `RadicalElectron`, `HydrogenType` — but these classes don't exist in the actual modules anymore (class names were changed).

2. **DOMAIN_MODEL.md references old class names**: Mentions `Point2D`/`Point3D`, `FormalCharge`, `RadicalElectron`, `IsotopeInfo` — but actual source uses `Coordinate2D`/`Coordinate3D`, `Charge`, `Atom.isotope` field (not separate `IsotopeInfo`).

3. **generation/__init__.py has broken imports**: Tries to import from non-existent modules.

4. **tool_interface.py references missing module**: `detection.functional_groups` is imported in a try/except but the module doesn't exist.

---

## 6. Test Audit

| Metric | Value |
|--------|-------|
| Test files | 3 (conftest.py, test_core.py, test_formula.py) |
| Test classes | 8 (TestAtom, TestBond, TestMolecularGraph, TestMolecularGraphBuilder, TestGeometry, TestCharges, TestParseFormula, TestFormulaToGraph) |
| Test functions | ~40 |
| Test fixtures | 4 (methane_graph, ethane_graph, benzene_graph, empty_registry, empty_bus) |
| Property-based tests | 0 (Hypothesis configured but not used) |
| Benchmark tests | 4 |
| Coverage tooling | Configured in pyproject.toml but not run |

### 🔴 Test Failures (Class Name Mismatches)

The test file `test_core.py` uses class names that DON'T MATCH the actual source code:

| Line in test_core.py | Uses | Should Use |
|----------------------|------|------------|
| `from chemengine.core.atoms import ... IsotopeInfo` | `IsotopeInfo` | `Isotope` |
| `from chemengine.core.geometry import Point2D, Point3D, Conformer` | `Point2D, Point3D` | `Coordinate2D, Coordinate3D` |
| `from chemengine.core.charges import FormalCharge, RadicalElectron` | `FormalCharge, RadicalElectron` | `Charge` (RadicalElectron doesn't exist as separate class) |

These will cause **ImportError** at test runtime.

### Missing Test Coverage

| Component | Tests | Notes |
|-----------|-------|-------|
| Core domain models | ✅ Existing | Atoms, bonds, graph, builder |
| Geometry models | ✅ Existing | But uses wrong class names |
| Charge models | ✅ Existing | But uses wrong class names |
| Formula parser | ✅ Existing | Complete |
| EventBus | ✗ Missing | No tests |
| AlgorithmRegistry | ✗ Missing | No tests |
| PluginManager | ✗ Missing | No tests |
| ChemEngineAPI | ✗ Missing | No tests |
| DatasetRegistry | ✗ Missing | No tests |
| Ring detection | ✗ Missing | No tests |
| Element class | ✗ Missing | No tests |
| Molecule class | ✗ Missing | No tests |

---

## 7. Technical Debt

### 🔴 Critical Issues (Blocking)

1. **generation/__init__.py broken imports** — Will crash on `from chemengine.generation import ...`
2. **test_core.py wrong class names** — `IsotopeInfo` → `Isotope`, `Point2D`/`Point3D` → `Coordinate2D`/`Coordinate3D`, `FormalCharge`/`RadicalElectron` → `Charge`
3. **correct/** **exports stale class names** — `Point2D`, `Point3D`, `IsotopeInfo`, `FormalCharge`, `RadicalElectron`, `HydrogenType` in `__all__` don't match actual classes

### ⚠️ Moderate Issues

4. **element.py only has 27/118 elements** — Missing 91 elements
5. **elements.json only has 20/118 elements** — Missing 98 elements
6. **DOMAIN_MODEL.md references old class names** — Documentation out of sync with code
7. **conftest.py defines `empty_bus` and `empty_registry` fixtures** but the actual test files never import or use them; they're dead fixtures
8. **`BondTopology` imported from `bonds` but defined in `enums`** — Works (Python re-exports) but confusing
9. **pyproject.toml requires Python ≥3.13** but only Python 3.10 is available in the test environment

### 🔧 Minor Issues

10. **`convert()` method in tool_interface.py** references `graph.canonical_smiles`, `graph.inchi`, `graph.inchikey` — these properties don't exist on MolecularGraph (they exist on the wrapper `MolecularIdentifiers`)
11. **`_exec_parse_smiles`** references `graph.canonical_smiles`, `graph.inchi`, `graph.inchikey` — same issue as above
12. **`_exec_parse_formula`** returns `graph.exact_mass` which DOES exist as a cached_property ✅
13. **`core/__init__.py`** lists `HydrogenType` in `__all__` but it doesn't exist anywhere
14. **`core/__init__.py`** lists `BondTopology` imported from `bonds` module but it's really in `enums`
15. **`benchmark_core.py` uses `pytest-benchmark` plugin** — requires the `benchmark` fixture from pytest-benchmark being installed

---

## 8. Next Milestone

### Where the Previous AI Stopped

The previous AI (Cline) completed **Phase 0 (Foundation)** according to ROADMAP.md:
- ✅ Project structure and build configuration
- ✅ Core domain models
- ✅ AlgorithmRegistry, EventBus, PluginManager
- ✅ ChemEngineAPI, DatasetRegistry
- ✅ Reference datasets (partial — only 20/118 elements)
- ✅ Formula parser
- ✅ Ring detection
- ✅ Test suite for core models
- ✅ Documentation (9 docs)

However, **critical bugs were introduced during Phase 0 that need immediate repair before moving forward**:
1. Test class names don't match actual source code (`IsotopeInfo` → `Isotope`, etc.)
2. `core/__init__.py` exports stale class names
3. `generation/__init__.py` imports non-existent modules
4. Python ≥3.13 is required but only 3.10 is available

### Recommended Next Milestone: **Repair Phase 0 + Begin Phase 1 (Parsing)**

#### Step 1: Critical Fixes
- Fix test class name mismatches
- Fix `core/__init__.py` stale exports
- Fix `generation/__init__.py` broken imports
- Fix `DOMAIN_MODEL.md` stale references
- Create LICENSE, CHANGELOG.md, CONTRIBUTING.md, TODO.md

#### Step 2: Complete Phase 0
- Complete element.py with all 118 elements
- Complete elements.json with all 118 elements
- Add missing tests (events, registry, plugin, datasets, API, rings)
- Reduce Python requirement to ≥3.10 or install Python 3.13

#### Step 3: Phase 1 — SMILES Parser
- Implement SMILES parser (highest priority)
- SMILES canonicalization
- Round-trip property-based tests

---

## Summary

| Category | Verdict |
|----------|---------|
| Architecture | ✅ Sound design, well-documented |
| Core Implementation | ✅ Solid foundation (all core modules complete) |
| Tests | ⚠️ Present but broken (wrong class names) |
| Documentation | ✅ 9/15 documents complete |
| Datasets | ⚠️ Partial (20/118 elements) |
| Plugin System | ✅ Complete infrastructure |
| Event System | ✅ Complete |
| AI Interface | ✅ Complete facade |
| Missing Modules | ✗ 10 packages are stubs, 16+ modules missing |
| Python Requirement | ⚠️ ≥3.13 required, only 3.10 available |
