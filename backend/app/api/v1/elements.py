"""Element Explorer API endpoints.

Exposes ChemEngine's element / electron-configuration subsystem as a clean
application API.

    GET /api/v1/elements               → periodic-table metadata (118 elements)
    GET /api/v1/elements/{identifier}  → full detail + computed electron structure

All element data and electron-configuration computation is performed by
ChemEngine; this module only defines the Pydantic contract and error mapping.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.elements import ElementDetailData, ElementError, ElementService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/elements", tags=["elements"])

_service = ElementService()


# --- Response Models ---


class ElementSummary(BaseModel):
    """Periodic-table metadata for one element."""

    atomic_number: int
    symbol: str
    name: str
    atomic_mass: float
    period: int
    group: int
    block: str
    category: str


class ElementListResponse(BaseModel):
    """The complete periodic table metadata."""

    elements: list[ElementSummary]


class OrbitalOccupancyOut(BaseModel):
    """One occupied subshell in the orbital diagram."""

    orbital: str
    electrons: int
    capacity: int
    subshell: str
    shell: int


class ElementDetail(BaseModel):
    """Full element exploration result: identity + computed electron structure."""

    atomic_number: int
    symbol: str
    name: str
    atomic_mass: float
    period: int
    group: int
    block: str
    category: str
    config_full: str
    config_shorthand: str
    noble_gas: str
    valence_electrons: int
    core_electrons: int
    unpaired_electrons: int
    shells: dict[str, int]
    subshells: dict[str, int]
    orbitals: list[OrbitalOccupancyOut]
    explanation: str


class ElementErrorDetail(BaseModel):
    """Stable machine-readable error code plus a user-facing message."""

    code: str
    message: str


def get_element_service() -> ElementService:
    """Return the shared ElementService singleton."""
    return _service


def _to_detail(data: ElementDetailData) -> ElementDetail:
    """Convert a service result into the API response model."""
    return ElementDetail(
        atomic_number=data.atomic_number,
        symbol=data.symbol,
        name=data.name,
        atomic_mass=data.atomic_mass,
        period=data.period,
        group=data.group,
        block=data.block,
        category=data.category,
        config_full=data.config_full,
        config_shorthand=data.config_shorthand,
        noble_gas=data.noble_gas,
        valence_electrons=data.valence_electrons,
        core_electrons=data.core_electrons,
        unpaired_electrons=data.unpaired_electrons,
        shells=data.shells,
        subshells=data.subshells,
        orbitals=[OrbitalOccupancyOut(**occ) for occ in data.orbitals],
        explanation=data.explanation,
    )


@router.get(
    "",
    response_model=ElementListResponse,
    summary="List the periodic table",
)
async def list_elements(
    service: Annotated[ElementService, Depends(get_element_service)],
) -> ElementListResponse:
    """Return metadata for every element, ordered by atomic number.

    The dataset is small (118 elements) and read-only, so a single request is
    the simplest coherent contract for the periodic table.
    """
    elements = await asyncio.to_thread(service.list_elements)
    return ElementListResponse(
        elements=[
            ElementSummary(
                atomic_number=e.atomic_number,
                symbol=e.symbol,
                name=e.name,
                atomic_mass=e.atomic_mass,
                period=e.period,
                group=e.group,
                block=e.block,
                category=e.category,
            )
            for e in elements
        ]
    )


@router.get(
    "/{identifier}",
    response_model=ElementDetail,
    summary="Explore an element",
    responses={
        404: {"model": ElementErrorDetail, "description": "Unknown element"},
    },
)
async def get_element(
    identifier: str,
    service: Annotated[ElementService, Depends(get_element_service)],
) -> ElementDetail:
    """Resolve an element by symbol, name, or atomic number.

    Returns its computed electron structure from ChemEngine.
    """
    try:
        detail = await asyncio.to_thread(service.get_element, identifier)
    except ElementError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception:
        logger.exception("Unexpected error while exploring element")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_error",
                "message": "We ran into a problem exploring that element. "
                "Please try again.",
            },
        ) from None
    return _to_detail(detail)
