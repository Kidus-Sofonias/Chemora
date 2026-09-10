"""VF2 subgraph isomorphism algorithm for molecular graphs.

Provides:
    - has_subgraph_match(): Check if a query graph exists in a target graph
    - find_subgraph_matches(): Find all matches of a query in a target
    - count_subgraph_matches(): Count matching occurrences
    - maximum_common_substructure(): Find MCS between two graphs
"""

from __future__ import annotations

from collections.abc import Callable

from chemengine.core.graph import MolecularGraph

# Type alias for compatibility function
AtomCompatibility = Callable[[MolecularGraph, int, MolecularGraph, int], bool]
BondCompatibility = Callable[[MolecularGraph, int, int, MolecularGraph, int, int], bool]


def _default_atom_compatible(target: MolecularGraph, t_i: int,
                              query: MolecularGraph, q_i: int) -> bool:
    """Default atom compatibility: same atomic number (wildcard 0 matches any)."""
    t_atom = target.atoms[t_i]
    q_atom = query.atoms[q_i]
    # Wildcard (atomic number 0) matches anything
    if q_atom.atomic_number == 0:
        return True
    # Aromaticity must match if query specifies it
    if q_atom.is_aromatic and not t_atom.is_aromatic:
        return False
    return t_atom.atomic_number == q_atom.atomic_number


def _default_bond_compatible(target: MolecularGraph, t1: int, t2: int,
                              query: MolecularGraph, q1: int, q2: int) -> bool:
    """Default bond compatibility: same bond order."""
    t_bond = target.get_bond(t1, t2)
    q_bond = query.get_bond(q1, q2)
    if t_bond is None or q_bond is None:
        return False
    # Wildcard bond (order 0) matches anything
    if q_bond.order == 0:
        return True
    return t_bond.order == q_bond.order


def _build_adjacency(graph: MolecularGraph) -> list[list[int]]:
    """Build adjacency list from a molecular graph."""
    n = graph.num_atoms
    adj: list[list[int]] = [[] for _ in range(n)]
    for bond in graph.bonds:
        adj[bond.atom1].append(bond.atom2)
        adj[bond.atom2].append(bond.atom1)
    return adj


def has_subgraph_match(
    target: MolecularGraph,
    query: MolecularGraph,
    *,
    atom_compatible: AtomCompatibility = _default_atom_compatible,
    bond_compatible: BondCompatibility = _default_bond_compatible,
) -> bool:
    """Check if the query graph exists as a subgraph of the target.

    Args:
        target: The larger graph to search within.
        query: The subgraph to find.
        atom_compatible: Optional atom compatibility function.
        bond_compatible: Optional bond compatibility function.

    Returns:
        True if at least one subgraph isomorphism exists.
    """
    return len(find_subgraph_matches(
        target, query,
        atom_compatible=atom_compatible,
        bond_compatible=bond_compatible,
        limit=1,
    )) > 0


def find_subgraph_matches(
    target: MolecularGraph,
    query: MolecularGraph,
    *,
    atom_compatible: AtomCompatibility = _default_atom_compatible,
    bond_compatible: BondCompatibility = _default_bond_compatible,
    limit: int = 0,
) -> list[dict[int, int]]:
    """Find all matches of query as a subgraph of target using VF2.

    Args:
        target: The larger graph to search within.
        query: The subgraph to find.
        atom_compatible: Optional atom compatibility function.
        bond_compatible: Optional bond compatibility function.
        limit: Maximum matches to find (0 = unlimited).

    Returns:
        List of mappings {query_atom: target_atom} for each match.
    """
    if query.num_atoms > target.num_atoms:
        return []
    if query.num_atoms == 0:
        return [{}]

    t_adj = _build_adjacency(target)
    q_adj = _build_adjacency(query)
    matches: list[dict[int, int]] = []
    seen: set[frozenset[int]] = set()

    # Mapping: query_atom -> target_atom
    q_to_t: dict[int, int] = {}
    t_used: set[int] = set()

    def _vf2_match(q_node: int) -> bool:
        """Recursive VF2 matching step."""
        nonlocal matches
        if len(matches) >= limit > 0:
            return True

        if q_node == query.num_atoms:
            # Dedup by target atom set (handles symmetric matches)
            t_set = frozenset(q_to_t.values())
            if t_set not in seen:
                seen.add(t_set)
                matches.append(dict(q_to_t))
            return len(matches) >= limit > 0

        # Find candidate target nodes for this query node
        candidates = _get_candidates(target, query, q_adj, t_adj,
                                     q_to_t, t_used, q_node,
                                     atom_compatible)

        for t_node in candidates:
            # Check bond consistency with already-matched neighbors
            if not _check_bond_consistency(target, query, q_adj,
                                            q_to_t, q_node, t_node,
                                            bond_compatible):
                continue

            # Match
            q_to_t[q_node] = t_node
            t_used.add(t_node)

            if _vf2_match(q_node + 1):
                return True

            # Backtrack
            del q_to_t[q_node]
            t_used.remove(t_node)

        return False

    _vf2_match(0)
    return matches


def count_subgraph_matches(
    target: MolecularGraph,
    query: MolecularGraph,
    *,
    atom_compatible: AtomCompatibility = _default_atom_compatible,
    bond_compatible: BondCompatibility = _default_bond_compatible,
) -> int:
    """Count the number of subgraph matches of query in target.

    Args:
        target: The larger graph to search within.
        query: The subgraph to find.
        atom_compatible: Optional atom compatibility function.
        bond_compatible: Optional bond compatibility function.

    Returns:
        Number of distinct matches found.
    """
    return len(find_subgraph_matches(
        target, query,
        atom_compatible=atom_compatible,
        bond_compatible=bond_compatible,
    ))


def _get_candidates(
    target: MolecularGraph,
    query: MolecularGraph,
    q_adj: list[list[int]],
    t_adj: list[list[int]],
    q_to_t: dict[int, int],
    t_used: set[int],
    q_node: int,
    atom_compatible: AtomCompatibility,
) -> list[int]:
    """Get candidate target nodes for a query node.

    Prefer neighbors of already-matched nodes (VF2 optimization).
    """
    # Find already-matched neighbors of this query node
    matched_neighbors = [n for n in q_adj[q_node] if n in q_to_t]

    if matched_neighbors:
        # Use neighbors of the matched target nodes
        candidates: set[int] = set()
        for q_nbr in matched_neighbors:
            t_nbr = q_to_t[q_nbr]
            for adj_t in t_adj[t_nbr]:
                if adj_t not in t_used:
                    candidates.add(adj_t)
        candidate_list = sorted(candidates)
    else:
        # No matched neighbors — try all unmatched target nodes
        candidate_list = sorted([
            i for i in range(target.num_atoms) if i not in t_used
        ])

    # Filter by atom compatibility
    return [
        t for t in candidate_list
        if atom_compatible(target, t, query, q_node)
    ]


def _check_bond_consistency(
    target: MolecularGraph,
    query: MolecularGraph,
    q_adj: list[list[int]],
    q_to_t: dict[int, int],
    q_node: int,
    t_node: int,
    bond_compatible: BondCompatibility,
) -> bool:
    """Check that all bonds to matched neighbors are consistent."""
    for q_nbr in q_adj[q_node]:
        if q_nbr in q_to_t:
            t_nbr = q_to_t[q_nbr]
            if not bond_compatible(target, t_node, t_nbr,
                                    query, q_node, q_nbr):
                return False
            # Also verify the bond exists in target
            if target.get_bond(t_node, t_nbr) is None:
                return False
    return True


def maximum_common_substructure(
    graph1: MolecularGraph,
    graph2: MolecularGraph,
    *,
    atom_compatible: AtomCompatibility | None = None,
    bond_compatible: BondCompatibility | None = None,
    min_atoms: int = 1,
) -> tuple[frozenset[int], frozenset[int]] | None:
    """Find the maximum common substructure (MCS) between two graphs.

    Uses a backtracking approach on atom pairs. For small graphs only
    (<20 atoms), as this is a computationally expensive NP-hard problem.

    Args:
        graph1: First molecular graph.
        graph2: Second molecular graph.
        atom_compatible: Optional atom compatibility function.
        bond_compatible: Optional bond compatibility function.
        min_atoms: Minimum number of atoms for a valid MCS.

    Returns:
        Tuple of (atoms_from_g1, atoms_from_g2) for the MCS, or None.
    """
    if atom_compatible is None:
        atom_compatible = _default_atom_compatible
    if bond_compatible is None:
        bond_compatible = _default_bond_compatible

    n1, n2 = graph1.num_atoms, graph2.num_atoms
    if n1 > 20 or n2 > 20:
        return None

    best: tuple[int, frozenset[int], frozenset[int]] = (0, frozenset(), frozenset())

    # Focus on heavy atoms only for MCS
    heavy1 = [i for i in range(n1) if graph1.atoms[i].atomic_number != 1]
    heavy2 = [j for j in range(n2) if graph2.atoms[j].atomic_number != 1]

    if len(heavy1) > 20 or len(heavy2) > 20:
        return None

    # Try all pairs of compatible heavy atoms as seeds
    for i in heavy1:
        for j in heavy2:
            if not atom_compatible(graph1, i, graph2, j):
                continue

            # Backtracking MCS from this seed
            mapping: dict[int, int] = {i: j}
            used1: set[int] = {i}
            used2: set[int] = {j}
            _mcs_depth = 0

            def _extend() -> None:
                nonlocal best, _mcs_depth
                _mcs_depth += 1
                if _mcs_depth > 30:  # Safety limit
                    _mcs_depth -= 1
                    return

                current = len(mapping)
                if current > best[0] and current >= min_atoms:
                    best = (current,
                            frozenset(mapping.keys()),
                            frozenset(mapping.values()))

                # Find candidate pairs among heavy atoms
                for a1 in heavy1:
                    if a1 in used1:
                        continue
                    for a2 in heavy2:
                        if a2 in used2:
                            continue
                        if not atom_compatible(graph1, a1, graph2, a2):
                            continue

                        # Check all existing mapping connections
                        ok = True
                        for m1, m2 in mapping.items():
                            b1 = graph1.get_bond(a1, m1)
                            b2 = graph2.get_bond(a2, m2)
                            if (b1 is None) != (b2 is None):
                                ok = False
                                break
                            if b1 is not None and b2 is not None:
                                if not bond_compatible(graph1, a1, m1,
                                                        graph2, a2, m2):
                                    ok = False
                                    break
                        if not ok:
                            continue

                        mapping[a1] = a2
                        used1.add(a1)
                        used2.add(a2)
                        _extend()
                        del mapping[a1]
                        used1.discard(a1)
                        used2.discard(a2)

                _mcs_depth -= 1

            _extend()

    if best[0] >= min_atoms:
        return (best[1], best[2])
    return None
