"""Enumerations for the chemistry engine — Milestone 1.

This module defines all shared enum types used across the engine. These are
the fundamental building blocks that every other domain model references.
Using enums rather than strings or integers provides type safety, prevents
invalid values, and makes the code self-documenting.

Every enum here is a StrEnum or IntEnum for serialization compatibility.
"""

from __future__ import annotations

import sys
from enum import Enum, IntEnum
from typing import Final

# StrEnum was introduced in Python 3.11. Provide a backport for Python 3.10.
if sys.version_info >= (3, 11):
    from enum import StrEnum as _StrEnum
else:
    class _StrEnum(str, Enum):
        """Backport of Python 3.11's StrEnum for Python 3.10."""
        def __repr__(self) -> str:
            return f"<{self.__class__.__name__}.{self.name}: {self.value!r}>"

# Re-export as StrEnum for consistent usage throughout the codebase
StrEnum = _StrEnum


class ElementSymbol(StrEnum):
    """All 118 known chemical element symbols.

    This enum provides type-safe element symbols used throughout the engine.
    Each member maps to its IUPAC-standard symbol string. The enum supports
    lookup by symbol (ElementSymbol("C")) and provides atomic number via
    the `atomic_number` property.

    Usage:
        >>> carbon = ElementSymbol("C")
        >>> carbon.atomic_number
        6
        >>> ElementSymbol.from_atomic_number(6)
        <ElementSymbol.C: 'C'>
    """

    # Period 1
    H = "H"
    He = "He"
    # Period 2
    Li = "Li"
    Be = "Be"
    B = "B"
    C = "C"
    N = "N"
    O = "O"
    F = "F"
    Ne = "Ne"
    # Period 3
    Na = "Na"
    Mg = "Mg"
    Al = "Al"
    Si = "Si"
    P = "P"
    S = "S"
    Cl = "Cl"
    Ar = "Ar"
    # Period 4
    K = "K"
    Ca = "Ca"
    Sc = "Sc"
    Ti = "Ti"
    V = "V"
    Cr = "Cr"
    Mn = "Mn"
    Fe = "Fe"
    Co = "Co"
    Ni = "Ni"
    Cu = "Cu"
    Zn = "Zn"
    Ga = "Ga"
    Ge = "Ge"
    As = "As"
    Se = "Se"
    Br = "Br"
    Kr = "Kr"
    # Period 5
    Rb = "Rb"
    Sr = "Sr"
    Y = "Y"
    Zr = "Zr"
    Nb = "Nb"
    Mo = "Mo"
    Tc = "Tc"
    Ru = "Ru"
    Rh = "Rh"
    Pd = "Pd"
    Ag = "Ag"
    Cd = "Cd"
    In = "In"
    Sn = "Sn"
    Sb = "Sb"
    Te = "Te"
    I = "I"
    Xe = "Xe"
    # Period 6
    Cs = "Cs"
    Ba = "Ba"
    La = "La"
    Ce = "Ce"
    Pr = "Pr"
    Nd = "Nd"
    Pm = "Pm"
    Sm = "Sm"
    Eu = "Eu"
    Gd = "Gd"
    Tb = "Tb"
    Dy = "Dy"
    Ho = "Ho"
    Er = "Er"
    Tm = "Tm"
    Yb = "Yb"
    Lu = "Lu"
    Hf = "Hf"
    Ta = "Ta"
    W = "W"
    Re = "Re"
    Os = "Os"
    Ir = "Ir"
    Pt = "Pt"
    Au = "Au"
    Hg = "Hg"
    Tl = "Tl"
    Pb = "Pb"
    Bi = "Bi"
    Po = "Po"
    At = "At"
    Rn = "Rn"
    # Period 7
    Fr = "Fr"
    Ra = "Ra"
    Ac = "Ac"
    Th = "Th"
    Pa = "Pa"
    U = "U"
    Np = "Np"
    Pu = "Pu"
    Am = "Am"
    Cm = "Cm"
    Bk = "Bk"
    Cf = "Cf"
    Es = "Es"
    Fm = "Fm"
    Md = "Md"
    No = "No"
    Lr = "Lr"
    Rf = "Rf"
    Db = "Db"
    Sg = "Sg"
    Bh = "Bh"
    Hs = "Hs"
    Mt = "Mt"
    Ds = "Ds"
    Rg = "Rg"
    Cn = "Cn"
    Nh = "Nh"
    Fl = "Fl"
    Mc = "Mc"
    Lv = "Lv"
    Ts = "Ts"
    Og = "Og"

    @property
    def atomic_number(self) -> int:
        """Return the atomic number (Z) for this element symbol."""
        return _SYMBOL_TO_Z[self.value]

    @property
    def group(self) -> int:
        """Return the periodic table group (1-18). 0 for f-block."""
        from chemengine.core.element import Element
        return Element.get(self.value).group

    @property
    def period(self) -> int:
        """Return the periodic table period (1-7)."""
        from chemengine.core.element import Element
        return Element.get(self.value).period

    @property
    def is_metal(self) -> bool:
        """Whether this element is classified as a metal."""
        from chemengine.core.element import Element
        return Element.get(self.value).is_metal

    @property
    def is_nonmetal(self) -> bool:
        """Whether this element is classified as a nonmetal."""
        from chemengine.core.element import Element
        return Element.get(self.value).is_nonmetal

    @property
    def is_metalloid(self) -> bool:
        """Whether this element is classified as a metalloid."""
        from chemengine.core.element import Element
        return Element.get(self.value).is_metalloid

    @property
    def common_valences(self) -> tuple[int, ...]:
        """Return the common valence states for this element."""
        from chemengine.core.element import Element
        return Element.get(self.value).oxidation_states

    @property
    def default_valence(self) -> int:
        """Return the most common/default valence for this element."""
        from chemengine.core.element import Element
        vals = Element.get(self.value).oxidation_states
        return vals[0] if vals else 0

    @property
    def max_valence(self) -> int:
        """Return the maximum known valence for this element."""
        from chemengine.core.element import Element
        return Element.get(self.value).max_valence

    @classmethod
    def from_atomic_number(cls, z: int) -> ElementSymbol:
        """Look up an element by its atomic number (1-118)."""
        if z < 1 or z > 118:
            raise ValueError(f"Invalid atomic number: {z}. Must be 1-118.")
        return cls(_Z_TO_SYMBOL[z])


# Internal lookup tables (only symbol<->z, rest delegated to Element)
_SYMBOL_TO_Z: Final[dict[str, int]] = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9, "Ne": 10,
    "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16, "Cl": 17, "Ar": 18,
    "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25, "Fe": 26,
    "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32, "As": 33, "Se": 34,
    "Br": 35, "Kr": 36, "Rb": 37, "Sr": 38, "Y": 39, "Zr": 40, "Nb": 41, "Mo": 42,
    "Tc": 43, "Ru": 44, "Rh": 45, "Pd": 46, "Ag": 47, "Cd": 48, "In": 49, "Sn": 50,
    "Sb": 51, "Te": 52, "I": 53, "Xe": 54, "Cs": 55, "Ba": 56,
    "La": 57, "Ce": 58, "Pr": 59, "Nd": 60, "Pm": 61, "Sm": 62, "Eu": 63, "Gd": 64,
    "Tb": 65, "Dy": 66, "Ho": 67, "Er": 68, "Tm": 69, "Yb": 70, "Lu": 71,
    "Hf": 72, "Ta": 73, "W": 74, "Re": 75, "Os": 76, "Ir": 77, "Pt": 78, "Au": 79,
    "Hg": 80, "Tl": 81, "Pb": 82, "Bi": 83, "Po": 84, "At": 85, "Rn": 86,
    "Fr": 87, "Ra": 88, "Ac": 89, "Th": 90, "Pa": 91, "U": 92, "Np": 93, "Pu": 94,
    "Am": 95, "Cm": 96, "Bk": 97, "Cf": 98, "Es": 99, "Fm": 100, "Md": 101, "No": 102,
    "Lr": 103, "Rf": 104, "Db": 105, "Sg": 106, "Bh": 107, "Hs": 108, "Mt": 109,
    "Ds": 110, "Rg": 111, "Cn": 112, "Nh": 113, "Fl": 114, "Mc": 115, "Lv": 116,
    "Ts": 117, "Og": 118,
}

_Z_TO_SYMBOL: Final[dict[int, str]] = {v: k for k, v in _SYMBOL_TO_Z.items()}


class BondOrder(IntEnum):
    """Chemical bond order (multiplicity).

    Represents the number of electron pairs shared between two atoms.
    AROMATIC represents a delocalized bond in an aromatic system (order ~1.5).
    QUADRUPLE represents metal-metal quadruple bonds found in coordination chemistry.
    """

    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3
    QUADRUPLE = 4
    AROMATIC = 5

    @property
    def is_single(self) -> bool:
        return self == BondOrder.SINGLE

    @property
    def is_double(self) -> bool:
        return self == BondOrder.DOUBLE

    @property
    def is_triple(self) -> bool:
        return self == BondOrder.TRIPLE

    @property
    def is_aromatic(self) -> bool:
        return self == BondOrder.AROMATIC

    @property
    def pi_bond_count(self) -> int:
        """Number of pi bonds (sigma bonds excluded)."""
        if self == BondOrder.DOUBLE:
            return 1
        if self == BondOrder.TRIPLE:
            return 2
        return 0

    @property
    def electron_count(self) -> int:
        """Number of electrons shared in this bond."""
        if self == BondOrder.AROMATIC:
            return 3  # ~1.5 * 2, but aromatic bonds delocalize
        return int(self) * 2


class BondType(StrEnum):
    """Classification of bond types for chemical reasoning.

    This enum categorizes bonds beyond simple order, enabling the engine to
    distinguish between different bonding contexts (e.g., covalent vs. dative
    in coordination compounds, or hydrogen bonds in biomolecules).
    """

    COVALENT = "covalent"
    DATIVE = "dative"
    IONIC = "ionic"
    HYDROGEN = "hydrogen"
    METALLIC = "metallic"
    AROMATIC = "aromatic"
    UNKNOWN = "unknown"


class BondTopology(StrEnum):
    """Topological context of a bond within the molecular graph.

    Distinguishes ring bonds from chain bonds, which is important for
    stereochemistry, ring perception, and property computation.
    """

    RING = "ring"
    CHAIN = "chain"
    UNSPECIFIED = "unspecified"


class ChiralTag(StrEnum):
    """Tetrahedral stereocenter descriptors (Cahn-Ingold-Prelog).

    Covers both absolute and relative stereochemistry, including
    pseudo-asymmetric centers (r, s) found in meso compounds.

    TH1 and TH2 are SMILES-specific notations for tetrahedral
    stereochemistry (@ and @@ respectively).
    """

    R = "R"
    S = "S"
    r = "r"
    s = "s"
    TH1 = "@"
    TH2 = "@@"
    NONE = "none"


class BondStereo(StrEnum):
    """Double bond stereochemistry descriptors.

    Covers E/Z (IUPAC preferred), cis/trans (common usage), and
    unspecified/not-stereogenic cases.
    """

    E = "E"
    Z = "Z"
    CIS = "cis"
    TRANS = "trans"
    NONE = "none"


class StereoCategory(StrEnum):
    """Broad classification of stereochemical elements.

    Used to categorize stereocenters for enumeration and filtering.
    """

    TETRAHEDRAL = "tetrahedral"
    DOUBLE_BOND = "double_bond"
    ALLENE = "allene"
    PLANAR = "planar"
    OCTAHEDRAL = "octahedral"
    SQUARE_PLANAR = "square_planar"
    NONE = "none"


class Hybridization(StrEnum):
    """Orbital hybridization state of an atom.

    Describes the mixing of atomic orbitals to form hybrid orbitals
    for bonding. sp = linear, sp2 = trigonal planar, sp3 = tetrahedral,
    sp3d = trigonal bipyramidal, sp3d2 = octahedral.
    """

    S = "s"
    SP = "sp"
    SP2 = "sp2"
    SP3 = "sp3"
    SP3D = "sp3d"
    SP3D2 = "sp3d2"
    UNKNOWN = "unknown"


class RadicalType(StrEnum):
    """Classification of radical species."""

    NONE = "none"
    MONORADICAL = "monoradical"
    DIRADICAL = "diradical"
    BI_RADICAL = "biradical"


class IsotopeType(StrEnum):
    """Classification of isotopic labeling."""

    NATURAL = "natural"
    LABELED = "labeled"
    RADIOACTIVE = "radioactive"
    ENRICHED = "enriched"


class SpinMultiplicity(IntEnum):
    """Spin multiplicity of a molecule: 2S+1.

    Singlet = 1 (no unpaired electrons)
    Doublet = 2 (one unpaired electron)
    Triplet = 3 (two unpaired electrons, parallel spins)
    Quartet = 4 (three unpaired electrons)
    Quintet = 5 (four unpaired electrons)
    """

    SINGLET = 1
    DOUBLET = 2
    TRIPLET = 3
    QUARTET = 4
    QUINTET = 5
    SEXTET = 6
    SEPTET = 7
    OCTET = 8

    @classmethod
    def from_unpaired_electrons(cls, n: int) -> SpinMultiplicity:
        """Compute spin multiplicity from number of unpaired electrons."""
        return cls(n + 1)
