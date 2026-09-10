"""Independent chemical validation (correctness gate, Phase H).

Uses well-known molecules with INDEPENDENTLY known expected values
(literature/reference values, NOT values computed by this engine).

Average molar masses from IUPAC 2021 standard atomic weights:
    H 1.008, C 12.011, N 14.007, O 15.999, Na 22.990, S 32.06,
    Cl 35.45, Ca 40.078, Fe 55.845
"""

import pytest

from chemengine.core.tool_interface import ChemEngineAPI


@pytest.fixture(scope="module")
def api() -> ChemEngineAPI:
    return ChemEngineAPI()


def avg_mass(composition: dict[str, int]) -> float:
    """Reference average molar mass from a {element: count} dict."""
    weights = {
        "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999,
        "Na": 22.990, "S": 32.06, "Cl": 35.45, "Ca": 40.078, "Fe": 55.845,
    }
    return sum(weights[e] * n for e, n in composition.items())


class TestKnownMolecules:
    """Each molecule: formula, mass, atom counts, connectivity, valence."""

    def test_water(self, api):
        g = api.parse("O", fmt="smiles")
        assert g.molecular_formula == "H2O"
        assert g.molecular_weight == pytest.approx(avg_mass({"H": 2, "O": 1}), rel=1e-3)
        assert g.num_atoms == 3
        assert g.num_bonds == 2
        result = api.validate(g)
        assert result.passed

    def test_carbon_dioxide(self, api):
        g = api.parse("O=C=O", fmt="smiles")
        assert g.molecular_formula == "CO2"
        assert g.molecular_weight == pytest.approx(avg_mass({"C": 1, "O": 2}), rel=1e-3)
        assert g.num_bonds == 2
        assert api.validate(g).passed

    def test_methane(self, api):
        g = api.parse("C", fmt="smiles")
        assert g.molecular_formula == "CH4"
        assert g.molecular_weight == pytest.approx(avg_mass({"C": 1, "H": 4}), rel=1e-3)
        assert g.num_bonds == 4
        assert api.validate(g).passed

    def test_ammonia(self, api):
        g = api.parse("N", fmt="smiles")
        assert g.molecular_formula == "H3N"
        assert g.molecular_weight == pytest.approx(avg_mass({"N": 1, "H": 3}), rel=1e-3)
        assert g.num_bonds == 3
        assert api.validate(g).passed

    def test_sodium_chloride(self, api):
        g = api.parse("[Na+].[Cl-]", fmt="smiles")
        assert g.molecular_formula == "ClNa"
        assert g.molecular_weight == pytest.approx(avg_mass({"Na": 1, "Cl": 1}), rel=1e-3)
        assert g.num_atoms == 2
        assert api.validate(g).passed

    def test_sulfuric_acid(self, api):
        g = api.parse("OS(=O)(=O)O", fmt="smiles")
        assert g.molecular_formula == "H2O4S"
        assert g.molecular_weight == pytest.approx(avg_mass({"H": 2, "S": 1, "O": 4}), rel=1e-3)
        assert g.num_atoms == 7
        assert api.validate(g).passed

    def test_calcium_hydroxide_formula(self, api):
        g = api.parse("Ca(OH)2", fmt="formula")
        assert g.molecular_formula == "H2CaO2"
        assert g.molecular_weight == pytest.approx(avg_mass({"Ca": 1, "O": 2, "H": 2}), rel=1e-3)
        assert g.num_atoms == 5

    def test_ferric_sulfate_formula(self, api):
        g = api.parse("Fe2(SO4)3", fmt="formula")
        assert g.molecular_formula == "Fe2O12S3"
        expected = avg_mass({"Fe": 2, "S": 3, "O": 12})
        assert g.molecular_weight == pytest.approx(expected, rel=1e-3)
        assert g.num_atoms == 17

    def test_benzene(self, api):
        g = api.parse("c1ccccc1", fmt="smiles")
        assert g.molecular_formula == "C6H6"
        assert g.molecular_weight == pytest.approx(avg_mass({"C": 6, "H": 6}), rel=1e-3)
        assert g.num_bonds == 12  # 6 ring bonds + 6 C-H
        assert api.compute(g, "num_rings") == 1
        assert api.validate(g).passed

    def test_ethanol(self, api):
        g = api.parse("CCO", fmt="smiles")
        assert g.molecular_formula == "C2H6O"
        assert g.molecular_weight == pytest.approx(46.069, rel=1e-3)
        assert api.compute(g, "hbd") == 1
        assert api.compute(g, "hba") == 1
        assert api.validate(g).passed

    def test_acetic_acid(self, api):
        g = api.parse("CC(=O)O", fmt="smiles")
        assert g.molecular_formula == "C2H4O2"
        assert g.molecular_weight == pytest.approx(60.052, rel=1e-3)
        assert api.compute(g, "hba") == 2
        assert api.compute(g, "hbd") == 1
        assert api.validate(g).passed

    def test_glucose_from_name(self, api):
        g = api.parse("glucose")
        # True glucose: C6H12O6, 180.156 g/mol
        assert g.molecular_formula == "C6H12O6"
        assert g.molecular_weight == pytest.approx(180.156, rel=1e-3)
        assert g.num_atoms == 24

    def test_caffeine_from_name(self, api):
        g = api.parse("caffeine")
        # True caffeine: C8H10N4O2, 194.19 g/mol
        assert g.molecular_formula == "C8H10N4O2"
        assert g.molecular_weight == pytest.approx(194.19, rel=1e-3)
        assert g.num_atoms == 24
        assert api.validate(g).passed


class TestCanonicalRepresentation:
    def test_canonical_deterministic_ethanol(self, api):
        # Two SMILES for ethanol must canonicalize identically.
        g1 = api.parse("CCO", fmt="smiles")
        g2 = api.parse("OCC", fmt="smiles")
        from chemengine.parsing.canonical import canonical_smiles
        assert canonical_smiles(g1) == canonical_smiles(g2)

    def test_canonical_benzene(self, api):
        from chemengine.parsing.canonical import canonical_smiles
        g1 = api.parse("c1ccccc1", fmt="smiles")
        g2 = api.parse("c1cccc(c1)", fmt="smiles")
        assert canonical_smiles(g1) == canonical_smiles(g2)


class TestGraphConnectivity:
    def test_connected_molecule(self, api):
        g = api.parse("CC(=O)O", fmt="smiles")
        # BFS from atom 0 must reach all atoms.
        seen = {0}
        frontier = [0]
        while frontier:
            nxt = []
            for idx in frontier:
                for n in g.get_neighbors(idx):
                    if n not in seen:
                        seen.add(n)
                        nxt.append(n)
            frontier = nxt
        assert len(seen) == g.num_atoms

    def test_salt_is_two_components(self, api):
        g = api.parse("[Na+].[Cl-]", fmt="smiles")
        assert g.num_atoms == 2
        assert g.num_bonds == 0  # ionic pair: no covalent bond
