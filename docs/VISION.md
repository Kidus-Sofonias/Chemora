# Vision

## Purpose

ChemEngine is a production-grade chemistry engine designed from the ground up to be the computational foundation for any chemistry-aware application. It is architecture-first, not feature-first: every subsystem is modular, extensible, and independently testable.

## Core Principles

1. **Molecular Graph as Single Source of Truth**: Every atom, bond, charge, isotope, stereocenter, coordinate, and property derives from the MolecularGraph. There is no other representation of a molecule anywhere in the system.

2. **Immutability**: All domain models are frozen dataclasses. Thread-safe, hashable, cacheable. Mutations go through the Builder pattern.

3. **Plugin Architecture**: Any Python package can extend the engine via entry points. No central plugin registry to maintain.

4. **Algorithm Registry**: Every algorithm is registered, versioned, and resolvable by capability tags. Hot-swappable at runtime.

5. **Event-Driven**: Typed pub/sub event bus with correlation ID tracing enables loose coupling and pipeline observability.

6. **AI-Ready**: Self-describing tool definitions with JSON Schema enable LLM function calling, CLI tools, and web APIs from a single facade.

## Scope

### In Scope
- Molecular graph construction and manipulation
- Chemical identifier parsing (SMILES, InChI, formula, IUPAC names)
- Isomer enumeration (constitutional, stereoisomer, conformer)
- Substructure detection (rings, aromaticity, functional groups)
- Stereochemistry perception and assignment (R/S, E/Z, cis/trans)
- Molecular property computation (mass, formula, logP, TPSA)
- Coordinate generation (2D layout, 3D conformers)
- Molecular rendering (SVG)
- Reaction infrastructure
- Molecular validation and sanitization

### Out of Scope (for v0.1)
- Quantum chemistry calculations
- Molecular dynamics simulations
- Crystal structure prediction
- NMR spectra prediction
- Retrosynthetic analysis
- UI components (this is a library, not an application)

## Future Domains (Architecture Anticipates)

The architecture is designed to support without fundamental redesign:
- Organometallic chemistry (dative bonds, coordination geometries)
- Polymer chemistry (repeating units, chain graphs)
- Biomolecules (proteins, nucleic acids, carbohydrates)
- Isotopologues and isotopomers
- Ions and radicals
- Crystallography (unit cells, space groups)
- Reaction networks and pathways
- Machine learning integration (descriptor computation, graph neural networks)