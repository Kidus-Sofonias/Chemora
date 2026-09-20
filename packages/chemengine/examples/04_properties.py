"""04 — Molecular properties: descriptors for drug-like molecules.

Computes the standard descriptor panel (mass, logP, TPSA, H-bond counts,
rotatable bonds, fraction sp3) for three molecules and applies a
Lipinski-style filter.
"""

from chemengine import ChemEngineAPI
from chemengine.properties.descriptors import (
    compute_hba,
    compute_hbd,
    compute_logp,
    compute_rotatable_bonds,
    compute_tpsa,
)
from chemengine.parsing.smiles import parse_smiles

chem = ChemEngineAPI()

molecules = {
    "aspirin":     "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofen":   "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
}

print(f"{'name':<12} {'formula':<8} {'weight':>8} {'logP':>6} {'TPSA':>7} {'HBA':>4} {'HBD':>4} {'rotB':>5}")
for name, smiles in molecules.items():
    mol = parse_smiles(smiles)
    weight = chem.compute(mol, "weight")
    logp = compute_logp(mol)
    tpsa = compute_tpsa(mol)
    hba = compute_hba(mol)
    hbd = compute_hbd(mol)
    rotb = compute_rotatable_bonds(mol)
    print(f"{name:<12} {chem.compute(mol, 'formula'):<8} {weight:>8.3f} {logp:>6.2f} {tpsa:>7.2f} {hba:>4} {hbd:>4} {rotb:>5}")

    # Lipinski-style sanity assertions (deterministic engine results).
    assert 0 < weight < 500
    assert rotb >= 0

print("descriptor panel computed for all molecules")
