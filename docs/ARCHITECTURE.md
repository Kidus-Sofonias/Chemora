# Architecture

## Overview

ChemEngine follows a layered architecture with strict dependency direction:

```
┌─────────────────────────────────────────────────────────────┐
│                    ChemEngineAPI (Facade)                     │
│         AI Agents │ CLI │ Web API │ Python Library           │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Tool Definitions (JSON Schema)             │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  AlgorithmRegistry  │  EventBus  │  PluginManager  │  DatasetRegistry │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Parsing  │  Detection  │  Generation  │  Stereochemistry   │
│  Properties │ Coordinates │ Rendering │ Reactions │ Validation │
│  IO │ Nomenclature                                           │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              MolecularGraph (Single Source of Truth)          │
│         Atom │ Bond │ Stereocenter │ Geometry │ Charges       │
└─────────────────────────────────────────────────────────────┘
```

## Package Dependency Rules

1. `core/` depends on NOTHING. It is the foundation.
2. Every subsystem depends on `core/` (MolecularGraph, Atom, Bond, etc.).
3. Subsystems do NOT depend on each other directly. They communicate through:
   - MolecularGraph (the shared data model)
   - AlgorithmRegistry (for algorithm discovery)
   - EventBus (for event-driven communication)
4. Plugins depend on `core/` and optionally on any subsystem.

## Key Design Patterns

### Builder Pattern
MolecularGraphBuilder provides mutable construction of immutable MolecularGraphs.

### Registry Pattern
AlgorithmRegistry provides centralized algorithm discovery and resolution.

### Observer Pattern
EventBus provides typed pub/sub with correlation ID tracing.

### Facade Pattern
ChemEngineAPI provides a unified interface over all subsystems.

### Strategy Pattern
Algorithms are registered and resolvable by capability tags, enabling runtime algorithm selection.

### Plugin Pattern
PluginProtocol + PluginManager enables third-party extensions via entry points.