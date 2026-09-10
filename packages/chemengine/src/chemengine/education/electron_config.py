"""Electron Configuration Generator — from first principles.

Generates electron configurations for any element using the
Aufbau principle, Hund's rule, and the Pauli exclusion principle.

No database lookups — configurations are COMPUTED from:
1. Atomic number Z
2. Orbital filling order (1s → 2s → 2p → 3s → 3p → 4s → 3d → 4p → ...)
3. Orbital capacity rules (s=2, p=6, d=10, f=14)

Usage:
    >>> from chemengine.education.electron_config import ElectronConfigurator
    >>> ec = ElectronConfigurator()
    >>> config = ec.configure(6)  # Carbon
    >>> print(config.shorthand)   # '[He] 2s2 2p2'
    >>> print(config.explain())   # Educational explanation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chemengine.core.element import Element

# Orbital filling order (Aufbau order)
# Energy levels determine the order in which orbitals are filled
ORBITAL_FILLING_ORDER: list[str] = [
    "1s", "2s", "2p", "3s", "3p", "4s",
    "3d", "4p", "5s", "4d", "5p", "6s",
    "4f", "5d", "6p", "7s", "5f", "6d", "7p",
]

# Noble gas electron configs (for shorthand notation)
NOBLE_GAS_CONFIGS: dict[int, tuple[str, int]] = {
    2: ("1s2", 2),           # He
    10: ("[Ne] 3s2 3p6", 10),  # Ne — but we'll build it
    18: ("[Ar]", 18),        # Ar
    36: ("[Kr]", 36),        # Kr
    54: ("[Xe]", 54),        # Xe
    86: ("[Rn]", 86),        # Rn
}

# Noble gas symbols by atomic number
NOBLE_GASES: dict[int, str] = {
    2: "He", 10: "Ne", 18: "Ar", 36: "Kr", 54: "Xe", 86: "Rn",
}

# Orbital capacities
ORBITAL_CAPACITY: dict[str, int] = {
    "s": 2, "p": 6, "d": 10, "f": 14,
}

# Angular momentum quantum number for each subshell type (used to order electron
# removal within a principal shell: higher l electrons are removed first).
_SUBSHELL_L: dict[str, int] = {"s": 0, "p": 1, "d": 2, "f": 3}

# Madelung-order position of each subshell (for deterministic electron addition).
_ORBITAL_INDEX: dict[str, int] = {
    orb: i for i, orb in enumerate(ORBITAL_FILLING_ORDER)
}

# Number of degenerate orbitals per subshell type (for Hund's-rule unpaired counts).
_ORBITALS_PER_SUBSHELL: dict[str, int] = {"s": 1, "p": 3, "d": 5, "f": 7}

# Neutral-atom ground-state exceptions to the strict Madelung (Aufbau) filling rule.
#
# These are the well-established d-block (transition-metal) exceptions, universally
# accepted in reference sources (NIST Atomic Spectra Database; standard inorganic
# chemistry references). For each element, only the valance (n-1)d / ns subshells are
# overridden; all inner subshells fill normally. This is deliberately NOT a full
# hardcoded lookup table — it is a small, explicitly-documented set of exceptions on
# top of the rule-driven Madelung filling. F-block (lanthanide/actinide) configurations
# are not overridden here; some f-block elements deviate from strict Aufbau in practice
# and those cases are left to the Madelung default rather than guessing a specific,
# contested ground state.
#
# Format: {atomic_number: {"<subshell>": <electrons>, ...}}
TRANSITION_METAL_EXCEPTIONS: dict[int, dict[str, int]] = {
    24: {"3d": 5, "4s": 1},   # Cr   [Ar]3d5 4s1
    29: {"3d": 10, "4s": 1},  # Cu   [Ar]3d10 4s1
    41: {"4d": 4, "5s": 1},   # Nb   [Kr]4d4 5s1
    42: {"4d": 5, "5s": 1},   # Mo   [Kr]4d5 5s1
    44: {"4d": 7, "5s": 1},   # Ru   [Kr]4d7 5s1
    45: {"4d": 8, "5s": 1},   # Rh   [Kr]4d8 5s1
    46: {"4d": 10, "5s": 0},  # Pd   [Kr]4d10
    47: {"4d": 10, "5s": 1},  # Ag   [Kr]4d10 5s1
    78: {"5d": 9, "6s": 1},   # Pt   [Xe]4f14 5d9 6s1
    79: {"5d": 10, "6s": 1},  # Au   [Xe]4f14 5d10 6s1
}


@dataclass(frozen=True, slots=True)
class OrbitalOccupancy:
    """Occupancy of a single orbital type (e.g., '2p' with 3 electrons).

    Attributes:
        orbital: Orbital label (e.g., '1s', '2p', '3d').
        electrons: Number of electrons in this orbital.
        capacity: Maximum capacity of this orbital.
        subshell: The subshell letter (s, p, d, f).
        shell: The principal quantum number (n).
    """
    orbital: str
    electrons: int
    capacity: int
    subshell: str = ""
    shell: int = 0

    def __post_init__(self) -> None:
        # Derive subshell and shell from orbital name
        if not self.subshell:
            object.__setattr__(self, 'subshell', self.orbital[-1])
        if not self.shell:
            object.__setattr__(self, 'shell', int(self.orbital[:-1]))

    @property
    def is_full(self) -> bool:
        return self.electrons >= self.capacity

    @property
    def is_empty(self) -> bool:
        return self.electrons == 0

    def __repr__(self) -> str:
        return f"{self.orbital}{self.electrons}"


@dataclass(frozen=True, slots=True)
class ElectronShell:
    """A complete electron shell (e.g., n=2 with 2s2 2p6).

    Attributes:
        n: Principal quantum number.
        orbitals: List of orbital occupancies in this shell.
        total_electrons: Total electrons in this shell.
    """
    n: int
    orbitals: tuple[OrbitalOccupancy, ...]
    total_electrons: int

    @property
    def subshell_notation(self) -> str:
        return " ".join(repr(o) for o in self.orbitals if o.electrons > 0)


@dataclass(frozen=True, slots=True)
class OrbitalDiagram:
    """Full orbital diagram with all occupied orbitals.

    Attributes:
        occupancies: List of all orbital occupancies.
        shells: List of electron shells.
        total_electrons: Total electrons.
    """
    occupancies: tuple[OrbitalOccupancy, ...]
    shells: tuple[ElectronShell, ...]
    total_electrons: int

    def __repr__(self) -> str:
        return " ".join(repr(o) for o in self.occupancies if o.electrons > 0)


@dataclass(frozen=True, slots=True)
class ElectronConfiguration:
    """Complete electron configuration for an element.

    Attributes:
        atomic_number: Atomic number Z.
        symbol: Element symbol.
        name: Element name.
        full: Full electron configuration (e.g., '1s2 2s2 2p2').
        shorthand: Noble gas shorthand (e.g., '[He] 2s2 2p2').
        noble_gas: The noble gas used in shorthand.
        diagram: Full orbital diagram.
        valence_electrons: Number of valence electrons.
        core_electrons: Number of core electrons.
    """
    atomic_number: int
    symbol: str
    name: str
    full: str
    shorthand: str
    noble_gas: str = ""
    diagram: OrbitalDiagram = field(default_factory=lambda: OrbitalDiagram((), (), 0))
    valence_electrons: int = 0
    core_electrons: int = 0
    charge: int = 0
    element: Element | None = None

    @property
    def shell_distribution(self) -> dict[int, int]:
        """Electrons per principal shell, e.g. {1: 2, 2: 8}."""
        return {
            s.n: s.total_electrons
            for s in self.diagram.shells
            if s.total_electrons > 0
        }

    @property
    def subshell_distribution(self) -> dict[str, int]:
        """Electrons per subshell, e.g. {'1s': 2, '2s': 2, '2p': 6}."""
        return {
            o.orbital: o.electrons
            for o in self.diagram.occupancies
            if o.electrons > 0
        }

    @property
    def unpaired_electrons(self) -> int:
        """Number of unpaired electrons via Hund's rule.

        Computed for the outermost partially-filled subshell, which is the
        standard approximation used by textbooks and reference tables. (It does
        not model full multi-subshell Hund's-coupling vector addition.)
        """
        for occ in reversed(self.diagram.occupancies):
            if 0 < occ.electrons < occ.capacity:
                orbitals = _ORBITALS_PER_SUBSHELL[occ.subshell]
                if occ.electrons <= orbitals:
                    return occ.electrons
                return 2 * orbitals - occ.electrons
        return 0

    @property
    def electron_type(self) -> str:
        """'cation', 'anion', or 'neutral' based on the net charge."""
        if self.charge > 0:
            return "cation"
        if self.charge < 0:
            return "anion"
        return "neutral"

    def explain(self) -> str:
        """Generate an educational explanation of this configuration."""
        lines: list[str] = []
        lines.append(f"Electron Configuration of {self.name} ({self.symbol}, Z={self.atomic_number})")
        lines.append("=" * 60)
        lines.append(f"Full configuration: {self.full}")
        lines.append(f"Shorthand: {self.shorthand}")
        lines.append(f"Valence electrons: {self.valence_electrons}")
        lines.append(f"Core electrons: {self.core_electrons}")
        lines.append("")

        # Explain orbital filling
        lines.append("Orbital Filling (Aufbau Principle):")
        lines.append("  Electrons fill orbitals from lowest to highest energy.")
        lines.append("  Order: 1s → 2s → 2p → 3s → 3p → 4s → 3d → 4p → ...")
        lines.append("")

        # Explain each occupied subshell
        for occ in self.diagram.occupancies:
            if occ.electrons > 0:
                shell_n = occ.shell
                sub = occ.subshell
                cap = occ.capacity
                lines.append(f"  {occ.orbital}: {occ.electrons}/{cap} electrons", )
                if sub == "s":
                    lines.append("    → s orbital: spherical, holds max 2 electrons")
                elif sub == "p":
                    lines.append("    → p orbital: dumbbell-shaped, holds max 6 electrons")
                elif sub == "d":
                    lines.append("    → d orbital: cloverleaf-shaped, holds max 10 electrons")
                elif sub == "f":
                    lines.append("    → f orbital: complex shapes, holds max 14 electrons")

                # Hund's rule explanation for partially filled
                if sub in ("p", "d", "f") and 0 < occ.electrons < cap:
                    lines.append("    → Hund's rule: electrons occupy degenerate orbitals singly first")
                    if occ.electrons <= 3:
                        lines.append(f"    → {occ.electrons} unpaired electron(s) — paramagnetic")
                    else:
                        lines.append("    → Some paired, some unpaired")
                elif occ.electrons == cap:
                    lines.append("    → Fully occupied")
                lines.append("")

        return "\n".join(lines)


class ElectronConfigurator:
    """Generate electron configurations from first principles.

    Uses the Aufbau principle, Hund's rule, and Pauli exclusion.

    Usage:
        >>> ec = ElectronConfigurator()
        >>> config = ec.configure(6)  # Carbon
        >>> print(config.shorthand)   # '[He] 2s2 2p2'
    """

    def configure(
        self,
        atomic_number: int | None = None,
        *,
        symbol: str | None = None,
        name: str | None = None,
        charge: int = 0,
    ) -> ElectronConfiguration:
        """Generate the electron configuration for an element or ion.

        Configurations are computed by the rule-driven Madelung (Aufbau) filling
        rule with a small, explicitly-documented set of transition-metal ground-state
        exceptions. Net charges are honoured by removing electrons (cations, from the
        highest principal shell first) or adding electrons (anions, to the next
        available subshell in Madelung order).

        Args:
            atomic_number: Atomic number Z (1-118). Provide exactly one of
                `atomic_number`, `symbol`, or `name`.
            symbol: Element symbol (e.g. 'Fe'). Mutually exclusive with `atomic_number`.
            name: Element name (e.g. 'Iron'). Mutually exclusive with `atomic_number`.
            charge: Net charge. Positive removes electrons (cation), negative adds
                electrons (anion). Defaults to 0 (neutral).

        Returns:
            ElectronConfiguration with full, shorthand, diagram, and distributions.

        Raises:
            ValueError: If no element identifier is given, identifiers conflict, or
                the request is outside the supported range.
        """
        atomic_number = self._resolve_z(atomic_number, symbol, name)
        element = Element.from_z(atomic_number)
        symbol_val = element.symbol
        name_val = element.name

        # Neutral-atom occupancy (rule-driven Madelung + documented exceptions)
        neutral = self._neutral_occupancies(atomic_number)
        # Apply the net charge to produce the ionic occupancy
        occupancies = self._apply_charge(neutral, charge)
        # Drop empty subshells for a clean representation (e.g. Pd ['']5s0).
        occupancies = [o for o in occupancies if o.electrons > 0]
        # Present in standard spectroscopic notation: (n-1)d before ns, i.e. sort
        # by principal shell then angular momentum (e.g. Fe -> [Ar]3d6 4s2).
        occupancies.sort(key=lambda o: (o.shell, _SUBSHELL_L[o.subshell]))
        total_electrons = sum(o.electrons for o in occupancies)

        # Build full configuration string
        full_parts = [repr(o) for o in occupancies if o.electrons > 0]
        full = " ".join(full_parts)

        # Build noble gas shorthand
        shorthand, noble_gas = self._build_shorthand(occupancies, atomic_number)

        # Build shell structure
        shells = self._build_shells(occupancies)

        # Build orbital diagram
        diagram = OrbitalDiagram(
            occupancies=tuple(occupancies),
            shells=tuple(shells),
            total_electrons=total_electrons,
        )

        # Compute valence and core electrons
        valence, core = self._count_valence_core(occupancies, element)

        return ElectronConfiguration(
            atomic_number=atomic_number,
            symbol=symbol_val,
            name=name_val,
            full=full,
            shorthand=shorthand,
            noble_gas=noble_gas,
            diagram=diagram,
            valence_electrons=valence,
            core_electrons=core,
            charge=charge,
            element=element,
        )

    def for_element(self, element: str | Element, *, charge: int = 0) -> ElectronConfiguration:
        """Generate the electron configuration for an element (by symbol or object).

        Args:
            element: An Element object or an element symbol string (e.g. 'C', 'Fe').
            charge: Net charge (see :meth:`configure`).

        Returns:
            ElectronConfiguration for the element/ion.
        """
        if isinstance(element, Element):
            return self.configure(element.atomic_number, charge=charge)
        return self.configure(symbol=str(element), charge=charge)

    def _resolve_z(self, atomic_number: int | None, symbol: str | None, name: str | None) -> int:
        """Resolve an element identifier (mutually-exclusive) to an atomic number."""
        provided = [
            id_ for id_ in (atomic_number is not None, symbol is not None, name is not None) if id_
        ]
        if not provided:
            raise ValueError("Provide one of atomic_number, symbol, or name.")
        if len(provided) > 1:
            raise ValueError("Provide exactly one of atomic_number, symbol, or name.")
        if atomic_number is not None:
            if atomic_number < 1 or atomic_number > 118:
                raise ValueError(f"Invalid atomic number: {atomic_number}")
            return int(atomic_number)
        if symbol is not None:
            return Element.from_symbol(str(symbol)).atomic_number
        if name is not None:
            return Element.from_name(str(name)).atomic_number
        raise ValueError("Unable to resolve element identifier.")

    def _neutral_occupancies(self, z: int) -> list[OrbitalOccupancy]:
        """Fill orbitals using the Madelung (Aufbau) rule plus d-block exceptions.

        Returns a list of OrbitalOccupancy for each subshell, in Madelung order.
        """
        remaining = z
        occupancies: list[OrbitalOccupancy] = []
        exceptions = TRANSITION_METAL_EXCEPTIONS.get(z, {})

        for orbital in ORBITAL_FILLING_ORDER:
            if remaining <= 0:
                break

            subshell = orbital[-1]
            capacity = ORBITAL_CAPACITY[subshell]

            if orbital in exceptions:
                electrons = exceptions[orbital]
                if electrons < 0 or electrons > capacity:
                    raise ValueError(
                        f"Invalid exception occupancy {orbital}={electrons} for Z={z}"
                    )
            else:
                electrons = min(remaining, capacity)

            occupancies.append(OrbitalOccupancy(
                orbital=orbital,
                electrons=electrons,
                capacity=capacity,
                subshell=subshell,
                shell=int(orbital[:-1]),
            ))
            remaining -= electrons

        return occupancies

    def _apply_charge(
        self, occupancies: list[OrbitalOccupancy], charge: int
    ) -> list[OrbitalOccupancy]:
        """Add (anion) or remove (cation) electrons to model a charged species.

        Cations: electrons are removed one at a time from the outermost principal
        shell first, and within a shell from the higher-l (higher-energy) subshell
        first (e.g. p before s; valence ns before (n-1)d). This reproduces the
        standard transition-metal rule that ns electrons are lost before (n-1)d.

        Anions: electrons are added one at a time to the first subshell in Madelung
        order that is not yet full.

        Args:
            occupancies: The neutral-atom subshell occupancies.
            charge: Net charge to apply.

        Returns:
            Updated occupancies (subshells emptied by cation formation are dropped).
        """
        if charge == 0:
            return occupancies

        occ: list[OrbitalOccupancy] = [
            OrbitalOccupancy(o.orbital, o.electrons, o.capacity, o.subshell, o.shell)
            for o in occupancies
        ]

        if charge > 0:
            for _ in range(charge):
                occ = self._remove_electron(occ)
        else:
            for _ in range(-charge):
                occ = self._add_electron(occ)

        # Drop emptied subshells for a clean, standard representation.
        return [o for o in occ if o.electrons > 0]

    def _remove_electron(self, occ: list[OrbitalOccupancy]) -> list[OrbitalOccupancy]:
        """Remove a single electron from the most loosely bound occupied subshell."""
        if not occ:
            raise ValueError("Cannot remove electrons: the species has no electrons.")
        occupied = [i for i, o in enumerate(occ) if o.electrons > 0]
        if not occupied:
            raise ValueError("Cannot remove electrons: the species has no electrons.")
        target = max(
            occupied,
            key=lambda i: (occ[i].shell, _SUBSHELL_L[occ[i].subshell]),
        )
        result: list[OrbitalOccupancy] = []
        for i, o in enumerate(occ):
            electrons = o.electrons - 1 if i == target else o.electrons
            result.append(
                OrbitalOccupancy(o.orbital, electrons, o.capacity, o.subshell, o.shell)
            )
        return result

    def _add_electron(self, occ: list[OrbitalOccupancy]) -> list[OrbitalOccupancy]:
        """Add a single electron to the first Madelung-order subshell that is not full."""
        by_order = sorted(occ, key=lambda o: _ORBITAL_INDEX[o.orbital])
        for o in by_order:
            if o.electrons < o.capacity:
                result: list[OrbitalOccupancy] = []
                for existing in occ:
                    electrons = (
                        existing.electrons + 1
                        if existing.orbital == o.orbital
                        else existing.electrons
                    )
                    result.append(
                        OrbitalOccupancy(
                            existing.orbital,
                            electrons,
                            existing.capacity,
                            existing.subshell,
                            existing.shell,
                        )
                    )
                return result

        # All subshells present are full: open the next Madelung-order subshell.
        present = {o.orbital for o in occ}
        frontier: str | None = None
        for orbital in ORBITAL_FILLING_ORDER:
            if orbital not in present:
                frontier = orbital
                break
        if frontier is None:
            raise ValueError("Cannot add electrons: all known subshells are full.")
        subshell = frontier[-1]
        return occ + [
            OrbitalOccupancy(
                orbital=frontier,
                electrons=1,
                capacity=ORBITAL_CAPACITY[subshell],
                subshell=subshell,
                shell=int(frontier[:-1]),
            )
        ]

    def _build_shorthand(
        self, occupancies: list[OrbitalOccupancy], z: int
    ) -> tuple[str, str]:
        """Build noble gas shorthand notation."""
        # Find the last noble gas before this element
        noble_gas_z = 0
        noble_gas_symbol = ""
        for ng_z, ng_sym in sorted(NOBLE_GASES.items()):
            if ng_z < z:
                noble_gas_z = ng_z
                noble_gas_symbol = ng_sym

        if noble_gas_z == 0:
            # Hydrogen or Helium — no shorthand
            parts = [repr(o) for o in occupancies if o.electrons > 0]
            return " ".join(parts), ""

        # Build shorthand: [NobleGas] remaining orbitals
        remaining_electrons = z - noble_gas_z
        remaining_parts: list[str] = []
        core_accounted = 0

        for occ in occupancies:
            # Skip orbitals fully consumed by the noble gas core
            if core_accounted < noble_gas_z:
                orbital_electrons = occ.electrons
                if core_accounted + orbital_electrons <= noble_gas_z:
                    core_accounted += orbital_electrons
                    continue
                else:
                    # This orbital is partially core, partially valence
                    # shouldn't happen with Aufbau, but handle it
                    core_accounted += orbital_electrons
                    continue

            # We're past the core — these are valence orbitals
            if remaining_electrons <= 0:
                break
            if occ.electrons <= remaining_electrons:
                remaining_parts.append(repr(occ))
                remaining_electrons -= occ.electrons
            else:
                remaining_parts.append(f"{occ.orbital}{remaining_electrons}")
                remaining_electrons = 0

        shorthand = f"[{noble_gas_symbol}] {' '.join(remaining_parts)}".strip()
        return shorthand, noble_gas_symbol

    def _build_shells(self, occupancies: list[OrbitalOccupancy]) -> list[ElectronShell]:
        """Group occupancies by principal quantum number into shells."""
        shell_dict: dict[int, list[OrbitalOccupancy]] = {}
        for occ in occupancies:
            n = occ.shell
            if n not in shell_dict:
                shell_dict[n] = []
            shell_dict[n].append(occ)

        shells: list[ElectronShell] = []
        for n in sorted(shell_dict.keys()):
            orbitals = shell_dict[n]
            total = sum(o.electrons for o in orbitals)
            shells.append(ElectronShell(
                n=n,
                orbitals=tuple(orbitals),
                total_electrons=total,
            ))
        return shells

    def _count_valence_core(
        self, occupancies: list[OrbitalOccupancy], element: Element
    ) -> tuple[int, int]:
        """Count valence and core electrons.

        Valence electrons = electrons in the outermost shell.
        Core electrons = total - valence.
        """
        if not occupancies:
            return 0, 0

        # Find the highest principal quantum number
        max_n = max(o.shell for o in occupancies)

        # Valence = electrons in the highest shell
        # For transition metals, also include (n-1)d electrons
        valence = 0
        for occ in occupancies:
            if occ.shell == max_n:
                valence += occ.electrons
            # Include d electrons for transition metals
            elif occ.subshell == "d" and occ.shell == max_n - 1:
                if element.is_transition_metal:
                    valence += occ.electrons

        total = sum(o.electrons for o in occupancies)
        core = total - valence

        return valence, core


def calculate_electron_configuration(
    element: str | int | Element, *, charge: int = 0
) -> ElectronConfiguration:
    """Generate an electron configuration for an element or ion (AI-facing).

    Thin facade over :class:`ElectronConfigurator` for direct/AI integration.

    Args:
        element: Element symbol (e.g. 'Fe'), atomic number (e.g. 26), or Element.
        charge: Net charge (positive = cation, negative = anion).

    Returns:
        ElectronConfiguration.

    Raises:
        ValueError: If the element identifier cannot be resolved.
    """
    configurator = ElectronConfigurator()
    if isinstance(element, Element):
        return configurator.for_element(element, charge=charge)
    if isinstance(element, str):
        return configurator.configure(symbol=element, charge=charge)
    return configurator.configure(atomic_number=int(element), charge=charge)


def _electron_config_to_dict(config: ElectronConfiguration) -> dict[str, Any]:
    """Serialize an ElectronConfiguration to a machine-readable dict."""
    return {
        "atomic_number": config.atomic_number,
        "symbol": config.symbol,
        "name": config.name,
        "charge": config.charge,
        "electron_type": config.electron_type,
        "full": config.full,
        "shorthand": config.shorthand,
        "noble_gas": config.noble_gas,
        "valence_electrons": config.valence_electrons,
        "core_electrons": config.core_electrons,
        "unpaired_electrons": config.unpaired_electrons,
        "shell_distribution": config.shell_distribution,
        "subshell_distribution": config.subshell_distribution,
        "total_electrons": sum(config.shell_distribution.values()),
    }


def register_electron_config_algorithm(registry: Any) -> None:
    """Register the electron-configuration algorithm with an AlgorithmRegistry."""
    from chemengine.core.registry import AlgorithmEntry

    registry.register(
        AlgorithmEntry(
            domain="education.electron_config",
            name="default",
            version="1.1.0",
            algorithm=calculate_electron_configuration,
            tags=frozenset({"atomic", "electrons", "deterministic"}),
            metadata=frozenset({
                ("rule", "Madelung/Aufbau + documented d-block exceptions"),
                ("ions", "charge parameter supported"),
                ("version", "1.1.0"),
            }),
        )
    )
