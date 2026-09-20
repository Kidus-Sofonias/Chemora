"""05 — Rendering: 2D layout and SVG depiction.

Generates 2D coordinates with the ring-aware layout and renders molecules
to standalone SVG strings.
"""

from chemengine import ChemEngineAPI
from chemengine.coordinates.layout_2d import generate_2d_coordinates
from chemengine.parsing.smiles import parse_smiles

chem = ChemEngineAPI()

for name, smiles in {
    "benzene":  "c1ccccc1",
    "aspirin":  "CC(=O)Oc1ccccc1C(=O)O",
    "caffeine": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
}.items():
    mol = parse_smiles(smiles)

    # Coordinates first: the renderer uses graph coordinates when present.
    coords = generate_2d_coordinates(mol)
    assert len(coords) == mol.num_atoms

    svg = chem.render(mol, title=name)
    assert svg.startswith("<svg") and "</svg>" in svg
    print(f"{name:<9} {mol.num_atoms:>2} atoms, {mol.num_bonds:>2} bonds, "
          f"SVG {len(svg):>6} chars, coords {len(coords):>2}")

import tempfile
from pathlib import Path

out = Path(tempfile.mkdtemp(prefix="chemengine_")) / "aspirin.svg"
with out.open("w", encoding="utf-8") as fh:
    fh.write(chem.render(parse_smiles("CC(=O)Oc1ccccc1C(=O)O"), title="aspirin"))
print(f"wrote {out} ({out.stat().st_size} bytes)")
