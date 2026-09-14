"""Chemistry service — thin application-layer adapter over ChemEngine.

The backend is a Facade adapter. All deterministic chemistry is delegated to
ChemEngine; nothing here re-implements chemistry algorithms.

Design notes (based on verified ChemEngine behaviour):
- ``parse_any`` auto-detects formula / SMILES / InChI / common name inputs.
- A bare **molecular formula does not encode connectivity**, so a formula
  parsed by the engine yields an identity (formula, masses, heavy atoms) but
  not a reliable molecular structure. For formula inputs the service therefore
  returns identity only and reports ``structure_available=False``.
- Structure-bearing inputs (SMILES, InChI, resolved names) produce a connected
  graph: the service returns the canonical SMILES, an engine-rendered SVG
  depiction, atoms/bonds, and bond-derived descriptors (logP, TPSA, HBA, HBD,
  rotatable bonds, ring count, fraction C(sp3)).
- The engine's InChI/InChIKey serializers are non-IUPAC-standard, so they are
  deliberately not exposed as production identifiers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from chemengine.core.graph import MolecularGraph
from chemengine.core.tool_interface import ChemEngineAPI
from chemengine.io.serialization import graph_to_dict
from chemengine.parsing.protocol import auto_detect_format
from chemengine.rendering.svg import render_svg

logger = logging.getLogger(__name__)

# Input types that carry explicit molecular structure (connectivity). Only for
# these does the engine reliably produce a real structure.
_STRUCTURAL_INPUT_TYPES = frozenset({"smiles", "inchi", "name"})

_MAX_INPUT_LENGTH = 160


class ChemistryError(Exception):
    """A stable, client-safe chemistry error.

    Attributes:
        code: Stable machine code ('invalid_input' | 'unsupported_input').
        message: A user-facing message without internal details.
    """

    def __init__(self, code: str, message: str) -> None:
        """Initialize with a stable code and a user-facing message."""
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ChemistryResult:
    """Structured, verified chemistry result for the explorer API."""

    input: str
    detected_type: str | None
    structure_available: bool
    identity: dict[str, object]
    structure: dict[str, object] | None = None
    properties: dict[str, object] | None = None


def _get_engine() -> ChemEngineAPI:
    """Return the shared ChemEngineAPI instance (module-level singleton)."""
    return ChemEngineAPI()
class ChemistryService:
    """Adapter that turns a raw user string into structured chemistry."""

    def __init__(self, engine: ChemEngineAPI | None = None) -> None:
        """Initialize with a ChemEngine facade (defaults to a shared instance)."""
        self._engine = engine if engine is not None else _get_engine()

    def explore(self, raw_input: str) -> ChemistryResult:
        """Analyse a user input through ChemEngine.

        Args:
            raw_input: User-provided chemical identifier.

        Returns:
            A structured ChemistryResult (identity always; structure and
            bond-derived descriptors only for structure-bearing inputs).

        Raises:
            ChemistryError: If the input is empty, too long, or unparseable.
        """
        text = raw_input.strip()
        if not text:
            raise ChemistryError(
                "invalid_input",
                "Please enter a molecule, formula, or SMILES.",
            )
        if len(text) > _MAX_INPUT_LENGTH:
            raise ChemistryError(
                "invalid_input",
                "That input is too long. Enter a smaller molecule.",
            )

        detected_type = auto_detect_format(text)

        try:
            graph = self._engine.parse(text)
        except ValueError as exc:
            logger.info(
                "Could not parse chemistry input",
                extra={
                    "detected_type": detected_type,
                    "error_type": type(exc).__name__,
                },
            )
            raise ChemistryError(
                "unsupported_input",
                "We couldn't recognize that input. Try a molecular formula "
                "(e.g. H2O), a SMILES string (e.g. CCO), an InChI string, or "
                "a common name (e.g. ethanol).",
            ) from exc

        identity = {
            "formula": graph.molecular_formula,
            "exact_mass": round(float(graph.exact_mass), 6),
            "average_mass": round(float(graph.molecular_weight), 6),
            "heavy_atom_count": int(graph.num_heavy_atoms),
            "atom_count": int(graph.num_atoms),
        }

        structure_available = detected_type in _STRUCTURAL_INPUT_TYPES

        if not structure_available:
            return ChemistryResult(
                input=text,
                detected_type=detected_type,
                structure_available=False,
                identity=identity,
            )

        return ChemistryResult(
            input=text,
            detected_type=detected_type,
            structure_available=True,
            identity=identity,
            structure=self._structure(graph),
            properties=self._properties(graph),
        )

    def _structure(self, graph: MolecularGraph) -> dict[str, object]:
        """Build the structure block (canonical SMILES + SVG + atoms + bonds)."""
        serialized = graph_to_dict(graph)
        atoms = [a["symbol"] for a in serialized.get("atoms", [])]
        bonds = [
            [int(b["atom1"]), int(b["atom2"]), int(b["order"])]
            for b in serialized.get("bonds", [])
        ]
        return {
            "canonical_smiles": self._engine.convert(graph, "smiles"),
            "formula": graph.molecular_formula,
            "atom_symbols": atoms,
            "bonds": bonds,
            "svg": render_svg(graph),
        }

    def _properties(self, graph: MolecularGraph) -> dict[str, object]:
        """Compute bond-derived descriptors (delegated to ChemEngine)."""
        return {
            "logp": round(float(self._engine.compute(graph, "logp")), 4),
            "tpsa": round(float(self._engine.compute(graph, "tpsa")), 4),
            "hba": int(self._engine.compute(graph, "hba")),
            "hbd": int(self._engine.compute(graph, "hbd")),
            "rotatable_bonds": int(self._engine.compute(graph, "rotatable_bonds")),
            "ring_count": int(self._engine.compute(graph, "num_rings")),
            "fraction_csp3": round(
                float(self._engine.compute(graph, "fraction_csp3")), 4
            ),
        }
