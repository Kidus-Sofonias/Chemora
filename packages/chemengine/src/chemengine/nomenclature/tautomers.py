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

from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.core.enums import BondOrder

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
        Sites in ascending first-atom-index order; empty when none.
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
        if site.tautomer_type == TautomerType.KETO_ENOL:
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


def canonical_tautomer(graph: MolecularGraph) -> MolecularGraph:
    """Select the canonical representative of a molecule's tautomer set.

    Deterministic choice: the input graph is returned unchanged unless a
    recognised partner's canonical SMILES is lexicographically smaller —
    the stable, reproducible tie-break used across the engine. Unrelated
    structures (no recognised sites) pass through untouched.

    Args:
        graph: The molecular graph (never mutated).

    Returns:
        The canonical representative graph.
    """
    from chemengine.parsing.canonical import canonical_smiles

    best = graph
    best_key = canonical_smiles(graph)
    for form in enumerate_tautomers(graph):
        key = canonical_smiles(form.graph)
        if key < best_key:
            best = form.graph
            best_key = key
    return best
