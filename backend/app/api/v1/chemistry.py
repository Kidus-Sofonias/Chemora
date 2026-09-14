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
from pydantic import BaseModel, Field

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


class MoleculeStructure(BaseModel):
    """Structure representation, present only for structure-bearing inputs."""

    canonical_smiles: str
    formula: str
    atom_symbols: list[str]
    bonds: list[list[int]]
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


class ChemistryExploreResponse(BaseModel):
    """Structured result of a chemistry exploration."""

    input: str
    detected_type: str | None
    structure_available: bool
    identity: MoleculeIdentity
    structure: MoleculeStructure | None
    properties: MoleculeProperties | None


class ChemistryErrorDetail(BaseModel):
    """Stable machine-readable error code plus a user-facing message."""

    code: str
    message: str


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
            MoleculeStructure(**result.structure) if result.structure is not None else None
        ),
        properties=(
            MoleculeProperties(**result.properties) if result.properties is not None else None
        ),
    )


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
