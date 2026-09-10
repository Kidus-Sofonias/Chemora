"""chemengine — A production-grade chemistry engine.

The Molecular Graph is the single source of truth for all chemistry operations.
Every atom, bond, charge, isotope, stereocenter, coordinate, and property
derives from this graph.

Architecture overview:
    - core/         : Immutable domain models (MolecularGraph, Atom, Bond, etc.)
                      and infrastructure (AlgorithmRegistry, EventBus, PluginManager)
    - parsing/      : Input parsers (SMILES, InChI, formula, IUPAC, aliases)
    - generation/   : Isomer and conformer enumeration
    - detection/    : Substructure, ring, aromaticity, functional group detection
    - stereochemistry/ : R/S, E/Z, cis/trans assignment
    - properties/   : Molecular property computation
    - coordinates/  : 2D and 3D coordinate generation
    - rendering/    : SVG molecular depiction
    - reactions/    : Reaction models, validation, and templates
    - validation/   : Graph sanitization and validity rules
    - io/           : Serialization and format conversion
    - nomenclature/ : IUPAC naming (graph → name)
    - datasets/     : Reference data (elements, isotopes, forcefield params)
    - utils/        : Logging, benchmarking, caching
"""

from chemengine.core.atoms import Atom
from chemengine.core.bonds import Bond, BondOrder
from chemengine.core.enums import BondStereo, ChiralTag, ElementSymbol
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.core.tool_interface import ChemEngineAPI

__all__ = [
    "ChemEngineAPI",
    "MolecularGraph",
    "MolecularGraphBuilder",
    "Atom",
    "Bond",
    "BondOrder",
    "ElementSymbol",
    "ChiralTag",
    "BondStereo",
]

__version__ = "1.0.0"
