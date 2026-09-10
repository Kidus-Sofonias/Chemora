# Modules

## Core (`chemengine/core/`)

| Module | Responsibility |
|--------|---------------|
| graph.py | MolecularGraph (single source of truth), MolecularGraphBuilder |
| atoms.py | Atom, Isotope |
| bonds.py | Bond, BondOrder, BondType |
| stereo.py | ChiralCenter, StereoConfig |
| geometry.py | Coordinate2D, Coordinate3D, Conformer |
| charges.py | Charge, ElectronConfiguration, ChargeDistribution |
| enums.py | ElementSymbol, BondOrder, BondType, BondTopology, ChiralTag, BondStereo, StereoCategory, etc. |
| element.py | Element, ElementQuery, IsotopeInfo |
| substructure.py | FunctionalGroup, Ring |
| molecule.py | Molecule, MolecularIdentifiers, MolecularProperties |
| registry.py | AlgorithmRegistry, AlgorithmEntry |
| events.py | EventBus, Event, EventType, SubscriptionToken |
| plugin.py | PluginProtocol, PluginManager |
| tool_interface.py | ChemEngineAPI, ToolDefinition |
| datasets.py | DatasetRegistry, Dataset |

## Parsing (`chemengine/parsing/`)

| Module | Responsibility |
|--------|---------------|
| protocol.py | Parser Protocol, auto_detect_format, parse_any |
| formula.py | Molecular formula → MolecularGraph |
| smiles.py | SMILES → MolecularGraph and inverse (OpenSMILES spec) |
| canonical.py | Canonical SMILES (Morgan-like invariants) |
| inchi.py | InChI → MolecularGraph (formula, connections, hydrogens, charge layers) |
| alias.py | Common name → SMILES (100+ chemical names) |
| errors.py | Position-aware parsing errors (SmilesSyntaxError, etc.) |

## Generation (`chemengine/generation/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | Constitutional isomer enumeration — Phase 4 |
| (stub) | Stereoisomer enumeration — Phase 4 |
| (stub) | Conformer generation — Phase 4 |

## Detection (`chemengine/detection/`)

| Module | Responsibility |
|--------|---------------|
| rings.py | SSSR ring perception, ring count, ring atom detection |
| (stub) | Hückel aromaticity detection — Phase 2 |
| (stub) | SMARTS-based functional group matching — Phase 2 |
| (stub) | VF2 subgraph isomorphism — Phase 2 |

## Stereochemistry (`chemengine/stereochemistry/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | CIP rule engine, R/S assignment — Phase 3 |
| (stub) | E/Z, cis/trans assignment — Phase 3 |
| (stub) | Stereo descriptor storage and comparison — Phase 3 |

## Properties (`chemengine/properties/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | Molecular property computation (mass, logP, TPSA) — Phase 5 |

## Coordinates (`chemengine/coordinates/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | 2D layout + 3D conformer generation — Phase 5 |

## Rendering (`chemengine/rendering/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | SVG molecule depiction — Phase 6 |
| (stub) | ASCII art / text representation — Phase 6 |

## Reactions (`chemengine/reactions/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | Reaction infrastructure — Phase 6 |

## Validation (`chemengine/validation/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | Graph sanitization and valence rules — Phase 4 |

## IO (`chemengine/io/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | Serialization and format conversion — Phase 7 |

## Nomenclature (`chemengine/nomenclature/`)

| Module | Responsibility |
|--------|---------------|
| (stub) | IUPAC naming engine — Phase 7 |

## Utils (`chemengine/utils/`)

| Module | Responsibility |
|--------|---------------|
| logging.py | Structured logging (structlog) |
| benchmarking.py | Performance measurement decorators |
| cache.py | LRU cache for expensive computations |

## Datasets (`chemengine/datasets/`)

| Module | Responsibility |
|--------|---------------|
| elements.json | All 118 elements with full properties |
| functional_groups.toml | SMARTS patterns for functional groups |
| ring_templates.toml | Ideal ring geometries |
| valence_rules.toml | Element-specific valence and charge limits |