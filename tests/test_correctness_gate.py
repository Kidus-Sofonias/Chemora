"""Correctness gate tests — Phases B & C.

Covers:
    - ChemEngineAPI.compute() delegation to the properties subsystem
    - convert() real serializers and accurate unsupported-target errors
"""

import inspect

import pytest

from chemengine.core.tool_interface import ChemEngineAPI


@pytest.fixture
def api() -> ChemEngineAPI:
    return ChemEngineAPI()


# ── Phase B: compute() delegates to the properties subsystem ──


class TestComputeDelegation:
    def test_mass_water(self, api):
        g = api.parse("O", fmt="smiles")
        assert api.compute(g, "mass") == pytest.approx(18.01056468, rel=1e-6)

    def test_logp_delegates(self, api):
        from chemengine.properties.descriptors import compute_logp
        g = api.parse("CCO", fmt="smiles")
        assert api.compute(g, "logp") == compute_logp(g)

    def test_tpsa_delegates(self, api):
        from chemengine.properties.descriptors import compute_tpsa
        g = api.parse("CC(=O)O", fmt="smiles")
        assert api.compute(g, "tpsa") == compute_tpsa(g)

    def test_fraction_csp3_delegates(self, api):
        from chemengine.properties.descriptors import compute_fraction_csp3
        g = api.parse("CCCC", fmt="smiles")
        assert api.compute(g, "fraction_csp3") == 1.0
        assert api.compute(g, "fraction_csp3") == compute_fraction_csp3(g)

    def test_hba_hbd_acetic_acid(self, api):
        g = api.parse("CC(=O)O", fmt="smiles")
        # Acetic acid: 2 acceptors (both O), 1 donor (OH)
        assert api.compute(g, "hba") == 2
        assert api.compute(g, "hbd") == 1

    def test_rotatable_bonds(self, api):
        g = api.parse("CCCC", fmt="smiles")
        assert api.compute(g, "rotatable_bonds") == 1

    def test_heavy_atoms_and_formula(self, api):
        g = api.parse("CCO", fmt="smiles")
        assert api.compute(g, "heavy_atoms") == 3
        assert api.compute(g, "formula") == "C2H6O"

    def test_num_rings(self, api):
        g = api.parse("c1ccccc1", fmt="smiles")
        assert api.compute(g, "num_rings") == 1

    def test_unknown_property_error_lists_supported(self, api):
        g = api.parse("O", fmt="smiles")
        with pytest.raises(ValueError, match="Supported properties"):
            api.compute(g, "does_not_exist")

    def test_no_duplicate_descriptor_logic(self, api):
        # compute() must delegate — the old duplicate helpers are gone.
        import chemengine.core.tool_interface as ti
        source = inspect.getsource(ti)
        assert "_count_hba" not in source
        assert "_count_hbd" not in source


# ── Phase C: convert() uses real serializers ──


class TestConvert:
    def test_to_formula(self, api):
        g = api.parse("CCO", fmt="smiles")
        assert api.convert(g, "formula") == "C2H6O"

    def test_to_smiles_roundtrip(self, api):
        g = api.parse("CCO", fmt="smiles")
        smiles = api.convert(g, "smiles")
        assert api.parse(smiles, fmt="smiles").molecular_formula == "C2H6O"

    def test_to_inchi(self, api):
        g = api.parse("CCO", fmt="smiles")
        inchi = api.convert(g, "inchi")
        assert inchi.startswith("InChI=")
        assert "C2H6O" in inchi

    def test_to_inchikey(self, api):
        g = api.parse("CCO", fmt="smiles")
        key = api.convert(g, "inchikey")
        assert len(key) == 27
        assert key.count("-") == 2

    def test_unknown_target_lists_supported(self, api):
        g = api.parse("CCO", fmt="smiles")
        with pytest.raises(ValueError, match="smiles, inchi, inchikey, formula"):
            api.convert(g, "name")

    def test_docstring_matches_supported_targets(self):
        doc = ChemEngineAPI.convert.__doc__
        supported_section = doc.split("Raises:")[0]
        assert "'name'" not in supported_section
        for target in ("smiles", "inchi", "inchikey", "formula"):
            assert target in supported_section
