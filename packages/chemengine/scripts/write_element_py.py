#!/usr/bin/env python3
"""Write the refactored element.py file."""
import os
from pathlib import Path

content = r'''"""
Element - periodic table element with full properties.

This module provides the Element class, which encapsulates all known
properties of a chemical element: atomic number, symbol, name, mass,
radius, electronegativity, valence states, periodic table position,
physical properties, and isotopic data.

The Element class is the authoritative source for element data. It
replaces raw atomic_number lookups with a rich object that carries
all element metadata.

Design:
    - Immutable frozen dataclass
    - All 118 elements pre-loaded from the datasets/elements.json file
    - Lookup by symbol, atomic number, or name
    - Strongly typed ElementQuery API for filtering
    - Falls back to built-in data if the dataset file is unavailable
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Iterator

from chemengine.core.datasets import get_global_dataset_registry
from chemengine.core.enums import ElementSymbol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IsotopeInfo:
    """Isotopic information for an element.

    Attributes:
        mass_number: Mass number A (protons + neutrons).
        exact_mass: Exact atomic mass in daltons.
        natural_abundance: Natural abundance as a decimal (0-1), or None if radioactive/trace.
    """
    mass_number: int
    exact_mass: float
    natural_abundance: float | None


@dataclass(frozen=True, slots=True)
class Element:
    """A chemical element from the periodic table.

    All data originates from the centralized datasets/elements.json file.
    """
    symbol: str
    atomic_number: int
    name: str
    atomic_mass: float
    period: int
    group: int
    block: str
    category: str
    electron_configuration: str
    oxidation_states: tuple[int, ...]
    covalent_radius: float
    vdw_radius: float
    electronegativity: float
    ionization_energy: float
    electron_affinity: float
    density: float
    melting_point: float
    boiling_point: float
    phase_at_stp: str
    isotopes: tuple[IsotopeInfo, ...]

    @property
    def van_der_waals_radius(self) -> float:
        return self.vdw_radius

    @property
    def common_valences(self) -> tuple[int, ...]:
        return self.oxidation_states

    @cached_property
    def max_valence(self) -> int:
        if not self.oxidation_states:
            return 0
        return max(abs(v) for v in self.oxidation_states)

    @property
    def element_symbol(self) -> ElementSymbol:
        return ElementSymbol(self.symbol)

    @property
    def is_metal(self) -> bool:
        return self.category in ("alkali_metal", "alkaline_earth", "transition_metal", "post_transition_metal", "lanthanide", "actinide")

    @property
    def is_nonmetal(self) -> bool:
        return self.category == "nonmetal"

    @property
    def is_metalloid(self) -> bool:
        return self.category == "metalloid"

    @property
    def is_halogen(self) -> bool:
        return self.group == 17

    @property
    def is_noble_gas(self) -> bool:
        return self.group == 18

    @property
    def is_transition_metal(self) -> bool:
        return 3 <= self.group <= 12

    @property
    def is_lanthanide(self) -> bool:
        return 57 <= self.atomic_number <= 71

    @property
    def is_actinide(self) -> bool:
        return 89 <= self.atomic_number <= 103

    @property
    def is_radioactive(self) -> bool:
        return all(iso.natural_abundance is None for iso in self.isotopes)

    @property
    def has_stable_isotopes(self) -> bool:
        return any(iso.natural_abundance is not None for iso in self.isotopes)

    @property
    def most_abundant_isotope(self) -> IsotopeInfo | None:
        stable = [iso for iso in self.isotopes if iso.natural_abundance is not None]
        if not stable:
            return None
        return max(stable, key=lambda x: x.natural_abundance or 0.0)

    @classmethod
    def get(cls, identifier: str | int | ElementSymbol) -> Element:
        if isinstance(identifier, ElementSymbol):
            return _ELEMENTS_BY_SYMBOL[identifier.value]
        if isinstance(identifier, int):
            return _ELEMENTS_BY_Z[identifier]
        if isinstance(identifier, str):
            return _ELEMENTS_BY_SYMBOL[identifier]
        raise KeyError(f"Invalid element identifier: {identifier}")

    @classmethod
    def from_z(cls, z: int) -> Element:
        if z < 1 or z > 118:
            raise ValueError(f"Invalid atomic number: {z}")
        return _ELEMENTS_BY_Z[z]

    @classmethod
    def from_symbol(cls, symbol: str) -> Element:
        return _ELEMENTS_BY_SYMBOL[symbol]

    @classmethod
    def from_name(cls, name: str) -> Element:
        key = name.lower()
        if key not in _ELEMENTS_BY_NAME:
            raise KeyError(f"Element not found: '{name}'")
        return _ELEMENTS_BY_NAME[key]

    @classmethod
    def all_elements(cls) -> tuple[Element, ...]:
        return tuple(_ELEMENTS_BY_Z.values())

    @classmethod
    def filter(cls, **filters: Any) -> ElementQuery:
        query = ElementQuery()
        for key, value in filters.items():
            query = query.filter(**{key: value})
        return query

    def __repr__(self) -> str:
        return f"Element({self.symbol}, Z={self.atomic_number}, '{self.name}')"


class ElementQuery:
    """Query API for filtering the periodic table."""

    def __init__(self) -> None:
        self._filters: list[Callable[[Element], bool]] = []

    def filter(self, **kwargs: Any) -> ElementQuery:
        for key, value in kwargs.items():
            predicate = self._make_predicate(key, value)
            if predicate is not None:
                self._filters.append(predicate)
        return self

    def execute(self) -> list[Element]:
        if not self._filters:
            return list(_ELEMENTS_BY_Z.values())
        return [el for el in _ELEMENTS_BY_Z.values() if all(f(el) for f in self._filters)]

    def __iter__(self) -> Iterator[Element]:
        return iter(self.execute())

    def __len__(self) -> int:
        return len(self.execute())

    def __getitem__(self, index: int) -> Element:
        return self.execute()[index]

    def _make_predicate(self, key: str, value: Any) -> Callable[[Element], bool] | None:
        pred_map = {
            "period": lambda el, v: el.period == v,
            "group": lambda el, v: el.group == v,
            "block": lambda el, v: el.block == v,
            "category": lambda el, v: el.category == v,
            "phase_at_stp": lambda el, v: el.phase_at_stp == v,
            "is_metal": lambda el, v: el.is_metal == v,
            "is_nonmetal": lambda el, v: el.is_nonmetal == v,
            "is_metalloid": lambda el, v: el.is_metalloid == v,
            "is_halogen": lambda el, v: el.is_halogen == v,
            "is_noble_gas": lambda el, v: el.is_noble_gas == v,
            "is_transition_metal": lambda el, v: el.is_transition_metal == v,
            "is_lanthanide": lambda el, v: el.is_lanthanide == v,
            "is_actinide": lambda el, v: el.is_actinide == v,
            "is_radioactive": lambda el, v: el.is_radioactive == v,
            "has_stable_isotopes": lambda el, v: el.has_stable_isotopes == v,
            "z": lambda el, v: el.atomic_number == v,
            "symbol": lambda el, v: el.symbol == v,
            "name": lambda el, v: el.name.lower() == v.lower(),
        }
        range_map = {
            "min_electronegativity": ("electronegativity", True),
            "max_electronegativity": ("electronegativity", False),
            "min_ionization_energy": ("ionization_energy", True),
            "max_ionization_energy": ("ionization_energy", False),
            "min_atomic_mass": ("atomic_mass", True),
            "max_atomic_mass": ("atomic_mass", False),
            "min_density": ("density", True),
            "max_density": ("density", False),
            "min_melting_point": ("melting_point", True),
            "max_melting_point": ("melting_point", False),
            "min_boiling_point": ("boiling_point", True),
            "max_boiling_point": ("boiling_point", False),
        }
        if key in pred_map:
            fn = pred_map[key]
            return lambda el, v=value, f=fn: f(el, v)
        if key in range_map:
            attr, is_min = range_map[key]
            if is_min:
                return lambda el, v=value, a=attr: getattr(el, a) >= v
            else:
                return lambda el, v=value, a=attr: getattr(el, a) <= v
        logger.warning(f"Unknown filter key: '{key}' (ignored)")
        return None


def _load_elements_from_registry() -> dict[int, dict[str, Any]]:
    try:
        registry = get_global_dataset_registry()
        ds = registry.get("elements")
        raw = ds.data
        result: dict[int, dict[str, Any]] = {}
        for sym, entry in raw.items():
            if sym.startswith("_"):
                continue
            z = int(entry["z"])
            result[z] = entry
        return result
    except (FileNotFoundError, KeyError, Exception) as e:
        logger.warning(f"Could not load elements from registry: {e}")
        return {}


_FALLBACK_DATA: list[dict[str, Any]] = [
    {"symbol": "H", "z": 1, "name": "Hydrogen", "mass": 1.008, "period": 1, "group": 1, "block": "s", "cat": "nonmetal", "config": "1s1", "ox": (-1, 1), "cov_r": 0.31, "vdw_r": 1.20, "en": 2.20, "ie": 13.598, "ea": 0.754, "density": 0.00008988, "mp": 14.01, "bp": 20.28, "phase": "gas", "isotopes": [(1, 1.007825, 0.999885), (2, 2.014102, 0.000115), (3, 3.016049, None)]},
    {"symbol": "He", "z": 2, "name": "Helium", "mass": 4.002602, "period": 1, "group": 18, "block": "s", "cat": "noble_gas", "config": "1s2", "ox": (0,), "cov_r": 0.28, "vdw_r": 1.40, "en": 0.0, "ie": 24.587, "ea": 0.0, "density": 0.0001785, "mp": 0.95, "bp": 4.22, "phase": "gas", "isotopes": [(3, 3.016029, 0.00000134), (4, 4.002603, 0.99999866)]},
    {"symbol": "Li", "z": 3, "name": "Lithium", "mass": 6.94, "period": 2, "group": 1, "block": "s", "cat": "alkali_metal", "config": "[He]2s1", "ox": (1,), "cov_r": 1.28, "vdw_r": 1.82, "en": 0.98, "ie": 5.392, "ea": 0.618, "density": 0.534, "mp": 453.69, "bp": 1615.0, "phase": "solid", "isotopes": [(6, 6.015122, 0.0759), (7, 7.016004, 0.9241)]},
    {"symbol": "Be", "z": 4, "name": "Beryllium", "mass": 9.0121831, "period": 2, "group": 2, "block": "s", "cat": "alkaline_earth", "config": "[He]2s2", "ox": (2,), "cov_r": 0.96, "vdw_r": 1.53, "en": 1.57, "ie": 9.323, "ea": 0.0, "density": 1.848, "mp": 1560.0, "bp": 2744.0, "phase": "solid", "isotopes": [(9, 9.012183, 1.0)]},
    {"symbol": "B", "z": 5, "name": "Boron", "mass": 10.81, "period": 2, "group": 13, "block": "p", "cat": "metalloid", "config": "[He]2s2 2p1", "ox": (1, 3), "cov_r": 0.84, "vdw_r": 1.92, "en": 2.04, "ie": 8.298, "ea": 0.277, "density": 2.34, "mp": 2349.0, "bp": 4200.0, "phase": "solid", "isotopes": [(10, 10.012937, 0.199), (11, 11.009305, 0.801)]},
    {"symbol": "C", "z": 6, "name": "Carbon", "mass": 12.011, "period": 2, "group": 14, "block": "p", "cat": "nonmetal", "config": "[He]2s2 2p2", "ox": (-4, -3, -2, -1, 1, 2, 3, 4), "cov_r": 0.76, "vdw_r": 1.70, "en": 2.55, "ie": 11.260, "ea": 1.263, "density": 2.267, "mp": 3823.0, "bp": 4300.0, "phase": "solid", "isotopes": [(12, 12.000000, 0.9893), (13, 13.003355, 0.0107), (14, 14.003242, None)]},
    {"symbol": "N", "z": 7, "name": "Nitrogen", "mass": 14.007, "period": 2, "group": 15, "block": "p", "cat": "nonmetal", "config": "[He]2s2 2p3", "ox": (-3, -2, -1, 1, 2, 3, 4, 5), "cov_r": 0.71, "vdw_r": 1.55, "en": 3.04, "ie": 14.534, "ea": 0.0, "density": 0.001251, "mp": 63.15, "bp": 77.36, "phase": "gas", "isotopes": [(14, 14.003074, 0.99636), (15, 15.000109, 0.00364)]},
    {"symbol": "O", "z": 8, "name": "Oxygen", "mass": 15.999, "period": 2, "group": 16, "block": "p", "cat": "nonmetal", "config": "[He]2s2 2p4", "ox": (-2, -1, 1, 2), "cov_r": 0.66, "vdw_r": 1.52, "en": 3.44, "ie": 13.618, "ea": 1.461, "density": 0.001429, "mp": 54.36, "bp": 90.20, "phase": "gas", "isotopes": [(16, 15.994915, 0.99757), (17, 16.999132, 0.00038), (18, 17.999161, 0.00205)]},
    {"symbol": "Fe", "z": 26, "name": "Iron", "mass": 55.845, "period": 4, "group": 8, "block": "d", "cat": "transition_metal", "config": "[Ar]3d6 4s2", "ox": (-4, -2, -1, 1, 2, 3, 4, 5, 6), "cov_r": 1.32, "vdw_r": 2.04, "en": 1.83, "ie": 7.902, "ea": 0.153, "density": 7.874, "mp": 1811.0, "bp": 3134.0, "phase": "solid", "isotopes": [(54, 53.939609, 0.05845), (56, 55.934936, 0.91754), (57, 56.935393, 0.02119), (58, 57.933274, 0.00282)]},
    {"symbol": "Au", "z": 79, "name": "Gold", "mass": 196.96657, "period": 6, "group": 11, "block": "d", "cat": "transition_metal", "config": "[Xe]4f14 5d10 6s1", "ox": (-3, -2, -1, 1, 2, 3, 5), "cov_r": 1.36, "vdw_r": 1.66, "en": 2.54, "ie": 9.226, "ea": 2.309, "density": 19.282, "mp": 1337.33, "bp": 3243.0, "phase": "solid", "isotopes": [(197, 196.966569, 1.0)]},
    {"symbol": "U", "z": 92, "name": "Uranium", "mass": 238.02891, "period": 7, "group": 3, "block": "f", "cat": "actinide", "config": "[Rn]5f3 6d1 7s2", "ox": (-1, 1, 2, 3, 4, 5, 6), "cov_r": 1.18, "vdw_r": 1.86, "en": 1.38, "ie": 6.194, "ea": 0.5, "density": 19.05, "mp": 1408.0, "bp": 4200.0, "phase": "solid", "isotopes": [(234, 234.040952, 0.000055), (235, 235.043930, 0.00720), (238, 238.050788, 0.992745)]},
]


def _build_elements() -> tuple[dict[int, Element], dict[str, Element], dict[str, Element]]:
    by_z: dict[int, Element] = {}
    by_symbol: dict[str, Element] = {}
    by_name: dict[str, Element] = {}
    registry_data = _load_elements_from_registry()
    used_fallback = False
    if registry_data:
        for z, entry in registry_data.items():
            isotopes = tuple(
                IsotopeInfo(mass_number=iso["mass_number"], exact_mass=iso["mass"], natural_abundance=iso["abundance"])
                for iso in entry.get("isotopes", [])
            )
            el = Element(symbol=entry["symbol"], atomic_number=entry["z"], name=entry["name"], atomic_mass=entry["atomic_mass"],
                period=entry.get("period", 0), group=entry.get("group", 0), block=entry.get("block", "unknown"),
                category=entry["category"], electron_configuration=entry.get("electron_configuration", ""),
                oxidation_states=tuple(entry.get("oxidation_states", [])),
                covalent_radius=entry.get("covalent_radius", 0.0), vdw_radius=entry.get("vdw_radius", 0.0),
                electronegativity=entry.get("electronegativity", 0.0), ionization_energy=entry.get("ionization_energy", 0.0),
                electron_affinity=entry.get("electron_affinity", 0.0), density=entry.get("density", 0.0),
                melting_point=entry.get("melting_point", 0.0), boiling_point=entry.get("boiling_point", 0.0),
                phase_at_stp=entry.get("phase_at_stp", "unknown"), isotopes=isotopes)
            by_z[z] = el
            by_symbol[el.symbol] = el
            by_name[el.name.lower()] = el
    else:
        used_fallback = True
        for ed in _FALLBACK_DATA:
            isotopes = tuple(IsotopeInfo(mass_number=mn, exact_mass=em, natural_abundance=ab)
                for mn, em, ab in ed.get("isotopes", []))
            el = Element(symbol=ed["symbol"], atomic_number=ed["z"], name=ed["name"], atomic_mass=ed["mass"],
                period=ed.get("period", 0), group=ed.get("group", 0), block=ed.get("block", "unknown"),
                category=ed.get("cat", "unknown"), electron_configuration=ed.get("config", ""),
                oxidation_states=tuple(ed.get("ox", [])),
                covalent_radius=ed.get("cov_r", 0.0), vdw_radius=ed.get("vdw_r", 0.0),
                electronegativity=ed.get("en", 0.0), ionization_energy=ed.get("ie", 0.0),
                electron_affinity=ed.get("ea", 0.0), density=ed.get("density", 0.0),
                melting_point=ed.get("mp", 0.0), boiling_point=ed.get("bp", 0.0),
                phase_at_stp=ed.get("phase", "unknown"), isotopes=isotopes)
            by_z[el.atomic_number] = el
            by_symbol[el.symbol] = el
            by_name[el.name.lower()] = el
    if used_fallback:
        logger.info("Element registry loaded from built-in fallback data (9 elements)")
    else:
        logger.info(f"Element registry loaded from dataset ({len(by_z)} elements)")
    return by_z, by_symbol, by_name


_ELEMENTS_BY_Z: dict[int, Element]
_ELEMENTS_BY_SYMBOL: dict[str, Element]
_ELEMENTS_BY_NAME: dict[str, Element]
_ELEMENTS_BY_Z, _ELEMENTS_BY_SYMBOL, _ELEMENTS_BY_NAME = _build_elements()
'''

target = Path(__file__).resolve().parent.parent / "src" / "chemengine" / "core" / "element.py"
with open(target, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Written {len(content)} bytes to {target}")
