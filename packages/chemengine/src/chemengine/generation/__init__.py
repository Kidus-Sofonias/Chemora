"""Generation subsystem — enumeration of isomers and conformers.

Provides:
    - Constitutional isomer enumeration (canonical augmentation)
    - Stereoisomer enumeration (from a constitutional graph)
    - Conformer generation (distance geometry + forcefield)
    - Isomer filtering by formula, mass, substructure
    - Lazy iteration for large isomer spaces
"""

from chemengine.generation.constitutional import (
    alkane_isomer_count,
    enumerate_functional_group_isomers,
    generate_alkane_isomers,
)
from chemengine.generation.filtering import (
    IsomerFilter,
    count_isomers_lazy,
    lazy_alkane_isomers,
    lazy_filtered_isomers,
)
from chemengine.generation.stereoisomers import (
    enumerate_stereoisomers,
)

__all__ = [
    "generate_alkane_isomers",
    "alkane_isomer_count",
    "enumerate_functional_group_isomers",
    "enumerate_stereoisomers",
    "IsomerFilter",
    "lazy_alkane_isomers",
    "lazy_filtered_isomers",
    "count_isomers_lazy",
]
