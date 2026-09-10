# Roadmap

> All phases complete as of August 26, 2026. Version 1.0.0 released.

## ✅ Phase 0: Foundation (v0.1.0)
- [x] Project structure and build configuration
- [x] Core domain models (MolecularGraph, Atom, Bond, etc.)
- [x] AlgorithmRegistry, EventBus, PluginManager
- [x] ChemEngineAPI (AI-ready facade)
- [x] DatasetRegistry
- [x] Reference datasets (elements, isotopes, functional groups)
- [x] Formula parser
- [x] Ring detection
- [x] Test suite for core models

## ✅ Phase 1: Parsing (v0.2.0)
- [x] SMILES parser (full OpenSMILES specification)
- [x] SMILES canonicalization
- [x] InChI parser (main layers)
- [x] Common alias resolver (100+ names)
- [x] Auto-detect format
- [x] Round-trip property-based tests

## ✅ Phase 2: Validation (v0.4.0)
- [x] 9 validation rules
- [x] 3 rule set profiles (strict, standard, relaxed)
- [x] Graph sanitization pipeline

## ✅ Phase 3: Functional Group Detection (v0.5.0)
- [x] 21 functional group detectors
- [x] All standard groups
- [x] Overlap detection and priority-based resolution

## ✅ Phase 4: Ring & Aromaticity (v0.6.0)
- [x] Enhanced ring detection (SSSR + all rings)
- [x] Ring system analysis (fused, bridged, spiro)
- [x] Hückel aromaticity detection

## ✅ Phase 5: Substructure Search (v0.7.0)
- [x] VF2 subgraph isomorphism
- [x] Maximum common substructure (MCS)
- [x] SMARTS tokenizer/parser

## ✅ Phase 6: Stereochemistry (v0.8.0)
- [x] CIP priority rules (Rules 1–4)
- [x] Tetrahedral center detection and assignment
- [x] Double bond stereochemistry (E/Z)

## ✅ Phase 7: Isomer Generation (v0.9.0)
- [x] Alkane isomer enumeration (C1–C8)
- [x] Functional group variant enumeration
- [x] Stereoisomer enumeration (2^N configs)

## ✅ Phase 8: Molecular Properties (v0.10.0)
- [x] TPSA computation
- [x] logP computation
- [x] HBA/HBD counting
- [x] Rotatable bond counting
- [x] Fraction CSp3 computation

## ✅ Phase 9: Coordinate Generation (v0.11.0)
- [x] 2D force-directed layout (Fruchterman-Reingold)
- [x] Ring template placement (3–8 membered rings)
- [x] 3D distance geometry conformer generation
- [x] Bounds matrix and metric matrix embedding
- [x] Steepest descent energy minimization
- [x] Conformer clustering by RMSD

## ✅ Phase 10: Rendering & Reactions (v0.12.0)
- [x] SVG molecular depiction
- [x] Single/double/triple/aromatic/wedge/dashed bond rendering
- [x] Atom labels with CPK colors and charge annotations
- [x] Reaction data models and builder API
- [x] Atom balance checking
- [x] Reaction templates (combustion, acid-base, esterification, dehydration, hydrogenation)

## ✅ Phase 11: Nomenclature & IO (v0.13.0)
- [x] IUPAC naming engine (alkanes, alkenes, alkynes, alcohols, aldehydes, ketones, acids, amines, nitriles, cycloalkanes, halides)
- [x] Functional group detection for naming
- [x] JSON serialization/deserialization
- [x] Format conversion (smiles, formula, json, name, dict)

## ✅ Phase 12: Release (v1.0.0)
- [x] 934 tests passing
- [x] 11 AI tools registered
- [x] All packages complete (no stubs)
- [x] Clean API surface
- [x] Documentation up to date
