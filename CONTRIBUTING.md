# Contributing to ChemEngine

Thank you for your interest in contributing to ChemEngine! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/chemengine.git
   cd chemengine
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify setup**
   ```bash
   pytest tests/ -v
   ```

## Code Style

- Follow PEP 8 with 100-character line limit
- Use type hints for all public functions and methods
- Docstrings should follow Google convention
- Run `ruff` before committing: `ruff check src/`

## Testing

- All new code must include tests
- Run the full test suite: `pytest`
- With coverage: `pytest --cov=chemengine`
- Property-based tests with Hypothesis are encouraged for parsers

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Ensure all tests pass and coverage doesn't decrease
4. Update documentation if needed
5. Submit a pull request with a clear description

## Architecture Constraints

- **MolecularGraph is the single source of truth**: No alternative molecule representations
- **Domain models are immutable**: Use the Builder pattern for mutations
- **All algorithms register with AlgorithmRegistry**: No direct imports of algorithm functions
- **Dependency direction**: `core/` → everything else (never the reverse)
- **Plugins use entry points**: Register under `chemengine.plugins` group

## Adding a New Algorithm

1. Implement the algorithm function/class
2. Create an `AlgorithmEntry` and register it
3. Add a `ToolDefinition` to `ChemEngineAPI` if it should be exposed to AI agents
4. Write tests
5. Add documentation
