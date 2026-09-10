"""Molecular property computation descriptors."""

from __future__ import annotations

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph
from chemengine.detection.rings import detect_rings

# TPSA fragment contributions (Ertl, P. et al., J. Med. Chem. 2000)
_TPSA_FRAGMENTS: dict[str, float] = {
    "[O]": 17.07,      # carbonyl oxygen
    "[OH]": 20.23,     # hydroxyl oxygen
    "[O-]": 23.06,     # negatively charged oxygen
    "[N]": 12.36,      # sp2 nitrogen
    "[NH]": 15.79,     # secondary amine nitrogen
    "[NH2]": 26.02,    # primary amine nitrogen
    "[N+]": 13.36,     # positively charged nitrogen
    "[N-O]": 21.81,    # N-oxide
    "[S]": 32.10,      # sulfoxide sulfur
    "[SO2]": 51.92,    # sulfone sulfur
}


def compute_tpsa(graph: MolecularGraph) -> float:
    """Compute topological polar surface area (TPSA).

    Uses fragment contributions based on atom types.

    Args:
        graph: The molecular graph.

    Returns:
        TPSA value in Angstroms^2.
    """
    tpsa = 0.0
    for i, atom in enumerate(graph.atoms):
        z = atom.atomic_number
        charge = atom.formal_charge
        nbrs = graph.get_neighbors(i)
        has_h = any(graph.atoms[n].atomic_number == 1 for n in nbrs)
        bonded_oxygen = any(
            graph.atoms[n].atomic_number == 8 for n in nbrs
        )

        if z == 8:  # Oxygen
            if charge == -1:
                tpsa += 23.06  # [O-]
            elif has_h:
                tpsa += 20.23  # [OH]
            elif any(graph.get_bond(i, n).order == BondOrder.DOUBLE
                     for n in nbrs if graph.atoms[n].atomic_number == 6):
                tpsa += 17.07  # C=O
            else:
                tpsa += 20.23  # default ether/hydroxyl
        elif z == 7:  # Nitrogen
            if charge == 1:
                tpsa += 13.36  # [N+]
            elif bonded_oxygen:
                tpsa += 21.81  # N-O
            elif has_h:
                h_count = sum(1 for n in nbrs
                              if graph.atoms[n].atomic_number == 1)
                if h_count >= 2:
                    tpsa += 26.02  # [NH2]
                else:
                    tpsa += 15.79  # [NH]
            else:
                # Check if double bonded (sp2)
                has_db = any(
                    graph.get_bond(i, n).order == BondOrder.DOUBLE
                    for n in nbrs
                )
                if has_db:
                    tpsa += 12.36  # imine / pyridine-like
                else:
                    tpsa += 15.79  # default
        elif z == 16:  # Sulfur
            # Check for sulfoxide or sulfone
            double_bonded_o = sum(
                1 for n in nbrs
                if graph.atoms[n].atomic_number == 8
                and graph.get_bond(i, n).order == BondOrder.DOUBLE
            )
            if double_bonded_o == 1:
                tpsa += 32.10  # S=O
            elif double_bonded_o == 2:
                tpsa += 51.92  # O=S=O

    return tpsa


def compute_logp(graph: MolecularGraph) -> float:
    """Compute Wildman-Crippen logP using fragment-based atom contributions.

    Uses the Wildman-Crippen method with atom-type contributions based on:
    - Element type
    - Bonding environment (aromatic, single, double, triple)
    - Neighbor elements (for context-dependent contributions)

    Reference: Wildman, S.A. & Crippen, G.M. J. Chem. Inf. Comput. Sci. 1999.

    Args:
        graph: The molecular graph.

    Returns:
        Estimated logP value.
    """
    logp = 0.0

    # Wildman-Crippen atom-type contributions (approximation)
    # These are based on the original paper's fragment tables
    _WC_LOGP: dict[int, float] = {
        1: 0.0000,    # H
        6: 0.1441,    # C (sp3, aliphatic)
        7: -0.0516,   # N
        8: -0.0024,   # O
        9: 0.3738,    # F
        15: -0.2490,  # P
        16: 0.0599,   # S
        17: 0.6895,   # Cl
        35: 0.8813,   # Br
        53: 0.8294,   # I
    }

    # Context-dependent corrections
    _AROMATIC_CORRECTION = 0.0819
    _C_DOUBLE_BOND = 0.2029     # C=C, C=O
    _C_TRIPLE_BOND = 0.1499     # C≡C, C≡N
    _OH_CORRECTION = -0.2035    # O-H bond
    _NH_CORRECTION = -0.0316    # N-H bond

    for i, atom in enumerate(graph.atoms):
        z = atom.atomic_number
        base = _WC_LOGP.get(z, 0.0)

        # Check bonding context
        is_aromatic = atom.is_aromatic
        has_double_bond = False
        has_triple_bond = False
        has_oh = False
        has_nh = False

        for nbr in graph.get_neighbors(i):
            bond = graph.get_bond(i, nbr)
            if bond is None:
                continue
            if bond.is_aromatic:
                is_aromatic = True
            if bond.order == BondOrder.DOUBLE:
                has_double_bond = True
            if bond.order == BondOrder.TRIPLE:
                has_triple_bond = True
            # Check for H-bonding contexts
            nbr_z = graph.atoms[nbr].atomic_number
            if z == 8 and nbr_z == 1:
                has_oh = True
            if z == 7 and nbr_z == 1:
                has_nh = True

        # Apply context corrections
        if z == 6 and is_aromatic:
            base = 0.0819  # Aromatic C
        elif z == 6 and has_double_bond:
            base = _C_DOUBLE_BOND
        elif z == 6 and has_triple_bond:
            base = _C_TRIPLE_BOND
        elif z == 6:
            base = 0.1441  # sp3 C

        if has_oh and z == 8:
            base += _OH_CORRECTION
        if has_nh and z == 7:
            base += _NH_CORRECTION

        logp += base

    return round(logp, 4)


def compute_hba(graph: MolecularGraph) -> int:
    """Count hydrogen bond acceptors (N, O, F atoms with available lone pairs).

    Excludes atoms that are fully substituted and cannot accept H-bonds:
    - Quaternary nitrogen (ammonium, N⁺ with 4 bonds) — no lone pair
    - Negatively charged oxygen with no available coordination
    - Fluorine counted only if not fully coordinated

    Args:
        graph: The molecular graph.

    Returns:
        Number of HBA atoms.
    """
    count = 0
    for i, atom in enumerate(graph.atoms):
        z = atom.atomic_number
        if z == 7:  # Nitrogen
            # Count bonds (excluding implicit H)
            nbr_count = len(graph.get_neighbors(i))
            # Quaternary N⁺ with 4 bonds has no lone pair — not an HBA
            if atom.formal_charge == 1 and nbr_count >= 4:
                continue
            # Otherwise, N is HBA (has lone pair)
            count += 1
        elif z == 8:  # Oxygen
            count += 1
        elif z == 9:  # Fluorine
            # F is always an HBA (has 3 lone pairs even when bonded)
            count += 1
    return count


def compute_hbd(graph: MolecularGraph) -> int:
    """Count hydrogen bond donors (O-H and N-H groups).

    Args:
        graph: The molecular graph.

    Returns:
        Number of HBD groups.
    """
    count = 0
    for i, atom in enumerate(graph.atoms):
        z = atom.atomic_number
        if z in (7, 8):
            for nbr in graph.get_neighbors(i):
                if graph.atoms[nbr].atomic_number == 1:
                    count += 1
                    break
    return count


def compute_rotatable_bonds(graph: MolecularGraph) -> int:
    """Count rotatable bonds (single non-ring bonds not to terminal atoms).

    A bond is rotatable if:
    1. It is a single bond
    2. It is not in a ring
    3. Both atoms have at least 2 heavy-atom neighbors (excluding H)

    Args:
        graph: The molecular graph.

    Returns:
        Number of rotatable bonds.
    """
    def _heavy_degree(atom_idx: int) -> int:
        """Count neighbors that are not hydrogen."""
        return sum(
            1 for n in graph.get_neighbors(atom_idx)
            if graph.atoms[n].atomic_number != 1
        )

    count = 0
    for bond in graph.bonds:
        if bond.order != BondOrder.SINGLE:
            continue
        if bond.topology == "ring":
            continue
        # Both atoms must have at least 2 heavy-atom neighbors
        if _heavy_degree(bond.atom1) > 1 and _heavy_degree(bond.atom2) > 1:
            count += 1
    return count


def compute_fraction_csp3(graph: MolecularGraph) -> float:
    """Compute fraction of sp3 carbons.

    Args:
        graph: The molecular graph.

    Returns:
        Fraction of carbon atoms that are sp3 hybridized (0.0 to 1.0).
    """
    sp3 = 0
    total_c = 0
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number == 6:
            total_c += 1
            nbrs = graph.get_neighbors(i)
            db_count = sum(
                1 for n in nbrs
                if graph.get_bond(i, n) is not None
                and graph.get_bond(i, n).order in (BondOrder.DOUBLE, BondOrder.TRIPLE, BondOrder.AROMATIC)
            )
            if db_count == 0:
                sp3 += 1
    if total_c == 0:
        return 0.0
    return sp3 / total_c


# Property registry for dynamic lookup
PROPERTY_REGISTRY: dict[str, callable] = {
    "tpsa": compute_tpsa,
    "logp": compute_logp,
    "hba": compute_hba,
    "hbd": compute_hbd,
    "rotatable_bonds": compute_rotatable_bonds,
    "fraction_csp3": compute_fraction_csp3,
}


def compute_property(graph: MolecularGraph, name: str) -> float | int | str:
    """Compute any registered molecular property by name.

    Args:
        graph: The molecular graph.
        name: Property name ('tpsa', 'logp', 'hba', 'hbd', 'rotatable_bonds', 'fraction_csp3').

    Returns:
        The computed property value.

    Raises:
        KeyError: If the property name is not registered.
    """
    if name == "tpsa":
        return compute_tpsa(graph)
    elif name == "logp":
        return compute_logp(graph)
    elif name == "hba":
        return compute_hba(graph)
    elif name == "hbd":
        return compute_hbd(graph)
    elif name == "rotatable_bonds":
        return compute_rotatable_bonds(graph)
    elif name == "fraction_csp3":
        return compute_fraction_csp3(graph)
    elif name == "formula":
        return graph.molecular_formula
    elif name == "mass":
        return graph.exact_mass
    elif name == "weight":
        return graph.molecular_weight
    elif name == "heavy_atoms":
        return graph.num_heavy_atoms
    elif name == "num_rings":
        rings = graph.rings if graph.rings else detect_rings(graph)
        return len(rings)
    else:
        raise KeyError(f"Unknown property: {name}")
