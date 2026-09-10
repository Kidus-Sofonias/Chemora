"""Reference datasets for the chemistry engine.

All reference data is stored in versioned JSON/TOML files rather than in code.
This enables:
    - Data updates without code changes
    - Versioned datasets for reproducibility
    - Plugin-contributed datasets
    - Hot-reloading during development

Available datasets:
    - elements.json: Atomic properties (mass, radius, electronegativity, valence)
    - isotopes.json: Isotopic masses and natural abundances
    - functional_groups.toml: SMARTS patterns for functional group detection
    - valence_rules.toml: Element-specific valence and charge limits
    - ring_templates.toml: Ideal ring geometries for 2D layout
    - forcefield.toml: UFF/MMFF forcefield parameters
"""

from chemengine.core.datasets import DatasetRegistry, get_global_dataset_registry

__all__ = ["DatasetRegistry", "get_global_dataset_registry"]
