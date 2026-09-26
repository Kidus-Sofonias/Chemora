"""Tests for the M36 retrosynthetic engine (analysis, planning, wiring).

Covers:
    - Module constants and template catalogue surface area.
    - Oracle regression: the 5 REFERENCE_ORACLE targets fire exactly the
      expected templates, every disconnection is valid and heavy-atom
      conserved, and headline surgeries yield the documented products.
    - Engine planning: complete routes, root-vs-leaf terminal semantics,
      caps, and cycle-guard dedup.
    - Route (de)serialisation round-trip.
    - Registry + ``ChemEngineAPI`` wiring (registration, tool dispatch).
    - Lazy-import / import-speed gate.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from chemengine.core.graph import MolecularGraph
from chemengine.core.registry import AlgorithmRegistry
from chemengine.parsing.smiles import parse_smiles, serialize_smiles
from chemengine.reactions.retrosynthesis import (
    _CATALOGUE_PREFIX,
    REFERENCE_ORACLE,
    RETRO_SYNTHESIS_TEMPLATES,
    RetrosynthesisEngine,
    SynthesisRoute,
    dict_to_retrosynthesis_route,
    get_retrosynthetic_template,
    list_retrosynthetic_templates,
    plan_retrosynthesis,
    register_retrosynthesis_algorithms,
    retrosynthesis_route_to_dict,
)

# (target, template_id, expected set of precursor molecular formulas)
HEADLINE_PRODUCTS = [
    ("CC(=O)OC", "m36-ester-fischer", {"C2H4O2", "CH4O"}),  # acid + methanol
    ("CC(=O)N", "m36-amide-hydrolysis", {"C2H4O2", "H3N"}),  # acid + ammonia
    ("CCO", "m36-alcohol-to-alkyl-halide", {"C2H5Cl", "H2O"}),  # ethyl chloride + water
    ("CC(=O)C", "m36-retro-aldol", {"C2H4O2", "CH3Cl"}),  # acid + chloromethane
]

# (target, template_id, expected heavy-atom total of the precursors)
HEADLINE_CONSERVATION = [
    ("CC(=O)OC", "m36-ester-fischer", 6),  # 5 + 1 (new O)
    ("CC(=O)N", "m36-amide-hydrolysis", 5),  # 4 + 1 (new O)
    ("CCO", "m36-alcohol-to-alkyl-halide", 4),  # 3 + 1 (Cl)
    ("CC(=O)C", "m36-retro-aldol", 6),  # 4 + 2 (new O + Cl)
]


# ---------------------------------------------------------------------------
# Module constants & catalogue surface
# ---------------------------------------------------------------------------
def test_module_constants_and_catalogue() -> None:
    assert _CATALOGUE_PREFIX == "m36"
    assert len(RETRO_SYNTHESIS_TEMPLATES) == 8
    templates = list_retrosynthetic_templates()
    assert len(templates) == 8
    assert all(t.id.startswith("m36-") for t in templates)
    assert get_retrosynthetic_template("m36-ester-fischer").id == "m36-ester-fischer"
    with pytest.raises(KeyError):
        get_retrosynthetic_template("m36-does-not-exist")


def test_engine_has_default_templates() -> None:
    engine = RetrosynthesisEngine()
    assert len(engine.templates) == len(RETRO_SYNTHESIS_TEMPLATES)


# ---------------------------------------------------------------------------
# Oracle regression
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("target", list(REFERENCE_ORACLE))
def test_oracle_must_match_fires_and_conservation(target: str) -> None:
    spec = REFERENCE_ORACLE[target]
    graph = parse_smiles(target)
    fired = set()
    for tmpl in RETRO_SYNTHESIS_TEMPLATES:
        for disc in tmpl.matches(graph):
            fired.add(tmpl.id)
            # every returned disconnection must be chemically valid ...
            assert all(p.validate() == [] for p in disc.precursors)
            # ... and heavy-atom conserved (precursors >= target; matches() enforces
            # exact equality against target + added heavy internally).
            assert sum(p.num_heavy_atoms for p in disc.precursors) >= graph.num_heavy_atoms
    assert spec["must_match"].issubset(fired)
    assert (fired & spec.get("must_not_match", set())) == set()


def test_biphenyl_does_not_fire_retro_diels_alder() -> None:
    graph = parse_smiles("C1=CC=C(C=C1)C1=CC=CC=C1")
    assert not get_retrosynthetic_template("m36-retro-diels-alder").matches(graph)


@pytest.mark.parametrize("target,template_id,expected", HEADLINE_PRODUCTS)
def test_headline_surgery_products(target: str, template_id: str, expected: set) -> None:
    graph = parse_smiles(target)
    tmpl = get_retrosynthetic_template(template_id)
    discs = tmpl.matches(graph)
    assert discs, f"{template_id} should match {target}"
    for disc in discs:
        assert {p.molecular_formula for p in disc.precursors} == expected


@pytest.mark.parametrize("target,template_id,expected_total", HEADLINE_CONSERVATION)
def test_headline_heavy_atom_conservation(
    target: str, template_id: str, expected_total: int
) -> None:
    graph = parse_smiles(target)
    tmpl = get_retrosynthetic_template(template_id)
    for disc in tmpl.matches(graph):
        assert sum(p.num_heavy_atoms for p in disc.precursors) == expected_total


# ---------------------------------------------------------------------------
# Engine planning, caps, dedup
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("target", ["CC(=O)OC", "CC(=O)N", "CC(=O)C", "CCO"])
def test_plan_returns_complete_routes(target: str) -> None:
    routes = plan_retrosynthesis(target, max_depth=6, max_routes=20)
    assert routes, f"expected at least one route for {target}"
    assert all(isinstance(r, SynthesisRoute) for r in routes)
    # The root target must be disconnected (never treated as terminal).
    assert routes[0].num_steps >= 1
    assert routes[0].is_complete is True
    for route in routes:
        for step in route.steps:
            for precursor in step.candidate.precursors:
                assert precursor.validate() == []


def test_biphenyl_yields_single_available_route() -> None:
    routes = plan_retrosynthesis("C1=CC=C(C=C1)C1=CC=CC=C1", max_depth=4, max_routes=10)
    assert len(routes) == 1
    assert routes[0].num_steps == 0
    assert routes[0].is_complete is False  # too heavy to count as a building block


def test_max_routes_cap_is_respected() -> None:
    routes = plan_retrosynthesis("CC(=O)OC", max_depth=6, max_routes=3)
    assert len(routes) <= 3


def test_max_candidates_per_step_limits_branching() -> None:
    generous = plan_retrosynthesis(
        "CC(=O)OC", max_depth=4, max_candidates_per_step=5, max_routes=50
    )
    restricted = plan_retrosynthesis(
        "CC(=O)OC", max_depth=4, max_candidates_per_step=1, max_routes=50
    )
    assert len(restricted) <= len(generous)


def test_symmetric_disconnections_are_deduplicated() -> None:
    routes = plan_retrosynthesis("CC(=O)C", max_depth=6, max_routes=50)
    # Acetone: carbonyl-reduction + retro-aldol.  The two symmetric methyl
    # cuts collapse to a single retro-aldol route under the structural sig.
    aldol = [
        r for r in routes if any(s.candidate.template_id == "m36-retro-aldol" for s in r.steps)
    ]
    assert len(aldol) == 1
    assert len(routes) == 2


def test_depth_cap_limits_route_length() -> None:
    routes = plan_retrosynthesis("CC(=O)OC", max_depth=1, max_routes=50)
    for route in routes:
        assert route.num_steps <= 1


def test_cycle_guard_terminates_reforming_template() -> None:
    engine = RetrosynthesisEngine(max_depth=8, max_routes=50, max_total_expansions=200)
    routes = engine.plan("CC(=O)OC")
    assert routes  # terminates and returns something
    for route in routes:
        assert route.num_steps <= 8


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("target", ["CC(=O)OC", "CC(=O)N", "CC(=O)C", "CCO"])
def test_route_serialisation_round_trip(target: str) -> None:
    routes = plan_retrosynthesis(target, max_depth=5, max_routes=5)
    assert routes
    for route in routes:
        data = retrosynthesis_route_to_dict(route)
        restored = dict_to_retrosynthesis_route(data)
        assert serialize_smiles(restored.target) == serialize_smiles(route.target)
        assert restored.num_steps == route.num_steps
        for orig_step, new_step in zip(route.steps, restored.steps):
            assert new_step.candidate.template_id == orig_step.candidate.template_id
            assert new_step.candidate.priority == orig_step.candidate.priority
            assert [_safe_smiles(p) for p in new_step.candidate.precursors] == [
                _safe_smiles(p) for p in orig_step.candidate.precursors
            ]
        assert data["is_complete"] == restored.is_complete


def _safe_smiles(graph: MolecularGraph) -> str:
    try:
        return serialize_smiles(graph)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Registry + API wiring
# ---------------------------------------------------------------------------
def test_register_retrosynthesis_algorithms_idempotent() -> None:
    registry = AlgorithmRegistry()
    assert ("reactions.retrosynthesis", "plan") not in registry
    register_retrosynthesis_algorithms(registry)
    register_retrosynthesis_algorithms(registry)  # second call is a no-op
    assert ("reactions.retrosynthesis", "plan") in registry
    assert ("reactions.retrosynthesis", "catalogue") in registry
    assert registry.get("reactions.retrosynthesis", "plan").algorithm is plan_retrosynthesis


def test_catalogue_entry_returns_templates() -> None:
    registry = AlgorithmRegistry()
    register_retrosynthesis_algorithms(registry)
    entries = registry.get("reactions.retrosynthesis", "catalogue")
    returned = entries.algorithm()
    assert {t.id for t in returned} == {t.id for t in RETRO_SYNTHESIS_TEMPLATES}
    # Returns template objects, not bare strings.
    assert all(hasattr(t, "find") and hasattr(t, "priority") for t in returned)


def test_api_tool_dispatch() -> None:
    from chemengine.core.registry import reset_global_registry
    from chemengine.core.tool_interface import ChemEngineAPI

    reset_global_registry()
    api = ChemEngineAPI()
    assert "retrosynthesize" in {t.name for t in api.list_tools(category="synthesis")}
    routes = api.retrosynthesize("CC(=O)OC", max_routes=5)
    assert isinstance(routes, list) and len(routes) >= 1
    result = api.execute_tool("retrosynthesize", {"smiles": "CC(=O)C"})
    assert "error" not in result
    assert result["num_routes"] == len(result["routes"])
    assert result["num_routes"] >= 1


# ---------------------------------------------------------------------------
# Import-speed / laziness gate
# ---------------------------------------------------------------------------
def test_retrosynthesis_is_lazy_on_package_import() -> None:
    code = (
        "import sys; import chemengine; print("
        "'RETRO_LAZY', 'chemengine.reactions.retrosynthesis' not in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "RETRO_LAZY True" in out.stdout


def test_package_import_is_fast() -> None:
    code = "import time; t=time.perf_counter(); import chemengine; print(time.perf_counter()-t)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    dt = float(out.stdout.strip().splitlines()[-1])
    assert dt < 0.1, f"import chemengine took {dt:.3f}s"
