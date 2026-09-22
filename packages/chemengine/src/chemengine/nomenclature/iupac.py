"""IUPAC Naming Engine — Graph → IUPAC name (M33 Phase 11.3).

Generates preferred IUPAC names (PINs) for the classes the naming
subsystem documents it supports:

- Linear and branched alkanes (methane through icosane) with alkyl and
  halogen substituents and proper locants
- Alkenes and alkynes with locants (``but-1-ene``, ``buta-1,3-diene``)
- Alcohols (``butan-1-ol``, ``propane-1,2-diol``), aldehydes
  (``propanal``, ``butanedial``), ketones (``pentane-2,4-dione``),
  carboxylic acids, esters (``ethyl ethanoate``), amides (including
  N-substituents), nitriles, and amines (primary/secondary with N-locants)
- Cycloalkanes with simple substituents (``methylcyclohexane``)
- Aromatic carbocycles: benzene, toluene, xylene isomers,
  ethylbenzene, halobenzenes, phenol and cresol isomers
- Unsubstituted common heterocycles (pyridine, pyrimidine, pyrrole,
  furan, thiophene, imidazole)

**Coverage boundary (honest).** Structures outside the classes above —
including fused aromatics (naphthalene), substituted heterocycles,
aromatics with carbonyl groups, any ring system larger than one simple
ring, and molecules with several interacting functional groups — raise
:class:`UnsupportedNamingError` rather than returning a plausible but
incorrect name. Callers (``name_molecule`` tool, serialization)
translate that into a structured error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chemengine.core.enums import BondOrder
from chemengine.core.graph import MolecularGraph


class UnsupportedNamingError(ValueError):
    """Raised when a graph is outside the naming subsystem's coverage.

    The message states the unsupported feature. This is a documented,
    catchable condition — the engine never returns a plausible but
    chemically incorrect name.
    """


# ── Stem Names ──

ALKANE_STEMS: dict[int, str] = {
    1: "meth", 2: "eth", 3: "prop", 4: "but", 5: "pent",
    6: "hex", 7: "hept", 8: "oct", 9: "non", 10: "dec",
    11: "undec", 12: "dodec", 13: "tridec", 14: "tetradec",
    15: "pentadec", 16: "hexadec", 17: "heptadec", 18: "octadec",
    19: "nonadec", 20: "icos",
}

SUBSTITUENT_NAMES: dict[int, str] = {
    1: "methyl", 2: "ethyl", 3: "propyl", 4: "butyl",
    5: "pentyl", 6: "hexyl", 7: "heptyl", 8: "octyl",
}

MULTI_PREFIXES: dict[int, str] = {
    1: "", 2: "di", 3: "tri", 4: "tetra", 5: "penta",
    6: "hexa", 7: "hepta", 8: "octa", 9: "nona", 10: "deca",
}

HALOGEN_NAMES: dict[int, str] = {9: "fluoro", 17: "chloro", 35: "bromo", 53: "iodo"}


def _is_nitro_nitrogen(graph: Any, idx: int) -> bool:
    """Whether atom ``idx`` is the nitrogen of a nitro group.

    Accepts both standard representations: charge-separated ``[N+](=O)[O-]``
    (one double O, one singly-bonded O carrying -1) and the pentavalent
    ``N(=O)=O`` form (two double-bonded neutral O).
    """
    atom = graph.atoms[idx]
    if atom.atomic_number != 7:
        return False
    double_os: list[int] = []
    single_o: int | None = None
    for n in graph.get_neighbors(idx):
        if graph.atoms[n].atomic_number != 8:
            # The carbon (or other) attachment point is expected — skip it.
            continue
        bond = graph.get_bond(idx, n)
        if bond is None or bond.is_aromatic:
            return False
        if bond.order == BondOrder.DOUBLE:
            double_os.append(n)
        elif bond.order == BondOrder.SINGLE:
            single_o = n
        else:
            return False
    if len(double_os) == 2 and single_o is None:
        # Pentavalent N(=O)=O: nitrogen neutral, oxygens neutral.
        return getattr(atom, "formal_charge", 0) == 0
    if len(double_os) == 1 and single_o is not None:
        # Charge-separated [N+](=O)[O-].
        return (
            getattr(atom, "formal_charge", 0) == 1
            and getattr(graph.atoms[single_o], "formal_charge", 0) == -1
        )
    return False

# Heterocycle names by (ring size, {element: count}) — unsubstituted only.
HETEROCYCLE_NAMES: dict[tuple[int, frozenset[tuple[int, int]]], str] = {
    (5, frozenset({(7, 1)})): "pyrrole",
    (5, frozenset({(8, 1)})): "furan",
    (5, frozenset({(16, 1)})): "thiophene",
    (5, frozenset({(7, 2)})): "imidazole",
    (6, frozenset({(7, 1)})): "pyridine",
    (6, frozenset({(7, 2)})): "pyrimidine",
    (6, frozenset({(8, 1)})): "pyran",
}

# ── Functional Group Priority (highest = 1) ──
FG_PRIORITY: dict[str, int] = {
    "carboxyl": 1,
    "ester": 2,
    "amide": 3,
    "nitrile": 4,
    "aldehyde": 5,
    "ketone": 6,
    "hydroxyl": 7,
    "amine": 8,
}


# ── Small helpers ──

def _stem_for(chain_len: int) -> str:
    """Return the alkane stem for a chain length, or raise unsupported."""
    stem = ALKANE_STEMS.get(chain_len)
    if stem is None:
        raise UnsupportedNamingError(f"carbon skeleton of {chain_len} atoms is outside naming coverage")
    return stem


def _is_aromatic(bond: object) -> bool:
    """True when a bond is aromatic."""
    return bool(getattr(bond, "is_aromatic", False))


def _neighbors_z(graph: MolecularGraph, idx: int) -> list[int]:
    """Atomic numbers of an atom's neighbors."""
    return [graph.atoms[n].atomic_number for n in graph.get_neighbors(idx)]


# ── Functional Group Detection ──

def _detect_functional_groups(graph: MolecularGraph) -> dict[str, list[int]]:
    """Detect key functional groups and return the atom indices.

    Keys: ``hydroxyl`` (O of O-H), ``amine`` (N), ``nitrile`` (N of C≡N),
    ``halogen``, ``alkene``/``alkyne`` (one C of each unsaturation),
    ``carboxyl``, ``ester``, ``amide`` (acyl C), ``aldehyde``/``carbonyl``
    (C of C=O). Aromatic-ring double bonds are excluded from
    ``alkene`` — aromaticity is handled by the ring namer.
    """
    groups: dict[str, list[int]] = {
        "hydroxyl": [],
        "carbonyl": [],
        "carboxyl": [],
        "ester": [],
        "amide": [],
        "amine": [],
        "nitrile": [],
        "nitro": [],
        "halogen": [],
        "alkene": [],
        "alkyne": [],
    }

    aromatic_bond_atoms = {
        frozenset((b.atom1, b.atom2))
        for b in graph.bonds
        if b.is_aromatic
    }

    for i, atom in enumerate(graph.atoms):
        z = atom.atomic_number
        neighbors = graph.get_neighbors(i)

        # Hydroxyl (O-H bonded to a non-O heavy atom)
        if z == 8:
            has_h = any(graph.atoms[n].atomic_number == 1 for n in neighbors)
            has_heavy = any(
                graph.atoms[n].atomic_number not in (1, 8) for n in neighbors
            )
            if has_h and has_heavy:
                groups["hydroxyl"].append(i)

        # Amine (N bonded to C, not a nitrile N, not an amide N)
        if z == 7:
            has_c = any(graph.atoms[n].atomic_number == 6 for n in neighbors)
            is_nitrile = any(
                (b := graph.get_bond(i, n)) is not None
                and b.order == BondOrder.TRIPLE
                and graph.atoms[n].atomic_number == 6
                for n in neighbors
            )
            is_amide_n = any(
                graph.atoms[nn].atomic_number == 6
                and any(
                    (ob := graph.get_bond(nn, m)) is not None
                    and ob.order == BondOrder.DOUBLE
                    and graph.atoms[m].atomic_number == 8
                    for m in graph.get_neighbors(nn)
                )
                for nn in neighbors
                if graph.atoms[nn].atomic_number == 6
            )
            if has_c and not is_nitrile and not is_amide_n and not _is_nitro_nitrogen(
                graph, i
            ):
                groups["amine"].append(i)

        # Nitro group (N(+)(=O)[O-]) — classified so that the aromatic
        # substituent walker emits 'nitro' instead of misreading the
        # positively charged N as an 'amino' prefix.
        if z == 7 and _is_nitro_nitrogen(graph, i):
            groups["nitro"].append(i)

        # Nitrile (C≡N)
        if z == 7:
            for n in neighbors:
                bond = graph.get_bond(i, n)
                if bond and bond.order == BondOrder.TRIPLE and graph.atoms[n].atomic_number == 6:
                    groups["nitrile"].append(i)

        # Halogen
        if z in (9, 17, 35, 53):
            groups["halogen"].append(i)

        # Alkene/Alkyne (non-aromatic unsaturations, counted once)
        if z == 6:
            for n in neighbors:
                if n <= i:
                    continue
                bond = graph.get_bond(i, n)
                if bond is None:
                    continue
                if frozenset((i, n)) in aromatic_bond_atoms:
                    continue
                if bond.order == BondOrder.DOUBLE:
                    groups["alkene"].append(i)
                elif bond.order == BondOrder.TRIPLE:
                    groups["alkyne"].append(i)

    def _is_carbonyl_c(i: int) -> bool:
        return any(
            (b := graph.get_bond(i, n)) is not None
            and b.order == BondOrder.DOUBLE
            and graph.atoms[n].atomic_number == 8
            for n in graph.get_neighbors(i)
        )

    # Carboxyl (C(=O)O-H)
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number != 6 or not _is_carbonyl_c(i):
            continue
        for n in graph.get_neighbors(i):
            bond = graph.get_bond(i, n)
            if (
                graph.atoms[n].atomic_number == 8
                and bond is not None
                and bond.order == BondOrder.SINGLE
                and any(graph.atoms[nn].atomic_number == 1 for nn in graph.get_neighbors(n))
            ):
                groups["carboxyl"].append(i)
                break

    # Ester (C(=O)O-C, not acid)
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number != 6 or i in groups["carboxyl"] or not _is_carbonyl_c(i):
            continue
        for n in graph.get_neighbors(i):
            bond = graph.get_bond(i, n)
            if (
                graph.atoms[n].atomic_number == 8
                and bond is not None
                and bond.order == BondOrder.SINGLE
                and any(
                    graph.atoms[nn].atomic_number == 6 and nn != i
                    for nn in graph.get_neighbors(n)
                )
            ):
                groups["ester"].append(i)
                break

    # Amide (C(=O)N)
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number != 6 or not _is_carbonyl_c(i):
            continue
        if i in groups["carboxyl"] or i in groups["ester"]:
            continue
        if any(
            graph.atoms[n].atomic_number == 7
            and (b := graph.get_bond(i, n)) is not None
            and b.order == BondOrder.SINGLE
            for n in graph.get_neighbors(i)
        ):
            groups["amide"].append(i)

    # Aldehyde (terminal C(=O)H) / Ketone (internal C(=O)C)
    higher_groups: set[int] = (
        set(groups["carboxyl"]) | set(groups["ester"]) | set(groups["amide"])
    )
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number != 6 or i in higher_groups:
            continue
        if not _is_carbonyl_c(i):
            continue
        if any(graph.atoms[nn].atomic_number == 1 for nn in graph.get_neighbors(i)):
            groups.setdefault("aldehyde", []).append(i)
        else:
            groups["carbonyl"].append(i)

    return groups


# ── Ring detection ──

def _ring_atom_set(graph: MolecularGraph) -> set[int]:
    """Indices of all atoms participating in any simple ring (size 3-8)."""
    rings = _find_simple_rings(graph)
    atoms: set[int] = set()
    for ring in rings:
        atoms.update(ring)
    return atoms


def _find_simple_rings(graph: MolecularGraph) -> list[list[int]]:
    """Find all simple rings up to size 8 (deterministic DFS)."""
    n = graph.num_atoms
    if n == 0:
        return []

    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    for bond in graph.bonds:
        adj[bond.atom1].append(bond.atom2)
        adj[bond.atom2].append(bond.atom1)

    seen_rings: set[tuple[int, ...]] = set()
    rings: list[list[int]] = []

    def dfs(start: int, current: int, path: list[int], visited: set[int]) -> None:
        for neighbor in sorted(adj[current]):
            if neighbor == start and len(path) >= 3:
                ring_key = tuple(sorted(path))
                if ring_key not in seen_rings:
                    seen_rings.add(ring_key)
                    rings.append(list(path))
            elif neighbor not in visited and neighbor > start and len(path) < 8:
                visited.add(neighbor)
                path.append(neighbor)
                dfs(start, neighbor, path, visited)
                path.pop()
                visited.discard(neighbor)

    for start in range(n):
        dfs(start, start, [start], {start})

    return rings


def _check_for_ring(graph: MolecularGraph) -> str | None:
    """Name a cyclic compound, or None when not (simply) cyclic.

    Retained for API compatibility. Raises :class:`UnsupportedNamingError`
    for ring systems outside the documented coverage.
    """
    rings = _find_simple_rings(graph)
    if not rings:
        return None
    ring = max(rings, key=len)
    if len(ring) < 3:
        return None
    return _name_ring(graph, rings)


# ── Chain enumeration (acyclic skeletons) ──

def _find_longest_chain(graph: MolecularGraph) -> list[int]:
    """Find the longest carbon chain in the molecule (deterministic).

    Retained for API compatibility; the naming functions use
    :func:`_all_carbon_chains` so locants can be minimized.
    """
    chains = _all_carbon_chains(graph)
    if not chains:
        return []
    best = max(len(c) for c in chains)
    return min(
        (c for c in chains if len(c) == best),
        key=lambda c: tuple(c),
    )


def _leaf_carbons(graph: MolecularGraph) -> list[int]:
    """Carbons with exactly one carbon neighbor (or none at all)."""
    leaves = []
    for i, atom in enumerate(graph.atoms):
        if atom.atomic_number != 6:
            continue
        c_neighbors = [
            n for n in graph.get_neighbors(i)
            if graph.atoms[n].atomic_number == 6
        ]
        if len(c_neighbors) <= 1:
            leaves.append(i)
    return sorted(leaves)


def _carbon_paths_between(graph: MolecularGraph, start: int, end: int) -> list[list[int]]:
    """All simple paths between two atoms through carbon atoms only."""
    paths: list[list[int]] = []

    def dfs(current: int, visited: set[int], path: list[int]) -> None:
        if current == end:
            paths.append(list(path))
            return
        for neighbor in graph.get_neighbors(current):
            if neighbor not in visited and graph.atoms[neighbor].atomic_number == 6:
                visited.add(neighbor)
                path.append(neighbor)
                dfs(neighbor, visited, path)
                path.pop()
                visited.discard(neighbor)

    dfs(start, {start}, [start])
    return paths


def _all_carbon_chains(graph: MolecularGraph) -> list[list[int]]:
    """All maximal carbon chains (leaf-to-leaf paths) of an acyclic molecule.

    For molecules with fewer than two leaf carbons (e.g. methane), the
    whole carbon set forms one trivial chain.
    """
    leaves = _leaf_carbons(graph)
    chains: list[list[int]] = []
    if len(leaves) < 2:
        carbons = [i for i, a in enumerate(graph.atoms) if a.atomic_number == 6]
        return [carbons] if carbons else []
    seen: set[tuple[int, ...]] = set()
    for i, start in enumerate(leaves):
        for end in leaves[i + 1:]:
            for path in _carbon_paths_between(graph, start, end):
                key = tuple(path)
                rkey = tuple(reversed(path))
                if key not in seen and rkey not in seen:
                    seen.add(key)
                    chains.append(path)
    return chains


def _chain_unsaturations(graph: MolecularGraph, chain: list[int]) -> tuple[int, int]:
    """Count (double, triple) bonds wholly inside a chain."""
    chain_set = set(chain)
    doubles = triples = 0
    for i in chain:
        for n in graph.get_neighbors(i):
            if n in chain_set and n > i:
                bond = graph.get_bond(i, n)
                if bond is None or bond.is_aromatic:
                    continue
                if bond.order == BondOrder.DOUBLE:
                    doubles += 1
                elif bond.order == BondOrder.TRIPLE:
                    triples += 1
    return doubles, triples


def _choose_hydrocarbon_chain(
    graph: MolecularGraph,
    chains: list[list[int]],
    require_doubles: int,
    require_triples: int,
) -> list[int]:
    """Pick the best hydrocarbon chain: most unsaturations, then longest,
    then lowest locants when oriented.
    """
    def key(chain: list[int]) -> tuple[int, int, int, tuple[int, ...], tuple[int, ...]]:
        d, t = _chain_unsaturations(graph, chain)
        # Final tiebreak (alkanes): minimize substituent locants across both
        # orientations so e.g. 2,3-dimethylpentane beats 3,4-.
        subs = _find_substituents(graph, chain)
        fwd = tuple(sorted(s[0] for s in subs))
        rev = tuple(sorted(s[0] for s in _find_substituents(graph, list(reversed(chain)))))
        return (d, t, -len(chain), _unsaturation_locants(graph, chain), min(fwd, rev))

    eligible = [
        c for c in chains
        if (lambda dt: dt[0] >= require_doubles and dt[1] >= require_triples)(
            _chain_unsaturations(graph, c)
        )
    ]
    if not eligible:
        raise UnsupportedNamingError("unsaturation pattern is outside naming coverage")
    return min(eligible, key=key)


def _unsaturation_locants(graph: MolecularGraph, chain: list[int]) -> tuple[int, ...]:
    """Sorted 1-based positions of unsaturations along a chain orientation."""
    chain_set = set(chain)
    locants = []
    for pos, i in enumerate(chain):
        for n in graph.get_neighbors(i):
            if n in chain_set and n > i:
                bond = graph.get_bond(i, n)
                if bond is not None and not bond.is_aromatic and bond.order in (
                    BondOrder.DOUBLE, BondOrder.TRIPLE
                ):
                    locants.append(pos + 1)
    return tuple(sorted(locants))


def _orient_for_locants(chain: list[int], score: Callable[[list[int]], tuple[int, ...]]) -> list[int]:
    """Return the chain orientation (forward/reversed) minimizing score()."""
    forward = list(chain)
    reverse = list(reversed(chain))
    return forward if score(forward) <= score(reverse) else reverse


# ── Substituent helpers ──

def _branch_is_pure_hydrocarbon(graph: MolecularGraph, start: int, excluded: set[int]) -> int | None:
    """Count carbons in a branch if it contains carbon only; else None."""
    count = 0
    visited = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        if node in excluded:
            continue
        z = graph.atoms[node].atomic_number
        if z == 6:
            count += 1
        elif z != 1:
            return None
        for neighbor in graph.get_neighbors(node):
            if neighbor not in visited and neighbor not in excluded:
                visited.add(neighbor)
                stack.append(neighbor)
    return count


def _format_substituent_prefix(substituents: list[tuple[int, str, int]]) -> str:
    """Format substituent list into a prefix string (no trailing hyphen).

    Example: ``[(2, 'methyl', 1)]`` -> ``'2-methyl'``; callers concatenate
    directly with the parent name (``'2-methylbutane'``).

    Locants are omitted only when a single substituent sits at
    position 1 (``'chloromethane'`` — no other position is possible).
    """
    if not substituents:
        return ""
    grouped: dict[str, list[int]] = {}
    for pos, name, _ in substituents:
        grouped.setdefault(name, []).append(pos)
    parts = []
    for name in sorted(grouped.keys()):
        positions = sorted(grouped[name])
        count = len(positions)
        prefix = MULTI_PREFIXES.get(count, f"({count}-)")
        # Omit a locant only when the whole molecule has exactly one
        # substituent and it sits at position 1 (unambiguous: chloromethane,
        # methylbenzene is written with an explicit 1 in multi-substituted
        # rings). With several substituents the locant disambiguates.
        if count == 1 and positions[0] == 1 and len(substituents) == 1:
            parts.append(f"{prefix}{name}")
        else:
            locants = ",".join(str(p) for p in positions)
            parts.append(f"{locants}-{prefix}{name}")
    return "-".join(parts)


# ── Main entry point ──

def generate_iupac_name(graph: MolecularGraph) -> str:
    """Generate a preferred IUPAC name for a molecular graph.

    See the module docstring for the exact supported classes. Anything
    outside that coverage raises :class:`UnsupportedNamingError`.

    Args:
        graph: The molecular graph.

    Returns:
        IUPAC name string (empty string for an empty graph).

    Raises:
        UnsupportedNamingError: The graph is outside naming coverage.
    """
    if graph.num_atoms == 0:
        return ""

    if graph.num_atoms == 1:
        atom = graph.atoms[0]
        if atom.atomic_number == 1:
            return "hydrogen"
        if atom.atomic_number == 6:
            return "methane"
        from chemengine.core.element import Element
        return Element.from_z(atom.atomic_number).name.lower()

    groups = _detect_functional_groups(graph)
    rings = _find_simple_rings(graph)

    # ── Ring systems ──
    if rings:
        return _name_ring(graph, rings)

    # ── Acyclic: functional-group priority ordering ──
    if groups.get("carboxyl"):
        return _name_carboxylic_acid(graph, groups)
    if groups.get("ester"):
        return _name_ester(graph, groups)
    if groups.get("amide"):
        return _name_amide(graph, groups)
    if groups.get("nitrile"):
        return _name_nitrile(graph, groups)
    if groups.get("aldehyde"):
        return _name_aldehyde(graph, groups)
    if groups.get("carbonyl"):
        return _name_ketone(graph, groups)
    if groups.get("hydroxyl"):
        return _name_alcohol(graph, groups)
    if groups.get("amine"):
        return _name_amine(graph, groups)

    return _name_hydrocarbon(graph, groups)


# ── Ring naming ──

def _name_ring(graph: MolecularGraph, rings: list[list[int]]) -> str:
    """Name a cyclic molecule within the documented coverage boundary."""
    groups = _detect_functional_groups(graph)
    ring = max(rings, key=len)
    ring_set = set(ring)
    ring_size = len(ring)
    atom_types = {i: atom.atomic_number for i, atom in enumerate(graph.atoms)}
    ring_atom_types = {atom_types[a] for a in ring}

    # ── Aromatic carbocycle (benzene family) ──
    ring_bonds = [
        b for b in graph.bonds
        if b.atom1 in ring_set and b.atom2 in ring_set
    ]
    is_aromatic_ring = ring_size >= 6 and all(b.is_aromatic for b in ring_bonds)

    other_rings = [r for r in rings if set(r) != ring_set]
    outside_atoms = [i for i in range(graph.num_atoms) if i not in ring_set
                     and graph.atoms[i].atomic_number != 1]

    # Collect ring substituents (heavy atoms directly bonded to the ring)
    substituents: list[tuple[int, str, int]] = []
    ring_pos = {a: pos for pos, a in enumerate(sorted(ring))}

    for a in sorted(ring):
        for n in graph.get_neighbors(a):
            if n in ring_set or graph.atoms[n].atomic_number == 1:
                continue
            z = graph.atoms[n].atomic_number
            if z in HALOGEN_NAMES:
                substituents.append((ring_pos[a] + 1, HALOGEN_NAMES[z], 1))
            elif z == 8:
                # hydroxyl (with H) or unsupported ether/ether-like O
                if any(graph.atoms[nn].atomic_number == 1 for nn in graph.get_neighbors(n)):
                    substituents.append((ring_pos[a] + 1, "hydroxy", 1))
                else:
                    raise UnsupportedNamingError("aromatic ethers are outside naming coverage")
            elif z == 7:
                if _is_nitro_nitrogen(graph, n):
                    substituents.append((ring_pos[a] + 1, "nitro", 1))
                else:
                    substituents.append((ring_pos[a] + 1, "amino", 1))
            elif z == 6:
                branch_len = _branch_is_pure_hydrocarbon(graph, n, ring_set)
                if branch_len is None:
                    raise UnsupportedNamingError(
                        "aromatic rings with carbonyl/side-chain heteroatom substituents are outside naming coverage"
                    )
                sub_name = SUBSTITUENT_NAMES.get(branch_len)
                if sub_name is None:
                    raise UnsupportedNamingError(f"alkyl substituent of length {branch_len} is outside naming coverage")
                substituents.append((ring_pos[a] + 1, sub_name, 1))
            else:
                raise UnsupportedNamingError("substituent element is outside naming coverage")

    if is_aromatic_ring and ring_atom_types == {6}:
        if other_rings or (outside_atoms and not substituents):
            raise UnsupportedNamingError("fused/bridged aromatic systems are outside naming coverage")
        if groups.get("carboxyl") or groups.get("ester") or groups.get("amide") \
                or groups.get("nitrile") or groups.get("aldehyde") or groups.get("carbonyl"):
            raise UnsupportedNamingError(
                "aromatic rings with carbonyl/nitrile groups are outside naming coverage"
            )
        if not substituents:
            # benzene (or an aromatic ring of another size — unsupported)
            if ring_size == 6:
                return "benzene"
            raise UnsupportedNamingError(f"aromatic ring of size {ring_size} is outside naming coverage")
        # Renumber the ring (all rotations x both directions) to give the
        # lowest sorted locant set, fixing substitution position 1.
        def rotate(subs: list[tuple[int, str, int]], k: int, mirror: bool) -> list[tuple[int, str, int]]:
            out = []
            for pos, name, count in subs:
                p = pos if pos <= ring_size else pos
                p = ((p - 1 + k) % ring_size) + 1
                if mirror:
                    p = ((1 - p) % ring_size) + 1
                out.append((p, name, count))
            return out

        best: list[tuple[int, str, int]] | None = None
        best_key: tuple[int, ...] | None = None
        for mirror in (False, True):
            for k in range(ring_size):
                candidate = rotate(substituents, k, mirror)
                key = tuple(sorted(pos for pos, _, _ in candidate))
                if best_key is None or key < best_key:
                    best_key = key
                    best = candidate
        chosen = best or substituents
        locs = sorted(pos for pos, _, _ in chosen)
        prefix = _format_substituent_prefix(chosen)
        name_body = prefix + "benzene"
        # phenol special case: hydroxy takes priority as suffix
        hydroxy = [pos for pos, name, _ in chosen if name == "hydroxy"]
        if hydroxy and len(hydroxy) == 1:
            others = [(pos, name, count) for pos, name, count in chosen if name != "hydroxy"]
            oh_pos = hydroxy[0]
            # renumber so that OH is position 1
            def renum(pos: int) -> int:
                return ((pos - oh_pos) % ring_size) + 1
            renumbered = [(renum(pos), name, count) for pos, name, count in others]
            if not renumbered:
                return "phenol"
            prefix2 = _format_substituent_prefix(renumbered)
            return prefix2 + "phenol"
        return name_body

    # ── Heterocycle (unsubstituted common names) ──
    if ring_atom_types != {6}:
        if substituents or other_rings or outside_atoms:
            raise UnsupportedNamingError("substituted heterocycles are outside naming coverage")
        het_counts: dict[int, int] = {}
        for a in ring:
            z = atom_types[a]
            if z != 6:
                het_counts[z] = het_counts.get(z, 0) + 1
        het_key = (ring_size, frozenset(het_counts.items()))
        name = HETEROCYCLE_NAMES.get(het_key)
        if name is not None:
            return name
        raise UnsupportedNamingError(
            f"heterocycle with composition {dict(het_counts)} is outside naming coverage"
        )

    # ── Saturated cycloalkane with simple substituents ──
    if ring_atom_types == {6} and not is_aromatic_ring:
        if other_rings:
            raise UnsupportedNamingError("fused/bridged ring systems are outside naming coverage")
        if groups.get("carboxyl") or groups.get("ester") or groups.get("amide") \
                or groups.get("nitrile") or groups.get("aldehyde") or groups.get("carbonyl"):
            raise UnsupportedNamingError("cycloalkanes with those functional groups are outside naming coverage")
        # Hydroxyl / amine become the principal suffix (cyclohexanol,
        # 2-methylcyclohexan-1-ol, cyclohexanamine).
        suffix: str | None = None
        if groups.get("hydroxyl"):
            if len(groups["hydroxyl"]) > 1:
                raise UnsupportedNamingError("poly-ol cycloalkanes are outside naming coverage")
            suffix = "ol"
        elif groups.get("amine"):
            if len(groups["amine"]) > 1:
                raise UnsupportedNamingError("diamino cycloalkanes are outside naming coverage")
            suffix = "amine"
        stem = _stem_for(ring_size)
        if suffix is not None:
            # Number from the suffix-bearing carbon (position 1); remaining
            # substituents renumber relative to it.
            suffix_pos: int | None = None
            if suffix == "ol":
                for pos, name, _ in substituents:
                    if name == "hydroxy":
                        suffix_pos = pos
                        break
            else:
                for pos, name, _ in substituents:
                    if name == "amino":
                        suffix_pos = pos
                        break
            if suffix_pos is None:
                raise UnsupportedNamingError("ring suffix atom not found in coverage")
            rest = [(p, n, c) for p, n, c in substituents if p != suffix_pos]

            def rotate_from(subs: list[tuple[int, str, int]], start: int) -> list[tuple[int, str, int]]:
                return [(((p - start) % ring_size) + 1, n, c) for p, n, c in subs]

            options = []
            for offset in range(ring_size):
                options.append(sorted(rotate_from(rest, (suffix_pos + offset) % ring_size)))
                mirrored = [((ring_size + 1 - p) % ring_size, n, c) for p, n, c in rest]
                options.append(sorted(rotate_from(mirrored, (suffix_pos + offset) % ring_size)))
            best = min(options, key=lambda subs: tuple(sorted(p for p, _, _ in subs)))
            prefix = _format_substituent_prefix(best) if best else ""
            if best:
                return f"{prefix}cyclo{stem}an-1-{suffix}"
            # Unambiguous single suffix: cyclohexanol / cyclohexanamine.
            return f"cyclo{stem}an{'ol' if suffix == 'ol' else 'amine'}"
        if not substituents:
            return "cyclo" + stem + "ane"
        # Number the ring: start at a substituent, direction minimizing locants
        positions = sorted({pos for pos, _, _ in substituents})
        # Try both orientations and rotations starting from first substituent
        def rotate_from(subs: list[tuple[int, str, int]], start: int) -> list[tuple[int, str, int]]:
            return [(((pos - start) % ring_size) + 1, name, count) for pos, name, count in subs]
        options = []
        for start in positions:
            options.append(sorted(rotate_from(substituents, start)))
            mirrored = [((ring_size + 1 - pos) % ring_size or ring_size, name, count)
                        for pos, name, count in substituents]
            options.append(sorted(rotate_from(mirrored, start)))
        best = min(options, key=lambda subs: tuple(sorted(pos for pos, _, _ in subs)))
        prefix = _format_substituent_prefix(best)
        return prefix + "cyclo" + stem + "ane"

    raise UnsupportedNamingError("ring system is outside naming coverage")


# ── Hydrocarbon naming ──

def _name_hydrocarbon(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name an acyclic hydrocarbon (alkane, alkene, alkyne) with locants."""
    chains = _all_carbon_chains(graph)
    if not chains:
        return "unknown"
    n_doubles = len(set(groups.get("alkene", [])))
    n_triples = len(set(groups.get("alkyne", [])))
    chain = _choose_hydrocarbon_chain(graph, chains, n_doubles, n_triples)
    chain_len = len(chain)
    stem = _stem_for(chain_len)

    # Orient chain to minimize unsaturation locants
    chain = _orient_for_locants(chain, lambda c: _unsaturation_locants(graph, c))
    locants = _unsaturation_locants(graph, chain)

    has_double = n_doubles > 0
    has_triple = n_triples > 0

    if has_double and has_triple:
        if n_doubles > 1 or n_triples > 1:
            raise UnsupportedNamingError("poly-en-yne naming is outside naming coverage")
        d_loc = locants[0] if locants else 1
        # ene locant vs yne locant: find separately
        ene_loc, yne_loc = _ene_yne_locants(graph, chain)
        return f"{stem}-{ene_loc}-en-{yne_loc}-yne"
    if has_double:
        if n_doubles == 1:
            loc = locants[0] if locants else 1
            return f"{stem}-{loc}-ene"
        if n_doubles > 3:
            raise UnsupportedNamingError("polyenes beyond trienes are outside naming coverage")
        stem2 = stem if stem.endswith("a") else stem + "a"
        loc_str = ",".join(str(l) for l in locants)
        suffix = "diene" if n_doubles == 2 else "triene"
        return f"{stem2}-{loc_str}-{suffix}"
    if has_triple:
        if n_triples == 1:
            loc = locants[0] if locants else 1
            return f"{stem}-{loc}-yne"
        if n_triples > 3:
            raise UnsupportedNamingError("polyynes beyond triynes are outside naming coverage")
        stem2 = stem if stem.endswith("a") else stem + "a"
        loc_str = ",".join(str(l) for l in locants)
        suffix = "diyne" if n_triples == 2 else "triyne"
        return f"{stem2}-{loc_str}-{suffix}"

    # Alkane: substituents. Orient the chain to minimize substituent
    # locants (2,3-dimethylpentane, never 3,4-).
    chain = _orient_for_locants(
        chain,
        lambda c: tuple(sorted(s[0] for s in _find_substituents(graph, c))),
    )
    substituents = _find_substituents(graph, chain)
    name = stem + "ane"
    if substituents:
        prefix = _format_substituent_prefix(substituents)
        name = prefix + name
    return name


def _ene_yne_locants(graph: MolecularGraph, chain: list[int]) -> tuple[int, int]:
    """Locants of the single double and single triple bond in a chain."""
    chain_set = set(chain)
    ene = yne = 0
    for pos, i in enumerate(chain):
        for n in graph.get_neighbors(i):
            if n in chain_set and n > i:
                bond = graph.get_bond(i, n)
                if bond is None or bond.is_aromatic:
                    continue
                if bond.order == BondOrder.DOUBLE:
                    ene = pos + 1
                elif bond.order == BondOrder.TRIPLE:
                    yne = pos + 1
    return ene or 1, yne or 1


def _find_substituents(
    graph: MolecularGraph,
    chain: list[int],
    exclude_atoms: set[int] | None = None,
) -> list[tuple[int, str, int]]:
    """Find substituents on the main chain (halogens, alkyl, hydroxy, amino)."""
    chain_set = set(chain)
    if exclude_atoms:
        chain_set |= exclude_atoms

    substituents: list[tuple[int, str, int]] = []

    for i, chain_atom in enumerate(chain):
        if exclude_atoms and chain_atom in exclude_atoms:
            continue
        for neighbor in graph.get_neighbors(chain_atom):
            if neighbor in chain_set:
                continue
            atom = graph.atoms[neighbor]
            z = atom.atomic_number
            if z == 1:
                continue
            pos = i + 1
            if z in HALOGEN_NAMES:
                substituents.append((pos, HALOGEN_NAMES[z], 1))
            elif z == 6:
                branch_len = _branch_is_pure_hydrocarbon(graph, neighbor, chain_set)
                if branch_len is None:
                    raise UnsupportedNamingError("branched substituent with heteroatoms is outside naming coverage")
                sub_name = SUBSTITUENT_NAMES.get(branch_len)
                if sub_name is None:
                    raise UnsupportedNamingError(f"alkyl substituent of length {branch_len} is outside naming coverage")
                substituents.append((pos, sub_name, 1))
            elif z == 8:
                # O-H is a hydroxy prefix; O without H is an ether linkage
                if any(graph.atoms[nn].atomic_number == 1 for nn in graph.get_neighbors(neighbor)):
                    substituents.append((pos, "hydroxy", 1))
                else:
                    raise UnsupportedNamingError("ethers are outside naming coverage")
            elif z == 7:
                if _is_nitro_nitrogen(graph, neighbor):
                    substituents.append((pos, "nitro", 1))
                elif any(graph.atoms[nn].atomic_number == 1 for nn in graph.get_neighbors(neighbor)):
                    substituents.append((pos, "amino", 1))
                else:
                    raise UnsupportedNamingError("non-amino nitrogen prefixes are outside naming coverage")
            elif z == 16:
                substituents.append((pos, "thio", 1))
            else:
                raise UnsupportedNamingError("substituent element is outside naming coverage")

    return substituents


def _hydrocarbon_branch_chain(graph: MolecularGraph, start: int, excluded: set[int]) -> list[int]:
    """Longest pure-hydrocarbon chain within a branch rooted at ``start``.

    The molecule is acyclic, so the branch is a tree and the longest
    path is its diameter (double DFS from an arbitrary root).
    """
    branch: set[int] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in branch or node in excluded:
            continue
        z = graph.atoms[node].atomic_number
        if z == 1:
            continue
        if z != 6:
            continue
        branch.add(node)
        stack.extend(graph.get_neighbors(node))
    if not branch:
        return []
    # diameter of the branch tree
    def farthest(src: int) -> tuple[int, list[int]]:
        best = (0, [src])
        def dfs(cur: int, path: list[int]) -> None:
            nonlocal best
            if len(path) > best[0]:
                best = (len(path), list(path))
            for n in graph.get_neighbors(cur):
                if n in branch and n not in path:
                    path.append(n)
                    dfs(n, path)
                    path.pop()
        dfs(src, [src])
        return best
    any_node = next(iter(branch))
    _, far_path = farthest(any_node)
    _, diameter = farthest(far_path[-1])
    return diameter


# ── Functional-group naming (acyclic) ──

def _chains_containing(graph: MolecularGraph, required: set[int]) -> list[list[int]]:
    """All carbon chains that contain every required atom."""
    chains = _all_carbon_chains(graph)
    return [c for c in chains if required <= set(c)]


def _best_oriented(
    chain: list[int],
    locant_fn: Callable[[list[int]], tuple[int, ...]],
) -> tuple[list[int], tuple[int, ...]]:
    """Orient a chain to minimize locants; return (chain, locants)."""
    forward = _orient_for_locants(chain, locant_fn)
    return forward, locant_fn(forward)


def _name_alcohol(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name an alcohol: ``butan-1-ol``, ``2-methylbutan-1-ol``."""
    oh_atoms = groups["hydroxyl"]
    oh_carbons: set[int] = set()
    for oh in oh_atoms:
        for n in graph.get_neighbors(oh):
            if graph.atoms[n].atomic_number == 6:
                oh_carbons.add(n)

    def oh_locants(chain: list[int]) -> tuple[int, ...]:
        return tuple(sorted(chain.index(c) + 1 for c in oh_carbons if c in chain))

    chains = [c for c in _chains_containing(graph, oh_carbons) if oh_carbons <= set(c)]
    if not chains:
        raise UnsupportedNamingError("hydroxyl outside the main chain is outside naming coverage")
    chain = min(chains, key=lambda c: (-len(c), oh_locants(_orient_for_locants(c, oh_locants))))
    chain, locs = _best_oriented(chain, oh_locants)
    stem = _stem_for(len(chain))

    # Off-chain substituents (e.g. the methyl in 2-methylbutan-1-ol); the
    # hydroxyl oxygens themselves are excluded from the substituent scan.
    substituents = _find_substituents(graph, chain, exclude_atoms=set(oh_atoms))
    prefix = _format_substituent_prefix(substituents) if substituents else ""

    n_oh = len(oh_atoms)
    if n_oh == 1:
        return f"{prefix}{stem}an-{locs[0]}-ol"
    loc_str = ",".join(str(l) for l in locs)
    return f"{prefix}{stem}ane-{loc_str}-{MULTI_PREFIXES.get(n_oh, str(n_oh))}ol"


def _name_aldehyde(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name an aldehyde: ``propanal``, ``butanedial``."""
    ald_atoms = set(groups["aldehyde"])
    chains = _chains_containing(graph, ald_atoms)
    if not chains or len(ald_atoms) > 2:
        raise UnsupportedNamingError("aldehyde arrangement is outside naming coverage")

    stem = None
    if len(ald_atoms) == 1:
        chain = max(chains, key=len)
        stem = _stem_for(len(chain))
        substituents = _find_substituents(graph, chain, exclude_atoms=ald_atoms)
        prefix = _format_substituent_prefix(substituents)
        return prefix + stem + "anal"
    # dialdehyde
    chain = min(chains, key=lambda c: (-len(c), _ald_locs(graph, c, ald_atoms)))
    stem = _stem_for(len(chain))
    return stem + "anedial"


def _ald_locs(graph: MolecularGraph, chain: list[int], ald: set[int]) -> tuple[int, ...]:
    return tuple(sorted(chain.index(a) + 1 for a in ald))


def _name_ketone(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name a ketone: ``propan-2-one``, ``pentane-2,4-dione``."""
    carbonyl = set(groups["carbonyl"])
    chains = _chains_containing(graph, carbonyl)
    if not chains:
        raise UnsupportedNamingError("ketone outside the main chain is outside naming coverage")

    def k_locs(chain: list[int]) -> tuple[int, ...]:
        return tuple(sorted(chain.index(c) + 1 for c in carbonyl))

    chain = min(chains, key=lambda c: (-len(c), k_locs(_orient_for_locants(c, k_locs))))
    chain, locs = _best_oriented(chain, k_locs)
    stem = _stem_for(len(chain))
    substituents = _find_substituents(graph, chain, exclude_atoms=carbonyl)
    prefix = _format_substituent_prefix(substituents)
    if len(carbonyl) == 1:
        return f"{prefix}{stem}an-{locs[0]}-one"
    loc_str = ",".join(str(l) for l in locs)
    return f"{prefix}{stem}ane-{loc_str}-dione"


def _name_carboxylic_acid(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name a carboxylic acid: ``propanoic acid``, ``2-methylbutanoic acid``."""
    carboxyl = set(groups["carboxyl"])
    if len(carboxyl) > 1:
        raise UnsupportedNamingError("diacids are outside naming coverage")
    c_atom = next(iter(carboxyl))
    chains = _chains_containing(graph, carboxyl)
    if not chains:
        raise UnsupportedNamingError("carboxyl group arrangement is outside naming coverage")
    # carboxyl carbon must be a chain endpoint
    chains = [c for c in chains if c[0] == c_atom or c[-1] == c_atom]
    if not chains:
        raise UnsupportedNamingError("carboxyl group arrangement is outside naming coverage")
    chain = max(chains, key=len)
    stem = _stem_for(len(chain))
    substituents = _find_substituents(graph, chain, exclude_atoms=carboxyl)
    prefix = _format_substituent_prefix(substituents)
    return prefix + stem + "anoic acid"


def _name_ester(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name an ester: ``ethyl ethanoate``, ``methyl propanoate``."""
    ester_carbons = set(groups["ester"])
    if len(ester_carbons) > 1:
        raise UnsupportedNamingError("polyesters are outside naming coverage")
    c_atom = next(iter(ester_carbons))
    # alkoxy carbon: C neighbor of the single-bonded O
    alkoxy_carbon = None
    for n in graph.get_neighbors(c_atom):
        bond = graph.get_bond(c_atom, n)
        if (
            bond is not None
            and bond.order == BondOrder.SINGLE
            and graph.atoms[n].atomic_number == 8
        ):
            for nn in graph.get_neighbors(n):
                if graph.atoms[nn].atomic_number == 6 and nn != c_atom:
                    alkoxy_carbon = nn
                    break
    if alkoxy_carbon is None:
        raise UnsupportedNamingError("ester arrangement is outside naming coverage")

    # alkyl part: branch from the alkoxy carbon (excluding the ester O)
    ester_o = next(
        n for n in graph.get_neighbors(alkoxy_carbon)
        if graph.atoms[n].atomic_number == 8
        and (b := graph.get_bond(alkoxy_carbon, n)) is not None
        and b.order == BondOrder.SINGLE
    )
    branch_len = _branch_is_pure_hydrocarbon(graph, alkoxy_carbon, {ester_o})
    if branch_len is None:
        raise UnsupportedNamingError("ester alkyl group with heteroatoms is outside naming coverage")
    alkyl = SUBSTITUENT_NAMES.get(branch_len)
    if alkyl is None:
        raise UnsupportedNamingError(f"ester alkyl group of length {branch_len} is outside naming coverage")

    # acyl part: longest chain through the ester carbon
    chains = _all_carbon_chains(graph)
    acyl_chains = [c for c in chains if c_atom in c]
    if not acyl_chains:
        raise UnsupportedNamingError("ester arrangement is outside naming coverage")
    chain = max(acyl_chains, key=len)
    stem = _stem_for(len(chain))
    substituents = _find_substituents(graph, chain, exclude_atoms={c_atom})
    prefix = _format_substituent_prefix(substituents)
    return f"{alkyl} {prefix}{stem}anoate"


def _name_amide(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name an amide: ``propanamide``, ``N-methylpropanamide``."""
    amide_carbons = set(groups["amide"])
    if len(amide_carbons) > 1:
        raise UnsupportedNamingError("diamides are outside naming coverage")
    c_atom = next(iter(amide_carbons))

    # N-substituents: carbon branches on the amide N
    n_substituents: list[str] = []
    for n in graph.get_neighbors(c_atom):
        bond = graph.get_bond(c_atom, n)
        if (
            bond is not None
            and bond.order == BondOrder.SINGLE
            and graph.atoms[n].atomic_number == 7
        ):
            amide_n = n
            for nn in graph.get_neighbors(amide_n):
                if graph.atoms[nn].atomic_number == 6 and nn != c_atom:
                    branch_len = _branch_is_pure_hydrocarbon(graph, nn, {amide_n})
                    if branch_len is None:
                        raise UnsupportedNamingError("amide N-substituent with heteroatoms is outside naming coverage")
                    name = SUBSTITUENT_NAMES.get(branch_len)
                    if name is None:
                        raise UnsupportedNamingError(f"N-substituent of length {branch_len} is outside naming coverage")
                    n_substituents.append(name)
    n_part = ""
    if n_substituents:
        grouped: dict[str, int] = {}
        for name in n_substituents:
            grouped[name] = grouped.get(name, 0) + 1
        parts = []
        for name in sorted(grouped):
            count = grouped[name]
            if count == 1:
                parts.append(f"N-{name}")
            else:
                prefix = MULTI_PREFIXES.get(count, f"({count}-)")
                parts.append(f"N,N-{prefix}{name}")
        n_part = "-".join(parts)

    chains = _all_carbon_chains(graph)
    acyl_chains = [c for c in chains if c_atom in c]
    if not acyl_chains:
        raise UnsupportedNamingError("amide arrangement is outside naming coverage")
    chain = max(acyl_chains, key=len)
    stem = _stem_for(len(chain))
    substituents = _find_substituents(graph, chain, exclude_atoms=amide_carbons)
    prefix = _format_substituent_prefix(substituents)
    return f"{n_part}{prefix}{stem}anamide"


def _name_nitrile(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name a nitrile: ``propanenitrile`` (nitrile C counts as chain C)."""
    nitrile_n = set(groups["nitrile"])
    if len(nitrile_n) > 1:
        raise UnsupportedNamingError("dinitriles are outside naming coverage")
    n_atom = next(iter(nitrile_n))
    nitrile_c = next(
        n for n in graph.get_neighbors(n_atom)
        if graph.atoms[n].atomic_number == 6
    )
    chains = _all_carbon_chains(graph)
    acyl_chains = [c for c in chains if nitrile_c in c]
    if not acyl_chains:
        raise UnsupportedNamingError("nitrile arrangement is outside naming coverage")
    chain = max(acyl_chains, key=len)
    stem = _stem_for(len(chain))
    substituents = _find_substituents(graph, chain, exclude_atoms={nitrile_c})
    prefix = _format_substituent_prefix(substituents)
    return f"{prefix}{stem}anenitrile"


def _name_amine(graph: MolecularGraph, groups: dict[str, list[int]]) -> str:
    """Name an amine: ``ethan-1-amine``, ``N-methylmethanamine``."""
    amine_atoms = set(groups["amine"])
    if len(amine_atoms) > 1:
        raise UnsupportedNamingError("diamines are outside naming coverage")
    a_atom = next(iter(amine_atoms))

    # Carbon attachments of the amine N
    carbons = [
        n for n in graph.get_neighbors(a_atom)
        if graph.atoms[n].atomic_number == 6
    ]
    if not carbons:
        raise UnsupportedNamingError("amine without carbon attachment is outside naming coverage")
    if len(carbons) > 2:
        raise UnsupportedNamingError("tertiary amines are outside naming coverage")

    if len(carbons) == 2:
        # Secondary amine R-NH-R': each side is a separate hydrocarbon
        # branch (the N breaks the carbon chain); smaller side = N-prefix.
        side_a = _hydrocarbon_branch_chain(graph, carbons[0], {a_atom})
        side_b = _hydrocarbon_branch_chain(graph, carbons[1], {a_atom})
        if not side_a or not side_b:
            raise UnsupportedNamingError("amine arrangement is outside naming coverage")
        main, sub = (side_a, side_b) if len(side_a) >= len(side_b) else (side_b, side_a)
        sub_name = SUBSTITUENT_NAMES.get(len(sub))
        if sub_name is None:
            raise UnsupportedNamingError(f"N-substituent of length {len(sub)} is outside naming coverage")
        stem = _stem_for(len(main))
        main_c = carbons[0] if carbons[0] in main else carbons[1]
        loc = main.index(main_c) + 1
        return f"N-{sub_name}{stem}an-{loc}-amine"

    # Primary amine R-NH2
    c_atom = carbons[0]
    chains = [c for c in _all_carbon_chains(graph) if c_atom in c]
    if not chains:
        raise UnsupportedNamingError("amine arrangement is outside naming coverage")
    chain = max(chains, key=len)

    def amine_loc(chain: list[int]) -> tuple[int, ...]:
        return (chain.index(c_atom) + 1,)

    chain = _orient_for_locants(chain, amine_loc)
    stem = _stem_for(len(chain))
    # The principal amine N must not be re-counted as an 'amino' prefix.
    substituents = _find_substituents(graph, chain, exclude_atoms={a_atom})
    prefix = _format_substituent_prefix(substituents)
    loc = chain.index(c_atom) + 1
    return f"{prefix}{stem}an-{loc}-amine"
