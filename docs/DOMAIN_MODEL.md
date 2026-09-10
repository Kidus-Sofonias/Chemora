# Domain Model

## MolecularGraph

The single source of truth for all chemistry operations.

| Field | Type | Description |
|-------|------|-------------|
| atoms | tuple[Atom, ...] | All atoms in the molecule |
| bonds | tuple[Bond, ...] | All bonds between atoms |
| name | str \| None | Optional human-readable name |
| stereo_config | StereoConfig | Complete stereochemical configuration |
| coordinates_2d | tuple[Coordinate2D, ...] \| None | 2D layout coordinates |
| coordinates_3d | tuple[Coordinate3D, ...] \| None | Primary 3D coordinates |
| conformers | tuple[Conformer, ...] | Additional 3D conformers |
| properties | frozenset[tuple[str, object]] | Extensible key-value metadata |

## Atom

A single atom in the molecular graph.

| Field | Type | Description |
|-------|------|-------------|
| atomic_number | int | Atomic number Z (1-118) |
| isotope | Isotope \| None | Isotopic information |
| formal_charge | int | Formal charge (-3 to +3) |
| radical_electrons | int | Unpaired electrons (0, 1, 2) |
| stereochemistry | ChiralTag | R/S/r/s/none |
| implicit_hydrogens | int \| None | Explicit H count or auto |
| atom_mapping | int \| None | Reaction mapping number |
| properties | frozenset | Extensible metadata |

## Bond

A chemical bond between two atoms.

| Field | Type | Description |
|-------|------|-------------|
| atom1 | int | Index of first atom |
| atom2 | int | Index of second atom |
| order | BondOrder | Single, double, triple, quadruple, aromatic |
| bond_type | BondType | Covalent, dative, ionic, hydrogen, etc. |
| stereochemistry | BondStereo | E/Z, cis/trans |
| topology | BondTopology | Ring, chain, unspecified |
| properties | frozenset | Extensible metadata |

## ChiralCenter

A single stereocenter in a molecule. Can represent both tetrahedral centers (sp3, R/S) and double-bond stereocenters (E/Z).

| Field | Type | Description |
|-------|------|-------------|
| category | StereoCategory | Type: tetrahedral or double_bond |
| atom_index | int \| None | Atom index (for tetrahedral) |
| bond_index | int \| None | Bond index (for double bonds) |
| chiral_tag | ChiralTag | R/S/r/s descriptor |
| bond_stereo | BondStereo | E/Z/cis/trans descriptor |
| substituents | tuple | Substituent indices in CIP priority order |

## StereoConfig

Complete stereochemical configuration for a molecule.

| Field | Type | Description |
|-------|------|-------------|
| centers | tuple[ChiralCenter, ...] | All stereocenters |
| is_assigned | bool | Whether fully assigned |
| assignment_method | str | Method used (e.g., 'cip') |

## Geometry

| Model | Description |
|-------|-------------|
| Coordinate2D | 2D coordinate with distance/midpoint methods |
| Coordinate3D | 3D coordinate with distance/midpoint/to_2d methods |
| Conformer | Complete 3D structure with energy/RMSD metadata |

## Charges

| Model | Description |
|-------|-------------|
| Charge | Charge value + atom index with sign helpers |
| ElectronConfiguration | Electron configuration (shell, valence, unpaired) |
| ChargeDistribution | Complete charge assignment for a molecule |