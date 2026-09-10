"""ChemEngineAPI — the universal query/tool interface for all consumers.

This is the single external-facing facade for the entire chemistry engine.
It wraps the registry, event bus, plugin manager, and dataset registry into
a unified API that can power:
    - AI agents (LLM function-calling)
    - CLIs (command-line tools)
    - Web APIs (FastAPI / Flask endpoints)
    - Desktop / mobile applications
    - Python library users

The API is self-describing: tools expose their input/output schemas as JSON
Schema, enabling AI agents to discover and use them automatically.

Architecture:
    - ToolDefinition: Self-describing tool metadata with JSON Schemas.
    - ChemEngineAPI: The unified facade with type-safe convenience methods
      and a generic execute_tool() for AI integration.

Design decisions:
    - Single facade: All capabilities accessible through one object.
    - Self-describing: All tools listable with full JSON Schema.
    - Type-safe convenience methods for direct Python usage.
    - Generic execute_tool() for dynamic/LLM-driven usage.
    - Correlation IDs for pipeline tracing through the event bus.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

from chemengine.core.graph import MolecularGraph
from chemengine.validation.report import ValidationResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Self-describing tool metadata for AI/LLM integration.

    Each tool exposes its name, description, input schema, output schema,
    and category. This enables AI agents to discover what the engine can do
    and how to call each function.

    Attributes:
        name: Unique tool name (e.g., 'parse_smiles').
        description: Human-readable description of what the tool does.
        input_schema: JSON Schema dict describing expected input.
        output_schema: JSON Schema dict describing the output format.
        category: Tool category ('parsing', 'generation', 'detection', etc.).
        tags: Optional tags for filtering and discovery.
    """

    name: str
    """Unique tool name (snake_case, e.g., 'parse_smiles')."""

    description: str
    """Human-readable description of what the tool does."""

    input_schema: dict[str, Any]
    """JSON Schema describing the expected input parameters."""

    output_schema: dict[str, Any]
    """JSON Schema describing the output format."""

    category: str = "general"
    """Tool category for grouping ('parsing', 'generation', 'detection', etc.)."""

    tags: frozenset[str] = frozenset()
    """Tags for filtering and discovery."""


class ChemEngineAPI:
    """Unified facade for the chemistry engine.

    Provides both type-safe convenience methods (for direct Python usage)
    and a generic execute_tool() method (for AI/dynamic usage).

    Usage:
        >>> api = ChemEngineAPI()
        >>> graph = api.parse("CCO", fmt="smiles")
        >>> print(graph.molecular_formula)
        'C2H6O'

        >>> tools = api.list_tools(category="parsing")
        >>> result = api.execute_tool("parse_smiles", {"smiles": "CCO"})
    """

    def __init__(self, registry: Any | None = None, bus: Any | None = None,
                 plugin_mgr: Any | None = None, datasets: Any | None = None) -> None:
        """Initialize the ChemEngineAPI.

        Args:
            registry: Optional AlgorithmRegistry (uses global if not provided).
            bus: Optional EventBus (uses global if not provided).
            plugin_mgr: Optional PluginManager (creates new if not provided).
            datasets: Optional DatasetRegistry (creates new if not provided).
        """
        from chemengine.core.datasets import get_global_dataset_registry
        from chemengine.core.events import get_global_bus
        from chemengine.core.plugin import PluginManager
        from chemengine.core.registry import get_global_registry

        self._registry = registry or get_global_registry()
        self._bus = bus or get_global_bus()
        self._plugin_mgr = plugin_mgr or PluginManager()
        self._datasets = datasets or get_global_dataset_registry()
        self._tools: dict[str, ToolDefinition] = {}
        self._register_builtin_tools()
        self._register_builtin_algorithms()

    # ── AI Tool Interface ──

    def list_tools(self, category: str | None = None,
                   tags: set[str] | None = None) -> list[ToolDefinition]:
        """List all available tools, optionally filtered.

        Args:
            category: Optional category filter.
            tags: Optional set of required tags.

        Returns:
            List of ToolDefinition objects matching the filters.
        """
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if tags:
            tools = [t for t in tools if tags.issubset(t.tags)]
        return tools

    def execute_tool(self, name: str, params: dict[str, Any],
                     correlation_id: str | None = None) -> dict[str, Any]:
        """Execute a tool by name with the given parameters.

        This is the primary entry point for AI agents. It validates the
        tool exists, executes it, and returns a structured result.

        Args:
            name: The tool name (e.g., 'parse_smiles').
            params: Parameters matching the tool's input_schema.
            correlation_id: Optional ID for pipeline tracing.

        Returns:
            A dict with the tool's output (matching output_schema).

        Raises:
            KeyError: If the tool is not found.
            ValueError: If parameters are invalid.
        """
        if name not in self._tools:
            available = ", ".join(sorted(self._tools.keys()))
            raise KeyError(f"Unknown tool '{name}'. Available tools: {available}")

        tool_def = self._tools[name]
        logger.info(f"Executing tool '{name}' with params={params}")

        # Find the implementation method
        method_name = f"_exec_{name}"
        if hasattr(self, method_name):
            method = getattr(self, method_name)
        else:
            raise NotImplementedError(f"Tool '{name}' has no implementation")

        try:
            result = method(params, correlation_id)
            # Publish tool executed event
            self._bus.publish(self._make_event(
                "tool.executed",
                {"tool": name, "params": params, "result": result},
                "tool_interface",
                correlation_id,
            ))
            return cast("dict[str, Any]", result)
        except Exception as e:
            logger.exception(f"Tool '{name}' failed: {e}")
            self._bus.publish(self._make_event(
                "tool.failed",
                {"tool": name, "params": params, "error": str(e)},
                "tool_interface",
                correlation_id,
            ))
            return {"error": str(e)}

    def execute_batch(self, calls: list[tuple[str, dict[str, Any], str | None]]
                      ) -> list[dict[str, Any]]:
        """Execute multiple tools in sequence.

        Args:
            calls: List of (tool_name, params, correlation_id) tuples.

        Returns:
            List of result dicts, one per call.
        """
        return [self.execute_tool(name, params, cid) for name, params, cid in calls]

    # ── Type-Safe Convenience Methods ──

    def parse(self, text: str, fmt: str | None = None) -> MolecularGraph:
        """Parse a chemical identifier (SMILES, InChI, formula, name) into a graph.

        Args:
            text: The input string (e.g., 'CCO', 'InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3').
            fmt: Optional format hint ('smiles', 'inchi', 'formula', 'name', 'auto').

        Returns:
            A MolecularGraph.

        Raises:
            ValueError: If parsing fails.
        """
        from chemengine.parsing.protocol import parse_any

        if fmt and fmt not in ("auto", "name"):
            algo = self._registry.get(f"parsing.{fmt}", "default")
            return cast("MolecularGraph", algo.algorithm(text))

        # Auto-detect (or name resolution) through the shared parse_any
        # pipeline: deterministic format detection with strict, structured
        # errors for malformed input.
        return parse_any(text)

    def convert(self, graph: MolecularGraph, target: str, **options: Any) -> str:
        """Convert a molecular graph to a different representation.

        Supported targets (all backed by real serializers):
            - 'smiles'   — SMILES string (parsing.smiles.serialize_smiles)
            - 'inchi'    — InChI string (parsing.inchi_serializer.serialize_inchi)
            - 'inchikey' — InChIKey (parsing.inchi_serializer.generate_inchi_key)
            - 'formula'  — Hill-system molecular formula

        Name serialization (IUPAC) is exposed via the name_molecule tool /
        nomenclature subsystem, not via convert().

        Args:
            graph: The molecular graph to convert.
            target: One of the supported targets above.
            **options: Additional format-specific options (passed to the
                SMILES serializer).

        Returns:
            The string representation in the target format.

        Raises:
            ValueError: If target format is unknown. The message lists all
                currently supported targets.
        """
        if target == "formula":
            return graph.molecular_formula
        if target == "smiles":
            from chemengine.parsing.smiles import serialize_smiles
            return serialize_smiles(graph, **options)
        if target == "inchi":
            from chemengine.parsing.inchi_serializer import serialize_inchi
            return serialize_inchi(graph)
        if target == "inchikey":
            from chemengine.parsing.inchi_serializer import generate_inchi_key
            return generate_inchi_key(graph)
        raise ValueError(
            f"Unknown target format: '{target}'. Supported targets: "
            "smiles, inchi, inchikey, formula"
        )

    def compute(self, graph: MolecularGraph, property_name: str) -> Any:
        """Compute a molecular property.

        Supported properties:
            - 'mass'           — exact monoisotopic mass (float)
            - 'weight'         — average molecular weight (float)
            - 'formula'        — Hill-system molecular formula (str)
            - 'heavy_atoms'    — non-hydrogen atom count (int)
            - 'logp'           — Wildman-Crippen logP (float)
            - 'tpsa'           — topological polar surface area (float)
            - 'fraction_csp3'  — fraction of sp3 carbons (float)
            - 'hba'            — H-bond acceptor count (int)
            - 'hbd'            — H-bond donor count (int)
            - 'rotatable_bonds' — rotatable bond count (int)
            - 'num_rings'      — ring count (int)

        Molecular descriptors (logP, TPSA, HBA, HBD, rotatable bonds,
        fraction sp3) are delegated to the properties subsystem
        (chemengine.properties.descriptors) — no descriptor logic is
        duplicated here.

        Args:
            graph: The molecular graph.
            property_name: One of the supported property names above.

        Returns:
            The computed property value.

        Raises:
            ValueError: If the property name is unsupported. The message
                lists all supported properties.
        """
        # Graph-level properties (no descriptor algorithm involved).
        graph_properties: dict[str, Any] = {
            "mass": graph.exact_mass,
            "weight": graph.molecular_weight,
            "formula": graph.molecular_formula,
            "heavy_atoms": graph.num_heavy_atoms,
        }
        if property_name in graph_properties:
            return graph_properties[property_name]

        # Molecular descriptors: delegate to the properties subsystem.
        from chemengine.properties.descriptors import compute_property

        try:
            return compute_property(graph, property_name)
        except KeyError:
            supported = sorted(set(graph_properties) | {"logp", "tpsa", "fraction_csp3", "hba", "hbd", "rotatable_bonds", "num_rings"})
            raise ValueError(
                f"Unknown property: '{property_name}'. "
                f"Supported properties: {', '.join(supported)}"
            ) from None

    def validate(self, graph: MolecularGraph, rule_set: str = "standard") -> ValidationResult:
        """Validate a molecular graph using the specified rule set.

        Args:
            graph: The molecular graph to validate.
            rule_set: Rule set profile — 'strict', 'standard', or 'relaxed'.

        Returns:
            A ValidationResult with all findings.
        """
        from chemengine.validation.rules import get_validation_rules
        errors: list[Any] = []
        warnings: list[Any] = []
        infos: list[Any] = []
        for rule in get_validation_rules(rule_set):
            for finding in rule.validate(graph):
                if finding.severity == "error":
                    errors.append(finding)
                elif finding.severity == "warning":
                    warnings.append(finding)
                else:
                    infos.append(finding)
        return ValidationResult(
            passed=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
            info=tuple(infos),
        )

    def sanitize(self, graph: MolecularGraph) -> MolecularGraph:
        """Sanitize a molecular graph, producing a chemically valid graph.

        Args:
            graph: The molecular graph to sanitize.

        Returns:
            A new, sanitized MolecularGraph.
        """
        from chemengine.validation.sanitize import sanitize as _sanitize
        return _sanitize(graph)

    def detect_functional_groups(self, graph: MolecularGraph) -> list[dict[str, Any]]:
        """Detect functional groups in a molecule.

        Args:
            graph: The molecular graph.

        Returns:
            List of detected functional groups with atom indices, names,
            priorities, categories, and SMARTS patterns.

        Groups detected include: Alcohol, Phenol, Ether, Aldehyde, Ketone,
        Carboxylic Acid, Ester, Amine (1°/2°/3°), Amide, Nitrile, Nitro,
        Halogen, Sulfide, Thiol, Sulfoxide, Sulfone, Alkene, Alkyne,
        Aromatic Ring.
        """
        from chemengine.detection.functional_groups import (
            detect_functional_groups_dict as _detect_fg,
        )
        return _detect_fg(graph)

    def render(self, graph: MolecularGraph, fmt: str = "svg", **options: Any) -> str:
        """Render a molecular graph to a visual format.

        Args:
            graph: The molecular graph.
            fmt: Output format ('svg').
            **options: Rendering options (bond_length, atom_labels, etc.).

        Returns:
            The rendered string (SVG markup).

        Raises:
            ValueError: Unknown render format.
        """
        if fmt == "svg":
            from chemengine.rendering.svg import render_svg as _render_svg
            return _render_svg(
                graph,
                bond_length=options.get("bond_length", 40.0),
                show_hydrogens=options.get("show_hydrogens", False),
                padding=options.get("padding", 30.0),
                title=options.get("title"),
            )
        raise ValueError(f"Unsupported render format: {fmt}")

    # ── Plugin Management ──

    def load_plugin(self, name: str) -> None:
        """Load a plugin by name."""
        self._plugin_mgr.load(name, self)

    def load_all_plugins(self) -> list[Any]:
        """Load all discovered plugins."""
        return self._plugin_mgr.load_all(self)

    def list_plugins(self) -> list[dict[str, str]]:
        """List loaded plugins."""
        return [
            {"name": p.name, "version": p.version}
            for p in self._plugin_mgr.list_loaded()
        ]

    # ── Registry Access ──

    @property
    def registry(self) -> Any:
        """The AlgorithmRegistry instance."""
        return self._registry

    @property
    def bus(self) -> Any:
        """The EventBus instance."""
        return self._bus

    @property
    def datasets(self) -> Any:
        """The DatasetRegistry instance."""
        return self._datasets

    # ── Internal Helpers ──

    def _register_builtin_algorithms(self) -> None:
        """Register built-in algorithms with the AlgorithmRegistry."""
        # Register formula parser
        from chemengine.parsing.formula import register_formula_parser
        register_formula_parser(self._registry)

        # Register SMILES parser (if available)
        try:
            from chemengine.parsing.smiles import register_smiles_parser
            register_smiles_parser(self._registry)
        except ImportError:
            logger.warning("SMILES parser not available")

        # Register electron-configuration algorithm
        try:
            from chemengine.education.electron_config import (
                register_electron_config_algorithm,
            )
            register_electron_config_algorithm(self._registry)
        except ImportError:
            logger.warning("Electron configuration algorithm not available")

    def _register_builtin_tools(self) -> None:
        """Register all built-in tool definitions."""
        builtins = [
            ToolDefinition(
                name="parse_smiles",
                description="Parse a SMILES string into a molecular graph",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"},
                        "compute": {
                            "type": "array", "items": {"type": "string"},
                            "description": ("Properties to compute. Supported: mass, weight, "
                                "formula, heavy_atoms, logp, tpsa, fraction_csp3, hba, hbd, "
                                "rotatable_bonds, num_rings")
                        }
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "canonical_smiles": {"type": "string"},
                        "inchi": {"type": "string"},
                        "inchikey": {"type": "string"},
                        "formula": {"type": "string"},
                        "exact_mass": {"type": "number"},
                        "heavy_atoms": {"type": "integer"},
                        "properties": {"type": "object"}
                    }
                },
                category="parsing",
                tags=frozenset({"smiles", "parsing"}),
            ),
            ToolDefinition(
                name="parse_formula",
                description="Parse a molecular formula into a graph",
                input_schema={
                    "type": "object",
                    "properties": {
                        "formula": {"type": "string", "description": "Molecular formula (e.g., C5H12)"}
                    },
                    "required": ["formula"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "formula": {"type": "string"},
                        "exact_mass": {"type": "number"},
                        "error": {"type": "string"}
                    }
                },
                category="parsing",
                tags=frozenset({"formula", "parsing"}),
            ),
            ToolDefinition(
                name="compute_property",
                description="Compute a molecular property from a graph",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"},
                        "properties": {
                            "type": "array", "items": {"type": "string"},
                            "description": ("Properties to compute. Supported: mass, weight, "
                                "formula, heavy_atoms, logp, tpsa, fraction_csp3, hba, hbd, "
                                "rotatable_bonds, num_rings")
                        }
                    },
                    "required": ["smiles", "properties"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string"},
                        "properties": {"type": "object"}
                    }
                },
                category="properties",
                tags=frozenset({"properties", "computation"}),
            ),
            ToolDefinition(
                name="validate",
                description="Validate a molecular graph for chemical correctness",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"},
                        "rule_set": {
                            "type": "string",
                            "enum": ["strict", "standard", "relaxed"],
                            "description": "Validation strictness"
                        }
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "is_valid": {"type": "boolean"},
                        "num_errors": {"type": "integer"},
                        "num_warnings": {"type": "integer"},
                        "errors": {"type": "array"},
                        "warnings": {"type": "array"},
                        "info": {"type": "array"}
                    }
                },
                category="validation",
                tags=frozenset({"validation", "check"}),
            ),
            ToolDefinition(
                name="sanitize",
                description="Sanitize a molecular graph to fix common issues",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"}
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "original_smiles": {"type": "string"},
                        "sanitized_smiles": {"type": "string"},
                        "formula": {"type": "string"}
                    }
                },
                category="validation",
                tags=frozenset({"validation", "sanitize"}),
            ),
            ToolDefinition(
                name="detect_functional_groups",
                description="Detect functional groups in a molecule",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"}
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string"},
                        "functional_groups": {"type": "array"}
                    }
                },
                category="detection",
                tags=frozenset({"detection", "functional_groups"}),
            ),
            ToolDefinition(
                name="generate_2d_coordinates",
                description="Generate 2D coordinates for a molecular graph",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"},
                        "bond_length": {"type": "number", "description": "Bond length in SVG units"}
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string"},
                        "coordinates": {"type": "array"}
                    }
                },
                category="coordinates",
                tags=frozenset({"coordinates", "2d"}),
            ),
            ToolDefinition(
                name="generate_3d_conformer",
                description="Generate 3D conformer(s) for a molecular graph",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"},
                        "num_conformers": {"type": "integer", "description": "Number of conformers to generate"}
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string"},
                        "conformers": {"type": "array"}
                    }
                },
                category="coordinates",
                tags=frozenset({"coordinates", "3d", "conformer"}),
            ),
            ToolDefinition(
                name="render_svg",
                description="Render a molecular graph as SVG",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"},
                        "bond_length": {"type": "number", "description": "Bond length in SVG units"},
                        "show_hydrogens": {"type": "boolean", "description": "Show explicit hydrogens"}
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "svg": {"type": "string", "description": "SVG markup string"}
                    }
                },
                category="rendering",
                tags=frozenset({"rendering", "svg"}),
            ),
            ToolDefinition(
                name="name_molecule",
                description="Generate IUPAC name for a molecule",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"}
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string"},
                        "name": {"type": "string", "description": "IUPAC name"}
                    }
                },
                category="nomenclature",
                tags=frozenset({"nomenclature", "iupac"}),
            ),
            ToolDefinition(
                name="generate_inchi",
                description="Generate InChI and InChIKey for a molecule",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"}
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string"},
                        "inchi": {"type": "string", "description": "InChI string"},
                        "inchikey": {"type": "string", "description": "InChIKey (27 chars)"}
                    }
                },
                category="parsing",
                tags=frozenset({"parsing", "inchi"}),
            ),
            ToolDefinition(
                name="serialize",
                description="Serialize a molecular graph to JSON or other formats",
                input_schema={
                    "type": "object",
                    "properties": {
                        "smiles": {"type": "string", "description": "SMILES string"},
                        "format": {"type": "string", "enum": ["json", "dict"], "description": "Output format"}
                    },
                    "required": ["smiles"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "data": {"description": "Serialized data"}
                    }
                },
                category="io",
                tags=frozenset({"io", "serialization"}),
            ),
            ToolDefinition(
                name="calculate_electron_configuration",
                description=(
                    "Compute the electron configuration for an element or ion. "
                    "Uses the Madelung (Aufbau) rule with documented transition-metal "
                    "exceptions; a net charge models cations/anions."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": ["string", "integer"],
                            "description": "Element symbol (e.g. 'Fe') or atomic number (e.g. 26)",
                        },
                        "charge": {
                            "type": "integer",
                            "description": "Net charge. Positive removes electrons (cation), negative adds electrons (anion). Default 0.",
                            "default": 0,
                        },
                    },
                    "required": ["element"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "atomic_number": {"type": "integer"},
                        "symbol": {"type": "string"},
                        "name": {"type": "string"},
                        "charge": {"type": "integer"},
                        "electron_type": {"type": "string"},
                        "full": {"type": "string", "description": "Full electron configuration"},
                        "shorthand": {"type": "string", "description": "Noble-gas shorthand"},
                        "noble_gas": {"type": "string"},
                        "valence_electrons": {"type": "integer"},
                        "core_electrons": {"type": "integer"},
                        "unpaired_electrons": {"type": "integer"},
                        "shell_distribution": {"type": "object"},
                        "subshell_distribution": {"type": "object"},
                        "total_electrons": {"type": "integer"},
                    },
                },
                category="atomic",
                tags=frozenset({"atomic", "electrons", "education", "deterministic"}),
            ),
        ]
        for tool in builtins:
            self._tools[tool.name] = tool

    def _make_event(self, event_type: str, payload: Any, source: str,
                    correlation_id: str | None = None) -> Any:
        """Create an Event object."""
        from chemengine.core.events import Event
        return Event(type=event_type, payload=payload, source=source,
                     correlation_id=correlation_id)

    # ── Tool Implementations ──

    def _exec_parse_smiles(self, params: dict[str, Any],
                           correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the parse_smiles tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        # Compute canonical SMILES using the canonicalization engine
        try:
            from chemengine.parsing.canonical import canonical_smiles
            canonical = canonical_smiles(graph)
        except Exception:
            canonical = ""
        # Compute InChI
        try:
            from chemengine.parsing.inchi_serializer import generate_inchi_key, serialize_inchi
            inchi = serialize_inchi(graph)
            inchikey = generate_inchi_key(graph)
        except Exception:
            inchi = ""
            inchikey = ""
        result = {
            "canonical_smiles": canonical,
            "inchi": inchi,
            "inchikey": inchikey,
            "formula": graph.molecular_formula,
            "exact_mass": graph.exact_mass,
            "heavy_atoms": graph.num_heavy_atoms,
            "formula_weight": graph.molecular_weight,
        }
        if "compute" in params:
            properties: dict[str, Any] = {}
            for prop in params["compute"]:
                try:
                    properties[prop] = self.compute(graph, prop)
                except Exception as e:
                    properties[prop] = str(e)
            result["properties"] = properties
        return result

    def _exec_parse_formula(self, params: dict[str, Any],
                            correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the parse_formula tool."""
        graph = self.parse(params["formula"], fmt="formula")
        return {
            "formula": graph.molecular_formula,
            "exact_mass": graph.exact_mass,
        }

    def _exec_compute_property(self, params: dict[str, Any],
                                correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the compute_property tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        props = {}
        for prop in params["properties"]:
            props[prop] = self.compute(graph, prop)
        return {"smiles": params["smiles"], "properties": props}

    def _exec_validate(self, params: dict[str, Any],
                        correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the validate tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        rule_set = params.get("rule_set", "standard")
        result = self.validate(graph, rule_set=rule_set)
        return result.to_dict()

    def _exec_sanitize(self, params: dict[str, Any],
                        correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the sanitize tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        sanitized = self.sanitize(graph)
        from chemengine.parsing.smiles import serialize_smiles
        try:
            sanitized_smiles = serialize_smiles(sanitized)
        except Exception:
            sanitized_smiles = ""
        return {
            "original_smiles": params["smiles"],
            "sanitized_smiles": sanitized_smiles,
            "formula": sanitized.molecular_formula,
        }

    def _exec_detect_functional_groups(self, params: dict[str, Any],
                                         correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the detect_functional_groups tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        groups = self.detect_functional_groups(graph)
        return {
            "smiles": params["smiles"],
            "functional_groups": groups,
        }

    def _exec_generate_inchi(self, params: dict[str, Any],
                               correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the generate_inchi tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        from chemengine.parsing.inchi_serializer import generate_inchi_key, serialize_inchi
        inchi = serialize_inchi(graph)
        inchikey = generate_inchi_key(graph)
        return {
            "smiles": params["smiles"],
            "inchi": inchi,
            "inchikey": inchikey,
        }

    def _exec_calculate_electron_configuration(
        self, params: dict[str, Any], correlation_id: str | None = None
    ) -> dict[str, Any]:
        """Implementation of the calculate_electron_configuration tool."""
        from chemengine.education.electron_config import (
            _electron_config_to_dict,
            calculate_electron_configuration,
        )
        config = calculate_electron_configuration(
            params["element"], charge=params.get("charge", 0)
        )
        result = _electron_config_to_dict(config)
        result["element"] = params["element"]
        return result

    def _exec_generate_2d_coordinates(self, params: dict[str, Any],
                                       correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the generate_2d_coordinates tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        from chemengine.coordinates.layout_2d import generate_2d_coordinates
        coords = generate_2d_coordinates(graph)
        return {
            "smiles": params["smiles"],
            "coordinates": [{"x": c.x, "y": c.y} for c in coords],
        }

    def _exec_generate_3d_conformer(self, params: dict[str, Any],
                                     correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the generate_3d_conformer tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        from chemengine.coordinates.conformer_3d import generate_conformers
        num = params.get("num_conformers", 1)
        conformers = generate_conformers(graph, num_conformers=num)
        return {
            "smiles": params["smiles"],
            "conformers": [
                {
                    "id": conf.id,
                    "energy": conf.energy,
                    "coordinates": [{"x": c.x, "y": c.y, "z": c.z} for c in conf.coordinates],
                }
                for conf in conformers
            ],
        }

    def _exec_render_svg(self, params: dict[str, Any],
                          correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the render_svg tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        from chemengine.rendering.svg import render_svg
        svg = render_svg(
            graph,
            bond_length=params.get("bond_length", 40.0),
            show_hydrogens=params.get("show_hydrogens", False),
        )
        return {"svg": svg}

    def _exec_name_molecule(self, params: dict[str, Any],
                             correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the name_molecule tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        from chemengine.nomenclature.iupac import generate_iupac_name
        name = generate_iupac_name(graph)
        return {"smiles": params["smiles"], "name": name}

    def _exec_serialize(self, params: dict[str, Any],
                         correlation_id: str | None = None) -> dict[str, Any]:
        """Implementation of the serialize tool."""
        graph = self.parse(params["smiles"], fmt="smiles")
        fmt = params.get("format", "json")
        if fmt == "json":
            from chemengine.io.serialization import graph_to_json
            return {"data": graph_to_json(graph)}
        else:
            from chemengine.io.serialization import graph_to_dict
            return {"data": graph_to_dict(graph)}


# ── Helper Functions ──

# NOTE: Descriptor helpers (HBA/HBD counts, logP, TPSA, fraction sp3, etc.)
# live in the properties subsystem (chemengine.properties.descriptors).
# ChemEngineAPI.compute() delegates there — do not duplicate descriptor
# algorithms in this module.
