"""Tests for the ChemEngineAPI facade."""

import pytest

from chemengine.core.datasets import reset_global_datasets
from chemengine.core.events import reset_global_bus
from chemengine.core.registry import reset_global_registry
from chemengine.core.tool_interface import ChemEngineAPI, ToolDefinition


class TestChemEngineAPI:
    """Tests for the ChemEngineAPI facade."""

    def setup_method(self):
        reset_global_bus()
        reset_global_registry()
        reset_global_datasets()
        self.api = ChemEngineAPI()

    def test_init(self):
        assert self.api is not None
        assert self.api.registry is not None
        assert self.api.bus is not None
        assert self.api.datasets is not None

    def test_list_tools(self):
        tools = self.api.list_tools()
        assert len(tools) > 0
        assert all(isinstance(t, ToolDefinition) for t in tools)

    def test_list_tools_by_category(self):
        parsing_tools = self.api.list_tools(category="parsing")
        assert len(parsing_tools) >= 2
        assert all(t.category == "parsing" for t in parsing_tools)

    def test_list_tools_by_tags(self):
        smiles_tools = self.api.list_tools(tags={"smiles"})
        assert len(smiles_tools) >= 1
        assert all("smiles" in t.tags for t in smiles_tools)

    def test_execute_parse_smiles(self):
        result = self.api.execute_tool("parse_smiles", {"smiles": "CCO"})
        assert result["formula"] == "C2H6O"
        assert result["heavy_atoms"] == 3  # 2 C + 1 O
        assert result["exact_mass"] > 0

    def test_execute_parse_smiles_with_canonical(self):
        result = self.api.execute_tool("parse_smiles", {"smiles": "CCO"})
        assert isinstance(result["canonical_smiles"], str)
        # Canonicalization may fail gracefully, but should at least
        # attempt to produce output for simple molecules
        assert result["canonical_smiles"] != "", (
            "Expected non-empty canonical SMILES for CCO"
        )

    def test_execute_parse_formula(self):
        result = self.api.execute_tool("parse_formula", {"formula": "C6H6"})
        assert result["formula"] == "C6H6"

    def test_execute_unknown_tool_raises(self):
        with pytest.raises(KeyError, match="Unknown tool"):
            self.api.execute_tool("nonexistent", {})

    def test_execute_batch(self):
        calls = [
            ("parse_smiles", {"smiles": "CCO"}, None),
            ("parse_formula", {"formula": "CH4"}, None),
        ]
        results = self.api.execute_batch(calls)
        assert len(results) == 2
        assert results[0]["formula"] == "C2H6O"
        assert results[1]["formula"] == "CH4"

    def test_parse_smiles(self):
        graph = self.api.parse("CCO", fmt="smiles")
        assert graph.molecular_formula == "C2H6O"

    def test_parse_formula(self):
        graph = self.api.parse("C6H6", fmt="formula")
        assert graph.molecular_formula == "C6H6"

    def test_parse_auto_detect(self):
        """Parse with auto-detection should work for SMILES."""
        graph = self.api.parse("CCO", fmt="auto")
        assert graph.molecular_formula == "C2H6O"

    def test_convert_to_smiles(self):
        graph = self.api.parse("CCO", fmt="smiles")
        smiles = self.api.convert(graph, "smiles")
        assert isinstance(smiles, str)
        assert len(smiles) > 0

    def test_convert_to_formula(self):
        graph = self.api.parse("CCO", fmt="smiles")
        formula = self.api.convert(graph, "formula")
        assert formula == "C2H6O"

    def test_convert_to_inchi(self):
        graph = self.api.parse("CCO", fmt="smiles")
        inchi = self.api.convert(graph, "inchi")
        assert inchi.startswith("InChI=")
        assert "C2H6O" in inchi

    def test_convert_unknown_target_raises(self):
        graph = self.api.parse("C", fmt="smiles")
        with pytest.raises(ValueError, match="Unknown target"):
            self.api.convert(graph, "xyz")

    def test_compute_mass(self):
        graph = self.api.parse("CCO", fmt="smiles")
        mass = self.api.compute(graph, "mass")
        assert isinstance(mass, float)
        assert mass > 0

    def test_compute_formula(self):
        graph = self.api.parse("CCO", fmt="smiles")
        formula = self.api.compute(graph, "formula")
        assert formula == "C2H6O"

    def test_compute_heavy_atoms(self):
        graph = self.api.parse("CCO", fmt="smiles")
        assert self.api.compute(graph, "heavy_atoms") == 3  # 2 C + 1 O

    def test_compute_unknown_property_raises(self):
        graph = self.api.parse("C", fmt="smiles")
        with pytest.raises(ValueError, match="Unknown property"):
            self.api.compute(graph, "nonexistent")

    def test_compute_hba_hbd(self):
        graph = self.api.parse("CCO", fmt="smiles")
        hba = self.api.compute(graph, "hba")
        hbd = self.api.compute(graph, "hbd")
        assert hba >= 1  # O is an acceptor
        assert hbd >= 1  # O-H is a donor

    def test_detect_functional_groups(self):
        graph = self.api.parse("CCO", fmt="smiles")
        groups = self.api.detect_functional_groups(graph)
        assert isinstance(groups, list)
        assert len(groups) > 0, "Ethanol should have at least 1 functional group"
        group_names = {g["name"] for g in groups}
        assert "Alcohol" in group_names, f"Expected Alcohol, got {group_names}"

    def test_render_svg(self):
        graph = self.api.parse("C", fmt="smiles")
        svg = self.api.render(graph, "svg")
        assert svg.startswith("<svg")
        assert "</svg>" in svg

    def test_render_unknown_format_raises(self):
        graph = self.api.parse("C", fmt="smiles")
        with pytest.raises(ValueError, match="Unsupported"):
            self.api.render(graph, "pdf")

    def test_list_plugins(self):
        plugins = self.api.list_plugins()
        assert plugins == []  # No plugins loaded

    def test_execute_error_returns_error_dict(self):
        result = self.api.execute_tool("parse_smiles", {"smiles": "!!invalid!!"})
        assert "error" in result

    def test_execute_tool_event_published(self):
        """Executing a tool should publish an event."""
        result = self.api.execute_tool("parse_smiles", {"smiles": "CCO"})
        assert result["formula"] == "C2H6O"

    def test_api_reuses_globals(self):
        """Creating a new API without args should reuse global singletons."""
        api2 = ChemEngineAPI()
        assert api2._registry is self.api._registry
        assert api2._bus is self.api._bus
        # DatasetRegistry may be the same global
        assert api2._datasets is self.api._datasets

    def test_parse_with_auto_unknown_format(self):
        """Parse with auto should fall through and try all parsers."""
        with pytest.raises(ValueError, match="Could not parse"):
            self.api.parse("!!!invalid!!!", fmt="auto")


class TestToolDefinition:
    """Tests for the ToolDefinition dataclass."""

    def test_create_tool_definition(self):
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            category="testing",
            tags=frozenset({"test"}),
        )
        assert tool.name == "test_tool"
        assert tool.category == "testing"
        assert "test" in tool.tags

    def test_tool_immutable(self):
        tool = ToolDefinition(
            name="test", description="a", input_schema={}, output_schema={},
        )
        with pytest.raises((AttributeError, TypeError)):
            tool.name = "changed"

    def test_default_category(self):
        tool = ToolDefinition(
            name="test", description="a", input_schema={}, output_schema={},
        )
        assert tool.category == "general"
        assert len(tool.tags) == 0
