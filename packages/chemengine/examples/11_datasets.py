"""11 — Datasets: reference data without a database.

Shows the dataset registry bundled with the engine (elements, functional
groups, ring templates, valence rules) and the typed ``Element`` API built
on top of the same reference data.
"""

from chemengine import ChemEngineAPI
from chemengine.core.element import Element

chem = ChemEngineAPI()

print("available datasets:", sorted(chem.datasets.list_available()))

# Raw reference data (dict keyed by element symbol).
elements = chem.datasets.get("elements")
carbon = elements.data["C"]
print(
    "carbon:",
    {k: carbon[k] for k in ("z", "symbol", "atomic_mass", "electronegativity")},
)

# The typed element API over the same data.
iron = Element.from_symbol("Fe")
print(
    "iron:",
    f"Z={iron.atomic_number}, group={iron.group}, block={iron.block}, "
    f"metal={iron.is_metal}, mp={iron.melting_point} K",
)

# Query API: halogens in period 4, noble gases, lanthanides.
halogens = Element.filter(group=17).execute()
noble = [el.symbol for el in Element.filter(is_noble_gas=True).execute()]
lanthanides = Element.filter(is_lanthanide=True).execute()
print("halogens:", [el.symbol for el in halogens])
print("noble gases:", noble)
print("lanthanide count:", len(lanthanides))

assert carbon["z"] == 6
assert iron.symbol == "Fe"
assert [el.symbol for el in halogens] == ["F", "Cl", "Br", "I", "At", "Ts"]
assert noble == ["He", "Ne", "Ar", "Kr", "Xe", "Rn", "Og"]
assert len(lanthanides) == 15
print("dataset + element queries verified")
