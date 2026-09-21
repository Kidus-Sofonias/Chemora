"""M33 Phase 4.3 — reaction atom-mapping reference-set oracle tests.

The version-controlled dataset ``tests/data/reaction_mapping_reference.json``
is the regression oracle for :func:`chemengine.reactions.mapping.map_reaction`.
Every case was individually reviewed against chemistry before being baked in
(see each case's ``note``); the suite here proves the implementation still
matches the reviewed behavior.

Reference-set composition (53 cases):
- 49 mapped cases: mapped/lost/gained/changed counts + ambiguity flag
- 3 explicit-failure cases: no common element, oversized partners, and a
  documented search-budget boundary (aromatic nitration with an unmappable N)
- 1 parse-guard case: empty SMILES rejected at parse level
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from chemengine.parsing.errors import SmilesSyntaxError
from chemengine.parsing.smiles import parse_smiles
from chemengine.reactions.mapping import map_reaction
from chemengine.reactions.reaction import Reaction, ReactionComponent

DATA = Path(__file__).parent / "data" / "reaction_mapping_reference.json"


def _load() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def _reaction(smiles: str) -> Reaction:
    left, right = smiles.split(">>")
    return Reaction(
        reactants=(ReactionComponent(parse_smiles(left.strip())),),
        products=(ReactionComponent(parse_smiles(right.strip())),),
    )


def _ids() -> list[str]:
    return [case["id"] for case in _load()["cases"]]


@pytest.fixture(params=_ids())
def case(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Parametrized reference case, resolved from the oracle by id."""
    by_id = {c["id"]: c for c in _load()["cases"]}
    return by_id[request.param]  # type: ignore[no-any-return]


class TestReferenceSet:
    """Every reference case must reproduce its reviewed behavior."""

    def test_meta_declares_reviewed_oracle(self) -> None:
        """Oracle metadata is honest: reviewed, complete, and large enough."""
        meta = _load()["meta"]
        assert meta["reviewed"] is True
        assert meta["num_cases"] == len(_load()["cases"])
        assert len(_load()["cases"]) >= 50  # M33 acceptance: 50+ reference set

    def test_case(self, case: dict[str, Any]) -> None:
        """Each reference case reproduces its reviewed mapping behavior."""
        if case["expect"] == "parse_error":
            with pytest.raises(SmilesSyntaxError):
                _reaction(case["smiles"])
            return

        result = map_reaction(_reaction(case["smiles"]))

        if case["expect"] == "failed":
            assert result.graph is None
            assert result.ok is False
            assert case["reason_contains"] in result.reason
            return

        assert result.ok is True
        graph = result.graph
        assert graph is not None
        assert result.ambiguous is case["ambiguous"]
        assert len(graph.mapped_atoms()) == case["mapped"]
        assert len(graph.lost_atoms()) == case["lost"]
        assert len(graph.gained_atoms()) == case["gained"]
        assert graph.num_changed_bonds() == case["changed"]
        assert len(graph.formed_bonds) == case["formed"]
        assert len(graph.broken_bonds) == case["broken"]

    def test_case_is_deterministic(self, case: dict[str, Any]) -> None:
        """Mapping is a pure function of the input: run twice, compare."""
        if case["expect"] == "parse_error":
            pytest.skip("parse-guard case: nothing to compare")
        first = map_reaction(_reaction(case["smiles"]))
        second = map_reaction(_reaction(case["smiles"]))
        assert first.ok == second.ok
        assert first.ambiguous == second.ambiguous
        if first.graph is not None and second.graph is not None:
            assert first.graph.to_dict() == second.graph.to_dict()


class TestReactionGraphInvariants:
    """Structural invariants independent of any single reference case."""

    def test_mapped_pairs_are_element_consistent(self) -> None:
        """Every mapped pair refers to valid, element-equal atoms."""
        reaction = _reaction("CCO>>CCO")
        result = map_reaction(reaction)
        assert result.graph is not None
        assert result.graph.is_consistent() is True

    def test_reactant_to_product_roundtrip(self) -> None:
        """The dict view matches the mapped-atom view exactly."""
        result = map_reaction(_reaction("CCO>>CCO"))
        assert result.graph is not None
        r_to_p = result.graph.reactant_to_product()
        assert set(r_to_p.keys()) == {a.reactant_index for a in result.graph.mapped_atoms()}
        assert set(r_to_p.values()) == {a.product_index for a in result.graph.mapped_atoms()}

    def test_roles_partition_heavy_atoms(self) -> None:
        """mapped+lost and mapped+gained reproduce each side's heavy count."""
        result = map_reaction(_reaction("CCO.O>>CCO"))
        assert result.graph is not None
        graph = result.graph
        total = len(graph.mapped_atoms()) + len(graph.lost_atoms()) + len(graph.gained_atoms())
        reactant_heavy = sum(
            1
            for a in graph.reaction.reactants[0].molecule.atoms
            if a.atomic_number != 1
        )
        product_heavy = sum(
            1
            for a in graph.reaction.products[0].molecule.atoms
            if a.atomic_number != 1
        )
        # mapped+lost = reactant heavy atoms; mapped+gained = product heavy
        assert len(graph.mapped_atoms()) + len(graph.lost_atoms()) == reactant_heavy
        assert len(graph.mapped_atoms()) + len(graph.gained_atoms()) == product_heavy
        assert total == reactant_heavy + product_heavy - len(graph.mapped_atoms())

    def test_to_dict_shape(self) -> None:
        """Serialization exposes counts and flat bond tuples."""
        result = map_reaction(_reaction("CC=O>>CCO"))
        assert result.graph is not None
        d = result.graph.to_dict()
        assert d["num_mapped"] == 3
        assert d["num_lost"] == 0
        assert d["num_gained"] == 0
        for key in ("atoms", "changed_bonds", "formed_bonds", "broken_bonds"):
            assert key in d
        assert len(d["changed_bonds"]) == 1  # C=O -> C-O

    def test_changed_bond_reports_order_transition(self) -> None:
        """Hydrogenation reports exactly one bond-order change, 2 -> 1."""
        result = map_reaction(_reaction("C=C>>CC"))
        assert result.graph is not None
        # The double bond becomes single: exactly one changed bond, 2 -> 1.
        assert result.graph.num_changed_bonds() == 1
        old, new = result.graph.changed_bonds[0][2], result.graph.changed_bonds[0][3]
        assert (old, new) == (2, 1)

    def test_explicit_failure_never_returns_partial_graph(self) -> None:
        """Failures carry a reason and never a half-built graph."""
        result = map_reaction(_reaction("C>>O"))
        assert result.graph is None
        assert result.reason  # explanation is always provided

    def test_multi_component_rejected_explicitly(self) -> None:
        """Multi-component correspondence is out of scope and explicit."""
        rxn = Reaction(
            reactants=(
                ReactionComponent(parse_smiles("CCO")),
                ReactionComponent(parse_smiles("CCO")),
            ),
            products=(ReactionComponent(parse_smiles("CCO")),),
        )
        result = map_reaction(rxn)
        assert result.ok is False
        assert "exactly one" in result.reason

    def test_symmetric_identity_flagged_asymmetric_not(self) -> None:
        """Symmetry yields ambiguity; asymmetric molecules do not."""
        assert map_reaction(_reaction("C1CC1>>C1CC1")).ambiguous is True
        assert map_reaction(_reaction("CCO>>CCO")).ambiguous is False
