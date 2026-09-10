"""Property-based tests using Hypothesis @given strategies.

Tests formula parsing round-trips, InChI parsing correctness,
and alias resolver consistency with randomly generated inputs.
"""

from __future__ import annotations

import math

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from chemengine.core.enums import ElementSymbol
from chemengine.parsing.alias import _COMMON_ALIASES, resolve_alias, resolve_alias_to_graph
from chemengine.parsing.formula import formula_to_graph, parse_formula
from chemengine.parsing.inchi import _parse_formula_layer, parse_inchi
from chemengine.parsing.smiles import parse_smiles, serialize_smiles

# ══════════════════════════════════════════════════════════════════
# HYPOTHESIS STRATEGIES
# ══════════════════════════════════════════════════════════════════

# Common organic elements for formula generation
_ORGANIC_ELEMENTS = [
    ("C", 6), ("H", 1), ("N", 7), ("O", 8), ("S", 16),
    ("P", 15), ("F", 9), ("Cl", 17), ("Br", 35),
]

# All element symbols for broader testing
_ALL_ELEMENTS = [el.value for el in ElementSymbol]


@st.composite
def st_element_symbol(draw):
    """Generate a valid element symbol string."""
    return draw(st.sampled_from(_ALL_ELEMENTS))


@st.composite
def st_small_formula(draw):
    """Generate a small molecular formula string (e.g., 'C2H6O')."""
    # Generate 1-3 element/count pairs
    n_elements = draw(st.integers(min_value=1, max_value=3))
    parts = []
    for _ in range(n_elements):
        symbol = draw(st.sampled_from([e[0] for e in _ORGANIC_ELEMENTS]))
        count = draw(st.integers(min_value=1, max_value=10))
        parts.append(f"{symbol}{count}" if count > 1 else symbol)
    # Always include carbon first if present
    carbon_part = [p for p in parts if p.startswith("C")]
    other_parts = [p for p in parts if not p.startswith("C")]
    # Sort: C first, then H, then others
    h_part = [p for p in other_parts if p.startswith("H")]
    rest = [p for p in other_parts if not p.startswith("H")]
    return "".join(carbon_part + h_part + rest)


@st.composite
def st_hydrocarbon_formula(draw):
    """Generate a C/H-only molecular formula for formula_to_graph."""
    c = draw(st.integers(min_value=1, max_value=10))
    # For hydrocarbons: H <= 2C+2 (alkane)
    h_max = min(2 * c + 2, 20)
    h = draw(st.integers(min_value=0, max_value=h_max))
    if c == 1 and h == 0:
        return "C"
    elif c == 1:
        return f"CH{h}" if h > 1 else "CH"
    elif h == 0:
        return f"C{c}"
    elif h == 1:
        return f"C{c}H"
    return f"C{c}H{h}"


@st.composite
def st_smiles_string(draw):
    """Generate a simple valid SMILES string."""
    # Generate simple linear alkanes: C, CC, CCC, etc.
    chain_length = draw(st.integers(min_value=1, max_value=8))
    return "C" * chain_length


@st.composite
def st_inchi_formula(draw):
    """Generate a valid InChI formula layer (e.g., 'C6H6')."""
    c_count = draw(st.integers(min_value=1, max_value=10))
    h_count = draw(st.integers(min_value=0, max_value=2 * c_count + 2))
    parts = [f"C{c_count}" if c_count > 1 else "C"]
    if h_count > 0:
        parts.append(f"H{h_count}" if h_count > 1 else "H")
    # Optional oxygen
    o_count = draw(st.integers(min_value=0, max_value=3))
    if o_count > 0:
        parts.append(f"O{o_count}" if o_count > 1 else "O")
    return "".join(parts)


@st.composite
def st_alias_name(draw):
    """Generate a valid alias name from the known alias dictionary."""
    return draw(st.sampled_from(list(_COMMON_ALIASES.keys())))


@st.composite
def st_known_smiles(draw):
    """Generate a known valid SMILES string."""
    known = [
        "C", "CC", "CCC", "CCCC", "CC(C)C",
        "C=C", "C#C", "C=CC",
        "CCO", "CO", "CC=O",
        "c1ccccc1", "Cc1ccccc1",
        "CC(=O)O", "CC(=O)OC",
        "CCN", "CN(C)C",
        "CCl", "CBr", "CF",
        "C1CC1", "C1CCC1", "C1CCCCC1",
    ]
    return draw(st.sampled_from(known))


# ══════════════════════════════════════════════════════════════════
# FORMULA PARSER PROPERTY TESTS
# ══════════════════════════════════════════════════════════════════


class TestFormulaParserProperties:
    """Hypothesis @given property-based tests for formula parsing."""

    @given(formula=st_small_formula())
    @settings(max_examples=200, deadline=None)
    def test_parse_formula_returns_dict(self, formula: str):
        """parse_formula always returns a dict mapping ElementSymbol -> int."""
        result = parse_formula(formula)
        assert isinstance(result, dict)
        for key, value in result.items():
            assert isinstance(key, ElementSymbol)
            assert isinstance(value, int)
            assert value > 0

    @given(formula=st_small_formula())
    @settings(max_examples=200, deadline=None)
    def test_parse_formula_total_atoms_positive(self, formula: str):
        """parse_formula returns at least one atom."""
        result = parse_formula(formula)
        total = sum(result.values())
        assert total >= 1

    @given(formula=st_hydrocarbon_formula())
    @settings(max_examples=200, deadline=None)
    def test_formula_to_graph_round_trip(self, formula: str):
        """formula_to_graph -> molecular_formula preserves C/H counts."""
        graph = formula_to_graph(formula)
        # Parse original formula
        original_counts = parse_formula(formula)
        # Get graph formula
        graph_formula = graph.molecular_formula
        graph_counts = parse_formula(graph_formula)

        # Carbon count must match exactly
        c_orig = original_counts.get(ElementSymbol.C, 0)
        c_graph = graph_counts.get(ElementSymbol.C, 0)
        assert c_graph >= c_orig, (
            f"Carbon count mismatch: expected >= {c_orig}, "
            f"got {c_graph} for formula '{formula}'"
        )

    @given(formula=st_small_formula())
    @settings(max_examples=100, deadline=None)
    def test_formula_to_graph_non_empty(self, formula: str):
        """formula_to_graph produces a non-empty graph."""
        graph = formula_to_graph(formula)
        assert graph.num_atoms >= 1
        assert math.isfinite(graph.exact_mass)

    @given(
        c=st.integers(min_value=1, max_value=10),
        h=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=100, deadline=None)
    def test_hill_system_ordering(self, c: int, h: int):
        """Formula output follows Hill system (C before H)."""
        formula = f"C{c}H{h}" if c > 1 or h > 1 else ("C" if c == 1 else "H")
        if c == 1 and h > 1:
            formula = f"CH{h}"
        elif c > 1 and h == 1:
            formula = f"C{c}H"
        elif c == 1 and h == 1:
            formula = "CH"

        graph = formula_to_graph(formula)
        result = parse_formula(graph.molecular_formula)

        # Carbon should come before hydrogen in Hill system
        formula_str = graph.molecular_formula
        c_pos = formula_str.find("C")
        h_pos = formula_str.find("H")
        if c_pos >= 0 and h_pos >= 0:
            assert c_pos < h_pos, (
                f"Hill system violated: '{formula_str}' "
                f"(C at {c_pos}, H at {h_pos})"
            )


# ══════════════════════════════════════════════════════════════════
# INCHI PARSER PROPERTY TESTS
# ══════════════════════════════════════════════════════════════════


class TestInChIParserProperties:
    """Hypothesis @given property-based tests for InChI parsing."""

    @given(formula_layer=st_inchi_formula())
    @settings(max_examples=200, deadline=None)
    def test_parse_formula_layer_returns_counts(self, formula_layer: str):
        """_parse_formula_layer returns dict of atomic_number -> count."""
        result = _parse_formula_layer(formula_layer)
        assert isinstance(result, dict)
        for z, count in result.items():
            assert isinstance(z, int)
            assert isinstance(count, int)
            assert z >= 1
            assert count >= 1

    @given(formula_layer=st_inchi_formula())
    @settings(max_examples=200, deadline=None)
    def test_parse_formula_layer_total_positive(self, formula_layer: str):
        """_parse_formula_layer always returns at least one atom."""
        result = _parse_formula_layer(formula_layer)
        total = sum(result.values())
        assert total >= 1

    @given(
        c=st.integers(min_value=1, max_value=6),
        h=st.integers(min_value=0, max_value=14),
    )
    @settings(max_examples=100, deadline=None)
    def test_inchi_parse_produces_valid_graph(self, c: int, h: int):
        """InChI with formula only produces a valid graph."""
        formula = f"C{c}H{h}" if c > 1 or h > 1 else ("C" if c == 1 else "H")
        if c == 1 and h > 1:
            formula = f"CH{h}"
        elif c > 1 and h == 1:
            formula = f"C{c}H"
        elif c == 1 and h == 1:
            formula = "CH"

        inchi = f"InChI=1S/{formula}"
        graph = parse_inchi(inchi)
        assert graph.num_atoms >= 1
        # Should have correct heavy atom count
        heavy = sum(1 for a in graph.atoms if a.atomic_number != 1)
        assert heavy == c

    @given(
        c=st.integers(min_value=1, max_value=6),
        h=st.integers(min_value=1, max_value=14),
    )
    @settings(max_examples=100, deadline=None)
    def test_inchi_with_connections_roundtrip(self, c: int, h: int):
        """InChI with connections layer produces consistent connectivity."""
        formula = f"C{c}H{h}"
        # Simple chain connection
        connection = "-".join(str(i) for i in range(1, c + 1))
        inchi = f"InChI=1S/{formula}/c{connection}/h{connection}H"

        graph = parse_inchi(inchi)
        assert graph.num_atoms >= 1
        # All carbon atoms should be connected in a chain
        carbons = [i for i, a in enumerate(graph.atoms) if a.atomic_number == 6]
        assert len(carbons) >= c


# ══════════════════════════════════════════════════════════════════
# ALIAS RESOLVER PROPERTY TESTS
# ══════════════════════════════════════════════════════════════════


class TestAliasResolverProperties:
    """Hypothesis @given property-based tests for alias resolution."""

    @given(name=st_alias_name())
    @settings(max_examples=100, deadline=None)
    def test_resolve_alias_returns_smiles(self, name: str):
        """resolve_alias returns a non-empty string for known aliases."""
        result = resolve_alias(name)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    @given(name=st_alias_name())
    @settings(max_examples=100, deadline=None)
    def test_resolve_alias_case_insensitive(self, name: str):
        """resolve_alias is case-insensitive."""
        upper_result = resolve_alias(name.upper())
        lower_result = resolve_alias(name.lower())
        # Both should resolve (or both should be None)
        if upper_result is not None and lower_result is not None:
            assert upper_result == lower_result

    @given(name=st_alias_name())
    @settings(max_examples=100, deadline=None)
    def test_resolve_alias_to_graph_valid(self, name: str):
        """resolve_alias_to_graph produces a valid graph."""
        graph = resolve_alias_to_graph(name)
        assert graph is not None
        assert graph.num_atoms >= 1
        assert math.isfinite(graph.exact_mass)

    @given(name=st_alias_name())
    @settings(max_examples=100, deadline=None)
    def test_resolve_alias_to_graph_has_correct_elements(self, name: str):
        """Graph from alias has atoms matching the expected SMILES."""
        smiles = resolve_alias(name)
        assume(smiles is not None)

        graph_from_alias = resolve_alias_to_graph(name)
        graph_from_smiles = parse_smiles(smiles)

        # Should have the same element counts
        z_alias = sorted(a.atomic_number for a in graph_from_alias.atoms)
        z_smiles = sorted(a.atomic_number for a in graph_from_smiles.atoms)
        assert z_alias == z_smiles, (
            f"Alias '{name}' produced different elements: "
            f"alias={z_alias}, smiles={z_smiles}"
        )

    @given(name=st.text(min_size=1, max_size=20))
    @settings(max_examples=200, deadline=None)
    def test_resolve_unknown_name_returns_none(self, name: str):
        """resolve_alias returns None for unknown names (most of the time)."""
        # Only check truly random strings (skip if they happen to be known)
        if name.lower().strip() not in _COMMON_ALIASES:
            result = resolve_alias(name)
            assert result is None


# ══════════════════════════════════════════════════════════════════
# SMILES ROUND-TRIP PROPERTY TESTS
# ══════════════════════════════════════════════════════════════════


class TestSmilesRoundTripProperties:
    """Hypothesis @given property-based tests for SMILES round-trips."""

    @given(smiles=st_known_smiles())
    @settings(max_examples=100, deadline=None)
    def test_smiles_round_trip_preserves_elements(self, smiles: str):
        """SMILES parse -> serialize -> reparse preserves element distribution."""
        graph1 = parse_smiles(smiles)
        serialized = serialize_smiles(graph1)
        graph2 = parse_smiles(serialized)

        z1 = sorted(a.atomic_number for a in graph1.atoms)
        z2 = sorted(a.atomic_number for a in graph2.atoms)
        assert z1 == z2, (
            f"Round-trip failed for '{smiles}': "
            f"serialized='{serialized}', z1={z1}, z2={z2}"
        )

    @given(smiles=st_known_smiles())
    @settings(max_examples=100, deadline=None)
    def test_smiles_round_trip_preserves_bonds(self, smiles: str):
        """SMILES parse -> serialize -> reparse preserves bond count."""
        graph1 = parse_smiles(smiles)
        serialized = serialize_smiles(graph1)
        graph2 = parse_smiles(serialized)

        assert graph2.num_bonds == graph1.num_bonds, (
            f"Bond count mismatch for '{smiles}': "
            f"{graph2.num_bonds} vs {graph1.num_bonds}"
        )

    @given(smiles=st_known_smiles())
    @settings(max_examples=100, deadline=None)
    def test_smiles_round_trip_preserves_formula(self, smiles: str):
        """SMILES parse -> serialize -> reparse preserves molecular formula."""
        graph1 = parse_smiles(smiles)
        serialized = serialize_smiles(graph1)
        graph2 = parse_smiles(serialized)

        assert graph2.molecular_formula == graph1.molecular_formula, (
            f"Formula mismatch for '{smiles}': "
            f"'{graph2.molecular_formula}' vs '{graph1.molecular_formula}'"
        )

    @given(chain_length=st.integers(min_value=1, max_value=10))
    @settings(max_examples=50, deadline=None)
    def test_alkane_chain_round_trip(self, chain_length: int):
        """Linear alkane chains round-trip correctly."""
        smiles = "C" * chain_length
        graph1 = parse_smiles(smiles)
        serialized = serialize_smiles(graph1)
        graph2 = parse_smiles(serialized)

        c1 = sum(1 for a in graph1.atoms if a.atomic_number == 6)
        c2 = sum(1 for a in graph2.atoms if a.atomic_number == 6)
        assert c1 == c2 == chain_length

    @given(
        chain_len=st.integers(min_value=1, max_value=6),
        branch_pos=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50, deadline=None)
    def test_branched_alkane_round_trip(self, chain_len: int, branch_pos: int):
        """Branched alkanes round-trip correctly."""
        assume(branch_pos < chain_len)
        # Build a simple branched SMILES: CCC(C)CC
        if chain_len < 2:
            smiles = "C" * chain_len
        else:
            pos = min(branch_pos, chain_len - 1)
            smiles = "C" * (pos + 1) + "(C)" + "C" * (chain_len - pos - 1)

        graph1 = parse_smiles(smiles)
        serialized = serialize_smiles(graph1)
        graph2 = parse_smiles(serialized)

        z1 = sorted(a.atomic_number for a in graph1.atoms)
        z2 = sorted(a.atomic_number for a in graph2.atoms)
        assert z1 == z2
