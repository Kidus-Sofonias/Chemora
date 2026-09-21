"""Architecture-level tests for the mechanism interfaces (M33, roadmap 12.5).

M33 explicitly ships *architecture only* — no executable mechanism engine.
These tests verify the extension points behave as documented: validation,
serialization, ordering, and the rule protocol. Deliberately absent: any
test that pushes electrons through a real transformation.
"""

from __future__ import annotations

import pytest

from chemengine.parsing.smiles import parse_smiles
from chemengine.reactions.mapping import map_reaction
from chemengine.reactions.mechanisms import (
    ArrowEndpoint,
    ArrowRef,
    ElectronMovement,
    MechanismRule,
    MechanismStep,
    MechanismTrace,
    MovementKind,
)
from chemengine.reactions.reaction import Reaction, ReactionComponent


def _reaction(smiles: str) -> Reaction:
    left, right = smiles.split(">>")
    return Reaction(
        reactants=(ReactionComponent(parse_smiles(left.strip())),),
        products=(ReactionComponent(parse_smiles(right.strip())),),
    )


class TestArrowRef:
    """ArrowRef endpoint invariants."""

    def test_atom_endpoint(self) -> None:
        """An atom endpoint serializes correctly."""
        ref = ArrowRef(atom=3)
        assert ref.atom == 3
        assert ref.bond is None
        assert ref.to_dict() == {"atom": 3, "bond": None}

    def test_bond_endpoint_normalizes_ordering(self) -> None:
        """A bond endpoint stores the unordered pair."""
        ref = ArrowRef(bond=(2, 5))
        assert ref.atom is None
        assert ref.bond == (2, 5)

    def test_both_endpoints_rejected(self) -> None:
        """Setting both endpoints is invalid."""
        with pytest.raises(ValueError, match="exactly one"):
            ArrowRef(atom=1, bond=(1, 2))

    def test_no_endpoint_rejected(self) -> None:
        """Setting neither endpoint is invalid."""
        with pytest.raises(ValueError, match="exactly one"):
            ArrowRef()

    def test_self_bond_rejected(self) -> None:
        """A bond must reference two distinct atoms."""
        with pytest.raises(ValueError, match="must differ"):
            ArrowRef(bond=(4, 4))


class TestElectronMovement:
    """Electron movement validation and serialization."""

    def test_paired_movement(self) -> None:
        """Default is a 2-electron movement."""
        mv = ElectronMovement(
            kind=MovementKind.BOND_FORMATION,
            source=ArrowRef(atom=0),
            target=ArrowRef(bond=(1, 2)),
        )
        assert mv.electron_count == 2
        d = mv.to_dict()
        assert d["kind"] == "bond_formation"
        assert d["electron_count"] == 2
        assert d["source"]["atom"] == 0
        assert d["target"]["bond"] == [1, 2]

    def test_single_electron_radical(self) -> None:
        """Radical steps carry a single electron."""
        mv = ElectronMovement(
            kind=MovementKind.SINGLE_ELECTRON,
            source=ArrowRef(bond=(0, 1)),
            target=ArrowRef(atom=2),
            electron_count=1,
        )
        assert mv.electron_count == 1

    def test_invalid_electron_count_rejected(self) -> None:
        """Only 1 or 2 electrons are valid."""
        with pytest.raises(ValueError, match="electron_count"):
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=(0, 1)),
                target=ArrowRef(atom=2),
                electron_count=3,
            )


class TestMechanismTrace:
    """Trace ordering and serialization."""

    def test_orders_steps(self) -> None:
        """from_steps sorts by step order."""
        rxn1 = _reaction("CCO>>CC=O")
        rxn2 = _reaction("CC=O>>CC(=O)O")
        step_a = MechanismStep(reaction=rxn1, order=2, description="second")
        step_b = MechanismStep(reaction=rxn2, order=1, description="first")
        trace = MechanismTrace.from_steps([step_a, step_b])
        assert [s.order for s in trace.steps] == [1, 2]
        assert len(trace) == 2

    def test_duplicate_order_rejected(self) -> None:
        """Step orders must be strictly increasing."""
        rxn = _reaction("CCO>>CC=O")
        steps = [
            MechanismStep(reaction=rxn, order=1),
            MechanismStep(reaction=rxn, order=1),
        ]
        with pytest.raises(ValueError, match="strictly increasing"):
            MechanismTrace.from_steps(steps)

    def test_empty_trace(self) -> None:
        """An empty trace is valid and serializes."""
        trace = MechanismTrace.from_steps([])
        assert len(trace) == 0
        assert trace.to_dict() == {"steps": []}

    def test_serialization_roundtrip_shape(self) -> None:
        """Serialized steps expose movement kinds and endpoints."""
        rxn = _reaction("CCO>>CC=O")
        mv = ElectronMovement(
            kind=MovementKind.LONE_PAIR_DONATION,
            source=ArrowRef(atom=2),
            target=ArrowRef(bond=(0, 2)),
        )
        trace = MechanismTrace.from_steps(
            [MechanismStep(reaction=rxn, movements=(mv,), order=1, description="ox")]
        )
        d = trace.to_dict()
        assert len(d["steps"]) == 1
        assert d["steps"][0]["movements"][0]["kind"] == "lone_pair_donation"


class TestMechanismRuleProtocol:
    """The future rule-engine contract."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """The protocol exposes the two rule methods."""
        assert hasattr(MechanismRule, "applies")
        assert hasattr(MechanismRule, "apply")

    def test_a_conforming_implementation_satisfies_protocol(self) -> None:
        """A future engine plugs in by implementing the protocol.

        Proven with a stub that performs no chemistry of its own.
        """

        class StubRule:
            name = "stub"

            def applies(self, graph: object) -> bool:
                return True

            def apply(self, graph: object) -> tuple[ElectronMovement, ...]:
                return ()

        assert isinstance(StubRule(), MechanismRule)

    def test_endpoints_enum_stable(self) -> None:
        """Endpoint values are part of the contract."""
        assert ArrowEndpoint.BOND.value == "bond"
        assert ArrowEndpoint.ATOM.value == "atom"


class TestArchitectureBoundary:
    """M33 ships interfaces only — no mechanism engine."""

    def test_module_executes_no_chemistry(self) -> None:
        """No engine entry point exists in the architecture module."""
        import chemengine.reactions.mechanisms as mod

        public = set(getattr(mod, "__all__", []))
        assert public == {
            "ArrowEndpoint",
            "ArrowRef",
            "ElectronMovement",
            "MechanismRule",
            "MechanismStep",
            "MechanismTrace",
            "MovementKind",
        }
        # No callable factory that could "run" a mechanism.
        for name in public:
            obj = getattr(mod, name)
            if callable(obj) and not isinstance(obj, type):
                raise AssertionError(f"unexpected engine function: {name}")

    def test_step_references_mapped_reaction(self) -> None:
        """Steps reference reactions; mapping machinery stays independent."""
        rxn = _reaction("CCO>>CC=O")
        result = map_reaction(rxn)
        step = MechanismStep(reaction=rxn, order=1)
        assert step.reaction is rxn
        # The mapping machinery remains available for future engines.
        assert result.ok
