"""Charge and electron configuration models — Milestone 1.

This module defines data structures for representing formal charges,
radical electrons, and electron configurations on atoms and molecules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Charge:
    """A formal charge on an atom.

    Attributes:
        value: The formal charge value (-10 to +10 typical).
        atom_index: The index of the atom this charge belongs to.
    """

    value: int
    atom_index: int

    @property
    def is_positive(self) -> bool:
        return self.value > 0

    @property
    def is_negative(self) -> bool:
        return self.value < 0

    @property
    def is_neutral(self) -> bool:
        return self.value == 0

    @property
    def sign(self) -> int:
        if self.value > 0:
            return 1
        if self.value < 0:
            return -1
        return 0

    def __post_init__(self) -> None:
        if abs(self.value) > 10:
            raise ValueError(f"Charge out of reasonable range: {self.value}")


@dataclass(frozen=True, slots=True)
class ElectronConfiguration:
    """Electron configuration for an atom or molecule.

    Attributes:
        configuration: String representation (e.g., '[He]2s2 2p2' for carbon).
        num_electrons: Total number of electrons.
        valence_electrons: Number of valence electrons.
        unpaired_electrons: Number of unpaired electrons.
    """

    configuration: str
    num_electrons: int = 0
    valence_electrons: int = 0
    unpaired_electrons: int = 0

    @property
    def is_closed_shell(self) -> bool:
        """Whether this configuration has no unpaired electrons."""
        return self.unpaired_electrons == 0

    @property
    def is_open_shell(self) -> bool:
        """Whether this configuration has unpaired electrons."""
        return self.unpaired_electrons > 0


@dataclass(frozen=True, slots=True)
class ChargeDistribution:
    """Complete charge distribution for a molecular graph.

    Attributes:
        total_charge: Sum of all formal charges.
        formal_charges: All formal charges in the molecule.
        total_radical_electrons: Sum of all radical electrons.
    """

    total_charge: int = 0
    formal_charges: tuple[Charge, ...] = ()
    total_radical_electrons: int = 0

    @property
    def is_neutral(self) -> bool:
        return self.total_charge == 0

    @property
    def is_radical_species(self) -> bool:
        return self.total_radical_electrons > 0

    @property
    def num_charged_atoms(self) -> int:
        return sum(1 for c in self.formal_charges if c.value != 0)
