"""01 — Quickstart: parse, identify, and inspect benzene.

The facade (ChemEngineAPI) is the single entry point for all capabilities.
"""

from chemengine import ChemEngineAPI

chem = ChemEngineAPI()

mol = chem.parse("c1ccccc1")  # benzene

print(f"formula:  {chem.convert(mol, 'formula')}")
print(f"weight:   {chem.compute(mol, 'weight'):.3f}")
print(f"rings:    {chem.compute(mol, 'num_rings')}")
print(f"InChIKey: {chem.convert(mol, 'inchikey')}")
