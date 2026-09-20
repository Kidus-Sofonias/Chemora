"""08 — InChI: serialization, parsing, and the identifier panel.

Round-trips molecules through the InChI serializer and compares the
standard identifiers the engine derives for the same structure.
"""

from chemengine import ChemEngineAPI
from chemengine.parsing.inchi import parse_inchi
from chemengine.parsing.inchi_serializer import serialize_inchi

chem = ChemEngineAPI()

smiles = {
    "ethanol": "CCO",
    "acetic acid": "CC(=O)O",
    "benzene": "c1ccccc1",
}

for name, smi in smiles.items():
    mol = chem.parse(smi)
    inchi = chem.convert(mol, "inchi")
    rebuilt = parse_inchi(inchi)

    print(f"{name:<11} {smi:<10} -> {inchi}")
    assert chem.convert(rebuilt, "formula") == chem.convert(mol, "formula"), (
        "InChI round-trip preserved the molecular formula"
    )

# Identifier panel: all derived from the same graph.
mol = chem.parse("CC(=O)O")
print()
print("formula: ", chem.convert(mol, "formula"))
print("smiles:  ", chem.convert(mol, "smiles"))
print("inchi:   ", chem.convert(mol, "inchi"))
print("inchikey:", chem.convert(mol, "inchikey"))
