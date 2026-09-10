"""InChI Round-Trip Tests — SMILES -> InChI -> graph -> InChI

Verifies that:
1. SMILES can be serialized to InChI
2. InChI can be parsed back to a graph
3. Re-serialization produces an identical (or chemically equivalent) InChI

Chemical correctness is verified by comparing atom counts, bond counts,
element composition, and molecular formula.
"""

from __future__ import annotations

from collections import Counter

from chemengine.parsing.inchi import parse_inchi
from chemengine.parsing.inchi_serializer import inchi_to_formula, serialize_inchi
from chemengine.parsing.smiles import parse_smiles

# ── Helper ──

def _assert_roundtrip(smiles: str, expected_inchi: str | None = None) -> None:
    """Verify SMILES -> InChI -> graph -> InChI round-trip.

    If expected_inchi is provided, also verify the first InChI matches.
    """
    g1 = parse_smiles(smiles)
    inchi1 = serialize_inchi(g1)

    if expected_inchi is not None:
        assert inchi1 == expected_inchi, f"Expected {expected_inchi}, got {inchi1}"

    g2 = parse_inchi(inchi1)
    inchi2 = serialize_inchi(g2)

    # Verify InChI strings match
    if inchi1 != inchi2:
        # If InChI strings differ, verify the graphs are chemically equivalent
        assert g1.num_atoms == g2.num_atoms, (
            f"Atom count mismatch: {g1.num_atoms} vs {g2.num_atoms}"
        )
        assert g1.num_bonds == g2.num_bonds, (
            f"Bond count mismatch: {g1.num_bonds} vs {g2.num_bonds}"
        )
        assert g1.molecular_formula == g2.molecular_formula, (
            f"Formula mismatch: {g1.molecular_formula} vs {g2.molecular_formula}"
        )
        c1 = Counter(a.atomic_number for a in g1.atoms)
        c2 = Counter(a.atomic_number for a in g2.atoms)
        assert c1 == c2, f"Element mismatch: {c1} vs {c2}"

    # Verify formula extraction
    extracted = inchi_to_formula(inchi1)
    assert extracted == g1.molecular_formula


# ── Simple Molecules (must be exact matches) ──

class TestSimpleMolecules:
    def test_water(self):
        _assert_roundtrip("O", "InChI=1S/H2O/c1/h1H2")

    def test_methane(self):
        _assert_roundtrip("C", "InChI=1S/CH4/c1/h1H4")

    def test_ammonia(self):
        _assert_roundtrip("N", "InChI=1S/H3N/c1/h1H3")

    def test_ethane(self):
        _assert_roundtrip("CC")

    def test_ethanol(self):
        _assert_roundtrip("CCO", "InChI=1S/C2H6O/c1-2-3/h1H3,2H2,3H")

    def test_ethylene(self):
        _assert_roundtrip("C=C", "InChI=1S/C2H4/c1-2/h1-2H2")

    def test_propane(self):
        _assert_roundtrip("CCC", "InChI=1S/C3H8/c1-2-3/h1H3,2H2,3H3")

    def test_acetic_acid(self):
        _assert_roundtrip("CC(=O)O", "InChI=1S/C2H4O2/c1-2(4)-3/h1H3,4H")

    def test_acetone(self):
        _assert_roundtrip("CC(=O)C", "InChI=1S/C3H6O/c1-2(4)-3/h1H3,4H3")


# ── Ring Systems ──

class TestRingSystems:
    def test_benzene(self):
        _assert_roundtrip("c1ccccc1", "InChI=1S/C6H6/c1:2:3:4:5:6:1/h1-6H")

    def test_cyclohexane(self):
        _assert_roundtrip("C1CCCCC1", "InChI=1S/C6H12/c1:2:3:4:5:6:1/h1-6H2")

    def test_toluene(self):
        _assert_roundtrip("Cc1ccccc1")

    def test_naphthalene(self):
        _assert_roundtrip("c1ccc2ccccc2c1")

    def test_phenol(self):
        _assert_roundtrip("Oc1ccccc1")

    def test_aniline(self):
        _assert_roundtrip("Nc1ccccc1")


# ── Branched Molecules ──

class TestBranchedMolecules:
    def test_isobutane(self):
        _assert_roundtrip("CC(C)C")

    def test_neopentane(self):
        _assert_roundtrip("CC(C)(C)C")

    def test_isopropanol(self):
        _assert_roundtrip("CC(C)O")

    def test_acetone(self):
        _assert_roundtrip("CC(=O)C")

    def test_aspirin(self):
        _assert_roundtrip("CC(=O)Oc1ccccc1C(=O)O")

    def test_caffeine(self):
        _assert_roundtrip("Cn1c(=O)c2c(ncn2C)n(C)c1=O")


# ── Functional Groups ──

class TestFunctionalGroups:
    def test_formaldehyde(self):
        _assert_roundtrip("C=O")

    def test_acetic_acid(self):
        _assert_roundtrip("CC(=O)O")

    def test_methylamine(self):
        _assert_roundtrip("CN")

    def test_dimethylamine(self):
        _assert_roundtrip("CNC")

    def test_diethyl_ether(self):
        _assert_roundtrip("CCOCC")

    def test_acetaldehyde(self):
        _assert_roundtrip("CC=O")

    def test_acetonitrile(self):
        _assert_roundtrip("CC#N")

    def test_nitromethane(self):
        _assert_roundtrip("C[N+](=O)[O-]")


# ── Charged Species ──

class TestChargedSpecies:
    def test_sodium_chloride_ion(self):
        _assert_roundtrip("[Na+].[Cl-]")

    def test_ammonium(self):
        _assert_roundtrip("[NH4+]")

    def test_hydroxide(self):
        _assert_roundtrip("[OH-]")


# ── Edge Cases ──

class TestEdgeCases:
    def test_single_carbon(self):
        _assert_roundtrip("C")

    def test_single_nitrogen(self):
        _assert_roundtrip("N")

    def test_single_oxygen(self):
        _assert_roundtrip("O")

    def test_bond_counts(self):
        """Verify atom and bond counts are preserved through round-trip."""
        for smiles in ["CCO", "c1ccccc1", "CC(=O)O", "CC(C)C"]:
            g1 = parse_smiles(smiles)
            g2 = parse_inchi(serialize_inchi(g1))
            assert g1.num_atoms == g2.num_atoms
            assert g1.num_bonds == g2.num_bonds

    def test_formula_preservation(self):
        """Verify molecular formula is preserved through round-trip."""
        for smiles in ["CCO", "c1ccccc1", "CC(=O)O", "C1CCCCC1"]:
            g1 = parse_smiles(smiles)
            g2 = parse_inchi(serialize_inchi(g1))
            assert g1.molecular_formula == g2.molecular_formula

    def test_element_composition(self):
        """Verify element composition is preserved through round-trip."""
        for smiles in ["CCO", "c1ccccc1", "CC(=O)O", "Nc1ccccc1"]:
            g1 = parse_smiles(smiles)
            g2 = parse_inchi(serialize_inchi(g1))
            c1 = Counter(a.atomic_number for a in g1.atoms)
            c2 = Counter(a.atomic_number for a in g2.atoms)
            assert c1 == c2

    def test_hydrogen_layer_grouping(self):
        """Verify hydrogen layer ranges are correctly serialized."""
        g = parse_smiles("c1ccccc1")  # benzene
        inchi = serialize_inchi(g)
        # All 6 carbons have 1 H each → range notation
        assert "h1-6H" in inchi

    def test_branch_notation(self):
        """Verify branch notation for acetic acid."""
        g = parse_smiles("CC(=O)O")
        inchi = serialize_inchi(g)
        # Should have branch notation
        assert "(" in inchi.split("/c")[1]

    def test_ring_notation(self):
        """Verify ring closure notation for benzene."""
        g = parse_smiles("c1ccccc1")
        inchi = serialize_inchi(g)
        conn = inchi.split("/c")[1].split("/h")[0]
        # Should have colon-separated ring bonds
        assert ":" in conn

    def test_inchi_to_formula(self):
        """Verify formula extraction from InChI strings."""
        assert inchi_to_formula("InChI=1S/C6H6/c1:2:3:4:5:6:1/h1-6H") == "C6H6"
        assert inchi_to_formula("InChI=1S/H2O/c1/h1H2") == "H2O"
        assert inchi_to_formula("InChI=1S/CH4/c1/h1H4") == "CH4"
        assert inchi_to_formula("InChI=1S/C2H6O/c1-2-3/h1H3,2H2,3H") == "C2H6O"
        assert inchi_to_formula("invalid") is None
        assert inchi_to_formula("InChI=1S/") is None
