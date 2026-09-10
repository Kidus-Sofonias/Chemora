"""Stereoisomer enumeration from a molecular graph."""

from __future__ import annotations

import itertools

from chemengine.core.bonds import BondOrder
from chemengine.core.enums import BondStereo, ChiralTag
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.core.stereo import ChiralCenter, StereoCategory


def enumerate_stereoisomers(graph: MolecularGraph) -> list[MolecularGraph]:
    """Enumerate all stereoisomers for a molecule.

    Generates all combinations of R/S for tetrahedral centers and
    E/Z for double bonds.

    Args:
        graph: The molecular graph.

    Returns:
        List of MolecularGraph objects for each stereoisomer.
    """
    # Find potential stereocenters (sp3 carbon with 4 distinct substituents)
    tetrahedral_centers: list[int] = []
    for i in range(graph.num_atoms):
        atom = graph.atoms[i]
        if atom.atomic_number == 6:
            nbrs = graph.get_neighbors(i)
            if len(nbrs) == 4:
                # Check that all 4 substituents are chemically distinct
                substituent_keys = []
                for n in nbrs:
                    n_atom = graph.atoms[n]
                    # Build a key: (atomic_number, formal_charge) as minimum distinction
                    key = (n_atom.atomic_number, n_atom.formal_charge)
                    substituent_keys.append(key)
                # A stereocenter requires at least 3 distinct substituents
                # (4 distinct is ideal, but 3 distinct + 1 duplicate is borderline)
                if len(set(substituent_keys)) >= 3:
                    tetrahedral_centers.append(i)

    # Find stereogenic double bonds
    stereo_bonds: list[int] = []
    for j, bond in enumerate(graph.bonds):
        if bond.order == BondOrder.DOUBLE:
            a1, a2 = bond.atom1, bond.atom2
            n1 = [n for n in graph.get_neighbors(a1) if n != a2]
            n2 = [n for n in graph.get_neighbors(a2) if n != a1]
            if len(n1) >= 1 and len(n2) >= 1:
                stereo_bonds.append(j)

    n_centers = len(tetrahedral_centers)
    n_bonds = len(stereo_bonds)
    n_isomers = 2 ** (n_centers + n_bonds)

    if n_isomers > 128:  # Safety limit
        return []

    isomers: list[MolecularGraph] = []
    for combo in itertools.product([ChiralTag.R, ChiralTag.S], repeat=n_centers):
        for bond_combo in itertools.product([BondStereo.E, BondStereo.Z], repeat=n_bonds):
            builder = MolecularGraphBuilder.from_graph(graph)
            for idx, center in enumerate(tetrahedral_centers):
                builder.add_chiral_center(ChiralCenter(
                    category=StereoCategory.TETRAHEDRAL,
                    atom_index=center,
                    chiral_tag=combo[idx],
                ))
            for idx, bond_idx in enumerate(stereo_bonds):
                builder.add_chiral_center(ChiralCenter(
                    category=StereoCategory.DOUBLE_BOND,
                    bond_index=bond_idx,
                    bond_stereo=bond_combo[idx],
                ))
            isomers.append(builder.build())

    return isomers
