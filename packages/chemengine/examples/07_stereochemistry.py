"""07 — Stereochemistry: tags, perception, and E/Z assignment.

Demonstrates what the stereochemistry subsystem guarantees today:

1. SMILES ``@``/``@@`` tags are stored on atoms as ``ChiralTag.TH1``/``TH2``.
2. :func:`~chemengine.stereochemistry.perception.perceive_stereochemistry`
   finds tetrahedral centers and stereogenic double bonds.
3. Bond stereo is assigned for ``/``-annotated SMILES.

Known limitation (documented, not hidden): the CIP descriptor assignment
for tetrahedral centers currently reports ``R`` for both ``@`` and ``@@``
variants of 2-butanol; structures requiring the absolute-descriptor
distinction should inspect the stored ``ChiralTag`` (as below).
"""

from chemengine.core.enums import ChiralTag
from chemengine.parsing.smiles import parse_smiles
from chemengine.stereochemistry.perception import perceive_stereochemistry

# 1. Tags survive parsing.
for smi, expected in [("C[C@H](O)CC", ChiralTag.TH1), ("C[C@@H](O)CC", ChiralTag.TH2)]:
    mol = parse_smiles(smi)
    assert mol.atoms[1].stereochemistry == expected
    print(f"{smi:<12} stores {expected.value!r} on the stereocenter")

# 2. Perception finds the tetrahedral center.
cfg = perceive_stereochemistry(parse_smiles("C[C@H](O)CC"))
assert cfg.count == 1 and cfg.centers[0].category.value == "tetrahedral"
print("2-butanol: tetrahedral center perceived at atom", cfg.centers[0].atom_index)

# 3. E/Z perception on alkene SMILES.
cfg = perceive_stereochemistry(parse_smiles("C/C=C/C"))
assert cfg.count == 1 and cfg.centers[0].category.value == "double_bond"
print("2-butene: stereogenic double bond perceived, descriptor",
      cfg.centers[0].bond_stereo.value)

print("stereo perception verified")
