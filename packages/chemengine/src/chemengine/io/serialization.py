"""Serialization — JSON and dictionary serialization for molecular graphs.

Implements:
- MolecularGraph → dict/JSON serialization
- dict/JSON → MolecularGraph deserialization
- Reaction serialization
- Conformer serialization
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from chemengine.core.atoms import Isotope
from chemengine.core.enums import (
    BondOrder,
    BondStereo,
    BondTopology,
    BondType,
    ChiralTag,
    Hybridization,
)
from chemengine.core.geometry import Conformer, Coordinate2D, Coordinate3D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder

if TYPE_CHECKING:  # pragma: no cover - typing only
    from chemengine.reactions.engine import MechanismResult
    from chemengine.reactions.reaction import Reaction, ReactionComponent

# ── MolecularGraph Serialization ──

def graph_to_dict(graph: MolecularGraph) -> dict[str, Any]:
    """Serialize a MolecularGraph to a dictionary.

    Args:
        graph: The molecular graph.

    Returns:
        Dictionary representation.
    """
    atoms = []
    for atom in graph.atoms:
        atom_dict: dict[str, Any] = {
            "atomic_number": atom.atomic_number,
            "symbol": atom.symbol,
        }
        if atom.formal_charge != 0:
            atom_dict["formal_charge"] = atom.formal_charge
        if atom.radical_electrons > 0:
            atom_dict["radical_electrons"] = atom.radical_electrons
        if atom.isotope is not None:
            atom_dict["isotope"] = {
                "mass_number": atom.isotope.mass_number,
                "exact_mass": atom.isotope.exact_mass,
            }
        if atom.stereochemistry != ChiralTag.NONE:
            atom_dict["stereochemistry"] = atom.stereochemistry.value
        if atom.hybridization != Hybridization.UNKNOWN:
            atom_dict["hybridization"] = atom.hybridization.value
        if atom.implicit_hydrogens is not None:
            atom_dict["implicit_hydrogens"] = atom.implicit_hydrogens
        if atom.is_aromatic:
            atom_dict["is_aromatic"] = True
        atoms.append(atom_dict)

    bonds = []
    for bond in graph.bonds:
        bond_dict: dict[str, Any] = {
            "atom1": bond.atom1,
            "atom2": bond.atom2,
            "order": bond.order.value,
        }
        if bond.bond_type != BondType.COVALENT:
            bond_dict["bond_type"] = bond.bond_type.value
        if bond.stereochemistry != BondStereo.NONE:
            bond_dict["stereochemistry"] = bond.stereochemistry.value
        if bond.topology != BondTopology.UNSPECIFIED:
            bond_dict["topology"] = bond.topology.value
        if bond.is_aromatic:
            bond_dict["is_aromatic"] = True
        if bond.length is not None:
            bond_dict["length"] = bond.length
        bonds.append(bond_dict)

    result: dict[str, Any] = {
        "atoms": atoms,
        "bonds": bonds,
        "formula": graph.molecular_formula,
        "exact_mass": round(graph.exact_mass, 6),
    }

    if graph.name:
        result["name"] = graph.name

    if graph.coordinates_2d:
        result["coordinates_2d"] = [
            {"x": c.x, "y": c.y} for c in graph.coordinates_2d
        ]

    if graph.coordinates_3d:
        result["coordinates_3d"] = [
            {"x": c.x, "y": c.y, "z": c.z} for c in graph.coordinates_3d
        ]

    if graph.conformers:
        result["conformers"] = [
            {
                "id": conf.id,
                "coordinates": [{"x": c.x, "y": c.y, "z": c.z} for c in conf.coordinates],
                "energy": conf.energy,
            }
            for conf in graph.conformers
        ]

    return result


def graph_to_json(graph: MolecularGraph, indent: int | None = None) -> str:
    """Serialize a MolecularGraph to JSON.

    Args:
        graph: The molecular graph.
        indent: JSON indentation (None for compact).

    Returns:
        JSON string.
    """
    return json.dumps(graph_to_dict(graph), indent=indent)


# ── MolecularGraph Deserialization ──

def dict_to_graph(data: dict[str, Any]) -> MolecularGraph:
    """Deserialize a dictionary to a MolecularGraph.

    Args:
        data: Dictionary representation (from graph_to_dict).

    Returns:
        A MolecularGraph.
    """
    builder = MolecularGraphBuilder()

    # Add atoms
    for atom_data in data.get("atoms", []):
        builder.add_atom(
            atomic_number=atom_data["atomic_number"],
            formal_charge=atom_data.get("formal_charge", 0),
            radical_electrons=atom_data.get("radical_electrons", 0),
            isotope=Isotope(
                mass_number=atom_data["isotope"]["mass_number"],
                exact_mass=atom_data["isotope"]["exact_mass"],
            ) if "isotope" in atom_data else None,
            stereochemistry=ChiralTag(atom_data["stereochemistry"]) if "stereochemistry" in atom_data else ChiralTag.NONE,
            hybridization=Hybridization(atom_data["hybridization"]) if "hybridization" in atom_data else Hybridization.UNKNOWN,
            implicit_hydrogens=atom_data.get("implicit_hydrogens"),
            is_aromatic=atom_data.get("is_aromatic", False),
        )

    # Add bonds
    for bond_data in data.get("bonds", []):
        builder.add_bond(
            atom1=bond_data["atom1"],
            atom2=bond_data["atom2"],
            order=BondOrder(bond_data["order"]),
            bond_type=BondType(bond_data["bond_type"]) if "bond_type" in bond_data else BondType.COVALENT,
            stereochemistry=BondStereo(bond_data["stereochemistry"]) if "stereochemistry" in bond_data else BondStereo.NONE,
            topology=BondTopology(bond_data["topology"]) if "topology" in bond_data else BondTopology.UNSPECIFIED,
            is_aromatic=bond_data.get("is_aromatic", False),
            length=bond_data.get("length"),
        )

    # Set name
    if "name" in data:
        builder.set_name(data["name"])

    # Set coordinates
    if "coordinates_2d" in data:
        builder.set_coordinates_2d([
            Coordinate2D(c["x"], c["y"]) for c in data["coordinates_2d"]
        ])

    if "coordinates_3d" in data:
        builder.set_coordinates_3d([
            Coordinate3D(c["x"], c["y"], c["z"]) for c in data["coordinates_3d"]
        ])

    # Add conformers
    if "conformers" in data:
        for conf_data in data["conformers"]:
            conf = Conformer(
                id=conf_data["id"],
                coordinates=tuple(
                    Coordinate3D(c["x"], c["y"], c["z"])
                    for c in conf_data["coordinates"]
                ),
                energy=conf_data.get("energy", 0.0),
            )
            builder.add_conformer(conf)

    return builder.build()


def json_to_graph(json_str: str) -> MolecularGraph:
    """Deserialize a JSON string to a MolecularGraph.

    Args:
        json_str: JSON string (from graph_to_json).

    Returns:
        A MolecularGraph.
    """
    data = json.loads(json_str)
    return dict_to_graph(data)


# ── Format Conversion ──

def convert_format(
    graph: MolecularGraph,
    source_format: str,
    target_format: str,
    **options: Any,
) -> str:
    """Convert a molecular graph between formats.

    Args:
        graph: The molecular graph.
        source_format: Source format (unused, graph is the source of truth).
        target_format: Target format ('smiles', 'formula', 'json', 'name', 'inchi', 'inchikey').
        **options: Format-specific options.

    Returns:
        String representation in the target format.
    """
    if target_format == "json":
        return graph_to_json(graph, indent=options.get("indent"))
    elif target_format == "formula":
        return graph.molecular_formula
    elif target_format == "smiles":
        from chemengine.parsing.smiles import serialize_smiles
        return serialize_smiles(graph)
    elif target_format == "name":
        from chemengine.nomenclature.iupac import generate_iupac_name
        return generate_iupac_name(graph)
    elif target_format == "inchi":
        from chemengine.parsing.inchi_serializer import serialize_inchi
        return serialize_inchi(graph)
    elif target_format == "inchikey":
        from chemengine.parsing.inchi_serializer import generate_inchi_key
        return generate_inchi_key(graph)
    else:
        raise ValueError(f"Unknown target format: {target_format}")


# ---------------------------------------------------------------------------
# Reaction serialization (M34: required for mechanism-trace round trips)
# ---------------------------------------------------------------------------

def reaction_to_dict(reaction: Reaction) -> dict[str, Any]:
    """Serialize a :class:`chemengine.reactions.reaction.Reaction`.

    Args:
        reaction: The reaction (reactants/products/agents as component
            dicts wrapping ``graph_to_dict`` molecules).

    Returns:
        JSON-ready dictionary representation.
    """
    def _component(c: ReactionComponent) -> dict[str, Any]:
        out: dict[str, Any] = {"molecule": graph_to_dict(c.molecule)}
        if c.coefficient != 1:
            out["coefficient"] = c.coefficient
        if c.label:
            out["label"] = c.label
        if c.atom_map is not None:
            out["atom_map"] = {str(k): v for k, v in c.atom_map.items()}
        return out

    return {
        "reactants": [_component(c) for c in reaction.reactants],
        "products": [_component(c) for c in reaction.products],
        "agents": [_component(c) for c in reaction.agents],
        "conditions": [
            {"name": c.name, "value": c.value} for c in reaction.conditions
        ],
        "arrow": {"arrow_type": reaction.arrow.arrow_type},
        "name": reaction.name,
        "equation": reaction.equation,
    }


def dict_to_reaction(data: dict[str, Any]) -> Reaction:
    """Deserialize a dict produced by :func:`reaction_to_dict`.

    Args:
        data: Serialized reaction dictionary.

    Returns:
        A :class:`~chemengine.reactions.reaction.Reaction`.
    """
    from chemengine.reactions.reaction import (
        Reaction,
        ReactionArrow,
        ReactionComponent,
        ReactionCondition,
    )

    def _component(c: dict[str, Any]) -> ReactionComponent:
        atom_map = c.get("atom_map")
        return ReactionComponent(
            molecule=dict_to_graph(c["molecule"]),
            coefficient=c.get("coefficient", 1),
            label=c.get("label", ""),
            atom_map={int(k): v for k, v in atom_map.items()} if atom_map else None,
        )

    return Reaction(
        reactants=tuple(_component(c) for c in data.get("reactants", [])),
        products=tuple(_component(c) for c in data.get("products", [])),
        agents=tuple(_component(c) for c in data.get("agents", [])),
        conditions=tuple(
            ReactionCondition(name=c["name"], value=c["value"])
            for c in data.get("conditions", [])
        ),
        arrow=ReactionArrow(
            arrow_type=data.get("arrow", {}).get("arrow_type", "forward")
        ),
        name=data.get("name", ""),
        equation=data.get("equation", ""),
    )


# ---------------------------------------------------------------------------
# Mechanism-trace serialization (M34)
# ---------------------------------------------------------------------------

MECHANISM_TRACE_SCHEMA = "chemengine.mechanism_trace/1"
"""Versioned schema tag for serialized mechanism traces."""


def mechanism_trace_to_dict(result: MechanismResult) -> dict[str, Any]:
    """Serialize a :class:`chemengine.reactions.engine.MechanismResult`.

    Each step entry carries order, description, executed rule id, the
    full reaction, the electron movements, plus derived reacting atoms,
    bond changes and charge changes -- enough to determine reacting
    atoms/bonds, electron movement, bond/charge changes, rule identity
    and ordering from the document alone.

    Args:
        result: Executed mechanism result.

    Returns:
        JSON-ready dictionary with schema tag ``MECHANISM_TRACE_SCHEMA``.
    """
    from chemengine.reactions.engine import step_details

    steps: list[dict[str, Any]] = []
    for index, step in enumerate(result.trace.steps):
        entry: dict[str, Any] = {
            "order": step.order,
            "description": step.description,
            "rule": result.rule_names[index],
            "reaction": reaction_to_dict(step.reaction),
            "movements": [m.to_dict() for m in step.movements],
        }
        entry.update(step_details(step))
        steps.append(entry)
    return {
        "schema": MECHANISM_TRACE_SCHEMA,
        "mechanism": result.mechanism,
        "rule_names": list(result.rule_names),
        "steps": steps,
    }


def dict_to_mechanism_trace(data: dict[str, Any]) -> MechanismResult:
    """Deserialize a dict produced by :func:`mechanism_trace_to_dict`.

    Args:
        data: Serialized mechanism trace dictionary.

    Returns:
        A :class:`~chemengine.reactions.engine.MechanismResult`.

    Raises:
        ValueError: schema tag missing/mismatched, or step/rule
            structure inconsistent (never silently repaired).
    """
    from chemengine.reactions.engine import MechanismResult, MechanismValidationError
    from chemengine.reactions.mechanisms import (
        ArrowRef,
        ElectronMovement,
        MechanismStep,
        MechanismTrace,
        MovementKind,
    )

    if data.get("schema") != MECHANISM_TRACE_SCHEMA:
        raise MechanismValidationError(
            f"unsupported mechanism trace schema {data.get('schema')!r}; "
            f"expected {MECHANISM_TRACE_SCHEMA!r}"
        )
    rule_names = tuple(data.get("rule_names", ()))
    step_dicts = data.get("steps", [])
    if len(rule_names) != len(step_dicts):
        raise MechanismValidationError(
            "rule_names length does not match step count"
        )

    def _ref(ref: dict[str, Any]) -> ArrowRef:
        bond = ref.get("bond")
        return ArrowRef(
            atom=ref.get("atom"),
            bond=tuple(bond) if bond is not None else None,
        )

    steps: list[MechanismStep] = []
    for index, d in enumerate(step_dicts):
        if d.get("rule") != rule_names[index]:
            raise MechanismValidationError(
                f"step {d.get('order')} rule {d.get('rule')!r} does not "
                f"match rule_names[{index}] {rule_names[index]!r}"
            )
        movements = tuple(
            ElectronMovement(
                kind=MovementKind(m["kind"]),
                source=_ref(m["source"]),
                target=_ref(m["target"]),
                electron_count=m["electron_count"],
            )
            for m in d.get("movements", [])
        )
        steps.append(
            MechanismStep(
                reaction=dict_to_reaction(d["reaction"]),
                movements=movements,
                order=d["order"],
                description=d.get("description", ""),
            )
        )
    return MechanismResult(
        mechanism=data["mechanism"],
        trace=MechanismTrace.from_steps(steps),
        rule_names=rule_names,
    )


def mechanism_trace_to_json(
    result: MechanismResult, indent: int | None = 2
) -> str:
    """Serialize a mechanism result to a stable JSON string."""
    return json.dumps(mechanism_trace_to_dict(result), indent=indent)


def json_to_mechanism_trace(json_str: str) -> MechanismResult:
    """Deserialize a JSON string produced by :func:`mechanism_trace_to_json`."""
    return dict_to_mechanism_trace(json.loads(json_str))
