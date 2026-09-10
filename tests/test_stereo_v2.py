"""Tests for Phase 6 v2.0: Atropisomer detection and stereo validation.
"""

from chemengine.core.enums import BondOrder, BondStereo
from chemengine.core.graph import MolecularGraphBuilder
from chemengine.parsing.smiles import parse_smiles
from chemengine.stereochemistry.stereo_validation import (
    StereoIssueType,
    StereoSeverity,
    StereoValidationResult,
    detect_atropisomer_candidates,
    validate_stereochemistry,
)

# ══════════════════════════════════════════════════════════════════
# ATROPOISOMER DETECTION TESTS
# ══════════════════════════════════════════════════════════════════


class TestAtropisomerDetection:
    """Tests for atropisomer candidate detection."""

    def test_biphenyl_atropisomer_candidate(self):
        """Biphenyl with ortho substituents should be detected as atropisomer."""
        # 2,2'-dimethylbiphenyl: ortho substituents restrict rotation
        builder = MolecularGraphBuilder()
        # Ring 1: 6 aromatic carbons
        ring1 = [builder.add_atom(6, is_aromatic=True) for _ in range(6)]
        for i in range(6):
            builder.add_bond(ring1[i], ring1[(i + 1) % 6], BondOrder.AROMATIC)
        # Ring 2: 6 aromatic carbons
        ring2 = [builder.add_atom(6, is_aromatic=True) for _ in range(6)]
        for i in range(6):
            builder.add_bond(ring2[i], ring2[(i + 1) % 6], BondOrder.AROMATIC)
        # Connect rings
        builder.add_bond(ring1[0], ring2[0], BondOrder.SINGLE)
        # Ortho substituents (methyl groups)
        builder.add_bond(ring1[1], builder.add_atom(6), BondOrder.SINGLE)
        builder.add_bond(ring2[1], builder.add_atom(6), BondOrder.SINGLE)
        graph = builder.build()

        atropisomers = detect_atropisomer_candidates(graph)
        assert len(atropisomers) >= 1
        assert atropisomers[0].chirality_label is None  # Not yet assigned

    def test_biphenyl_no_substituents_no_atropisomer(self):
        """Biphenyl without ortho substituents is NOT an atropisomer."""
        builder = MolecularGraphBuilder()
        ring1 = [builder.add_atom(6, is_aromatic=True) for _ in range(6)]
        for i in range(6):
            builder.add_bond(ring1[i], ring1[(i + 1) % 6], BondOrder.AROMATIC)
        ring2 = [builder.add_atom(6, is_aromatic=True) for _ in range(6)]
        for i in range(6):
            builder.add_bond(ring2[i], ring2[(i + 1) % 6], BondOrder.AROMATIC)
        builder.add_bond(ring1[0], ring2[0], BondOrder.SINGLE)
        graph = builder.build()

        atropisomers = detect_atropisomer_candidates(graph)
        assert len(atropisomers) == 0

    def test_amide_bond_atropisomer(self):
        """Amide C-N bond should be detected as restricted rotation."""
        # Simple amide: CH3-C(=O)-NH2
        builder = MolecularGraphBuilder()
        c_methyl = builder.add_atom(6)
        c_carbonyl = builder.add_atom(6)
        o = builder.add_atom(8)
        n = builder.add_atom(7)
        builder.add_bond(c_methyl, c_carbonyl, BondOrder.SINGLE)
        builder.add_bond(c_carbonyl, o, BondOrder.DOUBLE)
        builder.add_bond(c_carbonyl, n, BondOrder.SINGLE)
        # Add H atoms
        for _ in range(3):
            h = builder.add_atom(1)
            builder.add_bond(c_methyl, h, BondOrder.SINGLE)
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(n, h, BondOrder.SINGLE)
        graph = builder.build()

        atropisomers = detect_atropisomer_candidates(graph)
        assert len(atropisomers) >= 1

    def test_single_bond_no_atropisomer(self):
        """Simple C-C single bond is NOT an atropisomer."""
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.SINGLE)
        for _ in range(4):
            h = builder.add_atom(1)
            builder.add_bond(c1, h, BondOrder.SINGLE)
        for _ in range(4):
            h = builder.add_atom(1)
            builder.add_bond(c2, h, BondOrder.SINGLE)
        graph = builder.build()

        atropisomers = detect_atropisomer_candidates(graph)
        assert len(atropisomers) == 0


# ══════════════════════════════════════════════════════════════════
# STEREO VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestStereoValidation:
    """Tests for stereochemistry validation."""

    def test_valid_stereochemistry(self):
        """Molecule with correct stereo assignments passes validation."""
        # Use [C@H] to explicitly set tetrahedral stereochemistry
        graph = parse_smiles("[C@@H](F)(Cl)Br")
        result = validate_stereochemistry(graph)
        assert isinstance(result, StereoValidationResult)
        assert result.chiral_centers_count >= 1

    def test_missing_stereo_warning(self):
        """Molecule with potential stereocenter but no assignment gets warning."""
        # Build a chiral center without stereo tag
        builder = MolecularGraphBuilder()
        c = builder.add_atom(6)  # No stereochemistry
        f = builder.add_atom(9)
        cl = builder.add_atom(17)
        br = builder.add_atom(35)
        i_atom = builder.add_atom(53)
        builder.add_bond(c, f, BondOrder.SINGLE)
        builder.add_bond(c, cl, BondOrder.SINGLE)
        builder.add_bond(c, br, BondOrder.SINGLE)
        builder.add_bond(c, i_atom, BondOrder.SINGLE)
        graph = builder.build()

        result = validate_stereochemistry(graph)
        # Should have a missing stereo warning
        missing_issues = [i for i in result.issues
                          if i.issue_type == StereoIssueType.MISSING]
        assert len(missing_issues) >= 1
        assert any(i.severity == StereoSeverity.WARNING for i in missing_issues)

    def test_no_issues_for_simple_molecule(self):
        """Simple molecule without stereocenters has no issues."""
        graph = parse_smiles("CCO")
        result = validate_stereochemistry(graph)
        assert result.is_valid
        assert result.chiral_centers_count == 0
        assert result.double_bond_stereo_count == 0

    def test_validation_result_properties(self):
        """StereoValidationResult properties work correctly."""
        graph = parse_smiles("[C@@H](F)(Cl)Br")
        result = validate_stereochemistry(graph)
        assert result.error_count >= 0
        assert result.warning_count >= 0
        assert isinstance(result.issues, tuple)
        assert isinstance(result.atropisomers, tuple)

    def test_legacy_cis_trans_warning(self):
        """Legacy cis/trans notation triggers a warning."""
        builder = MolecularGraphBuilder()
        c1 = builder.add_atom(6)
        c2 = builder.add_atom(6)
        builder.add_bond(c1, c2, BondOrder.DOUBLE,
                         stereochemistry=BondStereo.CIS)
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(c1, h, BondOrder.SINGLE)
        for _ in range(2):
            h = builder.add_atom(1)
            builder.add_bond(c2, h, BondOrder.SINGLE)
        graph = builder.build()

        result = validate_stereochemistry(graph)
        inconsistent = [i for i in result.issues
                        if i.issue_type == StereoIssueType.INCONSISTENT]
        assert len(inconsistent) >= 1
