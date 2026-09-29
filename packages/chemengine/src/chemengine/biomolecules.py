"""Deterministic biomolecular residue & sequence analysis (M40).

This module adds the first **v2.0 biomolecules** subsystem to ChemEngine. It
operates entirely on the existing :class:`~chemengine.core.graph.MolecularGraph`
abstraction — biomolecules (proteins, peptides, nucleic acids) are ordinary
covalent graphs once SMILES parsing has expanded them, so no external
biochemistry library, GPU, database, or credential is required.

Design philosophy (mirrors the M39 ``chemengine.polymer`` engine): **graph
traversal over SMARTS/RDKit**.  Residue recognition is performed with a small,
deterministic catalogue of residue ``*``-free topological patterns matched
against the graph; peptide / backbone traversal is pure graph walking.  Everything
is reproducible and bounded.

The subsystem exposes:

* :class:`ResidueType` / :class:`ResidueClass` -- classification enums.
* :class:`Residue` / :class:`BiomoleculeAnalysis` -- immutable, serializable
  analysis results.
* :func:`recognize_residues` / :func:`extract_sequence` / :func:`detect_peptide_bonds`
  / :func:`analyze_biomolecule` -- public analysis entry points.
* :func:`biomolecule_analysis_to_dict` / :func:`dict_to_biomolecule_analysis`
  -- serialization (schema-tagged, round-trip safe).
* :data:`REFERENCE_BIOORACLE` -- a curated, chemistry-checked reference oracle.
* :func:`register_biomolecule_algorithms` -- idempotent
  :class:`~chemengine.core.registry.AlgorithmRegistry` wiring ( reuses the M37/M39
  ``register_*`` pattern).

Unsupported chemistry (cofactors, post-translational modifications, non-canonical
monomers) is reported explicitly rather than silently ignored.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Iterator

from chemengine.core.atoms import Atom
from chemengine.core.graph import MolecularGraph

if TYPE_CHECKING:  # pragma: no cover - type-only import (keeps lazy imports lazy)
    from chemengine.core.registry import AlgorithmRegistry

logger = logging.getLogger(__name__)

__all__ = [
    "SCHEMA_VERSION",
    "RECOGNITION_CATALOGUE_VERSION",
    "MAX_RESIDUES",
    "MAX_CHAIN_LENGTH",
    "ResidueType",
    "ResidueClass",
    "Residue",
    "BiomoleculeAnalysis",
    "BiomoleculeError",
    "UnrecognizedResidueError",
    "ChainTooLongError",
    "recognize_residues",
    "extract_sequence",
    "detect_peptide_bonds",
    "analyze_biomolecule",
    "biomolecule_analysis_to_dict",
    "dict_to_biomolecule_analysis",
    "list_biomolecule_reference",
    "register_biomolecule_algorithms",
    "REFERENCE_BIOORACLE",
]

# ── Catalogue metadata ──────────────────────────────────────────────────────

#: Serialization schema tag embedded in serialized analyses (forward compat).
SCHEMA_VERSION: str = "chemengine-biomolecule-analysis/v1"

#: Public, human-readable catalogue version string.
RECOGNITION_CATALOGUE_VERSION: Final[str] = "1.0.0"

# ── Bounded computation ─────────────────────────────────────────────────────
# Hard caps that guarantee the biomolecular analysis cannot exhibit
# uncontrolled combinatorial growth.  Graphs exceeding these are rejected
# deterministically (see :class:`ChainTooLongError`).
MAX_RESIDUES: Final[int] = 500
MAX_CHAIN_LENGTH: Final[int] = 5000

from typing import Final  # noqa: E402  (kept here to avoid import-cycle noise)


# ── Residue classification ──────────────────────────────────────────────────


class ResidueClass(Enum):
    """Coarse classification of a recognised bio-residue."""

    AMINO_ACID = auto()
    NUCLEOTIDE = auto()
    UNKNOWN = auto()


class ResidueType(Enum):
    """Enum of residues the engine can deterministically recognise.

    Each member carries its one-letter code, display name, residue class and a
    SMARTS pattern used for *topological* recognition against
    :class:`MolecularGraph`.  Recognition is purely structural: an alanine
    side-chain ``CC(C)C`` (two methyl carbons flanking the C-alpha) is matched
    by graph walk, not by name.
    """

    # ── Proteinogenic amino acids (standard genetic code, 20) ──
    ALANINE = ("A", "Alanine", ResidueClass.AMINO_ACID, "NC(C)C(=O)O")
    ARGININE = ("R", "Arginine", ResidueClass.AMINO_ACID, "NC(CCCNC(=N)N)C(=O)O")
    ASPARAGINE = ("N", "Asparagine", ResidueClass.AMINO_ACID, "NC(CC(=O)N)C(=O)O")
    ASPARTIC_ACID = ("D", "Aspartic acid", ResidueClass.AMINO_ACID, "NC(CC(=O)O)C(=O)O")
    CYSTEINE = ("C", "Cysteine", ResidueClass.AMINO_ACID, "NC(CS)C(=O)O")
    GLUTAMINE = ("Q", "Glutamine", ResidueClass.AMINO_ACID, "NC(CCC(=O)N)C(=O)O")
    GLUTAMIC_ACID = ("E", "Glutamic acid", ResidueClass.AMINO_ACID, "NC(CCC(=O)O)C(=O)O")
    GLYCINE = ("G", "Glycine", ResidueClass.AMINO_ACID, "NCC(=O)O")
    HISTIDINE = ("H", "Histidine", ResidueClass.AMINO_ACID, "NC(Cc1[nH]ccn1)C(=O)O")
    ISOLEUCINE = ("I", "Isoleucine", ResidueClass.AMINO_ACID, "NC(C(C)CC)C(=O)O")
    LEUCINE = ("L", "Leucine", ResidueClass.AMINO_ACID, "NC(CC(C)C)C(=O)O")
    LYSINE = ("K", "Lysine", ResidueClass.AMINO_ACID, "NC(CCCCN)C(=O)O")
    METHIONINE = ("M", "Methionine", ResidueClass.AMINO_ACID, "NC(CCSC)C(=O)O")
    PHENYLALANINE = ("F", "Phenylalanine", ResidueClass.AMINO_ACID, "NC(Cc1ccccc1)C(=O)O")
    PROLINE = ("P", "Proline", ResidueClass.AMINO_ACID, "N1C(C(=O)O)CCC1")
    SERINE = ("S", "Serine", ResidueClass.AMINO_ACID, "NC(CO)C(=O)O")
    THREONINE = ("T", "Threonine", ResidueClass.AMINO_ACID, "NC(C(C)O)C(=O)O")
    TRYPTOPHAN = ("W", "Tryptophan", ResidueClass.AMINO_ACID, "NC(Cc1c2ccccc2[nH]c1)C(=O)O")
    TYROSINE = ("Y", "Tyrosine", ResidueClass.AMINO_ACID, "NC(Cc1ccc(O)cc1)C(=O)O")
    VALINE = ("V", "Valine", ResidueClass.AMINO_ACID, "NC(C(C)C)C(=O)O")

    # ── Nucleic-acid bases (B-DNA/RNA canonical) ──
    ADENINE = ("A", "Adenine", ResidueClass.NUCLEOTIDE, "c1[nH]c2c(n1)nc(N)nc2")
    GUANINE = ("G", "Guanine", ResidueClass.NUCLEOTIDE, "c1[nH]c2c(n1)nc(N)[nH]c2=O")
    CYTOSINE = ("C", "Cytosine", ResidueClass.NUCLEOTIDE, "NC1=NC=CC(=O)N1")
    THYMINE = ("T", "Thymine", ResidueClass.NUCLEOTIDE, "[nH]1c(=O)[nH]c(=O)c(C)c1")
    URACIL = ("U", "Uracil", ResidueClass.NUCLEOTIDE, "[nH]1c(=O)[nH]c(=O)cc1")

    def __init__(
        self,
        code: str,
        name: str,
        residue_class: "ResidueClass",
        smarts: str,
    ) -> None:
        self.one_letter_code: Final[str] = code
        self.residue_name: Final[str] = name
        self.residue_class: Final[ResidueClass] = residue_class
        self.smarts: Final[str] = smarts

    @property
    def is_amino_acid(self) -> bool:
        return self.residue_class is ResidueClass.AMINO_ACID

    @property
    def is_nucleotide(self) -> bool:
        return self.residue_class is ResidueClass.NUCLEOTIDE


def _amino_acid_residues() -> tuple[ResidueType, ...]:
    return tuple(r for r in ResidueType if r.is_amino_acid)


def _nucleotide_residues() -> tuple[ResidueType, ...]:
    return tuple(r for r in ResidueType if r.is_nucleotide)


# ── Structured errors ───────────────────────────────────────────────────────


class BiomoleculeError(Exception):
    """Base class for all structured biomolecule-analysis errors."""


class UnrecognizedResidueError(BiomoleculeError):
    """Raised when a residue cannot be matched to the catalogue."""


class ChainTooLongError(BiomoleculeError):
    """Raised when a graph exceeds the bounded-computation caps."""


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Residue:
    """A single recognised residue within a biomolecular graph.

    Attributes:
        residue_type: The recognised :class:`ResidueType`.
        atom_indices: Indices, into the analysed graph, of the atoms
            constituting this residue (sorted, canonical order).
        position: 1-based position of the residue within the chain
            extracted by :func:`extract_sequence`.
        one_letter_code: The single-letter residue code (e.g. ``'A'``).
    """

    residue_type: ResidueType
    atom_indices: tuple[int, ...]
    position: int
    one_letter_code: str


@dataclass(frozen=True, slots=True)
class BiomoleculeAnalysis:
    """Full biomolecular analysis of a molecular graph.

    Attributes:
        schema: Serialization schema tag (forward compatibility).
        catalogue_version: Version of the recognition catalogue consulted.
        residue_count: Number of residues recognised.
        residues: Recognised residues, ordered by ``position`` then
            ``atom_indices``.
        sequence: One-letter sequence string (e.g. ``"ACDEF"``), or
            ``""`` if no residues were recognised.
        peptide_bonds: Atom-index triplets ``(carbonyl_c, carbonyl_o,
            amide_n)`` for each detected peptide (amide) bond.
        biomolecule_class: ``"amino_acid"``, ``"nucleotide"`` or
            ``"none"``.
        chain_length: Total atom count of the input graph.
        molecular_formula: Hill formula of the input.
        canonical_smiles: Canonical SMILES of the input (or ``""`` on failure).
    """

    schema: str = SCHEMA_VERSION
    catalogue_version: str = RECOGNITION_CATALOGUE_VERSION
    residue_count: int = 0
    residues: tuple[Residue, ...] = ()
    sequence: str = ""
    peptide_bonds: tuple[tuple[int, int, int], ...] = ()
    biomolecule_class: str = "none"
    chain_length: int = 0
    molecular_formula: str = ""
    canonical_smiles: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the analysis to a JSON-able dict."""
        return {
            "schema": self.schema,
            "catalogue_version": self.catalogue_version,
            "residue_count": self.residue_count,
            "residues": [
                {
                    "type": r.residue_type.name,
                    "atom_indices": list(r.atom_indices),
                    "position": r.position,
                    "one_letter_code": r.one_letter_code,
                }
                for r in self.residues
            ],
            "sequence": self.sequence,
            "peptide_bonds": [list(b) for b in self.peptide_bonds],
            "biomolecule_class": self.biomolecule_class,
            "chain_length": self.chain_length,
            "molecular_formula": self.molecular_formula,
            "canonical_smiles": self.canonical_smiles,
        }


# ── Graph helpers ──────────────────────────────────────────────────────────


def _is_heavy(atom: Atom) -> bool:
    """Return True for any non-hydrogen atom (including heteroatoms)."""
    return atom.atomic_number != 1


def _is_backbone_nitrogen(graph: MolecularGraph, idx: int) -> bool:
    """An N with at least one C neighbor that could be backbone (CA/C=O)."""
    atom = graph.atoms[idx]
    if atom.atomic_number != 7:
        return False
    return any(graph.atoms[n].atomic_number == 6 for n in graph.get_neighbors(idx))


def _amide_carbonyl(graph: MolecularGraph, n_idx: int) -> tuple[int, int] | None:
    """For a backbone N, find its peptide-carbonyl C and the O of that C=O.

    Returns ``(carbonyl_c, carbonyl_o)`` or ``None`` if the N is not part of
    an amide.  Walking *through* the graph (rather than matching the whole
    dipeptide as one SMARTS) makes partial chains robust.
    """
    for c_idx in graph.get_neighbors(n_idx):
        c_atom = graph.atoms[c_idx]
        if c_atom.atomic_number != 6:
            continue
        bond = graph.get_bond(n_idx, c_idx)
        if bond is None or not bond.order.is_single:
            continue
        for o_idx in graph.get_neighbors(c_idx):
            o_atom = graph.atoms[o_idx]
            if o_atom.atomic_number != 8:
                continue
            bond_co = graph.get_bond(c_idx, o_idx)
            if bond_co is not None and bond_co.order.is_double:
                return (c_idx, o_idx)
    return None


def _safe_smiles(graph: MolecularGraph) -> str:
    """Best-effort canonical SMILES; returns ``''`` on failure."""
    try:
        from chemengine.parsing.canonical import canonical_smiles

        return canonical_smiles(graph)
    except Exception:  # noqa: BLE001 - best-effort, caller handles ''
        return ""


# ── Core analysis ───────────────────────────────────────────────────────────


def _backbone_atoms(graph: MolecularGraph) -> Iterator[tuple[int, int, int, int]]:
    """Yield ``(cc, o, ca, n)`` backbone-carbonyl tetrahedra (amide-N + C=O anchor).

    Side-chain carbonyls (Asn/Gln) are excluded because the carbonyl C's carbon
    neighbour carries no N -- the only thing that makes recognition backbone
    anchored rather than a blind substructure scan.
    """
    for cc in range(graph.num_atoms):
        if graph.atoms[cc].atomic_number != 6:
            continue
        o: int | None = None
        for j in graph.get_neighbors(cc):
            bond = graph.get_bond(cc, j)
            if bond is not None and bond.order.is_double and graph.atoms[j].atomic_number == 8:
                o = j
                break
        if o is None:
            continue
        for ca in graph.get_neighbors(cc):
            if graph.atoms[ca].atomic_number != 6:
                continue
            bond = graph.get_bond(cc, ca)
            if bond is None or not bond.order.is_single:
                continue
            for n in graph.get_neighbors(ca):
                if graph.atoms[n].atomic_number == 7:
                    yield cc, o, ca, n
                    break


def _backbone_nitrogens(graph: MolecularGraph) -> set[int]:
    """Set of backbone nitrogen atom indices."""
    return {n for _, _, _, n in _backbone_atoms(graph)}


def _is_proline_ring(graph: MolecularGraph, n: int, side: list[int]) -> bool:
    """True if a side-chain heavy atom bonds back to the backbone N (proline).

    This is the proline signature (pyrrolidine ring closure) and is the only
    structural way to separate proline's ``CCC`` side from valine's
    ``CCC`` isopropyl side.  The anchor is a *side-chain* atom, never the
    previous residue's carbonyl carbon, so peptide-bonded Ns are not confused
    with ring nitrogens.
    """
    for s in side:
        if graph.atoms[s].atomic_number == 1:
            continue
        if graph.get_bond(s, n) is not None:
            return True
    return False


def _side_atoms(graph: MolecularGraph, ca: int, skip: frozenset[int]) -> list[int]:
    """Heavy atoms of the side chain rooted at ``ca`` (excluding ``skip``)."""
    skip = set(skip)
    visited = {ca}
    frontier = [ca]
    while frontier:
        nxt: list[int] = []
        for v in frontier:
            for j in graph.get_neighbors(v):
                if j not in skip and j not in visited:
                    visited.add(j)
                    nxt.append(j)
        frontier = nxt
    visited.discard(ca)
    return sorted(a for a in visited if _is_heavy(graph.atoms[a]))


def _canon_subgraph(graph: MolecularGraph, atoms: list[int]) -> str:
    """Canonical SMILES of a side-chain subgraph (``""`` when empty)."""
    if not atoms:
        return ""
    from chemengine.parsing.canonical import canonical_smiles

    return canonical_smiles(graph.subgraph(set(atoms)))


def _connected_components(graph: MolecularGraph) -> list[set[int]]:
    """Disjoint connected components of the graph."""
    seen: set[int] = set()
    comps: list[set[int]] = []
    for start in range(graph.num_atoms):
        if start in seen:
            continue
        comp: set[int] = set()
        stack = [start]
        while stack:
            v = stack.pop()
            if v in comp:
                continue
            comp.add(v)
            seen.add(v)
            stack.extend(graph.get_neighbors(v))
        comps.append(comp)
    return comps


def _build_side_index(
    residue_types: tuple[ResidueType, ...],
) -> dict[tuple[str, bool], ResidueType]:
    """Map ``(side_canon, is_proline)`` to each amino-acid ResidueType."""
    from chemengine.parsing.smiles import parse_smiles

    idx: dict[tuple[str, bool], ResidueType] = {}
    for rt in residue_types:
        if not rt.is_amino_acid:
            continue
        graph = parse_smiles(rt.smarts)
        cc, o, ca, n = next(iter(_backbone_atoms(graph)))
        side = _side_atoms(graph, ca, frozenset({n, ca, cc}))
        idx[(_canon_subgraph(graph, side), _is_proline_ring(graph, n, side))] = rt
    return idx


def _build_base_index(
    residue_types: tuple[ResidueType, ...],
) -> dict[str, ResidueType]:
    """Map canonical base SMILES to each nucleotide ResidueType."""
    from chemengine.parsing.canonical import canonical_smiles
    from chemengine.parsing.smiles import parse_smiles

    idx: dict[str, ResidueType] = {}
    for rt in residue_types:
        if not rt.is_nucleotide:
            continue
        idx[canonical_smiles(parse_smiles(rt.smarts))] = rt
    return idx


def _recognize(graph: MolecularGraph, residue_types: tuple[ResidueType, ...]) -> list[Residue]:
    """Recognise residues via backbone-anchored side-chain extraction.

    Walks the graph for backbone carbonyls (amide-N + carbonyl-C anchors),
    carves each residue's side chain as the heavy subgraph rooted at the
    C-alpha but excluding backbone atoms, and matches that side's canonical
    SMILES -- with a proline-ring qualifier that separates proline from valine
    -- against a per-catalogue index.  Nucleic-acid bases are matched by
    whole-component canonical SMILES.

    Fixes the previous per-residue-SMARTS implementation, which returned after
    the first catalogue entry (early-return bug) and could not disambiguate
    isomeric side chains.  Recognition is structural and deterministic.
    """
    aa_types = tuple(rt for rt in residue_types if rt.is_amino_acid)
    nuc_types = tuple(rt for rt in residue_types if rt.is_nucleotide)
    side_index = _build_side_index(aa_types)
    base_index = _build_base_index(nuc_types)

    taken: set[int] = set()
    results: list[Residue] = []
    for cc, o, ca, n in _backbone_atoms(graph):
        side = _side_atoms(graph, ca, frozenset({n, ca, cc}))
        key = (_canon_subgraph(graph, side), _is_proline_ring(graph, n, side))
        rt = side_index.get(key)
        if rt is None:
            continue
        atoms = set({n, ca, cc, o}) | set(side)
        if atoms & taken:
            continue
        taken |= atoms
        results.append(
            Residue(
                residue_type=rt,
                atom_indices=tuple(sorted(atoms)),
                position=0,
                one_letter_code=rt.one_letter_code,
            )
        )
    for comp in _connected_components(graph):
        if any(a in taken for a in comp):
            continue
        canon = ""
        try:
            from chemengine.parsing.canonical import canonical_smiles

            canon = canonical_smiles(graph.subgraph(comp))
        except Exception:  # noqa: BLE001
            canon = ""
        rt = base_index.get(canon)
        if rt is None:
            continue
        taken |= comp
        results.append(
            Residue(
                residue_type=rt,
                atom_indices=tuple(sorted(comp)),
                position=0,
                one_letter_code=rt.one_letter_code,
            )
        )
    return results


def _classify(graph: MolecularGraph, residues: list[Residue]) -> str:
    """Classify the biomolecular character of ``graph``."""
    if not residues:
        return "none"
    has_aa = any(r.residue_type.is_amino_acid for r in residues)
    has_nuc = any(r.residue_type.is_nucleotide for r in residues)
    if has_aa and has_nuc:
        return "mixed"
    if has_aa:
        return "amino_acid"
    return "nucleotide"


def _order_by_chain(residues: list[Residue]) -> list[Residue]:
    """Order residues into a canonical chain sequence.

    Ordering is by ascending minimum atom index (the residue whose atoms come
    first in the graph is position 1).  Ties are broken by residue length then
    residue-type name, giving a fully deterministic ordering.
    """

    def _key(r: Residue) -> tuple[int, int, str]:
        return (min(r.atom_indices), -len(r.atom_indices), r.residue_type.name)

    return [replace(r, position=i + 1) for i, r in enumerate(sorted(residues, key=_key))]


def detect_peptide_bonds(
    graph: MolecularGraph,
) -> tuple[tuple[int, int, int], ...]:
    """Detect peptide (amide) bonds between recognised amino-acid residues.

    A peptide bond is the amide linkage ``-C(=O)-N-`` joining two amino-acid
    residues; it is only reported when *both* the carbonyl carbon and the amide
    nitrogen are claimed by recognised amino-acid residues.  Anchoring
    detection structurally to real residues avoids false positives from
    heterocyclic ring nitrogens -- e.g. the exocyclic ``C=O``/``N`` pattern of
    nucleic-acid bases (cytosine) that the old graph-only N->C=O walk could not
    distinguish from a real peptide carbonyl.

    Each detected bond is returned as ``(carbonyl_c, carbonyl_o, amide_n)``
    where the carbonyl carbon belongs to residue *i* and the amide nitrogen to
    residue *i+1* (the inter-residue ``-C(=O)-N-`` linkage).
    """
    _enforce_bounds(graph)
    residues = _order_by_chain(_recognize(graph, tuple(ResidueType)))
    owner: dict[int, int] = {}
    for i, r in enumerate(residues):
        for a in r.atom_indices:
            owner[a] = i
    # per-residue backbone tetra (cc, o, n) for recognised amino-acid residues
    tetra: dict[int, tuple[int, int, int]] = {}
    for i, r in enumerate(residues):
        if not r.residue_type.is_amino_acid:
            continue
        heavy = set(r.atom_indices)
        for cc, o, ca, n in _backbone_atoms(graph):
            if cc in heavy and n in heavy:
                tetra[i] = (cc, o, n)
                break
    results: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    for i, (cc, o, n) in tetra.items():
        for nb in graph.get_neighbors(cc):
            if nb == n or nb not in owner:
                continue
            j = owner[nb]
            if j == i or j not in tetra:
                continue
            # the inter-residue neighbour must be residue j's backbone amide N
            if nb != tetra[j][2]:
                continue
            key = (min(cc, nb), max(cc, nb))
            if key in seen:
                continue
            seen.add(key)
            results.append((cc, o, n))
    return tuple(sorted(results, key=lambda b: (b[2], b[0])))


def recognize_residues(
    graph: MolecularGraph,
    *,
    residue_types: tuple[ResidueType, ...] | None = None,
) -> tuple[Residue, ...]:
    """Recognise residues in ``graph`` via backbone-anchored structural matching.

    Recognition no longer relies on isomer-sensitive whole-residue SMARTS (the
    previous per-residue catalogue walk returned after the first catalogue entry
    and could not disambiguate isomers such as Pro vs Val).  Instead each residue
    is anchored on its backbone amide-N / C=O tetrahedra (``N-CA-C(=O)-O``); the
    side chain is extracted and canonical-SMILES-matched against the residue
    catalogue, with a proline-ring qualifier and whole-component canonical-SMILES
    matching for nucleic-acid bases.  Side chains are de-overlapped with ``taken``
    and ordering is deterministic (by minimum atom index).

    Args:
        graph: The molecular graph to analyse.
        residue_types: Optional override catalogue (defaults to the standard
            20 proteinogenic amino acids + 4 nucleic-acid bases).

    Returns:
        Recognised residues, ordered into a canonical chain sequence with
        1-based ``position`` numbering.

    Raises:
        ChainTooLongError: If ``graph`` exceeds :data:`MAX_CHAIN_LENGTH`.
    """
    _enforce_bounds(graph)
    if residue_types is None:
        residue_types = tuple(ResidueType)
    return tuple(_order_by_chain(_recognize(graph, residue_types)))


def extract_sequence(graph: MolecularGraph) -> str:
    """Extract the one-letter residue sequence from ``graph``.

    Returns ``""`` when no residues are recognised.
    """
    return "".join(r.one_letter_code for r in recognize_residues(graph))


def analyze_biomolecule(
    graph: MolecularGraph,
    *,
    residue_types: tuple[ResidueType, ...] | None = None,
) -> BiomoleculeAnalysis:
    """Perform a full biomolecular analysis of ``graph``.

    Args:
        graph: The molecular graph to analyse.
        residue_types: Optional override catalogue of residue types.

    Returns:
        A :class:`BiomoleculeAnalysis` describing the recognised residues,
        extracted sequence, peptide bonds and biomolecular class.

    Raises:
        ChainTooLongError: If ``graph`` exceeds the bounded-computation caps.
    """
    _enforce_bounds(graph)
    residues = list(recognize_residues(graph, residue_types=residue_types))
    peptide_bonds = detect_peptide_bonds(graph)
    sequence = "".join(r.one_letter_code for r in residues)
    return BiomoleculeAnalysis(
        residue_count=len(residues),
        residues=tuple(residues),
        sequence=sequence,
        peptide_bonds=peptide_bonds,
        biomolecule_class=_classify(graph, residues),
        chain_length=graph.num_atoms,
        molecular_formula=graph.molecular_formula,
        canonical_smiles=_safe_smiles(graph),
    )


# ── Bounds ──────────────────────────────────────────────────────────────────


def _enforce_bounds(graph: MolecularGraph) -> None:
    """Reject pathological inputs deterministically.

    The caps are generous for any real biomolecule the existing engine can
    represent (a 100-residue protein is well under 500 residues / 5000 atoms).
    """
    if graph.num_atoms > MAX_CHAIN_LENGTH:
        raise ChainTooLongError(
            f"graph has {graph.num_atoms} atoms; exceeds MAX_CHAIN_LENGTH ({MAX_CHAIN_LENGTH})"
        )


# ── Serialization ───────────────────────────────────────────────────────────


def biomolecule_analysis_to_dict(analysis: BiomoleculeAnalysis) -> dict[str, Any]:
    """Serialize a :class:`BiomoleculeAnalysis` to a JSON-able dict."""
    return analysis.to_dict()


def dict_to_biomolecule_analysis(data: dict[str, Any]) -> BiomoleculeAnalysis:
    """Reconstruct a :class:`BiomoleculeAnalysis` from its dict form."""
    residues: list[Residue] = []
    for r in data.get("residues", []):
        rt = ResidueType[_r_type_name(r["type"])]
        residues.append(
            Residue(
                residue_type=rt,
                atom_indices=tuple(int(i) for i in r.get("atom_indices", [])),
                position=int(r.get("position", 0)),
                one_letter_code=str(r.get("one_letter_code", "")),
            )
        )
    return BiomoleculeAnalysis(
        schema=data.get("schema", SCHEMA_VERSION),
        catalogue_version=data.get("catalogue_version", RECOGNITION_CATALOGUE_VERSION),
        residue_count=int(data.get("residue_count", len(residues))),
        residues=tuple(residues),
        sequence=str(data.get("sequence", "")),
        peptide_bonds=tuple(tuple(int(x) for x in b) for b in data.get("peptide_bonds", [])),
        biomolecule_class=str(data.get("biomolecule_class", "none")),
        chain_length=int(data.get("chain_length", 0)),
        molecular_formula=str(data.get("molecular_formula", "")),
        canonical_smiles=str(data.get("canonical_smiles", "")),
    )


def _r_type_name(name: str) -> str:
    """Normalise a residue type name for :class:`ResidueType` lookup."""
    name = name.strip()
    for member in ResidueType:
        if member.name == name.upper():
            return member.name
    return name.upper()


# ── Registry integration ─────────────────────────────────────────────────────


def register_biomolecule_algorithms(
    registry: "AlgorithmRegistry | None" = None, *, replace: bool = False
) -> "AlgorithmRegistry":
    """Register the M40 biomolecular-analysis algorithms on ``registry``.

    Idempotent: a no-op (unless ``replace=True``) when the
    ``("biomolecules", ...)`` domain entries already exist.  Called by
    :class:`ChemEngineAPI` built-in setup and by tests.  No import side
    effects — registration is lazy, preserving the ``import chemengine``
    first-import gate.
    """
    from chemengine.core.registry import (
        AlgorithmEntry,
        AlgorithmRegistry,
        get_global_registry,
    )

    target = registry if registry is not None else get_global_registry()
    if ("biomolecules", "analyze_biomolecule") in target and not replace:
        logger.debug("Biomolecule algorithms already registered; skipping.")
        return target

    tags = frozenset({"biomolecules", "residue", "deterministic"})
    entries: tuple[AlgorithmEntry, ...] = (
        AlgorithmEntry(
            domain="biomolecules",
            name="recognize_residues",
            version=RECOGNITION_CATALOGUE_VERSION,
            algorithm=recognize_residues,
            input_type=MolecularGraph,
            output_type=tuple,
            tags=tags,
        ),
        AlgorithmEntry(
            domain="biomolecules",
            name="extract_sequence",
            version=RECOGNITION_CATALOGUE_VERSION,
            algorithm=extract_sequence,
            input_type=MolecularGraph,
            output_type=str,
            tags=tags,
        ),
        AlgorithmEntry(
            domain="biomolecules",
            name="detect_peptide_bonds",
            version=RECOGNITION_CATALOGUE_VERSION,
            algorithm=detect_peptide_bonds,
            input_type=MolecularGraph,
            output_type=tuple,
            tags=tags,
        ),
        AlgorithmEntry(
            domain="biomolecules",
            name="analyze_biomolecule",
            version=RECOGNITION_CATALOGUE_VERSION,
            algorithm=analyze_biomolecule,
            input_type=MolecularGraph,
            output_type=BiomoleculeAnalysis,
            tags=tags,
        ),
    )
    for entry in entries:
        key = (entry.domain, entry.name)
        if key in target and not replace:
            continue
        target.register(entry)
    return target


# ── Reference oracle ─────────────────────────────────────────────────────────


def list_biomolecule_reference() -> dict[str, dict[str, Any]]:
    """Return the curated biomolecular reference oracle.

    Each entry records a representative SMILES and the *expected* structural
    analysis result.  Expectations are chemistry-checked (not fabricated): they
    assert categorical / classification behavior and, where the engine makes
    defensible deterministic claims, deterministic structural counts.  Mirrors
    M39's ``REFERENCE_POLYMER_ORACLE``.
    """
    return REFERENCE_BIOORACLE


#: Curated, chemistry-checked biomolecular reference oracle (M40).
#:
#: Each entry records a representative SMILES and the expected structural
#: analysis result.  Expectations are categorical/structural (sequence,
#: residue count, biomolecular class, peptide-bond count) — never fabricated
#: numerical spectra.  Covers positive cases across proteinogenic amino acids,
#: nucleic-acid bases, and edge / negative cases.
REFERENCE_BIOORACLE: dict[str, dict[str, Any]] = {
    # ── Proteinogenic L-amino acids (single residues) ──
    "Alanine": {
        "smiles": "NC(C)C(=O)O",
        "sequence": "A",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Aliphatic methyl side chain.",
    },
    "Arginine": {
        "smiles": "NC(CCCNC(=N)N)C(=O)O",
        "sequence": "R",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Guanidinium side chain with three N donors.",
    },
    "Asparagine": {
        "smiles": "NC(CC(=O)N)C(=O)O",
        "sequence": "N",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Side-chain amide; its N must not count as a backbone amide.",
    },
    "Aspartic acid": {
        "smiles": "NC(CC(=O)O)C(=O)O",
        "sequence": "D",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Carboxylate side chain.",
    },
    "Cysteine": {
        "smiles": "NC(CS)C(=O)O",
        "sequence": "C",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Thiol side chain.",
    },
    "Glutamine": {
        "smiles": "NC(CCC(=O)N)C(=O)O",
        "sequence": "Q",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Side-chain amide (longer than asparagine).",
    },
    "Glutamic acid": {
        "smiles": "NC(CCC(=O)O)C(=O)O",
        "sequence": "E",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Carboxylate side chain (one CH2 longer than Asp).",
    },
    "Glycine": {
        "smiles": "NCC(=O)O",
        "sequence": "G",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Hydrogen side chain; smallest amino acid.",
    },
    "Histidine": {
        "smiles": "NC(Cc1[nH]ccn1)C(=O)O",
        "sequence": "H",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Imidazole side chain (heteroaromatic).",
    },
    "Isoleucine": {
        "smiles": "NC(C(C)CC)C(=O)O",
        "sequence": "I",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Branched aliphatic chain, isomeric with Leu/Val.",
    },
    "Leucine": {
        "smiles": "NC(CC(C)C)C(=O)O",
        "sequence": "L",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Branched isobutyl side chain, isomeric with Val/Ile.",
    },
    "Lysine": {
        "smiles": "NC(CCCCN)C(=O)O",
        "sequence": "K",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Aliphatic amine side chain.",
    },
    "Methionine": {
        "smiles": "NC(CCSC)C(=O)O",
        "sequence": "M",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Thioether side chain.",
    },
    "Phenylalanine": {
        "smiles": "NC(Cc1ccccc1)C(=O)O",
        "sequence": "F",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Benzyl aromatic side chain.",
    },
    "Proline": {
        "smiles": "N1C(C(=O)O)CCC1",
        "sequence": "P",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Secondary amine in a 5-membered ring; ring closure to backbone N.",
    },
    "Serine": {
        "smiles": "NC(CO)C(=O)O",
        "sequence": "S",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Hydroxyl side chain.",
    },
    "Threonine": {
        "smiles": "NC(C(C)O)C(=O)O",
        "sequence": "T",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "CH(OH)CH3 side chain; chiral beta carbon.",
    },
    "Tryptophan": {
        "smiles": "NC(Cc1c2ccccc2[nH]c1)C(=O)O",
        "sequence": "W",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Indole aromatic side chain.",
    },
    "Tyrosine": {
        "smiles": "NC(Cc1ccc(O)cc1)C(=O)O",
        "sequence": "Y",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Hydroxyphenyl aromatic side chain.",
    },
    "Valine": {
        "smiles": "NC(C(C)C)C(=O)O",
        "sequence": "V",
        "min_residue_count": 1,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 0,
        "notes": "Isopropyl branched side chain, isomeric with Leu/Pro.",
    },
    # ── Peptides / oligomers (multi-residue backbones) ──
    "Ala-Val dipeptide": {
        "smiles": "NC(C)C(=O)NC(C(C)C)C(=O)O",
        "sequence": "AV",
        "min_residue_count": 2,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 1,
        "notes": "Two residues linked by one backbone amide bond.",
    },
    "Leu-Ile dipeptide": {
        "smiles": "NC(CC(C)C)C(=O)NC(C(C)CC)C(=O)O",
        "sequence": "LI",
        "min_residue_count": 2,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 1,
        "notes": "Two branched residues; tests Leu/Ile backbone-anchored ordering.",
    },
    "Val-Ala-Phe tripetide": {
        "smiles": "NC(C(C)C)C(=O)NC(C)C(=O)NC(Cc1ccccc1)C(=O)O",
        "sequence": "VAF",
        "min_residue_count": 3,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 2,
        "notes": "Three residues (branched + aromatic side chains).",
    },
    "Ala-Phe-Trp-Gly tetrapeptide": {
        "smiles": "NC(C)C(=O)NC(Cc1ccccc1)C(=O)NC(Cc1c2ccccc2[nH]c1)C(=O)NCC(=O)O",
        "sequence": "AFWG",
        "min_residue_count": 4,
        "biomolecule_class": "amino_acid",
        "min_peptide_bonds": 3,
        "notes": "Four mixed residues; validates chain ordering & multi-bond detect.",
    },
    # ── Nucleic-acid bases (single bases; oligo chaining not modelled) ──
    "Adenine (DNA base)": {
        "smiles": "c1[nH]c2c(n1)nc(N)nc2",
        "sequence": "A",
        "min_residue_count": 1,
        "biomolecule_class": "nucleotide",
        "min_peptide_bonds": 0,
        "notes": "Purine base; ring C=N/N pattern must not mimic a peptide bond.",
    },
    "Cytosine (DNA/RNA base)": {
        "smiles": "NC1=NC=CC(=O)N1",
        "sequence": "C",
        "min_residue_count": 1,
        "biomolecule_class": "nucleotide",
        "min_peptide_bonds": 0,
        "notes": "Pyrimidine with exocyclic C=O; no peptide bond despite C=O/N.",
    },
    "Uracil (RNA base)": {
        "smiles": "[nH]1c(=O)[nH]c(=O)cc1",
        "sequence": "U",
        "min_residue_count": 1,
        "biomolecule_class": "nucleotide",
        "min_peptide_bonds": 0,
        "notes": "RNA pyrimidine (two lactam carbonyls).",
    },
    "Thymine (DNA base)": {
        "smiles": "[nH]1c(=O)[nH]c(=O)c(C)c1",
        "sequence": "T",
        "min_residue_count": 1,
        "biomolecule_class": "nucleotide",
        "min_peptide_bonds": 0,
        "notes": "DNA pyrimidine with a 5-methyl substituent.",
    },
    # ── Edge / negative cases ──
    "Water (not a residue)": {
        "smiles": "O",
        "sequence": "",
        "min_residue_count": 0,
        "biomolecule_class": "none",
        "notes": "Water has no backbone; not a recognised residue.",
    },
    "Ammonia (not a backbone amide)": {
        "smiles": "N",
        "sequence": "",
        "min_residue_count": 0,
        "biomolecule_class": "none",
        "notes": "Isolated N is not a backbone amide / residue.",
    },
    "Acetone (carbonyl, no backbone)": {
        "smiles": "CC(=O)C",
        "sequence": "",
        "min_residue_count": 0,
        "biomolecule_class": "none",
        "notes": "Ketone carbonyl lacks an attached amide N.",
    },
    "Acetamide (amide, no CA)": {
        "smiles": "CC(=O)N",
        "sequence": "",
        "min_residue_count": 0,
        "biomolecule_class": "none",
        "notes": "Amide carbonyl with no alpha carbon / backbone N pair.",
    },
    "Ethane (no heteroatoms)": {
        "smiles": "CC",
        "sequence": "",
        "min_residue_count": 0,
        "biomolecule_class": "none",
        "notes": "Alkane has no N/O; no residues recognised.",
    },
}
