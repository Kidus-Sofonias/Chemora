"""Chemistry Explorer API endpoints.

Exposes deterministic ChemEngine functionality as a clean application API.

    POST /api/v1/chemistry/explore

The backend is an application-layer adapter — all chemistry computation is
performed by ChemEngine, never duplicated here.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.services.ai.service import (
    AI_AUTH,
    AI_ERROR,
    AI_TIMEOUT,
    AI_UNAVAILABLE,
    RATE_LIMITED,
    TutorError,
    TutorService,
)
from app.services.chemistry import ChemistryError, ChemistryResult, ChemistryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chemistry", tags=["chemistry"])

_service = ChemistryService()


# --- Request / Response Models ---


class ChemistryExploreRequest(BaseModel):
    """Request body for exploring a chemical identifier."""

    input: str = Field(description="Formula, SMILES, InChI, or common name")


class MoleculeIdentity(BaseModel):
    """Elemental identity — correct for every input type."""

    formula: str
    exact_mass: float
    average_mass: float
    heavy_atom_count: int
    atom_count: int


class FunctionalGroup(BaseModel):
    """A curricular functional-group match — student-safe surface only."""

    name: str
    atom_indices: list[int]
    categories: list[str]


class MoleculeStructure(BaseModel):
    """Structure representation, present only for structure-bearing inputs."""

    canonical_smiles: str
    formula: str
    atom_symbols: list[str]
    bonds: list[list[int]]
    functional_groups: list[FunctionalGroup] = Field(default_factory=list)
    svg: str


class MoleculeProperties(BaseModel):
    """Bond-derived descriptors computed by ChemEngine."""

    logp: float
    tpsa: float
    hba: int
    hbd: int
    rotatable_bonds: int
    ring_count: int
    fraction_csp3: float


class BiomoleculeResidue(BaseModel):
    """One recognised residue (engine analysis, not stored content)."""

    type: str
    atom_indices: list[int]
    position: int
    one_letter_code: str


class BiomoleculeAnalysis(BaseModel):
    """M40 biomolecular analysis returned with the explore result."""
    schema_version: str = Field(
        ...,  # required
        validation_alias="schema",
        serialization_alias="schema",
    )

    residue_count: int
    residues: list[BiomoleculeResidue]
    sequence: str
    peptide_bonds: list[list[int]]
    biomolecule_class: str
    chain_length: int
    molecular_formula: str
    canonical_smiles: str


class ChemistryExploreResponse(BaseModel):
    """Structured result of a chemistry exploration."""

    model_config = ConfigDict(populate_by_name=True)

    input: str
    detected_type: str | None
    structure_available: bool
    identity: MoleculeIdentity
    structure: MoleculeStructure | None
    properties: MoleculeProperties | None
    biomolecule: BiomoleculeAnalysis | None = None


class ChemistryErrorDetail(BaseModel):
    """Stable machine-readable error code plus a user-facing message."""

    code: str
    message: str


class ChemistryExplainRequest(BaseModel):
    """Request body for explaining a molecule."""

    input: str = Field(description="Formula, SMILES, InChI, or common name")
    learning_mode: bool = Field(
        default=True,
        description="Request a student-friendly explanation (plain language, analogies).",
    )


class MoleculeExplainFacts(BaseModel):
    """Deterministic ChemEngine data supplied to the tutor as ground truth."""

    formula: str
    exact_mass: float
    average_mass: float
    heavy_atom_count: int
    atom_count: int
    canonical_smiles: str
    atom_symbols: list[str]
    bonds: list[list[int]]
    functional_groups: list[FunctionalGroup] = Field(default_factory=list)
    properties: dict[str, object] | None = None


class ChemistryExplainResponse(BaseModel):
    """Molecule explanation: deterministic facts + an AI explanation."""

    input: str
    detected_type: str | None
    facts: MoleculeExplainFacts
    explanation: str
    tools_used: list[str]


def get_chemistry_service() -> ChemistryService:
    """Return the shared ChemistryService singleton."""
    return _service


# --- Helper ---


def _to_response(result: ChemistryResult) -> ChemistryExploreResponse:
    """Convert a ChemistryResult into the API response model."""
    identity_data = result.identity
    return ChemistryExploreResponse(
        input=result.input,
        detected_type=result.detected_type,
        structure_available=result.structure_available,
        identity=MoleculeIdentity(
            formula=cast(str, identity_data["formula"]),
            exact_mass=cast(float, identity_data["exact_mass"]),
            average_mass=cast(float, identity_data["average_mass"]),
            heavy_atom_count=cast(int, identity_data["heavy_atom_count"]),
            atom_count=cast(int, identity_data["atom_count"]),
        ),
        structure=(
            MoleculeStructure.model_validate(result.structure)
            if result.structure is not None
            else None
        ),
        properties=(
            MoleculeProperties.model_validate(result.properties)
            if result.properties is not None
            else None
        ),
        biomolecule=(
            BiomoleculeAnalysis.model_validate(result.biomolecule)
            if result.biomolecule is not None
            else None
        ),
    )


def _to_explain_facts(result: ChemistryResult) -> dict[str, object]:
    """Assemble the deterministic molecule facts for the explain endpoint.

    Pulls identity, structure (atoms/bonds/functional groups), and descriptors
    straight out of the ChemEngine result so the tutor receives only verified,
    engine-computed data.
    """
    identity = result.identity
    structure = result.structure or {}
    return {
        "formula": cast(str, identity["formula"]),
        "exact_mass": cast(float, identity["exact_mass"]),
        "average_mass": cast(float, identity["average_mass"]),
        "heavy_atom_count": cast(int, identity["heavy_atom_count"]),
        "atom_count": cast(int, identity["atom_count"]),
        "canonical_smiles": cast(str, structure.get("canonical_smiles", "")),
        "atom_symbols": cast(list, structure.get("atom_symbols", [])),
        "bonds": cast(list, structure.get("bonds", [])),
        "functional_groups": cast(list, structure.get("functional_groups", [])),
        "properties": result.properties,
    }


#: Stable tutor error codes mapped to HTTP statuses (explain endpoint).
_TUTOR_STATUS_BY_CODE = {
    AI_AUTH: 500,
    AI_ERROR: 500,
    AI_TIMEOUT: 504,
    AI_UNAVAILABLE: 503,
    RATE_LIMITED: 429,
}


# --- Endpoints ---


@router.post(
    "/explore",
    response_model=ChemistryExploreResponse,
    summary="Explore a chemical identifier",
    responses={
        422: {"model": ChemistryErrorDetail, "description": "Invalid or unsupported input"},
    },
)
async def explore(
    request: ChemistryExploreRequest,
    service: Annotated[ChemistryService, Depends(get_chemistry_service)],
) -> ChemistryExploreResponse:
    """Analyse a formula, SMILES, InChI, or common name through ChemEngine.

    The chemistry computation is CPU-bound and synchronous (ChemEngine), so it
    is offloaded to the event loop's thread pool rather than blocking the async
    handler.
    """
    try:
        result = await asyncio.to_thread(service.explore, request.input)
    except ChemistryError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception:
        logger.exception("Unexpected error during chemistry exploration")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_error",
                "message": "We ran into a problem analysing that input. Please try again.",
            },
        ) from None
    return _to_response(result)


@router.post(
    "/explain_molecule",
    response_model=ChemistryExplainResponse,
    summary="Explain a molecule (facts from ChemEngine, explanation from the AI tutor)",
    responses={
        401: {"model": ChemistryErrorDetail, "description": "Not authenticated"},
        422: {
            "model": ChemistryErrorDetail,
            "description": "Input is not a structure-bearing molecule",
        },
        503: {"model": ChemistryErrorDetail, "description": "AI tutor unavailable"},
    },
)
async def explain_molecule(
    request: ChemistryExplainRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ChemistryService, Depends(get_chemistry_service)],
) -> ChemistryExplainResponse:
    """Explain a molecule, separating deterministic facts from the AI explanation.

    Deterministic chemistry (formula, masses, atoms, bonds, functional groups,
    descriptors) is computed by ChemEngine through the chemistry service, then
    passed to the AI tutor as structured context. The facts are returned to the
    client unchanged (engine ground truth); the model supplies only the
    `explanation` — its conceptual reasoning. This enforces the
    fact-vs-explanation distinction: facts are computed, the explanation reasons.

    The endpoint is session-gated because it invokes the AI tutor; the caller's
    identity comes from the server session, never from the client.
    """
    try:
        result = await asyncio.to_thread(service.explore, request.input)
    except ChemistryError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception:  # noqa: BLE001 — never leak internals to the client
        logger.exception("Unexpected error during chemistry exploration")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_error",
                "message": "We ran into a problem analysing that input. Please try again.",
            },
        ) from None

    if not result.structure_available or result.structure is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_input",
                "message": (
                    "We can only explain molecules with a structure. Enter a "
                    "SMILES string, an InChI, or a common name."
                ),
            },
        )

    facts = _to_explain_facts(result)
    tutor = TutorService(db)
    try:
        answer = await tutor.explain(
            user.id, facts, learning_mode=request.learning_mode
        )
    except TutorError as exc:
        raise HTTPException(
            status_code=_TUTOR_STATUS_BY_CODE.get(exc.code, 500),
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    return ChemistryExplainResponse(
        input=result.input,
        detected_type=result.detected_type,
        facts=MoleculeExplainFacts(**facts),
        explanation=answer.answer,
        tools_used=answer.tools_used,
    )
