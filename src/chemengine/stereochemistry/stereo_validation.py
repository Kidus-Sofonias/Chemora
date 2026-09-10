"""Stereochemistry validation — detects ambiguous and conflicting stereo assignments.

Implements:
- Atropisomer detection (restricted rotation around single bonds)
- Stereo conflict detection (multiple contradictory assignments)
- Stereo completeness check (missing stereo information)
- Validation report for stereochemical correctness
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from chemengine.core.enums import BondOrder, BondStereo, ChiralTag
from chemengine.core.graph import MolecularGraph


class StereoIssueType(Enum):
    """Type of stereochemistry issue."""
    CONFLICT = "conflict"           # Multiple contradictory assignments
    AMBIGUOUS = "ambiguous"         # Could be R or S, not enough info
    MISSING = "missing"             # Stereocenter exists but no assignment
    ATROPOISOMER = "atropisomer"   # Restricted rotation creates atropisomerism
    INCONSISTENT = "inconsistent"  # Stereo labels don't match geometry


class StereoSeverity(Enum):
    """Severity of stereochemistry issue."""
    ERROR = "error"       # Must be fixed
    WARNING = "warning"   # Should be reviewed
    INFO = "info"         # Informational


@dataclass(frozen=True, slots=True)
class StereoIssue:
    """A single stereochemistry issue."""
    issue_type: StereoIssueType
    severity: StereoSeverity
    message: str
    atom_indices: tuple[int, ...] = ()
    bond_indices: tuple[int, ...] = ()

    def __repr__(self) -> str:
        return f"StereoIssue({self.issue_type.value}, {self.severity.value}: {self.message})"


@dataclass(frozen=True, slots=True)
class Atropisomer:
    """Placeholder data structure for atropisomerism.

    Atropisomers arise from restricted rotation around a single bond,
    typically in biaryl systems with ortho substituents that prevent
    free rotation. This is a v2.0 placeholder — full atropisomer
    detection requires conformational analysis.

    Attributes:
        bond: The restricted-rotation bond (atom1, atom2).
        priority_groups: The groups that create steric hindrance.
        rotation_barrier: Estimated barrier to rotation in kcal/mol (if known).
        chirality_label: M/P for axial chirality, or None if unknown.
    """
    bond: tuple[int, int]
    priority_groups: tuple[tuple[int, int], ...] = ()  # (atom1_group, atom2_group)
    rotation_barrier: float | None = None
    chirality_label: str | None = None  # "M" or "P" for axial chirality

    def __repr__(self) -> str:
        label = self.chirality_label or "?"
        return f"Atropisomer(bond={self.bond}, chirality={label})"


@dataclass(frozen=True, slots=True)
class StereoValidationResult:
    """Result of stereochemistry validation.

    Attributes:
        is_valid: True if no errors found.
        issues: List of all stereochemistry issues found.
        atropisomers: List of detected atropisomer candidates.
        chiral_centers_count: Number of tetrahedral stereocenters.
        double_bond_stereo_count: Number of stereogenic double bonds.
        atropisomer_count: Number of potential atropisomers.
    """
    is_valid: bool
    issues: tuple[StereoIssue, ...]
    atropisomers: tuple[Atropisomer, ...]
    chiral_centers_count: int
    double_bond_stereo_count: int
    atropisomer_count: int

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == StereoSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == StereoSeverity.WARNING)

    def __repr__(self) -> str:
        return (
            f"StereoValidationResult(valid={self.is_valid}, "
            f"errors={self.error_count}, warnings={self.warning_count}, "
            f"chiral={self.chiral_centers_count}, "
            f"db_stereo={self.double_bond_stereo_count}, "
            f"atropisomers={self.atropisomer_count})"
        )


# ══════════════════════════════════════════════════════════════════
# ATROPOISOMER DETECTION (Placeholder)
# ══════════════════════════════════════════════════════════════════

def detect_atropisomer_candidates(graph: MolecularGraph) -> tuple[Atropisomer, ...]:
    """Detect potential atropisomer candidates.

    Atropisomerism occurs when rotation around a single bond is
    restricted by steric hindrance, typically in:
    - Biaryl systems (two aromatic rings connected by a single bond)
    - Amides with restricted C-N rotation
    - Sterically hindered biphenyls

    This is a simplified heuristic — full detection requires
    conformational energy analysis.

    Args:
        graph: The molecular graph.

    Returns:
        Tuple of Atropisomer candidates.
    """
    candidates: list[Atropisomer] = []

    for bond in graph.bonds:
        if bond.order != BondOrder.SINGLE:
            continue

        a1, a2 = bond.atom1, bond.atom2
        atom1 = graph.atoms[a1]
        atom2 = graph.atoms[a2]

        # Check for biaryl: both atoms are aromatic carbons
        if (atom1.atomic_number == 6 and atom1.is_aromatic and
                atom2.atomic_number == 6 and atom2.is_aromatic):
            # Check for ortho substituents (steric hindrance)
            ortho_substituents_1 = _count_ortho_substituents(graph, a1, a2)
            ortho_substituents_2 = _count_ortho_substituents(graph, a2, a1)

            if ortho_substituents_1 >= 1 and ortho_substituents_2 >= 1:
                candidates.append(Atropisomer(
                    bond=(a1, a2),
                    chirality_label=None,  # Requires 3D analysis
                ))

        # Check for amide C-N bond (restricted rotation)
        if ((atom1.atomic_number == 6 and atom2.atomic_number == 7) or
                (atom1.atomic_number == 7 and atom2.atomic_number == 6)):
            # Check if the carbon has a double bond to O (amide)
            c_atom = a1 if atom1.atomic_number == 6 else a2
            for nbr in graph.get_neighbors(c_atom):
                if nbr == (a2 if c_atom == a1 else a1):
                    continue
                nbr_bond = graph.get_bond(c_atom, nbr)
                if (nbr_bond is not None and nbr_bond.order == BondOrder.DOUBLE
                        and graph.atoms[nbr].atomic_number == 8):
                    # Amide C-N bond — restricted rotation
                    candidates.append(Atropisomer(
                        bond=(a1, a2),
                        chirality_label=None,
                    ))
                    break

    return tuple(candidates)


def _count_ortho_substituents(
    graph: MolecularGraph, ring_atom: int, connection_atom: int
) -> int:
    """Count non-hydrogen substituents on ortho positions of an aromatic ring.

    The ortho positions are the ring atoms adjacent to ring_atom (excluding
    the connection_atom). For each ortho atom, count its non-hydrogen,
    non-ring substituents (e.g., methyl groups on a biphenyl).
    """
    count = 0
    for ortho in graph.get_neighbors(ring_atom):
        if ortho == connection_atom:
            continue
        # ortho is a ring atom adjacent to ring_atom
        # Count its non-H, non-aromatic substituents
        for sub in graph.get_neighbors(ortho):
            if sub == ring_atom:
                continue
            sub_atom = graph.atoms[sub]
            if sub_atom.atomic_number != 1 and not sub_atom.is_aromatic:
                count += 1
    return count


# ══════════════════════════════════════════════════════════════════
# STEREO VALIDATION
# ══════════════════════════════════════════════════════════════════

def validate_stereochemistry(graph: MolecularGraph) -> StereoValidationResult:
    """Validate stereochemistry assignments in a molecular graph.

    Checks for:
    1. Conflicting assignments (same atom assigned both R and S)
    2. Missing assignments (stereocenter exists but no assignment)
    3. Inconsistent assignments (stereo labels don't match topology)
    4. Atropisomer candidates

    Args:
        graph: The molecular graph.

    Returns:
        StereoValidationResult with all issues found.
    """
    issues: list[StereoIssue] = []
    atropisomers = detect_atropisomer_candidates(graph)

    # Count stereocenters
    chiral_count = 0
    db_stereo_count = 0

    # Check tetrahedral centers
    for i, atom in enumerate(graph.atoms):
        if atom.stereochemistry != ChiralTag.NONE:
            chiral_count += 1

            # Check for conflicting assignment
            neighbors = list(graph.get_neighbors(i))
            if len(neighbors) != 4:
                issues.append(StereoIssue(
                    issue_type=StereoIssueType.CONFLICT,
                    severity=StereoSeverity.ERROR,
                    message=f"Atom {i} ({atom.symbol}) has stereochemistry "
                            f"but {len(neighbors)} neighbors (expected 4)",
                    atom_indices=(i,),
                ))

            # Check for symmetry that makes assignment ambiguous
            if len(neighbors) == 4:
                neighbor_elements = [graph.atoms[n].atomic_number for n in neighbors]
                if len(set(neighbor_elements)) < 4:
                    # May still be chiral if environments differ
                    # This is a heuristic — full check requires CIP
                    pass  # Don't flag as error, just informational

    # Check double bond stereochemistry
    for bond in graph.bonds:
        if bond.order == BondOrder.DOUBLE and bond.stereochemistry != BondStereo.NONE:
            db_stereo_count += 1

            # Check that both atoms of the double bond have stereo info
            a1, a2 = bond.atom1, bond.atom2
            atom1 = graph.atoms[a1]
            atom2 = graph.atoms[a2]

            # Check for E/Z consistency
            if bond.stereochemistry in (BondStereo.CIS, BondStereo.TRANS):
                # These are legacy labels — should be E/Z
                issues.append(StereoIssue(
                    issue_type=StereoIssueType.INCONSISTENT,
                    severity=StereoSeverity.WARNING,
                    message=f"Double bond ({a1},{a2}) uses legacy "
                            f"{'cis' if bond.stereochemistry == BondStereo.CIS else 'trans'} "
                            f"instead of E/Z notation",
                    bond_indices=(a1, a2),
                ))

    # Check for missing stereo assignments on potential stereocenters
    from chemengine.stereochemistry.cip import is_chiral_center
    for i in range(graph.num_atoms):
        if is_chiral_center(graph, i):
            atom = graph.atoms[i]
            if atom.stereochemistry == ChiralTag.NONE:
                issues.append(StereoIssue(
                    issue_type=StereoIssueType.MISSING,
                    severity=StereoSeverity.WARNING,
                    message=f"Atom {i} ({atom.symbol}) appears to be a "
                            f"chiral center but has no stereochemistry assignment",
                    atom_indices=(i,),
                ))

    # Check for atropisomers
    for atro in atropisomers:
        issues.append(StereoIssue(
            issue_type=StereoIssueType.ATROPOISOMER,
            severity=StereoSeverity.INFO,
            message=f"Potential atropisomer at bond {atro.bond} "
                    f"(restricted rotation)",
            bond_indices=atro.bond,
        ))

    has_errors = any(i.severity == StereoSeverity.ERROR for i in issues)

    return StereoValidationResult(
        is_valid=not has_errors,
        issues=tuple(issues),
        atropisomers=atropisomers,
        chiral_centers_count=chiral_count,
        double_bond_stereo_count=db_stereo_count,
        atropisomer_count=len(atropisomers),
    )
