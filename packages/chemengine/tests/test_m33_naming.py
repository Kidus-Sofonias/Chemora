"""M33 naming-layer tests: round-trips, negative cases, tautomers, names.

Covers the M33 nomenclature acceptance surface:
- generator/parser round-trip via InChIKey (canonical, order-independent)
- explicit unsupported handling (no silent misinterpretation)
- SMILES ring-closure and formula-detection regressions
- canonical (order-independent) InChI/InChIKey
- bounded tautomer detection / enumeration / canonicalization
- common-name dictionary integrity
"""

from __future__ import annotations

import pytest

from chemengine import ChemEngineAPI
from chemengine.nomenclature.common_names import (
    COMMON_NAMES_COUNT,
    common_names,
    validate_common_names,
)
from chemengine.nomenclature.iupac import (
    UnsupportedNamingError,
    generate_iupac_name,
)
from chemengine.nomenclature.tautomers import (
    MAX_TAUTOMER_FORMS,
    canonical_tautomer,
    detect_tautomers,
    enumerate_tautomers,
)
from chemengine.parsing.iupac import NameParseError, parse_iupac_name
from chemengine.parsing.protocol import auto_detect_format


@pytest.fixture(scope="module")
def chem() -> ChemEngineAPI:
    return ChemEngineAPI()


def _key(chem: ChemEngineAPI, graph) -> str:
    return chem.convert(graph, "inchikey")


# ── Generator: correct names / explicit unsupported ──


class TestGenerator:
    @pytest.mark.parametrize(
        ("smiles", "expected"),
        [
            ("CCO", "ethan-1-ol"),
            ("CC(=O)O", "ethanoic acid"),
            ("CCC(C)=O", "butan-2-one"),
            ("CC(C)CCO", "3-methylbutan-1-ol"),
            ("CCC(C)C(C)C", "2,3-dimethylpentane"),  # minimized locants
            ("c1ccccc1", "benzene"),
            ("c1ccccc1O", "phenol"),
            ("Cc1ccccc1", "methylbenzene"),
            ("c1ccc(Cl)cc1Cl", "1,3-dichlorobenzene"),
            ("O=[N+]([O-])c1ccccc1", "nitrobenzene"),  # never 'aminobenzene'
            ("C1CCCCC1", "cyclohexane"),
            ("C1CCCCC1O", "cyclohexanol"),
            ("C1CCCCC1N", "cyclohexanamine"),
        ],
    )
    def test_names(self, chem, smiles, expected):
        assert generate_iupac_name(chem.parse(smiles)) == expected

    def test_aromatic_ether_unsupported(self, chem):
        with pytest.raises(UnsupportedNamingError):
            generate_iupac_name(chem.parse("COc1ccccc1"))

    def test_tertiary_amine_unsupported(self, chem):
        with pytest.raises(UnsupportedNamingError):
            generate_iupac_name(chem.parse("CCN(CC)CC"))


# ── Parser: round-trip + position-aware errors ──


class TestRoundTrip:
    @pytest.mark.parametrize(
        "smiles",
        [
            "CCO", "CCCO", "CCCCCO", "CCCCCCO",
            "CC(=O)O", "CCCC(=O)O", "CCCCCC(=O)O",
            "CC(C)O", "CCC(C)C", "CC(C)CCO", "CCC(C)CC(=O)O",
            "CC(=O)NCC", "CCCC(=O)NC", "CCC(C)=O",
            "CC(=O)OC", "CCC(=O)OCC",
            "Cc1ccccc1", "c1ccccc1O", "c1ccccc1Cl", "c1ccccc1N",
            "c1ccc(O)cc1Cl", "c1ccc(Cl)cc1Cl",
            "CCN", "CCCN", "CC(C)N", "CCNCC",
            "O=[N+]([O-])c1ccccc1", "[O-][N+](=O)c1ccc(C)cc1",
            "c1ccccc1", "C1CCCCC1", "CCCCCC", "CCCCC(C)C", "CCC(C)C(C)C",
        ],
    )
    def test_round_trip(self, chem, smiles):
        name = generate_iupac_name(chem.parse(smiles))
        g2 = parse_iupac_name(name)
        assert _key(chem, g2) == _key(chem, chem.parse(smiles))

    def test_parse_error_has_position(self):
        with pytest.raises(NameParseError) as exc:
            parse_iupac_name("2-methylbutanoic")  # missing 'acid'
        assert exc.value.position is not None

    def test_unknown_name_rejected(self):
        with pytest.raises(NameParseError):
            parse_iupac_name("definitelynotachemical")


# ── SMILES / detection regressions fixed under M33 ──


class TestParsingRegressions:
    def test_saturated_ring_closure(self, chem):
        """'C1CCCCC1' was previously misrouted to the formula parser (C6)."""
        g = chem.parse("C1CCCCC1")
        assert g.molecular_formula == "C6H12"

    def test_bare_h_not_smiles(self, chem):
        """Structural formulas parse through the formula parser, not SMILES."""
        assert chem.parse("CH3CH3").molecular_formula == "C2H6"
        assert chem.parse("C2H5OH").molecular_formula == "C2H6O"

    def test_detect(self):
        assert auto_detect_format("C1CCCCC1") == "smiles"
        assert auto_detect_format("C6H6") == "formula"
        assert auto_detect_format("C2H5OH") == "formula"
        assert auto_detect_format("H2O") == "formula"

    def test_formula_parser_still_works(self, chem):
        assert chem.parse("C6H6").molecular_formula == "C6H6"
        assert chem.parse("H2O").molecular_formula == "H2O"


# ── Canonical (order-independent) InChI/InChIKey ──


class TestCanonicalInChI:
    @pytest.mark.parametrize(
        "smiles_set",
        [
            {"CCO", "OCC", "C(O)C"},
            {"CCC(C)C", "CC(C)CC"},
            {"C1CCCCC1", "C1CCCCC1"},
        ],
    )
    def test_key_order_independent(self, chem, smiles_set):
        keys = {_key(chem, chem.parse(s)) for s in smiles_set}
        assert len(keys) == 1

    def test_inchi_smiles_roundtrip_stable(self, chem):
        """SMILES round-trip preserves the InChI (the canonical-order
        guarantee; InChI-text re-parsing is covered by its own suite)."""
        g = chem.parse("CC(=O)Oc1ccccc1C(=O)O")
        i1 = chem.convert(g, "inchi")
        g2 = chem.parse(chem.convert(g, "smiles"))
        assert chem.convert(g2, "inchi") == i1


# ── Tautomers ──


class TestTautomers:
    def test_keto_enol_detected(self, chem):
        sites = detect_tautomers(chem.parse("CC(=O)C"))
        assert len(sites) == 1
        assert sites[0].tautomer_type == "keto-enol"

    def test_amide_imidic_detected(self, chem):
        sites = detect_tautomers(chem.parse("CC(=O)NC"))
        assert sites[0].tautomer_type == "amide-imidic"

    def test_unrelated_untouched(self, chem):
        for smi in ("CCO", "c1ccccc1", "CCCC"):
            assert detect_tautomers(chem.parse(smi)) == []
            assert enumerate_tautomers(chem.parse(smi)) == []

    def test_partner_is_valid_chemistry(self, chem):
        form = enumerate_tautomers(chem.parse("CC(=O)C"))[0]
        # Enol of acetone: same formula, C=C(O) pattern.
        assert chem.convert(form.graph, "formula") == "C3H6O"

    def test_bounded_enumeration(self, chem):
        forms = enumerate_tautomers(chem.parse("CC(=O)C"), max_forms=1)
        assert len(forms) <= 1
        assert MAX_TAUTOMER_FORMS == 8

    def test_canonical_deterministic(self, chem):
        g = chem.parse("CC(=O)C")
        c1 = canonical_tautomer(g)
        c2 = canonical_tautomer(canonical_tautomer(g))
        assert chem.convert(c1, "inchikey") == chem.convert(c2, "inchikey")

    def test_canonical_passthrough(self, chem):
        g = chem.parse("CCO")
        assert chem.convert(canonical_tautomer(g), "inchikey") == _key(
            chem, g
        )

    def test_input_not_mutated(self, chem):
        g = chem.parse("CC(=O)C")
        before = chem.convert(g, "smiles")
        enumerate_tautomers(g)
        canonical_tautomer(g)
        assert chem.convert(g, "smiles") == before


# ── Common names ──


class TestCommonNames:
    def test_count_is_honest_and_nonzero(self):
        assert COMMON_NAMES_COUNT == len(common_names()) > 0

    def test_all_entries_parse(self):
        assert validate_common_names() == []

    def test_known_entries_resolve(self, chem):
        assert chem.parse("aspirin").molecular_formula == "C9H8O4"
        assert chem.parse("toluene").molecular_formula == "C7H8"
