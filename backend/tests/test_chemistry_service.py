"""ChemistryService integration tests — real ChemEngine, no fakes.

These tests prove the backend adapter delegates to the actual deterministic
engine (values below are ChemEngine's own verified outputs, cross-checked in
the M22 probes and consistent with the ChemEngine test suite).
"""

from __future__ import annotations

import pytest

from app.services.chemistry import ChemistryError, ChemistryService


@pytest.fixture
def service() -> ChemistryService:
    """Provide a ChemistryService backed by the real ChemEngine."""
    return ChemistryService()


def test_water_formula_identity(service: ChemistryService) -> None:
    """A molecular formula yields identity only — never a structure."""
    result = service.explore("H2O")
    assert result.detected_type == "formula"
    assert result.structure_available is False
    assert result.structure is None
    assert result.properties is None
    assert result.identity["formula"] == "H2O"
    assert result.identity["exact_mass"] == pytest.approx(18.010565, abs=1e-4)
    assert result.identity["average_mass"] == pytest.approx(18.015, abs=1e-3)


def test_ethanol_smiles_matches_name(service: ChemistryService) -> None:
    """The same molecule parsed from SMILES and by name agrees."""
    by_smiles = service.explore("CCO")
    by_name = service.explore("ethanol")
    assert by_smiles.structure is not None and by_name.structure is not None
    assert (
        by_smiles.structure["canonical_smiles"]
        == by_name.structure["canonical_smiles"]
        == "CCO"
    )
    assert by_smiles.identity == by_name.identity
    assert by_smiles.properties == by_name.properties


def test_exact_mass_and_average_mass_distinct(service: ChemistryService) -> None:
    """The correctness-gate distinction must survive the adapter."""
    result = service.explore("CCO")
    identity = result.identity
    assert identity["exact_mass"] == pytest.approx(46.041865, abs=1e-4)
    assert identity["average_mass"] == pytest.approx(46.069, abs=1e-3)
    assert identity["exact_mass"] != identity["average_mass"]


def test_structure_svg_and_bonds(service: ChemistryService) -> None:
    """A structural input yields an SVG depiction and descriptors."""
    result = service.explore("c1ccccc1")
    assert result.structure is not None
    svg = result.structure["svg"]
    assert isinstance(svg, str) and svg.strip().startswith("<svg")
    assert result.properties is not None
    assert result.properties["ring_count"] == 1
    assert result.properties["hbd"] == 0
    assert result.properties["hba"] == 0


def test_empty_input_raises_invalid(service: ChemistryService) -> None:
    """Whitespace-only input is rejected as invalid_input."""
    with pytest.raises(ChemistryError) as exc_info:
        service.explore("   ")
    assert exc_info.value.code == "invalid_input"


def test_overlong_input_raises_invalid(service: ChemistryService) -> None:
    """Unreasonably long input is rejected as invalid_input."""
    with pytest.raises(ChemistryError) as exc_info:
        service.explore("C" * 500)
    assert exc_info.value.code == "invalid_input"


def test_unparseable_input_raises_unsupported(service: ChemistryService) -> None:
    """Unrecognizable input raises unsupported_input with a safe message."""
    with pytest.raises(ChemistryError) as exc_info:
        service.explore("zzzznotamolecule")
    assert exc_info.value.code == "unsupported_input"
    # Message is user-facing and free of internals.
    assert "Traceback" not in exc_info.value.message
