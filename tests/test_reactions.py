"""Tests for Phase 10: Reactions Infrastructure
- Reaction model
- Reaction builder
- Atom balance checking
- Reaction templates
"""

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.reactions.reaction import (
    Reaction,
    ReactionArrow,
    ReactionBuilder,
    ReactionComponent,
    ReactionCondition,
    get_reaction_template,
    list_reaction_templates,
)

# ── Fixtures ──

def _make_water():
    builder = MolecularGraphBuilder()
    o = builder.add_atom(8)
    for _ in range(2):
        h = builder.add_atom(1)
        builder.add_bond(o, h, BondOrder.SINGLE)
    return builder.build()


def _make_methane():
    builder = MolecularGraphBuilder()
    c = builder.add_atom(6)
    for _ in range(4):
        h = builder.add_atom(1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


def _make_co2():
    builder = MolecularGraphBuilder()
    c = builder.add_atom(6)
    o1 = builder.add_atom(8)
    o2 = builder.add_atom(8)
    builder.add_bond(c, o1, BondOrder.DOUBLE)
    builder.add_bond(c, o2, BondOrder.DOUBLE)
    return builder.build()


def _make_oxygen():
    builder = MolecularGraphBuilder()
    o1 = builder.add_atom(8)
    o2 = builder.add_atom(8)
    builder.add_bond(o1, o2, BondOrder.DOUBLE)
    return builder.build()


def _make_ethanol():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    o = builder.add_atom(8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o, BondOrder.SINGLE)
    for c, n in [(c1, 3), (c2, 2)]:
        for _ in range(n):
            h = builder.add_atom(1)
            builder.add_bond(c, h, BondOrder.SINGLE)
    h = builder.add_atom(1)
    builder.add_bond(o, h, BondOrder.SINGLE)
    return builder.build()


def _make_acetic_acid():
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(6)
    c2 = builder.add_atom(6)
    o1 = builder.add_atom(8)
    o2 = builder.add_atom(8)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    builder.add_bond(c2, o1, BondOrder.DOUBLE)
    builder.add_bond(c2, o2, BondOrder.SINGLE)
    for _ in range(3):
        h = builder.add_atom(1)
        builder.add_bond(c1, h, BondOrder.SINGLE)
    h = builder.add_atom(1)
    builder.add_bond(o2, h, BondOrder.SINGLE)
    return builder.build()


# ── ReactionComponent Tests ──

class TestReactionComponent:
    def test_create_component(self):
        water = _make_water()
        comp = ReactionComponent(molecule=water)
        assert comp.coefficient == 1
        assert comp.molecule.molecular_formula == "H2O"

    def test_component_with_coefficient(self):
        water = _make_water()
        comp = ReactionComponent(molecule=water, coefficient=2)
        assert comp.coefficient == 2

    def test_component_with_label(self):
        water = _make_water()
        comp = ReactionComponent(molecule=water, label="solvent")
        assert comp.label == "solvent"

    def test_component_repr(self):
        water = _make_water()
        comp = ReactionComponent(molecule=water, coefficient=2)
        assert "2" in repr(comp)


# ── ReactionCondition Tests ──

class TestReactionCondition:
    def test_condition(self):
        cond = ReactionCondition(name="temperature", value="25°C")
        assert cond.name == "temperature"
        assert cond.value == "25°C"

    def test_condition_repr(self):
        cond = ReactionCondition(name="solvent", value="THF")
        assert "solvent" in repr(cond)


# ── Reaction Tests ──

class TestReaction:
    def test_simple_reaction(self):
        methane = _make_methane()
        oxygen = _make_oxygen()
        co2 = _make_co2()
        water = _make_water()

        reaction = Reaction(
            reactants=(
                ReactionComponent(methane, coefficient=1),
                ReactionComponent(oxygen, coefficient=2),
            ),
            products=(
                ReactionComponent(co2, coefficient=1),
                ReactionComponent(water, coefficient=2),
            ),
        )
        assert reaction.num_reactants == 2
        assert reaction.num_products == 2

    def test_balanced_reaction(self):
        methane = _make_methane()
        oxygen = _make_oxygen()
        co2 = _make_co2()
        water = _make_water()

        reaction = Reaction(
            reactants=(
                ReactionComponent(methane, coefficient=1),
                ReactionComponent(oxygen, coefficient=2),
            ),
            products=(
                ReactionComponent(co2, coefficient=1),
                ReactionComponent(water, coefficient=2),
            ),
        )
        assert reaction.is_balanced()

    def test_unbalanced_reaction(self):
        methane = _make_methane()
        oxygen = _make_oxygen()
        co2 = _make_co2()

        reaction = Reaction(
            reactants=(
                ReactionComponent(methane, coefficient=1),
                ReactionComponent(oxygen, coefficient=1),
            ),
            products=(
                ReactionComponent(co2, coefficient=1),
            ),
        )
        assert not reaction.is_balanced()

    def test_atom_count_difference(self):
        methane = _make_methane()
        oxygen = _make_oxygen()
        co2 = _make_co2()
        water = _make_water()

        reaction = Reaction(
            reactants=(
                ReactionComponent(methane, coefficient=1),
                ReactionComponent(oxygen, coefficient=2),
            ),
            products=(
                ReactionComponent(co2, coefficient=1),
                ReactionComponent(water, coefficient=2),
            ),
        )
        diff = reaction.atom_count_difference()
        assert diff == {}  # Balanced = no difference

    def test_to_dict(self):
        water = _make_water()
        reaction = Reaction(
            reactants=(ReactionComponent(water, coefficient=1),),
            products=(ReactionComponent(water, coefficient=1),),
            name="Water self-ionization",
        )
        d = reaction.to_dict()
        assert d["name"] == "Water self-ionization"
        assert len(d["reactants"]) == 1
        assert len(d["products"]) == 1
        assert d["is_balanced"]

    def test_reaction_repr(self):
        water = _make_water()
        reaction = Reaction(
            reactants=(ReactionComponent(water, coefficient=2),),
            products=(ReactionComponent(water, coefficient=2),),
            name="Test",
        )
        r = repr(reaction)
        assert "Reaction" in r
        assert "Test" in r

    def test_reaction_with_conditions(self):
        water = _make_water()
        reaction = Reaction(
            reactants=(ReactionComponent(water, coefficient=1),),
            products=(ReactionComponent(water, coefficient=1),),
            conditions=(ReactionCondition("temperature", "100°C"),),
        )
        assert len(reaction.conditions) == 1

    def test_reaction_with_agents(self):
        water = _make_water()
        reaction = Reaction(
            reactants=(ReactionComponent(water, coefficient=1),),
            products=(ReactionComponent(water, coefficient=1),),
            agents=(ReactionComponent(water, label="catalyst"),),
        )
        assert reaction.num_agents == 1

    def test_reaction_arrow(self):
        arrow = ReactionArrow(arrow_type="reversible")
        assert "⇌" in repr(arrow)


# ── ReactionBuilder Tests ──

class TestReactionBuilder:
    def test_build_simple(self):
        water = _make_water()
        reaction = (
            ReactionBuilder()
            .add_reactant(water)
            .add_product(water)
            .build()
        )
        assert reaction.num_reactants == 1
        assert reaction.num_products == 1

    def test_build_with_all_components(self):
        methane = _make_methane()
        oxygen = _make_oxygen()
        co2 = _make_co2()
        water = _make_water()

        reaction = (
            ReactionBuilder()
            .add_reactant(methane, coefficient=1)
            .add_reactant(oxygen, coefficient=2)
            .add_product(co2, coefficient=1)
            .add_product(water, coefficient=2)
            .add_agent(water, label="catalyst")
            .add_condition(ReactionCondition("temperature", "ignition"))
            .set_name("Combustion of methane")
            .set_equation("CH4 + 2O2 -> CO2 + 2H2O")
            .build()
        )
        assert reaction.name == "Combustion of methane"
        assert reaction.is_balanced()

    def test_build_no_reactants_raises(self):
        water = _make_water()
        with pytest.raises(ValueError, match="reactant"):
            ReactionBuilder().add_product(water).build()

    def test_build_no_products_raises(self):
        water = _make_water()
        with pytest.raises(ValueError, match="product"):
            ReactionBuilder().add_reactant(water).build()

    def test_set_arrow(self):
        water = _make_water()
        reaction = (
            ReactionBuilder()
            .add_reactant(water)
            .add_product(water)
            .set_arrow(ReactionArrow("reversible"))
            .build()
        )
        assert reaction.arrow.arrow_type == "reversible"


# ── ReactionTemplate Tests ──

class TestReactionTemplate:
    def test_list_templates(self):
        templates = list_reaction_templates()
        assert len(templates) >= 4
        assert any(t.name == "Combustion" for t in templates)

    def test_get_template(self):
        template = get_reaction_template("combustion")
        assert template is not None
        assert template.name == "Combustion"

    def test_get_unknown_template(self):
        template = get_reaction_template("nonexistent")
        assert template is None

    def test_template_matches_reactants(self):
        template = get_reaction_template("combustion")
        assert template.matches_reactants(["C", "O=O"])

    def test_template_no_match(self):
        template = get_reaction_template("combustion")
        assert not template.matches_reactants(["CCO"])

    def test_template_conditions(self):
        template = get_reaction_template("combustion")
        assert len(template.conditions) > 0

    def test_all_templates_have_required_fields(self):
        for template in list_reaction_templates():
            assert template.name
            assert template.description
            assert len(template.reactant_patterns) > 0
            assert len(template.product_patterns) > 0
