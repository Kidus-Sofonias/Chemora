"""education — Educational chemistry module for ChemEngine.

Provides educational tools for students, teachers, and scientists:
    - electron_config: Electron configuration generation from first principles
    - lewis_structures: Lewis structure generation from first principles
    - stoichiometry: Stoichiometric calculations from first principles

Design philosophy:
    Everything is computed from first principles. No database lookups for
    compound data — the engine derives properties, names, and explanations
    from the molecular graph and fundamental chemistry rules.
"""

from chemengine.education.electron_config import (
    ElectronConfiguration,
    ElectronConfigurator,
    ElectronShell,
    OrbitalDiagram,
    OrbitalOccupancy,
    calculate_electron_configuration,
)
from chemengine.education.lewis_structures import (
    LewisStructure,
    LewisStructureGenerator,
    LonePairInfo,
)
from chemengine.education.stoichiometry import (
    BalancedEquation,
    MolarMass,
    StoichiometryCalculator,
    StoichiometryResult,
)

__all__ = [
    "ElectronConfigurator",
    "ElectronConfiguration",
    "OrbitalDiagram",
    "ElectronShell",
    "OrbitalOccupancy",
    "calculate_electron_configuration",
    "LewisStructureGenerator",
    "LewisStructure",
    "LonePairInfo",
    "StoichiometryCalculator",
    "StoichiometryResult",
    "BalancedEquation",
    "MolarMass",
]
