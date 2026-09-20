"""09 — Isomer generation: alkane isomer counts and enumeration.

The generation subsystem enumerates constitutional isomers for small
alkanes and verifies each is a distinct molecule.
"""

from chemengine.generation.constitutional import (
    alkane_isomer_count,
    generate_alkane_isomers,
)
from chemengine.parsing.canonical import canonical_smiles

# Known constitutional-isomer counts (OEIS A000602).
known = {1: 1, 2: 1, 3: 1, 4: 2, 5: 3, 6: 5, 7: 9, 8: 18}
for n, expected in known.items():
    got = alkane_isomer_count(n)
    print(f"C{n}H{2 * n + 2}: {got} isomer(s)")
    assert got == expected, f"alkane_isomer_count({n}) = {got}, expected {expected}"

# Enumerate pentane's isomers and check they are structurally distinct.
isomers = generate_alkane_isomers(5)
canon = {canonical_smiles(g) for g in isomers}
print(f"pentane isomers: {len(isomers)} generated, {len(canon)} distinct")
print(sorted(canon))
assert len(canon) == len(isomers) == 3
print("isomer enumeration verified")
