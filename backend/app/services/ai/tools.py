"""ChemEngine tool boundary for the AI tutor (M29).

Model-supplied tool calls are treated as untrusted input. This module is the
only place where a tutor tool call reaches ChemEngine, and it enforces:

1. **Allowlist** — only a fixed set of student-appropriate tools is exposed.
   Unknown or disallowed tool names are rejected before execution.
2. **Schema validation** — arguments are validated against the tool's
   registered JSON schema (required keys, types, bounds) before execution.
3. **Controlled errors** — any failure becomes a :class:`ToolError` with a
   stable code; raw engine exceptions never reach the model or the client.

Allowlist rationale (derived from ChemEngine's 13-tool registry):
``parse_smiles``/``parse_formula`` (deterministic identity),
``compute_property`` (masses/descriptors), ``validate``,
``detect_functional_groups``, ``calculate_electron_configuration``.

Deliberately **not** exposed: ``sanitize`` (mutates structures),
``generate_2d_coordinates``/``generate_3d_conformer`` (heavy, irrelevant to
tutoring), ``render_svg`` (the explorer UI already renders structures),
``serialize`` (dumps full graphs), ``generate_inchi`` (non-IUPAC-standard
serializers deliberately not exposed anywhere in the product).
"""

from __future__ import annotations

import logging
from typing import Any

from chemengine.core.tool_interface import ChemEngineAPI

logger = logging.getLogger(__name__)

#: Tools the tutor may invoke, with the reason each is exposed.
TUTOR_TOOLS: dict[str, str] = {
    "parse_smiles": "deterministic identity from a SMILES string",
    "parse_formula": "deterministic identity from a molecular formula",
    "compute_property": "deterministic masses and molecular descriptors",
    "validate": "chemical-correctness checks on a structure",
    "detect_functional_groups": "curriculum-relevant functional-group analysis",
    "calculate_electron_configuration": "Madelung-rule electron configurations",
}

_MAX_STRING_ARG_LENGTH = 200
_MAX_LIST_ARG_LENGTH = 20


class ToolError(Exception):
    """A controlled tool failure. Safe to surface to the model/client."""

    def __init__(self, code: str, message: str) -> None:
        """Initialize with a stable code and user-facing message."""
        super().__init__(message)
        self.code = code
        self.message = message


class TutorToolbox:
    """Validated, allowlisted bridge between the tutor loop and ChemEngine."""

    def __init__(self, engine: ChemEngineAPI | None = None) -> None:
        """Initialize with the ChemEngine facade (shared instance by default)."""
        self._engine = engine if engine is not None else ChemEngineAPI()

    @property
    def allowed_names(self) -> frozenset[str]:
        """The names of every tool the tutor may call."""
        return frozenset(TUTOR_TOOLS)

    def openai_tool_definitions(self) -> list[dict[str, Any]]:
        """OpenAI function-calling definitions for the allowlisted tools."""
        definitions: list[dict[str, Any]] = []
        for tool in self._engine.list_tools():
            if tool.name not in TUTOR_TOOLS:
                continue
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
            )
        return definitions

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate and execute one allowlisted tool call.

        Raises:
            ToolError: On unknown/disallowed tools, invalid arguments, or any
                engine failure (never a raw exception).
        """
        if name not in TUTOR_TOOLS:
            raise ToolError("tool_not_allowed", f"Tool '{name}' is not available to the tutor.")
        if not isinstance(arguments, dict):
            raise ToolError("invalid_arguments", "Tool arguments must be an object.")

        schema = self._input_schema(name)
        if schema is None:
            raise ToolError("tool_unavailable", "That tool is temporarily unavailable.")
        self._validate_arguments(name, arguments, schema)

        try:
            result = self._engine.execute_tool(name, arguments)
        except Exception as exc:  # noqa: BLE001 - boundary converts everything
            logger.warning("Tutor tool '%s' failed: %s", name, type(exc).__name__)
            raise ToolError("tool_failed", "The chemistry calculation failed.") from exc

        if not isinstance(result, dict):
            raise ToolError("tool_failed", "The chemistry calculation failed.")
        # ChemEngine returns {"error": ...} on internal failure.
        if "error" in result:
            raise ToolError("tool_failed", "The chemistry calculation failed.")
        return result

    # ── Validation internals ──────────────────────────────────────────

    def _input_schema(self, name: str) -> dict[str, Any] | None:
        """Return the registered input schema for an allowlisted tool."""
        for tool in self._engine.list_tools():
            if tool.name == name:
                schema: dict[str, Any] = dict(tool.input_schema)
                return schema
        return None

    def _validate_arguments(
        self, name: str, arguments: dict[str, Any], schema: dict[str, Any]
    ) -> None:
        """Minimal JSON-schema validation: required keys, types, bounds."""
        for key in schema.get("required", []):
            if key not in arguments:
                raise ToolError(
                    "invalid_arguments", f"Missing required argument '{key}' for '{name}'."
                )
        properties = schema.get("properties", {})
        for key, value in arguments.items():
            if key not in properties:
                raise ToolError("invalid_arguments", f"Unknown argument '{key}' for '{name}'.")
            expected = properties[key].get("type")
            if expected is None:
                continue
            types = expected if isinstance(expected, list) else [expected]
            if not self._type_matches(value, types):
                raise ToolError(
                    "invalid_arguments", f"Argument '{key}' for '{name}' has the wrong type."
                )
            if isinstance(value, str) and len(value) > _MAX_STRING_ARG_LENGTH:
                raise ToolError("invalid_arguments", f"Argument '{key}' is too long.")
            if isinstance(value, list) and len(value) > _MAX_LIST_ARG_LENGTH:
                raise ToolError("invalid_arguments", f"Argument '{key}' has too many items.")

    @staticmethod
    def _type_matches(value: Any, types: list[str]) -> bool:  # noqa: ANN401
        """Check a JSON value against JSON-schema type names."""
        for expected in types:
            if expected == "string" and isinstance(value, str):
                return True
            if expected == "integer" and isinstance(value, int) and not isinstance(value, bool):
                return True
            if expected == "number" and isinstance(value, (int, float)) and not isinstance(
                value, bool
            ):
                return True
            if expected == "boolean" and isinstance(value, bool):
                return True
            if expected == "array" and isinstance(value, list):
                return True
            if expected == "object" and isinstance(value, dict):
                return True
        return False


