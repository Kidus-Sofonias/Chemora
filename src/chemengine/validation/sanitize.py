"""Graph sanitization algorithms for molecular graphs.

Sanitization repairs common chemical graph issues to produce chemically
valid molecules. Operations are performed through MolecularGraphBuilder
and produce a new, sanitized MolecularGraph.

Operations:
    - add_implicit_hydrogens: Compute and set missing implicit H counts.
    - assign_formal_charges: Assign formal charges from valence rules.
    - remove_duplicate_bonds: Deduplicate bonds between the same atom pair.
    - sanitize: Run all sanitization steps in order.
"""

from __future__ import annotations

from chemengine.core.atoms import Atom
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder


def add_implicit_hydrogens(graph: MolecularGraph) -> MolecularGraph:
    """Compute and set implicit hydrogen counts for all atoms.

    For each atom where implicit_hydrogens is None, auto-compute the
    appropriate count based on valence rules:
        implicit_H = max_valence - (bond_order_sum + formal_charge)

    Args:
        graph: The molecular graph to sanitize.

    Returns:
        A new MolecularGraph with implicit hydrogens populated.
    """
    builder = MolecularGraphBuilder.from_graph(graph)
    new_atoms: list[Atom] = []

    for i, atom in enumerate(graph.atoms):
        if atom.implicit_hydrogens is not None:
            # Already set — keep as-is
            new_atoms.append(atom)
            continue

        if atom.atomic_number == 0:
            # Wildcard — no implicit H
            new_atoms.append(atom)
            continue

        # Count total bond order
        total_bond_order = sum(
            bond.order for bond in graph.bonds
            if bond.atom1 == i or bond.atom2 == i
        )

        # Compute implicit H
        max_val = atom.max_valence if atom.max_valence > 0 else atom.default_valence
        if max_val <= 0:
            max_val = 4  # Fallback

        # For noble gases, no implicit H
        if atom.element.is_noble_gas:
            impl_h = 0
        else:
            val = max_val - (total_bond_order + atom.formal_charge)
            impl_h = max(val, 0)
            # Cap at reasonable max (main group elements)
            impl_h = min(impl_h, 4)

        new_atom = Atom(
            atomic_number=atom.atomic_number,
            formal_charge=atom.formal_charge,
            radical_electrons=atom.radical_electrons,
            isotope=atom.isotope,
            stereochemistry=atom.stereochemistry,
            hybridization=atom.hybridization,
            valence=atom.valence,
            implicit_hydrogens=impl_h,
            atom_mapping=atom.atom_mapping,
            is_aromatic=atom.is_aromatic,
            properties=atom.properties,
        )
        new_atoms.append(new_atom)

    # Rebuild
    builder._atoms = new_atoms
    return builder.build()


def assign_formal_charges(graph: MolecularGraph) -> MolecularGraph:
    """Assign formal charges from valence rules.

    Uses a heuristic based on element group number (typical valence):
        FC = typical_valence - total_bond_order

    Atoms that already have a non-zero formal charge (from SMILES parsing)
    are left unchanged.

    Args:
        graph: The molecular graph to sanitize.

    Returns:
        A new MolecularGraph with formal charges assigned.
    """
    # Element group numbers (valence electrons in neutral atom)
    _GROUP: dict[int, int] = {
        1: 1, 2: 2,  # H, He
        3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7, 10: 8,  # Period 2
        11: 1, 12: 2, 13: 3, 14: 4, 15: 5, 16: 6, 17: 7, 18: 8,  # Period 3
    }
    _TRANSITION_METALS: set[int] = set(range(21, 31)) | set(range(39, 49)) | set(range(72, 81))

    new_atoms: list[Atom] = []
    changed = False

    for i, atom in enumerate(graph.atoms):
        z = atom.atomic_number
        if z == 0:
            new_atoms.append(atom)
            continue

        # Don't overwrite explicitly set charges (from SMILES parsing)
        if atom.formal_charge != 0:
            new_atoms.append(atom)
            continue

        # Count total bond order for this atom
        total_bond_order = sum(
            bond.order for bond in graph.bonds
            if bond.atom1 == i or bond.atom2 == i
        )

        # Get element's typical valence (group number for main group)
        if z in _GROUP:
            typical_valence = _GROUP[z]
        elif z in _TRANSITION_METALS:
            try:
                typical_valence = atom.element.default_valence
            except Exception:
                typical_valence = 2
        else:
            try:
                typical_valence = atom.element.default_valence
            except Exception:
                typical_valence = 4

        if typical_valence <= 0:
            new_atoms.append(atom)
            continue

        expected_charge = typical_valence - total_bond_order

        if expected_charge != 0:
            new_atom = Atom(
                atomic_number=z,
                formal_charge=expected_charge,
                radical_electrons=atom.radical_electrons,
                isotope=atom.isotope,
                stereochemistry=atom.stereochemistry,
                hybridization=atom.hybridization,
                valence=atom.valence,
                implicit_hydrogens=atom.implicit_hydrogens,
                atom_mapping=atom.atom_mapping,
                is_aromatic=atom.is_aromatic,
                properties=atom.properties,
            )
            new_atoms.append(new_atom)
            changed = True
        else:
            new_atoms.append(atom)

    if not changed:
        return graph

    builder = MolecularGraphBuilder.from_graph(graph)
    builder._atoms = new_atoms
    return builder.build()


def remove_duplicate_bonds(graph: MolecularGraph) -> MolecularGraph:
    """Remove duplicate bonds between the same atom pair.

    If two bonds exist between atoms (a, b), keep the one with the
    higher bond order (more specific).

    Args:
        graph: The molecular graph to sanitize.

    Returns:
        A new MolecularGraph with duplicate bonds removed.
    """
    seen_pairs: dict[tuple[int, int], int] = {}
    duplicates: set[int] = set()

    for j, bond in enumerate(graph.bonds):
        pair = (min(bond.atom1, bond.atom2), max(bond.atom1, bond.atom2))
        if pair in seen_pairs:
            # Keep the bond with higher order
            existing_idx = seen_pairs[pair]
            existing_bond = graph.bonds[existing_idx]
            if bond.order > existing_bond.order:
                duplicates.add(existing_idx)
                seen_pairs[pair] = j
            else:
                duplicates.add(j)
        else:
            seen_pairs[pair] = j

    if not duplicates:
        return graph

    # Rebuild without duplicates
    builder = MolecularGraphBuilder.from_graph(graph)
    builder._bonds = [
        bond for j, bond in enumerate(graph.bonds)
        if j not in duplicates
    ]
    return builder.build()


def sanitize(graph: MolecularGraph) -> MolecularGraph:
    """Run all sanitization steps on a molecular graph.

    Applies, in order:
        1. Remove duplicate bonds
        2. Add implicit hydrogens
        3. Assign formal charges (placeholder)

    Args:
        graph: The molecular graph to sanitize.

    Returns:
        A new, sanitized MolecularGraph.
    """
    result = remove_duplicate_bonds(graph)
    result = add_implicit_hydrogens(result)
    result = assign_formal_charges(result)
    return result
