"""Core domain models and infrastructure for the chemistry engine.

This package contains:
    - Immutable domain models: MolecularGraph, Atom, Bond, Stereocenter, etc.
    - Infrastructure: AlgorithmRegistry, EventBus, PluginManager, ChemEngineAPI
    - Enums: ElementSymbol, BondOrder, ChiralTag, BondStereo, etc.

The MolecularGraph is the single source of truth. Every module communicates
through these immutable models. No module passes ad-hoc dicts or lists.
"""

from chemengine.core.atoms import Atom, Isotope
from chemengine.core.bonds import Bond, BondOrder, BondType
from chemengine.core.charges import Charge, ChargeDistribution, ElectronConfiguration
from chemengine.core.datasets import Dataset, DatasetRegistry
from chemengine.core.element import Element, ElementQuery, IsotopeInfo
from chemengine.core.enums import (
    BondStereo,
    BondTopology,
    ChiralTag,
    ElementSymbol,
    Hybridization,
    IsotopeType,
    RadicalType,
    SpinMultiplicity,
    StereoCategory,
)
from chemengine.core.events import Event, EventBus, EventType, SubscriptionToken
from chemengine.core.geometry import Conformer, Coordinate2D, Coordinate3D
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.core.plugin import PluginManager, PluginProtocol
from chemengine.core.registry import AlgorithmEntry, AlgorithmRegistry
from chemengine.core.stereo import ChiralCenter, StereoConfig
from chemengine.core.tool_interface import ChemEngineAPI, ToolDefinition

__all__ = [
    "MolecularGraph",
    "MolecularGraphBuilder",
    "Atom",
    "Isotope",
    "Element",
    "ElementQuery",
    "IsotopeInfo",
    "Bond",
    "BondOrder",
    "BondType",
    "BondTopology",
    "ChiralCenter",
    "StereoConfig",
    "Coordinate2D",
    "Coordinate3D",
    "Conformer",
    "Charge",
    "ElectronConfiguration",
    "ChargeDistribution",
    "ElementSymbol",
    "ChiralTag",
    "BondStereo",
    "StereoCategory",
    "RadicalType",
    "IsotopeType",
    "Hybridization",
    "SpinMultiplicity",
    "AlgorithmRegistry",
    "AlgorithmEntry",
    "EventBus",
    "Event",
    "EventType",
    "SubscriptionToken",
    "PluginProtocol",
    "PluginManager",
    "ChemEngineAPI",
    "ToolDefinition",
    "DatasetRegistry",
    "Dataset",
]
