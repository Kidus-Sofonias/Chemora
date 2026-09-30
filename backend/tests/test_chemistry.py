"""Tests for the Chemistry Explorer API.

These tests exercise the real ChemEngine through the backend adapter for
supported, engine-verified inputs. No ChemEngine output is faked — assertions
target values the engine actually computes (cross-checked during M22).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.main import app
from tests.conftest import MockGoogleTokenVerifier


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
        "biomolecule",
    }
    assert set(data["identity"].keys()) == {
        "formula",
        "exact_mass",
        "average_mass",
        "heavy_atom_count",
        "atom_count",
    }


# --- Biomolecular analysis (M40) ---


@pytest.mark.asyncio
async def test_biomolecule_tripeptide(client: AsyncClient) -> None:
    """The Cys-Val-Ala tripeptide is recognised as three residues, two bonds."""
    response = await _explore(
        client, "NC(C)C(=O)NC(C(C)C)C(=O)N1C(C(=O)O)CCC1"
    )
    assert response.status_code == 200
    data = response.json()
    bm = data["biomolecule"]
    assert bm is not None
    assert bm["biomolecule_class"] == "amino_acid"
    assert bm["residue_count"] == 3
    assert len(bm["residues"]) == 3
    assert bm["sequence"] == "AVP"
    assert len(bm["peptide_bonds"]) == 2
    # Each peptide bond is an atom-index triplet.
    for bond in bm["peptide_bonds"]:
        assert len(bond) == 3


@pytest.mark.asyncio
async def test_biomolecule_alanine_single_residue(client: AsyncClient) -> None:
    """Alanine is a single amino-acid residue (class amino_acid)."""
    response = await _explore(client, "NC(C)C(=O)O")
    assert response.status_code == 200
    data = response.json()
    bm = data["biomolecule"]
    assert bm is not None
    assert bm["biomolecule_class"] == "amino_acid"
    assert bm["residue_count"] == 1
    assert bm["sequence"] == "A"
    # No peptide bonds in a single residue.
    assert bm["peptide_bonds"] == []


@pytest.mark.asyncio
async def test_biomolecule_ethanol_class_none(client: AsyncClient) -> None:
    """Ethanol is structure-bearing but not biomolecular: class 'none'."""
    response = await _explore(client, "CCO")
    assert response.status_code == 200
    data = response.json()
    bm = data["biomolecule"]
    assert bm is not None
    assert bm["biomolecule_class"] == "none"
    assert bm["sequence"] == ""
    assert bm["residue_count"] == 0


@pytest.mark.asyncio
async def test_biomolecule_h2o_is_none(client: AsyncClient) -> None:
    """H2O is a bare formula — no structure, so biomolecule is null."""
    response = await _explore(client, "H2O")
    assert response.status_code == 200
    data = response.json()
    assert data["structure_available"] is False
    assert data["biomolecule"] is None


# --- Functional groups (added in M41) ---


@pytest.mark.asyncio
async def test_ethanol_explore_includes_functional_groups(client: AsyncClient) -> None:
    """The explore response now reports functional groups for structures."""
    response = await _explore(client, "CCO")
    assert response.status_code == 200
    data = response.json()
    groups = data["structure"]["functional_groups"]
    assert isinstance(groups, list)
    names = [g["name"] for g in groups]
    assert "Alcohol" in names
    alcohol = next(g for g in groups if g["name"] == "Alcohol")
    assert alcohol["atom_indices"]  # the -OH atoms
    assert set(alcohol["categories"]) >= {"oxygen", "hydroxy", "polar"}


@pytest.mark.asyncio
async def test_benzene_explore_functional_groups(client: AsyncClient) -> None:
    """Benzene is recognised as an aromatic ring in the functional groups."""
    response = await _explore(client, "c1ccccc1")
    assert response.status_code == 200
    groups = response.json()["structure"]["functional_groups"]
    assert any(g["name"] == "Aromatic Ring" for g in groups)


# --- explain_molecule endpoint (M41) ---


def _ethanol_facts() -> dict:
    """Deterministic ethanol facts (mirrors what the explain endpoint assembles)."""
    return {
        "formula": "C2H6O",
        "exact_mass": 46.041865,
        "average_mass": 46.069,
        "heavy_atom_count": 3,
        "atom_count": 9,
        "canonical_smiles": "CCO",
        "atom_symbols": ["C", "C", "O", "H", "H", "H", "H", "H", "H"],
        "bonds": [[0, 1, 1], [1, 2, 1], [0, 3, 1], [0, 4, 1], [0, 5, 1],
                  [1, 6, 1], [1, 7, 1], [2, 8, 1]],
        "functional_groups": [{"name": "Alcohol", "atom_indices": [1, 2],
                               "categories": ["oxygen", "hydroxy", "polar"]}],
        "properties": {"logp": 0.0823, "tpsa": 20.23, "hba": 1, "hbd": 1,
                       "rotatable_bonds": 0, "ring_count": 0, "fraction_csp3": 1.0},
    }


async def _authenticate(
    api_client: AsyncClient, verifier: MockGoogleTokenVerifier
) -> None:
    """Authenticate the test client via the mocked Google verifier (as M29 tests do)."""
    verifier.register_token("m41_token", sub="sub_m41", email="student@chemora.test")
    login = await api_client.post(
        "/api/v1/auth/google", json={"credential": "m41_token"}
    )
    assert login.status_code == 200


class TestExplainMolecule:
    """M41 explain_molecule endpoint: facts (ChemEngine) + explanation (tutor)."""

    async def test_explains_a_structure_bearing_molecule(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A structure-bearing input returns separate facts and explanation."""
        await _authenticate(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/chemistry/explain_molecule",
            json={"input": "CCO"},
        )
        assert response.status_code == 200
        body = response.json()
        # Facts are deterministic ChemEngine values, returned verbatim.
        facts = body["facts"]
        assert facts["formula"] == "C2H6O"
        assert facts["exact_mass"] == pytest.approx(46.041865, abs=1e-4)
        assert facts["atom_symbols"]
        assert facts["bonds"]
        assert any(g["name"] == "Alcohol" for g in facts["functional_groups"])
        assert facts["properties"]["hbd"] == 1
        # The explanation is the tutor's reasoning (not a fact echo).
        explanation = body["explanation"]
        assert isinstance(explanation, str) and explanation.strip()
        assert body["tools_used"] == []
        assert body["detected_type"] == "smiles"

    async def test_explains_respects_learning_mode_flag(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Both learning-mode values produce a valid explanation response."""
        await _authenticate(api_client, mock_google_verifier)
        base = {"input": "c1ccccc1"}  # benzene
        resp_standard = await api_client.post(
            "/api/v1/chemistry/explain_molecule",
            json={**base, "learning_mode": False},
        )
        resp_learning = await api_client.post(
            "/api/v1/chemistry/explain_molecule",
            json={**base, "learning_mode": True},
        )
        assert resp_standard.status_code == 200
        assert resp_learning.status_code == 200
        std = resp_standard.json()
        learn = resp_learning.json()
        assert std["facts"]["formula"] == "C6H6"
        assert learn["facts"]["formula"] == "C6H6"
        assert std["explanation"] and learn["explanation"]

    async def test_formula_input_without_structure_is_unsupported(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A bare formula has no structure to explain → unsupported_input."""
        await _authenticate(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/chemistry/explain_molecule",
            json={"input": "H2O"},
        )
        assert response.status_code == 422
        body = response.json()
        assert body["detail"]["code"] == "unsupported_input"
        assert "structure" in body["detail"]["message"].lower()

    async def test_unrecognized_input_is_unsupported(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Unrecognizable input surfaces as unsupported_input (no internals)."""
        await _authenticate(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/chemistry/explain_molecule",
            json={"input": "zzzznotamolecule"},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "unsupported_input"
        assert "traceback" not in response.text.lower()

    async def test_unauthenticated_rejected(
        self,
        api_client: AsyncClient,
    ) -> None:
        """The explain endpoint is session-gated (the AI tutor is not anonymous)."""
        response = await api_client.post(
            "/api/v1/chemistry/explain_molecule",
            json={"input": "CCO"},
        )
        assert response.status_code == 401

    async def test_no_internals_on_tutor_failure(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A provider failure maps to a stable status, not a 500 traceback."""
        await _authenticate(api_client, mock_google_verifier)
        from app.services.ai.provider import AIProviderError, MockAIProvider

        def failing(*_a: object, **_k: object) -> str:  # noqa: ANN401
            raise AIProviderError("unavailable", "tutor down")

        monkeypatch.setattr(MockAIProvider, "generate", failing)
        response = await api_client.post(
            "/api/v1/chemistry/explain_molecule",
            json={"input": "CCO"},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "ai_unavailable"
        assert "traceback" not in response.text.lower()
