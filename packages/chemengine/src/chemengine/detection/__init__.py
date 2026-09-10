"""Detection subsystem — ring perception, aromaticity, functional groups, substructure matching.

Provides:
    - Ring detection (BFS-based SSSR with Ring objects) in rings.py
    - Ring system analysis (fused/bridged/spiro) in ring_systems.py
    - Aromaticity detection (Hückel 4n+2 rule) in aromaticity.py
    - Functional group detection (21+ groups with overlap resolution) in functional_groups.py    - Substructure matching (VF2 subgraph isomorphism + SMARTS)
"""

from chemengine.detection.aromaticity import (
    AromaticityResult,
    AromaticityType,
    assess_all_rings,
    assess_ring_aromaticity,
    assign_aromaticity,
)
from chemengine.detection.functional_groups import (
    FunctionalGroupMatch,
    detect_functional_groups,
    detect_functional_groups_dict,
    get_functional_groups,
    list_available_groups,
)
from chemengine.detection.ring_systems import (
    RingSystem,
    RingSystemType,
    detect_ring_systems,
    is_bridgehead_atom,
    is_spiro_center,
)
from chemengine.detection.rings import (
    detect_rings,
    find_all_rings,
    is_ring_atom,
    is_ring_bond,
    ring_count,
)

__all__ = [
    # Rings
    "detect_rings",
    "find_all_rings",
    "ring_count",
    "is_ring_atom",
    "is_ring_bond",
    # Ring systems
    "RingSystem",
    "RingSystemType",
    "detect_ring_systems",
    "is_spiro_center",
    "is_bridgehead_atom",
    # Aromaticity
    "AromaticityResult",
    "AromaticityType",
    "assess_ring_aromaticity",
    "assess_all_rings",
    "assign_aromaticity",
    # Functional groups
    "FunctionalGroupMatch",
    "detect_functional_groups",
    "detect_functional_groups_dict",
    "list_available_groups",
    "get_functional_groups",
    # Substructure
    "has_subgraph_match",
    "find_subgraph_matches",
    "count_subgraph_matches",
    "maximum_common_substructure",
]

from chemengine.detection.substructure import (
    count_subgraph_matches,
    find_subgraph_matches,
    has_subgraph_match,
    maximum_common_substructure,
)
