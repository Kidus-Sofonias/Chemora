"""Tests for the M39 polymer-analysis module.

Covers the reference oracle, repeat-unit extraction, structural degree of
polymerization, (de)serialization round-trips and registry registration.
"""

from __future__ import annotations

import pytest

from chemengine.core.graph import MolecularGraph
from chemengine.core.registry import AlgorithmRegistry, get_global_registry
from chemengine.parsing.smiles import parse_smiles
from chemengine.polymer import (
    POLYMER_CATALOGUE_VERSION,
    REFERENCE_POLYMER_ORACLE,
    SCHEMA_VERSION,
    PolymerAnalysis,
    analyze_polymer,
    degree_of_polymerization,
    dict_to_polymer_analysis,
    extract_repeat_unit,
    find_end_groups,
    list_polymer_reference,
    polymer_analysis_to_dict,
    register_polymer_algorithms,
)

MOL_W_TOL = 0.05


@pytest.mark.parametrize("smiles", list(REFERENCE_POLYMER_ORACLE))
class TestReferenceOracle:
    """Every curated reference polymer must analyze to its expected values."""

    def test_repeat_unit_formula(self, smiles: str) -> None:
        """Repeat-unit molecular formula matches the oracle."""
        expected = REFERENCE_POLYMER_ORACLE[smiles]["repeat_unit_formula"]
        analysis = analyze_polymer(parse_smiles(smiles))
        assert analysis.repeat_unit is not None
        assert analysis.repeat_unit.formula == expected

    def test_repeat_unit_weight(self, smiles: str) -> None:
        """Repeat-unit molecular weight matches the oracle."""
        expected = REFERENCE_POLYMER_ORACLE[smiles]["repeat_unit_weight"]
        analysis = analyze_polymer(parse_smiles(smiles))
        assert analysis.repeat_unit is not None
        assert abs(analysis.repeat_unit.molecular_weight - expected) < MOL_W_TOL

    def test_attachment_elements(self, smiles: str) -> None:
        """Attachment element tuple matches the oracle."""
        expected = REFERENCE_POLYMER_ORACLE[smiles]["attachment_elements"]
        analysis = analyze_polymer(parse_smiles(smiles))
        assert analysis.repeat_unit is not None
        assert analysis.repeat_unit.attachment_elements == expected

    def test_polymerization_type(self, smiles: str) -> None:
        """Polymerization type matches the oracle."""
        expected = REFERENCE_POLYMER_ORACLE[smiles]["polymerization_type"]
        assert analyze_polymer(parse_smiles(smiles)).polymerization_type == expected

    def test_degree_of_polymerization(self, smiles: str) -> None:
        """Degree of polymerization matches the oracle."""
        expected = REFERENCE_POLYMER_ORACLE[smiles]["degree_of_polymerization"]
        assert analyze_polymer(parse_smiles(smiles)).degree_of_polymerization == expected

    def test_connection_points(self, smiles: str) -> None:
        """Wildcard inputs report two connection points."""
        analysis = analyze_polymer(parse_smiles(smiles))
        assert analysis.has_connection_points is True
        assert analysis.num_connection_points == 2


@pytest.mark.parametrize("smiles", list(REFERENCE_POLYMER_ORACLE))
class TestSerialization:
    """PolymerAnalysis must round-trip through dict form losslessly."""

    def test_round_trip_to_dict(self, smiles: str) -> None:
        """to_dict/dict round-trips losslessly."""
        original = analyze_polymer(parse_smiles(smiles))
        reconstructed = dict_to_polymer_analysis(polymer_analysis_to_dict(original))
        assert polymer_analysis_to_dict(original) == polymer_analysis_to_dict(reconstructed)

    def test_round_trip_preserves_repeat_unit(self, smiles: str) -> None:
        """Round-trip preserves the repeat-unit formula."""
        original = analyze_polymer(parse_smiles(smiles))
        reconstructed = dict_to_polymer_analysis(polymer_analysis_to_dict(original))
        assert reconstructed.repeat_unit is not None
        assert reconstructed.repeat_unit.formula == original.repeat_unit.formula

    def test_schema_version_preserved(self, smiles: str) -> None:
        """Round-trip preserves the schema version tag."""
        analysis = dict_to_polymer_analysis(
            polymer_analysis_to_dict(analyze_polymer(parse_smiles(smiles)))
        )
        assert analysis.schema == SCHEMA_VERSION


class TestDegreeOfPolymerization:
    """Structural DPn for terminal chains and repeat-unit forms."""

    @pytest.mark.parametrize(
        ("smiles", "expected"),
        [
            ("*CC*", 1),
            ("*CCO*", 1),
            ("*OC(=O)CC*", 1),
            ("*C(F)(F)*", 1),
            ("CCCCCC", 6),
            ("CCCCC", 5),
            ("CCC", 3),
            ("CCCl", 3),
            ("CCCCCl", 5),
        ],
    )
    def test_dp_values(self, smiles: str, expected: int) -> None:
        """DPn matches the expected structural period."""
        assert degree_of_polymerization(parse_smiles(smiles)) == expected

    @pytest.mark.parametrize(
        "smiles",
        ["CC(C)C", "CC(C)(C)C", "C1CCCCC1", "c1ccccc1"],
    )
    def test_non_linear_returns_none(self, smiles: str) -> None:
        """Branched / cyclic chains have no DPn."""
        assert degree_of_polymerization(parse_smiles(smiles)) is None


class TestExtractRepeatUnit:
    """Repeat-unit extraction for terminal alkanes and wildcard forms."""

    @pytest.mark.parametrize(
        ("smiles", "formula", "mw"),
        [
            ("CCCCCC", "CH2", 14.027),
            ("CCCC", "CH2", 14.027),
            ("CCC", "CH2", 14.027),
            ("COCOCOCOCO", "CH2O", 30.026),
        ],
    )
    def test_terminal_mer(self, smiles: str, formula: str, mw: float) -> None:
        """Terminal-chain mer matches the expected minimal repeat unit."""
        unit = extract_repeat_unit(parse_smiles(smiles))
        assert unit is not None
        assert unit.formula == formula
        assert abs(unit.molecular_weight - mw) < MOL_W_TOL

    def test_wildcard_pe(self) -> None:
        """PE repeat unit is C2H4 with carbon attachments."""
        unit = extract_repeat_unit(parse_smiles("*CC*"))
        assert unit is not None
        assert unit.formula == "C2H4"
        assert unit.attachment_elements == ("C", "C")

    @pytest.mark.parametrize("smiles", ["CC(C)C", "C1CCCCC1", "c1ccccc1"])
    def test_non_extractable(self, smiles: str) -> None:
        """Branched / cyclic inputs yield no repeat unit."""
        assert extract_repeat_unit(parse_smiles(smiles)) is None


class TestAnalyzePolymer:
    """End-to-end analysis coordination (dpn + repeat unit + type)."""

    def test_hexane_analysis(self) -> None:
        """Hexane: DPn 6, addition, CH2 mer, nMw ~= 6 x CH2."""
        analysis = analyze_polymer(parse_smiles("CCCCCC"))
        assert analysis.degree_of_polymerization == 6
        assert analysis.polymerization_type == "addition"
        assert analysis.repeat_unit is not None
        assert analysis.repeat_unit.formula == "CH2"
        assert analysis.number_avg_mw is not None
        assert abs(analysis.number_avg_mw - 6 * 14.027) < 0.1

    def test_pvc_analysis(self) -> None:
        """PVC: addition, single mer, C2H3Cl repeat unit."""
        analysis = analyze_polymer(parse_smiles("*CC(Cl)*"))
        assert analysis.polymerization_type == "addition"
        assert analysis.degree_of_polymerization == 1
        assert analysis.repeat_unit.formula == "C2H3Cl"

    def test_pet_is_condensation(self) -> None:
        """PET repeat unit is classified as condensation."""
        analysis = analyze_polymer(parse_smiles("*OC(=O)c1ccccc1CO*"))
        assert analysis.polymerization_type == "condensation"

    def test_terminal_chain_end_groups(self) -> None:
        """CCCl end groups are methyl and Cl-halide."""
        analysis = analyze_polymer(parse_smiles("CCCl"))
        assert analysis.polymerization_type == "addition"
        assert [eg.element for eg in analysis.end_groups] == ["C", "Cl"]


class TestEndGroups:
    """Terminal end-group detection on chains."""

    def test_hexane_end_groups(self) -> None:
        """Hexane has two methyl end groups."""
        groups = find_end_groups(parse_smiles("CCCCCC"))
        assert len(groups) == 2
        assert all(g.element == "C" for g in groups)
        assert all(g.hydrogens == 3 for g in groups)

    def test_benzene_has_no_end_groups(self) -> None:
        """Benzene (cyclic) has no end groups."""
        assert find_end_groups(parse_smiles("c1ccccc1")) == ()

    def test_wildcard_has_no_end_groups(self) -> None:
        """Wildcard-containing inputs have no end groups."""
        assert find_end_groups(parse_smiles("*CC*")) == ()


class TestCatalogueMetadata:
    """Module-level catalog metadata constants."""

    def test_schema_version(self) -> None:
        """Schema tag is the v1 polymer-analysis tag."""
        assert SCHEMA_VERSION == "chemengine-polymer-analysis/v1"

    def test_catalogue_version(self) -> None:
        """Catalogue version is 1.0.0."""
        assert POLYMER_CATALOGUE_VERSION == "1.0.0"

    def test_reference_keys(self) -> None:
        """list_polymer_reference mirrors the oracle keys."""
        assert list_polymer_reference() == tuple(REFERENCE_POLYMER_ORACLE)
        assert len(REFERENCE_POLYMER_ORACLE) == 8


class TestRegistry:
    """Algorithm registry registration behaviour."""

    def test_register_on_fresh_registry(self) -> None:
        """Registration populates three polymer algorithms."""
        registry = AlgorithmRegistry()
        register_polymer_algorithms(registry)
        assert ("polymer", "analyze") in registry
        assert ("polymer", "repeat_unit") in registry
        assert ("polymer", "degree_of_polymerization") in registry
        assert registry.count == 3

    def test_registration_is_idempotent(self) -> None:
        """Re-registering is a no-op (no duplicate entries)."""
        registry = AlgorithmRegistry()
        register_polymer_algorithms(registry)
        register_polymer_algorithms(registry)
        assert registry.count == 3

    def test_register_replace(self) -> None:
        """replace=True re-registers even when present."""
        registry = AlgorithmRegistry()
        register_polymer_algorithms(registry, replace=True)
        assert ("polymer", "analyze") in registry

    def test_register_uses_global_by_default(self) -> None:
        """Without a registry, the global singleton is populated."""
        global_reg = get_global_registry()
        register_polymer_algorithms()
        assert ("polymer", "analyze") in global_reg

    def test_analyze_entry_types(self) -> None:
        """The analyze entry advertises its input/output types."""
        registry = AlgorithmRegistry()
        register_polymer_algorithms(registry)
        entry = registry.get("polymer", "analyze")
        assert entry.algorithm is analyze_polymer
        assert entry.input_type is MolecularGraph
        assert entry.output_type is PolymerAnalysis
