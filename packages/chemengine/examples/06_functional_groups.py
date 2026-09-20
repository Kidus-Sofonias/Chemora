"""06 — Functional group detection.

Uses the facade's functional-group detector (SMARTS-backed) on molecules
with contrasting chemistry.
"""

from chemengine import ChemEngineAPI
from chemengine.parsing.smiles import parse_smiles

chem = ChemEngineAPI()

molecules = {
    "acetic acid":   "CC(=O)O",
    "ethyl acetate": "CC(=O)OCC",
    "acetamide":     "CC(=O)N",
    "acetonitrile":  "CC#N",
    "ethanolamine":  "NCCO",
}

for name, smiles in molecules.items():
    mol = parse_smiles(smiles)
    groups = chem.detect_functional_groups(mol)
    names = sorted({g["name"] for g in groups})
    print(f"{name:<14} -> {', '.join(names) if names else '(none)'}")

# Deterministic expectations.
assert {g["name"] for g in chem.detect_functional_groups(parse_smiles("CC(=O)O"))} >= {"Carboxylic Acid"}
assert {g["name"] for g in chem.detect_functional_groups(parse_smiles("CC#N"))} == {"Nitrile"}
print("functional group detection behaves as expected")
