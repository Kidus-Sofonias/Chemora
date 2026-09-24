"""M34 mechanism engine tests: reference oracle and invariants.

The version-controlled dataset ``tests/data/mechanism_reference.json``
is the regression oracle for :class:`chemengine.reactions.engine.MechanismEngine`.
Every case was reviewed against chemistry before being baked in (see each
case's ``note``); the suites here prove the engine still matches the
reviewed behavior: positives explain green, negatives decline or are
rejected with the documented structured error, every step conserves atoms
and charge, execution is deterministic, inputs are never mutated, traces
round-trip through the io architecture, and the first-import gate holds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chemengine.parsing.smiles import parse_smiles, serialize_smiles
from chemengine.reactions.engine import (
    CATALOGUE,
    DEFAULT_RULES,
    MechanismEngine,
    MechanismError,
    MechanismNotApplicableError,
    MechanismScenario,
    MechanismValidationError,
    list_mechanisms,
)
from chemengine.reactions.mechanisms import (
    ArrowRef,
    ElectronMovement,
    MechanismRule,
    MovementKind,
)
from chemengine.reactions.reaction import Reaction, ReactionComponent

DATA = Path(__file__).parent / "data" / "mechanism_reference.json"


def _load() -> dict:
    """Load the reviewed mechanism reference oracle."""
    return json.loads(DATA.read_text(encoding="utf-8"))


def _ids() -> list[str]:
    """All oracle case ids, in file order."""
    return [case["id"] for case in _load()["cases"]]


def _case(case_id: str) -> dict:
    """Resolve one oracle case by id."""
    by_id = {c["id"]: c for c in _load()["cases"]}
    return by_id[case_id]


def _reaction(spec: str) -> Reaction:
    """Build a single-component-per-side reaction from ``A>>B`` SMILES."""
    left, right = spec.split(">>")
    return Reaction(
        reactants=(ReactionComponent(parse_smiles(left.strip())),),
        products=(ReactionComponent(parse_smiles(right.strip())),),
    )


def _scenario(case: dict) -> MechanismScenario:
    """Build the declared scenario for an oracle case."""
    return MechanismScenario(
        name=case["mechanism"],
        steps=tuple(_reaction(s) for s in case["steps"]),
        expect_applicable=case["type"] == "positive",
    )


@pytest.fixture(params=_ids())
def case(request: pytest.FixtureRequest) -> dict:
    """Parametrized reference case, resolved from the oracle by id."""
    return _case(request.param)  # type: ignore[no-any-return]


@pytest.fixture(params=[c["id"] for c in _load()["cases"] if c["type"] == "positive"])
def positive_case(request: pytest.FixtureRequest) -> dict:
    """Parametrized positive-only reference case."""
    return _case(request.param)  # type: ignore[no-any-return]


@pytest.fixture(params=[c["id"] for c in _load()["cases"] if c["type"] == "negative"])
def negative_case(request: pytest.FixtureRequest) -> dict:
    """Parametrized negative-only reference case."""
    return _case(request.param)  # type: ignore[no-any-return]


class TestReferenceMeta:
    """The oracle itself must be honest and large enough."""

    def test_meta_declares_reviewed_oracle(self) -> None:
        """Metadata marks the set reviewed, complete, and milestone-tagged."""
        meta = _load()["meta"]
        assert meta["reviewed"] is True
        assert meta["milestone"] == "M34"
        assert meta["case_count"] == len(_load()["cases"])

    def test_at_least_25_cases(self) -> None:
        """The scoped acceptance floor is >= 25 curated scenarios."""
        assert len(_load()["cases"]) >= 25

    def test_all_ten_mechanisms_covered(self) -> None:
        """Every curated mechanism appears in the positive cases."""
        covered = set(_load()["meta"]["mechanisms_covered"])
        assert covered == set(CATALOGUE)
        assert len(CATALOGUE) >= 10

    def test_positive_and_negative_mix(self) -> None:
        """The oracle contains both positive and applicability-negative cases."""
        types = {c["type"] for c in _load()["cases"]}
        assert types == {"positive", "negative"}

    def test_every_case_has_a_note(self) -> None:
        """Each scenario carries its reviewed chemistry note."""
        for entry in _load()["cases"]:
            assert entry["note"].strip(), entry["id"]


class TestReferenceOracle:
    """Every reference case must reproduce the reviewed behavior."""

    def test_positive_cases_explain_green(self, positive_case: dict) -> None:
        """A positive scenario executes into a validated trace."""
        engine = MechanismEngine()
        result = engine.explain(_scenario(positive_case))
        spec = CATALOGUE[positive_case["mechanism"]]
        assert result.mechanism == positive_case["mechanism"]
        assert result.rule_names == spec.rule_sequence
        assert len(result.trace) == len(positive_case["steps"])
        assert [s.order for s in result.trace.steps] == list(
            range(1, len(positive_case["steps"]) + 1)
        )
        assert all(s.description for s in result.trace.steps)
        assert all(s.movements for s in result.trace.steps)

    def test_negative_cases_decline_or_reject(self, negative_case: dict) -> None:
        """A negative scenario raises its documented structured error."""
        engine = MechanismEngine()
        expected = {
            "not_applicable": MechanismNotApplicableError,
            "validation": MechanismValidationError,
        }[negative_case["expect_error"]]
        with pytest.raises(MechanismError) as excinfo:
            engine.explain(_scenario(negative_case))
        assert isinstance(excinfo.value, expected)
        assert type(excinfo.value) is expected
        assert str(excinfo.value)


class TestConservation:
    """Every step of every positive scenario conserves atoms and charge."""

    def test_each_step_balanced(self, positive_case: dict) -> None:
        """Atom counts, formulas and total charge match across each step."""
        for spec in positive_case["steps"]:
            reaction = _reaction(spec)
            left = reaction.reactants[0].molecule
            right = reaction.products[0].molecule
            assert reaction.is_balanced(), spec
            assert left.molecular_formula == right.molecular_formula, spec
            assert sum(a.formal_charge for a in left.atoms) == sum(
                a.formal_charge for a in right.atoms
            ), spec


class TestDeterminism:
    """Identical inputs produce identical mechanisms, rules and traces."""

    def test_repeated_explain_is_json_identical(self) -> None:
        """Two runs of one multi-step and one single-step case match exactly."""
        engine = MechanismEngine()
        for case_id in ("sn1-tbutyl-iodide", "sn2-methanol", "mk-propene"):
            scenario = _scenario(_case(case_id))
            first = engine.explain(scenario).to_json()
            second = engine.explain(scenario).to_json()
            assert first == second, case_id

    def test_repeated_identify_is_stable(self) -> None:
        """identify() is a fixed function of the reaction."""
        engine = MechanismEngine()
        reaction = _reaction("CC=C.[H]Br>>CC(C)Br")
        assert engine.identify(reaction) == engine.identify(reaction)
        assert engine.identify(reaction) == "markovnikov_addition"


class TestNoMutation:
    """The engine never mutates input graphs."""

    def test_graphs_unchanged_after_explain(self) -> None:
        """Canonical SMILES and graph hashes are identical before and after."""
        engine = MechanismEngine()
        for case_id in ("e1cb-ethyl", "ae-ester-ammonia", "sn2-methanol"):
            scenario = _scenario(_case(case_id))
            before = []
            for reaction in scenario.steps:
                for component in (*reaction.reactants, *reaction.products):
                    g = component.molecule
                    before.append((serialize_smiles(g), g.graph_hash))
            engine.explain(scenario)
            after = []
            for reaction in scenario.steps:
                for component in (*reaction.reactants, *reaction.products):
                    g = component.molecule
                    after.append((serialize_smiles(g), g.graph_hash))
            assert before == after, case_id


class TestSerialization:
    """Traces round-trip through the io architecture, stably."""

    def test_dict_round_trip_is_identical(self) -> None:
        """to_dict -> dict_to -> to_dict reproduces the document exactly."""
        from chemengine.io.serialization import (
            dict_to_mechanism_trace,
            mechanism_trace_to_dict,
        )

        engine = MechanismEngine()
        for case_id in ("sn2-methanol", "sn1-tbutyl-iodide", "e1cb-ethyl"):
            result = engine.explain(_scenario(_case(case_id)))
            doc = mechanism_trace_to_dict(result)
            rebuilt = dict_to_mechanism_trace(doc)
            assert mechanism_trace_to_dict(rebuilt) == doc, case_id

    def test_json_round_trip_is_identical(self) -> None:
        """JSON serialization is byte-stable across a round trip."""
        engine = MechanismEngine()
        result = engine.explain(_scenario(_case("ae-ester-ammonia")))
        text = result.to_json()
        from chemengine.io.serialization import json_to_mechanism_trace

        rebuilt = json_to_mechanism_trace(text)
        assert rebuilt.to_json() == text

    def test_step_entries_are_structured(self) -> None:
        """Each step documents atoms, movements, bond/charge changes, rule."""
        engine = MechanismEngine()
        result = engine.explain(_scenario(_case("sn2-methanol")))
        doc = result.to_dict()
        assert doc["schema"] == "chemengine.mechanism_trace/1"
        assert doc["mechanism"] == "sn2"
        step = doc["steps"][0]
        for key in (
            "order",
            "description",
            "rule",
            "reaction",
            "movements",
            "reacting_atoms",
            "bond_changes",
            "charge_changes",
        ):
            assert key in step, key
        assert step["rule"] == "sn2"
        assert len(step["bond_changes"]) == 2
        assert step["charge_changes"]
        assert step["reacting_atoms"]
        assert step["movements"][0]["kind"] in {m.value for m in MovementKind}

    def test_reaction_round_trip(self) -> None:
        """reaction_to_dict/dict_to_reaction preserves the reaction."""
        from chemengine.io.serialization import dict_to_reaction, reaction_to_dict

        reaction = _reaction("C[Cl].[OH-]>>C[O][H].[Cl-]")
        rebuilt = dict_to_reaction(reaction_to_dict(reaction))
        assert reaction_to_dict(rebuilt) == reaction_to_dict(reaction)
        assert rebuilt.is_balanced()

    def test_bad_schema_rejected(self) -> None:
        """Foreign documents are refused, never silently repaired."""
        from chemengine.io.serialization import dict_to_mechanism_trace

        with pytest.raises(MechanismValidationError, match="schema"):
            dict_to_mechanism_trace({"schema": "other/9", "steps": []})

    def test_rule_step_mismatch_rejected(self) -> None:
        """rule_names and per-step rules must agree on load."""
        from chemengine.io.serialization import mechanism_trace_to_dict

        engine = MechanismEngine()
        doc = mechanism_trace_to_dict(
            engine.explain(_scenario(_case("sn2-methanol")))
        )
        doc["rule_names"] = ["heterolysis"]
        from chemengine.io.serialization import dict_to_mechanism_trace

        with pytest.raises(MechanismValidationError, match="rule_names"):
            dict_to_mechanism_trace(doc)


class TestRegistry:
    """The engine registers through the existing registry architecture."""

    def test_registration_and_discovery(self) -> None:
        """Engine + catalogue register, get, resolve and list correctly."""
        from chemengine.core.registry import AlgorithmRegistry
        from chemengine.reactions.engine import register_mechanism_algorithms

        registry = AlgorithmRegistry()
        register_mechanism_algorithms(registry)
        assert ("reactions.mechanisms", "engine") in registry
        assert ("reactions.mechanisms", "catalogue") in registry
        entries = registry.list(domain="reactions.mechanisms")
        assert len(entries) == 2
        entry = registry.get("reactions.mechanisms", "engine")
        assert "deterministic" in entry.tags
        resolved = registry.resolve(
            domain="reactions.mechanisms", tags={"mechanism"}
        )
        assert resolved.name in {"engine", "catalogue"}

    def test_registered_engine_executes(self) -> None:
        """The registered engine callable runs explain on a scenario."""
        from chemengine.core.registry import AlgorithmRegistry
        from chemengine.reactions.engine import register_mechanism_algorithms

        registry = AlgorithmRegistry()
        register_mechanism_algorithms(registry)
        entry = registry.get("reactions.mechanisms", "engine")
        result = entry.algorithm(_scenario(_case("sn2-methanol")))
        assert result.mechanism == "sn2"

    def test_tool_interface_registers_engine(self) -> None:
        """ChemEngineAPI built-in setup exposes the mechanism engine."""
        from chemengine.core.tool_interface import ChemEngineAPI

        api = ChemEngineAPI()
        registry = api.registry
        assert ("reactions.mechanisms", "engine") in registry


class TestFirstImportGate:
    """The engine stays out of the bare ``import chemengine`` path."""

    def test_bare_import_does_not_load_engine(self) -> None:
        """Fresh interpreter: root import never pulls reactions.engine."""
        import subprocess
        import sys

        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [
                sys.executable,
                "-c",
                "import chemengine, sys; "
                "assert 'chemengine.reactions.engine' not in sys.modules, "
                "'mechanism engine imported by package root'",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr


class TestCatalogue:
    """The curated catalogue is complete, explicit and protocol-clean."""

    def test_ten_named_mechanisms(self) -> None:
        """Exactly the ten scoped mechanisms are available."""
        expected = {
            "sn2", "sn1", "e2", "e1", "e1cb",
            "electrophilic_addition", "markovnikov_addition",
            "carbonyl_addition", "carbonyl_addition_elimination",
            "proton_transfer",
        }
        assert set(CATALOGUE) == expected
        assert [m.id for m in list_mechanisms()] == list(CATALOGUE)

    def test_constraints_are_explicit(self) -> None:
        """Every mechanism documents its applicability constraints."""
        for spec in CATALOGUE.values():
            assert spec.title
            assert spec.constraints, spec.id
            assert all(line.strip() for line in spec.constraints)

    def test_rule_sequences_resolve(self) -> None:
        """Declared rule sequences reference real rules in DEFAULT_RULES."""
        known = {rule.name for rule in DEFAULT_RULES}
        assert len(DEFAULT_RULES) == 12
        for spec in CATALOGUE.values():
            assert spec.rule_sequence, spec.id
            for rule_name in spec.rule_sequence:
                assert rule_name in known, (spec.id, rule_name)

    def test_rules_satisfy_protocol(self) -> None:
        """All twelve rules satisfy the frozen M33 MechanismRule protocol."""
        for rule in DEFAULT_RULES:
            assert isinstance(rule, MechanismRule)
            assert rule.name
            assert callable(rule.applies) and callable(rule.apply)

    def test_get_mechanism(self) -> None:
        """Lookup returns the spec and None for unknown names."""
        from chemengine.reactions.engine import get_mechanism

        assert get_mechanism("sn2").id == "sn2"
        assert get_mechanism("nope") is None


class TestStructuredErrors:
    """Failures are typed, messageful ChemEngine errors -- never silent."""

    def test_unknown_mechanism_is_base_error(self) -> None:
        """A scenario naming an unknown mechanism raises MechanismError."""
        engine = MechanismEngine()
        scenario = MechanismScenario(
            name="not_a_mechanism", steps=(_reaction("CC>>CC"),)
        )
        with pytest.raises(MechanismError) as excinfo:
            engine.explain(scenario)
        assert type(excinfo.value) is MechanismError
        assert "unknown mechanism" in str(excinfo.value)

    def test_empty_scenario_rejected(self) -> None:
        """A scenario without steps is a validation error."""
        engine = MechanismEngine()
        with pytest.raises(MechanismValidationError, match="no steps"):
            engine.explain(MechanismScenario(name="sn2", steps=()))

    def test_chain_break_rejected(self) -> None:
        """Step 2 must continue step 1's product exactly."""
        engine = MechanismEngine()
        scenario = MechanismScenario(
            name="sn1",
            steps=(
                _reaction("CC(C)(C)Cl.[I-]>>[C+](C)(C)C.[Cl-].[I-]"),
                _reaction("CC(C)(C)Cl.[Br-]>>CC(C)(C)Br.[Cl-]"),
            ),
        )
        with pytest.raises(MechanismValidationError, match="continue"):
            engine.explain(scenario)

    def test_movement_coverage_rejects_unexplained_change(self) -> None:
        """A movement set omitting a bond change is rejected."""
        from chemengine.reactions.engine import pair_atoms, validate_movements
        from chemengine.reactions.mapping import map_reaction

        reaction = _reaction("C[Cl].[OH-]>>C[O][H].[Cl-]")
        graph = map_reaction(reaction).graph
        assert graph is not None
        pairing = pair_atoms(graph)
        partial = (
            ElectronMovement(
                kind=MovementKind.LONE_PAIR_DONATION,
                source=ArrowRef(atom=2),
                target=ArrowRef(bond=(0, 2)),
            ),
        )
        with pytest.raises(MechanismValidationError, match="not explained"):
            validate_movements(graph, partial, pairing, step=1)

    def test_out_of_range_movement_rejected(self) -> None:
        """Endpoint indices must address real reactant atoms."""
        from chemengine.reactions.engine import pair_atoms, validate_movements
        from chemengine.reactions.mapping import map_reaction

        reaction = _reaction("C[Cl].[OH-]>>C[O][H].[Cl-]")
        graph = map_reaction(reaction).graph
        assert graph is not None
        bad = (
            ElectronMovement(
                kind=MovementKind.BOND_BREAKING,
                source=ArrowRef(bond=(0, 999)),
                target=ArrowRef(atom=1),
            ),
        )
        with pytest.raises(MechanismValidationError, match="out of range"):
            validate_movements(graph, bad, pair_atoms(graph), step=1)


class TestIdentify:
    """Single-step identification is deterministic and honest."""

    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            ("C[Cl].[OH-]>>C[O][H].[Cl-]", "sn2"),
            ("C([H])C[Cl].C[O-]>>C=C.C[O][H].[Cl-]", "e2"),
            ("CC=C.[H]Br>>CC(C)Br", "markovnikov_addition"),
            ("C=C.[H]Br>>C([H])CBr", "electrophilic_addition"),
            ("C=O.[C-]#N>>[O-]C[C]#N", "carbonyl_addition"),
            ("CO.[H]Cl>>C([H])[OH2+].[Cl-]", "proton_transfer"),
            ("CC(C)(C)Cl.[I-]>>[C+](C)(C)C.[Cl-].[I-]", None),
            ("CC>>CC", None),
            ("CC=C.[H]Br>>CCCBr", None),
        ],
    )
    def test_identify(self, spec: str, expected: str | None) -> None:
        """Known single-step patterns identify; others return None."""
        engine = MechanismEngine()
        assert engine.identify(_reaction(spec)) == expected


class TestValenceAndBoundedWork:
    """Charge-aware valence and bounded execution."""

    def test_onium_intermediates_pass_valence(self) -> None:
        """Hydronium/oxonium-style species are not false-positived."""
        from chemengine.reactions.engine import validate_side

        hydronium = parse_smiles("[H][OH2+].[Cl-]")
        assert validate_side(hydronium, label="hydronium") == []

    def test_genuine_valence_violation_detected(self) -> None:
        """A carbon with five single bonds is rejected."""
        from chemengine.core.graph import MolecularGraphBuilder
        from chemengine.reactions.engine import validate_side

        builder = MolecularGraphBuilder()
        carbon = builder.add_atom(atomic_number=6)
        for _ in range(5):
            neighbor = builder.add_atom(atomic_number=9)
            builder.add_bond(atom1=carbon, atom2=neighbor)
        mol = builder.build()
        issues = validate_side(mol, label="overvalent")
        assert issues, "expected a valence issue"
        assert "bond-order sum" in issues[0]

    def test_whole_oracle_is_bounded(self) -> None:
        """All cases (positive and negative) execute well inside a budget.

        Guards against accidental unbounded search/recursion: the whole
        oracle normally finishes in well under a second; 30 seconds is a
        deliberately generous CI-safe ceiling.
        """
        import time

        engine = MechanismEngine()
        start = time.perf_counter()
        for entry in _load()["cases"]:
            try:
                engine.explain(_scenario(entry))
            except MechanismError:
                pass
        elapsed = time.perf_counter() - start
        assert elapsed < 30.0, f"oracle execution took {elapsed:.1f}s"
