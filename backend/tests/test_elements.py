"""Tests for the Element Explorer API.

These tests exercise the real ChemEngine element dataset and the real
deterministic electron-configuration subsystem through the backend adapter.
Expected values are the engine's own verified outputs (cross-checked against
ChemEngine's education test suite during M23). Nothing is faked.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client() -> AsyncClient:
    """Provide an ASGI test client (no DB/auth required for /elements)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- Element list ---


@pytest.mark.asyncio
async def test_list_elements_returns_full_table(client: AsyncClient) -> None:
    """The engine dataset exposes all 118 elements ordered by atomic number."""
    response = await client.get("/api/v1/elements")
    assert response.status_code == 200
    elements = response.json()["elements"]
    assert len(elements) == 118
    assert [e["atomic_number"] for e in elements] == list(range(1, 119))
    assert elements[0]["symbol"] == "H"
    assert elements[7]["symbol"] == "O"
    assert elements[117]["symbol"] == "Og"


@pytest.mark.asyncio
async def test_list_elements_schema(client: AsyncClient) -> None:
    """Each summary carries exactly the periodic-table metadata fields."""
    response = await client.get("/api/v1/elements")
    elements = response.json()["elements"]
    assert set(elements[0].keys()) == {
        "atomic_number",
        "symbol",
        "name",
        "atomic_mass",
        "period",
        "group",
        "block",
        "category",
    }


@pytest.mark.asyncio
async def test_oxygen_summary_metadata(client: AsyncClient) -> None:
    """Oxygen: period 2, group 16, p-block — from the engine dataset."""
    response = await client.get("/api/v1/elements")
    oxygen = response.json()["elements"][7]
    assert oxygen["name"] == "Oxygen"
    assert oxygen["period"] == 2
    assert oxygen["group"] == 16
    assert oxygen["block"] == "p"


# --- Element detail: electron configuration ---


@pytest.mark.asyncio
async def test_oxygen_detail_by_symbol(client: AsyncClient) -> None:
    """O by symbol: full computed configuration, valence/core/unpaired."""
    response = await client.get("/api/v1/elements/O")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "O"
    assert data["atomic_number"] == 8
    assert data["config_full"] == "1s2 2s2 2p4"
    assert data["config_shorthand"] == "[He] 2s2 2p4"
    assert data["noble_gas"] == "He"
    assert data["valence_electrons"] == 6
    assert data["core_electrons"] == 2
    assert data["unpaired_electrons"] == 2
    assert data["shells"] == {"1": 2, "2": 6}
    assert data["subshells"] == {"1s": 2, "2s": 2, "2p": 4}


@pytest.mark.asyncio
async def test_oxygen_detail_by_name_is_case_insensitive(client: AsyncClient) -> None:
    """Name lookup is normalised: 'oxygen' and 'Oxygen' resolve to O."""
    for identifier in ("oxygen", "Oxygen", "OXYGEN"):
        response = await client.get(f"/api/v1/elements/{identifier}")
        assert response.status_code == 200
        assert response.json()["symbol"] == "O"


@pytest.mark.asyncio
async def test_oxygen_detail_by_atomic_number(client: AsyncClient) -> None:
    """Atomic-number lookup works as a digit string."""
    response = await client.get("/api/v1/elements/8")
    assert response.status_code == 200
    assert response.json()["symbol"] == "O"


@pytest.mark.asyncio
async def test_iron_detail_shells_and_unpaired(client: AsyncClient) -> None:
    """Fe: 3d6 4s2 gives 4 unpaired electrons; shells 2/8/14/2."""
    response = await client.get("/api/v1/elements/Fe")
    assert response.status_code == 200
    data = response.json()
    assert data["atomic_number"] == 26
    assert data["config_shorthand"] == "[Ar] 3d6 4s2"
    assert data["unpaired_electrons"] == 4
    assert data["shells"] == {"1": 2, "2": 8, "3": 14, "4": 2}


@pytest.mark.asyncio
async def test_helium_detail(client: AsyncClient) -> None:
    """He: full configuration and empty core."""
    response = await client.get("/api/v1/elements/He")
    assert response.status_code == 200
    data = response.json()
    assert data["config_full"] == "1s2"
    assert data["valence_electrons"] == 2
    assert data["core_electrons"] == 0
    assert data["unpaired_electrons"] == 0


@pytest.mark.asyncio
async def test_chromium_transition_metal_exception(client: AsyncClient) -> None:
    """Cr is a documented Aufbau exception: [Ar] 3d5 4s1, not 3d4 4s2."""
    response = await client.get("/api/v1/elements/Cr")
    assert response.status_code == 200
    data = response.json()
    assert data["config_shorthand"] == "[Ar] 3d5 4s1"
    assert data["subshells"]["3d"] == 5
    assert data["subshells"]["4s"] == 1


@pytest.mark.asyncio
async def test_copper_transition_metal_exception(client: AsyncClient) -> None:
    """Cu is a documented Aufbau exception: [Ar] 3d10 4s1."""
    response = await client.get("/api/v1/elements/Cu")
    assert response.status_code == 200
    assert response.json()["config_shorthand"] == "[Ar] 3d10 4s1"


@pytest.mark.asyncio
async def test_orbital_data_is_structured(client: AsyncClient) -> None:
    """The orbital diagram carries per-subshell occupancy from the engine."""
    response = await client.get("/api/v1/elements/O")
    orbitals = response.json()["orbitals"]
    assert orbitals == [
        {"orbital": "1s", "electrons": 2, "capacity": 2, "subshell": "s", "shell": 1},
        {"orbital": "2s", "electrons": 2, "capacity": 2, "subshell": "s", "shell": 2},
        {"orbital": "2p", "electrons": 4, "capacity": 6, "subshell": "p", "shell": 2},
    ]


@pytest.mark.asyncio
async def test_explanation_is_deterministic_text(client: AsyncClient) -> None:
    """The educational explanation is engine-generated and self-consistent."""
    response = await client.get("/api/v1/elements/O")
    explanation = response.json()["explanation"]
    assert "Oxygen" in explanation
    assert "1s2 2s2 2p4" in explanation


@pytest.mark.asyncio
async def test_detail_schema(client: AsyncClient) -> None:
    """The detail response matches the documented schema exactly."""
    response = await client.get("/api/v1/elements/O")
    data = response.json()
    assert set(data.keys()) == {
        "atomic_number",
        "symbol",
        "name",
        "atomic_mass",
        "period",
        "group",
        "block",
        "category",
        "config_full",
        "config_shorthand",
        "noble_gas",
        "valence_electrons",
        "core_electrons",
        "unpaired_electrons",
        "shells",
        "subshells",
        "orbitals",
        "explanation",
    }


# --- Error handling ---


@pytest.mark.asyncio
async def test_unknown_symbol_404(client: AsyncClient) -> None:
    """An unknown symbol yields a clean 404 with a stable error code."""
    response = await client.get("/api/v1/elements/Zz")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["code"] == "unknown_element"
    assert "traceback" not in response.text.lower()


@pytest.mark.asyncio
async def test_unknown_name_404(client: AsyncClient) -> None:
    """An unknown element name yields a clean 404."""
    response = await client.get("/api/v1/elements/unobtainium")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "unknown_element"


@pytest.mark.asyncio
async def test_atomic_number_out_of_range_404(client: AsyncClient) -> None:
    """An atomic number beyond 118 yields a clean 404."""
    response = await client.get("/api/v1/elements/200")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "unknown_element"


@pytest.mark.asyncio
async def test_invalid_identifier_404(client: AsyncClient) -> None:
    """Nonsense identifiers are rejected without internals."""
    response = await client.get("/api/v1/elements/zz9")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["code"] in {"unknown_element", "invalid_identifier"}
    assert "KeyError" not in response.text


@pytest.mark.asyncio
async def test_empty_identifier_404(client: AsyncClient) -> None:
    """A whitespace identifier is rejected as invalid."""
    response = await client.get("/api/v1/elements/%20%20")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "invalid_identifier"


