"""Correctness gate tests — Phases D & E.

Covers:
    - parse_any() routing: valid / invalid / ambiguous / empty / unsupported
    - AI tool audit: all 13 exposed tools have real implementations whose
      behavior matches their declared JSON Schemas.
"""

import pytest

from chemengine.core.tool_interface import ChemEngineAPI
from chemengine.parsing.protocol import parse_any


@pytest.fixture
def api() -> ChemEngineAPI:
    return ChemEngineAPI()


# ── Phase D: parse_any routing ──


class TestParseAny:
    def test_smiles(self):
        assert parse_any("CCO").molecular_formula == "C2H6O"

    def test_inchi(self):
        g = parse_any("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3")
        assert g.molecular_formula == "C2H6O"

    def test_formula(self):
        assert parse_any("H2O").molecular_formula == "H2O"

    def test_formula_with_parens_routes_to_formula(self):
        g = parse_any("Mg(OH)2")
        assert g.molecular_formula == "H2MgO2"

    def test_name(self):
        g = parse_any("ethanol")
        assert g.molecular_formula == "C2H6O"

    def test_inchikey_fails_clearly(self):
        with pytest.raises(ValueError, match="InChIKey"):
            parse_any("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            parse_any("")

    def test_malformed_input_raises(self):
        with pytest.raises(ValueError):
            parse_any("C((((([")

    def test_malformed_never_returns_empty_graph(self):
        # Malformed input must not silently produce a useless graph.
        with pytest.raises(ValueError):
            parse_any("][)(***")

    def test_deterministic(self):
        results = {parse_any("CCO").molecular_formula for _ in range(5)}
        assert results == {"C2H6O"}


class TestAPIParse:
    def test_parse_smiles_and_formula(self, api):
        assert api.parse("CCO", fmt="smiles").molecular_formula == "C2H6O"
        assert api.parse("H2O", fmt="formula").molecular_formula == "H2O"

    def test_parse_auto_uses_parse_any(self, api):
        assert api.parse("CCO").molecular_formula == "C2H6O"
        assert api.parse("Mg(OH)2").molecular_formula == "H2MgO2"

    def test_parse_invalid_raises(self, api):
        with pytest.raises(ValueError):
            api.parse("This Is Not A Molecule!!")


# ── Phase E: AI tool audit ──


EXPECTED_TOOLS = {
    "parse_smiles", "parse_formula", "compute_property", "validate",
    "sanitize", "detect_functional_groups", "generate_2d_coordinates",
    "generate_3d_conformer", "render_svg", "name_molecule", "generate_inchi",
    "serialize", "calculate_electron_configuration",
}


class TestToolAudit:
    def test_thirteen_tools_registered(self, api):
        names = {t.name for t in api.list_tools()}
        assert names == EXPECTED_TOOLS

    @pytest.mark.parametrize(
        "tool,params",
        [
            ("parse_smiles", {"smiles": "CCO"}),
            ("parse_formula", {"formula": "H2O"}),
            ("compute_property", {"smiles": "CCO",
                                  "properties": ["mass", "logp", "tpsa",
                                                 "hba", "hbd", "fraction_csp3"]}),
            ("validate", {"smiles": "CCO"}),
            ("sanitize", {"smiles": "CCO"}),
            ("detect_functional_groups", {"smiles": "CC(=O)O"}),
            ("generate_2d_coordinates", {"smiles": "CCO"}),
            ("generate_3d_conformer", {"smiles": "CCO", "num_conformers": 1}),
            ("render_svg", {"smiles": "CCO"}),
            ("name_molecule", {"smiles": "CCO"}),
            ("generate_inchi", {"smiles": "CCO"}),
            ("serialize", {"smiles": "CCO"}),
            ("calculate_electron_configuration", {"element": "Fe"}),
        ],
    )
    def test_tool_executes(self, api, tool, params):
        result = api.execute_tool(tool, params)
        assert "error" not in result, f"{tool} failed: {result.get('error')}"

    def test_every_tool_has_schema_and_impl(self, api):
        for tool in api.list_tools():
            assert tool.input_schema.get("type") == "object"
            assert tool.output_schema.get("type") == "object"
            assert tool.description
            # Implementation must exist (execute raises otherwise)
            assert hasattr(api, f"_exec_{tool.name}"), tool.name

    def test_compute_property_schema_lists_real_properties(self, api):
        tool = {t.name: t for t in api.list_tools()}["compute_property"]
        desc = tool.input_schema["properties"]["properties"]["description"]
        for prop in ("mass", "logp", "tpsa", "fraction_csp3", "hba", "hbd",
                     "rotatable_bonds", "num_rings"):
            assert prop in desc, f"{prop} missing from compute_property schema"

    def test_unknown_tool_error(self, api):
        with pytest.raises(KeyError, match="Available tools"):
            api.execute_tool("nonexistent", {})

    def test_calculate_electron_configuration_output(self, api):
        result = api.execute_tool("calculate_electron_configuration", {"element": "Fe"})
        assert result["atomic_number"] == 26
        assert result["symbol"] == "Fe"
        assert result["shorthand"] == "[Ar] 3d6 4s2"

    def test_generate_inchi_output(self, api):
        result = api.execute_tool("generate_inchi", {"smiles": "CCO"})
        assert result["inchi"].startswith("InChI=")
        assert len(result["inchikey"]) == 27
