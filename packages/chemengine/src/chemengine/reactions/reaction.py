"""Reaction Models — Core data structures for chemical reactions.

Implements:
- Reaction class (reactants → products with agents/reagents)
- Reaction validation (atom/balance checking)
- Reaction templates for common transformations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chemengine.core.graph import MolecularGraph

# ── Reaction Components ──

@dataclass(frozen=True, slots=True)
class ReactionComponent:
    """A single component in a reaction (reactant, product, or agent).

    Attributes:
        molecule: The molecular graph.
        coefficient: Stoichiometric coefficient (1 = no explicit coefficient).
        label: Optional label (e.g., 'solvent', 'catalyst').
        atom_map: Optional atom mapping dict (reactant_atom → product_atom).
    """
    molecule: MolecularGraph
    coefficient: int = 1
    label: str = ""
    atom_map: dict[int, int] | None = None

    def __repr__(self) -> str:
        coeff = f"{self.coefficient} " if self.coefficient != 1 else ""
        label = f" ({self.label})" if self.label else ""
        return f"{coeff}{self.molecule.molecular_formula}{label}"


@dataclass(frozen=True, slots=True)
class ReactionCondition:
    """A reaction condition (temperature, pressure, solvent, catalyst, etc.).

    Attributes:
        name: Condition name (e.g., 'temperature', 'solvent').
        value: Condition value (e.g., '25°C', 'THF').
    """
    name: str
    value: str

    def __repr__(self) -> str:
        return f"{self.name}={self.value}"


@dataclass(frozen=True, slots=True)
class ReactionArrow:
    """Reaction arrow type."""
    arrow_type: str = "forward"  # forward, reversible, equilibrium

    def __repr__(self) -> str:
        if self.arrow_type == "reversible":
            return "⇌"
        if self.arrow_type == "equilibrium":
            return "⇌"
        return "→"


@dataclass(frozen=True, slots=True)
class Reaction:
    """A chemical reaction.

    Attributes:
        reactants: Reactant molecules with coefficients.
        products: Product molecules with coefficients.
        agents: Agents (solvents, catalysts, reagents) — not consumed.
        conditions: Reaction conditions.
        arrow: Reaction arrow type.
        name: Optional name (e.g., 'Diels-Alder reaction').
        equation: Optional SMILES reaction equation string.
    """
    reactants: tuple[ReactionComponent, ...]
    products: tuple[ReactionComponent, ...]
    agents: tuple[ReactionComponent, ...] = ()
    conditions: tuple[ReactionCondition, ...] = ()
    arrow: ReactionArrow = field(default_factory=ReactionArrow)
    name: str = ""
    equation: str = ""

    @property
    def num_reactants(self) -> int:
        """Number of reactant species."""
        return len(self.reactants)

    @property
    def num_products(self) -> int:
        """Number of product species."""
        return len(self.products)

    @property
    def num_agents(self) -> int:
        """Number of agents."""
        return len(self.agents)

    def is_balanced(self) -> bool:
        """Check if the reaction is atom-balanced.

        Returns:
            True if atom counts match between reactants and products.
        """
        reactant_atoms = self._count_atoms(self.reactants)
        product_atoms = self._count_atoms(self.products)
        return reactant_atoms == product_atoms

    def atom_count_difference(self) -> dict[str, int]:
        """Compute the atom count difference between reactants and products.

        Returns:
            Dict mapping element symbol to difference (positive = more in products).
        """
        reactant_atoms = self._count_atoms(self.reactants)
        product_atoms = self._count_atoms(self.products)

        all_elements = set(reactant_atoms.keys()) | set(product_atoms.keys())
        diff = {}
        for elem in all_elements:
            r_count = reactant_atoms.get(elem, 0)
            p_count = product_atoms.get(elem, 0)
            d = p_count - r_count
            if d != 0:
                diff[elem] = d
        return diff

    def _count_atoms(self, components: tuple[ReactionComponent, ...]) -> dict[str, int]:
        """Count total atoms across all components, weighted by coefficients."""
        counts: dict[str, int] = {}
        for comp in components:
            formula = comp.molecule.formula_dict
            for elem, count in formula.items():
                counts[elem] = counts.get(elem, 0) + count * comp.coefficient
        return counts

    def total_formula_reactants(self) -> dict[str, int]:
        """Total atom count across all reactants."""
        return self._count_atoms(self.reactants)

    def total_formula_products(self) -> dict[str, int]:
        """Total atom count across all products."""
        return self._count_atoms(self.products)

    def to_dict(self) -> dict[str, Any]:
        """Serialize reaction to a dictionary."""
        return {
            "name": self.name,
            "equation": self.equation,
            "reactants": [
                {
                    "formula": comp.molecule.molecular_formula,
                    "coefficient": comp.coefficient,
                    "label": comp.label,
                }
                for comp in self.reactants
            ],
            "products": [
                {
                    "formula": comp.molecule.molecular_formula,
                    "coefficient": comp.coefficient,
                    "label": comp.label,
                }
                for comp in self.products
            ],
            "agents": [
                {
                    "formula": comp.molecule.molecular_formula,
                    "coefficient": comp.coefficient,
                    "label": comp.label,
                }
                for comp in self.agents
            ],
            "conditions": [
                {"name": c.name, "value": c.value}
                for c in self.conditions
            ],
            "is_balanced": self.is_balanced(),
            "arrow": self.arrow.arrow_type,
        }

    def __repr__(self) -> str:
        parts = []
        reactant_strs = [repr(r) for r in self.reactants]
        product_strs = [repr(p) for p in self.products]
        agent_strs = [repr(a) for a in self.agents]

        parts.append(" + ".join(reactant_strs))
        parts.append(f" {self.arrow} ")
        parts.append(" + ".join(product_strs))

        if agent_strs:
            parts.append(f" [{', '.join(agent_strs)}]")

        name_str = f" ({self.name})" if self.name else ""
        return f"Reaction({''.join(parts)}){name_str}"


# ── Reaction Builder ──

class ReactionBuilder:
    """Builder for constructing Reaction objects.

    Usage:
        >>> builder = ReactionBuilder()
        >>> builder.add_reactant(ethanol, coefficient=2)
        >>> builder.add_product(acetic_acid, coefficient=1)
        >>> builder.add_condition(ReactionCondition("temperature", "78°C"))
        >>> reaction = builder.build()
    """

    def __init__(self) -> None:
        self._reactants: list[ReactionComponent] = []
        self._products: list[ReactionComponent] = []
        self._agents: list[ReactionComponent] = []
        self._conditions: list[ReactionCondition] = []
        self._arrow = ReactionArrow()
        self._name = ""
        self._equation = ""

    def add_reactant(
        self,
        molecule: MolecularGraph,
        coefficient: int = 1,
        label: str = "",
    ) -> ReactionBuilder:
        """Add a reactant to the reaction."""
        self._reactants.append(ReactionComponent(molecule, coefficient, label))
        return self

    def add_product(
        self,
        molecule: MolecularGraph,
        coefficient: int = 1,
        label: str = "",
    ) -> ReactionBuilder:
        """Add a product to the reaction."""
        self._products.append(ReactionComponent(molecule, coefficient, label))
        return self

    def add_agent(
        self,
        molecule: MolecularGraph,
        coefficient: int = 1,
        label: str = "",
    ) -> ReactionBuilder:
        """Add an agent (solvent, catalyst, reagent)."""
        self._agents.append(ReactionComponent(molecule, coefficient, label))
        return self

    def add_condition(self, condition: ReactionCondition) -> ReactionBuilder:
        """Add a reaction condition."""
        self._conditions.append(condition)
        return self

    def set_arrow(self, arrow: ReactionArrow) -> ReactionBuilder:
        """Set the reaction arrow type."""
        self._arrow = arrow
        return self

    def set_name(self, name: str) -> ReactionBuilder:
        """Set the reaction name."""
        self._name = name
        return self

    def set_equation(self, equation: str) -> ReactionBuilder:
        """Set the SMILES reaction equation."""
        self._equation = equation
        return self

    def build(self) -> Reaction:
        """Build and return the Reaction."""
        if not self._reactants:
            raise ValueError("Reaction must have at least one reactant")
        if not self._products:
            raise ValueError("Reaction must have at least one product")
        return Reaction(
            reactants=tuple(self._reactants),
            products=tuple(self._products),
            agents=tuple(self._agents),
            conditions=tuple(self._conditions),
            arrow=self._arrow,
            name=self._name,
            equation=self._equation,
        )


# ── Reaction Templates ──

@dataclass(frozen=True, slots=True)
class ReactionTemplate:
    """A template for a common reaction type.

    Attributes:
        name: Template name (e.g., 'combustion', 'neutralization').
        description: Description of the reaction type.
        reactant_patterns: SMILES patterns for reactants.
        product_patterns: SMILES patterns for products.
        conditions: Typical conditions.
    """
    name: str
    description: str
    reactant_patterns: tuple[str, ...]
    product_patterns: tuple[str, ...]
    conditions: tuple[ReactionCondition, ...] = ()

    def matches_reactants(self, smiles_list: list[str]) -> bool:
        """Check if a list of SMILES strings matches the reactant patterns."""
        if len(smiles_list) != len(self.reactant_patterns):
            return False
        return sorted(smiles_list) == sorted(self.reactant_patterns)


# Common reaction templates
REACTION_TEMPLATES: dict[str, ReactionTemplate] = {
    "combustion": ReactionTemplate(
        name="Combustion",
        description="Complete combustion of a hydrocarbon",
        reactant_patterns=("C", "O=O"),
        product_patterns=("O=C=O", "O"),
        conditions=(ReactionCondition("temperature", "ignition"),),
    ),
    "acid_base": ReactionTemplate(
        name="Acid-Base Neutralization",
        description="Neutralization of an acid with a base",
        reactant_patterns=("[H]O", "[O-]"),
        product_patterns=("O",),
        conditions=(),
    ),
    "esterification": ReactionTemplate(
        name="Esterification",
        description="Fischer esterification of a carboxylic acid with an alcohol",
        reactant_patterns=("C(=O)O", "CO"),
        product_patterns=("C(=O)OC", "O"),
        conditions=(ReactionCondition("catalyst", "H+"),),
    ),
    "dehydration": ReactionTemplate(
        name="Dehydration",
        description="Elimination of water from an alcohol",
        reactant_patterns=("CO",),
        product_patterns=("C=C", "O"),
        conditions=(ReactionCondition("catalyst", "H2SO4"),),
    ),
    "hydrogenation": ReactionTemplate(
        name="Hydrogenation",
        description="Addition of hydrogen across a double/triple bond",
        reactant_patterns=("C=C", "[H][H]"),
        product_patterns=("CC",),
        conditions=(ReactionCondition("catalyst", "Pd/C"),),
    ),
}


def get_reaction_template(name: str) -> ReactionTemplate | None:
    """Get a reaction template by name."""
    return REACTION_TEMPLATES.get(name)


def list_reaction_templates() -> list[ReactionTemplate]:
    """List all available reaction templates."""
    return list(REACTION_TEMPLATES.values())
