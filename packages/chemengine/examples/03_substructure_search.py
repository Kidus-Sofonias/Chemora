"""03 — Substructure search: heavy-atom query graphs.

Demonstrates subgraph matching with :mod:`chemengine.detection.substructure`.

Matching semantics: the matcher maps the **full** query graph onto the
**full** target graph. Parsed SMILES carry explicit hydrogens, so a query
built by ``parse_smiles`` would have to map its hydrogens too. Queries for
functional motifs are therefore built heavy-atom-only (see
:func:`heavy_query` below): hydrogens are implied by the pattern's valences.
"""

from chemengine.core.enums import BondOrder
from chemengine.core.graph import MolecularGraphBuilder, MolecularGraph
from chemengine.detection.substructure import (
    count_subgraph_matches,
    has_subgraph_match,
)
from chemengine.parsing.smiles import parse_smiles


def heavy_query(*atoms: tuple[int, ...], bonds: list[tuple[int, int, BondOrder]]) -> MolecularGraph:
    """Build a heavy-atom query graph.

    Args:
        atoms: One ``(atomic_number, is_aromatic)`` tuple per atom.
        bonds: ``(i, j, order)`` triples over the atom indices.
    """
    builder = MolecularGraphBuilder()
    for z, aromatic in atoms:
        builder.add_atom(atomic_number=z, is_aromatic=aromatic)
    for i, j, order in bonds:
        builder.add_bond(i, j, order)
    return builder.build()


benzene_ring = heavy_query(
    (6, True), (6, True), (6, True), (6, True), (6, True), (6, True),
    bonds=[(i, (i + 1) % 6, BondOrder.AROMATIC) for i in range(6)],
)

carboxylic_acid = heavy_query(
    (6, False), (8, False), (8, False),
    bonds=[(0, 1, BondOrder.DOUBLE), (0, 2, BondOrder.SINGLE)],
)

phenol = heavy_query(
    (6, True), (6, True), (6, True), (6, True), (6, True), (6, True), (8, False),
    bonds=[(i, (i + 1) % 6, BondOrder.AROMATIC) for i in range(6)] + [(5, 6, BondOrder.SINGLE)],
)

aspirin = parse_smiles("CC(=O)Oc1ccccc1C(=O)O")
paracetamol = parse_smiles("CC(=O)Nc1ccc(O)cc1")

print("benzene ring in aspirin:     ", count_subgraph_matches(aspirin, benzene_ring))
print("benzene ring in paracetamol: ", count_subgraph_matches(paracetamol, benzene_ring))
print("carboxylic acid in aspirin:  ", has_subgraph_match(aspirin, carboxylic_acid))
print("carboxylic acid in paracetamol:", has_subgraph_match(paracetamol, carboxylic_acid))
print("phenol motif in paracetamol: ", has_subgraph_match(paracetamol, phenol))

assert count_subgraph_matches(aspirin, benzene_ring) == 1
assert has_subgraph_match(aspirin, carboxylic_acid)
assert not has_subgraph_match(paracetamol, carboxylic_acid)
assert has_subgraph_match(paracetamol, phenol)
print("all substructure expectations hold")
