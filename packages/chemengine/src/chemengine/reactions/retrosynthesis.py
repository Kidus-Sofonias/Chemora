"""Bounded template-based retrosynthetic engine (M36).

This module implements retrosynthetic *analysis* built directly on the shared
:class:`~chemengine.core.graph.MolecularGraph` abstraction -- there is no
SMARTS or sub-string manipulation anywhere.  Disconnection "surgery" is purely

    * subtractive  -- remove bonds of the target, and
    * additive     -- splice in explicit reagent atoms (H, Cl, a new O, ...).

Because no target atom is ever deleted, atomic conservation holds by
construction.  The bounded :class:`RetrosynthesisEngine` then walks the
disconnection graph with a depth-first expansion capped by ``max_depth``,
``max_candidates_per_step``, ``max_total_expansions`` and ``max_routes``.

No registration happens at import time.  :func:`register_retrosynthesis_algorithms`
is the explicit, lazy entry point wired into :class:`ChemEngineAPI` setup.
"""

from __future__ import annotations

__all__ = [
    "Disconnection",
    "RetrosyntheticCandidate",
    "RetrosyntheticTemplate",
    "RetrosynthesisEngine",
    "RetrosynthesisStep",
    "SynthesisRoute",
    "plan_retrosynthesis",
    "register_retrosynthesis_algorithms",
    "retrosynthesis_route_to_dict",
    "dict_to_retrosynthesis_route",
    "RETRO_SYNTHESIS_TEMPLATES",
    "get_retrosynthetic_template",
    "list_retrosynthetic_templates",
    "REFERENCE_ORACLE",
]

from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import product
from typing import TYPE_CHECKING, Any

from chemengine.core.atoms import Atom
from chemengine.core.bonds import BondOrder, BondTopology
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder

if TYPE_CHECKING:  # pragma: no cover - type-only import
    from chemengine.core.registry import AlgorithmRegistry

# A molecule at or below this many heavy atoms is a terminal building block.
_TERMINAL_HEAVY = 6

#: Catalogue version reported by the engine / registry entries.
_CATALOGUE_VERSION = (1, 0, 0)
_CATALOGUE_VERSION_STR = ".".join(str(p) for p in _CATALOGUE_VERSION)
_CATALOGUE_PREFIX = "m36"

#: Schema tag embedded in serialised routes (for forward compatibility).
SCHEMA_VERSION = "chemengine-retrosynthetic-route/v1"

# Immutable atom "specs" reused by the additive surgery.  These are *templates*
# only -- :func:`_apply_surgery` reads their fields and splices fresh atoms into
# the builder, so sharing the instances is safe.
_H = Atom(atomic_number=1)
_CL = Atom(atomic_number=17)
_O = Atom(atomic_number=8)


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------
def _heavy_neighbors(graph: MolecularGraph, index: int) -> tuple[int, ...]:
    """Non-hydrogen neighbour indices of ``index``."""
    return tuple(n for n in graph.get_neighbors(index) if graph.atoms[n].atomic_number != 1)


def _hydrogen_count(graph: MolecularGraph, index: int) -> int:
    """Explicit + implicit hydrogens attached to ``index``."""
    atom = graph.atoms[index]
    count = atom.implicit_hydrogens if atom.implicit_hydrogens else 0
    return count + sum(1 for n in graph.get_neighbors(index) if graph.atoms[n].atomic_number == 1)


def _bond_cut_set(graph: MolecularGraph, a: int, b: int) -> frozenset[int]:
    """Unordered atom pair describing a bond cut between ``a`` and ``b``."""
    bond = graph.get_bond(a, b)
    if bond is None:
        return frozenset((a, b))
    return frozenset((bond.atom1, bond.atom2))


def _h_to_target(target_index: int) -> tuple[Atom, tuple[tuple[str, int, BondOrder], ...]]:
    """An explicit hydrogen bonded back to a target atom."""
    return (_H, (("t", target_index, BondOrder.SINGLE),))


def _new_heavy(
    element: Atom, target_index: int, order: BondOrder = BondOrder.SINGLE
) -> tuple[Atom, tuple[tuple[str, int, BondOrder], ...]]:
    """A fresh heavy atom bonded back to a target atom."""
    return (element, (("t", target_index, order),))


def _carbonyl_oxygen(target: MolecularGraph, c: int) -> int | None:
    """Return the oxygen double-bonded to carbon ``c``, if any."""
    for n in target.get_neighbors(c):
        bond = target.get_bond(c, n)
        if bond is not None and bond.is_double and target.atoms[n].symbol == "O":
            return n
    return None


# ---------------------------------------------------------------------------
# Surgery description + application
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class _Surgery:
    """Declarative description of a single disconnection.

    Attributes:
        cuts:           frozensets of two atom indices -- target bonds to remove.
        new_atoms:      ``(Atom, bond_specs)`` tuples for atoms to add.  Each
                        bond_spec is ``("t", target_index, order)`` (bond to a
                        surviving target atom) or ``("n", slot, order)`` (bond
                        to a newly-added atom at ``slot``).
        order_changes:  ``(frozenset({a, b}), BondOrder)`` rewrites applied to
                        surviving target bonds (e.g. ``C=O`` -> ``C-O``).
    """

    cuts: tuple[frozenset[int], ...]
    new_atoms: tuple[tuple[Atom, tuple[tuple[str, int, BondOrder], ...]], ...] = ()
    order_changes: tuple[tuple[frozenset[int], BondOrder], ...] = ()
    _order_lookup: dict[frozenset[int], BondOrder] = field(
        default_factory=dict, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_order_lookup", {pair: order for pair, order in self.order_changes}
        )

    def order_for(self, a: int, b: int) -> BondOrder | None:
        return self._order_lookup.get(frozenset((a, b)))


def _iter_cut_pairs(target: MolecularGraph, surgery: _Surgery) -> Iterable[tuple[int, int]]:
    """Yield ``(a, b)`` pairs for every bond described by ``surgery.cuts``."""
    for pair in surgery.cuts:
        members = tuple(pair)
        if len(members) == 2:
            yield members[0], members[1]


def _apply_surgery(target: MolecularGraph, surgery: _Surgery) -> tuple[MolecularGraph, ...]:
    """Apply ``surgery`` to ``target`` and return the cleaved precursors.

    The reconstruction copies every surviving target atom (preserving its
    element, charge, explicit/implicit hydrogens and aromatic flag), re-wires
    surviving bonds (honouring ``order_changes``), splices in the new reagent
    atoms, then splits the result into connected components.  H-only fragments
    (e.g. a lone hydronium) are discarded as they are not meaningful
    precursors.
    """
    builder = MolecularGraphBuilder()

    # 1) Surviving target atoms.
    for idx in range(target.num_atoms):
        atom = target.atoms[idx]
        builder.add_atom(
            atomic_number=atom.atomic_number,
            formal_charge=atom.formal_charge,
            implicit_hydrogens=atom.implicit_hydrogens,
            is_aromatic=atom.is_aromatic,
        )

    cut_pairs = {frozenset((a, b)) for a, b in _iter_cut_pairs(target, surgery)}

    # 2) Surviving target bonds.
    for bond in target.bonds:
        if frozenset((bond.atom1, bond.atom2)) in cut_pairs:
            continue
        new_order = surgery.order_for(bond.atom1, bond.atom2)
        builder.add_bond(
            bond.atom1,
            bond.atom2,
            order=new_order if new_order is not None else bond.order,
            is_aromatic=bond.is_aromatic,
        )

    # 3) New reagent atoms + their bonds.
    new_atom_indices: list[int] = []
    for element, bond_specs in surgery.new_atoms:
        spec_atom = Atom(
            atomic_number=element.atomic_number,
            formal_charge=element.formal_charge,
            implicit_hydrogens=element.implicit_hydrogens,
            is_aromatic=element.is_aromatic,
        )
        new_idx = builder.add_atom(
            atomic_number=spec_atom.atomic_number,
            formal_charge=spec_atom.formal_charge,
            implicit_hydrogens=spec_atom.implicit_hydrogens,
            is_aromatic=spec_atom.is_aromatic,
        )
        new_atom_indices.append(new_idx)
        for kind, partner, order in bond_specs:
            target_partner = new_atom_indices[partner] if kind == "n" else int(partner)
            builder.add_bond(new_idx, target_partner, order=order)

    modified = builder.build()

    # 4) Split into connected precursors, dropping H-only fragments.
    precursors: list[MolecularGraph] = []
    for comp in modified.connected_components():
        if not any(modified.atoms[i].atomic_number != 1 for i in comp):
            continue
        precursors.append(modified.subgraph(set(comp)))
    return tuple(precursors)


# ---------------------------------------------------------------------------
# Disconnection + candidate model
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Disconnection:
    """A single matched retrosynthetic disconnection for a target."""

    template: RetrosyntheticTemplate
    target: MolecularGraph
    cuts: tuple[frozenset[int], ...]
    site: dict[str, int]
    precursors: tuple[MolecularGraph, ...]
    reagents: tuple[str, ...] = ()
    score: float = 0.0

    def is_terminal(self) -> bool:
        """True when every precursor is a terminal building block."""
        return all(p.num_heavy_atoms <= _TERMINAL_HEAVY for p in self.precursors)

    def __hash__(self) -> int:  # pragma: no cover - used for set dedup  # noqa: D105
        return hash((self.template.id, tuple(sorted(self.cuts))))


@dataclass(frozen=True, slots=True)
class RetrosyntheticCandidate:
    """A ranked, serialisable retrosynthetic proposal for one step."""

    template_id: str
    target: MolecularGraph
    precursors: tuple[MolecularGraph, ...]
    reagents: tuple[str, ...] = ()
    cuts: tuple[tuple[int, int], ...] = ()
    score: float = 0.0
    priority: int = 0
    is_terminal: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise this candidate to a plain dict."""
        from chemengine.io.serialization import graph_to_dict

        return {
            "template_id": self.template_id,
            "priority": self.priority,
            "score": round(self.score, 6),
            "is_terminal": self.is_terminal,
            "cuts": [list(c) for c in self.cuts],
            "reagents": list(self.reagents),
            "target": graph_to_dict(self.target),
            "target_smiles": _safe_smiles(self.target),
            "precursors": [graph_to_dict(p) for p in self.precursors],
            "precursor_smiles": [_safe_smiles(p) for p in self.precursors],
        }

    @classmethod
    def from_disconnection(
        cls, disc: Disconnection, *, score: float | None = None
    ) -> RetrosyntheticCandidate:
        """Build a :class:`RetrosyntheticCandidate` from a :class:`Disconnection`."""
        return cls(
            template_id=disc.template.id,
            target=disc.target,
            precursors=disc.precursors,
            reagents=disc.reagents,
            cuts=tuple(sorted(tuple(c) for c in disc.cuts)),
            score=disc.score if score is None else score,
            priority=disc.template.priority,
            is_terminal=disc.is_terminal(),
        )


# ---------------------------------------------------------------------------
# Template base class
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RetrosyntheticTemplate:
    """Base class for all M36 retrosynthetic disconnections."""

    id: str
    title: str
    forward_reaction: str = ""
    priority: int = 0
    constraints: tuple[str, ...] = ()
    reagents: tuple[str, ...] = ()

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        """Return ``[(site, surgery), ...]`` matches against ``target``."""
        raise NotImplementedError

    def matches(self, target: MolecularGraph) -> list[Disconnection]:
        """Materialise concrete, valid :class:`Disconnection` objects."""
        results: list[Disconnection] = []
        for site, surgery in self.find(target):
            precursors = _apply_surgery(target, surgery)
            if not all(p.validate() == [] for p in precursors):
                continue
            # Conservation guard (heavy atoms): target + added heavy atoms must
            # equal the sum of precursor heavy atoms (H-only fragments dropped).
            added_heavy = sum(1 for atom, _ in surgery.new_atoms if atom.atomic_number != 1)
            if sum(p.num_heavy_atoms for p in precursors) != (target.num_heavy_atoms + added_heavy):
                continue
            score = float(-sum(p.num_heavy_atoms for p in precursors))
            results.append(
                Disconnection(
                    template=self,
                    target=target,
                    cuts=surgery.cuts,
                    site=site,
                    precursors=precursors,
                    reagents=self.reagents,
                    score=score,
                )
            )
        return results

    def __hash__(self) -> int:  # noqa: D105
        return hash(self.id)


def _safe_smiles(graph: MolecularGraph) -> str:
    try:
        from chemengine.parsing.smiles import serialize_smiles

        return serialize_smiles(graph)
    except Exception:
        return ""


def _canonical_smiles(graph: MolecularGraph) -> str:
    """Best-effort canonical SMILES (falls back to ``_safe_smiles``)."""
    try:
        from chemengine.parsing.canonical import canonical_smiles

        return canonical_smiles(graph)
    except Exception:
        return _safe_smiles(graph)


def _route_signature(route: SynthesisRoute) -> tuple:
    """Canonical structural signature for de-duplicating routes.

    Two routes are considered duplicates when they share the same target
    canonical SMILES and the same per-step ``(template id, precursor
    canonical-SMILES)`` sequence -- independent of internal atom indexing,
    so symmetric disconnections collapse to a single route.  Precursors are
    sorted within a step so that reagent/product ordering does not create
    spurious duplicates.
    """
    return (
        _canonical_smiles(route.target),
        tuple(
            (
                step.candidate.template_id,
                tuple(sorted(_canonical_smiles(p) for p in step.candidate.precursors)),
            )
            for step in route.steps
        ),
    )


# ---------------------------------------------------------------------------
# Concrete disconnection templates
# ---------------------------------------------------------------------------
class EsterFischer(RetrosyntheticTemplate):
    """Ester saponification: ``RC(=O)OR' -> RCOOH + R'OH``."""

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        out: list[tuple[dict[str, int], _Surgery]] = []
        # Iterate carbonyl *carbons* (C double-bonded to O).  `_carbonyl_oxygen`
        # expects the carbon and returns its =O partner -- the previous loop
        # mis-called it with the oxygen atom, which always returned ``None``.
        for c in range(target.num_atoms):
            if target.atoms[c].symbol != "C" or target.atoms[c].is_aromatic:
                continue
            o = _carbonyl_oxygen(target, c)
            if o is None:
                continue
            # Ether oxygen = the other O atom adjacent to the carbonyl C.
            ether_os = [
                x
                for x in target.get_neighbors(c)
                if x != o and target.atoms[x].symbol == "O" and not target.atoms[x].is_aromatic
            ]
            if not ether_os:
                continue
            orx = ether_os[0]
            # Alkyl group R' on the ether oxygen (exclude the carbonyl carbon
            # and any oxygen so we don't pick the ester backbone itself).
            r_candidates = [
                r
                for r in _heavy_neighbors(target, orx)
                if r != c and r != o and target.atoms[r].symbol != "O"
            ]
            if not r_candidates:
                continue
            r = r_candidates[0]
            surgery = _Surgery(
                cuts=(_bond_cut_set(target, c, orx),),
                new_atoms=(
                    _h_to_target(orx),  # -> R'-OH
                    _new_heavy(_O, c),  # new acid hydroxyl O on carbonyl C
                    (_H, (("n", 1, BondOrder.SINGLE),)),  # -> acid -OH
                ),
            )
            out.append(
                (
                    {"carbonyl_O": o, "carbonyl_C": c, "ether_O": orx, "alkyl_R": r},
                    surgery,
                )
            )
        return out


class AmideHydrolysis(RetrosyntheticTemplate):
    """Amide hydrolysis: ``RC(=O)NR'R'' -> RCOOH + R'R''NH2``."""

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        out: list[tuple[dict[str, int], _Surgery]] = []
        for n in range(target.num_atoms):
            if target.atoms[n].symbol != "N" or target.atoms[n].is_aromatic:
                continue
            if _hydrogen_count(target, n) < 1:
                continue
            for c in _heavy_neighbors(target, n):
                o = _carbonyl_oxygen(target, c)
                if o is None:
                    continue
                surgery = _Surgery(
                    cuts=(_bond_cut_set(target, c, n),),
                    new_atoms=(
                        _h_to_target(n),  # saturate the amine -> NH3 / RNH3
                        _new_heavy(_O, c),  # new acid hydroxyl O on carbonyl C
                        (_H, (("n", 1, BondOrder.SINGLE),)),  # -> acid -OH
                    ),
                )
                out.append(({"carbonyl_O": o, "carbonyl_C": c, "amide_N": n}, surgery))
                break
        return out


class EtherCleavageAryl(RetrosyntheticTemplate):
    """Aryl-ether cleavage: ``Ar-O-R -> ArOH + R-Cl``."""

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        out: list[tuple[dict[str, int], _Surgery]] = []
        for o in range(target.num_atoms):
            if target.atoms[o].symbol != "O":
                continue
            heavy = [x for x in target.get_neighbors(o) if target.atoms[x].atomic_number != 1]
            aromatics = [x for x in heavy if target.atoms[x].is_aromatic]
            aliphatics = [
                x
                for x in heavy
                if not target.atoms[x].is_aromatic and target.atoms[x].symbol != "O"
            ]
            if not aromatics or not aliphatics:
                continue
            aryl = aromatics[0]
            r = aliphatics[0]
            surgery = _Surgery(
                cuts=(_bond_cut_set(target, o, r),),
                new_atoms=(
                    _h_to_target(o),  # -> ArOH
                    (_CL, (("t", r, BondOrder.SINGLE),)),  # -> R-Cl
                ),
            )
            out.append(({"phenolic_O": o, "aryl_C": aryl, "alkyl_R": r}, surgery))
        return out


class EtherCleavageAlkyl(RetrosyntheticTemplate):
    """Alkyl-ether cleavage: ``R-O-R' -> R-OH + R'-Cl``.

    The bond between the ether oxygen and *one* alkyl group is cut; that alkyl
    becomes the halide, the oxygen (kept with the other alkyl) becomes the
    alcohol.
    """

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        out: list[tuple[dict[str, int], _Surgery]] = []
        for o in range(target.num_atoms):
            if target.atoms[o].symbol != "O":
                continue
            heavy = [
                x
                for x in _heavy_neighbors(target, o)
                if not target.atoms[x].is_aromatic and target.atoms[x].symbol != "O"
            ]
            if len(heavy) != 2:
                continue
            r, s = heavy[0], heavy[1]
            surgery = _Surgery(
                cuts=(_bond_cut_set(target, o, s),),
                new_atoms=(
                    _h_to_target(o),  # -> R-OH (kept with r)
                    (_CL, (("t", s, BondOrder.SINGLE),)),  # -> R'-Cl
                ),
            )
            out.append(({"ether_O": o, "alkyl_R1": r, "alkyl_R2": s}, surgery))
        return out


class AlcoholToAlkylHalide(RetrosyntheticTemplate):
    """Alcohol -> alcohol-derived alkyl halide + water: ``R-OH -> R-Cl + H2O``."""

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        out: list[tuple[dict[str, int], _Surgery]] = []
        for o in range(target.num_atoms):
            if target.atoms[o].symbol != "O":
                continue
            if _hydrogen_count(target, o) != 1:
                continue
            heavy = [x for x in target.get_neighbors(o) if target.atoms[x].atomic_number != 1]
            if len(heavy) != 1:
                continue
            c = heavy[0]
            surgery = _Surgery(
                cuts=(_bond_cut_set(target, c, o),),
                new_atoms=(
                    (_CL, (("t", c, BondOrder.SINGLE),)),  # -> R-Cl
                    _h_to_target(o),  # -> H2O
                ),
            )
            out.append(({"hydroxyl_O": o, "alkyl_C": c}, surgery))
        return out


class CarbonylReduction(RetrosyntheticTemplate):
    """Ketone/aldehyde reduction: ``R-C(=O)-R' -> R-CH(OH)-R'``."""

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        out: list[tuple[dict[str, int], _Surgery]] = []
        for c in range(target.num_atoms):
            if target.atoms[c].symbol != "C" or target.atoms[c].is_aromatic:
                continue
            o = _carbonyl_oxygen(target, c)
            if o is None:
                continue
            surgery = _Surgery(
                cuts=(),
                order_changes=((frozenset((c, o)), BondOrder.SINGLE),),
                new_atoms=(
                    _h_to_target(o),  # -> alcohol -OH on former =O
                    _h_to_target(c),  # saturate the reduced carbon
                ),
            )
            out.append(({"carbonyl_C": c, "carbonyl_O": o}, surgery))
        return out


class DieneDielsAlder(RetrosyntheticTemplate):
    """Retro-Diels-Alder: open one aliphatic ring bond of a cyclic diene/diene."""

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        out: list[tuple[dict[str, int], _Surgery]] = []
        for bond in target.bonds:
            if not bond.is_single or bond.is_aromatic:
                continue
            if bond.topology != BondTopology.RING:
                continue
            a, b = bond.atom1, bond.atom2
            if target.atoms[a].is_aromatic or target.atoms[b].is_aromatic:
                continue
            surgery = _Surgery(cuts=(_bond_cut_set(target, a, b),))
            out.append(({"ring_bond_a": a, "ring_bond_b": b}, surgery))
        return out


class RetroAldol(RetrosyntheticTemplate):
    """Retro-aldol: ``R-CH(OR'')-C(=O)-R' -> R-CHO + R'-CO-OR''`` (C-C scission).

    The C-C bond between a carbonyl carbon and an adjacent (alpha) carbon that
    carries at least one hydrogen is cut.  The alpha carbon receives a chlorine
    (to terminate it as an alkyl chloride) and the carbonyl fragment is left as a
    carboxylic acid by adding a fresh oxygen + hydrogen.
    """

    def find(self, target: MolecularGraph) -> list[tuple[dict[str, int], _Surgery]]:
        out: list[tuple[dict[str, int], _Surgery]] = []
        for c in range(target.num_atoms):
            o = _carbonyl_oxygen(target, c)
            if o is None:
                continue
            for a in _heavy_neighbors(target, c):
                if target.atoms[a].symbol != "C" or target.atoms[a].is_aromatic:
                    continue
                if _hydrogen_count(target, a) < 1:
                    continue
                surgery = _Surgery(
                    cuts=(_bond_cut_set(target, c, a),),
                    new_atoms=(
                        (_CL, (("t", a, BondOrder.SINGLE),)),  # -> R-Cl
                        _new_heavy(_O, c),  # new acid O on carbonyl C
                        (_H, (("n", 1, BondOrder.SINGLE),)),  # -> acid -OH
                    ),
                )
                out.append(({"carbonyl_C": c, "carbonyl_O": o, "alpha_C": a}, surgery))
        return out


_TEMPLATES: tuple[RetrosyntheticTemplate, ...] = (
    EsterFischer(
        id=f"{_CATALOGUE_PREFIX}-ester-fischer",
        title="Ester saponification (retro-ester)",
        forward_reaction="RC(=O)OR' + H2O -> RCOOH + R'OH",
        priority=3,
        reagents=("water",),
    ),
    AmideHydrolysis(
        id=f"{_CATALOGUE_PREFIX}-amide-hydrolysis",
        title="Amide hydrolysis",
        forward_reaction="RC(=O)NR'R'' + H2O -> RCOOH + R'R''NH2",
        priority=3,
        reagents=("water",),
    ),
    EtherCleavageAryl(
        id=f"{_CATALOGUE_PREFIX}-ether-cleavage-aryl",
        title="Aryl-ether cleavage",
        forward_reaction="Ar-O-R -> ArOH + R-Cl",
        priority=2,
        reagents=("Cl",),
    ),
    EtherCleavageAlkyl(
        id=f"{_CATALOGUE_PREFIX}-ether-cleavage-alkyl",
        title="Alkyl-ether cleavage",
        forward_reaction="R-O-R' -> R-OH + R'-Cl",
        priority=2,
        reagents=("Cl",),
    ),
    AlcoholToAlkylHalide(
        id=f"{_CATALOGUE_PREFIX}-alcohol-to-alkyl-halide",
        title="Alcohol to alkyl halide",
        forward_reaction="R-OH -> R-Cl + H2O",
        priority=1,
        reagents=("Cl",),
    ),
    CarbonylReduction(
        id=f"{_CATALOGUE_PREFIX}-carbonyl-reduction",
        title="Carbonyl reduction",
        forward_reaction="R-C(=O)-R' + 2 H -> R-CHOH-R'",
        priority=1,
        reagents=(),
    ),
    DieneDielsAlder(
        id=f"{_CATALOGUE_PREFIX}-retro-diels-alder",
        title="Retro-Diels-Alder (ring opening)",
        forward_reaction="diene + dienophile -> cycloadduct",
        priority=2,
        reagents=(),
    ),
    RetroAldol(
        id=f"{_CATALOGUE_PREFIX}-retro-aldol",
        title="Retro-aldol (C-C scission next to carbonyl)",
        forward_reaction="R-CHO + R'CO-R'' -> R-CH(OH)-C(=O)-R''",
        priority=2,
        reagents=(),
    ),
)

# Public catalogue (lookup tables built once at import -- cheap, no I/O).
RETRO_SYNTHESIS_TEMPLATES: tuple[RetrosyntheticTemplate, ...] = _TEMPLATES
_TEMPLATE_INDEX: dict[str, RetrosyntheticTemplate] = {t.id: t for t in _TEMPLATES}


def list_retrosynthetic_templates() -> tuple[RetrosyntheticTemplate, ...]:
    """Return all registered retrosynthetic templates."""
    return _TEMPLATES


def get_retrosynthetic_template(template_id: str) -> RetrosyntheticTemplate:
    """Look up a template by its identifier."""
    try:
        return _TEMPLATE_INDEX[template_id]
    except KeyError as exc:
        raise KeyError(f"Unknown retrosynthetic template: {template_id!r}") from exc


#: Deterministic regression oracle.  Keys are target SMILES; values describe
#: the expected *minimum* behaviour -- ``"must_match"`` is the set of template
#: ids that must fire, ``"must_not_match"`` is the set that must not, and
#: ``"terminal"`` asserts that every returned route is chemically complete.
REFERENCE_ORACLE: dict[str, dict[str, Any]] = {
    "CC(=O)OC": {
        "description": "methyl acetate -> ester-fischer (acid + alcohol)",
        "must_match": {f"{_CATALOGUE_PREFIX}-ester-fischer"},
        "must_not_match": set(),
    },
    "CC(=O)N": {
        "description": "acetamide -> amide-hydrolysis (acid + ammonia)",
        "must_match": {f"{_CATALOGUE_PREFIX}-amide-hydrolysis"},
        "must_not_match": set(),
    },
    "CCO": {
        "description": "ethanol -> alcohol->halide (ethyl chloride + water)",
        "must_match": {f"{_CATALOGUE_PREFIX}-alcohol-to-alkyl-halide"},
        "must_not_match": set(),
    },
    "CC(=O)C": {
        "description": "acetone -> retro-aldol",
        "must_match": {f"{_CATALOGUE_PREFIX}-retro-aldol"},
        "must_not_match": set(),
    },
    "C1=CC=C(C=C1)C1=CC=CC=C1": {
        "description": "biphenyl -> retro-diels-alder (ring bond)",
        "must_match": set(),
        "must_not_match": {f"{_CATALOGUE_PREFIX}-retro-diels-alder"},
        "note": "no aliphatic ring bond present, so RDA must not fire",
    },
}


# ---------------------------------------------------------------------------
# Route model
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RetrosynthesisStep:
    """One disconnection step within a :class:`SynthesisRoute`."""

    order: int
    """Position of the step in the route (0 = first disconnection)."""

    depth: int
    """Tree depth of this step (0 = the root target)."""

    candidate: RetrosyntheticCandidate
    """The proposal this step realises."""

    precursor_step_indices: tuple[int | None, ...] = ()
    """``order`` of the child step for each precursor, or ``None`` for a
    terminal building block with no further expansion."""

    @property
    def template_id(self) -> str:
        """Identifier of the template that produced this step."""
        return self.candidate.template_id

    @property
    def is_terminal(self) -> bool:
        """Whether this step terminates in a building-block leaf."""
        return self.candidate.is_terminal


@dataclass(frozen=True, slots=True)
class SynthesisRoute:
    """A complete, hashable retrosynthetic route (target + ordered steps)."""

    target: MolecularGraph
    """The original target molecule."""

    steps: tuple[RetrosynthesisStep, ...] = ()
    """Ordered disconnection steps (root disconnection first)."""

    @property
    def num_steps(self) -> int:
        """Number of disconnection steps in the route."""
        return len(self.steps)

    @property
    def target_smiles(self) -> str:
        """Canonical SMILES of the route target."""
        return _safe_smiles(self.target)

    @property
    def is_complete(self) -> bool:
        """True when every terminal (un-expanded) leaf is a building block."""
        if not self.steps:
            return self.target.num_heavy_atoms <= _TERMINAL_HEAVY
        for step in self.steps:
            for precursor, idx in zip(step.candidate.precursors, step.precursor_step_indices):
                if idx is None and precursor.num_heavy_atoms > _TERMINAL_HEAVY:
                    return False
        return True

    def __hash__(self) -> int:  # pragma: no cover - for set dedup  # noqa: D105
        return hash((self.target_smiles, tuple(s.candidate.template_id for s in self.steps)))


@dataclass(frozen=True, slots=True)
class _Tree:
    """Internal search tree node used by the bounded DFS."""

    target: MolecularGraph
    disconnection: Disconnection | None = None
    children: tuple[_Tree, ...] = ()


# ---------------------------------------------------------------------------
# Bounded depth-first search engine
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RetrosynthesisEngine:
    """Bounded template-based retrosynthetic planner.

    The search expands the target through disconnections, recursing into each
    precursor until every leaf is a terminal building block (or a bound
    prevents further growth).  A canonical-SMILES memo is used as a cycle
    guard: a molecule already on the current root-to-leaf path is not
    re-expanded, which prevents infinite loops where a template would simply
    re-form the target.
    """

    templates: tuple[RetrosyntheticTemplate, ...] = field(default_factory=lambda: _TEMPLATES)
    max_depth: int = 6
    max_candidates_per_step: int = 10
    max_total_expansions: int = 200
    max_routes: int = 50

    def plan(self, target: MolecularGraph | str) -> list[SynthesisRoute]:
        """Plan retrosynthetic routes from ``target`` (SMILES or graph)."""
        if isinstance(target, str):
            from chemengine.parsing.smiles import parse_smiles

            target = parse_smiles(target)
        counter: list[int] = [0]
        trees = self._grow(target, 0, counter, ())
        routes = [self._to_route(tree) for tree in trees]
        routes.sort(
            key=lambda r: (
                r.num_steps,
                -sum(s.candidate.score for s in r.steps),
            )
        )
        # Deduplicate structurally-identical routes before the cap.  The
        # signature is canonical-SMILES based so that symmetric disconnections
        # (e.g. acetone's two equivalent methyl groups) collapse to a single
        # route even though they carry different internal atom indices.
        seen: set[tuple] = set()
        unique: list[SynthesisRoute] = []
        for route in routes:
            sig = _route_signature(route)
            if sig in seen:
                continue
            seen.add(sig)
            unique.append(route)
        return unique[: self.max_routes]

    # -- internal -----------------------------------------------------------
    def _rank(self, target: MolecularGraph) -> list[Disconnection]:
        """Run every template against ``target`` and rank the matches."""
        discons: list[Disconnection] = []
        for template in self.templates:
            discons.extend(template.matches(target))
        discons.sort(key=lambda d: (d.template.priority, -d.score, d.template.id))
        return discons

    def _grow(
        self,
        target: MolecularGraph,
        depth: int,
        counter: list[int],
        path: tuple[str, ...],
    ) -> list[_Tree]:
        """Depth-first expansion returning a (capped) list of result trees.

        Semantics
        ---------
        * The **root** target (depth 0) is always a candidate for
          disconnection -- the goal molecule is never itself treated as a
          terminal building block.
        * A **precursor** node becomes a leaf when it is a small molecule
          (``heavy_atoms <= _TERMINAL_HEAVY``) *or* when no template can
          disconnect it -- in both cases the parent disconnection stays
          feasible rather than being pruned as infeasible.
        * A canonical-SMILES cycle guard skips any molecule already on the
          root-to-leaf path (e.g. a template that would simply re-form the
          target), preventing infinite recursion.
        """
        # Small building block (precursor only -- the root always expands).
        if depth > 0 and target.num_heavy_atoms <= _TERMINAL_HEAVY:
            return [_Tree(target=target)]
        if depth >= self.max_depth or counter[0] >= self.max_total_expansions:
            return [_Tree(target=target)]
        # Canonical-SMILES cycle guard.
        canonical = _safe_smiles(target)
        if canonical and canonical in path:
            return [_Tree(target=target)]
        ranked = self._rank(target)
        ranked = ranked[: self.max_candidates_per_step]
        if not ranked:
            # No disconnections available -> treat as an available leaf.
            return [_Tree(target=target)]
        counter[0] += 1
        new_path = path + (canonical,) if canonical else path
        trees: list[_Tree] = []
        for disc in ranked:
            options: list[list[_Tree]] = []
            feasible = True
            for precursor in disc.precursors:
                children = self._grow(precursor, depth + 1, counter, new_path)
                if not children:
                    feasible = False
                    break
                options.append(children)
            if not feasible:
                continue
            for combo in product(*options):
                trees.append(
                    _Tree(
                        target=target,
                        disconnection=disc,
                        children=tuple(combo),
                    )
                )
                if len(trees) >= self.max_routes:
                    return trees
        return trees

    def _to_route(self, tree: _Tree) -> SynthesisRoute:
        """Flatten a search tree into a linear :class:`SynthesisRoute`."""
        steps: list[RetrosynthesisStep] = []

        def walk(node: _Tree | None, depth: int) -> int | None:
            if node is None or node.disconnection is None:
                return None
            order = len(steps)
            candidate = RetrosyntheticCandidate.from_disconnection(
                node.disconnection, score=node.disconnection.score
            )
            child_indices = tuple(walk(child, depth + 1) for child in node.children)
            steps.append(
                RetrosynthesisStep(
                    order=order,
                    depth=depth,
                    candidate=candidate,
                    precursor_step_indices=child_indices,
                )
            )
            return order

        walk(tree, 0)
        return SynthesisRoute(target=tree.target, steps=tuple(steps))


# ---------------------------------------------------------------------------
# Public convenience API
# ---------------------------------------------------------------------------
def plan_retrosynthesis(
    smiles_or_graph: MolecularGraph | str,
    *,
    max_depth: int = 6,
    max_candidates_per_step: int = 10,
    max_total_expansions: int = 200,
    max_routes: int = 50,
) -> list[SynthesisRoute]:
    """Plan retrosynthetic routes for a target (SMILES or graph)."""
    engine = RetrosynthesisEngine(
        max_depth=max_depth,
        max_candidates_per_step=max_candidates_per_step,
        max_total_expansions=max_total_expansions,
        max_routes=max_routes,
    )
    return engine.plan(smiles_or_graph)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_retrosynthesis_algorithms(
    registry: AlgorithmRegistry | None = None,
    *,
    replace: bool = False,
) -> None:
    """Register the M36 retrosynthetic algorithms with ``registry``.

    Mirrors the ``register_mechanism_algorithms`` pattern: a no-op when the
    entry already exists (``replace=False``).  Called explicitly by
    ``ChemEngineAPI`` built-in setup and by tests against any registry.  No
    import side effects -- registration is lazy, preserving the
    ``import chemengine`` first-import gate.
    """
    from chemengine.core.registry import AlgorithmEntry, get_global_registry

    target = registry if registry is not None else get_global_registry()
    plan_key = ("reactions.retrosynthesis", "plan")
    if plan_key in target and not replace:
        return
    target.register(
        AlgorithmEntry(
            domain="reactions.retrosynthesis",
            name="plan",
            version=f"m36.{_CATALOGUE_VERSION_STR}",
            algorithm=plan_retrosynthesis,
            input_type=str,
            output_type=list,
            tags=frozenset({"retro", "reactions", "synthesis", "deterministic"}),
        )
    )
    target.register(
        AlgorithmEntry(
            domain="reactions.retrosynthesis",
            name="catalogue",
            version=f"m36.{_CATALOGUE_VERSION_STR}",
            algorithm=list_retrosynthetic_templates,
            input_type=None,
            output_type=tuple,
            tags=frozenset({"retro", "reactions", "templates"}),
        )
    )


# ---------------------------------------------------------------------------
# Route (de)serialisation
# ---------------------------------------------------------------------------
def retrosynthesis_route_to_dict(route: SynthesisRoute) -> dict[str, Any]:
    """Serialise a :class:`SynthesisRoute` to a JSON-able dict."""
    from chemengine.io.serialization import graph_to_dict

    steps = [
        {
            "order": step.order,
            "depth": step.depth,
            "template_id": step.candidate.template_id,
            "priority": step.candidate.priority,
            "score": round(step.candidate.score, 6),
            "is_terminal": step.candidate.is_terminal,
            "cuts": [list(c) for c in step.candidate.cuts],
            "reagents": list(step.candidate.reagents),
            "target_smiles": _safe_smiles(step.candidate.target),
            "target": graph_to_dict(step.candidate.target),
            "precursors": [
                {
                    "smiles": _safe_smiles(p),
                    "graph": graph_to_dict(p),
                }
                for p in step.candidate.precursors
            ],
            "precursor_step_indices": [
                int(i) if i is not None else None for i in step.precursor_step_indices
            ],
        }
        for step in route.steps
    ]
    return {
        "schema": SCHEMA_VERSION,
        "catalogue_version": f"m36.{_CATALOGUE_VERSION_STR}",
        "is_complete": route.is_complete,
        "num_steps": len(steps),
        "target_smiles": _safe_smiles(route.target),
        "target": graph_to_dict(route.target),
        "steps": steps,
    }


def dict_to_retrosynthesis_route(data: dict[str, Any]) -> SynthesisRoute:
    """Reconstruct a :class:`SynthesisRoute` from its dict form."""
    from chemengine.io.serialization import dict_to_graph

    target = dict_to_graph(data["target"])
    steps: list[RetrosynthesisStep] = []
    for sd in data.get("steps", []):
        candidate = RetrosyntheticCandidate(
            template_id=sd["template_id"],
            target=dict_to_graph(sd["target"]),
            precursors=tuple(dict_to_graph(p["graph"]) for p in sd["precursors"]),
            reagents=tuple(sd.get("reagents", ())),
            cuts=tuple(tuple(c) for c in sd.get("cuts", [])),
            score=float(sd.get("score", 0.0)),
            priority=int(sd.get("priority", 0)),
            is_terminal=bool(sd.get("is_terminal", False)),
        )
        steps.append(
            RetrosynthesisStep(
                order=sd["order"],
                depth=sd["depth"],
                candidate=candidate,
                precursor_step_indices=tuple(
                    int(i) if i is not None else None for i in sd.get("precursor_step_indices", [])
                ),
            )
        )
    return SynthesisRoute(target=target, steps=tuple(steps))
