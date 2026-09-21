"""Mechanism architecture (M33, roadmap 12.5) — INTERFACES ONLY.

**This module deliberately contains no mechanism engine.** It establishes
the typed extension points a future mechanism engine will plug into:
electron-movement representation, reaction steps, traces, and the rule
protocol. No rule implementation ships here; no method in this module
executes chemistry. Any concrete electron-pushing logic belongs to a
future, separately-scoped milestone.

Why an explicit architecture milestone
--------------------------------------
Mechanism work (electron pushing, arrow formalism, rule application) is
the most error-prone area of computational chemistry. Shipping an
executable engine without first fixing the *representation* invites
ad-hoc, incompatible designs later. This module fixes the vocabulary:

- :class:`ElectronMovement` — one arrow in the arrow formalism
  (bond formation, bond breaking, lone-pair donation, single-electron
  movement for radical steps).
- :class:`MechanismStep` — one elementary step: the mapped
  :class:`~chemengine.reactions.reaction.Reaction` it transforms plus the
  electron movements that justify it, ordered with its neighbors.
- :class:`MechanismTrace` — the full sequence of steps connecting a
  starting material to a product, with validation of ordering and
  endpoints.
- :class:`MechanismRule` — the ``Protocol`` a future rule engine
  implements (``applies`` / ``apply``); rules return *validated
  proposals*, they do not mutate graphs in place.

All structures are frozen dataclasses referencing atom indices of the
:class:`~chemengine.core.graph.MolecularGraph` SSOT. Nothing here
computes electron flow — the classes exist so that future work has a
stable, testable contract, and so that the broader roadmap (12.x) can
be scheduled against concrete interfaces rather than intentions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from chemengine.reactions.mapping import ReactionGraph
    from chemengine.reactions.reaction import Reaction


class MovementKind(Enum):
    """Kind of electron movement (one arrow in the arrow formalism)."""

    BOND_FORMATION = "bond_formation"  # electron pair creates a new bond
    BOND_BREAKING = "bond_breaking"  # bond electron pair leaves the bond
    LONE_PAIR_DONATION = "lone_pair_donation"  # lone pair forms/extends a bond
    SINGLE_ELECTRON = "single_electron"  # radical: one electron moves
    RESONANCE_SHIFT = "resonance_shift"  # pi-system reorganization


class ArrowEndpoint(Enum):
    """Where an arrow starts or ends (source/target of electron flow)."""

    BOND = "bond"  # a bond between two atoms
    ATOM = "atom"  # an atom (lone pair, orbital, radical site)


@dataclass(frozen=True, slots=True)
class ArrowRef:
    """Reference to an arrow endpoint.

    Exactly one of ``atom`` / ``bond`` is set; the other is ``None``.
    Bond endpoints reference the (unordered) atom pair.
    """

    atom: int | None = None
    bond: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        """Enforce the exactly-one-endpoint and distinct-bond invariants."""
        if (self.atom is None) == (self.bond is None):
            raise ValueError(
                "ArrowRef requires exactly one of atom or bond (got "
                f"atom={self.atom!r}, bond={self.bond!r})"
            )
        if self.bond is not None:
            a, b = self.bond
            if a == b:
                raise ValueError(f"bond endpoints must differ (got {a}, {b})")

    def to_dict(self) -> dict[str, Any]:
        """Serialize (indices only)."""
        return {"atom": self.atom, "bond": list(self.bond) if self.bond else None}


@dataclass(frozen=True, slots=True)
class ElectronMovement:
    """One electron-pushing arrow.

    Attributes:
        kind: What kind of movement this is.
        source: Where the electrons start.
        target: Where they end.
        electron_count: 2 for paired movement, 1 for radical steps.
    """

    kind: MovementKind
    source: ArrowRef
    target: ArrowRef
    electron_count: int = 2

    def __post_init__(self) -> None:
        """Reject electron counts that are neither paired nor single."""
        if self.electron_count not in (1, 2):
            raise ValueError(
                f"electron_count must be 1 or 2 (got {self.electron_count})"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize (indices only)."""
        return {
            "kind": self.kind.value,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "electron_count": self.electron_count,
        }


@dataclass(frozen=True, slots=True)
class MechanismStep:
    """One elementary step of a mechanism.

    The step references the :class:`Reaction` whose reactant/product graphs
    it connects (a *mapped* reaction is strongly recommended so downstream
    consumers can follow atoms) and the electron movements that justify the
    transformation.
    """

    reaction: Reaction
    movements: tuple[ElectronMovement, ...] = ()
    order: int = 0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize (indices only, no molecule blobs)."""
        return {
            "order": self.order,
            "description": self.description,
            "movements": [m.to_dict() for m in self.movements],
        }


@dataclass(frozen=True, slots=True)
class MechanismTrace:
    """A validated sequence of mechanism steps from start to product.

    Created via :meth:`from_steps`, which enforces ordering (strictly
    increasing step numbers) — construction by hand is possible but the
    factory is the supported path.
    """

    steps: tuple[MechanismStep, ...] = field(default=())

    @classmethod
    def from_steps(cls, steps: Sequence[MechanismStep]) -> MechanismTrace:
        """Build a trace, enforcing strictly increasing step order.

        Raises:
            ValueError: step numbers are not strictly increasing.
        """
        ordered = tuple(sorted(steps, key=lambda s: s.order))
        for prev, curr in zip(ordered, ordered[1:]):
            if prev.order == curr.order:
                raise ValueError(
                    f"duplicate mechanism step order {curr.order!r}; "
                    "orders must be strictly increasing"
                )
        return cls(steps=ordered)

    def __len__(self) -> int:
        """Number of steps in the trace."""
        return len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        """Serialize (indices only)."""
        return {"steps": [s.to_dict() for s in self.steps]}


@runtime_checkable
class MechanismRule(Protocol):
    """Protocol for a future mechanism rule engine.

    A rule inspects a mapped reaction graph and either declines
    (``applies`` → False) or returns a validated proposal: the electron
    movements that would explain the transformation, plus a confidence
    note. Rules never mutate molecular graphs; the caller owns any
    application of the proposal.

    Implementing a real rule set is **future work**, explicitly out of
    scope for M33 (roadmap 12.5 is architecture only).
    """

    name: str

    def applies(self, graph: ReactionGraph) -> bool:
        """Whether this rule recognizes the transformation."""
        ...

    def apply(self, graph: ReactionGraph) -> tuple[ElectronMovement, ...]:
        """Propose the electron movements explaining the transformation."""
        ...


__all__ = [
    "ArrowEndpoint",
    "ArrowRef",
    "ElectronMovement",
    "MechanismRule",
    "MechanismStep",
    "MechanismTrace",
    "MovementKind",
]
