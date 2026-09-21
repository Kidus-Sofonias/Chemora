"""Nomenclature — IUPAC naming engine (M33: naming, common names, tautomers).

Modules:
    iupac: Graph -> IUPAC name for basic organic molecules
    tautomers: Bounded keto-enol / amide-imidic tautomer handling
    common_names: Curated common/trivial-name dictionary (audit tools)
"""

from chemengine.nomenclature.common_names import (
    COMMON_NAMES_COUNT,
    common_names,
    validate_common_names,
)
from chemengine.nomenclature.iupac import generate_iupac_name
from chemengine.nomenclature.tautomers import (
    MAX_TAUTOMER_FORMS,
    TautomerForm,
    TautomerSite,
    TautomerType,
    canonical_tautomer,
    detect_tautomers,
    enumerate_tautomers,
)

__all__ = [
    "COMMON_NAMES_COUNT",
    "MAX_TAUTOMER_FORMS",
    "TautomerForm",
    "TautomerSite",
    "TautomerType",
    "canonical_tautomer",
    "common_names",
    "detect_tautomers",
    "enumerate_tautomers",
    "generate_iupac_name",
    "validate_common_names",
]
