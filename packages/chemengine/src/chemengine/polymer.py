"""Polymer chemistry engine (M39).

Deterministic, graph-based polymer chemistry on the shared
:class:`~chemengine.core.graph.MolecularGraph` abstraction.  The engine
operates exclusively on the molecular graph -- no SMARTS, no external chem
libraries, no string matching -- so every result is reproducible and every
algorithm composes with the existing parsing / serialization pipeline.

Two representations are supported:

* **Repeat-unit form** -- a single monomeric repeat unit whose
  polymerization junctions are expressed with ``*`` (wildcard, atomic
  number 0) atoms, e.g. ``*CC*`` (polyethylene), ``*OC(=O)c1ccccc1CO*``
  (polyethylene terephthalate).  The wildcard atoms are the *connection
  points* where the repeat unit links to its neighbours in the polymer
  chain.
* **Terminal-chain form** -- a finite oligomer / chain with no wildcards,
  e.g. ``CCCCCC`` (a short polyethylene oligomer).  The engine detects the
  backbone and its structural periodicity to recover the degree of
  polymerization and the minimal repeat unit.

Capabilities
------------
* :func:`find_connection_points` -- locate ``*`` junction atoms.
* :func:`extract_repeat_unit` -- carve the repeat unit out of the graph
  (wildcard-free), preserving the attachment atoms.
* :func:`classify_polymerization` -- ``addition`` vs ``condensation`` from
  a condensation linkage (an in-chain carbonyl bonded to O or N spanning the
  two attachment points).
* :func:`find_end_groups` -- terminal functional groups of a chain.
* :func:`degree_of_polymerization` -- structural DP from backbone
  periodicity (KMP minimal-period on internal backbone signatures).
* :func:`analyze_polymer` -- one-shot :class:`PolymerAnalysis`.
* :func:`polymer_analysis_to_dict` / :func:`dict_to_polymer_analysis` --
  (de)serialization through the existing :mod:`chemengine.io.serialization`
  surface.
* :data:`REFERENCE_POLYMER_ORACLE` -- 8 curated, chemistry-checked cases.
* :func:`register_polymer_algorithms` -- lazy :class:`AlgorithmRegistry`
  wiring.

No import side effects: this module is **not** imported by
``chemengine/__init__.py`` (it is absent from ``_LAZY_EXPORTS``), preserving
the ``import chemengine`` first-import gate (roadmap 15.6, <100 ms).
Registration is lazy via :func:`register_polymer_algorithms`, wired into
:class:`~chemengine.core.tool_interface.ChemEngineAPI` built-in setup.

Chemistry notes
---------------
* ``*`` atoms (atomic number 0) are *placeholders*; they are excluded from
  molecular formulas, molecular weights and validation -- only the real
  (heavy + hydrogen) atoms count.  ``analyze_polymer`` therefore never
  hands a wildcard-containing graph to ``MolecularGraph.validate()`` (which
  rejects atomic number 0).
* ``degree_of_polymerization`` reports the *structural* degree of
  polymerization: the backbone length divided by the minimal repeating
  structural unit.  For polyethylene-family backbones -- whose minimal
  structural repeat is a single ``-CH2-`` -- this therefore counts
  ``-CH2-`` units rather than the ethylene-based monomer; the value is
  always internally consistent (DPn x mer-MW ~= chain MW) and explicitly
  documented as structural.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from chemengine.core.atoms import Atom
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder

if TYPE_CHECKING:  # pragma: no cover - type-only import
    from chemengine.core.registry import AlgorithmRegistry


logger = logging.getLogger(__name__)

__all__ = [
    "EndGroup",
    "RepeatUnit",
    "PolymerAnalysis",
    "SCHEMA_VERSION",
    "POLYMER_CATALOGUE_VERSION",
    "REFERENCE_POLYMER_ORACLE",
    "find_connection_points",
    "extract_repeat_unit",
    "find_end_groups",
    "degree_of_polymerization",
    "classify_polymerization",
    "analyze_polymer",
    "number_avg_mw",
    "polymer_analysis_to_dict",
    "dict_to_polymer_analysis",
    "list_polymer_reference",
    "register_polymer_algorithms",
]

# ── Catalogue metadata ────────────────────────────────────────────────────────

#: Schema tag embedded in serialized analyses (forward compatibility).
SCHEMA_VERSION: str = "chemengine-polymer-analysis/v1"

_CATALOGUE_VERSION: Final[tuple[int, int, int]] = (1, 0, 0)
_CATALOGUE_VERSION_STR: Final[str] = ".".join(str(p) for p in _CATALOGUE_VERSION)
_CATALOGUE_PREFIX: Final[str] = "m39"
#: Public, human-readable catalogue version string.
POLYMER_CATALOGUE_VERSION: Final[str] = _CATALOGUE_VERSION_STR

_WILD_CARD_Z: Final[int] = 0  # ``*`` wildcard / connection-point atom
_HYDROGEN_Z: Final[int] = 1



# ── Graph helpers ─────────────────────────────────────────────────────────────


def _is_connection_point(atom: Atom) -> bool:
    """Return True for a ``*`` wildcard (polymer connection-point) atom."""
    return atom.atomic_number == _WILD_CARD_Z


def _is_real_atom(atom: Atom) -> bool:
    """Return True for a non-placeholder atom (not ``*`` and not hydrogen)."""
    return atom.atomic_number not in (_WILD_CARD_Z, _HYDROGEN_Z)


def _heavy_neighbors(graph: MolecularGraph, index: int) -> tuple[int, ...]:
    """Return the heavy-atom (non-H, non-``*``) neighbour indices of ``index``."""
    return tuple(
        n
        for n in graph.get_neighbors(index)
        if graph.atoms[n].atomic_number not in (_WILD_CARD_Z, _HYDROGEN_Z)
    )


def _hydrogen_count(graph: MolecularGraph, index: int) -> int:
    """Return the number of explicit hydrogen neighbours of ``index``."""
    return sum(
        1
        for n in graph.get_neighbors(index)
        if graph.atoms[n].atomic_number == _HYDROGEN_Z
    )


def _safe_smiles(graph: MolecularGraph) -> str:
    """Best-effort SMILES serialization; returns ``""`` on failure."""
    try:
        from chemengine.parsing.smiles import serialize_smiles

        return serialize_smiles(graph)
    except Exception:  # noqa: BLE001 - best-effort, caller handles ""
        return ""


def _canonical_smiles(graph: MolecularGraph) -> str:
    """Canonical SMILES (falls back to :func:`_safe_smiles`) for stable output."""
    try:
        from chemengine.parsing.canonical import canonical_smiles

        return canonical_smiles(graph)
    except Exception:  # noqa: BLE001 - best-effort
        return _safe_smiles(graph)


def _formula_no_wildcards(graph: MolecularGraph) -> str:
    """Hill-system formula of ``graph`` excluding ``*`` placeholder atoms.

    The standard :attr:`MolecularGraph.molecular_formula` would render
    wildcards as ``*``; polymers treat ``*`` as junctions, so they are
    dropped from the formula and molecular weight.
    """
    counts: dict[str, int] = {}
    for atom in graph.atoms:
        if _is_connection_point(atom):
            continue
        sym = atom.symbol
        counts[sym] = counts.get(sym, 0) + 1
    parts: list[str] = []
    for sym in ("C", "H"):
        if sym in counts:
            cnt = counts.pop(sym)
            parts.append(f"{sym}{cnt if cnt > 1 else ''}")
    for sym in sorted(counts):
        cnt = counts[sym]
        parts.append(f"{sym}{cnt if cnt > 1 else ''}")
    return "".join(parts)


def _mw_no_wildcards(graph: MolecularGraph) -> float:
    """Average molecular weight of ``graph`` excluding ``*`` atoms.

    Bypasses :attr:`MolecularGraph.molecular_weight` (which dereferences the
    element table and raises ``AttributeError`` for ``*`` placeholders).
    """
    total = 0.0
    for atom in graph.atoms:
        if _is_connection_point(atom):
            continue
        if atom.isotope is not None:
            total += atom.isotope.exact_mass
        else:
            total += atom.mass
    return total


def _strip_wildcards(
    graph: MolecularGraph,
) -> tuple[MolecularGraph, dict[int, int]]:
    """Return a copy of ``graph`` without ``*`` atoms and a remap {old->new}.

    Bonds incident to a wildcard are dropped; bonds between two real atoms
    are preserved.  The heavy neighbours that were bonded to the wildcards
    become the attachment atoms of the repeat unit (see
    :func:`_attachment_atoms`).
    """
    keep = [
        i for i in range(graph.num_atoms) if not _is_connection_point(graph.atoms[i])
    ]
    remap = {old: new for new, old in enumerate(keep)}
    builder = MolecularGraphBuilder()
    for old in keep:
        atom = graph.atoms[old]
        builder.add_atom(
            atomic_number=atom.atomic_number,
            formal_charge=atom.formal_charge,
            implicit_hydrogens=atom.implicit_hydrogens,
            is_aromatic=atom.is_aromatic,
        )
    for bond in graph.bonds:
        if bond.atom1 in remap and bond.atom2 in remap:
            builder.add_bond(
                remap[bond.atom1],
                remap[bond.atom2],
                bond.order,
                is_aromatic=bond.is_aromatic,
            )
    return builder.build(), remap


def _attachment_atoms(
    graph: MolecularGraph,
    stars: tuple[int, ...],
    remap: dict[int, int] | None = None,
) -> tuple[int, ...]:
    """Heavy atoms bonded to the ``*`` connection points.

    ``remap`` (from :func:`_strip_wildcards`) translates indices into the
    stripped graph; pass ``None`` to keep original-graph indices.
    """
    attachments: list[int] = []
    for star in stars:
        for neighbour in graph.get_neighbors(star):
            if graph.atoms[neighbour].atomic_number in (_WILD_CARD_Z, _HYDROGEN_Z):
                continue
            attachments.append(neighbour if remap is None else remap[neighbour])
    return tuple(attachments)



def _new_graph_from_atoms(
    graph: MolecularGraph, indices: set[int]
) -> tuple[MolecularGraph, dict[int, int]]:
    """Build a subgraph preserving ``indices`` and their internal bonds."""
    remap = {old: new for new, old in enumerate(sorted(indices))}
    builder = MolecularGraphBuilder()
    for old in sorted(indices):
        atom = graph.atoms[old]
        builder.add_atom(
            atomic_number=atom.atomic_number,
            formal_charge=atom.formal_charge,
            implicit_hydrogens=atom.implicit_hydrogens,
            is_aromatic=atom.is_aromatic,
        )
    for bond in graph.bonds:
        if bond.atom1 in remap and bond.atom2 in remap:
            builder.add_bond(
                remap[bond.atom1],
                remap[bond.atom2],
                bond.order,
                is_aromatic=bond.is_aromatic,
            )
    return builder.build(), remap


def _signature(graph: MolecularGraph, index: int) -> tuple[str, int, int]:
    """Backbone signature of atom ``index``: ``(element, heavy-nb, h-count)``.

    Heavy-neighbour count distinguishes substituted positions (e.g. a
    polystyrene carbon bearing a phenyl) from plain methylene carbons.
    """
    atom = graph.atoms[index]
    return (
        atom.symbol,
        len(_heavy_neighbors(graph, index)),
        _hydrogen_count(graph, index),
    )


def _kmp_period(seq: tuple[Any, ...]) -> int:
    """Return the minimal period of ``seq`` via the KMP prefix function.

    Returns ``len(seq)`` when the sequence is aperiodic, and ``0`` for an
    empty sequence.
    """
    n = len(seq)
    if n == 0:
        return 0
    pi = [0] * n
    for i in range(1, n):
        j = pi[i - 1]
        while j > 0 and seq[i] != seq[j]:
            j = pi[j - 1]
        if seq[i] == seq[j]:
            j += 1
        pi[i] = j
    period = n - pi[n - 1]
    return period


def _backbone_path(graph: MolecularGraph) -> tuple[int, ...] | None:
    """Return the heavy-atom backbone path of a linear chain, or ``None``.

    The backbone is the shortest path between the two terminal heavy atoms
    (heavy-degree 1).  ``None`` is returned when the graph is not a simple
    linear chain: fewer or more than two terminals, or a heavy atom lies
    outside the path (i.e. the molecule is branched/cyclic).
    """
    terminals = [
        i
        for i in range(graph.num_atoms)
        if _is_real_atom(graph.atoms[i]) and len(_heavy_neighbors(graph, i)) == 1
    ]
    if len(terminals) != 2:
        return None
    path = graph.shortest_path(terminals[0], terminals[1])
    if path is None:
        return None
    path_set = set(path)
    if any(
        _is_real_atom(graph.atoms[i]) and i not in path_set
        for i in range(graph.num_atoms)
    ):
        return None  # a heavy atom lies outside the backbone -> branched
    return tuple(path)


def _has_condensation_linkage(
    graph: MolecularGraph, path: tuple[int, ...]
) -> bool:
    """True if the backbone ``path`` carries a condensation carbonyl.

    A condensation linkage is a carbonyl carbon (C double-bonded to O) that
    is *also* single-bonded to another oxygen or nitrogen along the polymer
    backbone -- the structural fingerprint of an ester / amide / carbonate
    connection between two monomer fragments (e.g. PET, PC, nylon).  A
    pendant carbonyl (PMMA's ester side group) is excluded because it does
    not lie on the backbone path.
    """
    for idx in path:
        atom = graph.atoms[idx]
        if atom.symbol != "C":
            continue
        # Locate the carbonyl oxygen (=O) bonded to this carbon.
        carbonyl_o: int | None = None
        for neighbour in graph.get_neighbors(idx):
            bond = graph.get_bond(idx, neighbour)
            if bond is not None and bond.is_double and graph.atoms[neighbour].symbol == "O":
                carbonyl_o = neighbour
                break
        if carbonyl_o is None:
            continue
        # Any OTHER O or N bonded to the carbonyl carbon (single bond) => linkage.
        for neighbour in graph.get_neighbors(idx):
            if neighbour == carbonyl_o:
                continue
            bond = graph.get_bond(idx, neighbour)
            if (
                bond is not None
                and bond.is_single
                and graph.atoms[neighbour].symbol in ("O", "N")
            ):
                return True
    return False


def _end_group_label(symbol: str, hydrogens: int, heavy_neighbors: int) -> str:
    """Human-readable label for a terminal end group.

    Labels are inferred from the (element, hydrogen-count, heavy-degree)
    triple -- the same information a user reads off an R-group formula.
    ``heavy_neighbors`` is accepted for future extension.
    """
    if symbol == "C":
        return {3: "methyl", 2: "vinyl", 1: "carbonyl/formyl"}.get(hydrogens, "methyl")
    if symbol == "O":
        return "hydroxyl" if hydrogens == 1 else "alkoxy"
    if symbol == "S":
        return "thiol" if hydrogens == 1 else "thioether"
    if symbol == "N":
        return {2: "amino", 1: "secondary-amine"}.get(hydrogens, "amine")
    if symbol in ("F", "Cl", "Br", "I"):
        return f"{symbol}-halide"
    return f"{symbol}-terminal"



# ── Data models ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EndGroup:
    """A terminal functional group of a polymer chain.

    Attributes:
        atom_index: Index of the terminal heavy atom in the analysed graph.
        element: Element symbol of the terminal atom (e.g. ``'C'``, ``'Cl'``).
        hydrogens: Number of explicit hydrogens bound to the terminal atom.
        description: Human-readable label (e.g. ``'methyl'``, ``'hydroxyl'``).
        formula: Minimal fragment formula (e.g. ``'CH3'``, ``'Cl'``, ``'OH'``).
    """

    atom_index: int
    element: str
    hydrogens: int
    description: str
    formula: str


@dataclass(frozen=True, slots=True)
class RepeatUnit:
    """The minimal repeating unit of a polymer.

    Attributes:
        graph: Wildcard-free :class:`MolecularGraph` of the repeat unit.
        attachment_atoms: Indices, in ``graph``, of the atoms that were
            bonded to the ``*`` connection points (or, for a terminal chain,
            the two boundary atoms of the period sub-unit).
        formula: Hill-system molecular formula (wildcards excluded).
        molecular_weight: Average molecular weight (wildcards excluded).
        canonical_smiles: Stable canonical SMILES for de-duplication.
        attachment_elements: Element symbols of the attachment atoms.
    """

    graph: MolecularGraph
    attachment_atoms: tuple[int, ...]
    formula: str
    molecular_weight: float
    canonical_smiles: str
    attachment_elements: tuple[str, ...]



@dataclass(frozen=True, slots=True)
class PolymerAnalysis:
    """Full polymer analysis of a molecular graph.

    Attributes:
        schema: Serialisation schema tag (forward compatibility).
        catalogue_version: Version of the polymer catalogue consulted.
        polymerization_type: ``'addition'``, ``'condensation'``,
            ``'terminal'`` (finite chain, no polymerization signature) or
            ``'none'`` (not a polymer).
        has_connection_points: Whether the input carried ``*`` junctions.
        num_connection_points: Count of ``*`` atoms in the input.
        repeat_unit: Extracted repeat unit, or ``None`` if not determinable.
                end_groups: Terminal end groups (empty for wildcard repeat-unit form).
        degree_of_polymerization: Structural DP, or ``None`` if not a linear
            periodic chain.
        number_avg_mw: Estimated number-average MW (DPn x repeat-unit MW),
            or ``None`` when not determinable.
        molecular_weight: Average molecular weight of the input (wildcards
            excluded).
        molecular_formula: Hill formula of the input (wildcards excluded).
        canonical_smiles: Canonical SMILES of the input.
    """

    schema: str = SCHEMA_VERSION
    catalogue_version: str = POLYMER_CATALOGUE_VERSION
    polymerization_type: str = "none"
    has_connection_points: bool = False
    num_connection_points: int = 0
    repeat_unit: RepeatUnit | None = None
    end_groups: tuple[EndGroup, ...] = ()
    degree_of_polymerization: int | None = None
    number_avg_mw: float | None = None
    molecular_weight: float = 0.0
    molecular_formula: str = ""
    canonical_smiles: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the analysis to a JSON-able dict."""
        from chemengine.io.serialization import graph_to_dict

        repeat_unit_dict: dict[str, Any] | None
        if self.repeat_unit is None:
            repeat_unit_dict = None
        else:
            repeat_unit_dict = {
                "graph": graph_to_dict(self.repeat_unit.graph),
                "attachment_atoms": list(self.repeat_unit.attachment_atoms),
                "formula": self.repeat_unit.formula,
                "molecular_weight": round(self.repeat_unit.molecular_weight, 6),
                "canonical_smiles": self.repeat_unit.canonical_smiles,
                "attachment_elements": list(self.repeat_unit.attachment_elements),
            }
        return {
            "schema": self.schema,
            "catalogue_version": self.catalogue_version,
            "polymerization_type": self.polymerization_type,
            "has_connection_points": self.has_connection_points,
            "num_connection_points": self.num_connection_points,
            "repeat_unit": repeat_unit_dict,
            "end_groups": [
                {
                    "atom_index": eg.atom_index,
                    "element": eg.element,
                    "hydrogens": eg.hydrogens,
                    "description": eg.description,
                    "formula": eg.formula,
                }
                for eg in self.end_groups
            ],
            "degree_of_polymerization": self.degree_of_polymerization,
            "number_avg_mw": (
                round(self.number_avg_mw, 6) if self.number_avg_mw is not None else None
            ),
            "molecular_weight": round(self.molecular_weight, 6),
            "molecular_formula": self.molecular_formula,
            "canonical_smiles": self.canonical_smiles,
        }



# ── Public algorithms ─────────────────────────────────────────────────────────


def find_connection_points(graph: MolecularGraph) -> tuple[int, ...]:
    """Return the indices of all ``*`` (wildcard) connection-point atoms.

    In a polymer SMILES these junctions mark where a repeat unit links to
    its neighbours.  A graph with no connection points is a terminal chain
    (or a non-polymer) rather than a repeat-unit form.
    """
    return tuple(
        i for i in range(graph.num_atoms) if _is_connection_point(graph.atoms[i])
    )


def _periodicity_repeat_unit(
    graph: MolecularGraph,
) -> tuple[RepeatUnit | None, int | None]:
    """Recover ``(repeat_unit, dpn)`` for a terminal chain via backbone period.

    Walks the heavy-atom backbone, computes per-atom signatures, finds the
    minimal period of the *internal* atoms and extracts the first period as
    the repeat unit.  Returns ``(None, None)`` when the chain is branched,
    cyclic or not cleanly periodic.
    """
    backbone = _backbone_path(graph)
    if backbone is None or len(backbone) < 3:
        return None, None
    signatures = tuple(_signature(graph, i) for i in backbone)
    internals = signatures[1:-1]
    period = _kmp_period(internals)
    if period == 0 or len(internals) % period != 0:
        return None, None
    # A lone internal atom is trivially periodic (period 1 == run length);
    # with two or more internals, a period equal to the whole run means no
    # smaller repeating unit exists and the backbone is not periodic.
    if len(internals) > 1 and period >= len(internals):
        return None, None
    if len(backbone) % period != 0:
        return None, None
    dpn = len(backbone) // period
    mer_backbone = set(backbone[1 : 1 + period])
    backbone_set = set(backbone)
    included: set[int] = set(mer_backbone)
    queue: list[int] = list(mer_backbone)
    while queue:
        current = queue.pop()
        for neighbour in graph.get_neighbors(current):
            if neighbour in included or neighbour in backbone_set:
                # Skip mer atoms (already included) and any other backbone
                # atom -- they belong to neighbouring repeat units.
                continue
            neighbour_atom = graph.atoms[neighbour]
            if not _is_real_atom(neighbour_atom) and neighbour_atom.atomic_number != _HYDROGEN_Z:
                continue
            included.add(neighbour)
            if neighbour_atom.atomic_number != _HYDROGEN_Z:
                queue.append(neighbour)
    ru_graph, remap = _new_graph_from_atoms(graph, included)
    attachment = (remap[backbone[1]], remap[backbone[1 + period - 1]])
    repeat_unit = RepeatUnit(
        graph=ru_graph,
        attachment_atoms=attachment,
        formula=ru_graph.molecular_formula,
        molecular_weight=ru_graph.molecular_weight,
        canonical_smiles=_canonical_smiles(ru_graph),
        attachment_elements=tuple(ru_graph.atoms[a].symbol for a in attachment),
    )
    return repeat_unit, dpn



def extract_repeat_unit(graph: MolecularGraph) -> RepeatUnit | None:
    """Extract the repeat unit from a polymer graph.

    For a ``*``-delimited repeat unit the wildcards are stripped and the
    remaining (real) atoms form the repeat unit; the attachment atoms are
    the heavy neighbours that were bonded to the connection points.  For a
    terminal chain the period-based repeat unit is recovered (see
    :func:`_periodicity_repeat_unit`).  Returns ``None`` when no repeat
    unit can be determined.
    """
    stars = find_connection_points(graph)
    if not stars:
        unit, _ = _periodicity_repeat_unit(graph)
        return unit
    stripped, remap = _strip_wildcards(graph)
    if not stripped.atoms:
        return None
    attachments = _attachment_atoms(graph, stars, remap)
    attachment_elements = tuple(
        stripped.atoms[a].symbol for a in attachments if a < stripped.num_atoms
    )
    return RepeatUnit(
        graph=stripped,
        attachment_atoms=attachments,
        formula=stripped.molecular_formula,
        molecular_weight=stripped.molecular_weight,
        canonical_smiles=_canonical_smiles(stripped),
        attachment_elements=attachment_elements,
    )


def classify_polymerization(repeat_unit: RepeatUnit | None) -> str:
    """Classify a repeat unit as ``addition`` or ``condensation``.

    Condensation is signalled by an in-chain carbonyl (C=O) that is
    single-bonded to an oxygen or nitrogen *and* lies on the backbone
    path between the two attachment atoms -- the structural fingerprint of
    an ester / amide / carbonate linkage.  A pendant carbonyl (e.g.
    poly(methyl methacrylate)) is correctly classified as ``addition``
    because it does not straddle the attachment atoms.  Returns
    ``'addition'`` as the conservative default when the attachment
    geometry is insufficient to decide.
    """
    if repeat_unit is None:
        return "addition"
    attachments = repeat_unit.attachment_atoms
    if len(attachments) < 2:
        return "addition"
    first, last = attachments[0], attachments[-1]
    if first == last:
        return "addition"  # symmetric junction (e.g. polystyrene) -- always addition
    path = repeat_unit.graph.shortest_path(first, last)
    if path is None:
        return "addition"
    if _has_condensation_linkage(repeat_unit.graph, tuple(path)):
        return "condensation"
    return "addition"


def find_end_groups(graph: MolecularGraph) -> tuple[EndGroup, ...]:
    """Identify the terminal end groups of a (non-wildcard) chain.

    Each end group is a terminal heavy atom (heavy-degree 1) together with
    its explicit hydrogens and a best-effort label.  Returns an empty tuple
    for branched, cyclic or wildcard-containing inputs.
    """
    if find_connection_points(graph):
        return ()
    groups: list[EndGroup] = []
    for atom_index in range(graph.num_atoms):
        atom = graph.atoms[atom_index]
        if not _is_real_atom(atom):
            continue
        if len(_heavy_neighbors(graph, atom_index)) != 1:
            continue
        symbol = atom.symbol
        hydrogens = _hydrogen_count(graph, atom_index)
        formula = f"{symbol}H{hydrogens}" if hydrogens else symbol
        groups.append(
            EndGroup(
                atom_index=atom_index,
                element=symbol,
                hydrogens=hydrogens,
                description=_end_group_label(symbol, hydrogens, 1),
                formula=formula,
            )
        )
    return tuple(groups)


def degree_of_polymerization(graph: MolecularGraph) -> int | None:
    """Structural degree of polymerization of ``graph``.

        For ``*``-delimited inputs a single ``*``-delimited repeat unit (two
    connection points) reports ``1``; multi-segment forms report ``None``.
    For terminal chains the backbone periodicity is computed directly.
    Returns ``None`` when the input is not a linear chain or has no
    detectable periodic repeat.
    """
    stars = find_connection_points(graph)
    if stars:
        # A ``*``-delimited fragment is a repeat-unit form, not a polymer
        # chain.  Two connection points == a single mer (DP == 1); more than
        # two is a multi-segment construction whose DP is indeterminate.
        return 1 if len(stars) == 2 else None
    backbone = _backbone_path(graph)
    if backbone is None:
        return None
    if len(backbone) < 3:
        return 1
    signatures = tuple(_signature(graph, i) for i in backbone)
    internals = signatures[1:-1]
    period = _kmp_period(internals)
    if period == 0:
        return None
    # A lone internal atom is trivially periodic (period 1 == sequence length);
    # with two or more internals, a period equal to the whole run means no
    # smaller repeating unit exists and the backbone is not periodic.
    if len(internals) > 1 and period >= len(internals):
        return None
    if len(internals) % period != 0:
        return None
    if len(backbone) % period != 0:
        return None
    return len(backbone) // period


def number_avg_mw(
    graph: MolecularGraph,
    repeat_unit: RepeatUnit | None,
    dpn: int | None,
) -> float | None:
    """Estimate the number-average molecular weight (DPn x repeat-unit MW).

    ``None`` is returned when either the repeat unit or the DP is
    unavailable, or when the input is a multi-segment ``*`` chain (whose
    de-starred graph is not a single mer).  The estimate ignores end-group
    mass, which is negligible for high-DP polymers.
    """
    if repeat_unit is None or dpn is None:
        return None
    stars = find_connection_points(graph)
    if len(stars) > 2:  # multi-segment wildcard chain -- not a single mer
        return None
    return dpn * repeat_unit.molecular_weight


def analyze_polymer(graph: MolecularGraph) -> PolymerAnalysis:
    """Analyze ``graph`` for polymer structure and properties.

    Args:
        graph: A :class:`~chemengine.core.graph.MolecularGraph` -- typically
            the result of parsing a polymer SMILES (with ``*`` junctions) or
            a terminal oligomer SMILES.

    Returns:
        A :class:`PolymerAnalysis` describing the repeat unit, end groups,
        polymerization type and (where determinable) the structural degree
        of polymerization and number-average molecular weight.
    """
    stars = find_connection_points(graph)
    has_cp = bool(stars)
    repeat_unit = extract_repeat_unit(graph)
    dpn = degree_of_polymerization(graph)
    if has_cp:
        end_groups: tuple[EndGroup, ...] = ()
        polymerization_type = classify_polymerization(repeat_unit)
    elif repeat_unit is not None:
        end_groups = find_end_groups(graph)
        backbone = _backbone_path(graph)
        if backbone is not None and _has_condensation_linkage(graph, backbone):
            polymerization_type = "condensation"
        else:
            polymerization_type = "addition"
    else:
        end_groups = find_end_groups(graph)
        polymerization_type = "terminal" if end_groups else "none"
    naw = number_avg_mw(graph, repeat_unit, dpn)
    return PolymerAnalysis(
        has_connection_points=has_cp,
        num_connection_points=len(stars),
        polymerization_type=polymerization_type,
        repeat_unit=repeat_unit,
        end_groups=end_groups,
        degree_of_polymerization=dpn,
        number_avg_mw=naw,
        molecular_weight=_mw_no_wildcards(graph),
        molecular_formula=_formula_no_wildcards(graph),
        canonical_smiles=_canonical_smiles(graph),
    )


# ── (De)serialization ─────────────────────────────────────────────────────────


def polymer_analysis_to_dict(analysis: PolymerAnalysis) -> dict[str, Any]:
    """Serialize a :class:`PolymerAnalysis` to a JSON-able dict."""
    return analysis.to_dict()


def dict_to_polymer_analysis(data: dict[str, Any]) -> PolymerAnalysis:
    """Reconstruct a :class:`PolymerAnalysis` from its dict form."""
    from chemengine.io.serialization import dict_to_graph

    repeat_unit_data = data.get("repeat_unit")
    repeat_unit: RepeatUnit | None = None
    if repeat_unit_data is not None:
        ru_graph = dict_to_graph(repeat_unit_data["graph"])
        repeat_unit = RepeatUnit(
            graph=ru_graph,
            attachment_atoms=tuple(repeat_unit_data.get("attachment_atoms", [])),
            formula=repeat_unit_data.get("formula", ru_graph.molecular_formula),
            molecular_weight=float(
                repeat_unit_data.get("molecular_weight", ru_graph.molecular_weight)
            ),
            canonical_smiles=repeat_unit_data.get("canonical_smiles", ""),
            attachment_elements=tuple(repeat_unit_data.get("attachment_elements", [])),
        )
    end_groups = tuple(
        EndGroup(
            atom_index=int(eg["atom_index"]),
            element=str(eg["element"]),
            hydrogens=int(eg["hydrogens"]),
            description=str(eg["description"]),
            formula=str(eg["formula"]),
        )
        for eg in data.get("end_groups", [])
    )
    dpn = data.get("degree_of_polymerization")
    return PolymerAnalysis(
        schema=data.get("schema", SCHEMA_VERSION),
        catalogue_version=data.get("catalogue_version", POLYMER_CATALOGUE_VERSION),
        polymerization_type=str(data.get("polymerization_type", "none")),
        has_connection_points=bool(data.get("has_connection_points", False)),
        num_connection_points=int(data.get("num_connection_points", 0)),
        repeat_unit=repeat_unit,
        end_groups=end_groups,
        degree_of_polymerization=dpn,
        number_avg_mw=(
            float(data["number_avg_mw"]) if data.get("number_avg_mw") is not None else None
        ),
        molecular_weight=float(data.get("molecular_weight", 0.0)),
        molecular_formula=str(data.get("molecular_formula", "")),
        canonical_smiles=str(data.get("canonical_smiles", "")),
    )


# ── Reference oracle ──────────────────────────────────────────────────────────


#: Curated, chemistry-checked reference polymers.  Each entry records the
#: reactant SMILES, the expected repeat-unit formula/weight, the connection
#: atoms' elements and the expected polymerization type.  Serves as living
#: documentation of the engine's contracts (mirrors M38's REFERENCE_ORACLE).
REFERENCE_POLYMER_ORACLE: dict[str, dict[str, Any]] = {
    "*CC*": {
        "name": "polyethylene (PE)",
        "repeat_unit_formula": "C2H4",
        "repeat_unit_weight": 28.054,
        "attachment_elements": ("C", "C"),
        "polymerization_type": "addition",
        "degree_of_polymerization": 1,
    },
    "*C(Cc1ccccc1)*": {
        "name": " polystyrene (PS)",
        "repeat_unit_formula": "C8H8",
        "repeat_unit_weight": 104.152,
        "attachment_elements": ("C", "C"),
        "polymerization_type": "addition",
        "degree_of_polymerization": 1,
    },
    "*OC(=O)c1ccccc1CO*": {
        "name": " polyethylene terephthalate (PET)",
        "repeat_unit_formula": "C8H6O3",
        "repeat_unit_weight": 150.133,
        "attachment_elements": ("O", "O"),
        "polymerization_type": "condensation",
        "degree_of_polymerization": 1,
    },
    "*CC(Cl)*": {
        "name": " polyvinyl chloride (PVC)",
        "repeat_unit_formula": "C2H3Cl",
        "repeat_unit_weight": 62.496,
        "attachment_elements": ("C", "C"),
        "polymerization_type": "addition",
        "degree_of_polymerization": 1,
    },
    "*CCO*": {
        "name": " polyethylene oxide / polyethylene glycol (PEO/PEG)",
        "repeat_unit_formula": "C2H4O",
        "repeat_unit_weight": 44.053,
        "attachment_elements": ("C", "O"),
        "polymerization_type": "addition",
        "degree_of_polymerization": 1,
    },
    "*C(F)(F)*": {
        "name": " polytetrafluoroethylene (PTFE)",
        "repeat_unit_formula": "CF2",
        "repeat_unit_weight": 50.014,
        "attachment_elements": ("C", "C"),
        "polymerization_type": "addition",
        "degree_of_polymerization": 1,
    },
    "*OCCN*": {
        "name": " poly(oxyethylene imine) segment",
        "repeat_unit_formula": "C2H5NO",
        "repeat_unit_weight": 59.068,
        "attachment_elements": ("O", "N"),
        "polymerization_type": "addition",
        "degree_of_polymerization": 1,
    },
    "*OC(=O)CC*": {
        "name": " hydroxy-acetate repeat (condensation)",
        "repeat_unit_formula": "C3H4O2",
        "repeat_unit_weight": 72.063,
        "attachment_elements": ("O", "C"),
        "polymerization_type": "condensation",
        "degree_of_polymerization": 1,
    },
}


def list_polymer_reference() -> tuple[str, ...]:
    """Return the canonical SMILES keys of the reference oracle."""
    return tuple(REFERENCE_POLYMER_ORACLE)







# ── Registry integration ─────────────────────────────────────────────────────


def register_polymer_algorithms(
    registry: AlgorithmRegistry | None = None, *, replace: bool = False,
) -> AlgorithmRegistry:
    """Register the M39 polymer algorithms on registry.

    Idempotent: a no-op (unless replace=True) when the polymer
    domain entries already exist.  Called by :class:`ChemEngineAPI` built-in
    setup and by tests.  No import side effects -- registration is lazy,
    preserving the `import chemengine` first-import gate.
    """
    from chemengine.core.registry import AlgorithmEntry, get_global_registry

    target = registry if registry is not None else get_global_registry()
    if ("polymer", "analyze") in target and not replace:
        logger.debug("Polymer algorithms already registered; skipping.")
        return target
    version = f"{_CATALOGUE_PREFIX}.{_CATALOGUE_VERSION_STR}"
    tags = frozenset({"polymer", "analysis", "deterministic"})
    entries: tuple[AlgorithmEntry, ...] = (
        AlgorithmEntry(
            domain="polymer",
            name="analyze",
            version=version,
            algorithm=analyze_polymer,
            input_type=MolecularGraph,
            output_type=PolymerAnalysis,
            tags=tags,
        ),
        AlgorithmEntry(
            domain="polymer",
            name="repeat_unit",
            version=version,
            algorithm=extract_repeat_unit,
            input_type=MolecularGraph,
            output_type=RepeatUnit,
            tags=frozenset({"polymer", "repeat_unit", "deterministic"}),
        ),
        AlgorithmEntry(
            domain="polymer",
            name="degree_of_polymerization",
            version=version,
            algorithm=degree_of_polymerization,
            input_type=MolecularGraph,
            output_type=int,
            tags=frozenset({"polymer", "degree_of_polymerization", "deterministic"}),
        ),
    )
    for entry in entries:
        key = (entry.domain, entry.name)
        if key in target and not replace:
            continue
        target.register(entry)
    return target

