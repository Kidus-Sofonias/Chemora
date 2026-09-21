"""ReactionGraph and deterministic atom-atom mapping (M33, roadmap 12.2).

A :class:`ReactionGraph` pairs a :class:`~chemengine.reactions.reaction.Reaction`
with an explicit atom correspondence between its reactant and product graphs.
The correspondence is computed by :func:`map_reaction`.

Why a dedicated search (not the generic MCS engine)?
---------------------------------------------------
Reaction atom mapping differs from substructure search in two essential ways:

1. **Bond orders are the signal, not a constraint.** A mapping that requires
   identical bond orders can never cross the very bond changes a reaction
   describes. The correspondence here is therefore *skeleton-based*: element
   equality plus bond *existence*, with bond-order differences reported as
   changed/formed/broken bonds.
2. **The pairing itself is the result.** The generic MCS engine returns two
   index sets; the reactant→product pairing is the output here, so the search
   below tracks the mapping dict directly.

Determinism and symmetry
------------------------
Seeds and candidates are explored in ascending index order and the best
mapping is only replaced by a strictly larger one, so the result is a stable
function of the input graphs — never random. When multiple distinct maximal
mappings of equal size exist (a genuinely symmetric correspondence, e.g. a
reversible chain orientation), :func:`map_reaction` returns the canonical
(index-ordered) mapping and sets ``ambiguous=True`` rather than hiding the
choice.

Coverage boundary (honest)
--------------------------
- Heavy atoms only; hydrogens are outside the correspondence (elemental
  balance remains verifiable through :meth:`Reaction.is_balanced`).
- A single :class:`~chemengine.reactions.reaction.ReactionComponent` per side
  (a ``.``-separated multi-fragment graph counts as one component and is
  supported — unmapped fragments surface as lost/gained atoms).
- The search is bounded at 20 heavy atoms per side (same bound as the
  substructure engine; MCS is NP-hard). Larger inputs fail explicitly with a
  reason, never silently.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any

from chemengine.core.graph import MolecularGraph
from chemengine.reactions.reaction import Reaction

__all__ = [
    "AtomRole",
    "MappedAtom",
    "ReactionGraph",
    "MappingResult",
    "map_reaction",
]

# Same engine bound as chemengine.detection.substructure: MCS is NP-hard and
# the exhaustive search below is only tractable — and only intended — for
# small reaction partners.
MAX_HEAVY_ATOMS = 20
# Deterministic work budget: node expansions across both the primary search
# and the ambiguity probe. The count is a pure function of the input graphs,
# so exceeding it is reproducible; when it happens the mapping fails
# explicitly instead of hanging or returning an unexplored result.
MAX_SEARCH_NODES = 200_000


# ── Atom roles ──

class AtomRole:
    """Classification of a heavy atom's fate across the reaction.

    Attributes:
        MAPPED: atom persists from reactant side to product side.
        LOST: atom exists only on the reactant side.
        GAINED: atom exists only on the product side.
    """

    MAPPED = "mapped"
    LOST = "lost"
    GAINED = "gained"


@dataclass(frozen=True, slots=True)
class MappedAtom:
    """One heavy atom's correspondence across the reaction.

    Attributes:
        reactant_index: Index into the reactant atom tuple, or ``None`` for
            gained atoms.
        product_index: Index into the product atom tuple, or ``None`` for
            lost atoms.
        atomic_number: Element of the atom (identical on both sides for
            mapped atoms).
        role: One of :class:`AtomRole`.
    """

    reactant_index: int | None
    product_index: int | None
    atomic_number: int
    role: str


# ── ReactionGraph ──

@dataclass(frozen=True, slots=True)
class ReactionGraph:
    """A reaction plus its explicit atom correspondence.

    Attributes:
        reaction: The underlying reaction.
        atoms: One :class:`MappedAtom` per heavy atom (reactant-side atoms
            first, then gained product-side atoms).
        changed_bonds: Bonds whose order changed, as tuples
            ``(reactant_a, reactant_b, old_order, new_order)`` with numeric
            orders (1=single, 2=double, 3=triple, 4=quadruple; 0 means the
            bond did not exist on that side).
        formed_bonds: Reactant-side mapped pairs bonded in the product but
            not the reactant.
        broken_bonds: Reactant-side mapped pairs bonded in the reactant but
            not the product.
    """

    reaction: Reaction
    atoms: tuple[MappedAtom, ...]
    changed_bonds: tuple[tuple[int, int, int, int], ...] = ()
    formed_bonds: tuple[tuple[int, int], ...] = ()
    broken_bonds: tuple[tuple[int, int], ...] = ()

    # -- queries ---------------------------------------------------------

    def mapped_atoms(self) -> tuple[MappedAtom, ...]:
        """Atoms present on both sides."""
        return tuple(a for a in self.atoms if a.role == AtomRole.MAPPED)

    def lost_atoms(self) -> tuple[MappedAtom, ...]:
        """Heavy atoms that exist only on the reactant side."""
        return tuple(a for a in self.atoms if a.role == AtomRole.LOST)

    def gained_atoms(self) -> tuple[MappedAtom, ...]:
        """Heavy atoms that exist only on the product side."""
        return tuple(a for a in self.atoms if a.role == AtomRole.GAINED)

    def reactant_to_product(self) -> dict[int, int]:
        """Dict of reactant atom index → product atom index (mapped only)."""
        return {
            a.reactant_index: a.product_index  # type: ignore[misc]
            for a in self.mapped_atoms()
        }

    def num_changed_bonds(self) -> int:
        """Number of bonds whose order changed between the sides."""
        return len(self.changed_bonds)

    def is_consistent(self) -> bool:
        """Sanity check: mapped indices exist on their respective graphs."""
        reactant = self.reaction.reactants[0].molecule
        product = self.reaction.products[0].molecule
        for a in self.atoms:
            if a.role == AtomRole.MAPPED:
                if a.reactant_index is None or a.product_index is None:
                    return False
                if a.reactant_index >= reactant.num_atoms:
                    return False
                if a.product_index >= product.num_atoms:
                    return False
                if (
                    reactant.atoms[a.reactant_index].atomic_number
                    != product.atoms[a.product_index].atomic_number
                ):
                    return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph (indices and roles only, no molecule blobs)."""
        return {
            "atoms": [
                {
                    "reactant_index": a.reactant_index,
                    "product_index": a.product_index,
                    "atomic_number": a.atomic_number,
                    "role": a.role,
                }
                for a in self.atoms
            ],
            "changed_bonds": [list(b) for b in self.changed_bonds],
            "formed_bonds": [list(b) for b in self.formed_bonds],
            "broken_bonds": [list(b) for b in self.broken_bonds],
            "num_mapped": len(self.mapped_atoms()),
            "num_lost": len(self.lost_atoms()),
            "num_gained": len(self.gained_atoms()),
        }


# ── Mapping result ──

@dataclass(frozen=True, slots=True)
class MappingResult:
    """Outcome of :func:`map_reaction`.

    Attributes:
        graph: The constructed ReactionGraph, or ``None`` if mapping failed.
        ambiguous: True when multiple distinct maximal mappings of equal
            size exist. The returned graph uses the canonical index-ordered
            mapping, but symmetric atom pairs are interchangeable.
        reason: Human-readable explanation when ``graph`` is ``None``.
    """

    graph: ReactionGraph | None = None
    ambiguous: bool = False
    reason: str = ""

    @property
    def ok(self) -> bool:
        """Whether a ReactionGraph was produced."""
        return self.graph is not None


# ── Core mapping ──

def _bond_value(graph: MolecularGraph, i: int, j: int) -> int:
    """Numeric bond order between two atoms (0 if no bond).

    ``BondOrder`` is an ``IntEnum`` (SINGLE=1 … QUADRUPLE=4); AROMATIC (5)
    normalizes to 1 because aromatic bond orders are resolved by kekulization
    upstream, and mapping compares only existence here anyway.
    """
    bond = graph.get_bond(i, j)
    if bond is None:
        return 0
    order = int(bond.order)
    return order if 1 <= order <= 4 else 1


def _heavy_atoms(graph: MolecularGraph) -> list[int]:
    """Indices of heavy (non-hydrogen) atoms."""
    return [i for i in range(graph.num_atoms) if graph.atoms[i].atomic_number != 1]


def _atom_signature(graph: MolecularGraph, i: int) -> tuple[int, int, tuple[int, ...]]:
    """One-hop invariant used ONLY to order the search deterministically.

    ``(element, heavy degree, sorted neighbor elements)``.

    **Not a compatibility filter.** Reaction mapping must pair atoms whose
    neighborhoods legitimately change (chlorination, epoxidation, SN2 …),
    so requiring equal signatures would make the search chemically
    unsound. Signatures order the seed/candidate loops; the actual search
    accepts any element-equal pair consistent with bond existence.
    """
    neighbors: list[int] = []
    for j in graph.get_neighbors(i):
        if graph.atoms[j].atomic_number != 1:
            neighbors.append(graph.atoms[j].atomic_number)
    neighbors.sort()
    atom = graph.atoms[i]
    return (atom.atomic_number, len(neighbors), tuple(neighbors))


class _BudgetError(Exception):
    """Internal: raised when the deterministic node budget is exhausted."""


class _FoundMaxError(Exception):
    """Internal: raised to stop all search once a maximum-size mapping exists."""


def _skeleton_mcs(
    reactant: MolecularGraph,
    product: MolecularGraph,
) -> tuple[dict[int, int], bool] | None:
    """Deterministic skeleton MCS that preserves the reactant→product pairing.

    Atom compatibility: identical element. Bond compatibility: bond
    *existence* only (orders intentionally ignored — see module docstring).

    Search control (all deterministic, all sound):
    - **Adjacency sets** — O(1) bond-existence checks via precomputed
      neighbor sets instead of linear scans.
    - **Signature ordering** — seeds and candidates are explored in
      signature order (a stable heuristic; see :func:`_atom_signature`).
    - **Global early stop** — once a mapping of the maximum possible size
      (``min(heavy_r, heavy_p)``) exists, no larger mapping is possible and
      the search ends.
    - **Branch and bound** — a partial mapping is abandoned when even a
      perfect completion cannot beat the best found so far.
    - **Node budget** — pathological inputs hit :data:`MAX_SEARCH_NODES`.

    Returns:
        ``(mapping, ambiguous)`` where ``mapping`` maps reactant indices to
        product indices, or ``None`` if either side exceeds
        :data:`MAX_HEAVY_ATOMS`.

    Ambiguity semantics: the probe detects an alternative *only if it is
    found within the budget*. On exhaustion the result is conservatively
    reported as ambiguous — never silently ambiguous-free.
    """
    heavy_r = _heavy_atoms(reactant)
    heavy_p = _heavy_atoms(product)
    if len(heavy_r) > MAX_HEAVY_ATOMS or len(heavy_p) > MAX_HEAVY_ATOMS:
        return None

    # Precomputed structure for O(1) checks and deterministic ordering.
    adj_r = {i: set(reactant.get_neighbors(i)) for i in range(reactant.num_atoms)}
    adj_p = {j: set(product.get_neighbors(j)) for j in range(product.num_atoms)}
    sig_r = {i: _atom_signature(reactant, i) for i in heavy_r}
    sig_p = {j: _atom_signature(product, j) for j in heavy_p}
    order_r = sorted(heavy_r, key=lambda i: (sig_r[i], i))
    order_p = sorted(heavy_p, key=lambda j: (sig_p[j], j))
    # Element-equal candidates in signature order — element equality IS a
    # sound constraint (any valid pair must share it); signatures only rank.
    compat_r: dict[int, list[int]] = {
        i: [j for j in order_p if product.atoms[j].atomic_number
            == reactant.atoms[i].atomic_number]
        for i in order_r
    }
    compat_p: dict[int, list[int]] = {
        j: [i for i in order_r if reactant.atoms[i].atomic_number
            == product.atoms[j].atomic_number]
        for j in order_p
    }

    best_size = 0
    best_map: dict[int, int] = {}
    nodes = 0
    max_possible = min(len(heavy_r), len(heavy_p))

    mapping: dict[int, int] = {}
    used_r: set[int] = set()
    used_p: set[int] = set()

    def _extend() -> None:
        nonlocal best_size, best_map, nodes
        nodes += 1
        if nodes > MAX_SEARCH_NODES:
            raise _BudgetError

        current = len(mapping)
        unmapped = min(
            len(heavy_r) - len(used_r), len(heavy_p) - len(used_p)
        )
        if current > best_size:
            best_size = current
            best_map = dict(mapping)
            if best_size == max_possible:
                raise _FoundMaxError
        if current + unmapped < best_size:
            return  # cannot beat the incumbent

        for a1 in order_r:
            if a1 in used_r:
                continue
            for a2 in compat_r[a1]:
                if a2 in used_p:
                    continue
                # Skeleton compatibility: bond existence must match.
                ok = True
                for m1, m2 in mapping.items():
                    b1 = m1 in adj_r[a1]
                    b2 = m2 in adj_p[a2]
                    if b1 != b2:
                        ok = False
                        break
                if not ok:
                    continue

                mapping[a1] = a2
                used_r.add(a1)
                used_p.add(a2)
                _extend()
                del mapping[a1]
                used_r.discard(a1)
                used_p.discard(a2)

    # Seed loop: every compatible (reactant, product) start pair, in index
    # order. The budget exception must abort the entire search and becomes an
    # explicit failure here: when no maximum-size mapping is ever found the
    # space cannot be pruned to certainty, so returning the best-so-far would
    # be unsound.
    try:
        for i in order_r:
            for j in compat_r[i]:
                mapping = {i: j}
                used_r = {i}
                used_p = {j}
                with contextlib.suppress(_FoundMaxError):
                    _extend()
                if best_size == max_possible:
                    break
            if best_size == max_possible:
                break
    except _BudgetError:
        return None

    if best_size == 0:
        return {}, False

    # ── Ambiguity detection ──
    #
    # **Full correspondence** (best_size == max_possible): a second maximal
    # mapping must be a *full* alternative bijection. Enumerate full
    # mappings in ONE shared backtracking tree with a fixed variable order.
    # Unlike per-seed restarts, this tree is shared across candidate
    # assignments, so symmetric molecules hit an alternative immediately and
    # asymmetric ones exhaust a heavily pruned tree in milliseconds. The
    # enumeration stops at the second distinct full mapping; budget
    # exhaustion is conservative (reported as ambiguous).
    #
    # **Partial correspondence**: the incumbent leaves atoms unmapped, so
    # alternatives may reuse the incumbent's pairs — full-mapping
    # enumeration does not apply. The forced-seed probe is used instead:
    # for each (i, j) with j != best_map[i], test whether any mapping of
    # size best_size exists that uses the forced pair.
    nodes = 0

    if best_size == max_possible:
        # Enumerate over the SMALLER side (full correspondence means every
        # atom of the smaller side is mapped); when the sides are unequal
        # the larger side's incumbent pairs are fixed and alternatives
        # permute only the smaller side's assignment.
        if len(heavy_r) <= len(heavy_p):
            vars_side = order_r
            partners = compat_r
            adj_self, adj_other = adj_r, adj_p
            forward = True
        else:
            vars_side = order_p
            partners = compat_p
            adj_self, adj_other = adj_p, adj_r
            forward = False
        found_alt = False

        def _enum() -> None:
            nonlocal nodes, found_alt
            nodes += 1
            if nodes > MAX_SEARCH_NODES:
                raise _BudgetError
            if len(mapping) == len(vars_side):
                completed = mapping if forward else {v: k for k, v in mapping.items()}
                if completed != best_map:
                    found_alt = True
                    raise _FoundMaxError  # second distinct mapping found
                return  # incumbent completed; keep searching for others
            a1 = vars_side[len(mapping)]
            for j in partners[a1]:
                if j in used_p:
                    continue
                ok = True
                for m1, m2 in mapping.items():
                    if (m1 in adj_self[a1]) != (m2 in adj_other[j]):
                        ok = False
                        break
                if not ok:
                    continue
                mapping[a1] = j
                used_p.add(j)
                _enum()
                del mapping[a1]
                used_p.discard(j)
                if found_alt:
                    raise _FoundMaxError  # propagate the early stop

        try:
            mapping = {}
            used_p = set()
            with contextlib.suppress(_FoundMaxError):
                _enum()
        except _BudgetError:
            # Enumeration incomplete: the incumbent is a valid full mapping,
            # so the size is right, but uniqueness is unproven. Conservative,
            # deterministic answer — never silently ambiguity-free.
            return best_map, True
        return best_map, found_alt

    # Partial-correspondence probe.

    def _probe_extend() -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_SEARCH_NODES:
            raise _BudgetError
        if len(mapping) >= best_size:
            raise _FoundMaxError  # a genuine alternative of maximal size
        # Same sound prune as the primary search: a branch that cannot
        # possibly reach best_size can never prove ambiguity.
        unmapped = min(
            len(heavy_r) - len(used_r), len(heavy_p) - len(used_p)
        )
        if len(mapping) + unmapped < best_size:
            return
        for a1 in order_r:
            if a1 in used_r:
                continue
            for a2 in compat_r[a1]:
                if a2 in used_p:
                    continue
                ok = True
                for m1, m2 in mapping.items():
                    b1 = m1 in adj_r[a1]
                    b2 = m2 in adj_p[a2]
                    if b1 != b2:
                        ok = False
                        break
                if not ok:
                    continue
                mapping[a1] = a2
                used_r.add(a1)
                used_p.add(a2)
                _probe_extend()
                del mapping[a1]
                used_r.discard(a1)
                used_p.discard(a2)

    ambiguous = False
    try:
        for i in order_r:
            for j in compat_r[i]:
                if j == best_map.get(i):
                    continue
                # No extra seed filter here: an alternative mapping by
                # definition pairs atoms differently than the incumbent, so
                # incumbent-consistency prechecks are unsound (they reject
                # genuine alternatives, e.g. ethane {0→1, 1→0}). The probe's
                # own pairwise checks are the only sound filter.
                mapping = {i: j}
                used_r = {i}
                used_p = {j}
                try:
                    _probe_extend()
                except _FoundMaxError:
                    ambiguous = True
                    break
            if ambiguous:
                break
    except _BudgetError:
        # Search incomplete: a smaller-than-maximal mapping was accepted and
        # an alternative may exist. Conservative, deterministic answer.
        return best_map, True

    return best_map, ambiguous


def map_reaction(
    reaction: Reaction,
    *,
    min_mapped_atoms: int = 1,
) -> MappingResult:
    """Compute the deterministic atom-atom mapping for a reaction.

    Maps the first reactant component to the first product component
    (skeleton-based; see module docstring). Reactant heavy atoms without a
    product counterpart are classified as lost; product heavy atoms without
    a reactant counterpart as gained. Bond-order differences over mapped
    pairs are reported as changed/formed/broken bonds.

    Args:
        reaction: The reaction to map.
        min_mapped_atoms: Minimum number of atoms that must map for the
            mapping to be considered valid.

    Returns:
        A :class:`MappingResult`. ``graph`` is ``None`` with a ``reason``
        when the reaction shape is unsupported (empty sides, multiple
        components on a side, oversized partners, or too few mappable
        atoms). Failures are explicit — the function never silently returns
        a partial or arbitrary mapping.
    """
    if not reaction.reactants or not reaction.products:
        return MappingResult(reason="reaction has an empty reactant or product side")
    if len(reaction.reactants) > 1 or len(reaction.products) > 1:
        return MappingResult(
            reason="mapping requires exactly one reactant and one product "
            "component; multi-component correspondence is not supported"
        )

    reactant = reaction.reactants[0].molecule
    product = reaction.products[0].molecule

    result = _skeleton_mcs(reactant, product)
    if result is None:
        if (
            len(_heavy_atoms(reactant)) > MAX_HEAVY_ATOMS
            or len(_heavy_atoms(product)) > MAX_HEAVY_ATOMS
        ):
            return MappingResult(
                reason=f"reaction partner exceeds {MAX_HEAVY_ATOMS} heavy "
                "atoms on a side"
            )
        return MappingResult(
            reason="deterministic search budget exhausted before a provably "
            "maximal mapping was found; reduce the reaction size or symmetry"
        )
    r_to_p, ambiguous = result

    if len(r_to_p) < min_mapped_atoms:
        return MappingResult(
            reason=f"fewer than {min_mapped_atoms} atoms map between reactant and product"
        )

    # Build the atom correspondence.
    entries: list[MappedAtom] = []
    for ri in range(reactant.num_atoms):
        atom = reactant.atoms[ri]
        if atom.atomic_number == 1:
            continue  # hydrogens are outside the mapping scope
        if ri in r_to_p:
            entries.append(
                MappedAtom(ri, r_to_p[ri], atom.atomic_number, AtomRole.MAPPED)
            )
        else:
            entries.append(MappedAtom(ri, None, atom.atomic_number, AtomRole.LOST))
    for pi in range(product.num_atoms):
        atom = product.atoms[pi]
        if atom.atomic_number == 1:
            continue
        if pi not in r_to_p.values():
            entries.append(MappedAtom(None, pi, atom.atomic_number, AtomRole.GAINED))

    # Bond analysis over mapped pairs only.
    mapped_pairs = sorted(r_to_p.items())
    changed: list[tuple[int, int, int, int]] = []
    formed: list[tuple[int, int]] = []
    broken: list[tuple[int, int]] = []
    for idx, (ri, pi) in enumerate(mapped_pairs):
        for rj, pj in mapped_pairs[idx + 1 :]:
            rv = _bond_value(reactant, ri, rj)
            pv = _bond_value(product, pi, pj)
            if rv == pv:
                continue
            if rv == 0:
                formed.append((ri, rj))
            elif pv == 0:
                broken.append((ri, rj))
            changed.append((ri, rj, rv, pv))

    graph = ReactionGraph(
        reaction=reaction,
        atoms=tuple(entries),
        changed_bonds=tuple(changed),
        formed_bonds=tuple(formed),
        broken_bonds=tuple(broken),
    )
    return MappingResult(graph=graph, ambiguous=ambiguous)
