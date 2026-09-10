# Architecture Decision Records

## ADR-001: Frozen Dataclasses over Pydantic

**Status**: Accepted

**Context**: Need immutable domain models that are hashable, thread-safe, and memory-efficient.

**Decision**: Use `@dataclass(frozen=True, slots=True)` instead of Pydantic models.

**Consequences**:
- Zero runtime overhead (no validation metaclass)
- Built-in immutability (no `__setattr__` tricks)
- Slots reduce memory by ~40%
- No serialization bias (no built-in JSON schema generation)
- Validation done in `__post_init__` where needed

## ADR-002: Protocols over ABCs

**Status**: Accepted

**Context**: Need structural subtyping for parsers, plugins, and algorithms.

**Decision**: Use `typing.Protocol` instead of `abc.ABC`.

**Consequences**:
- Duck typing without inheritance coupling
- Simple functions can serve as parsers/plugins
- No base class registration needed
- Better compatibility with static type checkers

## ADR-003: Builder Pattern for Graph Construction

**Status**: Accepted

**Context**: MolecularGraph is immutable, but graph construction requires many mutations.

**Decision**: Use MolecularGraphBuilder for construction, .build() returns immutable graph.

**Consequences**:
- Clean separation of mutable construction from immutable domain
- Builder can validate before building
- `from_graph()` enables modification of existing graphs
- Slightly more verbose than direct construction

## ADR-004: Single Source of Truth (No Intermediate Representations)

**Status**: Accepted

**Context**: Parsers could produce intermediate representations before converting to MolecularGraph.

**Decision**: Every parser directly produces a MolecularGraph. No intermediate representations.

**Consequences**:
- No duplication of molecule representations
- Simpler debugging (only one type to understand)
- Parser implementations are more complex
- Guarantees consistency across all operations

## ADR-005: Algorithm Registry over Direct Imports

**Status**: Accepted

**Context**: Need runtime algorithm selection, plugin overrides, and versioning.

**Decision**: Centralized AlgorithmRegistry with domain/name/version/tags.

**Consequences**:
- Runtime algorithm resolution by capability tags
- Plugin algorithms can override built-in ones
- Version tracking for reproducibility
- Slight indirection cost on algorithm lookup

## ADR-006: Synchronous Event Bus over Async

**Status**: Accepted

**Context**: Need loose coupling between modules without async complexity.

**Decision**: Synchronous EventBus with threading.Lock for thread safety.

**Consequences**:
- Events processed immediately in publisher's thread
- No async event loop complexity
- Easy debugging (stack traces are straightforward)
- Async wrapper can be added later if needed

## ADR-007: Entry Point Plugin Discovery

**Status**: Accepted

**Context**: Need plugin discovery without a central registry file.

**Decision**: Use `importlib.metadata.entry_points` under `chemengine.plugins` group.

**Consequences**:
- No central plugin list to maintain
- Plugins discovered automatically from installed packages
- Standard Python mechanism (no custom discovery)
- Plugin must be installed as a package

## ADR-008: Datasets as Files, Not Code

**Status**: Accepted

**Context**: Reference data (elements, isotopes, forcefields) needs to be versioned and updatable independently.

**Decision**: Store all reference data in JSON/TOML files in `datasets/` directory.

**Consequences**:
- Data updates without code changes
- Versioned datasets for reproducibility
- Plugin-contributed datasets
- Hot-reloading during development
- Slight I/O overhead on first access (mitigated by caching)

## ADR-009: ChemEngineAPI as Single Facade

**Status**: Accepted

**Context**: Need a single entry point for all consumers (AI, CLI, web, library).

**Decision**: ChemEngineAPI wraps registry, event bus, plugin manager, and datasets.

**Consequences**:
- Single import for all functionality
- Self-describing tools for AI agents
- Consistent error handling and logging
- Plugin injection point (plugins receive the API)
- Slight indirection for direct library users

## ADR-010: Correlation IDs for Pipeline Tracing

**Status**: Accepted

**Context**: Need to trace a molecule through multi-step pipelines for debugging and benchmarking.

**Decision**: Events carry optional correlation_id strings.

**Consequences**:
- Full pipeline traceability
- Easy debugging of complex operations
- Performance analysis across pipeline steps
- Optional overhead (None = no tracing)