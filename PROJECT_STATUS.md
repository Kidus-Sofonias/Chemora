# Chemora — Project Status Report

**Date:** September 17, 2026
**Version:** 1.0.0 (ChemEngine) / 0.1.0 (Chemora monorepo) / Backend M19–M20+M22–M25 complete / Web M21–M25 complete
**Status:** ✅ ChemEngine v1.0.0 complete · Monorepo migration complete · Backend Foundation (M19) + Authentication (M20) + Web Auth (M21) + Chemistry Explorer (M22) + Element Explorer (M23) + Chemistry Learning Core (M24) + Learning & Practice Expansion (M25) complete

---

## Executive Summary

ChemEngine v1.0.0 is **complete** with all 1635 tests passing (0 failures, 1 skipped). All planned phases (0–15) are finished. The repository has been restructured from a ChemEngine-only layout into the Chemora monorepo layout. The FastAPI backend (M19), Google-authenticated sessions (M20), the web auth client (M21), the Chemistry Explorer (M22), the Element Explorer (M23), the Chemistry Learning Core (M24), and the Learning & Practice Expansion (M25) are **complete** (106 backend tests, 52 web tests) — together they run real deterministic chemistry, element/electron-structure exploration, and a ChemEngine-backed learning experience with server-graded practice end to end.

| Metric | Value |
|--------|-------|
| **Overall Completion** | ~87% of v1.0.0 scope |
| **Passing Tests** | 1635 / 1635 (100%) |
| **Skipped** | 1 (directional bond round-trip) |
| **Source Files** | 72 Python files across 16 packages |
| **Test Files** | 37 |
| **Elements** | All 118 loaded from `elements.json` |
| **Packages Complete** | 16/16 (core, parsing, detection, generation, stereochemistry, properties, coordinates, rendering, reactions, validation, io, nomenclature, datasets, utils, compounds, education) |
| **Backend Tests** | 106 / 106 passing (M19 Foundation, M20 Authentication, M22 Chemistry API, M23 Elements API, M24+M25 Learning API) |
| **Web Tests** | 52 / 52 passing (M21 Auth integration, M22 Chemistry Explorer, M23 Element Explorer, M24+M25 Learning) |
| **Next Milestone** | M26 — Content Management Foundation (to be scoped) |

---

## Monorepo Migration (Complete — 2026-09-10)

The repository was restructured from a ChemEngine-only layout into the Chemora monorepo layout. All existing functionality is preserved.

**Repository structure:**
- `packages/chemengine/` — ChemEngine package (src layout preserved)
- `apps/web/` — React + Vite web client (M21 ✅; see below)
- `backend/` — FastAPI backend (M19 ✅ + M20 ✅; see below)
- `infrastructure/` — CI/CD, Docker (reserved)
- `TODO.md`, `PROJECT_STATUS.md`, `gantt.html` — Project tracking (updated)

**Verification:**
- 1635 tests passed, 1 skipped (baseline preserved)
- `import chemengine` works from installed package
- No duplicate ChemEngine implementation
- No chemistry functionality lost

---

## Backend Milestones

### ✅ M19: Backend Foundation (Complete)
- FastAPI application, CORS middleware, `/health` endpoint
- Async SQLAlchemy 2.0 engine + session factory (asyncpg)
- Alembic migrations scaffolding (repo-root `alembic/`)
- Backend `pyproject.toml`, pydantic-settings configuration, `.env.example`

### ✅ M20: Authentication (Complete)
- Google Sign-In / Identity Services — server-side ID-token verification via `google-auth` (`GoogleTokenVerifier`): signature, issuer, audience, expiry, subject
- User identity keyed by Google `sub`; email is **not** the identity key; unique constraint on `google_subject`
- Server-managed sessions with absolute expiration, inactivity timeout, and sliding renewal; revocation on logout
- Endpoints: `POST /api/v1/auth/google`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`
- Reusable `get_current_user` FastAPI dependency
- Alembic migration `001_initial_auth_tables` (users + sessions)
- 40 backend tests passing (in-memory SQLite + mock `GoogleTokenVerifier`)
- Architecture: `Endpoint → AuthService → GoogleTokenVerifier → User/Session models`

### ✅ M21: Frontend Authentication Integration (Complete)
- React 18 + Vite + TypeScript web app (`apps/web/`)
- Centralized `ApiClient` (fetch + `credentials: include`, JSON, typed base URL, 401-vs-network error classification)
- `AuthProvider` state machine: loading / unauthenticated / authenticated / error — never shows authenticated content before the session check finishes
- `AuthService`: `getCurrentUser()` / `exchangeCredential()` / `signOut()`
- `GoogleSignInProvider` port; production uses Google's official GIS client (`accounts.google.com/gsi/client`) — ID token sent to backend, never treated as a Chemora session
- 18 passing frontend tests (real ApiClient + AuthService vs. scriptable fake backend + mock Google provider)
- Mobile (`apps/mobile`) not yet configured — compatibility gap documented

### ✅ M22: Chemistry Explorer Foundation (Complete)
- Backend `POST /api/v1/chemistry/explore` + `ChemistryService` adapter over ChemEngine
- Identity for every input; structure (canonical SMILES, SVG, atoms/bonds) and bond-derived descriptors only for structure-bearing inputs
- Explorer UI with distinct chemistry/network/server error states
- 20 backend tests, 9 frontend tests

### ✅ M23: Element Explorer (Complete)
- Backend `GET /api/v1/elements` (118-element periodic table) + `GET /api/v1/elements/{identifier}` (symbol / name / atomic-number, case-insensitive) + `ElementService` adapter over `Element` / `ElectronConfigurator`
- Exposed structured electron data: full & noble-gas configurations, shell and subshell distributions, per-subshell orbital occupancy, valence/core/unpaired electron counts, and the engine's deterministic explanation
- Interactive periodic table (real 18-column grid, engine period/group/block placement, f-block rows, block colouring + text labels, accessible element cells, deliberate horizontal scroll on mobile)
- Element detail view: superscript configuration, orbital-box diagram from engine occupancy, shell distribution, counts, explanation; `prefers-reduced-motion` respected
- Client-side search (name / symbol / atomic number) over the engine-provided list — a UI index, not a second data source
- `unknown_element` / `invalid_identifier` 404 contract; network vs server errors distinguished
- 18 backend tests (incl. Cr/Cu Aufbau exceptions), 10 frontend tests

### ✅ M24: Chemistry Learning Core (Complete)
- Isolated content layer (`backend/app/learning/content.py`, 3 seeded lessons) — content is application data, NOT ChemEngine
- Learning API under `/api/v1/learning/` with explicit Pydantic models; answer keys never leave the server; deterministic (non-LLM) answer validation
- Progress persisted in `lesson_progress` (migration `002_lesson_progress`, FK → users CASCADE, unique per user/lesson): sections, per-question outcomes, derived percent, auto lesson completion, resume
- `chemistry_spotlight` sections render live engine-computed element data through the same component the Element Explorer uses
- Web Learn tab: catalog, section progression, progress bar, server-graded practice with immediate feedback, structured-errors only
- 17 backend tests, 10 frontend tests

### ✅ M25: Learning & Practice Expansion (Complete)
- Content expanded to 5 seeded lessons: *Chemical Formulas* and *Molecules and Their Properties* added to the M24 three — content still lives in the seed layer, outside ChemEngine
- `chemistry_spotlight` sections can now name a molecule (`molecule_input`) as well as an element; the client fetches live results from the existing M22 chemistry explore API and reuses the `ExplorerResult` component
- Two ChemEngine-backed answer kinds: `formula` (canonicalized via `formula_to_graph(...).molecular_formula`, so `H2O`/`HOH` both grade correct and `CO2` does not) and `element` (symbol / case-insensitive name / atomic number via `Element.from_symbol|from_name|from_z`)
- Grading remains deterministic and server-side; unparseable chemistry answers return `422 invalid_answer` rather than being marked wrong; answer keys never leave the server
- Defect fixed (found by testing, not by inspection): the in-progress `formula` kind used `parse_formula` (element counts) and read a non-existent `molecular_formula`, so no formula answer could ever be graded correct — corrected to the proper engine API with a regression guard over every seeded chemistry question
- Practice results view per practice section (attempted / correct / needs another look / accuracy); no gamification
- 11 new backend tests (106 total), 5 new frontend tests (52 total)

### ⬜ M26: Content Management Foundation (To Be Scoped)
Moving the seeded content layer into the database behind an admin CMS, without changing the learning API contract or the frontend learning architecture. Scope, dependencies, and acceptance criteria to be defined before work begins.

---

## Completed Milestones

### ✅ Phase 0: Foundation (v0.1.0)
- Core domain models: `MolecularGraph`, `Atom`, `Bond`, `Isotope`, `Charge`, `Coordinate2D`, `Coordinate3D`, `Conformer`
- All enums: `ElementSymbol` (all 118), `BondOrder`, `BondType`, `BondTopology`, `ChiralTag`, `BondStereo`, `Hybridization`
- `AlgorithmRegistry`, `EventBus`, `PluginManager`, `ChemEngineAPI`, `DatasetRegistry`
- `MolecularGraphBuilder` — builder pattern for immutable graph construction

### ✅ Phase 1: Parsing (v0.2.0)
- SMILES parser — full OpenSMILES specification
- SMILES canonicalization — Morgan-like iterative atom invariant refinement
- SMILES serializer — spanning-tree-based deterministic output
- InChI parser — formula, connections, hydrogens, charge layers
- Common alias resolver — 100+ chemical names → SMILES
- Auto-detect format — SMILES, InChI, formula, name detection
- `parse_any()` — automatic format detection and dispatch

### ✅ Phase 2: Validation (v0.4.0)
- 9 built-in validation rules: valence, hypervalent, charge, total charge, isotope, graph structure, radical, valence saturation, aromaticity
- 3 rule set profiles: strict, standard (default), relaxed
- Graph sanitization: add implicit hydrogens, remove duplicate bonds, full sanitize pipeline

### ✅ Phase 3: Functional Group Engine (v0.5.0)
- Functional group detection engine with 21 detectors
- All standard groups: Alcohol, Phenol, Ether, Aldehyde, Ketone, Carboxylic Acid, Ester, Amine (1°/2°/3°), Amide, Nitrile, Nitro, Halogen, Sulfide, Thiol, Sulfoxide, Sulfone, Alkene, Alkyne, Aromatic Ring

### ✅ Phase 4: Ring & Aromaticity (v0.6.0)
- Enhanced ring detection, ring system analysis, Hückel aromaticity

### ✅ Phase 5: Substructure Search (v0.7.0)
- VF2 subgraph isomorphism: `has_subgraph_match()`, `find_subgraph_matches()`, `count_subgraph_matches()`
- Maximum common substructure (MCS) via backtracking
- SMARTS tokenizer/parser: `parse_smarts()`, `smarts_match()`, `smarts_findall()`, `smarts_count()`

### ✅ Phase 6: Stereochemistry (v0.8.0)
- CIP priority rules: `get_cip_priority()` with atomic number and isotope tie-breaking
- Tetrahedral detection: `is_chiral_center()`, `assign_tetrahedral()`, `detect_tetrahedral_centers()`
- Double bond stereochemistry: `is_stereogenic_double_bond()`, `assign_double_bond_stereo()`
- Perception pipeline: `perceive_stereochemistry()` combining tetrahedral and double bond detection

### ✅ Phase 7: Isomer Generation (v0.9.0)
- Alkane isomer enumeration: `generate_alkane_isomers(n)` for C1–C8 with canonical key dedup
- Alkane isomer counts: `alkane_isomer_count(n)` for known reference values
- Functional group variant enumeration: `enumerate_functional_group_isomers(n, element)`
- Stereoisomer enumeration: `enumerate_stereoisomers(graph)` with 2^N config generation

### ✅ Phase 8: Molecular Properties (v0.10.0)
- TPSA computation: fragment contributions for O, N, S polar groups
- logP computation: simplified atom-contribution model
- HBA/HBD counting: hydrogen bond acceptor/donor detection
- Rotatable bond counting, Fraction CSp3 computation

### ✅ Phase 9: Coordinate Generation (v0.11.0) — NEW
- **2D Force-Directed Layout**: Fruchterman-Reingold algorithm with ring template placement for 3–8 membered rings
- **Ring Detection**: DFS-based cycle detection for monocyclic and fused ring systems
- **3D Conformer Generation**: Distance geometry with bounds matrix, metric matrix embedding, and steepest descent energy minimization
- **Conformer Clustering**: RMSD-based greedy clustering with energy ranking
- **Bond Length Constraints**: C–C single/double/triple bond length enforcement in minimization
- **VDW Clash Avoidance**: Van der Waals radius-based non-bonded interaction penalties

### ✅ Phase 10: Rendering & Reactions (v0.12.0) — NEW
- **SVG Molecular Depiction**: Full SVG renderer with configurable bond length, atom colors, font sizes
- **Bond Rendering**: Single, double, triple, aromatic (dashed inner), wedge, and dashed wedge bonds
- **Atom Labels**: Element symbols with background circles, charge annotations, CPK-like element colors
- **Reaction Models**: `Reaction`, `ReactionComponent`, `ReactionCondition`, `ReactionArrow` dataclasses
- **Reaction Builder**: Fluent builder API for constructing reactions
- **Atom Balance Checking**: `is_balanced()` and `atom_count_difference()` methods
- **Reaction Templates**: 5 built-in templates (combustion, acid-base, esterification, dehydration, hydrogenation)
- **Reaction Serialization**: `to_dict()` for JSON export

### ✅ Phase 11: Nomenclature & IO (v0.13.0) — NEW
- **IUPAC Naming Engine**: Basic organic nomenclature for alkanes, alkenes, alkynes, alcohols, aldehydes, ketones, carboxylic acids, amines, nitriles, cycloalkanes, and halogenated compounds
- **Functional Group Detection**: Hydroxyl, carbonyl, carboxyl, amine, nitrile, halogen, alkene, alkyne detection
- **Longest Chain Detection**: DFS-based longest carbon chain finding for naming backbone
- **Substituent Naming**: Methyl, ethyl, propyl, butyl, halogen substituents with locants
- **JSON Serialization**: `graph_to_dict()`, `graph_to_json()`, `dict_to_graph()`, `json_to_graph()`
- **Format Conversion**: `convert_format()` supporting smiles, formula, json, name, dict targets
- **Coordinate Serialization**: 2D/3D coordinates and conformers included in serialized output

### ✅ Phase 12: Release (v1.0.0) — NEW
- **Comprehensive Test Suite**: 934 tests across 26 test files
- **AI Tool Interface**: 11 registered tools (parse_smiles, parse_formula, compute_property, validate, sanitize, detect_functional_groups, generate_2d_coordinates, generate_3d_conformer, render_svg, name_molecule, serialize)
- **Clean Package Structure**: All 15 packages complete with proper `__init__.py` exports
- **Version 1.0.0**: Production-ready release

---

## Test Suite Summary

| Test File | Tests | Status |
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
| `test_rings_enhanced.py` | 26 | ✅ All pass |
| `test_molecule.py` | 7 | ✅ All pass |
| `test_validation.py` | 59 | ✅ All pass |
| `test_functional_groups.py` | 55 | ✅ All pass |
| `test_substructure.py` | 24 | ✅ All pass |
| `test_stereochemistry.py` | 7 | ✅ All pass |
| `test_generation.py` | 9 | ✅ All pass |
| `test_properties.py` | 17 | ✅ All pass |
| `test_coordinates.py` | 31 | ✅ All pass |
| `test_rendering.py` | 28 | ✅ All pass |
| `test_reactions.py` | 28 | ✅ All pass |
| `test_nomenclature.py` | 26 | ✅ All pass |
| `test_io.py` | 26 | ✅ All pass |
| `test_coverage_low.py` | 143 | ✅ All pass |
| `test_coverage_critical.py` | 68 | ✅ All pass |
| `test_electron_config.py` | 47 | ✅ All pass |
| `test_smarts_comprehensive.py` + others | ~130 | ✅ All pass |
| **Total** | **1636** | **1635 pass, 1 skip** |

---

## Architecture Verification

| Principle | Status |
|-----------|--------|
| MolecularGraph is single source of truth | ✅ CONFIRMED |
| Domain models are immutable | ✅ CONFIRMED |
| Dependency direction (core → everything) | ✅ CONFIRMED |
| No circular imports | ✅ CONFIRMED |
| Plugin architecture | ✅ EXISTS |
| Event system | ✅ EXISTS |
| AI Tool interface | ✅ 13 tools registered (incl. `calculate_electron_configuration`) |

---

## Version 1.0.0 Scorecard

| Category | Status |
|----------|--------|
| Core Models | ✅ 100% |
| Infrastructure | ✅ 100% |
| Formula Parser | ✅ 100% |
| SMILES Parser | ✅ 100% |
| InChI Parser | ✅ 100% |
| Alias Resolver | ✅ 100% |
| Canonical SMILES | ✅ 85% |
| Ring Detection | ✅ 100% |
| Validation | ✅ 100% |
| Functional Groups | ✅ 100% |
| Ring Systems | ✅ 100% |
| Aromaticity | ✅ 100% |
| Substructure | ✅ 100% |
| Stereochemistry | ✅ 100% |
| Isomer Generation | ✅ 100% |
| Molecular Properties | ✅ 100% |
| Coordinate Generation | ✅ 100% |
| Rendering (SVG) | ✅ 100% |
| Reactions | ✅ 100% |
| Nomenclature (IUPAC) | ✅ 100% |
| IO (Serialization) | ✅ 100% |
| Atomic Chemistry (Electron Config) | ✅ 100% |
| **Overall** | **✅ 100%** |

```
Overall Health: ✅ EXCELLENT
  - Architecture:       ✅ Sound, well-documented
  - Core Implementation: ✅ Solid (all core modules complete)
  - Tests:              ✅ 1635 pass (1 skip)
  - All Packages:       ✅ 16/16 complete (no stubs)
  - Bug Status:         ✅ All pre-existing failures fixed
  - AI Interface:       ✅ 13 tools registered
  - New Features:       ✅ compounds/, education/ (electron config) modules added
  - Version:            ✅ 1.0.0
```
