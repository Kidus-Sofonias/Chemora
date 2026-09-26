"""Tests for the M38 forward reaction-prediction engine.

Covers:
    - Module constants and template catalogue surface area.
    - Oracle regression: each ``REFERENCE_ORACLE`` reactant fires the expected
      templates and yields the documented product molecular formulas.
    - Prediction (de)serialisation round-trip.
    - Registry + ``ChemEngineAPI`` wiring (registration, idempotency).
    - Lazy-import / import-speed gate.
"""

from __future__ import annotations

import subprocess
import sys

from chemengine.core.registry import AlgorithmRegistry
from chemengine.reactions.forward import (
    _CATALOGUE_PREFIX,
    FORWARD_REACTION_TEMPLATES,
    REFERENCE_ORACLE,
    ForwardReactionEngine,
    ForwardReactionTemplate,
    dict_to_forward_prediction,
    forward_prediction_to_dict,
    list_forward_reaction_templates,
    predict_reaction,
    register_forward_reaction_algorithms,
)


# ---------------------------------------------------------------------------
# Module constants & catalogue surface
# ---------------------------------------------------------------------------
def test_module_constants_and_catalogue() -> None:
    assert _CATALOGUE_PREFIX == "m38"
    assert len(FORWARD_REACTION_TEMPLATES) == 5
    expected_ids = {
        "m38-ester-saponification",
        "m38-alkene-hydrogenation",
        "m38-e2-elimination",
        "m38-alcohol-dehydration",
        "m38-hydrolysis-alkyl-halide",
    }
    assert {t.id for t in FORWARD_REACTION_TEMPLATES} == expected_ids
    returned = list_forward_reaction_templates()
    assert {t.id for t in returned} == expected_ids
    assert isinstance(returned, tuple)
    assert all(isinstance(t, ForwardReactionTemplate) for t in returned)
    assert all(hasattr(t, "find") and hasattr(t, "priority") for t in returned)
    # Catalogue is ordered by priority (descending); ties share a priority and
    # are broken deterministically by template id inside the engine.
    priorities = [t.priority for t in FORWARD_REACTION_TEMPLATES]
    assert priorities == sorted(priorities, reverse=True), priorities


# ---------------------------------------------------------------------------
# Oracle regression
# ---------------------------------------------------------------------------
def test_reference_oracle_matches() -> None:
    for smiles, spec in REFERENCE_ORACLE.items():
        preds = predict_reaction(smiles)
        fired = {p.template_id for p in preds}
        assert spec["must_match"].issubset(fired), (smiles, fired)
        assert spec["must_not_match"].isdisjoint(fired), (smiles, fired)
        formulas = {
            graph.molecular_formula
            for pred in preds
            for graph in pred.product_graphs
        }
        assert spec["product_formulas"] == formulas, (smiles, formulas)


def test_engine_predict_matches_convenience_wrapper() -> None:
    # The bounded engine and the thin ``predict_reaction`` wrapper agree.
    engine = ForwardReactionEngine()
    direct = engine.predict("CCCl")
    wrapped = predict_reaction("CCCl")
    assert {p.template_id for p in direct} == {p.template_id for p in wrapped}


def test_no_templates_fire_on_unmatched_reactant() -> None:
    # Ethane has no halogen, OH, carbonyl or C=C - no M38 template can fire.
    assert predict_reaction("CC") == []


# ---------------------------------------------------------------------------
# Prediction (de)serialisation
# ---------------------------------------------------------------------------
def test_prediction_round_trip() -> None:
    preds = predict_reaction("CCCl")
    assert preds, "expected at least one prediction for chloroethane"
    data = forward_prediction_to_dict(preds[0])
    assert data["template_id"] == "m38-e2-elimination"
    assert "product_smiles" in data
    rebuilt = dict_to_forward_prediction(data)
    assert rebuilt.template_id == preds[0].template_id
    assert rebuilt.reactant_smiles == preds[0].reactant_smiles
    assert rebuilt.product_smiles == preds[0].product_smiles


# ---------------------------------------------------------------------------
# Registry + API wiring
# ---------------------------------------------------------------------------
def test_register_forward_reaction_algorithms_idempotent() -> None:
    registry = AlgorithmRegistry()
    assert ("reactions.forward", "predict") not in registry
    register_forward_reaction_algorithms(registry)
    register_forward_reaction_algorithms(registry)  # second call is a no-op
    assert ("reactions.forward", "predict") in registry
    assert ("reactions.forward", "catalogue") in registry
    assert (
        registry.get("reactions.forward", "predict").algorithm is predict_reaction
    )
    assert (
        registry.get("reactions.forward", "catalogue").algorithm
        is list_forward_reaction_templates
    )


def test_api_registers_forward_engine() -> None:
    from chemengine.core.tool_interface import ChemEngineAPI

    api = ChemEngineAPI()
    assert ("reactions.forward", "predict") in api._registry
    assert ("reactions.forward", "catalogue") in api._registry
    # Retrosynthesis wiring is untouched by the forward addition.
    assert ("reactions.retrosynthesis", "plan") in api._registry


# ---------------------------------------------------------------------------
# Lazy-import gate
# ---------------------------------------------------------------------------
def test_lazy_import_gate() -> None:
    code = (
        "import sys, chemengine; "
        "assert 'chemengine.reactions.forward' not in sys.modules"
    )
    subprocess.check_output([sys.executable, "-c", code], text=True)
