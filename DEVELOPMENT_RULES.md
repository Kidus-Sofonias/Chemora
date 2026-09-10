# ChemEngine Development Rules

## Code Standards

1. **Type hints required** — Every public function must have full type annotations. Use `from __future__ import annotations` for forward references.

2. **Immutability** — Domain models must be `@dataclass(frozen=True, slots=True)`. No mutation of input objects. Use the Builder pattern for construction.

3. **MolecularGraph is the single source of truth** — No intermediate molecule representations. All parsers produce `MolecularGraph` directly.

4. **Error handling** — Use `ValueError` for invalid input, `KeyError` for missing lookups, `NotImplementedError` for planned-but-unimplemented features. Never use bare `assert` for validation.

5. **Logging** — Use `structlog` via `chemengine.utils.logging.get_logger()`. Always include context.

6. **Documentation** — All public API has Google-style docstrings. Module-level docstrings explain purpose and design decisions.

## Architecture Rules

7. **Dependency direction** — `core/` depends on nothing. All other packages depend on `core/`. No circular imports.

8. **Algorithm registration** — Every algorithm registers with `AlgorithmRegistry`. No direct imports of algorithm implementation functions.

9. **Plugin support** — Extensions use `importlib.metadata.entry_points` under `chemengine.plugins`. No hardcoded plugin lists.

10. **Event-driven communication** — Use `EventBus` for cross-module communication. Direct imports between subsystems are discouraged.

## Testing Rules

11. **Every public function has tests** — Aim for >90% coverage on core, >80% overall.

12. **Round-trip tests** — Parsers must have round-trip property-based tests (parse → serialize → re-parse → compare).

13. **Edge cases** — Test empty strings, unusual characters, extreme values, and error paths.

## Naming Conventions

- `snake_case` for functions, methods, variables
- `PascalCase` for classes, enums, protocols
- `UPPER_CASE` for constants
- Leading `_` for private/internal (not exported in `__all__`)

## Git Conventions

- Feature branches from `main`
- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`
- Squash merges to main
- CHANGELOG.md updated with each release
