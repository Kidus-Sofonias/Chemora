"""10 — Reactions: building, balancing, and templates.

Constructs the esterification of ethanol and acetic acid with the
ReactionBuilder, checks atom balance, and inspects the built-in template
library.
"""

from chemengine import ChemEngineAPI
from chemengine.reactions.reaction import ReactionBuilder, ReactionCondition, list_reaction_templates

chem = ChemEngineAPI()

ethanol = chem.parse("CCO")
acetic_acid = chem.parse("CC(O)=O")
ethyl_acetate = chem.parse("CC(=O)OCC")
water = chem.parse("O")

reaction = (
    ReactionBuilder()
    .add_reactant(acetic_acid, coefficient=1, label="acetic acid")
    .add_reactant(ethanol, coefficient=1, label="ethanol")
    .add_product(ethyl_acetate, coefficient=1, label="ethyl acetate")
    .add_product(water, coefficient=1, label="water")
    .add_condition(ReactionCondition("catalyst", "H2SO4, reflux"))
    .set_name("Fischer esterification")
    .build()
)

print("name:        ", reaction.name)
print("reactants:   ", reaction.num_reactants)
print("products:    ", reaction.num_products)
print("conditions:  ", [f"{c.name}: {c.value}" for c in reaction.conditions])
print("atom-balanced:", reaction.is_balanced())
assert reaction.is_balanced()

templates = list_reaction_templates()
print("built-in templates:", sorted(t.name for t in templates))
assert any("Esterification" in t.name for t in templates)
print("reaction layer verified")
