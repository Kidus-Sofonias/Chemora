"""Element service — thin application-layer adapter over ChemEngine.

The backend is a Facade adapter. All element data and all electron-configuration
computation is delegated to ChemEngine (``chemengine.core.element`` and
``chemengine.education.electron_config``); nothing here re-implements chemistry.

Design notes (based on verified ChemEngine behaviour):
- ``Element.all_elements()`` exposes the full 118-element dataset with
  period/group/block/category metadata.
- ``Element`` lookups are exact-match (case-sensitive symbols, exact names),
  so this service performs identifier *normalisation* (presentation-level
  convenience: digit strings → atomic number, capitalised symbols, lowercased
  names) — not chemistry.
- ``ElectronConfigurator().for_element(element)`` computes the full
  configuration from first principles (Aufbau/Hund/Pauli) and exposes the
  shorthand, shell/subshell distributions, the structured orbital diagram, and
  valence/core/unpaired electron counts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from chemengine.core.element import Element
from chemengine.education.electron_config import ElectronConfigurator

logger = logging.getLogger(__name__)


class ElementError(Exception):
    """A stable, client-safe element error.

    Attributes:
        code: Stable machine code (``'unknown_element'`` | ``'invalid_identifier'``).
        message: A user-facing message without internal details.
    """

    def __init__(self, code: str, message: str) -> None:
        """Initialize with a stable code and a user-facing message."""
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ElementSummaryData:
    """Periodic-table metadata for one element."""

    atomic_number: int
    symbol: str
    name: str
    atomic_mass: float
    period: int
    group: int
    block: str
    category: str


@dataclass(frozen=True, slots=True)
class ElementDetailData:
    """Full element exploration result: identity + electron structure."""

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
    orbitals: list[dict[str, object]]
    explanation: str


class ElementService:
    """Adapter exposing ChemEngine's element subsystem to the API."""

    def list_elements(self) -> list[ElementSummaryData]:
        """Return the full periodic table metadata, ordered by atomic number."""
        elements = sorted(Element.all_elements(), key=lambda e: e.atomic_number)
        return [
            ElementSummaryData(
                atomic_number=int(e.atomic_number),
                symbol=e.symbol,
                name=e.name,
                atomic_mass=round(float(e.atomic_mass), 6),
                period=int(e.period),
                group=int(e.group),
                block=e.block,
                category=e.category,
            )
            for e in elements
        ]

    def get_element(self, identifier: str) -> ElementDetailData:
        """Resolve an element identifier and compute its electron structure.

        Args:
            identifier: Element symbol (e.g. ``O``), name (e.g. ``oxygen``),
                or atomic number (e.g. ``8``). Case-insensitive.

        Returns:
            The full structured element detail.

        Raises:
            ElementError: If the identifier is empty or no element matches.
        """
        element = self._resolve(identifier)
        config = ElectronConfigurator().for_element(element)
        return ElementDetailData(
            atomic_number=int(element.atomic_number),
            symbol=element.symbol,
            name=element.name,
            atomic_mass=round(float(element.atomic_mass), 6),
            period=int(element.period),
            group=int(element.group),
            block=element.block,
            category=element.category,
            config_full=config.full,
            config_shorthand=config.shorthand,
            noble_gas=config.noble_gas,
            valence_electrons=int(config.valence_electrons),
            core_electrons=int(config.core_electrons),
            unpaired_electrons=int(config.unpaired_electrons),
            shells={
                str(shell): count
                for shell, count in sorted(config.shell_distribution.items())
            },
            subshells=dict(sorted(config.subshell_distribution.items())),
            orbitals=[
                {
                    "orbital": occ.orbital,
                    "electrons": int(occ.electrons),
                    "capacity": int(occ.capacity),
                    "subshell": occ.subshell,
                    "shell": int(occ.shell),
                }
                for occ in config.diagram.occupancies
                if occ.electrons > 0
            ],
            explanation=config.explain(),
        )

    def _resolve(self, identifier: str) -> Element:
        """Normalise a user identifier and resolve it through ChemEngine."""
        text = identifier.strip()
        if not text:
            raise ElementError(
                "invalid_identifier",
                "Please choose an element by symbol, name, or atomic number.",
            )
        if len(text) > 40:
            raise ElementError(
                "invalid_identifier",
                "That element identifier is too long.",
            )

        try:
            if text.isdigit():
                element = Element.from_z(int(text))
            else:
                try:
                    element = Element.from_symbol(text[:3].capitalize())
                except KeyError:
                    element = Element.from_name(text.lower())
        except (KeyError, ValueError) as exc:
            logger.info(
                "Could not resolve element identifier",
                extra={"error_type": type(exc).__name__},
            )
            raise ElementError(
                "unknown_element",
                "We couldn't find that element. Try a symbol (e.g. O), a name "
                "(e.g. oxygen), or an atomic number (e.g. 8).",
            ) from exc
        logger.info("Resolved element identifier", extra={"symbol": element.symbol})
        return element

