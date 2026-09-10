"""compounds ΓÇö Dynamic compound registry with no database.

The core philosophy: compounds are NEVER stored as static records.
Every compound is parsed from a SMILES/formula/name ΓåÆ MolecularGraph,
and ALL properties are computed from that graph on-the-fly.

Admin-editable metadata (common names, safety notes, uses, hazards)
lives in a TOML config file that maps to SMILES strings. The engine
resolves the SMILES to a graph and computes everything else.

Usage:
    >>> from chemengine.compounds import CompoundRegistry
    >>> registry = CompoundRegistry()
    >>> aspirin = registry.resolve("aspirin")
    >>> print(aspirin.smiles)          # 'CC(=O)OC1=CC=CC=C1C(=O)O'
    >>> print(aspirin.graph.molecular_formula)  # 'C9H8O4'
    >>> print(aspirin.metadata.uses)   # ['Pain relief', 'Anti-inflammatory']

    >>> # Or from SMILES directly (no registry needed)
    >>> ethanol = registry.from_smiles("CCO")
    >>> print(ethanol.graph.exact_mass)  # 46.0419

Design:
    - CompoundRegistry: Loads admin-editable TOML config
    - CompoundRecord: SMILES + metadata (names, uses, safety, etc.)
    - Compound: Resolved compound with graph + computed properties
    - No database ΓÇö everything computed from MolecularGraph
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

from chemengine.core.element import Element
from chemengine.core.graph import MolecularGraph

logger = logging.getLogger(__name__)

# Default path to compounds config
_COMPOUNDS_DIR: Path = Path(__file__).resolve().parent.parent / "datasets"


@dataclass(frozen=True, slots=True)
class CompoundMetadata:
    """Admin-editable metadata for a compound.

    This is the ONLY part that's "stored" ΓÇö and it's just text fields
    in a TOML file. The actual chemistry is always computed from the graph.

    Attributes:
        common_names: List of common names (e.g., ['Aspirin', 'Acetylsalicylic acid']).
        uses: List of uses (e.g., ['Pain relief', 'Anti-inflammatory']).
        hazards: Safety hazard descriptions.
        cas_number: CAS registry number.
        category: Compound category (e.g., 'drug', 'solvent', 'reagent').
        description: Free-text description.
        tags: Searchable tags.
    """
    common_names: tuple[str, ...] = ()
    uses: tuple[str, ...] = ()
    hazards: tuple[str, ...] = ()
    cas_number: str = ""
    category: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CompoundRecord:
    """An admin-editable compound entry in the TOML config.

    Contains the SMILES (which is the source of truth for structure)
    and human-readable metadata.
    """
    smiles: str
    metadata: CompoundMetadata = field(default_factory=CompoundMetadata)


@dataclass(frozen=True, slots=True)
class Compound:
    """A fully resolved compound with graph and computed properties.

    Created by the registry from a CompoundRecord. The graph is the
    source of truth ΓÇö all properties are derived from it.

    Attributes:
        smiles: The SMILES string.
        graph: The MolecularGraph (computed from SMILES).
        metadata: Admin-editable metadata.
    """
    smiles: str
    graph: MolecularGraph
    metadata: CompoundMetadata = field(default_factory=CompoundMetadata)

    @property
    def formula(self) -> str:
        return self.graph.molecular_formula

    @property
    def exact_mass(self) -> float:
        return self.graph.exact_mass

    @property
    def molecular_weight(self) -> float:
        return self.graph.molecular_weight

    @property
    def num_atoms(self) -> int:
        return self.graph.num_atoms

    @property
    def num_heavy_atoms(self) -> int:
        return self.graph.num_heavy_atoms

    @property
    def iupac_name(self) -> str:
        from chemengine.nomenclature.iupac import generate_iupac_name
        return generate_iupac_name(self.graph)

    @property
    def inchi(self) -> str:
        from chemengine.parsing.inchi_serializer import serialize_inchi
        return serialize_inchi(self.graph)

    @property
    def inchikey(self) -> str:
        from chemengine.parsing.inchi_serializer import generate_inchi_key
        return generate_inchi_key(self.graph)

    @property
    def formula_dict(self) -> dict[str, int]:
        return self.graph.formula_dict

    def functional_groups(self) -> list[dict[str, Any]]:
        from chemengine.detection.functional_groups import detect_functional_groups_dict
        return detect_functional_groups_dict(self.graph)

    def properties(self) -> dict[str, Any]:
        from chemengine.properties.descriptors import (
            compute_fraction_csp3,
            compute_hba,
            compute_hbd,
            compute_logp,
            compute_rotatable_bonds,
            compute_tpsa,
        )
        return {
            "exact_mass": self.graph.exact_mass,
            "molecular_weight": self.graph.molecular_weight,
            "tpsa": compute_tpsa(self.graph),
            "logp": compute_logp(self.graph),
            "hba": compute_hba(self.graph),
            "hbd": compute_hbd(self.graph),
            "rotatable_bonds": compute_rotatable_bonds(self.graph),
            "fraction_csp3": compute_fraction_csp3(self.graph),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "smiles": self.smiles,
            "formula": self.formula,
            "exact_mass": round(self.exact_mass, 6),
            "molecular_weight": round(self.molecular_weight, 4),
            "iupac_name": self.iupac_name,
            "inchi": self.inchi,
            "inchikey": self.inchikey,
            "metadata": {
                "common_names": list(self.metadata.common_names),
                "uses": list(self.metadata.uses),
                "hazards": list(self.metadata.hazards),
                "cas_number": self.metadata.cas_number,
                "category": self.metadata.category,
                "description": self.metadata.description,
                "tags": list(self.metadata.tags),
            },
        }


class CompoundRegistry:
    """Dynamic compound registry ΓÇö no database, everything computed.

    Loads admin-editable TOML config that maps compound names to SMILES
    strings and metadata. When you resolve a compound, the engine:
    1. Finds the SMILES in the TOML config
    2. Parses SMILES ΓåÆ MolecularGraph
    3. Computes ALL properties from the graph
    4. Returns a Compound with graph + metadata

    Usage:
        >>> registry = CompoundRegistry()
        >>> aspirin = registry.resolve("aspirin")
        >>> print(aspirin.formula)  # 'C9H8O4'
    """

    def __init__(self, config_dir: str | Path | None = None) -> None:
        self._config_dir = Path(config_dir) if config_dir else _COMPOUNDS_DIR
        self._records: dict[str, CompoundRecord] = {}
        self._loaded = False
        self._load_compounds()

    def _load_compounds(self) -> None:
        """Load compound definitions from the TOML config."""
        filepath = self._config_dir / "compounds.toml"
        if not filepath.exists():
            logger.info(f"No compounds.toml found at {filepath}, starting empty")
            self._loaded = True
            return

        try:
            with open(filepath, "rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            logger.warning(f"Failed to load compounds.toml: {e}")
            self._loaded = True
            return

        for name, entry in data.get("compound", {}).items():
            smiles = entry.get("smiles", "")
            if not smiles:
                continue

            meta = CompoundMetadata(
                common_names=tuple(entry.get("common_names", [])),
                uses=tuple(entry.get("uses", [])),
                hazards=tuple(entry.get("hazards", [])),
                cas_number=entry.get("cas_number", ""),
                category=entry.get("category", ""),
                description=entry.get("description", ""),
                tags=tuple(entry.get("tags", [])),
            )
            self._records[name.lower()] = CompoundRecord(smiles=smiles, metadata=meta)

        self._loaded = True
        logger.info(f"Loaded {len(self._records)} compound records from {filepath}")

    def resolve(self, name: str) -> Compound:
        """Resolve a compound by name from the admin-editable config.

        Args:
            name: Compound name (case-insensitive).

        Returns:
            A Compound with graph and metadata.

        Raises:
            KeyError: If the compound is not found.
            ValueError: If the SMILES cannot be parsed.
        """
        key = name.lower()
        if key not in self._records:
            available = ", ".join(sorted(self._records.keys()))
            raise KeyError(
                f"Unknown compound '{name}'. Available: {available}"
            )

        record = self._records[key]
        graph = self._parse_smiles(record.smiles)
        return Compound(
            smiles=record.smiles,
            graph=graph,
            metadata=record.metadata,
        )

    def from_smiles(self, smiles: str) -> Compound:
        """Create a Compound directly from a SMILES string.

        No registry lookup ΓÇö just parse and compute.

        Args:
            smiles: SMILES string.

        Returns:
            A Compound with graph (no metadata).
        """
        graph = self._parse_smiles(smiles)
        return Compound(smiles=smiles, graph=graph)

    def from_formula(self, formula: str) -> Compound:
        """Create a Compound from a molecular formula.

        Note: This creates a disconnected graph (no bonding info).
        Use from_smiles() for structured compounds.

        Args:
            formula: Molecular formula (e.g., 'C2H6O').

        Returns:
            A Compound with graph.
        """
        from chemengine.parsing.formula import parse_formula
        graph = parse_formula(formula)
        return Compound(smiles="", graph=graph)

    def search(self, query: str) -> list[Compound]:
        """Search compounds by name, category, or tags.

        Args:
            query: Search query (case-insensitive).

        Returns:
            List of matching Compounds.
        """
        query_lower = query.lower()
        results: list[Compound] = []

        for name, record in self._records.items():
            # Search in name
            if query_lower in name:
                results.append(self.resolve(name))
                continue
            # Search in common names
            if any(query_lower in cn.lower() for cn in record.metadata.common_names):
                results.append(self.resolve(name))
                continue
            # Search in category
            if query_lower in record.metadata.category.lower():
                results.append(self.resolve(name))
                continue
            # Search in tags
            if any(query_lower in tag.lower() for tag in record.metadata.tags):
                results.append(self.resolve(name))
                continue

        return results

    def list_compounds(self) -> list[str]:
        """List all registered compound names."""
        return sorted(self._records.keys())

    def add_compound(
        self,
        name: str,
        smiles: str,
        metadata: CompoundMetadata | None = None,
    ) -> None:
        """Add a compound to the registry at runtime.

        Args:
            name: Compound name (will be stored lowercase).
            smiles: SMILES string.
            metadata: Optional metadata.
        """
        # Validate SMILES by parsing it
        self._parse_smiles(smiles)

        self._records[name.lower()] = CompoundRecord(
            smiles=smiles,
            metadata=metadata or CompoundMetadata(),
        )

    def _parse_smiles(self, smiles: str) -> MolecularGraph:
        """Parse a SMILES string into a MolecularGraph."""
        from chemengine.parsing.smiles import parse_smiles
        return parse_smiles(smiles)


# ΓöÇΓöÇ Convenience: Built-in Compound Catalog ΓöÇΓöÇ

# These are computed, not stored ΓÇö just SMILES strings with names.
# An admin can override/extend these via compounds.toml.

_BUILTIN_COMPOUNDS: dict[str, dict[str, Any]] = {
    "water": {
        "smiles": "O",
        "common_names": ["Water", "Dihydrogen monoxide"],
        "uses": ["Solvent", "Universal solvent"],
        "category": "solvent",
    },
    "ethanol": {
        "smiles": "CCO",
        "common_names": ["Ethanol", "Ethyl alcohol", "Drinking alcohol"],
        "uses": ["Solvent", "Antiseptic", "Fuel"],
        "category": "solvent",
    },
    "methane": {
        "smiles": "C",
        "common_names": ["Methane", "Marsh gas"],
        "uses": ["Fuel", "Chemical feedstock"],
        "category": "fuel",
    },
    "acetic_acid": {
        "smiles": "CC(=O)O",
        "common_names": ["Acetic acid", "Ethanoic acid", "Vinegar acid"],
        "uses": ["Solvent", "Reagent", "Food additive"],
        "category": "reagent",
    },
    "aspirin": {
        "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "common_names": ["Aspirin", "Acetylsalicylic acid"],
        "uses": ["Pain relief", "Anti-inflammatory", "Antipyretic"],
        "hazards": ["GI bleeding", "Reye's syndrome in children"],
        "cas_number": "50-78-2",
        "category": "drug",
    },
    "caffeine": {
        "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
        "common_names": ["Caffeine", "1,3,7-Trimethylxanthine"],
        "uses": ["Stimulant", "Performance enhancement"],
        "category": "drug",
    },
    "glucose": {
        "smiles": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
        "common_names": ["Glucose", "D-Glucose", "Blood sugar"],
        "uses": ["Energy source", "Biochemical fuel"],
        "category": "biochemical",
    },
    "benzene": {
        "smiles": "c1ccccc1",
        "common_names": ["Benzene", "Cyclohexatriene"],
        "uses": ["Chemical feedstock", "Solvent"],
        "hazards": ["Carcinogen"],
        "category": "chemical",
    },
    "ethanolamine": {
        "smiles": "NCCO",
        "common_names": ["Ethanolamine", "Monoethanolamine", "2-Aminoethanol"],
        "uses": ["Surfactant", "Gas scrubbing"],
        "category": "chemical",
    },
    "acetone": {
        "smiles": "CC(=O)C",
        "common_names": ["Acetone", "Propanone", "Dimethyl ketone"],
        "uses": ["Solvent", "Nail polish remover"],
        "category": "solvent",
    },
}


def _register_builtin_compounds(registry: CompoundRegistry) -> None:
    """Register built-in compound catalog if no config file exists."""
    if not registry._records:
        for name, data in _BUILTIN_COMPOUNDS.items():
            meta = CompoundMetadata(
                common_names=tuple(data.get("common_names", [])),
                uses=tuple(data.get("uses", [])),
                hazards=tuple(data.get("hazards", [])),
                cas_number=data.get("cas_number", ""),
                category=data.get("category", ""),
            )
            registry.add_compound(name, data["smiles"], meta)
