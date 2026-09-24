"""Executable reaction mechanism engine (M34, roadmap 12.5 successor).

This module implements the *engine* the M33 architecture deliberately left
open: curated electron-pushing rules that run over the frozen
:class:`~chemengine.reactions.mechanisms` contract and produce validated,
conservation-checked :class:`MechanismTrace` sequences.

Scope (bounded, honest)
-----------------------
- The engine executes **curated, named mechanisms** with explicit
  applicability constraints (see :data:`CATALOGUE`). It does not infer
  novel mechanisms, predict yields or conditions, or simulate kinetics.
- Supported mechanisms (10): ``sn2``, ``sn1``, ``e2``, ``e1``, ``e1cb``,
  ``electrophilic_addition``, ``markovnikov_addition``,
  ``carbonyl_addition``, ``carbonyl_addition_elimination``,
  ``proton_transfer`` -- built from 12 elementary rules.
- Determinism: rule priority, pattern searches, atom pairing, and step
  ordering are fixed functions of the inputs. Identical inputs produce
  identical mechanisms, rules, step ordering, atom references, and
  serialized traces.
- Bounded work: rules are single-pass structural matchers (no recursive
  exploration); mapping delegates to the M33 bounded search.

Index convention (per step)
---------------------------
Every :class:`ArrowRef` in a step's movements uses **reactant-side atom
indices** of that step's :class:`Reaction` (hydrogens included). Bonds
that form may not exist in the reactant; they are still referenced by
their reactant-index atom pair. When several symmetry-equivalent
hydrogens exist, the referenced one is the lowest-index eligible child
(canonical, documented).

Why pairing is augmented (not just the M33 mapping)
---------------------------------------------------
The M33 skeleton mapper corresponds only atoms whose bond environments
match exactly within the mapped set. Atoms whose bond partners change
across the step -- the carbon center of an SN2, a leaving group, a
migrating nucleophile -- are therefore left outside the mapping, and
:attr:`ReactionGraph.changed_bonds` cannot see their bond changes. Rules
here consequently pattern-match the **raw graphs** by structural role
(change-shape + charge-delta signatures), and the engine computes
bond/charge changes over an *augmented heavy-atom correspondence*: the
M33 mapped correspondence first, then unpaired heavy atoms matched per
element in ascending index order (deterministic; for the curated
scenarios, chemically correct). Hydrogens stay outside the
correspondence -- mirroring the M33 mapping scope -- and are accounted
for by per-side structural checks (bonded-hydrogen neighbor counts) plus
global formula conservation. Inputs are never mutated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from chemengine.core.graph import MolecularGraph
from chemengine.reactions.mapping import ReactionGraph, map_reaction
from chemengine.reactions.mechanisms import (
    ArrowRef,
    ElectronMovement,
    MechanismRule,
    MechanismStep,
    MechanismTrace,
    MovementKind,
)
from chemengine.reactions.reaction import Reaction

if TYPE_CHECKING:  # pragma: no cover - typing only
    from chemengine.core.registry import AlgorithmRegistry

__all__ = [
    "CATALOGUE",
    "DEFAULT_RULES",
    "MechanismEngine",
    "MechanismError",
    "MechanismNotApplicableError",
    "MechanismResult",
    "MechanismScenario",
    "MechanismSpec",
    "MechanismValidationError",
    "bond_changes",
    "charge_changes",
    "get_mechanism",
    "list_mechanisms",
    "pair_atoms",
    "register_mechanism_algorithms",
    "step_details",
]

HALOGENS = frozenset({9, 17, 35, 53})
"""Halogen atomic numbers (F, Cl, Br, I)."""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MechanismError(ValueError):
    """Base class for structured mechanism-engine failures."""

    def __init__(self, message: str, *, step: int | None = None) -> None:
        """Store the 1-based step number when the failure is step-local."""
        self.step = step
        prefix = f"mechanism step {step}: " if step is not None else ""
        super().__init__(prefix + message)


class MechanismNotApplicableError(MechanismError):
    """No curated rule recognizes the transformation (declined, not forced)."""


class MechanismValidationError(MechanismError):
    """A proposal or scenario violated a chemical/structural invariant."""


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MechanismSpec:
    """A curated, named mechanism with explicit applicability constraints.

    Attributes:
        id: Stable identifier used in scenarios and serialized traces.
        title: Human-readable name.
        rule_sequence: Required per-step rule ids, in order.
            :meth:`MechanismEngine.explain` rejects scenarios whose
            executed rules differ, so a declared mechanism can never be
            attributed to different rules.
        constraints: Explicit applicability constraints (what is and is
            not supported). The engine claims no generality beyond these.
    """

    id: str
    title: str
    rule_sequence: tuple[str, ...]
    constraints: tuple[str, ...]


CATALOGUE: dict[str, MechanismSpec] = {
    "sn2": MechanismSpec(
        id="sn2",
        title="Bimolecular nucleophilic substitution (SN2)",
        rule_sequence=("sn2",),
        constraints=(
            "one concerted step: exactly one C-LG bond breaks (LG = halogen)",
            "exactly one bond forms at the same carbon center",
            "nucleophile ends with charge +1 relative to reactant",
            "no other heavy-atom bond or charge changes; formula conserved",
        ),
    ),
    "sn1": MechanismSpec(
        id="sn1",
        title="Unimolecular nucleophilic substitution (SN1)",
        rule_sequence=("heterolysis", "sn1_capture"),
        constraints=(
            "step 1: heterolysis of C-LG (LG = halogen) giving a carbocation",
            "  and halide (charge-separated, atoms conserved)",
            "step 2: a nucleophile lone pair bonds to the carbocation",
            "exactly two steps; no concerted displacement",
        ),
    ),
    "e2": MechanismSpec(
        id="e2",
        title="Bimolecular elimination (E2)",
        rule_sequence=("e2",),
        constraints=(
            "one concerted step: C-LG breaks (LG = halogen) while a beta C-H",
            "  bond (bonded hydrogen present) and the C-C pi bond change",
            "an anionic O/N base is protonated by exactly one hydrogen",
            "beta carbon neutral in the reactant; formula conserved",
        ),
    ),
    "e1": MechanismSpec(
        id="e1",
        title="Unimolecular elimination (E1)",
        rule_sequence=("heterolysis", "e1_deprotonation"),
        constraints=(
            "step 1: heterolysis of C-LG (LG = halogen) to a carbocation",
            "step 2: a base removes a beta hydrogen as the C-C pi bond forms",
            "exactly two steps; the carbocation forms before deprotonation",
        ),
    ),
    "e1cb": MechanismSpec(
        id="e1cb",
        title="Conjugate-base elimination (E1cB)",
        rule_sequence=("e1cb_deprotonation", "e1cb_elimination"),
        constraints=(
            "step 1: a base removes a beta hydrogen forming a carbanion",
            "  while the C-LG bond (LG = halogen) remains intact",
            "step 2: the carbanion lone pair forms the C-C pi bond and",
            "  expels LG with its bond pair",
            "exactly two steps; carbanion forms before leaving-group loss",
            "electronic activation of the carbanion (EWG) is not evaluated",
            "  -- this is a bounded structural match of the step pattern",
        ),
    ),
    "electrophilic_addition": MechanismSpec(
        id="electrophilic_addition",
        title="Electrophilic addition of H-X across an alkene (symmetric)",
        rule_sequence=("electrophilic_addition",),
        constraints=(
            "one C=C and one H-X fragment (X = halogen, exactly one H on X)",
            "both alkene carbons carry the same number of carbon substituents",
            "  (regiochemistry not discriminating; e.g. ethene)",
            "H and X end on the two former alkene carbons; neutral overall",
            "single net step (the stepwise ionic pathway is out of scope);",
            "  anti-Markovnikov/peroxide addition is NOT supported",
        ),
    ),
    "markovnikov_addition": MechanismSpec(
        id="markovnikov_addition",
        title="Markovnikov electrophilic addition of H-X across an alkene",
        rule_sequence=("markovnikov_addition",),
        constraints=(
            "one C=C and one H-X fragment (X = halogen, exactly one H on X)",
            "X ends on the alkene carbon with strictly more carbon",
            "  substituents than the other (Markovnikov regiochemistry)",
            "H ends on the other alkene carbon; neutral overall",
            "single net step (the stepwise ionic pathway is out of scope)",
        ),
    ),
    "carbonyl_addition": MechanismSpec(
        id="carbonyl_addition",
        title="Nucleophilic addition to a carbonyl",
        rule_sequence=("carbonyl_addition",),
        constraints=(
            "one C=O (aldehyde/ketone-type) and a separate-fragment",
            "  nucleophile (anionic carbon e.g. cyanide, or neutral amine N)",
            "the nucleophile bond forms at the carbonyl carbon; C=O -> C-O",
            "oxygen ends deprotonated (-1); nucleophile oxidized by +1",
            "formula and total charge conserved",
        ),
    ),
    "carbonyl_addition_elimination": MechanismSpec(
        id="carbonyl_addition_elimination",
        title="Nucleophilic acyl substitution (addition-elimination)",
        rule_sequence=("carbonyl_addition", "tetrahedral_collapse"),
        constraints=(
            "step 1: nucleophilic addition to C=O giving a tetrahedral",
            "  intermediate (alkoxide O-; amine nucleophile becomes N+)",
            "step 2: the alkoxide lone pair reforms C=O and expels a",
            "  heteroatom leaving group (alkoxide or halide) with its pair",
            "exactly two steps; no concerted substitution",
        ),
    ),
    "proton_transfer": MechanismSpec(
        id="proton_transfer",
        title="Bronsted proton transfer between heteroatoms",
        rule_sequence=("proton_transfer",),
        constraints=(
            "one H moves from a heteroatom donor to a different heteroatom",
            "  acceptor (neither atomic number 6); carbon deprotonation",
            "  belongs to the elimination mechanisms, not here",
            "donor loses exactly one bonded H and gains charge -1;",
            "  acceptor gains exactly one bonded H and gains charge +1",
            "no heavy-atom bond changes; total charge and formula conserved",
        ),
    ),
}
"""Ordered catalogue of curated mechanisms (insertion order = scan order)."""


def get_mechanism(name: str) -> MechanismSpec | None:
    """Return the catalogue entry for ``name``, or ``None`` if unknown."""
    return CATALOGUE.get(name)


def list_mechanisms() -> tuple[MechanismSpec, ...]:
    """Return all curated mechanism specs in deterministic scan order."""
    return tuple(CATALOGUE.values())


# ---------------------------------------------------------------------------
# Low-level helpers (raw-graph pattern queries)
# ---------------------------------------------------------------------------

def _sides(graph: ReactionGraph) -> tuple[MolecularGraph, MolecularGraph]:
    """Return the (reactant, product) raw graphs of a mapped reaction."""
    rxn = graph.reaction
    return rxn.reactants[0].molecule, rxn.products[0].molecule


def _q(mol: MolecularGraph, i: int) -> int:
    """Formal charge of atom ``i``."""
    return mol.atoms[i].formal_charge


def _z(mol: MolecularGraph, i: int) -> int:
    """Atomic number of atom ``i``."""
    return mol.atoms[i].atomic_number


def _order(mol: MolecularGraph, a: int, b: int) -> int:
    """Bond order between ``a`` and ``b`` (0 when unbonded)."""
    bond = mol.get_bond(a, b)
    return int(bond.order.value) if bond is not None else 0


def _children(mol: MolecularGraph, i: int) -> tuple[int, ...]:
    """Indices of hydrogen atoms bonded to atom ``i``, ascending."""
    return tuple(j for j in mol.get_neighbors(i) if _z(mol, j) == 1)


def _total_charge(mol: MolecularGraph) -> int:
    """Sum of formal charges over all atoms."""
    return sum(a.formal_charge for a in mol.atoms)


def _heavy(mol: MolecularGraph) -> list[int]:
    """Heavy-atom indices, ascending."""
    return [i for i, a in enumerate(mol.atoms) if a.atomic_number != 1]


def _carbon_substituents(mol: MolecularGraph, i: int) -> int:
    """Number of carbon neighbors of atom ``i``."""
    return sum(1 for j in mol.get_neighbors(i) if _z(mol, j) == 6)


def _canonical_pair(a: int, b: int) -> tuple[int, int]:
    """Unordered atom pair."""
    return (a, b) if a < b else (b, a)


# ---------------------------------------------------------------------------
# Augmented heavy-atom pairing + derived changes
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Pairing:
    """Deterministic reactant<->product heavy-atom correspondence.

    Attributes:
        r2p: reactant heavy index -> product heavy index.
        p2r: product heavy index -> reactant heavy index.
    """

    r2p: dict[int, int]
    p2r: dict[int, int]


def pair_atoms(graph: ReactionGraph) -> Pairing:
    """Build the augmented heavy-atom correspondence for a step.

    Starts from the M33 mapping, then pairs leftover heavy atoms per
    element in ascending index order (deterministic; hydrogens are
    excluded, mirroring the M33 mapping scope). Never mutates inputs.
    """
    r2p: dict[int, int] = {}
    for entry in graph.mapped_atoms():
        if entry.reactant_index is not None and entry.product_index is not None:
            r2p[entry.reactant_index] = entry.product_index
    reactant, product = _sides(graph)
    left_r = [i for i in _heavy(reactant) if i not in r2p]
    used_p = set(r2p.values())
    left_p = [j for j in _heavy(product) if j not in used_p]
    for z in sorted({_z(reactant, i) for i in left_r} | {_z(product, j) for j in left_p}):
        rs = [i for i in left_r if _z(reactant, i) == z]
        ps = [j for j in left_p if _z(product, j) == z]
        for i, j in zip(rs, ps, strict=False):
            r2p[i] = j
            left_r.remove(i)
            left_p.remove(j)
    p2r = {p: r for r, p in r2p.items()}
    return Pairing(r2p=r2p, p2r=p2r)


def bond_changes(
    graph: ReactionGraph, pairing: Pairing
) -> tuple[tuple[int, int, int, int], ...]:
    """Heavy bonds whose order differs across the step (ra, rb, ro, po).

    Computed over the augmented pairing in reactant index space; 0 means
    absent on that side. Deterministically ordered ascending. Hydrogen
    bonds are excluded (H stays outside the correspondence) and are
    accounted for by per-side children checks instead.
    """
    reactant, product = _sides(graph)
    pairs: set[tuple[int, int]] = set()
    for bond in reactant.bonds:
        if _z(reactant, bond.atom1) != 1 and _z(reactant, bond.atom2) != 1:
            pairs.add(_canonical_pair(bond.atom1, bond.atom2))
    for bond in product.bonds:
        if (
            bond.atom1 in pairing.p2r
            and bond.atom2 in pairing.p2r
            and _z(product, bond.atom1) != 1
            and _z(product, bond.atom2) != 1
        ):
            pairs.add(_canonical_pair(pairing.p2r[bond.atom1], pairing.p2r[bond.atom2]))
    out: list[tuple[int, int, int, int]] = []
    for a, b in sorted(pairs):
        pa, pb = pairing.r2p.get(a), pairing.r2p.get(b)
        ro = _order(reactant, a, b)
        po = _order(product, pa, pb) if pa is not None and pb is not None else 0
        if ro != po:
            out.append((a, b, ro, po))
    return tuple(out)


def charge_changes(
    graph: ReactionGraph, pairing: Pairing
) -> tuple[dict[str, Any], ...]:
    """Paired heavy atoms whose formal charge differs (plus unpaired).

    JSON-ready entries ordered by reactant index, then unpaired atoms by
    their own index.
    """
    reactant, product = _sides(graph)
    out: list[dict[str, Any]] = []
    for i in sorted(pairing.r2p):
        j = pairing.r2p[i]
        qi, qj = _q(reactant, i), _q(product, j)
        if qi != qj:
            out.append(
                {"reactant_atom": i, "product_atom": j, "reactant": qi, "product": qj}
            )
    for i in _heavy(reactant):
        if i not in pairing.r2p:
            out.append(
                {
                    "reactant_atom": i,
                    "product_atom": None,
                    "reactant": _q(reactant, i),
                    "product": None,
                }
            )
    for j in _heavy(product):
        if j not in pairing.p2r:
            out.append(
                {
                    "reactant_atom": None,
                    "product_atom": j,
                    "reactant": None,
                    "product": _q(product, j),
                }
            )
    return tuple(out)


def _charge_deltas(graph: ReactionGraph, pairing: Pairing) -> dict[int, int]:
    """Paired reactant heavy atoms with a charge change {r_index: delta}."""
    reactant, product = _sides(graph)
    out: dict[int, int] = {}
    for i, j in sorted(pairing.r2p.items()):
        delta = _q(product, j) - _q(reactant, i)
        if delta:
            out[i] = delta
    return out


def _movement_bond_pairs(
    movements: Sequence[ElectronMovement],
) -> set[tuple[int, int]]:
    """All atom pairs referenced as bonds by the movements."""
    out: set[tuple[int, int]] = set()
    for m in movements:
        for ref in (m.source, m.target):
            if ref.bond is not None:
                out.add(_canonical_pair(*ref.bond))
    return out


def _movement_atoms(movements: Sequence[ElectronMovement]) -> set[int]:
    """All atom indices referenced by the movements."""
    out: set[int] = set()
    for m in movements:
        for ref in (m.source, m.target):
            if ref.atom is not None:
                out.add(ref.atom)
            if ref.bond is not None:
                out.update(ref.bond)
    return out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _valence_issues(mol: MolecularGraph) -> list[str]:
    """Charge-aware valence check (bond-order sums, not plain degree).

    ``MolecularGraph.validate`` compares degree against a charge-blind
    element maximum, falsely rejecting legitimate onium intermediates
    (hydronium, oxonium, ammonium). This bounds the bond-order sum by
    ``max_valence + max(formal_charge, 0)`` instead; structural sanity
    still defers to ``MolecularGraph.validate``.
    """
    issues: list[str] = []
    for i, atom in enumerate(mol.atoms):
        order_sum = sum(
            int(bond.order.value)
            for bond in mol.bonds
            if bond.atom1 == i or bond.atom2 == i
        )
        limit = atom.max_valence
        if limit <= 0:
            continue
        limit += max(atom.formal_charge, 0)
        if order_sum > limit:
            issues.append(
                f"Atom {i} ({atom.symbol}): bond-order sum {order_sum} exceeds "
                f"allowed valence {limit} (max {atom.max_valence}, "
                f"charge {atom.formal_charge:+d})"
            )
    return issues


def validate_side(mol: MolecularGraph, *, label: str) -> list[str]:
    """Structural + charge-aware valence issues for one side of a step."""
    structural = [m for m in mol.validate() if "max valence" not in m]
    return [f"{label}: {m}" for m in structural + _valence_issues(mol)]


def validate_conservation(graph: ReactionGraph) -> list[str]:
    """Atom- and charge-conservation issues for one step."""
    reactant, product = _sides(graph)
    issues: list[str] = []
    if not graph.reaction.is_balanced():
        issues.append("explicit atom counts differ between reactant and product")
    if reactant.molecular_formula != product.molecular_formula:
        issues.append(
            f"molecular formula differs: {reactant.molecular_formula} -> "
            f"{product.molecular_formula}"
        )
    if _total_charge(reactant) != _total_charge(product):
        issues.append(
            f"total charge differs: {_total_charge(reactant)} -> "
            f"{_total_charge(product)}"
        )
    return issues


def validate_movements(
    graph: ReactionGraph,
    movements: Sequence[ElectronMovement],
    pairing: Pairing,
    *,
    step: int | None = None,
) -> None:
    """Raise :class:`MechanismValidationError` when movements are unsound.

    Checks: non-empty; endpoint index ranges; kind-specific endpoint
    shapes; and coverage -- every heavy bond change must be referenced
    by a movement, so the electron-pushing explains the transformation
    it claims to.
    """
    reactant = graph.reaction.reactants[0].molecule
    if not movements:
        raise MechanismValidationError("rule produced no electron movements", step=step)
    for m in movements:
        for side_name, ref in (("source", m.source), ("target", m.target)):
            refs = [x for x in (ref.atom, *(ref.bond or ())) if x is not None]
            for idx in refs:
                if not 0 <= idx < reactant.num_atoms:
                    raise MechanismValidationError(
                        f"movement {side_name} index {idx} out of range "
                        f"(reactant has {reactant.num_atoms} atoms)",
                        step=step,
                    )
        if m.kind == MovementKind.LONE_PAIR_DONATION and (
            m.source.atom is None or m.target.bond is None
        ):
            raise MechanismValidationError(
                "lone_pair_donation requires an atom source and a bond target",
                step=step,
            )
        if m.kind == MovementKind.BOND_BREAKING and m.source.bond is None:
            raise MechanismValidationError(
                "bond_breaking requires a bond source", step=step
            )
        if m.kind == MovementKind.BOND_FORMATION and m.target.bond is None:
            raise MechanismValidationError(
                "bond_formation requires a bond target", step=step
            )
        if m.kind == MovementKind.RESONANCE_SHIFT and (
            m.source.bond is None or m.target.bond is None
        ):
            raise MechanismValidationError(
                "resonance_shift requires bond source and target", step=step
            )
    changes = bond_changes(graph, pairing)
    referenced = _movement_bond_pairs(movements)
    for a, b, _ro, _po in changes:
        if _canonical_pair(a, b) not in referenced:
            raise MechanismValidationError(
                f"bond change ({a}, {b}) is not explained by any movement",
                step=step,
            )


def step_details(step: MechanismStep) -> dict[str, Any]:
    """Structured per-step fields for serialization.

    Returns reacting atom indices, bond changes and charge changes;
    with the step's movements and order this determines reacting atoms/
    bonds, electron movement, bond/charge changes and ordering. Pure
    function of the step's reaction (recomputes the bounded mapping).
    """
    mapping = map_reaction(step.reaction)
    if mapping.graph is None:
        raise MechanismValidationError(
            f"cannot map step {step.order} reaction: {mapping.reason}",
            step=step.order,
        )
    pairing = pair_atoms(mapping.graph)
    reactant = step.reaction.reactants[0].molecule
    changes = bond_changes(mapping.graph, pairing)
    atoms = sorted(
        _movement_atoms(step.movements) | {i for change in changes for i in change[:2]}
    )
    atoms = [i for i in atoms if i < reactant.num_atoms]
    return {
        "reacting_atoms": atoms,
        "bond_changes": [
            {"atom1": a, "atom2": b, "reactant_order": ro, "product_order": po}
            for a, b, ro, po in changes
        ],
        "charge_changes": list(charge_changes(mapping.graph, pairing)),
    }

# Rules (MechanismRule protocol implementations)
#
# Each rule pattern-matches the raw graphs through a *signature*: the
# shape of the heavy bond changes plus the exact charge-delta map over the
# augmented pairing. Signatures are mutually exclusive across rules, so
# first-match selection is deterministic and attribution is verifiable.
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Sn2Rule(MechanismRule):
    """Concerted substitution: one bond breaks, one forms, same carbon."""

    name: str = "sn2"

    def applies(self, graph: ReactionGraph) -> bool:
        """Exactly one C-LG break and one new bond at that carbon."""
        return _sn2_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Nucleophile lone pair forms C-Nu as the C-LG pair leaves LG."""
        pattern = _sn2_pattern(graph)
        if pattern is None:
            raise MechanismValidationError("sn2 pattern missing in apply()")
        center, lg, nu = pattern
        return (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=nu),
                target=ArrowRef(bond=_canonical_pair(center, nu)),
            ),
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(center, lg)),
                target=ArrowRef(atom=lg),
            ),
        )


def _sn2_pattern(graph: ReactionGraph) -> tuple[int, int, int] | None:
    """(center carbon, leaving halogen, nucleophile) for the SN2 signature."""
    reactant, _product = _sides(graph)
    pairing = pair_atoms(graph)
    changes = bond_changes(graph, pairing)
    if len(changes) != 2:
        return None
    broken = [(a, b) for a, b, ro, po in changes if (ro, po) == (1, 0)]
    formed = [(a, b) for a, b, ro, po in changes if (ro, po) == (0, 1)]
    if len(broken) != 1 or len(formed) != 1:
        return None
    shared = set(broken[0]) & set(formed[0])
    if len(shared) != 1:
        return None
    center = shared.pop()
    lg = broken[0][0] if broken[0][1] == center else broken[0][1]
    nu = formed[0][0] if formed[0][1] == center else formed[0][1]
    if _z(reactant, center) != 6 or _z(reactant, lg) not in HALOGENS:
        return None
    if not (_z(reactant, nu) in {7, 8, 16, 53} or _q(reactant, nu) < 0):
        return None
    deltas = _charge_deltas(graph, pairing)
    if deltas != {nu: 1, lg: -1}:
        return None
    return center, lg, nu


@dataclass(frozen=True, slots=True)
class HeterolysisRule(MechanismRule):
    """C-LG ionization to a carbocation/halide pair (SN1/E1 step 1)."""

    name: str = "heterolysis"

    def applies(self, graph: ReactionGraph) -> bool:
        """One C-halogen bond breaks; the pair ends charge-separated."""
        return _heterolysis_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """The C-LG bond pair leaves with the halogen."""
        pattern = _heterolysis_pattern(graph)
        if pattern is None:
            raise MechanismValidationError("heterolysis pattern missing in apply()")
        center, lg = pattern
        return (
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(center, lg)),
                target=ArrowRef(atom=lg),
            ),
        )


def _heterolysis_pattern(graph: ReactionGraph) -> tuple[int, int] | None:
    """(carbocation carbon, leaving halogen) for the ionization signature."""
    reactant, _product = _sides(graph)
    pairing = pair_atoms(graph)
    changes = bond_changes(graph, pairing)
    if len(changes) != 1:
        return None
    a, b, ro, po = changes[0]
    if (ro, po) != (1, 0):
        return None
    deltas = _charge_deltas(graph, pairing)
    centers = [i for i in (a, b) if _z(reactant, i) == 6 and deltas.get(i) == 1]
    leaving = [i for i in (a, b) if _z(reactant, i) in HALOGENS and deltas.get(i) == -1]
    if len(centers) != 1 or len(leaving) != 1:
        return None
    if centers[0] == leaving[0]:
        return None
    if set(deltas) != {centers[0], leaving[0]}:
        return None
    return centers[0], leaving[0]


@dataclass(frozen=True, slots=True)
class Sn1CaptureRule(MechanismRule):
    """A nucleophile lone pair bonds to a carbocation (SN1 step 2)."""

    name: str = "sn1_capture"

    def applies(self, graph: ReactionGraph) -> bool:
        """Exactly one new bond forms at a +1 carbon center."""
        return _sn1_capture_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Nucleophile lone pair forms the C-Nu bond."""
        pattern = _sn1_capture_pattern(graph)
        if pattern is None:
            raise MechanismValidationError("sn1_capture pattern missing in apply()")
        center, nu = pattern
        return (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=nu),
                target=ArrowRef(bond=_canonical_pair(center, nu)),
            ),
        )


def _sn1_capture_pattern(graph: ReactionGraph) -> tuple[int, int] | None:
    """(carbocation carbon, nucleophile) for the capture signature."""
    reactant, _product = _sides(graph)
    pairing = pair_atoms(graph)
    changes = bond_changes(graph, pairing)
    if len(changes) != 1:
        return None
    a, b, ro, po = changes[0]
    if (ro, po) != (0, 1):
        return None
    deltas = _charge_deltas(graph, pairing)
    centers = [i for i in (a, b) if _z(reactant, i) == 6 and deltas.get(i) == -1]
    nus = [i for i in (a, b) if i not in centers and deltas.get(i) == 1]
    if len(centers) != 1 or len(nus) != 1:
        return None
    nu = nus[0]
    if not (_z(reactant, nu) in HALOGENS | {7, 8, 16} or _q(reactant, nu) < 0):
        return None
    if set(deltas) != {centers[0], nu}:
        return None
    return centers[0], nu


def _pi_and_lg_pair(
    graph: ReactionGraph,
) -> tuple[int, int, int] | None:
    """Shared E2/E1cB-elimination geometry (cb, ca, leaving halogen).

    Signature: exactly two heavy changes -- a C-C order increase (1->2)
    and a C-halogen break (1->0) sharing exactly one atom (the alpha
    carbon). Returns ``None`` when the shape or element roles differ.
    """
    reactant, _product = _sides(graph)
    pairing = pair_atoms(graph)
    changes = bond_changes(graph, pairing)
    if len(changes) != 2:
        return None
    increasing = [(a, b) for a, b, ro, po in changes if (ro, po) == (1, 2)]
    breaking = [(a, b) for a, b, ro, po in changes if (ro, po) == (1, 0)]
    if len(increasing) != 1 or len(breaking) != 1:
        return None
    shared = set(increasing[0]) & set(breaking[0])
    if len(shared) != 1:
        return None
    ca = shared.pop()
    cb = increasing[0][0] if increasing[0][1] == ca else increasing[0][1]
    lg = breaking[0][0] if breaking[0][1] == ca else breaking[0][1]
    if _z(reactant, ca) != 6 or _z(reactant, cb) != 6:
        return None
    if _z(reactant, lg) not in HALOGENS:
        return None
    return cb, ca, lg


@dataclass(frozen=True, slots=True)
class E2Rule(MechanismRule):
    """Concerted elimination: LG leaves as the pi bond forms (E2)."""

    name: str = "e2"

    def applies(self, graph: ReactionGraph) -> bool:
        """C-LG + beta C-H + anionic base + neutral beta carbon."""
        return _e2_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Base takes the beta H; the C-H pair forms pi; LG takes the pair."""
        pattern = _e2_pattern(graph)
        if pattern is None:
            raise MechanismValidationError("e2 pattern missing in apply()")
        cb, ca, lg, base, h = pattern
        return (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=base),
                target=ArrowRef(bond=_canonical_pair(h, base)),
            ),
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(cb, h)),
                target=ArrowRef(bond=_canonical_pair(cb, ca)),
            ),
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(ca, lg)),
                target=ArrowRef(atom=lg),
            ),
        )


def _e2_pattern(graph: ReactionGraph) -> tuple[int, int, int, int, int] | None:
    """(cb, ca, lg, base, h) for the concerted E2 signature."""
    reactant, product = _sides(graph)
    pairing = pair_atoms(graph)
    geometry = _pi_and_lg_pair(graph)
    if geometry is None:
        return None
    cb, ca, lg = geometry
    deltas = _charge_deltas(graph, pairing)
    bases = [i for i, d in deltas.items() if d == 1 and i not in (cb, ca, lg)]
    if len(bases) != 1 or set(deltas) != {lg, bases[0]}:
        return None
    base = bases[0]
    if _z(reactant, base) not in {7, 8} or _q(reactant, base) != -1:
        return None
    if deltas.get(lg) != -1 or _q(reactant, cb) != 0:
        return None
    r_cb = len(_children(reactant, cb))
    r_base = len(_children(reactant, base))
    if r_cb < 1:
        return None
    if len(_children(product, pairing.r2p[cb])) != r_cb - 1:
        return None
    if len(_children(product, pairing.r2p[base])) != r_base + 1:
        return None
    h = _children(reactant, cb)[0]
    return cb, ca, lg, base, h


@dataclass(frozen=True, slots=True)
class E1DeprotonationRule(MechanismRule):
    """Base removes a beta H from a carbocation (E1 step 2)."""

    name: str = "e1_deprotonation"

    def applies(self, graph: ReactionGraph) -> bool:
        """Carbocation center + explicit beta H + base gaining one H."""
        return _e1_deprotonation_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Base lone pair takes H; the C-H pair becomes the C-C pi bond."""
        pattern = _e1_deprotonation_pattern(graph)
        if pattern is None:
            raise MechanismValidationError("e1_deprotonation pattern missing in apply()")
        cb, ca, base, h = pattern
        return (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=base),
                target=ArrowRef(bond=_canonical_pair(h, base)),
            ),
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(cb, h)),
                target=ArrowRef(bond=_canonical_pair(cb, ca)),
            ),
        )


def _e1_deprotonation_pattern(graph: ReactionGraph) -> tuple[int, int, int, int] | None:
    """(cb, ca, base, h) for carbocation deprotonation."""
    reactant, product = _sides(graph)
    pairing = pair_atoms(graph)
    changes = bond_changes(graph, pairing)
    if len(changes) != 1:
        return None
    a, b, ro, po = changes[0]
    if (ro, po) != (1, 2):
        return None
    if _z(reactant, a) != 6 or _z(reactant, b) != 6:
        return None
    deltas = _charge_deltas(graph, pairing)
    ca_cands = [i for i in (a, b) if _q(reactant, i) == 1 and deltas.get(i) == -1]
    if len(ca_cands) != 1:
        return None
    ca = ca_cands[0]
    cb = b if a == ca else a
    bases = [i for i, d in deltas.items() if d == 1 and i != ca]
    if len(bases) != 1 or set(deltas) != {ca, bases[0]}:
        return None
    base = bases[0]
    if _z(reactant, base) not in {7, 8}:
        return None
    if any(_z(reactant, j) in HALOGENS for j in reactant.get_neighbors(ca)):
        return None
    r_cb = len(_children(reactant, cb))
    if r_cb < 1 or len(_children(product, pairing.r2p[cb])) != r_cb - 1:
        return None
    if len(_children(product, pairing.r2p[base])) != len(_children(reactant, base)) + 1:
        return None
    h = _children(reactant, cb)[0]
    return cb, ca, base, h


@dataclass(frozen=True, slots=True)
class E1cbDeprotonationRule(MechanismRule):
    """Base removes a beta H forming a carbanion (E1cB step 1)."""

    name: str = "e1cb_deprotonation"

    def applies(self, graph: ReactionGraph) -> bool:
        """C-LG intact; base takes one H; beta carbon becomes carbanion."""
        return _e1cb_deprotonation_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Base takes H; the C-H pair lands on the beta carbon."""
        pattern = _e1cb_deprotonation_pattern(graph)
        if pattern is None:
            raise MechanismValidationError(
                "e1cb_deprotonation pattern missing in apply()"
            )
        cb, base, h = pattern
        return (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=base),
                target=ArrowRef(bond=_canonical_pair(h, base)),
            ),
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(cb, h)),
                target=ArrowRef(atom=cb),
            ),
        )


def _e1cb_deprotonation_pattern(graph: ReactionGraph) -> tuple[int, int, int] | None:
    """(cb, base, h) for carbanion-forming deprotonation."""
    reactant, product = _sides(graph)
    pairing = pair_atoms(graph)
    if bond_changes(graph, pairing) != ():
        return None
    deltas = _charge_deltas(graph, pairing)
    carbanions = [i for i, d in deltas.items() if d == -1]
    if len(carbanions) != 1 or len(deltas) != 2:
        return None
    cb = carbanions[0]
    if _z(reactant, cb) != 6:
        return None
    bases = [i for i, d in deltas.items() if d == 1]
    if len(bases) != 1:
        return None
    base = bases[0]
    if _z(reactant, base) not in {7, 8} or _q(reactant, base) != -1:
        return None
    # The C-LG bond must exist on a carbon adjacent to the carbanion.
    lg_found = False
    for j in reactant.get_neighbors(cb):
        if _z(reactant, j) != 6:
            continue
        if any(_z(reactant, k) in HALOGENS for k in reactant.get_neighbors(j)):
            lg_found = True
    if not lg_found:
        return None
    r_cb = len(_children(reactant, cb))
    if r_cb < 1 or len(_children(product, pairing.r2p[cb])) != r_cb - 1:
        return None
    if len(_children(product, pairing.r2p[base])) != len(_children(reactant, base)) + 1:
        return None
    h = _children(reactant, cb)[0]
    return cb, base, h


@dataclass(frozen=True, slots=True)
class E1cbEliminationRule(MechanismRule):
    """Carbanion expels the leaving group as pi forms (E1cB step 2)."""

    name: str = "e1cb_elimination"

    def applies(self, graph: ReactionGraph) -> bool:
        """Carbanion beta to C-LG; pi forms; LG leaves anionic."""
        return _e1cb_elimination_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Carbanion lone pair forms pi; the C-LG pair leaves with LG."""
        pattern = _e1cb_elimination_pattern(graph)
        if pattern is None:
            raise MechanismValidationError(
                "e1cb_elimination pattern missing in apply()"
            )
        cb, ca, lg = pattern
        return (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=cb),
                target=ArrowRef(bond=_canonical_pair(cb, ca)),
            ),
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(ca, lg)),
                target=ArrowRef(atom=lg),
            ),
        )


def _e1cb_elimination_pattern(graph: ReactionGraph) -> tuple[int, int, int] | None:
    """(cb, ca, lg) for the carbanion elimination signature."""
    reactant, product = _sides(graph)
    pairing = pair_atoms(graph)
    geometry = _pi_and_lg_pair(graph)
    if geometry is None:
        return None
    cb, ca, lg = geometry
    deltas = _charge_deltas(graph, pairing)
    if deltas != {cb: 1, lg: -1}:
        return None
    if _q(reactant, cb) != -1:
        return None
    if len(_children(product, pairing.r2p[cb])) != len(_children(reactant, cb)):
        return None
    return cb, ca, lg


@dataclass(frozen=True, slots=True)
class ElectrophilicAdditionRule(MechanismRule):
    """H-X addition across a substitution-symmetric alkene (net step)."""

    name: str = "electrophilic_addition"

    def applies(self, graph: ReactionGraph) -> bool:
        """Equal alkene substitution; H and X land on the alkene carbons."""
        return _addition_pattern(graph, require_markovnikov=False) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Pi pair forms C-H; the H-X pair forms C-X."""
        pattern = _addition_pattern(graph, require_markovnikov=False)
        if pattern is None:
            raise MechanismValidationError(
                "electrophilic_addition pattern missing in apply()"
            )
        a, b, ch, cx, x, h = pattern
        return _addition_movements(a, b, ch, cx, x, h)


@dataclass(frozen=True, slots=True)
class MarkovnikovAdditionRule(MechanismRule):
    """H-X addition with X on the more substituted alkene carbon."""

    name: str = "markovnikov_addition"

    def applies(self, graph: ReactionGraph) -> bool:
        """X lands on the alkene carbon with strictly more C substituents."""
        return _addition_pattern(graph, require_markovnikov=True) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Pi pair forms C-H; the H-X pair forms C-X."""
        pattern = _addition_pattern(graph, require_markovnikov=True)
        if pattern is None:
            raise MechanismValidationError(
                "markovnikov_addition pattern missing in apply()"
            )
        a, b, ch, cx, x, h = pattern
        return _addition_movements(a, b, ch, cx, x, h)


def _addition_movements(
    a: int, b: int, ch: int, cx: int, x: int, h: int
) -> tuple[ElectronMovement, ...]:
    """Shared net-step movement construction for H-X additions."""
    return (
        ElectronMovement(
            kind=MovementKind.BOND_BREAKING,
            source=ArrowRef(bond=_canonical_pair(a, b)),
            target=ArrowRef(bond=_canonical_pair(ch, h)),
        ),
        ElectronMovement(
            kind=MovementKind.BOND_BREAKING,
            source=ArrowRef(bond=_canonical_pair(h, x)),
            target=ArrowRef(bond=_canonical_pair(cx, x)),
        ),
    )


def _addition_pattern(
    graph: ReactionGraph, *, require_markovnikov: bool
) -> tuple[int, int, int, int, int, int] | None:
    """(a, b, ch, cx, x, h) for an H-X/alkene addition, or ``None``.

    ``a``/``b`` are the reactant alkene carbons; ``ch`` receives H,
    ``cx`` receives the halogen ``x``; ``h`` is the hydrogen that moves
    (the unique hydrogen bonded to ``x`` in the reactant).
    """
    reactant, product = _sides(graph)
    pairing = pair_atoms(graph)
    changes = bond_changes(graph, pairing)
    if len(changes) != 2:
        return None
    drops = [(a, b) for a, b, ro, po in changes if (ro, po) == (2, 1)]
    forms = [(a, b) for a, b, ro, po in changes if (ro, po) == (0, 1)]
    if len(drops) != 1 or len(forms) != 1:
        return None
    a, b = drops[0]
    if _z(reactant, a) != 6 or _z(reactant, b) != 6:
        return None
    f0, f1 = forms[0]
    hal_ends = [i for i in (f0, f1) if _z(reactant, i) in HALOGENS]
    c_ends = [i for i in (f0, f1) if _z(reactant, i) == 6]
    if len(hal_ends) != 1 or len(c_ends) != 1:
        return None
    x = hal_ends[0]
    cx = c_ends[0]
    if cx not in (a, b):
        return None
    ch = b if cx == a else a
    hx = _children(reactant, x)
    if len(hx) != 1:
        return None
    h = hx[0]
    if _charge_deltas(graph, pairing) != {}:
        return None
    if len(_children(product, pairing.r2p[x])) != 0:
        return None
    if len(_children(product, pairing.r2p[ch])) != len(_children(reactant, ch)) + 1:
        return None
    if len(_children(product, pairing.r2p[cx])) != len(_children(reactant, cx)):
        return None
    sub_x = _carbon_substituents(reactant, cx)
    sub_h = _carbon_substituents(reactant, ch)
    if require_markovnikov and not sub_x > sub_h:
        return None
    if not require_markovnikov and sub_x != sub_h:
        return None
    return a, b, ch, cx, x, h


@dataclass(frozen=True, slots=True)
class CarbonylAdditionRule(MechanismRule):
    """Nucleophilic addition to a carbonyl giving an alkoxide."""

    name: str = "carbonyl_addition"

    def applies(self, graph: ReactionGraph) -> bool:
        """Anionic C (or neutral N) nucleophile adds; C=O becomes C-O(-)."""
        return _carbonyl_addition_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Nucleophile lone pair forms C-Nu; the pi pair lands on oxygen."""
        pattern = _carbonyl_addition_pattern(graph)
        if pattern is None:
            raise MechanismValidationError(
                "carbonyl_addition pattern missing in apply()"
            )
        c, o, nu = pattern
        return (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=nu),
                target=ArrowRef(bond=_canonical_pair(c, nu)),
            ),
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(c, o)),
                target=ArrowRef(atom=o),
            ),
        )


def _carbonyl_addition_pattern(graph: ReactionGraph) -> tuple[int, int, int] | None:
    """(carbonyl C, carbonyl O, nucleophile) for the addition signature."""
    reactant, product = _sides(graph)
    pairing = pair_atoms(graph)
    changes = bond_changes(graph, pairing)
    if len(changes) != 2:
        return None
    drops = [(a, b) for a, b, ro, po in changes if (ro, po) == (2, 1)]
    forms = [(a, b) for a, b, ro, po in changes if (ro, po) == (0, 1)]
    if len(drops) != 1 or len(forms) != 1:
        return None
    d0, d1 = drops[0]
    ox = [i for i in (d0, d1) if _z(reactant, i) == 8]
    cs = [i for i in (d0, d1) if _z(reactant, i) == 6]
    if len(ox) != 1 or len(cs) != 1:
        return None
    c, o = cs[0], ox[0]
    if c not in forms[0]:
        return None
    nu = forms[0][0] if forms[0][1] == c else forms[0][1]
    if _z(reactant, nu) not in {6, 7}:
        return None
    comps = reactant.connected_components()
    comp_of = {atom: idx for idx, cc in enumerate(comps) for atom in cc}
    if comp_of.get(nu) == comp_of.get(c):
        return None
    deltas = _charge_deltas(graph, pairing)
    if deltas != {o: -1, nu: 1}:
        return None
    if len(_children(product, pairing.r2p[c])) != len(_children(reactant, c)):
        return None
    if len(_children(product, pairing.r2p[o])) != len(_children(reactant, o)):
        return None
    return c, o, nu


@dataclass(frozen=True, slots=True)
class TetrahedralCollapseRule(MechanismRule):
    """Alkoxide lone pair reforms C=O and expels a leaving group."""

    name: str = "tetrahedral_collapse"

    def applies(self, graph: ReactionGraph) -> bool:
        """Tetrahedral alkoxide collapses to carbonyl + anionic LG."""
        return _collapse_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """O lone pair forms the pi bond; the C-LG pair leaves with LG."""
        pattern = _collapse_pattern(graph)
        if pattern is None:
            raise MechanismValidationError(
                "tetrahedral_collapse pattern missing in apply()"
            )
        c, o, lg = pattern
        return (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=o),
                target=ArrowRef(bond=_canonical_pair(c, o)),
            ),
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(c, lg)),
                target=ArrowRef(atom=lg),
            ),
        )


def _collapse_pattern(graph: ReactionGraph) -> tuple[int, int, int] | None:
    """(carbon, alkoxide O, leaving heteroatom) for tetrahedral collapse."""
    reactant, product = _sides(graph)
    pairing = pair_atoms(graph)
    changes = bond_changes(graph, pairing)
    if len(changes) != 2:
        return None
    increases = [(a, b) for a, b, ro, po in changes if (ro, po) == (1, 2)]
    breaking = [(a, b) for a, b, ro, po in changes if (ro, po) == (1, 0)]
    if len(increases) != 1 or len(breaking) != 1:
        return None
    i0, i1 = increases[0]
    ox = [k for k in (i0, i1) if _z(reactant, k) == 8 and _q(reactant, k) == -1]
    cs = [k for k in (i0, i1) if _z(reactant, k) == 6]
    if len(ox) != 1 or len(cs) != 1:
        return None
    o, c = ox[0], cs[0]
    if c not in breaking[0]:
        return None
    lg = breaking[0][0] if breaking[0][1] == c else breaking[0][1]
    if _z(reactant, lg) not in HALOGENS | {8} or lg == o:
        return None
    deltas = _charge_deltas(graph, pairing)
    if deltas != {o: 1, lg: -1}:
        return None
    if len(_children(product, pairing.r2p[o])) != len(_children(reactant, o)):
        return None
    if len(_children(product, pairing.r2p[lg])) != len(_children(reactant, lg)):
        return None
    return c, o, lg


@dataclass(frozen=True, slots=True)
class ProtonTransferRule(MechanismRule):
    """Bronsted proton transfer between two heteroatoms."""

    name: str = "proton_transfer"

    def applies(self, graph: ReactionGraph) -> bool:
        """One H moves heteroatom->heteroatom with mirrored charge shifts."""
        return _proton_transfer_pattern(graph) is not None

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """The donor-H pair leaves the donor and forms the acceptor-H bond."""
        pattern = _proton_transfer_pattern(graph)
        if pattern is None:
            raise MechanismValidationError(
                "proton_transfer pattern missing in apply()"
            )
        donor, acceptor, h = pattern
        return (
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=_canonical_pair(donor, h)),
                target=ArrowRef(bond=_canonical_pair(acceptor, h)),
            ),
        )


def _proton_transfer_pattern(graph: ReactionGraph) -> tuple[int, int, int] | None:
    """(donor, acceptor, moving H) for a validated proton transfer."""
    reactant, product = _sides(graph)
    pairing = pair_atoms(graph)
    if bond_changes(graph, pairing) != ():
        return None
    deltas = _charge_deltas(graph, pairing)
    if len(deltas) != 2:
        return None
    donors = [i for i, d in deltas.items() if d == -1]
    acceptors = [i for i, d in deltas.items() if d == 1]
    if len(donors) != 1 or len(acceptors) != 1:
        return None
    donor, acceptor = donors[0], acceptors[0]
    if donor == acceptor:
        return None
    if _z(reactant, donor) in {1, 6} or _z(reactant, acceptor) in {1, 6}:
        return None
    donor_children = _children(reactant, donor)
    if len(donor_children) < 1:
        return None
    if len(_children(product, pairing.r2p[donor])) != len(donor_children) - 1:
        return None
    if (
        len(_children(product, pairing.r2p[acceptor]))
        != len(_children(reactant, acceptor)) + 1
    ):
        return None
    return donor, acceptor, donor_children[0]


DEFAULT_RULES: tuple[MechanismRule, ...] = (
    Sn2Rule(),
    HeterolysisRule(),
    Sn1CaptureRule(),
    E2Rule(),
    E1DeprotonationRule(),
    E1cbDeprotonationRule(),
    E1cbEliminationRule(),
    MarkovnikovAdditionRule(),
    ElectrophilicAdditionRule(),
    CarbonylAdditionRule(),
    TetrahedralCollapseRule(),
    ProtonTransferRule(),
)
"""Fixed rule priority (deterministic first-match selection)."""


# ---------------------------------------------------------------------------
# Scenario / result / engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MechanismScenario:
    """A curated sequence of elementary reactions declaring a mechanism.

    Attributes:
        name: Catalogue id the executed rules must match.
        steps: Elementary reactions in order (single component per side,
            mappable by the M33 mapper). Step i's product graph must be
            identical to step i+1's reactant graph.
        expect_applicable: When ``False`` the scenario declares itself a
            negative case: no rule may match. If a rule *does* match,
            that is reported as a validation error.
    """

    name: str
    steps: tuple[Reaction, ...]
    expect_applicable: bool = True


@dataclass(frozen=True, slots=True)
class MechanismResult:
    """Executed mechanism: trace plus per-step rule attribution.

    Attributes:
        mechanism: Catalogue id that was declared and verified.
        trace: The validated M33 :class:`MechanismTrace`.
        rule_names: Executed rule id per step (equals the spec's
            ``rule_sequence`` by construction).
    """

    mechanism: str
    trace: MechanismTrace
    rule_names: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize through the io architecture (JSON-ready dict)."""
        from chemengine.io.serialization import mechanism_trace_to_dict

        return mechanism_trace_to_dict(self)

    def to_json(self, indent: int | None = 2) -> str:
        """Serialize to a stable JSON string."""
        from chemengine.io.serialization import mechanism_trace_to_json

        return mechanism_trace_to_json(self, indent=indent)


class MechanismEngine:
    """Executes curated electron-pushing rules into validated traces.

    The engine is stateless and deterministic: rule priority is the fixed
    :data:`DEFAULT_RULES` order (or the caller-supplied order), pattern
    searches scan ascending atom indices, and every proposal is validated
    (conservation, charge-aware valence, movement/change coverage, trace
    ordering, chain continuity, rule attribution) before entering the
    trace. No input graph is ever mutated.

    Args:
        rules: Optional explicit rule list (priority = order). Defaults
            to :data:`DEFAULT_RULES`.
    """

    def __init__(self, rules: Sequence[MechanismRule] | None = None) -> None:
        """Store the fixed rule priority list."""
        self._rules: tuple[MechanismRule, ...] = (
            tuple(rules) if rules is not None else DEFAULT_RULES
        )
        self._by_name = {rule.name: rule for rule in self._rules}

    @property
    def rules(self) -> tuple[MechanismRule, ...]:
        """The fixed rule priority list."""
        return self._rules

    def select_rule(self, graph: ReactionGraph) -> MechanismRule | None:
        """First applicable rule in fixed priority order, or ``None``."""
        for rule in self._rules:
            if rule.applies(graph):
                return rule
        return None

    def explain(self, scenario: MechanismScenario) -> MechanismResult:
        """Execute a scenario into a validated :class:`MechanismResult`.

        Per step, in order: chain continuity (canonical SMILES), bounded
        mapping, atom/charge conservation, structural + valence checks,
        then rule selection, movement construction and coverage
        validation. Finally the executed rule sequence must equal the
        catalogue entry's ``rule_sequence``.

        Raises:
            MechanismError: unknown mechanism name.
            MechanismNotApplicableError: no rule recognizes a step (or a
                declared negative case correctly declined -- callers
                testing negatives catch this type).
            MechanismValidationError: mapping, conservation, valence,
                movement coverage, chain continuity, a rule matching a
                declared negative, or attribution failure. Nothing is
                repaired silently.
        """
        spec = CATALOGUE.get(scenario.name)
        if spec is None:
            raise MechanismError(
                f"unknown mechanism {scenario.name!r}; known: "
                f"{', '.join(CATALOGUE)}"
            )
        if not scenario.steps:
            raise MechanismValidationError("scenario has no steps")
        steps: list[MechanismStep] = []
        rule_names: list[str] = []
        previous_product: str | None = None
        for idx, reaction in enumerate(scenario.steps, start=1):
            if previous_product is not None:
                current = _canonical_smiles(reaction.reactants[0].molecule)
                if current != previous_product:
                    raise MechanismValidationError(
                        f"step {idx} reactant does not continue the previous "
                        f"product ({current!r} != {previous_product!r})",
                        step=idx,
                    )
            mapping = map_reaction(reaction)
            if mapping.graph is None:
                raise MechanismValidationError(
                    f"cannot map reaction: {mapping.reason}", step=idx
                )
            graph = mapping.graph
            issues = validate_conservation(graph)
            issues += validate_side(
                reaction.reactants[0].molecule, label=f"step {idx} reactant"
            )
            issues += validate_side(
                reaction.products[0].molecule, label=f"step {idx} product"
            )
            if issues:
                raise MechanismValidationError("; ".join(issues), step=idx)
            rule = self.select_rule(graph)
            if rule is None:
                raise MechanismNotApplicableError(
                    f"no curated rule recognizes this transformation "
                    f"(declared mechanism {scenario.name!r})",
                    step=idx,
                )
            if not scenario.expect_applicable:
                raise MechanismValidationError(
                    f"rule {rule.name!r} applied, but the scenario declares "
                    "expect_applicable=False",
                    step=idx,
                )
            movements = rule.apply(graph)
            pairing = pair_atoms(graph)
            validate_movements(graph, movements, pairing, step=idx)
            steps.append(
                MechanismStep(
                    reaction=reaction,
                    movements=movements,
                    order=idx,
                    description=f"{spec.id} step {idx}: {rule.name}",
                )
            )
            rule_names.append(rule.name)
            previous_product = _canonical_smiles(
                reaction.products[0].molecule
            )
        if tuple(rule_names) != spec.rule_sequence:
            raise MechanismValidationError(
                f"executed rules {tuple(rule_names)} do not match the "
                f"declared {spec.id} sequence {spec.rule_sequence}"
            )
        trace = MechanismTrace.from_steps(steps)
        return MechanismResult(
            mechanism=spec.id,
            trace=trace,
            rule_names=tuple(rule_names),
        )

    def identify(self, reaction: Reaction) -> str | None:
        """Deterministically identify a *single-step* mechanism, or ``None``.

        Scans :data:`CATALOGUE` in insertion order and returns the first
        entry whose single rule applies to the mapped reaction.
        Multi-step mechanisms (``sn1``, ``e1``, ``e1cb``,
        ``carbonyl_addition_elimination``) are never returned here --
        they require :meth:`explain` over their full step sequence.
        Unmappable or unrecognized inputs return ``None``.
        """
        mapping = map_reaction(reaction)
        if mapping.graph is None:
            return None
        graph = mapping.graph
        if validate_conservation(graph):
            return None
        for spec in CATALOGUE.values():
            if len(spec.rule_sequence) != 1:
                continue
            rule = self._by_name.get(spec.rule_sequence[0])
            if rule is not None and rule.applies(graph):
                return spec.id
        return None


def _canonical_smiles(mol: MolecularGraph) -> str:
    """Canonical SMILES for chain-continuity checks (local import)."""
    from chemengine.parsing.smiles import serialize_smiles

    return serialize_smiles(mol)


def register_mechanism_algorithms(registry: AlgorithmRegistry | None = None) -> None:
    """Register the mechanism engine and catalogue with an AlgorithmRegistry.

    Follows the established pattern (``register_formula_parser`` et al.):
    an explicit function, called by ``ChemEngineAPI`` built-in setup and
    by tests against any registry (global when ``registry`` is ``None``).
    No import side effects -- this module performs no registration at
    import time, so the ``import chemengine`` first-import gate cannot be
    affected (the package root never imports this module lazily or not).
    """
    from chemengine.core.registry import AlgorithmEntry, get_global_registry

    target = registry if registry is not None else get_global_registry()
    engine = MechanismEngine()
    target.register(
        AlgorithmEntry(
            domain="reactions.mechanisms",
            name="engine",
            version="1.0.0",
            algorithm=engine.explain,
            input_type=MechanismScenario,
            output_type=MechanismResult,
            tags=frozenset({"mechanism", "reactions", "deterministic"}),
        )
    )
    target.register(
        AlgorithmEntry(
            domain="reactions.mechanisms",
            name="catalogue",
            version="1.0.0",
            algorithm=list_mechanisms,
            input_type=None,
            output_type=tuple,
            tags=frozenset({"mechanism", "reactions", "deterministic"}),
        )
    )



# ---------------------------------------------------------------------------
