"""Tautomer handling (M33 Phase 11.5).

Detects tautomeric forms and selects a canonical representative within a
strictly bounded transformation set:

- keto–enol tautomerism (ketone/aldehyde ⇄ enol)
- amide–imidic acid tautomerism (amide ⇄ imidic acid)

**Coverage boundary (honest).** Only the two classes above are recognised;
heteroatom tautomerism in rings (pyrazoles, imidazoles, porphyrins),
nitro/aci-nitro, and multi-site prototropic cascades are outside this
module. Transformations are strictly bounded: each detection pass yields at
most one enumerated partner per recognised site and
:func:`enumerate_tautomers` caps the returned set at ``max_forms`` (default
8), so pathological input cannot trigger uncontrolled expansion.

All functions are deterministic: identical input graphs produce identical
outputs. The molecular graph (SSOT) is never mutated — partners are built
through :class:`~chemengine.core.graph.MolecularGraphBuilder`.
"""

from __future__ import annotations

from dataclasses import dataclass

from chemengine.core.enums import BondOrder
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder

__all__ = [
    "TautomerType",
    "TautomerSite",
    "TautomerForm",
    "MAX_TAUTOMER_FORMS",
    "detect_tautomers",
    "enumerate_tautomers",
    "canonical_tautomer",
]

# Hard cap on enumerated forms per molecule (bounds resource use).
MAX_TAUTOMER_FORMS: int = 8


class TautomerType:
    """Recognised tautomer classes (constants, not an enum, for cheap use)."""

    KETO_ENOL = "keto-enol"
    AMIDE_IMIDIC = "amide-imidic"
    ENOL_KETO = "enol-keto"
    IMIDIC_AMIDE = "imidic-amide"


@dataclass(frozen=True)
class TautomerSite:
    """One recognised tautomeric site in a molecule."""

    tautomer_type: str
    # Atom indices participating in the transformation.
    atoms: tuple[int, ...]
    # Index of the hydrogen-bearing atom in the current form (None when the
    # site is in its de-protiated form).
    h_source: int | None


@dataclass(frozen=True)
class TautomerForm:
    """A tautomeric form: the partner graph and the transformation used."""

    tautomer_type: str
    graph: MolecularGraph


def _is_carbonyl_carbon(graph: MolecularGraph, idx: int) -> int | None:
    """Oxygen index of the C=O double bond on carbon ``idx``, else None."""
    if graph.atoms[idx].atomic_number != 6:
        return None
    for n in graph.get_neighbors(idx):
        bond = graph.get_bond(idx, n)
        if bond is None or bond.is_aromatic:
            continue
        if bond.order == BondOrder.DOUBLE and graph.atoms[n].atomic_number == 8:
            return n
    return None


def _is_enol_site(graph: MolecularGraph, idx: int) -> tuple[int, int] | None:
    """Return ``(alpha_carbon, hydroxyl_oxygen)`` for an enol carbon, else None.

    An enol carbon bears a hydroxyl and is double-bonded to another carbon:
    it is the recognisable partner of a keto site. This direction matters
    because it is what makes :func:`canonical_tautomer` tautomer-invariant --
    without it an enol and its keto form canonicalized to two different
    graphs, so the "canonical" form depended on which tautomer was supplied.
    """
    if graph.atoms[idx].atomic_number != 6:
        return None
    oxygen: int | None = None
    for n in graph.get_neighbors(idx):
        bond = graph.get_bond(idx, n)
        if bond is None or bond.is_aromatic or bond.order != BondOrder.SINGLE:
            continue
        if graph.atoms[n].atomic_number == 8 and _has_h(graph, n):
            oxygen = n
            break
    if oxygen is None:
        return None
    for n in graph.get_neighbors(idx):
        bond = graph.get_bond(idx, n)
        if bond is None or bond.is_aromatic or bond.order != BondOrder.DOUBLE:
            continue
        # No hydrogen requirement on the partner: the enol of an internal
        # ketone carries no H on the double-bonded carbon (that H moved to
        # the oxygen when the keto form was de-protiated), and the shift
        # below adds one back anyway.
        if graph.atoms[n].atomic_number == 6:
            return (n, oxygen)
    return None


def _is_imidic_site(graph: MolecularGraph, idx: int) -> tuple[int, int] | None:
    """Return ``(nitrogen, hydroxyl_oxygen)`` for an imidic carbon, else None.

    An imidic-acid carbon (``C(-OH)=N-H``) is the partner of an amide
    carbonyl (``C=O``, ``N-H``). Without this direction the amide/imidic pair
    had the same asymmetry as keto/enol: canonical_tautomer(amide) returned
    the amide while canonical_tautomer(imidic acid) returned the imidic acid.
    """
    if graph.atoms[idx].atomic_number != 6 or graph.atoms[idx].is_aromatic:
        return None
    oxygen: int | None = None
    for n in graph.get_neighbors(idx):
        bond = graph.get_bond(idx, n)
        if bond is None or bond.is_aromatic or bond.order != BondOrder.SINGLE:
            continue
        if graph.atoms[n].atomic_number == 8 and _has_h(graph, n):
            oxygen = n
            break
    if oxygen is None:
        return None
    for n in graph.get_neighbors(idx):
        bond = graph.get_bond(idx, n)
        if bond is None or bond.is_aromatic or bond.order != BondOrder.DOUBLE:
            continue
        # The nitrogen need not carry a hydrogen: N-substituted imidic acids
        # (C(-OH)=N-CH3) tautomerize to the corresponding N-substituted amide
        # by moving the hydroxyl hydrogen to the nitrogen.
        if graph.atoms[n].atomic_number == 7:
            return (n, oxygen)
    return None


def _has_h(graph: MolecularGraph, idx: int) -> bool:
    atom = graph.atoms[idx]
    if getattr(atom, "implicit_hydrogens", 0):
        return True
    return any(
        graph.atoms[n].atomic_number == 1 for n in graph.get_neighbors(idx)
    )


def _neighbours_with(graph: MolecularGraph, idx: int, z: int) -> list[int]:
    return [
        n for n in graph.get_neighbors(idx)
        if graph.atoms[n].atomic_number == z
    ]


def detect_tautomers(graph: MolecularGraph) -> list[TautomerSite]:
    """Detect recognised tautomeric sites (deterministic, atom order).

    Args:
        graph: The molecular graph (never mutated).

    Returns:
        Deterministic sites: carbonyl-directed sites first (keto-enol and
        amide-imidic, ascending carbon index), then partner-directed sites
        (enol-keto and imidic-amide, ascending carbon index). Empty when
        none.
    """
    sites: list[TautomerSite] = []
    for idx, atom in enumerate(graph.atoms):
        if atom.atomic_number != 6 or atom.is_aromatic:
            continue
        oxygen = _is_carbonyl_carbon(graph, idx)
        if oxygen is None:
            continue
        # amide–imidic takes priority: a carbonyl with an N–H neighbour is
        # an amide (its keto–enol reading is not the principal tautomer).
        amide_n = [n for n in _neighbours_with(graph, idx, 7) if _has_h(graph, n)]
        if amide_n:
            sites.append(TautomerSite(
                TautomerType.AMIDE_IMIDIC,
                atoms=(amide_n[0], idx, oxygen),
                h_source=amide_n[0],
            ))
            continue
        # keto–enol: an alpha carbon bearing H sits next to the C=O.
        alpha = [n for n in _neighbours_with(graph, idx, 6) if _has_h(graph, n)]
        if alpha:
            sites.append(TautomerSite(
                TautomerType.KETO_ENOL,
                atoms=(alpha[0], idx, oxygen),
                h_source=alpha[0],
            ))
    for idx, atom in enumerate(graph.atoms):
        if atom.atomic_number != 6 or atom.is_aromatic:
            continue
        if _is_carbonyl_carbon(graph, idx) is not None:
            continue  # the keto direction already covers this carbon
        enol = _is_enol_site(graph, idx)
        if enol is not None:
            alpha_c, oxygen = enol
            sites.append(TautomerSite(
                TautomerType.ENOL_KETO,
                atoms=(alpha_c, idx, oxygen),
                h_source=oxygen,
            ))
            continue
        imidic = _is_imidic_site(graph, idx)
        if imidic is not None:
            n_atom, oxygen = imidic
            sites.append(TautomerSite(
                TautomerType.IMIDIC_AMIDE,
                atoms=(n_atom, idx, oxygen),
                h_source=oxygen,
            ))
    return sites


def _remove_h(builder: MolecularGraphBuilder, graph: MolecularGraph, idx: int) -> None:
    """Drop one explicit hydrogen neighbour of ``idx`` (if any)."""
    for n in graph.get_neighbors(idx):
        if graph.atoms[n].atomic_number == 1:
            for j, bond in enumerate(builder._bonds):
                if {bond.atom1, bond.atom2} == {idx, n}:
                    builder.remove_bond(j)
                    break
            builder._atoms = [
                a for i, a in enumerate(builder._atoms) if i != n
            ]
            # Removing the atom shifts every index above ``n`` down by one,
            # so the remaining bonds must be re-indexed to match. Filtering
            # only ``_atoms`` left bonds pointing at shifted indices: one
            # hydrogen ended up bonded to two heavy atoms, which both gave it
            # an impossible valence of two and invented a phantom three-member
            # ring -- corrupting every tautomer partner graph built here and,
            # through ring perception, the InChI/InChIKey of those partners.
            builder._bonds = [
                type(bond)(
                    atom1=bond.atom1 if bond.atom1 < n else bond.atom1 - 1,
                    atom2=bond.atom2 if bond.atom2 < n else bond.atom2 - 1,
                    order=bond.order,
                    bond_type=bond.bond_type,
                    stereochemistry=bond.stereochemistry,
                    topology=bond.topology,
                    is_aromatic=bond.is_aromatic,
                    length=bond.length,
                    properties=bond.properties,
                )
                for bond in builder._bonds
            ]
            return


def _add_h(builder: MolecularGraphBuilder, idx: int) -> None:
    h = builder.add_atom(1)
    builder.add_bond(idx, h, BondOrder.SINGLE)


def _shift_h(
    graph: MolecularGraph,
    site: TautomerSite,
    src: int,
    dst: int,
    to_double: tuple[int, int],
    to_single: tuple[int, int],
) -> MolecularGraph:
    """Build the partner form: move H src→dst and swap the two bonds.

    ``to_double`` is the bond that becomes double, ``to_single`` the one
    that becomes single. Indices refer to the *input* graph.
    """
    builder = MolecularGraphBuilder.from_graph(graph)
    _remove_h(builder, graph, src)
    _add_h(builder, dst)
    _swap_bond(builder, *to_double, BondOrder.DOUBLE)
    _swap_bond(builder, *to_single, BondOrder.SINGLE)
    return builder.build()


def _swap_bond(
    builder: MolecularGraphBuilder,
    a: int,
    b: int,
    new_order: BondOrder,
) -> None:
    for j, bond in enumerate(builder._bonds):
        if {bond.atom1, bond.atom2} == {a, b}:
            builder._bonds[j] = (
                type(bond)(
                    atom1=bond.atom1, atom2=bond.atom2, order=new_order,
                    bond_type=bond.bond_type,
                    stereochemistry=bond.stereochemistry,
                    topology=bond.topology, is_aromatic=bond.is_aromatic,
                    length=bond.length, properties=bond.properties,
                )
            )
            return


def enumerate_tautomers(
    graph: MolecularGraph,
    max_forms: int = MAX_TAUTOMER_FORMS,
) -> list[TautomerForm]:
    """Enumerate recognised tautomeric partners (bounded, deterministic).

    The input graph itself is not a tautomer of anything, so it is NOT
    included in the returned list; each entry is one generated partner.
    The set is capped at ``max_forms`` (clamped to
    :data:`MAX_TAUTOMER_FORMS`) to bound resource use.

    Args:
        graph: The molecular graph (never mutated).
        max_forms: Upper bound on returned forms.

    Returns:
        Deterministic list of partner forms; empty when no site matches.
    """
    cap = min(max_forms, MAX_TAUTOMER_FORMS)
    forms: list[TautomerForm] = []
    for site in detect_tautomers(graph):
        if len(forms) >= cap:
            break
        if site.h_source is None:
            continue
        a, c, o = site.atoms
        if site.tautomer_type == TautomerType.ENOL_KETO:
            # enol C-OH becomes C=O; the alpha C=C becomes a C-C single bond.
            g = _shift_h(
                graph, site,
                src=o, dst=a,
                to_double=(c, o), to_single=(a, c),
            )
        elif site.tautomer_type == TautomerType.IMIDIC_AMIDE:
            # imidic C-OH / C=N-H becomes amide C=O / C-N(H).
            g = _shift_h(
                graph, site,
                src=o, dst=a,
                to_double=(c, o), to_single=(c, a),
            )
        elif site.tautomer_type == TautomerType.KETO_ENOL:
            # keto C=O becomes C–O(H); alpha C–H becomes alpha C=C(O).
            g = _shift_h(
                graph, site,
                src=a, dst=o,
                to_double=(a, c), to_single=(c, o),
            )
        else:
            # amide N–H + C=O becomes imidic N=C–O(H).
            g = _shift_h(
                graph, site,
                src=a, dst=o,
                to_double=(c, a), to_single=(c, o),
            )
        forms.append(TautomerForm(site.tautomer_type, g))
    return forms


def canonical_tautomer(
    graph: MolecularGraph,
    max_forms: int = MAX_TAUTOMER_FORMS,
) -> MolecularGraph:
    """Select the canonical representative of a molecule's tautomer set.

    The representative is chosen from the *closure* of the tautomer graph,
    bounded by ``max_forms``: the input plus every partner reachable by
    repeatedly enumerating partners. A single enumeration step is not enough
    when a molecule has several tautomeric sites -- canonicalizing the keto
    form of an unsymmetrical ketone reaches all of its enols, while
    canonicalizing one enol would otherwise only reach the keto form, so the
    two calls returned different representatives for the same compound. With
    the closure the choice depends only on the tautomer set, not on which
    member was supplied.

    Deterministic choice: the lexicographically smallest canonical SMILES
    wins -- the stable, reproducible tie-break used across the engine.
    Structures with no recognised sites pass through untouched.

    Args:
        graph: The molecular graph (never mutated).
        max_forms: Upper bound on distinct forms considered.

    Returns:
        The canonical representative graph.
    """
    from chemengine.parsing.canonical import canonical_smiles

    cap = max(1, min(max_forms, MAX_TAUTOMER_FORMS))
    best = graph
    best_key = canonical_smiles(graph)
    seen: set[str] = {best_key}
    frontier: list[MolecularGraph] = [graph]
    while frontier and len(seen) <= cap:
        nxt: list[MolecularGraph] = []
        for member in frontier:
            for form in enumerate_tautomers(member, max_forms=cap):
                key = canonical_smiles(form.graph)
                if key in seen:
                    continue
                seen.add(key)
                if key < best_key:
                    best = form.graph
                    best_key = key
                nxt.append(form.graph)
        frontier = nxt
    return best
