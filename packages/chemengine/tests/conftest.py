"""Shared test fixtures for the chemistry engine."""

import pytest

from chemengine.core.bonds import BondOrder
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder


@pytest.fixture
def methane_graph() -> MolecularGraph:
    """Return a methane (CH4) molecular graph."""
    builder = MolecularGraphBuilder()
    c = builder.add_atom(atomic_number=6)
    for _ in range(4):
        h = builder.add_atom(atomic_number=1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


@pytest.fixture
def ethane_graph() -> MolecularGraph:
    """Return an ethane (C2H6) molecular graph."""
    builder = MolecularGraphBuilder()
    c1 = builder.add_atom(atomic_number=6)
    c2 = builder.add_atom(atomic_number=6)
    builder.add_bond(c1, c2, BondOrder.SINGLE)
    for i in (c1, c2):
        for _ in range(3):
            h = builder.add_atom(atomic_number=1)
            builder.add_bond(i, h, BondOrder.SINGLE)
    return builder.build()


@pytest.fixture
def benzene_graph() -> MolecularGraph:
    """Return a benzene (C6H6) molecular graph."""
    builder = MolecularGraphBuilder()
    carbons = []
    for i in range(6):
        c = builder.add_atom(atomic_number=6)
        carbons.append(c)
    for i in range(6):
        builder.add_bond(carbons[i], carbons[(i + 1) % 6], BondOrder.AROMATIC)
    for c in carbons:
        h = builder.add_atom(atomic_number=1)
        builder.add_bond(c, h, BondOrder.SINGLE)
    return builder.build()


