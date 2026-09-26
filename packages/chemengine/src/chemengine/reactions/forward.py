"""Bounded forward reaction-prediction engine (M38).

Predicts products from reactant :class:`~chemengine.core.graph.MolecularGraph`
objects using a curated catalogue of deterministic, template-based
transformations -- the *forward* counterpart to the M36 retrosynthetic engine:
M34 identifies a mechanism (backward), M36 plans backward (target -> precursors),
M38 predicts forward (reactants -> products).

No SMARTS, no string manipulation -- every transformation is expressed as
atom-index pairs on a merged reactant canvas. Conservation holds by
construction; the engine double-checks heavy-atom conservation as a guard.
No import side effects: this module is **not** imported by
``chemengine/__init__.py``, preserving the ``import chemengine`` first-import
gate (roadmap 15.6 < 100 ms). Registration is lazy via
:func:`register_forward_reaction_algorithms`, wired into
:class:`~chemengine.core.tool_interface.ChemEngineAPI` setup.
"""

from __future__ import annotations

__all__ = [
    "FORWARD_REACTION_TEMPLATES",
    "ForwardReactionEngine",
    "ForwardReactionTemplate",
    "ForwardSurgery",
    "ReactionPrediction",
    "SCHEMA_VERSION",
    "REFERENCE_ORACLE",
    "dict_to_forward_prediction",
    "forward_prediction_to_dict",
    "list_forward_reaction_templates",
    "predict_reaction",
    "register_forward_reaction_algorithms",
]

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder

if TYPE_CHECKING:  # pragma: no cover - type-only import
    from chemengine.core.registry import AlgorithmRegistry


# Leaving groups / partners recognised by the catalogue.
_HALOGEN_SYMBOLS: frozenset[str] = frozenset({"Cl", "Br", "I"})

#: Catalogue version reported by the engine / registry entries.
_CATALOGUE_VERSION: tuple[int, int, int] = (1, 0, 0)
_CATALOGUE_VERSION_STR: str = ".".join(str(p) for p in _CATALOGUE_VERSION)
_CATALOGUE_PREFIX: str = "m38"

#: Schema tag embedded in serialised predictions (forward compatibility).
SCHEMA_VERSION: str = "chemengine-forward-prediction/v1"


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------
def _heavy_neighbors(graph: MolecularGraph, index: int) -> tuple[int, ...]:
    """Return the heavy-atom (non-hydrogen) neighbour indices of ``index``."""
    return tuple(
        n for n in graph.get_neighbors(index) if graph.atoms[n].atomic_number != 1
    )


def _hydrogens_on(graph: MolecularGraph, index: int) -> tuple[int, ...]:
    """Return the explicit hydrogen neighbour indices of ``index``."""
    return tuple(
        n for n in graph.get_neighbors(index) if graph.atoms[n].atomic_number == 1
    )


def _carbonyl_oxygen(graph: MolecularGraph, carbon: int) -> int | None:
    """Return the oxygen double-bonded to ``carbon`` (a carbonyl), if any.

    Mirrors the helper used by the M36 retrosynthetic templates so the two
    engines agree on what "carbonyl" means.
    """
    for n in graph.get_neighbors(carbon):
        bond = graph.get_bond(carbon, n)
        if bond is not None and bond.is_double and graph.atoms[n].symbol == "O":
            return n
    return None


def _atom_to_component(
    components: tuple[tuple[int, ...], ...],
) -> dict[int, int]:
    """Map every atom index in the merged graph to its source reactant index."""
    return {
        idx: comp_idx
        for comp_idx, comp in enumerate(components)
        for idx in comp
    }


def _safe_smiles(graph: MolecularGraph) -> str:
    """Best-effort SMILES serialization; returns ``""`` on failure."""
    try:
        from chemengine.parsing.smiles import serialize_smiles

        return serialize_smiles(graph)
    except Exception:
        return ""


def _canonical_smiles(graph: MolecularGraph) -> str:
    """Canonical SMILES (falls back to :func:`_safe_smiles`) for de-dup."""
    try:
        from chemengine.parsing.canonical import canonical_smiles

        return canonical_smiles(graph)
    except Exception:
        return _safe_smiles(graph)


# ---------------------------------------------------------------------------
# Forward surgery
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ForwardSurgery:
    """Declarative description of one forward reaction step.

    All atom indices refer to the *merged* reactant graph produced by
    :func:`_merge` -- the same convention used by M36's ``_Surgery``.

    Attributes:
        break_bonds: Atom-index pairs whose bond should be deleted.
        form_bonds: ``(atom_a, atom_b, BondOrder)`` triples creating a new bond.
        order_changes: ``(frozenset({a, b}), BondOrder)`` rewrites applied to
            an existing surviving bond (e.g. ``C=C`` -> ``C-C``).
    """

    break_bonds: tuple[tuple[int, int], ...] = ()
    form_bonds: tuple[tuple[int, int, BondOrder], ...] = ()
    order_changes: tuple[tuple[frozenset[int], BondOrder], ...] = ()


def _merge(
    reactants: tuple[MolecularGraph, ...],
) -> tuple[MolecularGraph, tuple[tuple[int, ...], ...]]:
    """Combine ``reactants`` into one canvas graph, preserving component layout.

    Returns the merged graph and, for each reactant, the tuple of its (offset)
    atom indices within the merged graph. Reactants are left as disconnected
    components -- forward templates supply the new inter-component bonds.
    """
    builder = MolecularGraphBuilder()
    components: list[tuple[int, ...]] = []
    offset = 0
    for graph in reactants:
        start = offset
        for atom in graph.atoms:
            builder.add_atom(
                atomic_number=atom.atomic_number,
                formal_charge=atom.formal_charge,
                implicit_hydrogens=atom.implicit_hydrogens,
                is_aromatic=atom.is_aromatic,
            )
        for bond in graph.bonds:
            builder.add_bond(
                bond.atom1 + start,
                bond.atom2 + start,
                bond.order,
                is_aromatic=bond.is_aromatic,
            )
        offset += graph.num_atoms
        components.append(tuple(range(start, start + graph.num_atoms)))
    return builder.build(), tuple(components)


def _apply_forward_surgery(
    merged: MolecularGraph,
    surgery: ForwardSurgery,
) -> tuple[MolecularGraph, ...]:
    """Materialise one :class:`ForwardSurgery` on ``merged`` -> product graphs.

    Copies surviving atoms (preserving element/charge/hydrogens/aromaticity),
    re-wires surviving bonds (honouring ``order_changes`` and skipping
    ``break_bonds``), splices in ``form_bonds``, builds the graph, then splits
    it into connected components -- one per product. H-only fragments are
    discarded, matching M36's behaviour.
    """
    builder = MolecularGraphBuilder()
    # 1) Surviving atoms (copied verbatim, like M36's _apply_surgery).
    for idx in range(merged.num_atoms):
        atom = merged.atoms[idx]
        builder.add_atom(
            atomic_number=atom.atomic_number,
            formal_charge=atom.formal_charge,
            implicit_hydrogens=atom.implicit_hydrogens,
            is_aromatic=atom.is_aromatic,
        )

    break_set: set[frozenset[int]] = {frozenset(pair) for pair in surgery.break_bonds}
    order_lookup: dict[frozenset[int], BondOrder] = {
        pair: order for pair, order in surgery.order_changes
    }
    present: set[frozenset[int]] = set()

    # 2) Surviving bonds (skip broken; honour order rewrites).
    for bond in merged.bonds:
        pair = frozenset((bond.atom1, bond.atom2))
        if pair in break_set:
            continue
        new_order = order_lookup.get(pair, bond.order)
        present.add(pair)
        builder.add_bond(bond.atom1, bond.atom2, new_order, is_aromatic=bond.is_aromatic)

    # 3) Newly formed bonds (skip anything already present -- safety only).
    for atom_a, atom_b, order in surgery.form_bonds:
        pair = frozenset((atom_a, atom_b))
        if pair in present:
            continue
        present.add(pair)
        builder.add_bond(atom_a, atom_b, order)

    products_graph = builder.build()

    # 4) Split into connected products; drop H-only fragments.
    products: list[MolecularGraph] = []
    for comp in products_graph.connected_components():
        if not any(products_graph.atoms[i].atomic_number != 1 for i in comp):
            continue
        products.append(products_graph.subgraph(set(comp)))
    return tuple(products)


def _normalize_reactants(
    reactants: MolecularGraph | str | Sequence[MolecularGraph | str],
) -> tuple[MolecularGraph, ...]:
    """Normalise a SMILES string / graph / sequence into a reactant tuple.

    Strings are split on ``"."`` so multi-component mixtures parse as distinct
    reactants (robust whether or not the SMILES tokenizer joins them).
    """
    if isinstance(reactants, MolecularGraph):
        return (reactants,)
    if isinstance(reactants, str):
        from chemengine.parsing.smiles import parse_smiles

        return tuple(
            parse_smiles(part) for part in reactants.split(".") if part.strip()
        )
    seq = tuple(reactants)
    if seq and isinstance(seq[0], str):
        from chemengine.parsing.smiles import parse_smiles

        return tuple(parse_smiles(cast(str, smiles)) for smiles in seq)
    return cast(tuple[MolecularGraph, ...], seq)


@dataclass(frozen=True, slots=True)
class ForwardReactionTemplate:
    """Base class for all M38 forward reaction transformations.

    Attributes:
        id: Stable catalogue identifier (e.g. ``m38-e2-elimination``).
        title: Human-readable title.
        forward_reaction: Informational reaction equation string.
        priority: Ordering weight (higher fires first); ties broken by id.
        conditions: Typical reaction conditions (solvent, catalyst, ...).
    """

    id: str
    title: str
    forward_reaction: str = ""
    priority: int = 0
    conditions: tuple[str, ...] = ()

    def find(
        self,
        merged: MolecularGraph,
        components: tuple[tuple[int, ...], ...],
    ) -> list[tuple[dict[str, int], ForwardSurgery]]:
        """Return every ``(site, surgery)`` match of this template.

        Args:
            merged: All reactants combined into one graph (disconnected).
            components: Atom-index tuples, one per source reactant.

        Returns:
            Zero or more matches. Each site maps role-name -> atom index in
            ``merged``; each surgery is ready for :func:`_apply_forward_surgery`.
        """
        raise NotImplementedError

    def __hash__(self) -> int:  # noqa: D105
        return hash(self.id)


class EsterSaponification(ForwardReactionTemplate):
    """Esterification (forward of M36 ``ester-fischer``).

    acid + alcohol -> ester + water.
    """

    def find(
        self,
        merged: MolecularGraph,
        components: tuple[tuple[int, ...], ...],
    ) -> list[tuple[dict[str, int], ForwardSurgery]]:
        """Match a carboxylic acid and an alcohol across two reactant components."""
        out: list[tuple[dict[str, int], ForwardSurgery]] = []
        comp = _atom_to_component(components)
        acid_sites: list[tuple[int, int, int, int]] = []
        for carbon in range(merged.num_atoms):
            atom_c = merged.atoms[carbon]
            if atom_c.symbol != "C" or atom_c.is_aromatic:
                continue
            carbonyl_o = _carbonyl_oxygen(merged, carbon)
            if carbonyl_o is None:
                continue
            for oxygen in merged.get_neighbors(carbon):
                if oxygen == carbonyl_o:
                    continue
                atom_o = merged.atoms[oxygen]
                if atom_o.symbol != "O" or atom_o.is_aromatic:
                    continue
                hydrogens = _hydrogens_on(merged, oxygen)
                if not hydrogens:
                    continue
                acid_sites.append((carbon, carbonyl_o, oxygen, hydrogens[0]))

        acid_oh_set = {oh for (_, _, oh, _) in acid_sites}
        alcohol_sites: list[tuple[int, int, int]] = []
        for oxygen in range(merged.num_atoms):
            atom_o = merged.atoms[oxygen]
            if atom_o.symbol != "O" or atom_o.is_aromatic or oxygen in acid_oh_set:
                continue
            hydrogens = _hydrogens_on(merged, oxygen)
            heavy = _heavy_neighbors(merged, oxygen)
            if len(hydrogens) != 1 or len(heavy) != 1:
                continue
            carbon_r = heavy[0]
            if (
                merged.atoms[carbon_r].symbol != "C"
                or merged.atoms[carbon_r].is_aromatic
            ):
                continue
            if _carbonyl_oxygen(merged, carbon_r) is not None:
                continue
            alcohol_sites.append((oxygen, hydrogens[0], carbon_r))

        for carbon, carbonyl_o, acid_oh, h_acid in acid_sites:
            for alc_o, h_alc, carbon_r in alcohol_sites:
                if comp[carbon] == comp[alc_o]:
                    continue
                surgery = ForwardSurgery(
                    break_bonds=((carbon, acid_oh), (alc_o, h_alc)),
                    form_bonds=(
                        (carbon, alc_o, BondOrder.SINGLE),
                        (acid_oh, h_alc, BondOrder.SINGLE),
                    ),
                )
                out.append(
                    (
                        {
                            "carbonyl_C": carbon,
                            "carbonyl_O": carbonyl_o,
                            "acid_OH": acid_oh,
                            "acid_H": h_acid,
                            "alcohol_O": alc_o,
                            "alcohol_H": h_alc,
                                                        "alcohol_R": carbon_r,
                        },
                        surgery,
                    )
                )
        return out


class AlkeneHydrogenation(ForwardReactionTemplate):
    """Addition: alkene + H2 -> alkane (hydrogenation of a C=C double bond)."""

    def find(
        self,
        merged: MolecularGraph,
        components: tuple[tuple[int, ...], ...],
    ) -> list[tuple[dict[str, int], ForwardSurgery]]:
        """Match a C=C double bond in one reactant with an H-H bond elsewhere."""
        out: list[tuple[dict[str, int], ForwardSurgery]] = []
        comp = _atom_to_component(components)
        for bond in merged.bonds:
            a, b = bond.atom1, bond.atom2
            if not (
                merged.atoms[a].symbol == "C"
                and merged.atoms[b].symbol == "C"
            ):
                continue
            if bond.order != BondOrder.DOUBLE or bond.is_aromatic:
                continue
            for h_bond in merged.bonds:
                c, d = h_bond.atom1, h_bond.atom2
                if not (
                    merged.atoms[c].atomic_number == 1
                    and merged.atoms[d].atomic_number == 1
                ):
                    continue
                if comp[a] == comp[c]:
                    continue
                surgery = ForwardSurgery(
                    break_bonds=((c, d),),
                    form_bonds=(
                        (a, c, BondOrder.SINGLE),
                        (b, d, BondOrder.SINGLE),
                    ),
                    order_changes=((frozenset((a, b)), BondOrder.SINGLE),),
                )
                out.append(
                    ({"alkene_a": a, "alkene_b": b, "h2_a": c, "h2_b": d}, surgery)
                )
        return out


class E2Elimination(ForwardReactionTemplate):
    """E2 beta-elimination: alkyl halide -> alkene + HX."""

    def find(
        self,
        merged: MolecularGraph,
        components: tuple[tuple[int, ...], ...],
    ) -> list[tuple[dict[str, int], ForwardSurgery]]:
        """Match a C-X bond plus an adjacent beta-hydrogen (intramolecular)."""
        out: list[tuple[dict[str, int], ForwardSurgery]] = []
        for bond in merged.bonds:
            a, b = bond.atom1, bond.atom2
            ca = x = 0
            if (
                merged.atoms[a].symbol in _HALOGEN_SYMBOLS
                and merged.atoms[b].symbol == "C"
            ):
                x, ca = a, b
            elif (
                merged.atoms[b].symbol in _HALOGEN_SYMBOLS
                and merged.atoms[a].symbol == "C"
            ):
                x, ca = b, a
            else:
                continue
            if ca == 0 and x == 0:
                continue
            # Leaving group must be bonded to the organic carbon only.
            if set(_heavy_neighbors(merged, x)) != {ca}:
                continue
            for cbeta in merged.get_neighbors(ca):
                if cbeta == x:
                    continue
                if (
                    merged.atoms[cbeta].symbol != "C"
                    or merged.atoms[cbeta].is_aromatic
                ):
                    continue
                hydrogens = _hydrogens_on(merged, cbeta)
                if not hydrogens:
                    continue
                hbeta = hydrogens[0]
                surgery = ForwardSurgery(
                    break_bonds=((ca, x), (cbeta, hbeta)),
                    form_bonds=((x, hbeta, BondOrder.SINGLE),),
                    order_changes=((frozenset((ca, cbeta)), BondOrder.DOUBLE),),
                )
                out.append(
                    (
                        {"halo_C": ca, "halo_X": x, "beta_C": cbeta, "beta_H": hbeta},
                        surgery,
                    )
                )
                break  # one beta-H per (Calpha, Cbeta) keeps the result bounded
        return out


class AlcoholDehydration(ForwardReactionTemplate):
    """Acid-catalysed dehydration: alcohol -> alkene + water.

    An O-H protonated alcohol eliminates a neighbouring beta-H, forming a C=C
    and expelling water.  Carbonyl-bearing C are excluded so ketones/aldehydes
    are not mistaken for alcohols.
    """

    def find(
        self,
        merged: MolecularGraph,
        components: tuple[tuple[int, ...], ...],
    ) -> list[tuple[dict[str, int], ForwardSurgery]]:
        """Match an alcohol O-H plus an adjacent beta-hydrogen (intramolecular)."""
        out: list[tuple[dict[str, int], ForwardSurgery]] = []
        for oxygen in range(merged.num_atoms):
            atom_o = merged.atoms[oxygen]
            if atom_o.symbol != "O" or atom_o.is_aromatic:
                continue
            hydrogens = _hydrogens_on(merged, oxygen)
            heavy = _heavy_neighbors(merged, oxygen)
            if len(hydrogens) != 1 or len(heavy) != 1:
                continue
            alpha_c = heavy[0]
            if (
                merged.atoms[alpha_c].symbol != "C"
                or merged.atoms[alpha_c].is_aromatic
            ):
                continue
            if _carbonyl_oxygen(merged, alpha_c) is not None:
                continue  # the OH sits on a carbonyl carbon -> not a plain alcohol
            h_alc = hydrogens[0]
            for cbeta in _heavy_neighbors(merged, alpha_c):
                if cbeta == oxygen:
                    continue
                if (
                    merged.atoms[cbeta].symbol != "C"
                    or merged.atoms[cbeta].is_aromatic
                ):
                    continue
                beta_h_pool = _hydrogens_on(merged, cbeta)
                if not beta_h_pool:
                    continue
                hbeta = beta_h_pool[0]
                surgery = ForwardSurgery(
                    break_bonds=((alpha_c, oxygen), (cbeta, hbeta)),
                    form_bonds=((oxygen, hbeta, BondOrder.SINGLE),),
                    order_changes=((frozenset((alpha_c, cbeta)), BondOrder.DOUBLE),),
                )
                out.append(
                    (
                        {
                            "alpha_C": alpha_c,
                            "OH_O": oxygen,
                            "OH_H": h_alc,
                            "beta_C": cbeta,
                            "beta_H": hbeta,
                        },
                        surgery,
                    )
                )
                break  # one beta-H per (alpha_C, beta_C) keeps the result bounded
        return out


class HydrolysisAlkylHalide(ForwardReactionTemplate):
    """Nucleophilic substitution: alkyl halide + water -> alcohol + HX.

    The water oxygen attacks the alkyl carbon as the halide leaves with one of
    water's hydrogens (forming HX).  Forward of the M36 reverse of
    ``alcohol-to-alkyl-halide``.
    """

    def find(
        self,
        merged: MolecularGraph,
        components: tuple[tuple[int, ...], ...],
    ) -> list[tuple[dict[str, int], ForwardSurgery]]:
        """Match a C-X bond plus a water (H-O-H) component across reactants."""
        out: list[tuple[dict[str, int], ForwardSurgery]] = []
        comp = _atom_to_component(components)
        cx_sites: list[tuple[int, int]] = []
        for bond in merged.bonds:
            a, b = bond.atom1, bond.atom2
            ca = x = -1
            if (
                merged.atoms[a].symbol in _HALOGEN_SYMBOLS
                and merged.atoms[b].symbol == "C"
            ):
                ca, x = b, a
            elif (
                merged.atoms[b].symbol in _HALOGEN_SYMBOLS
                and merged.atoms[a].symbol == "C"
            ):
                ca, x = a, b
            else:
                continue
            if ca == -1 or x == -1:
                continue
            if set(_heavy_neighbors(merged, x)) == {ca}:
                cx_sites.append((ca, x))

        h2o_sites: list[tuple[int, int, int]] = []
        for atoms in components:
            if len(atoms) != 3:
                continue
            oxygens = [i for i in atoms if merged.atoms[i].symbol == "O"]
            if len(oxygens) != 1:
                continue
            o = oxygens[0]
            hs = tuple(i for i in atoms if merged.atoms[i].atomic_number == 1)
            if len(hs) != 2:
                continue
            h2o_sites.append((o, hs[0], hs[1]))

        for ca, x in cx_sites:
            for o, h1, _h2 in h2o_sites:
                if comp[ca] == comp[o]:
                    continue
                surgery = ForwardSurgery(
                    break_bonds=((ca, x), (o, h1)),
                    form_bonds=(
                        (ca, o, BondOrder.SINGLE),
                        (x, h1, BondOrder.SINGLE),
                    ),
                )
                out.append(
                    ({"halo_C": ca, "halo_X": x, "water_O": o, "water_H": h1}, surgery)
                )
        return out


#: Ordered catalogue (priority, then id, is the deterministic ordering).
_TEMPLATES: tuple[ForwardReactionTemplate, ...] = (
    EsterSaponification(
        id=f"{_CATALOGUE_PREFIX}-ester-saponification",
        title="Esterification (acid + alcohol -> ester + water)",
        forward_reaction="RCOOH + R'OH -> RCOOR' + H2O",
        priority=5,
        conditions=("acid",),
    ),
    AlkeneHydrogenation(
        id=f"{_CATALOGUE_PREFIX}-alkene-hydrogenation",
        title="Alkene hydrogenation (C=C + H2 -> alkane)",
        forward_reaction="R2C=CR2 + H2 -> R2CH-CH2R2",
        priority=4,
        conditions=("Pd/C",),
    ),
    E2Elimination(
        id=f"{_CATALOGUE_PREFIX}-e2-elimination",
        title="E2 beta-elimination (alkyl halide -> alkene + HX)",
        forward_reaction="R-CH2-CH2-X -> R-CH=CH2 + HX",
        priority=3,
    ),
    AlcoholDehydration(
        id=f"{_CATALOGUE_PREFIX}-alcohol-dehydration",
        title="Alcohol dehydration (alcohol -> alkene + water)",
        forward_reaction="R-CH2-CH2-OH -> R-CH=CH2 + H2O",
        priority=3,
    ),
    HydrolysisAlkylHalide(
        id=f"{_CATALOGUE_PREFIX}-hydrolysis-alkyl-halide",
        title="Alkyl-halide hydrolysis (R-X + H2O -> R-OH + HX)",
        forward_reaction="R-Cl + H2O -> R-OH + HCl",
        priority=2,
    ),
)

#: Public, immutable catalogue (built once at import -- cheap, no I/O).
FORWARD_REACTION_TEMPLATES: tuple[ForwardReactionTemplate, ...] = _TEMPLATES
_TEMPLATE_INDEX: dict[str, ForwardReactionTemplate] = {t.id: t for t in _TEMPLATES}


def get_forward_reaction_template(template_id: str) -> ForwardReactionTemplate:
    """Look up a forward reaction template by its identifier."""
    try:
        return _TEMPLATE_INDEX[template_id]
    except KeyError as exc:
        raise KeyError(f"Unknown forward reaction template: {template_id!r}") from exc


def list_forward_reaction_templates() -> tuple[ForwardReactionTemplate, ...]:
    """Return all registered forward reaction templates."""
    return _TEMPLATES


# ---------------------------------------------------------------------------
# Prediction model
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ReactionPrediction:
    """One predicted forward-reaction outcome.

    Attributes:
        template_id: Identifier of the template that produced the prediction.
        reactant_graphs: The (unmodified) input reactant graphs.
        product_graphs: Predicted product graphs, sorted by product SMILES.
        reactant_smiles: SMILES of each reactant (best-effort).
        product_smiles: SMILES of each product (best-effort), sorted.
        site: Role-name -> merged-graph atom index that fired.
        priority: Template priority (higher fires first).
        score: Engine-internal score (heavy-atom count of the products).
    """

    template_id: str
    reactant_graphs: tuple[MolecularGraph, ...]
    product_graphs: tuple[MolecularGraph, ...]
    reactant_smiles: tuple[str, ...]
    product_smiles: tuple[str, ...]
    site: dict[str, int] = field(default_factory=dict)
    priority: int = 0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the prediction (molecules via ``graph_to_dict``)."""
        from chemengine.io.serialization import graph_to_dict

        return {
            "schema": SCHEMA_VERSION,
            "catalogue_version": f"{_CATALOGUE_PREFIX}.{_CATALOGUE_VERSION_STR}",
            "template_id": self.template_id,
            "priority": self.priority,
            "reactant_smiles": list(self.reactant_smiles),
            "product_smiles": list(self.product_smiles),
            "site": dict(self.site),
            "score": round(self.score, 6),
                        "products": [graph_to_dict(g) for g in self.product_graphs],
        }


# ---------------------------------------------------------------------------
# Bounded predictor
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ForwardReactionEngine:
    """Bounded, deterministic forward reaction-prediction engine.

    Walks the template catalogue over the merged reactant graph, applies each
    matching :class:`ForwardSurgery`, validates heavy-atom conservation + graph
    validity, then de-duplicates structurally identical product sets.

    Attributes:
        templates: Catalogue to iterate (defaults to the M38 catalogue).
        max_candidates_per_template: Cap on matches expanded per template.
        max_results: Cap on the number of returned predictions.
    """

    templates: tuple[ForwardReactionTemplate, ...] = field(
        default_factory=lambda: FORWARD_REACTION_TEMPLATES
    )
    max_candidates_per_template: int = 20
    max_results: int = 50

    def predict(
        self,
        reactants: MolecularGraph | str | tuple[MolecularGraph, ...],
        *,
        template_id: str | None = None,
    ) -> list[ReactionPrediction]:
        """Predict products for ``reactants``.

        Args:
            reactants: A SMILES string (``"."``-separated for mixtures), a single
                :class:`MolecularGraph`, or a sequence of either.
            template_id: When given, only that template id is applied.

        Returns:
            De-duplicated, deterministic predictions sorted by
            ``(priority desc, score desc, template_id, product_smiles)``.
        """
        graphs = _normalize_reactants(reactants)
        if not graphs:
            raise ValueError("predict requires at least one reactant")
        merged, components = _merge(graphs)
        reactant_smiles = tuple(_safe_smiles(g) for g in graphs)
        reactant_heavy = sum(g.num_heavy_atoms for g in graphs)

        results: list[ReactionPrediction] = []
        for tmpl in sorted(self.templates, key=lambda t: t.priority):
            if template_id is not None and tmpl.id != template_id:
                continue
            matches = tmpl.find(merged, components)[: self.max_candidates_per_template]
            for site, surgery in matches:
                products = _apply_forward_surgery(merged, surgery)
                if not products:
                    continue
                if not all(p.validate() == [] for p in products):
                    continue
                if sum(p.num_heavy_atoms for p in products) != reactant_heavy:
                    continue
                ordered = tuple(sorted(products, key=_safe_smiles))
                results.append(
                    ReactionPrediction(
                        template_id=tmpl.id,
                        reactant_graphs=graphs,
                        product_graphs=ordered,
                        reactant_smiles=reactant_smiles,
                        product_smiles=tuple(_safe_smiles(p) for p in ordered),
                        site=dict(site),
                        priority=tmpl.priority,
                        score=float(sum(p.num_heavy_atoms for p in ordered)),
                    )
                )

        seen: set[tuple] = set()
        unique: list[ReactionPrediction] = []
        for pred in results:
            key = (
                pred.template_id,
                tuple(sorted(_canonical_smiles(p) for p in pred.product_graphs)),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(pred)
        unique.sort(
            key=lambda r: (
                -r.priority,
                -r.score,
                r.template_id,
                r.product_smiles,
            )
        )
        return unique[: self.max_results]


def predict_reaction(
    reactants: MolecularGraph | str | tuple[MolecularGraph, ...],
    *,
    template_id: str | None = None,
    max_candidates_per_template: int = 20,
    max_results: int = 50,
) -> list[ReactionPrediction]:
    """Predict products for ``reactants`` using the default M38 catalogue.

    Thin callable wrapper around :class:`ForwardReactionEngine` -- the function
    registered in the :class:`~chemengine.core.registry.AlgorithmRegistry`.
    """
    engine = ForwardReactionEngine(
        max_candidates_per_template=max_candidates_per_template,
        max_results=max_results,
    )
    return engine.predict(reactants, template_id=template_id)


# ---------------------------------------------------------------------------
# Deterministic regression oracle
# ---------------------------------------------------------------------------
#: Deterministic regression oracle.  Keys are reactant SMILES (``"."``-joined
#: for mixtures); values describe the expected behaviour: ``must_match`` is the
#: set of template ids that must fire, ``must_not_match`` the set that must not,
#: and ``product_formulas`` the set of product molecular formulas that must be
#: produced.  The catalogue doubles as living documentation of the contracts.
REFERENCE_ORACLE: dict[str, dict[str, Any]] = {
    "CCCl": {
        "description": "Chloroethane E2 elimination -> ethene + HCl",
        "must_match": {f"{_CATALOGUE_PREFIX}-e2-elimination"},
        "must_not_match": set(),
        "product_formulas": {"C2H4", "HCl"},
    },
    "CCO": {
        "description": "Ethanol dehydration -> ethene + water",
        "must_match": {f"{_CATALOGUE_PREFIX}-alcohol-dehydration"},
        "must_not_match": set(),
        "product_formulas": {"C2H4", "H2O"},
    },
    "C=C.[H][H]": {
        "description": "Ethylene hydrogenation -> ethane",
        "must_match": {f"{_CATALOGUE_PREFIX}-alkene-hydrogenation"},
        "must_not_match": set(),
        "product_formulas": {"C2H6"},
    },
    "CC(=O)O.CO": {
        "description": "Acetic acid + methanol esterification -> methyl acetate + water",
        "must_match": {f"{_CATALOGUE_PREFIX}-ester-saponification"},
        "must_not_match": set(),
        "product_formulas": {"C3H6O2", "H2O"},
    },
    "CCl.O": {
        "description": "Chloromethane + water hydrolysis -> methanol + HCl",
        "must_match": {f"{_CATALOGUE_PREFIX}-hydrolysis-alkyl-halide"},
        "must_not_match": set(),
        "product_formulas": {"CH4O", "HCl"},
    },
}


# ---------------------------------------------------------------------------
# Prediction (de)serialisation
# ---------------------------------------------------------------------------
def forward_prediction_to_dict(pred: ReactionPrediction) -> dict[str, Any]:
    """Serialise a :class:`ReactionPrediction` to a JSON-able dict."""
    return pred.to_dict()


def dict_to_forward_prediction(data: dict[str, Any]) -> ReactionPrediction:
    """Reconstruct a :class:`ReactionPrediction` from its dict form."""
    from chemengine.io.serialization import dict_to_graph

    products = tuple(dict_to_graph(p) for p in data.get("products", []))
    prod_smiles = tuple(_safe_smiles(p) for p in products) or tuple(
        data.get("product_smiles", [])
    )
    return ReactionPrediction(
        template_id=data["template_id"],
        reactant_graphs=_normalize_reactants(data.get("reactant_smiles", [])),
        product_graphs=products,
        reactant_smiles=tuple(data.get("reactant_smiles", [])),
        product_smiles=prod_smiles,
        site=dict(data.get("site", {})),
        priority=int(data.get("priority", 0)),
        score=float(data.get("score", 0.0)),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_forward_reaction_algorithms(
    registry: AlgorithmRegistry | None = None,
    *,
    replace: bool = False,
) -> None:
    """Register the M38 forward-reaction algorithms with ``registry``.

    Mirrors the ``register_retrosynthesis_algorithms`` pattern: a no-op when the
    entry already exists (``replace=False``).  Called explicitly by
    :class:`~chemengine.core.tool_interface.ChemEngineAPI` built-in setup and by
    tests against any registry.  No import side effects -- registration is lazy,
    preserving the ``import chemengine`` first-import gate.
    """
    from chemengine.core.registry import AlgorithmEntry, get_global_registry

    target = registry if registry is not None else get_global_registry()
    predict_key = ("reactions.forward", "predict")
    if predict_key in target and not replace:
        return
    target.register(
        AlgorithmEntry(
            domain="reactions.forward",
            name="predict",
            version=f"{_CATALOGUE_PREFIX}.{_CATALOGUE_VERSION_STR}",
            algorithm=predict_reaction,
            input_type=str,
            output_type=list,
            tags=frozenset(
                {"forward", "reactions", "prediction", "synthesis", "deterministic"}
            ),
        )
    )
    target.register(
        AlgorithmEntry(
            domain="reactions.forward",
            name="catalogue",
            version=f"{_CATALOGUE_PREFIX}.{_CATALOGUE_VERSION_STR}",
            algorithm=list_forward_reaction_templates,
            input_type=None,
            output_type=tuple,
            tags=frozenset({"forward", "reactions", "templates"}),
        )
    )
