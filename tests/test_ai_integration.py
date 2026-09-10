"""Tests for Phase 13: AI Integration — streaming, tool registry, offline inference.
"""

import pytest

from chemengine.core.ai_integration import (
    OfflineInference,
    StreamingIterator,
    ToolRegistry,
    create_tool_registry,
    stream_isomers,
)
from chemengine.generation.constitutional import generate_alkane_isomers

# ══════════════════════════════════════════════════════════════════
# STREAMING TESTS
# ══════════════════════════════════════════════════════════════════


class TestStreamingIterator:
    """Tests for StreamingIterator."""

    def test_basic_streaming(self):
        """Basic streaming produces correct chunks."""
        stream = StreamingIterator(items=[1, 2, 3, 4, 5], chunk_size=2)
        chunks = list(stream)
        assert len(chunks) == 3  # [1,2], [3,4], [5]
        assert chunks[0].data == (1, 2)
        assert chunks[1].data == (3, 4)
        assert chunks[2].data == (5,)
        assert chunks[2].is_final is True

    def test_streaming_with_transform(self):
        """Streaming with transform function."""
        stream = StreamingIterator(
            items=[1, 2, 3],
            chunk_size=2,
            transform=lambda x: x * 2,
        )
        chunks = list(stream)
        assert chunks[0].data == (2, 4)
        assert chunks[1].data == (6,)

    def test_streaming_cancel(self):
        """Streaming can be cancelled."""
        stream = StreamingIterator(items=range(100), chunk_size=5)
        chunks = []
        for chunk in stream:
            chunks.append(chunk)
            if chunk.chunk_id >= 2:
                stream.cancel()
        assert len(chunks) <= 3

    def test_streaming_collect_all(self):
        """collect_all returns all items."""
        stream = StreamingIterator(items=[1, 2, 3, 4, 5], chunk_size=2)
        result = stream.collect_all()
        assert result == [1, 2, 3, 4, 5]

    def test_streaming_empty(self):
        """Streaming empty iterator produces no chunks."""
        stream = StreamingIterator(items=[], chunk_size=10)
        chunks = list(stream)
        assert len(chunks) == 0

    def test_streaming_single_chunk(self):
        """All items fit in one chunk."""
        stream = StreamingIterator(items=[1, 2, 3], chunk_size=10)
        chunks = list(stream)
        assert len(chunks) == 1
        assert chunks[0].is_final is True


# ══════════════════════════════════════════════════════════════════
# TOOL REGISTRY TESTS
# ══════════════════════════════════════════════════════════════════


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get(self):
        """Register and retrieve a tool."""
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        tool = registry.get("test_tool")
        assert tool is not None
        assert tool["name"] == "test_tool"

    def test_list_tools(self):
        """List all tools."""
        registry = ToolRegistry()
        registry.register(
            name="tool1", description="T1",
            input_schema={}, output_schema={}, category="parsing",
        )
        registry.register(
            name="tool2", description="T2",
            input_schema={}, output_schema={}, category="detection",
        )
        all_tools = registry.list_tools()
        assert len(all_tools) == 2

    def test_list_tools_by_category(self):
        """Filter tools by category."""
        registry = ToolRegistry()
        registry.register(
            name="tool1", description="T1",
            input_schema={}, output_schema={}, category="parsing",
        )
        registry.register(
            name="tool2", description="T2",
            input_schema={}, output_schema={}, category="detection",
        )
        parsing = registry.list_tools(category="parsing")
        assert len(parsing) == 1
        assert parsing[0]["name"] == "tool1"

    def test_query_by_capability(self):
        """Query tools by capability (tag)."""
        registry = ToolRegistry()
        registry.register(
            name="tool1", description="T1",
            input_schema={}, output_schema={},
            tags=["smiles", "parsing"],
        )
        results = registry.query_by_capability("smiles")
        assert len(results) == 1

    def test_to_openai_format(self):
        """Convert to OpenAI function-calling format."""
        registry = create_tool_registry()
        openai = registry.to_openai_format()
        assert len(openai) > 0
        assert openai[0]["type"] == "function"
        assert "function" in openai[0]

    def test_to_anthropic_format(self):
        """Convert to Anthropic tool-use format."""
        registry = create_tool_registry()
        anthropic = registry.to_anthropic_format()
        assert len(anthropic) > 0
        assert "name" in anthropic[0]
        assert "input_schema" in anthropic[0]

    def test_to_json_schema(self):
        """Export as JSON Schema."""
        registry = create_tool_registry()
        schema = registry.to_json_schema()
        assert schema["type"] == "object"
        assert "properties" in schema


# ══════════════════════════════════════════════════════════════════
# OFFLINE INFERENCE TESTS
# ══════════════════════════════════════════════════════════════════


class TestOfflineInference:
    """Tests for OfflineInference."""

    def test_register_local_model(self):
        """Register a local model."""
        inference = OfflineInference()
        inference.register_local_model("my_model", "mock_model", ["parsing"])
        models = inference.detect_local_models()
        assert "my_model" in models

    def test_register_fallback(self):
        """Register a fallback strategy."""
        inference = OfflineInference()
        inference.register_fallback("parsing", lambda x: "fallback_result")
        strategy, source = inference.get_inference_strategy("parsing")
        assert source == "fallback"

    def test_local_model_preferred(self):
        """Local model is preferred over fallback."""
        inference = OfflineInference()
        inference.register_local_model("local", lambda x: "local", ["parsing"])
        inference.register_fallback("parsing", lambda x: "fallback")
        strategy, source = inference.get_inference_strategy("parsing")
        assert source == "local"

    def test_execute_inference(self):
        """Execute inference with local model."""
        inference = OfflineInference()
        inference.register_local_model(
            "adder", lambda x: x + 1, ["increment"]
        )
        result = inference.execute_inference("increment", 5)
        assert result == 6

    def test_no_strategy_raises(self):
        """No strategy available raises RuntimeError."""
        inference = OfflineInference()
        with pytest.raises(RuntimeError, match="No inference strategy"):
            inference.execute_inference("unknown", None)

    def test_is_online_returns_false(self):
        """Offline mode always reports offline."""
        inference = OfflineInference()
        assert inference.is_online() is False


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION TESTS
# ══════════════════════════════════════════════════════════════════


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_stream_isomers(self):
        """stream_isomers creates a streaming iterator."""
        isomers = generate_alkane_isomers(4)
        stream = stream_isomers(iter(isomers), chunk_size=2)
        chunks = list(stream)
        assert len(chunks) == 1  # 2 isomers fit in one chunk

    def test_create_tool_registry(self):
        """create_tool_registry returns a populated registry."""
        registry = create_tool_registry()
        tools = registry.list_tools()
        assert len(tools) >= 10  # At least 10 tools registered
        names = [t["name"] for t in tools]
        assert "parse_smiles" in names
        assert "validate" in names
        assert "render_svg" in names
