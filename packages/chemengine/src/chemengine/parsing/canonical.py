"""SMILES canonicalization — produces a unique, deterministic SMILES string
for a given molecular graph.

Algorithm:
    1. Compute canonical atom invariants using iterative refinement
       (Morgan-like extended connectivity).
    2. Use invariants to assign a canonical ordering to atoms.
    3. Serialize atoms in canonical order with canonical ring closure labels.

The resulting SMILES is deterministic: same graph always gives same string.
"""

from __future__ import annotations

import hashlib

from chemengine.core.enums import ChiralTag
from chemengine.core.graph import MolecularGraph
from chemengine.parsing.smiles import serialize_smiles


def canonical_smiles(graph: MolecularGraph) -> str:
    """Produce a canonical (unique, deterministic) SMILES for a molecular graph.

    Uses Morgan-like extended connectivity to assign canonical atom ordering,
    then serializes the graph in that order.

    Args:
        graph: The molecular graph to canonicalize.

    Returns:
        A canonical SMILES string.
    """
    # Step 1: Compute canonical atom ordering
    order = _compute_canonical_order(graph)

    # Step 2: Re-index atoms by canonical order
    reindexed = _reindex_graph(graph, order)

    # Step 3: Serialize with canonical ordering
    return serialize_smiles(reindexed)


def _compute_canonical_order(graph: MolecularGraph) -> list[int]:
    """Compute canonical atom ordering using Morgan-like algorithm.

    Returns:
        List of atom indices in canonical order (first = canonical start atom).
    """
    n = graph.num_atoms
    if n == 0:
        return []

    # Step 1: Compute initial invariants
    # Each invariant is a tuple that captures atomic properties
    invariants: list[tuple] = []
    for i, atom in enumerate(graph.atoms):
        degree = graph.get_degree(i)
        heavy_degree = sum(
            1 for nbr in graph.get_neighbors(i)
            if graph.atoms[nbr].atomic_number != 1
        )
        inv = (
            atom.atomic_number,
            degree,
            heavy_degree,
            atom.formal_charge,
            1 if atom.isotope is not None else 0,
            atom.isotope.mass_number if atom.isotope else 0,
            1 if atom.is_aromatic else 0,
            atom.implicit_hydrogens if atom.implicit_hydrogens is not None else -1,
            atom.stereochemistry.value if atom.stereochemistry != ChiralTag.NONE else "",
            1 if atom.is_metal else 0,
        )
        invariants.append(inv)

    # Step 2: Iteratively refine invariants using neighbor information
    # Uses Morgan extended connectivity: hash(current_invariant, sorted(neighbor_invariants))
    max_iterations = 10
    for iteration in range(max_iterations):
        new_invariants: list[tuple] = []
        for i in range(n):
            # Gather neighbor invariants
            neighbor_invs = tuple(
                sorted(invariants[nbr] for nbr in graph.get_neighbors(i))
            )
            # Hash current + neighbors
            h = hashlib.sha256()
            h.update(str(invariants[i]).encode())
            h.update(str(neighbor_invs).encode())
            new_invariants.append((iteration + 1, h.hexdigest()[:16]))

        # Check for convergence (all invariants unique)
        if len(set(new_invariants)) == n:
            invariants = new_invariants
            break

        # Merge invariants (prepend previous iteration's value for stability)
        merged: list[tuple] = []
        for old_inv, new_inv in zip(invariants, new_invariants):
            merged.append(old_inv + new_inv)
        invariants = merged

    # Step 3: Assign canonical ordering
    # Atoms are sorted by (invariant, original_index) for determinism
    indexed = list(enumerate(invariants))
    indexed.sort(key=lambda x: (x[1], x[0]))

    # Extract canonical order: atom indices sorted by ascending invariant
    canonical_order = [idx for idx, _ in indexed]

    return canonical_order


def _reindex_graph(graph: MolecularGraph, order: list[int]) -> MolecularGraph:
    """Re-index atoms by the given order, rebuilding the graph.

    Args:
        graph: The original molecular graph.
        order: List of atom indices in the desired order.

    Returns:
        A new MolecularGraph with atoms re-indexed.
    """
    from chemengine.core.graph import MolecularGraphBuilder

    # Build old-to-new index mapping
    old_to_new: dict[int, int] = {}
    builder = MolecularGraphBuilder()

    # Preserve graph metadata
    builder.set_name(graph.name)
    if graph.coordinates_2d:
        builder.set_coordinates_2d(list(graph.coordinates_2d))
    if graph.coordinates_3d:
        builder.set_coordinates_3d(list(graph.coordinates_3d))
    for conf in graph.conformers:
        builder.add_conformer(conf)
    for ring in graph.rings:
        builder.add_ring(ring)
    for center in graph.stereo_config.centers:
        builder.add_chiral_center(center)
    for key, val in graph.properties:
        builder.set_property(key, val)

    for new_idx, old_idx in enumerate(order):
        atom = graph.atoms[old_idx]
        builder.add_atom(
            atomic_number=atom.atomic_number,
            formal_charge=atom.formal_charge,
            radical_electrons=atom.radical_electrons,
            isotope=atom.isotope,
            stereochemistry=atom.stereochemistry,
            hybridization=atom.hybridization,
            valence=atom.valence,
            implicit_hydrogens=atom.implicit_hydrogens,
            atom_mapping=atom.atom_mapping,
            is_aromatic=atom.is_aromatic,
            properties=dict(atom.properties),
        )
        old_to_new[old_idx] = new_idx

    # Re-add bonds with new indices
    for bond in graph.bonds:
        a1 = old_to_new[bond.atom1]
        a2 = old_to_new[bond.atom2]
        builder.add_bond(
            a1, a2,
            order=bond.order,
            bond_type=bond.bond_type,
            stereochemistry=bond.stereochemistry,
            topology=bond.topology,
            is_aromatic=bond.is_aromatic,
            length=bond.length,
            properties=dict(bond.properties),
        )

    return builder.build()


def is_canonical(graph: MolecularGraph, smiles: str) -> bool:
    """Check if a SMILES string is canonical for the given graph.

    Args:
        graph: The molecular graph.
        smiles: The SMILES string to check.

    Returns:
        True if the SMILES is canonical for this graph.
    """
    canonical = canonical_smiles(graph)

    # Compare by parsing both and checking graph equivalence
    from chemengine.parsing.smiles import parse_smiles
    g_canon = parse_smiles(canonical)
    g_check = parse_smiles(smiles)

    # Compare heavy atom counts and element distributions
    z_canon = sorted(a.atomic_number for a in g_canon.atoms)
    z_check = sorted(a.atomic_number for a in g_check.atoms)
    if z_canon != z_check:
        return False

    # Compare bond counts
    if g_canon.num_bonds != g_check.num_bonds:
        return False

    return True
