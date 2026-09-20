"""02 — SMILES round-trips: parse, canonicalize, and rebuild.

Demonstrates the SMILES subsystem directly: canonical serialization and
the parse → serialize → parse identity property.
"""

from chemengine.parsing.canonical import canonical_smiles
from chemengine.parsing.smiles import parse_smiles, serialize_smiles

# Three ways of writing the same molecule.
inputs = ["CCO", "OCC", "C(O)C"]

graphs = [parse_smiles(s) for s in inputs]
serialized = [serialize_smiles(g) for g in graphs]
canon = [canonical_smiles(g) for g in graphs]

print("raw input      ->", inputs)
print("serialized     ->", serialized)
print("canonical      ->", canon)

# Deterministic identity: re-parsing a serialized SMILES gives the same
# canonical form again.
for g in graphs:
    again = parse_smiles(serialize_smiles(g))
    assert canonical_smiles(again) == canonical_smiles(g)

print("round-trip identity holds for all inputs")
