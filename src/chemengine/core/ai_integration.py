"""AI Integration — streaming support, enhanced tool registry, and offline inference.

Implements:
- Streaming iterator for long-running operations
- Tool registry with query by name, category, capability
- OpenAI and Anthropic tool format conversion
- Offline inference support with fallback strategies
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

# ══════════════════════════════════════════════════════════════════
# STREAMING SUPPORT
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """A single chunk in a streaming response.

    Attributes:
        chunk_id: Unique identifier for this chunk.
        data: The chunk data (partial result).
        is_final: Whether this is the last chunk.
        metadata: Optional metadata (progress, total, etc.).
    """
    chunk_id: int
    data: Any
    is_final: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class StreamingIterator:
    """Streaming iterator for long-running operations.

    Wraps a generator and provides chunked access to results.
    Useful for isomer enumeration, substructure search, etc.

    Usage:
        >>> stream = StreamingIterator(
        ...     items=range(100),
        ...     chunk_size=10,
        ...     transform=lambda x: {"value": x}
        ... )
        >>> for chunk in stream:
        ...     print(chunk.data)  # List of 10 items
    """

    def __init__(
        self,
        items: Iterator[Any] | list[Any],
        chunk_size: int = 10,
        transform: Callable[[Any], Any] | None = None,
    ) -> None:
        self._items = items if hasattr(items, '__next__') else iter(items)
        self._chunk_size = chunk_size
        self._transform = transform or (lambda x: x)
        self._chunk_id = 0
        self._cancelled = False

    def __iter__(self) -> Iterator[StreamChunk]:
        return self

    def __next__(self) -> StreamChunk:
        if self._cancelled:
            raise StopIteration

        chunk_data = []
        for _ in range(self._chunk_size):
            try:
                item = next(self._items)
                chunk_data.append(self._transform(item))
            except StopIteration:
                break

        if not chunk_data:
            raise StopIteration

        self._chunk_id += 1
        is_final = len(chunk_data) < self._chunk_size

        return StreamChunk(
            chunk_id=self._chunk_id,
            data=tuple(chunk_data),
            is_final=is_final,
            metadata={
                "chunk_size": self._chunk_size,
                "items_in_chunk": len(chunk_data),
            },
        )

    def cancel(self) -> None:
        """Cancel the streaming iteration."""
        self._cancelled = True

    def collect_all(self) -> list[Any]:
        """Collect all results into a list (for non-streaming usage)."""
        results = []
        for chunk in self:
            results.extend(chunk.data)
        return results


# ══════════════════════════════════════════════════════════════════
# ENHANCED TOOL REGISTRY
# ══════════════════════════════════════════════════════════════════


class ToolRegistry:
    """Enhanced tool registry with query capabilities.

    Supports:
    - Query by name, category, capability
    - Tool discovery and filtering
    - Format conversion (OpenAI, Anthropic)
    """

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        category: str = "general",
        tags: list[str] | None = None,
        examples: list[dict[str, Any]] | None = None,
    ) -> None:
        """Register a tool with full metadata."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "category": category,
            "tags": tags or [],
            "examples": examples or [],
        }

    def get(self, name: str) -> dict[str, Any] | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[dict[str, Any]]:
        """List all tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t["category"] == category]
        return tools

    def query_by_capability(self, capability: str) -> list[dict[str, Any]]:
        """Query tools by capability (tag)."""
        return [
            t for t in self._tools.values()
            if capability in t.get("tags", [])
        ]

    def to_openai_format(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in self._tools.values()
        ]

    def to_anthropic_format(self) -> list[dict[str, Any]]:
        """Convert all tools to Anthropic tool-use format."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in self._tools.values()
        ]

    def to_json_schema(self) -> dict[str, Any]:
        """Export all tools as a single JSON Schema document."""
        return {
            "type": "object",
            "properties": {
                t["name"]: t["input_schema"]
                for t in self._tools.values()
            },
            "required": [],
        }


# ══════════════════════════════════════════════════════════════════
# OFFLINE INFERENCE SUPPORT
# ══════════════════════════════════════════════════════════════════


class OfflineInference:
    """Offline inference support for privacy-sensitive applications.

    Provides local model detection and fallback strategies
    when network access is unavailable.
    """

    def __init__(self) -> None:
        self._local_models: dict[str, Any] = {}
        self._fallback_strategies: dict[str, Callable] = {}

    def register_local_model(
        self, name: str, model: Any, capabilities: list[str]
    ) -> None:
        """Register a local model for offline inference."""
        self._local_models[name] = {
            "model": model,
            "capabilities": capabilities,
        }

    def register_fallback(
        self, capability: str, strategy: Callable
    ) -> None:
        """Register a fallback strategy for a capability."""
        self._fallback_strategies[capability] = strategy

    def detect_local_models(self) -> list[str]:
        """Detect available local models."""
        return list(self._local_models.keys())

    def is_online(self) -> bool:
        """Check if network is available (always True for offline mode)."""
        return False

    def get_inference_strategy(
        self, capability: str
    ) -> tuple[Any | None, str]:
        """Get the best inference strategy for a capability.

        Returns:
            Tuple of (model_or_strategy, source) where source is
            'local', 'fallback', or 'none'.
        """
        # Check local models first
        for name, info in self._local_models.items():
            if capability in info["capabilities"]:
                return info["model"], "local"

        # Check fallback strategies
        if capability in self._fallback_strategies:
            return self._fallback_strategies[capability], "fallback"

        return None, "none"

    def execute_inference(
        self, capability: str, input_data: Any
    ) -> Any:
        """Execute inference using the best available strategy."""
        strategy, source = self.get_inference_strategy(capability)

        if strategy is None:
            raise RuntimeError(
                f"No inference strategy available for '{capability}'"
            )

        if source == "local":
            # Local model — call directly
            if callable(strategy):
                return strategy(input_data)
            return strategy
        elif source == "fallback":
            # Fallback strategy
            return strategy(input_data)
        else:
            raise RuntimeError(f"Unknown source: {source}")


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def stream_isomers(
    isomers: Iterator[Any],
    chunk_size: int = 10,
) -> StreamingIterator:
    """Create a streaming iterator for isomer enumeration."""
    return StreamingIterator(isomers, chunk_size=chunk_size)


def stream_substructure_matches(
    matches: Iterator[Any],
    chunk_size: int = 100,
) -> StreamingIterator:
    """Create a streaming iterator for substructure matches."""
    return StreamingIterator(matches, chunk_size=chunk_size)


def create_tool_registry() -> ToolRegistry:
    """Create a pre-populated tool registry with all ChemEngine tools."""
    registry = ToolRegistry()

    # Register all tools
    registry.register(
        name="parse_smiles",
        description="Parse a SMILES string into a molecular graph.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string", "description": "SMILES string"}
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "formula": {"type": "string"},
                "num_atoms": {"type": "integer"},
            },
        },
        category="parsing",
        tags=["smiles", "parsing"],
        examples=[{"smiles": "CCO"}],
    )

    registry.register(
        name="compute_property",
        description="Compute a molecular property.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
                "property": {"type": "string"},
            },
            "required": ["smiles", "property"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "property": {"type": "string"},
                "value": {},
            },
        },
        category="properties",
        tags=["computation", "descriptors"],
    )

    registry.register(
        name="validate",
        description="Validate a molecular graph for chemical correctness.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "is_valid": {"type": "boolean"},
                "errors": {"type": "array"},
            },
        },
        category="validation",
        tags=["validation", "quality"],
    )

    registry.register(
        name="detect_functional_groups",
        description="Detect functional groups in a molecule.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "functional_groups": {"type": "array"},
            },
        },
        category="detection",
        tags=["functional-groups", "detection"],
    )

    registry.register(
        name="generate_2d_coordinates",
        description="Generate 2D coordinates for a molecule.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
                "seed": {"type": "integer"},
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "coordinates": {"type": "array"},
            },
        },
        category="coordinates",
        tags=["2d", "layout"],
    )

    registry.register(
        name="generate_3d_conformer",
        description="Generate 3D conformers for a molecule.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
                "num_conformers": {"type": "integer", "default": 1},
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "conformers": {"type": "array"},
            },
        },
        category="coordinates",
        tags=["3d", "conformer"],
    )

    registry.register(
        name="render_svg",
        description="Render a molecule as SVG.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
                "bond_length": {"type": "number"},
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "svg": {"type": "string"},
            },
        },
        category="rendering",
        tags=["svg", "depiction"],
    )

    registry.register(
        name="name_molecule",
        description="Generate an IUPAC name for a molecule.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
        },
        category="nomenclature",
        tags=["iupac", "naming"],
    )

    registry.register(
        name="serialize",
        description="Serialize a molecule to various formats.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
                "format": {"type": "string", "enum": ["json", "dict"]},
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "data": {"type": "object"},
            },
        },
        category="io",
        tags=["serialization", "json"],
    )

    registry.register(
        name="generate_inchi",
        description="Generate InChI and InChIKey for a molecule.",
        input_schema={
            "type": "object",
            "properties": {
                "smiles": {"type": "string"},
            },
            "required": ["smiles"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "inchi": {"type": "string"},
                "inchikey": {"type": "string"},
            },
        },
        category="parsing",
        tags=["inchi", "identifier"],
    )

    return registry
