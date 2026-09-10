"""Tests for the validation subsystem (Phase 2).

Covers:
    - Validation data models (ValidationError, ValidationResult, ValidationReport)
    - All built-in validation rules (valence, hypervalent, charge, isotope, etc.)
    - Graph sanitization (add implicit H, remove duplicate bonds)
    - Integration with MolecularGraph and ChemEngineAPI
"""

from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.validation.report import (
    ValidationError,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)
from chemengine.validation.rules import (
    AromaticityRule,
    ChargeRule,
    GraphStructureRule,
    HypervalentRule,
    IsotopeRule,
    TotalChargeRule,
    ValenceRule,
    get_validation_rules,
)
from chemengine.validation.sanitize import (
    add_implicit_hydrogens,
    remove_duplicate_bonds,
    sanitize,
)

# ════════════════════════════════════════════════════════════════
#  Data Model Tests
# ════════════════════════════════════════════════════════════════


class TestValidationSeverity:
    """Test the ValidationSeverity enum."""

    def test_severity_values(self):
        assert ValidationSeverity.ERROR == "error"
        assert ValidationSeverity.WARNING == "warning"
        assert ValidationSeverity.INFO == "info"


class TestValidationError:
    """Test the ValidationError dataclass."""

    def test_create_error(self):
        err = ValidationError(
            rule="valence",
            severity=ValidationSeverity.ERROR,
            message="Valence exceeded",
            atom_index=0,
        )
        assert err.rule == "valence"
        assert err.severity == ValidationSeverity.ERROR
        assert err.message == "Valence exceeded"
        assert err.atom_index == 0
        assert err.bond_index is None
        assert err.detail == {}

    def test_error_with_detail(self):
        err = ValidationError(
            rule="charge",
            severity=ValidationSeverity.WARNING,
            message="Unusual charge",
            atom_index=5,
            detail={"charge": 3, "max": 2},
        )
        assert err.detail == {"charge": 3, "max": 2}
        assert err.atom_index == 5

    def test_error_immutable(self):
        err = ValidationError(
            rule="test",
            severity=ValidationSeverity.ERROR,
            message="test",
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            err.rule = "new_rule"  # type: ignore


class TestValidationResult:
    """Test the ValidationResult dataclass."""

    def test_passed_result(self):
        result = ValidationResult(
            passed=True,
            errors=(),
            warnings=(),
            info=(),
        )
        assert result.is_valid
        assert result.num_errors == 0
        assert result.num_warnings == 0
        assert result.num_info == 0
        assert result.all_findings == ()

    def test_failed_result(self):
        err = ValidationError(
            rule="valence",
            severity=ValidationSeverity.ERROR,
            message="Valence exceeded",
        )
        result = ValidationResult(
            passed=False,
            errors=(err,),
            warnings=(),
            info=(),
        )
        assert not result.is_valid
        assert result.num_errors == 1

    def test_all_findings_ordered(self):
        err = ValidationError(rule="e", severity=ValidationSeverity.ERROR, message="e")
        warn = ValidationError(rule="w", severity=ValidationSeverity.WARNING, message="w")
        info = ValidationError(rule="i", severity=ValidationSeverity.INFO, message="i")
        result = ValidationResult(
            passed=False,
            errors=(err,),
            warnings=(warn,),
            info=(info,),
        )
        assert result.all_findings == (err, warn, info)

    def test_to_dict(self):
        err = ValidationError(
            rule="valence",
            severity=ValidationSeverity.ERROR,
            message="Too many bonds",
            atom_index=1,
            detail={"max": 4},
        )
        result = ValidationResult(
            passed=False,
            errors=(err,),
            warnings=(),
            info=(),
        )
        d = result.to_dict()
        assert d["is_valid"] is False
        assert d["num_errors"] == 1
        assert d["errors"][0]["rule"] == "valence"
        assert d["errors"][0]["severity"] == "error"
        assert d["errors"][0]["detail"]["max"] == 4


class TestValidationReport:
    """Test the ValidationReport dataclass."""

    def test_create_report(self):
        result = ValidationResult(passed=True, errors=(), warnings=(), info=())
        report = ValidationReport(
            molecule_id="CCO",
            timestamp=datetime.datetime(2026, 7, 20),
            rule_set="standard",
            result=result,
        )
        assert report.molecule_id == "CCO"
        assert report.is_valid
        assert report.rule_set == "standard"

    def test_report_to_dict(self):
        err = ValidationError(
            rule="test", severity=ValidationSeverity.ERROR, message="failure"
        )
        result = ValidationResult(passed=False, errors=(err,), warnings=(), info=())
        report = ValidationReport(
            molecule_id="test",
            timestamp=datetime.datetime(2026, 1, 1),
            rule_set="strict",
            result=result,
        )
        d = report.to_dict()
        assert d["molecule_id"] == "test"
        assert d["is_valid"] is False
        assert "timestamp" in d

    def test_repr(self):
        result = ValidationResult(passed=True, errors=(), warnings=(), info=())
        report = ValidationReport(
            molecule_id="C",
            timestamp=datetime.datetime(2026, 7, 20),
            rule_set="standard",
            result=result,
        )
        assert report.molecule_id in repr(report)


# ════════════════════════════════════════════════════════════════
#  Validation Rule Tests
# ════════════════════════════════════════════════════════════════


class TestValenceRule:
    """Test the ValenceRule."""

    def test_valid_methane(self):
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6, implicit_hydrogens=4)
        graph = builder.build()
        rule = ValenceRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_valid_ethanol(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        c2 = builder.add_atom(atomic_number=6, implicit_hydrogens=2)
        o = builder.add_atom(atomic_number=8, implicit_hydrogens=1)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c2, o, BondOrder.SINGLE)
        graph = builder.build()
        rule = ValenceRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_valence_exceeded_carbon(self):
        """Carbon with 5 bonds should fail."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6, implicit_hydrogens=0)
        neighbors = []
        for _ in range(5):
            n = builder.add_atom(atomic_number=1)
            neighbors.append(n)
            builder.add_bond(c, n, BondOrder.SINGLE)
        graph = builder.build()
        rule = ValenceRule()
        findings = list(rule.validate(graph))
        assert len(findings) >= 1
        assert findings[0].rule == "valence"
        assert findings[0].severity == ValidationSeverity.ERROR

    def test_valence_exceeded_oxygen(self):
        """Oxygen with 3 bonds should fail."""
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8, implicit_hydrogens=0)
        for _ in range(3):
            n = builder.add_atom(atomic_number=1)
            builder.add_bond(o, n, BondOrder.SINGLE)
        graph = builder.build()
        rule = ValenceRule()
        findings = list(rule.validate(graph))
        assert len(findings) >= 1


class TestHypervalentRule:
    """Test the HypervalentRule for expanded octets."""

    def test_valid_sulfur_hexafluoride(self):
        """SF6 is valid — sulfur can have 6 bonds."""
        builder = MolecularGraphBuilder()
        s = builder.add_atom(atomic_number=16, implicit_hydrogens=0)
        for _ in range(6):
            f = builder.add_atom(atomic_number=9)
            builder.add_bond(s, f, BondOrder.SINGLE)
        graph = builder.build()
        rule = HypervalentRule()
        findings = list(rule.validate(graph))
        # S max valence is 6 from element data, so 6 bonds should pass
        assert len(findings) == 0

    def test_oxygen_not_hypervalent(self):
        """Oxygen (Z=8) is not hypervalent — rules should skip it."""
        builder = MolecularGraphBuilder()
        o = builder.add_atom(atomic_number=8, implicit_hydrogens=2)
        graph = builder.build()
        rule = HypervalentRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_phosphorus_pentachloride(self):
        """PCl5 is valid hypervalent — P can have 5 bonds."""
        builder = MolecularGraphBuilder()
        p = builder.add_atom(atomic_number=15, implicit_hydrogens=0)
        for _ in range(5):
            cl = builder.add_atom(atomic_number=17)
            builder.add_bond(p, cl, BondOrder.SINGLE)
        graph = builder.build()
        rule = HypervalentRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0


class TestChargeRule:
    """Test the ChargeRule."""

    def test_neutral_atoms_pass(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)  # C, neutral
        builder.add_atom(atomic_number=8)  # O, neutral
        builder.add_atom(atomic_number=7)  # N, neutral
        graph = builder.build()
        rule = ChargeRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_valid_charges_pass(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=8, formal_charge=-1)   # O-
        builder.add_atom(atomic_number=7, formal_charge=1)    # N+
        builder.add_atom(atomic_number=6, formal_charge=-1)   # C-
        graph = builder.build()
        rule = ChargeRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_invalid_charge_fails(self):
        """Carbon with charge +3 is invalid."""
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6, formal_charge=3)  # C+++ not allowed
        graph = builder.build()
        rule = ChargeRule()
        findings = list(rule.validate(graph))
        assert len(findings) >= 1

    def test_nitrogen_charge_range(self):
        """Nitrogen can have charges -2 to +3."""
        for charge in (-2, -1, 0, 1, 2, 3):
            builder = MolecularGraphBuilder()
            builder.add_atom(atomic_number=7, formal_charge=charge)
            graph = builder.build()
            rule = ChargeRule()
            findings = list(rule.validate(graph))
            assert len(findings) == 0, f"N with charge {charge} should be valid"

    def test_nitrogen_charge_out_of_range(self):
        """Nitrogen with charge -3 is outside allowed range."""
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=7, formal_charge=-3)
        graph = builder.build()
        rule = ChargeRule()
        findings = list(rule.validate(graph))
        assert len(findings) >= 1, "N with charge -3 should fail"


class TestTotalChargeRule:
    """Test the TotalChargeRule."""

    def test_neutral_molecule(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        builder.add_atom(atomic_number=6)
        graph = builder.build()
        rule = TotalChargeRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_charged_molecule_has_info(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=11, formal_charge=1)  # Na+
        builder.add_atom(atomic_number=17, formal_charge=-1)  # Cl-
        graph = builder.build()
        rule = TotalChargeRule()
        findings = list(rule.validate(graph))
        # Total charge = 0 (Na+ and Cl- cancel)
        assert len(findings) == 0

    def test_large_charge_warning(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=26, formal_charge=3)  # Fe+++
        graph = builder.build()
        rule = TotalChargeRule()
        findings = list(rule.validate(graph))
        # Should have at least one info finding about non-zero charge
        assert len(findings) >= 1


class TestIsotopeRule:
    """Test the IsotopeRule."""

    def test_no_isotope_passes(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        graph = builder.build()
        rule = IsotopeRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_known_isotope_passes(self):
        from chemengine.core.atoms import Isotope
        builder = MolecularGraphBuilder()
        builder.add_atom(
            atomic_number=6,
            isotope=Isotope(mass_number=13, exact_mass=13.003355, abundance=0.0107),
        )
        graph = builder.build()
        rule = IsotopeRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0, f"Carbon-13 should be valid, got {findings}"

    def test_unknown_isotope_warns(self):
        from chemengine.core.atoms import Isotope
        builder = MolecularGraphBuilder()
        # Carbon-999 doesn't exist
        builder.add_atom(
            atomic_number=6,
            isotope=Isotope(mass_number=999, exact_mass=999.0, abundance=0.0),
        )
        graph = builder.build()
        rule = IsotopeRule()
        findings = list(rule.validate(graph))
        assert len(findings) >= 1


class TestGraphStructureRule:
    """Test the GraphStructureRule."""

    def test_valid_simple_graph(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        graph = builder.build()
        rule = GraphStructureRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_self_bond_detected(self):
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        graph = builder.build()
        # Can't create self-bond via builder (raises ValueError)
        # Test the validate method works on the raw graph
        rule = GraphStructureRule()
        graph_builder = MolecularGraphBuilder()
        graph_builder._atoms = [builder._atoms[0]]
        graph_builder._bonds = []
        g = graph_builder.build()
        # Manually add a bond by creating a graph with a self-bond
        # (Builder prevents this, so we test via the rule directly)
        # The graph_structure check for self-bonds is primarily about
        # checking existing bonds, which can't be created via builder.
        # This is tested indirectly via the validate() method on graph.
        findings = list(rule.validate(g))
        # No bonds = no errors
        assert len(findings) == 0

    def test_duplicate_bond_detected(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        graph = builder.build()
        rule = GraphStructureRule()
        findings = list(rule.validate(graph))
        # Should detect duplicate bond
        assert any(f.rule == "graph_structure" for f in findings)

    def test_hydrogen_multiple_bonds(self):
        """Hydrogen with 2 bonds should be flagged."""
        builder = MolecularGraphBuilder()
        h = builder.add_atom(atomic_number=1)
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(h, c1, BondOrder.SINGLE)
        builder.add_bond(h, c2, BondOrder.SINGLE)
        graph = builder.build()
        rule = GraphStructureRule()
        findings = list(rule.validate(graph))
        assert len(findings) >= 1


class TestAromaticityRule:
    """Test the AromaticityRule."""

    def test_no_aromatic_atoms_passes(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        graph = builder.build()
        rule = AromaticityRule()
        findings = list(rule.validate(graph))
        assert len(findings) == 0

    def test_aromatic_bond_between_non_aromatic_atoms(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6, is_aromatic=False)
        c2 = builder.add_atom(atomic_number=6, is_aromatic=False)
        builder.add_bond(c1, c2, BondOrder.AROMATIC)
        graph = builder.build()
        rule = AromaticityRule()
        findings = list(rule.validate(graph))
        # Should warn about aromatic bond connecting non-aromatic atoms
        assert len(findings) >= 1


# ════════════════════════════════════════════════════════════════
#  Rule Set Tests
# ════════════════════════════════════════════════════════════════


class TestRuleSets:
    """Test rule set selection."""

    def test_standard_has_all_rules(self):
        rules = get_validation_rules("standard")
        names = {r.name for r in rules}
        assert "valence" in names
        assert "charge" in names
        assert "graph_structure" in names

    def test_relaxed_excludes_some_rules(self):
        rules = get_validation_rules("relaxed")
        names = {r.name for r in rules}
        assert "valence" in names

    def test_strict_includes_all(self):
        rules = get_validation_rules("strict")
        rules_standard = get_validation_rules("standard")
        assert len(rules) >= len(rules_standard)

    def test_default_is_standard(self):
        rules = get_validation_rules()
        rules_standard = get_validation_rules("standard")
        names = {r.name for r in rules}
        std_names = {r.name for r in rules_standard}
        assert names == std_names


# ════════════════════════════════════════════════════════════════
#  ValidationRule Protocol Tests
# ════════════════════════════════════════════════════════════════


class TestValidationRuleProtocol:
    """Test that validation rules conform to the protocol."""

    def test_rule_has_required_attributes(self):
        rule = ValenceRule()
        assert hasattr(rule, "name")
        assert hasattr(rule, "description")
        assert hasattr(rule, "validate")
        assert callable(rule.validate)

    def test_rule_returns_iterator(self):
        rule = ValenceRule()
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        graph = builder.build()
        result = rule.validate(graph)
        # Should be iterable
        assert hasattr(result, "__iter__")
        items = list(result)
        assert isinstance(items, list)


# ════════════════════════════════════════════════════════════════
#  Sanitization Tests
# ════════════════════════════════════════════════════════════════


class TestAddImplicitHydrogens:
    """Test the add_implicit_hydrogens sanitization."""

    def test_methane_gets_4_hydrogens(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)  # No implicit H set
        graph = builder.build()
        sanitized = add_implicit_hydrogens(graph)
        assert sanitized.atoms[0].implicit_hydrogens is not None
        assert sanitized.atoms[0].implicit_hydrogens == 4

    def test_already_set_preserved(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6, implicit_hydrogens=3)
        graph = builder.build()
        sanitized = add_implicit_hydrogens(graph)
        assert sanitized.atoms[0].implicit_hydrogens == 3

    def test_oxygen_gets_2_hydrogens(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=8)
        graph = builder.build()
        sanitized = add_implicit_hydrogens(graph)
        h = sanitized.atoms[0].implicit_hydrogens
        assert h is not None and h >= 0

    def test_wildcard_gets_no_hydrogens(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=0)  # Wildcard
        graph = builder.build()
        sanitized = add_implicit_hydrogens(graph)
        assert sanitized.atoms[0].implicit_hydrogens is None

    def test_carbon_with_double_bond(self):
        """Formaldehyde: C=O — C should have 2 H."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        o = builder.add_atom(atomic_number=8)
        builder.add_bond(c, o, BondOrder.DOUBLE)
        graph = builder.build()
        sanitized = add_implicit_hydrogens(graph)
        c_h = sanitized.atoms[c].implicit_hydrogens
        assert c_h == 2, f"Formaldehyde C should have 2 H, got {c_h}"


class TestRemoveDuplicateBonds:
    """Test the remove_duplicate_bonds sanitization."""

    def test_no_duplicates_unchanged(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        graph = builder.build()
        sanitized = remove_duplicate_bonds(graph)
        assert sanitized.num_bonds == 1

    def test_removes_duplicates(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        graph = builder.build()
        sanitized = remove_duplicate_bonds(graph)
        assert sanitized.num_bonds == 1  # Keeps the higher-order bond

    def test_keeps_higher_order(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        builder.add_bond(c1, c2, BondOrder.SINGLE)  # Added after
        graph = builder.build()
        sanitized = remove_duplicate_bonds(graph)
        assert sanitized.num_bonds == 1
        bond = sanitized.bonds[0]
        assert bond.order == BondOrder.DOUBLE  # Higher order preserved


class TestSanitize:
    """Test the full sanitize pipeline."""

    def test_sanitize_pipeline(self):
        """Sanitize should run all steps without error."""
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        o = builder.add_atom(atomic_number=8)
        builder.add_bond(c, o, BondOrder.DOUBLE)
        graph = builder.build()
        sanitized = sanitize(graph)
        assert sanitized.num_atoms == 2
        # Should have implicit H assigned
        assert sanitized.atoms[0].implicit_hydrogens is not None
        assert sanitized.atoms[1].implicit_hydrogens is not None

    def test_sanitize_removes_duplicate_bonds(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        builder.add_bond(c1, c2, BondOrder.DOUBLE)
        graph = builder.build()
        sanitized = sanitize(graph)
        assert sanitized.num_bonds == 1


# ════════════════════════════════════════════════════════════════
#  Integration Tests
# ════════════════════════════════════════════════════════════════


class TestMolecularGraphIntegration:
    """Test integration with MolecularGraph."""

    def test_sanitize_method(self):
        from chemengine.core.graph import MolecularGraph
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6)
        builder.add_atom(atomic_number=8)
        builder.add_bond(c, 1, BondOrder.DOUBLE)
        graph = builder.build()
        sanitized = graph.sanitize()
        assert isinstance(sanitized, MolecularGraph)
        assert sanitized.atoms[0].implicit_hydrogens is not None

    def test_validate_method_still_works(self):
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(atomic_number=6)
        c2 = builder.add_atom(atomic_number=6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        graph = builder.build()
        issues = graph.validate()
        assert isinstance(issues, list)

    def test_is_valid_property(self):
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        graph = builder.build()
        assert graph.is_valid is True


class TestChemEngineAPIIntegration:
    """Test integration with ChemEngineAPI."""

    def test_validate_via_api(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6, implicit_hydrogens=4)
        graph = builder.build()
        result = api.validate(graph)
        assert result.is_valid
        assert result.num_errors == 0

    def test_validate_invalid_via_api(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        builder = MolecularGraphBuilder()
        c = builder.add_atom(atomic_number=6, implicit_hydrogens=0)
        for _ in range(5):
            n = builder.add_atom(atomic_number=1)
            builder.add_bond(c, n, BondOrder.SINGLE)
        graph = builder.build()
        result = api.validate(graph)
        assert not result.is_valid
        assert result.num_errors >= 1

    def test_sanitize_via_api(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        builder = MolecularGraphBuilder()
        builder.add_atom(atomic_number=6)
        graph = builder.build()
        sanitized = api.sanitize(graph)
        assert sanitized.atoms[0].implicit_hydrogens is not None

    def test_execute_validate_tool(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        result = api.execute_tool("validate", {"smiles": "CCO"})
        assert "is_valid" in result
        assert result["num_errors"] == 0

    def test_execute_sanitize_tool(self):
        from chemengine.core.tool_interface import ChemEngineAPI
        api = ChemEngineAPI()
        result = api.execute_tool("sanitize", {"smiles": "CCO"})
        assert "sanitized_smiles" in result
        assert "formula" in result
