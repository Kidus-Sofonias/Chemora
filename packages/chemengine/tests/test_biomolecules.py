"""Tests for the M40 biomolecular-analysis module.

Covers the reference oracle (20 proteinogenic amino acids + 4 nucleic-acid
bases + negatives), residue disambiguation (Pro vs Val), peptide-bond counting,
serialization round-trips and registry registration.
"""

from __future__ import annotations

import pytest

from chemengine.biomolecules import (
    RECOGNITION_CATALOGUE_VERSION,
    REFERENCE_BIOORACLE,
    SCHEMA_VERSION,
    BiomoleculeAnalysis,
    BiomoleculeError,
    ChainTooLongError,
    ResidueType,
    analyze_biomolecule,
    biomolecule_analysis_to_dict,
    detect_peptide_bonds,
    dict_to_biomolecule_analysis,
    extract_sequence,
    list_biomolecule_reference,
    recognize_residues,
    register_biomolecule_algorithms,
)
from chemengine.core.graph import MolecularGraph
from chemengine.core.registry import AlgorithmRegistry
from chemengine.parsing.smiles import parse_smiles


@pytest.mark.parametrize("name", list(REFERENCE_BIOORACLE))
class TestReferenceOracle:
    """Every curated reference biomolecule must analyze to its expected values."""

    def test_residue_count(self, name: str) -> None:
        """Recognised residue count meets the oracle minimum."""
        expected = REFERENCE_BIOORACLE[name]["min_residue_count"]
        analysis = analyze_biomolecule(parse_smiles(REFERENCE_BIOORACLE[name]["smiles"]))
        assert analysis.residue_count >= expected

    def test_sequence(self, name: str) -> None:
        """One-letter sequence matches the oracle exactly."""
        expected = REFERENCE_BIOORACLE[name]["sequence"]
        analysis = analyze_biomolecule(parse_smiles(REFERENCE_BIOORACLE[name]["smiles"]))
        assert analysis.sequence == expected

    def test_biomolecule_class(self, name: str) -> None:
        """Classified biomolecule class matches the oracle."""
        expected = REFERENCE_BIOORACLE[name]["biomolecule_class"]
        analysis = analyze_biomolecule(parse_smiles(REFERENCE_BIOORACLE[name]["smiles"]))
        assert analysis.biomolecule_class == expected

    def test_peptide_bonds(self, name: str) -> None:
        """Detected peptide-bond count meets the oracle minimum."""
        expected = REFERENCE_BIOORACLE[name].get("min_peptide_bonds", 0)
        analysis = analyze_biomolecule(parse_smiles(REFERENCE_BIOORACLE[name]["smiles"]))
        assert len(analysis.peptide_bonds) >= expected


class TestReferenceOracleConsistency:
    """The oracle helper exposes the curated reference verbatim."""

    def test_list_reference_matches_oracle(self) -> None:
        """``list_biomolecule_reference`` returns the canonical oracle."""
        assert list_biomolecule_reference() is REFERENCE_BIOORACLE

    def test_oracle_covers_all_twenty_amino_acids(self) -> None:
        """The oracle recognises at least the 20 proteinogenic AAs."""
        seen: set[str] = set()
        for entry in REFERENCE_BIOORACLE.values():
            seen.update(entry["sequence"])
        aa_codes = {rt.one_letter_code for rt in ResidueType if rt.is_amino_acid}
        assert aa_codes.issubset(seen)


class TestDisambiguation:
    """Isomer-sensitive cases the old SMARTS engine could not separate."""

    def test_proline_vs_valine(self) -> None:
        """Proline secondary-amine ring classifies as P, not V."""
        pro = analyze_biomolecule(parse_smiles("N1C(C(=O)O)CCC1"))
        val = analyze_biomolecule(parse_smiles("NC(C(C)B)C(=O)O".replace("B", "C")))
        assert pro.sequence == "P"
        assert val.sequence == "V"

    def test_leucine_vs_valine(self) -> None:
        """Leucine branched side chain classifies as L, distinct from V."""
        leu = analyze_biomolecule(parse_smiles("NC(CC(C)B)C(=O)O".replace("B", "C")))
        val = analyze_biomolecule(parse_smiles("NC(C(C)B)C(=O)O".replace("B", "C")))
        assert leu.sequence == "L"
        assert val.sequence == "V"


class TestPeptideBonds:
    """Backbone-anchored peptide-bond counting across oligomers."""

    def _bonds(self, smiles: str) -> int:
        """Count peptide bonds for ``smiles``."""
        return len(detect_peptide_bonds(parse_smiles(smiles)))

    def test_single_residue_has_no_peptide_bond(self) -> None:
        """A single amino acid exposes zero peptide bonds."""
        assert self._bonds("NC(C)C(=O)O") == 0  # Ala

    def test_dipeptide_has_one_peptide_bond(self) -> None:
        """A dipeptide exposes exactly one peptide bond."""
        assert self._bonds("NC(C)C(=O)NC(C(C)B)C(=O)O".replace("B", "C")) == 1  # Ala-Val

    def test_tripeptide_has_two_peptide_bonds(self) -> None:
        """A tripeptide exposes exactly two peptide bonds."""
        assert self._bonds("NC(C)C(=O)NC(C)C(=O)NC(C)C(=O)O") == 2  # AAA

    def test_tetrapeptide_has_three_peptide_bonds(self) -> None:
        """A tetrapeptide exposes exactly three peptide bonds."""
        seq = "NC(C)C(=O)NC(Cc1ccccc1)C(=O)NC(Cc1c2ccccc2[nH]c1)C(=O)NCC(=O)O"
        assert self._bonds(seq) == 3  # AFG

    def test_base_exocyclic_carbonyl_is_not_a_peptide_bond(self) -> None:
        """Cytosine exocyclic C=O is not mistaken for a peptide bond."""
        assert self._bonds("NC1=NC=CC(=O)N1") == 0  # cytosine base


class TestResidueOrdering:
    """``_order_by_chain`` assigns 1-based, contiguous positions."""

    def test_positions_are_one_based_and_contiguous(self) -> None:
        """Residue positions run 1..n and read in chain order."""
        residues = recognize_residues(parse_smiles("NC(C)C(=O)NCC(=O)O"))  # Ala-Gly
        positions = [r.position for r in residues]
        assert positions == list(range(1, len(residues) + 1))
        assert "".join(r.one_letter_code for r in residues) == "AG"


class TestErrors:
    """Public entry points enforce bounded computation deterministically."""

    def test_chain_too_long_raises(self) -> None:
        """Graphs exceeding the cap raise ChainTooLongError."""
        poly_cgc = "C" * 5001  # 5001 atoms, exceeds MAX_CHAIN_LENGTH (5000)
        with pytest.raises(ChainTooLongError):
            analyze_biomolecule(parse_smiles(poly_cgc))

    def test_errors_are_biomolecule_errors(self) -> None:
        """Structured errors derive from the BiomoleculeError base class."""
        assert issubclass(ChainTooLongError, BiomoleculeError)


class TestSerialization:
    """``BiomoleculeAnalysis`` round-trips losslessly through dict form."""

    def test_round_trip_to_dict(self) -> None:
        """to_dict/dict round-trips losslessly for an Ala-Val dipeptide."""
        analysis = analyze_biomolecule(parse_smiles("NC(C)C(=O)NC(C(C)B)C(=O)O".replace("B", "C")))
        original_dict = biomolecule_analysis_to_dict(analysis)
        reconstructed = dict_to_biomolecule_analysis(original_dict)
        assert biomolecule_analysis_to_dict(reconstructed) == original_dict


class TestRegistry:
    """Biomolecule algorithms register idempotently (M37/M39 pattern)."""

    def test_register_on_fresh_registry(self) -> None:
        """All four biomolecule algorithms register on a fresh registry."""
        registry = AlgorithmRegistry()
        register_biomolecule_algorithms(registry)
        assert ("biomolecules", "analyze_biomolecule") in registry
        assert ("biomolecules", "recognize_residues") in registry
        assert ("biomolecules", "detect_peptide_bonds") in registry
        assert ("biomolecules", "extract_sequence") in registry
        assert registry.count == 4

    def test_registration_is_idempotent(self) -> None:
        """Registering twice registers four entries, not eight."""
        registry = AlgorithmRegistry()
        register_biomolecule_algorithms(registry)
        register_biomolecule_algorithms(registry)
        assert registry.count == 4

    def test_register_replace(self) -> None:
        """Re-registering with replace=True still yields four entries."""
        registry = AlgorithmRegistry()
        register_biomolecule_algorithms(registry)
        register_biomolecule_algorithms(registry, replace=True)
        assert registry.count == 4

    def test_entry_types(self) -> None:
        """analyze_biomolecule entry is typed MolecularGraph->BiomoleculeAnalysis."""
        registry = AlgorithmRegistry()
        register_biomolecule_algorithms(registry)
        entry = registry.get("biomolecules", "analyze_biomolecule")
        assert entry.algorithm is analyze_biomolecule
        assert entry.input_type is MolecularGraph
        assert entry.output_type is BiomoleculeAnalysis
        assert entry.version == RECOGNITION_CATALOGUE_VERSION


class TestCatalogueMetadata:
    """Module-level catalogue metadata constants."""

    def test_schema_version(self) -> None:
        """The serialization schema tag is version v1."""
        assert SCHEMA_VERSION == "chemengine-biomolecule-analysis/v1"

    def test_catalogue_version(self) -> None:
        """The recognition catalogue version is 1.0.0."""
        assert RECOGNITION_CATALOGUE_VERSION == "1.0.0"

    def test_reference_keys(self) -> None:
        """The reference accessor returns the oracle object by identity."""
        assert list_biomolecule_reference() is REFERENCE_BIOORACLE


class TestPublicEntryPoints:
    """Smoke tests for the public analysis entry points."""

    def test_extract_sequence_single(self) -> None:
        """A single alanine yields the sequence A."""
        assert extract_sequence(parse_smiles("NC(C)C(=O)O")) == "A"

    def test_extract_sequence_empty(self) -> None:
        """An empty/organic graph yields an empty sequence."""
        assert extract_sequence(parse_smiles("CC")) == ""

    def test_recognize_residues_count(self) -> None:
        """Glycine is recognised as exactly one residue."""
        residues = recognize_residues(parse_smiles("NCC(=O)O"))  # Gly
        assert len(residues) == 1
        assert residues[0].one_letter_code == "G"
