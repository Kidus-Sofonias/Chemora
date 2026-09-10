"""Atom domain model — Milestone 1.

This module defines the Atom dataclass, which represents a single atom in a
molecular graph. Every atom carries its element identity, isotopic information,
formal charge, radical state, valence, hybridization, stereochemistry,
coordinates, and extensible metadata.

The Atom is immutable (frozen=True, slots=True) for thread safety and
hashability. All mutations go through MolecularGraphBuilder.

Validation:
    - Atomic number must be 1-118
    - Formal charge must be within reasonable range (-10 to +10)
    - Radical electrons must be 0, 1, or 2
    - Implicit hydrogens must be non-negative if specified
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chemengine.core.element import Element
from chemengine.core.enums import ChiralTag, ElementSymbol, Hybridization, IsotopeType, RadicalType


@dataclass(frozen=True, slots=True)
class Isotope:
    """Isotopic information for an atom.

    Stores the mass number, exact mass, natural abundance, and classification
    of a specific isotope of an element.

    Attributes:
        mass_number: Total number of protons + neutrons (e.g., 13 for carbon-13).
        exact_mass: The exact atomic mass in daltons (u).
        abundance: Natural abundance as a fraction (0.0 to 1.0). 0.0 for
            radioactive or synthetic isotopes.
        isotope_type: Classification (natural, labeled, radioactive, enriched).

    Usage:
        >>> c13 = Isotope(mass_number=13, exact_mass=13.003355, abundance=0.0107)
        >>> c13.mass_number
        13
        >>> c13.isotope_type
        <IsotopeType.NATURAL: 'natural'>
    """

    mass_number: int
    exact_mass: float
    abundance: float = 0.0
    isotope_type: IsotopeType = IsotopeType.NATURAL

    def __post_init__(self) -> None:
        if not (0.0 <= self.abundance <= 1.0):
            raise ValueError(f"Abundance must be between 0.0 and 1.0, got {self.abundance}")
        if self.mass_number < 1:
            raise ValueError(f"Mass number must be >= 1, got {self.mass_number}")


@dataclass(frozen=True, slots=True)
class Atom:
    """A single atom in a molecular graph.

    This is the fundamental particle representation. Every atom in every
    molecule — organic, inorganic, organometallic, or biomolecular — is
    represented by this single class.

    Attributes:
        atomic_number: Atomic number Z (1-118). Determines the element.
        formal_charge: Formal charge on the atom (-10 to +10 typical).
        radical_electrons: Number of unpaired electrons (0, 1, or 2).
        isotope: Optional isotopic information. None = natural abundance.
        stereochemistry: Tetrahedral stereochemistry tag (R/S/r/s/none).
        hybridization: Orbital hybridization state (sp3, sp2, sp, etc.).
        valence: Explicit valence state. None = auto-compute from bonds.
        implicit_hydrogens: Number of implicit hydrogen atoms. None = auto-compute.
        atom_mapping: Atom-atom mapping number for reaction mapping.
        is_aromatic: Whether this atom is part of an aromatic system.
        properties: Extensible key-value metadata (frozen set of tuples).

    Usage:
        >>> carbon = Atom(atomic_number=6)
        >>> carbon.symbol
        'C'
        >>> carbon.formal_charge
        0

        >>> oxygen_radical = Atom(atomic_number=8, radical_electrons=1)
        >>> oxygen_radical.radical_type
        <RadicalType.MONORADICAL: 'monoradical'>
    """

    atomic_number: int
    formal_charge: int = 0
    radical_electrons: int = 0
    isotope: Isotope | None = None
    stereochemistry: ChiralTag = ChiralTag.NONE
    hybridization: Hybridization = Hybridization.UNKNOWN
    valence: int | None = None
    implicit_hydrogens: int | None = None
    atom_mapping: int | None = None
    is_aromatic: bool = False
    properties: frozenset[tuple[str, Any]] = frozenset()

    # ── Computed Properties ──

    @property
    def element(self) -> Element:
        """The Element object for this atom."""
        if self.atomic_number == 0:
            # Wildcard atom: return a minimal Element representation
            raise AttributeError("Wildcard atom (Z=0) has no Element")
        return Element.from_z(self.atomic_number)

    @property
    def symbol(self) -> str:
        """Element symbol string (e.g., 'C', 'Fe', '*' for wildcard)."""
        if self.atomic_number == 0:
            return "*"
        # Use cached property from element
        try:
            return self.element.symbol
        except (AttributeError, KeyError, ValueError):
            return "?"

    @property
    def element_symbol(self) -> ElementSymbol:
        """The ElementSymbol enum for this atom."""
        return ElementSymbol(self.symbol)

    @property
    def mass(self) -> float:
        """Atomic mass.

        Uses the explicit isotope exact mass if set; otherwise the
        monoisotopic mass (most abundant natural isotope). This keeps
        MolecularGraph.exact_mass a true monoisotopic mass while
        MolecularGraph.molecular_weight separately uses standard atomic
        weights (average).
        """
        if self.atomic_number == 0:
            return 0.0
        if self.isotope is not None:
            return self.isotope.exact_mass
        try:
            element = self.element
            most_abundant = element.most_abundant_isotope
            if most_abundant is not None:
                return most_abundant.exact_mass
            return element.atomic_mass
        except (AttributeError, KeyError, ValueError):
            return 0.0

    @property
    def is_metal(self) -> bool:
        """Whether this atom is a metal."""
        return self.element.is_metal

    @property
    def is_halogen(self) -> bool:
        """Whether this atom is a halogen (F, Cl, Br, I, At, Ts)."""
        return self.element.is_halogen

    @property
    def is_chalcogen(self) -> bool:
        """Whether this atom is a chalcogen (O, S, Se, Te, Po, Lv)."""
        return self.element.group == 16

    @property
    def is_pnictogen(self) -> bool:
        """Whether this atom is a pnictogen (N, P, As, Sb, Bi, Mc)."""
        return self.element.group == 15

    @property
    def is_hydrogen(self) -> bool:
        """Whether this atom is hydrogen."""
        return self.atomic_number == 1

    @property
    def is_carbon(self) -> bool:
        """Whether this atom is carbon."""
        return self.atomic_number == 6

    @property
    def is_nitrogen(self) -> bool:
        """Whether this atom is nitrogen."""
        return self.atomic_number == 7

    @property
    def is_oxygen(self) -> bool:
        """Whether this atom is oxygen."""
        return self.atomic_number == 8

    @property
    def is_sulfur(self) -> bool:
        """Whether this atom is sulfur."""
        return self.atomic_number == 16

    @property
    def is_phosphorus(self) -> bool:
        """Whether this atom is phosphorus."""
        return self.atomic_number == 15

    @property
    def default_valence(self) -> int:
        """Default valence for this element."""
        return self.element.default_valence

    @property
    def max_valence(self) -> int:
        """Maximum allowed valence for this element."""
        return self.element.max_valence

    @property
    def common_valences(self) -> tuple[int, ...]:
        """Common valence states for this element."""
        return self.element.common_valences

    @property
    def radical_type(self) -> RadicalType:
        """Radical classification based on unpaired electron count."""
        if self.radical_electrons == 0:
            return RadicalType.NONE
        if self.radical_electrons == 1:
            return RadicalType.MONORADICAL
        return RadicalType.DIRADICAL

    @property
    def has_isotope(self) -> bool:
        """Whether this atom has specified isotopic information."""
        return self.isotope is not None

    @property
    def is_charged(self) -> bool:
        """Whether this atom has a non-zero formal charge."""
        return self.formal_charge != 0

    @property
    def is_radical(self) -> bool:
        """Whether this atom has unpaired electrons."""
        return self.radical_electrons > 0

    # ── Immutable Update Methods ──

    def with_charge(self, charge: int) -> Atom:
        """Return a new Atom with the given formal charge (immutable)."""
        return Atom(
            atomic_number=self.atomic_number,
            formal_charge=charge,
            radical_electrons=self.radical_electrons,
            isotope=self.isotope,
            stereochemistry=self.stereochemistry,
            hybridization=self.hybridization,
            valence=self.valence,
            implicit_hydrogens=self.implicit_hydrogens,
            atom_mapping=self.atom_mapping,
            is_aromatic=self.is_aromatic,
            properties=self.properties,
        )

    def with_isotope(self, isotope: Isotope | None) -> Atom:
        """Return a new Atom with the given isotope info (immutable)."""
        return Atom(
            atomic_number=self.atomic_number,
            formal_charge=self.formal_charge,
            radical_electrons=self.radical_electrons,
            isotope=isotope,
            stereochemistry=self.stereochemistry,
            hybridization=self.hybridization,
            valence=self.valence,
            implicit_hydrogens=self.implicit_hydrogens,
            atom_mapping=self.atom_mapping,
            is_aromatic=self.is_aromatic,
            properties=self.properties,
        )

    def with_stereochemistry(self, stereo: ChiralTag) -> Atom:
        """Return a new Atom with the given stereochemistry (immutable)."""
        return Atom(
            atomic_number=self.atomic_number,
            formal_charge=self.formal_charge,
            radical_electrons=self.radical_electrons,
            isotope=self.isotope,
            stereochemistry=stereo,
            hybridization=self.hybridization,
            valence=self.valence,
            implicit_hydrogens=self.implicit_hydrogens,
            atom_mapping=self.atom_mapping,
            is_aromatic=self.is_aromatic,
            properties=self.properties,
        )

    def with_hybridization(self, hybridization: Hybridization) -> Atom:
        """Return a new Atom with the given hybridization state (immutable)."""
        return Atom(
            atomic_number=self.atomic_number,
            formal_charge=self.formal_charge,
            radical_electrons=self.radical_electrons,
            isotope=self.isotope,
            stereochemistry=self.stereochemistry,
            hybridization=hybridization,
            valence=self.valence,
            implicit_hydrogens=self.implicit_hydrogens,
            atom_mapping=self.atom_mapping,
            is_aromatic=self.is_aromatic,
            properties=self.properties,
        )

    def __post_init__(self) -> None:
        """Validate atom properties."""
        if not 0 <= self.atomic_number <= 118:
            if self.atomic_number != 0:
                raise ValueError(f"Atomic number must be 1-118, got {self.atomic_number}")
        if abs(self.formal_charge) > 10:
            raise ValueError(f"Formal charge out of range: {self.formal_charge}")
        if self.radical_electrons not in (0, 1, 2):
            raise ValueError(f"Radical electrons must be 0, 1, or 2, got {self.radical_electrons}")
        if self.implicit_hydrogens is not None and self.implicit_hydrogens < 0:
            raise ValueError(f"Implicit hydrogens must be >= 0, got {self.implicit_hydrogens}")
        if self.atomic_number > 0 and self.atomic_number == 2 and self.implicit_hydrogens is not None and self.implicit_hydrogens > 0:
            raise ValueError("Helium (Z=2) cannot have implicit hydrogens")

    def __repr__(self) -> str:
        parts = [f"Atom({self.symbol}"]
        if self.formal_charge != 0:
            parts.append(f"charge={self.formal_charge:+d}")
        if self.is_radical:
            parts.append(f"radical={self.radical_electrons}")
        if self.stereochemistry != ChiralTag.NONE:
            parts.append(f"stereo={self.stereochemistry.value}")
        if self.hybridization != Hybridization.UNKNOWN:
            parts.append(f"hyb={self.hybridization.value}")
        if self.isotope is not None:
            parts.append(f"iso={self.isotope.mass_number}")
        return " ".join(parts) + ")"
