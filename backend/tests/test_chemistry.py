"""Tests for the Chemistry Explorer API.

These tests exercise the real ChemEngine through the backend adapter for
supported, engine-verified inputs. No ChemEngine output is faked — assertions
target values the engine actually computes (cross-checked during M22).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.main import app


@pytest.fixture
def client() -> AsyncClient:
    """Provide an ASGI test client (no DB/auth required for /chemistry)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _explore(client: AsyncClient, text: str) -> Response:
    """POST the given input to the explore endpoint."""
    response = await client.post(
        "/api/v1/chemistry/explore",
        json={"input": text},
    )
    return response


# --- Formula inputs: identity only (no misleading structure) ---


@pytest.mark.asyncio
async def test_water_formula_identity(client: AsyncClient) -> None:
    """H2O formula: identity only, no structure/derived descriptors."""
    response = await _explore(client, "H2O")
    assert response.status_code == 200
    data = response.json()
    assert data["detected_type"] == "formula"
    assert data["structure_available"] is False
    assert data["identity"]["formula"] == "H2O"
    assert data["identity"]["exact_mass"] == pytest.approx(18.010565, abs=1e-4)
    assert data["identity"]["average_mass"] == pytest.approx(18.015, abs=1e-3)
    assert data["identity"]["heavy_atom_count"] == 1
    assert data["identity"]["atom_count"] == 3
    # Correctness: a formula does not encode connectivity.
    assert data["structure"] is None
    assert data["properties"] is None


@pytest.mark.asyncio
async def test_co2_formula_identity(client: AsyncClient) -> None:
    """CO2 formula: masses correct; no structure claimed."""
    response = await _explore(client, "CO2")
    assert response.status_code == 200
    data = response.json()
    assert data["identity"]["formula"] == "CO2"
    assert data["identity"]["exact_mass"] == pytest.approx(43.98983, abs=1e-4)
    assert data["identity"]["average_mass"] == pytest.approx(44.009, abs=1e-3)
    assert data["structure_available"] is False
    assert data["structure"] is None
    assert data["properties"] is None


# --- Structure-bearing inputs (SMILES / names) ---


@pytest.mark.asyncio
async def test_ethanol_smiles_structure(client: AsyncClient) -> None:
    """CCO (SMILES) parses to ethanol with structure and properties."""
    response = await _explore(client, "CCO")
    assert response.status_code == 200
    data = response.json()
    assert data["detected_type"] == "smiles"
    assert data["structure_available"] is True
    assert data["identity"]["formula"] == "C2H6O"
    assert data["identity"]["exact_mass"] == pytest.approx(46.041865, abs=1e-4)
    assert data["structure"] is not None
    assert data["structure"]["canonical_smiles"] == "CCO"
    assert "C" in data["structure"]["atom_symbols"]
    assert isinstance(data["structure"]["bonds"], list)
    assert data["structure"]["svg"].strip().startswith("<svg")
    # Descriptors delegated to ChemEngine.
    props = data["properties"]
    assert props is not None
    assert props["hba"] == 1
    assert props["hbd"] == 1
    assert props["fraction_csp3"] == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_ethanol_name_resolution(client: AsyncClient) -> None:
    """A supported common name resolves to the same molecule as CCO."""
    response = await _explore(client, "ethanol")
    assert response.status_code == 200
    data = response.json()
    assert data["detected_type"] == "name"
    assert data["identity"]["formula"] == "C2H6O"
    assert data["structure"]["canonical_smiles"] == "CCO"


@pytest.mark.asyncio
async def test_benzene_ring_count(client: AsyncClient) -> None:
    """Benzene (SMILES) reports one ring."""
    response = await _explore(client, "c1ccccc1")
    assert response.status_code == 200
    data = response.json()
    assert data["identity"]["formula"] == "C6H6"
    assert data["properties"]["ring_count"] == 1


@pytest.mark.asyncio
async def test_glucose_smiles_generated(client: AsyncClient) -> None:
    """Glucose (name) produces a valid canonical SMILES and heavy atoms."""
    response = await _explore(client, "glucose")
    assert response.status_code == 200
    data = response.json()
    assert data["identity"]["formula"] == "C6H12O6"
    assert data["identity"]["heavy_atom_count"] == 12
    assert data["structure"]["canonical_smiles"].startswith("C(O)")


# --- Input validation ---


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
async def test_empty_input_422(client: AsyncClient, bad: str) -> None:
    """Empty or whitespace-only input is rejected as invalid_input."""
    response = await _explore(client, bad)
    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_unsupported_input_422(client: AsyncClient) -> None:
    """Unrecognizable input yields unsupported_input without internals."""
    response = await _explore(client, "zzzznotamolecule")
    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["code"] == "unsupported_input"
    assert "traceback" not in response.text.lower()


@pytest.mark.asyncio
async def test_overlong_input_422(client: AsyncClient) -> None:
    """Absurdly long input is rejected as invalid_input."""
    response = await _explore(client, "C" * 200)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_input"


@pytest.mark.asyncio
async def test_missing_input_field_422(client: AsyncClient) -> None:
    """A request without the required field is rejected."""
    response = await client.post("/api/v1/chemistry/explore", json={})
    assert response.status_code == 422


# --- Response schema ---


@pytest.mark.asyncio
async def test_response_schema(client: AsyncClient) -> None:
    """The response body matches the documented schema exactly."""
    response = await _explore(client, "CCO")
    data = response.json()
    assert set(data.keys()) == {
        "input",
        "detected_type",
        "structure_available",
        "identity",
        "structure",
        "properties",
    }
    assert set(data["identity"].keys()) == {
        "formula",
        "exact_mass",
        "average_mass",
        "heavy_atom_count",
        "atom_count",
    }
