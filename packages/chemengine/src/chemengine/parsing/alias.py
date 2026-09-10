"""Common chemical name resolver — maps trivial names to SMILES.

Supports:
    - Small molecules (water, ammonia, methane, etc.)
    - Organic solvents (ethanol, acetone, benzene, etc.)
    - Common drugs (aspirin, paracetamol, caffeine)
    - Amino acids (glycine, alanine, etc.)
    - Ions and functional groups
"""

from __future__ import annotations

from typing import Any

from chemengine.core.graph import MolecularGraph
from chemengine.parsing.protocol import Parser
from chemengine.parsing.smiles import parse_smiles

# ── Common Name → SMILES Lookup ──

_COMMON_ALIASES: dict[str, str] = {
    # Small molecules
    "water": "O",
    "water (h2o)": "O",
    "ammonia": "N",
    "methane": "C",
    "hydrogen": "[H][H]",
    "oxygen": "O=O",
    "nitrogen": "N#N",
    "carbon dioxide": "O=C=O",
    "carbon monoxide": "C#O",
    "hydrogen chloride": "Cl",
    "hydrogen fluoride": "F",
    "hydrogen sulfide": "S",
    "sulfuric acid": "OS(=O)(=O)O",
    "nitric acid": "O[N+](=O)[O-]",
    "hydrochloric acid": "Cl",
    "acetic acid": "CC(=O)O",

    # Hydrocarbons
    "ethane": "CC",
    "propane": "CCC",
    "butane": "CCCC",
    "pentane": "CCCCC",
    "hexane": "CCCCCC",
    "heptane": "CCCCCCC",
    "octane": "CCCCCCCC",
    "nonane": "CCCCCCCCC",
    "decane": "CCCCCCCCCC",
    "ethene": "C=C",
    "ethylene": "C=C",
    "acetylene": "C#C",
    "ethyne": "C#C",
    "propene": "CC=C",
    "propylene": "CC=C",
    "propyne": "CC#C",
    "butadiene": "C=CC=C",
    "benzene": "c1ccccc1",
    "toluene": "Cc1ccccc1",
    "xylene": "Cc1ccc(C)cc1",  # p-xylene
    "styrene": "C=Cc1ccccc1",
    "naphthalene": "c1ccc2ccccc2c1",

    # Alcohols
    "methanol": "CO",
    "ethanol": "CCO",
    "propanol": "CCCO",
    "isopropanol": "CC(C)O",
    "butanol": "CCCCO",
    "ethylene glycol": "OCCO",
    "glycerol": "OCC(O)CO",
    "phenol": "c1ccc(O)cc1",

    # Aldehydes & Ketones
    "formaldehyde": "C=O",
    "acetaldehyde": "CC=O",
    "acetone": "CC(=O)C",
    "benzaldehyde": "O=Cc1ccccc1",

    # Carboxylic acids
    "formic acid": "C(=O)O",
    "propionic acid": "CCC(=O)O",
    "butyric acid": "CCCC(=O)O",
    "benzoic acid": "c1ccc(C(=O)O)cc1",

    # Esters
    "methyl acetate": "CC(=O)OC",
    "ethyl acetate": "CC(=O)OCC",

    # Amines
    "methylamine": "CN",
    "dimethylamine": "CNC",
    "trimethylamine": "CN(C)C",
    "ethylamine": "CCN",
    "triethylamine": "CCN(CC)CC",
    "aniline": "Nc1ccccc1",
    "pyridine": "c1ccncc1",
    "piperidine": "C1CCNCC1",
    "pyrrolidine": "C1CCNC1",

    # Ethers
    "dimethyl ether": "COC",
    "diethyl ether": "CCOCC",
    "methyl tert-butyl ether": "COC(C)(C)C",
    "tetrahydrofuran": "C1CCOC1",
    "dioxane": "C1COCCO1",

    # Halogenated
    "chloroform": "C(Cl)(Cl)Cl",
    "dichloromethane": "C(Cl)Cl",
    "carbon tetrachloride": "C(Cl)(Cl)(Cl)Cl",
    "chlorobenzene": "c1ccc(Cl)cc1",

    # Heterocycles
    "furan": "c1ccoc1",
    "thiophene": "c1ccsc1",
    "pyrrole": "c1cc[nH]c1",
    "imidazole": "c1cnc[nH]1",
    "pyrazole": "c1cn[nH]c1",
    "oxazole": "c1cocn1",
    "thiazole": "c1cscn1",
    "pyrimidine": "c1cncnc1",
    "pyrazine": "c1cnccn1",
    "indole": "c1ccc2[nH]ccc2c1",
    "quinoline": "c1ccc2ncccc2c1",
    "purine": "c1c2c(nc1)ncn2",

    # Common drugs
    "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "acetaminophen": "CC(=O)Nc1ccc(O)cc1",
    "ibuprofen": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "caffeine": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "nicotine": "CN1CCCC1c1cccnc1",
    "glucose": "OC[C@@H](O1)[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",
    "sucrose": "OC[C@H]1O[C@@](CO)(O[C@H]2[C@H](O)[C@@H](O)[C@H](O)[C@@H](CO)O2)[C@@H](O)[C@@H]1O",

    # Amino acids
    "glycine": "C(C(=O)O)N",
    "alanine": "CC(C(=O)O)N",
    "valine": "CC(C)C(C(=O)O)N",
    "leucine": "CC(C)CC(C(=O)O)N",
    "isoleucine": "CC[C@H](C)[C@@H](C(=O)O)N",
    "serine": "C([C@@H](C(=O)O)N)O",
    "cysteine": "C([C@@H](C(=O)O)N)S",
    "methionine": "CSCC[C@@H](C(=O)O)N",
    "phenylalanine": "C1=CC=C(C=C1)C[C@@H](C(=O)O)N",
    "tyrosine": "C1=CC(=CC=C1C[C@@H](C(=O)O)N)O",
    "tryptophan": "c1ccc2c(c1)c([nH]c2)C[C@@H](C(=O)O)N",
    "proline": "C1C[C@H](NC1)C(=O)O",
    "lysine": "C(CCN)C[C@@H](C(=O)O)N",
    "arginine": "C(C[C@@H](C(=O)O)N)CN=C(N)N",
    "histidine": "c1c[nH]cn1C[C@@H](C(=O)O)N",
    "aspartic acid": "C([C@@H](C(=O)O)N)C(=O)O",
    "glutamic acid": "C(CC(=O)O)[C@@H](C(=O)O)N",
    "asparagine": "C([C@@H](C(=O)O)N)C(=O)N",
    "glutamine": "C(CC(=O)N)[C@@H](C(=O)O)N",
}


def resolve_alias(name: str) -> str | None:
    """Resolve a common chemical name to a SMILES string.

    Args:
        name: The common name (e.g., 'water', 'benzene', 'aspirin').

    Returns:
        SMILES string if found, None otherwise.
    """
    clean = name.strip().lower()
    return _COMMON_ALIASES.get(clean)


def resolve_alias_to_graph(name: str) -> MolecularGraph | None:
    """Resolve a common chemical name to a MolecularGraph.

    Args:
        name: The common name.

    Returns:
        MolecularGraph if found, None otherwise.
    """
    smiles = resolve_alias(name)
    if smiles is None:
        return None
    return parse_smiles(smiles)


class AliasParser(Parser):
    """Parser that resolves common chemical names to molecular graphs."""

    def parse(self, text: str, /, **options: Any) -> MolecularGraph:
        graph = resolve_alias_to_graph(text)
        if graph is None:
            raise ValueError(f"Unknown chemical name: '{text}'")
        return graph

    def serialize(self, graph: MolecularGraph, /, **options: Any) -> str:
        raise NotImplementedError("AliasParser does not support serialization")


def register_alias_parser(registry: Any) -> None:
    """Register the alias resolver with the AlgorithmRegistry."""
    from chemengine.core.registry import AlgorithmEntry

    parser = AliasParser()
    registry.register(AlgorithmEntry(
        domain="parsing.alias",
        name="default",
        version="1.0.0",
        algorithm=parser.parse,
        input_type=str,
        output_type=MolecularGraph,
        tags=frozenset({"alias", "parsing", "fast"}),
    ))
