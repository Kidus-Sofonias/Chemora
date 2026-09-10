"""Regression tests for the group-aware molecular formula parser.

Covers (correctness gate, Phase A/G):
    - simple formulas
    - parenthesized groups (Mg(OH)2, Fe2(SO4)3, Al2(SO4)3, Ca(OH)2, (NH4)2SO4)
    - nested groups
    - hydrates (dot and star separators, leading multipliers)
    - charged formulas
    - whitespace handling
    - malformed formulas (structured FormulaParseError, nothing silently dropped)
    - downstream molecular formula / mass behavior via formula_to_graph
"""

import pytest

from chemengine.parsing.errors import FormulaParseError
from chemengine.parsing.formula import formula_to_graph, parse_formula, parse_formula_parts


def as_symbols(counts: dict) -> dict[str, int]:
    """Convert an ElementSymbol-keyed dict to a plain-str dict."""
    return {s.value: n for s, n in counts.items()}


class TestGateExamples:
    """The exact examples required by the correctness gate."""

    @pytest.mark.parametrize(
        "formula,expected",
        [
            ("Mg(OH)2", {"Mg": 1, "O": 2, "H": 2}),
            ("Fe2(SO4)3", {"Fe": 2, "S": 3, "O": 12}),
            ("Al2(SO4)3", {"Al": 2, "S": 3, "O": 12}),
            ("Ca(OH)2", {"Ca": 1, "O": 2, "H": 2}),
            ("(NH4)2SO4", {"N": 2, "H": 8, "S": 1, "O": 4}),
        ],
    )
    def test_gate_examples(self, formula, expected):
        assert as_symbols(parse_formula(formula)) == expected

    def test_simple(self):
        assert as_symbols(parse_formula("H2O")) == {"H": 2, "O": 1}
        assert as_symbols(parse_formula("NaCl")) == {"Na": 1, "Cl": 1}
        assert as_symbols(parse_formula("CH4")) == {"C": 1, "H": 4}
        assert as_symbols(parse_formula("C5H12")) == {"C": 5, "H": 12}

    def test_multi_digit_counts(self):
        assert as_symbols(parse_formula("C12H22O11")) == {"C": 12, "H": 22, "O": 11}


class TestNestedGroups:
    def test_double_nested(self):
        counts = parse_formula("Ca(Al(OH)4)2")
        assert as_symbols(counts) == {"Ca": 1, "Al": 2, "O": 8, "H": 8}

    def test_nested_with_multiplier(self):
        counts = parse_formula("Mg2(Fe(CN)6)3")
        assert as_symbols(counts) == {"Mg": 2, "Fe": 3, "C": 18, "N": 18}


class TestHydrates:
    def test_copper_sulfate_pentahydrate(self):
        counts = parse_formula("CuSO4.5H2O")
        assert as_symbols(counts) == {"Cu": 1, "S": 1, "O": 9, "H": 10}

    def test_star_separator(self):
        counts = parse_formula("CuSO4*5H2O")
        assert as_symbols(counts) == {"Cu": 1, "S": 1, "O": 9, "H": 10}

    def test_magnesium_sulfate_heptahydrate(self):
        counts = parse_formula("MgSO4.7H2O")
        assert as_symbols(counts) == {"Mg": 1, "S": 1, "O": 11, "H": 14}

    def test_sodium_carbonate_decahydrate(self):
        counts = parse_formula("Na2CO3.10H2O")
        assert as_symbols(counts) == {"Na": 2, "C": 1, "O": 13, "H": 20}


class TestChargedFormulas:
    def test_ammonium(self):
        counts, charge = parse_formula_parts("NH4+")
        assert as_symbols(counts) == {"N": 1, "H": 4}
        assert charge == 1

    def test_sulfate_caret(self):
        counts, charge = parse_formula_parts("SO4^2-")
        assert as_symbols(counts) == {"S": 1, "O": 4}
        assert charge == -2

    def test_sulfate_space(self):
        counts, charge = parse_formula_parts("SO4 2-")
        assert as_symbols(counts) == {"S": 1, "O": 4}
        assert charge == -2

    def test_iron_sign_first(self):
        counts, charge = parse_formula_parts("Fe+3")
        assert as_symbols(counts) == {"Fe": 1}
        assert charge == 3

    def test_calcium_space(self):
        counts, charge = parse_formula_parts("Ca 2+")
        assert as_symbols(counts) == {"Ca": 1}
        assert charge == 2


class TestWhitespace:
    def test_surrounding_whitespace(self):
        assert as_symbols(parse_formula("  H2O  ")) == {"H": 2, "O": 1}


class TestMalformedFormulas:
    """Invalid syntax must raise FormulaParseError — nothing silently dropped."""

    @pytest.mark.parametrize(
        "formula",
        [
            "",                      # empty
            "   ",                   # whitespace only
            "Xx",                    # unknown element
            "Mg(OH",                 # unmatched '('
            "Mg(OH)2(",              # unmatched '('
            "C((",                   # unmatched '('
            "H2O)",                  # stray ')'
            "H2OO)",                 # stray ')'
            "CuSO4.",                # dangling dot
            ".5H2O",                 # leading dot
            "13CO2",                 # isotope prefix (not in spec)
            "C2H6O!",                # invalid character
            "H2O;NaCl",              # invalid character
            "5H2O",                  # leading multiplier on main component
            "NH4++",                 # double charge sign
        ],
    )
    def test_raises_structured_error(self, formula):
        with pytest.raises(FormulaParseError):
            parse_formula(formula)

    def test_error_is_valueerror(self):
        # FormulaParseError must remain a ValueError subclass so existing
        # `except ValueError` call sites keep working.
        with pytest.raises(ValueError):
            parse_formula("Xx")

    def test_error_carries_position(self):
        with pytest.raises(FormulaParseError) as exc_info:
            parse_formula("H2Oq")
        assert exc_info.value.pos is not None
        assert exc_info.value.formula == "H2Oq"


class TestFormulaToGraphDownstream:
    """Downstream molecular formula / mass behavior."""

    def test_methane_graph(self):
        graph = formula_to_graph("CH4")
        assert graph.molecular_formula == "CH4"
        assert graph.num_atoms == 5
        assert graph.num_bonds == 4

    def test_water_connectivity(self):
        graph = formula_to_graph("H2O")
        assert graph.molecular_formula == "H2O"
        assert graph.num_bonds == 2  # both H bonded to O

    def test_parenthesized_group_counts(self):
        graph = formula_to_graph("Mg(OH)2")
        assert graph.molecular_formula == "H2MgO2"
        assert graph.num_atoms == 5

    def test_gate_group_formula_mass(self):
        # Fe2(SO4)3: 2*55.845 + 3*32.06 + 12*15.999 (average masses)
        graph = formula_to_graph("Fe2(SO4)3")
        expected = 2 * 55.845 + 3 * 32.06 + 12 * 15.999
        assert graph.molecular_weight == pytest.approx(expected, rel=1e-3)

    def test_hydrate_counts(self):
        graph = formula_to_graph("CuSO4.5H2O")
        assert graph.num_atoms == 1 + 1 + 9 + 10

    def test_exact_mass_water(self):
        graph = formula_to_graph("H2O")
        # Monoisotopic: 2*1.00782503 + 15.99491462
        assert graph.exact_mass == pytest.approx(18.01056468, rel=1e-6)

    def test_custom_name(self):
        graph = formula_to_graph("C5H12", name="pentane")
        assert graph.name == "pentane"

    def test_hill_ordering(self):
        graph = formula_to_graph("C2H5OH")
        assert graph.molecular_formula == "C2H6O"
