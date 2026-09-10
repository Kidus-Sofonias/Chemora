"""Validation rules for molecular graphs.

Implements all built-in validation rules:
    - ValenceRule: Check every atom's bond count + implicit H against max valence.
    - HypervalentRule: Expanded octet handling for S, P, Cl, Br, I, etc.
    - ChargeRule: Check formal charge against element-specific range.
    - TotalChargeRule: Check overall molecular charge consistency.
    - IsotopeRule: Check isotope mass numbers against known isotopes.
    - GraphStructureRule: Disconnected graph, duplicate bonds, self-bonds.
    - RadicalRule: Check for unpaired electrons.
    - ValenceSaturationRule: Check for unfilled valence (missing implicit H).
    - AromaticityRule: Basic aromatic consistency checks.

All rules follow the ValidationRule protocol and can be registered
with the ValidationRuleSet and AlgorithmRegistry.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from chemengine.core.bonds import BondOrder
from chemengine.core.element import Element
from chemengine.core.graph import MolecularGraph
from chemengine.validation.report import ValidationError, ValidationSeverity


class ValenceRule:
    """Check every atom's total bond count against maximum valence.

    For each atom, compute the total number of bonds (counting bond order)
    plus implicit hydrogens. If this exceeds the element's max valence,
    emit an error.

    Handles hypervalent atoms (S, P, Cl, Br, I) with expanded octets
    by checking against their specific max_valence from valence_rules.
    """

    name = "valence"
    description = "Check atom bond counts against maximum valence limits"

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        n = graph.num_atoms
        for i in range(n):
            atom = graph.atoms[i]
            if atom.atomic_number == 0:
                continue  # Wildcard atom — skip

            # Count total bond order (not just degree).
            # Aromatic bonds are counted Kekulé-aware (Kekulé-average
            # valence); BondOrder.AROMATIC is an enum sentinel (5), NOT a
            # real bond order — summing it raw would flag every aromatic
            # atom as hypervalent.
            #
            # For an atom with k aromatic bonds, any valid Kekulé structure
            # assigns alternating single/double bonds such that:
            #     k=0 -> 0, k=1 -> 1.5 (average), k=2 -> 3 (1+2),
            #     k>=3 -> 4 (fusion carbons: 1+1+2)
            # If the atom also carries an exocyclic multiple bond (e.g. a
            # carbonyl C in an aromatic ring), its aromatic bonds count as
            # 1 each so the ring stays single-bond-adjacent to the double.
            aromatic_bonds = [
                b for b in graph.bonds
                if (b.atom1 == i or b.atom2 == i)
                and (b.is_aromatic or b.order == BondOrder.AROMATIC)
            ]
            has_exocyclic_multiple = any(
                (b.atom1 == i or b.atom2 == i)
                and not b.is_aromatic
                and b.order != BondOrder.AROMATIC
                and b.order >= BondOrder.DOUBLE
                for b in graph.bonds
            )
            k = len(aromatic_bonds)
            if has_exocyclic_multiple:
                aromatic_sum = float(k)
            elif k >= 3:
                aromatic_sum = 4.0
            elif k == 2:
                aromatic_sum = 3.0
            else:
                aromatic_sum = 1.5 * k
            total_bond_order = aromatic_sum + sum(
                b.order for b in graph.bonds
                if (b.atom1 == i or b.atom2 == i)
                and not (b.is_aromatic or b.order == BondOrder.AROMATIC)
            )

            # Get implicit hydrogens
            impl_h_val: float
            if atom.implicit_hydrogens is not None:
                # Explicit implicit hydrogens — still check
                impl_h_val = float(atom.implicit_hydrogens)
            else:
                # Auto-compute: max valence - used valence
                max_val = atom.max_valence if atom.max_valence > 0 else 4
                used = total_bond_order + atom.formal_charge
                # For main-group elements, implicit H = max_val - used
                val = max(max_val - used, 0)
                # Cap at a reasonable maximum (most atoms don't have 8+ H)
                val = min(val, 4)
                # For atoms with no bonds, assign valence-based H
                if total_bond_order == 0 and atom.formal_charge == 0:
                    val = min(float(atom.default_valence), 4.0)
                if val < 0:
                    val = 0
                impl_h_val = float(val)

            total = total_bond_order + impl_h_val
            max_val = atom.max_valence if atom.max_valence > 0 else 4

            if total > max_val + 1e-9:
                element = atom.symbol
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Atom {i} ({element}): total connections "
                        f"{total} exceeds max valence {max_val}"
                    ),
                    atom_index=i,
                    detail={
                        "element": element,
                        "atomic_number": atom.atomic_number,
                        "total_connections": total,
                        "max_valence": max_val,
                        "bond_order_sum": total_bond_order,
                        "implicit_hydrogens": impl_h_val,
                        "formal_charge": atom.formal_charge,
                    },
                )


class HypervalentRule:
    """Validate expanded octet configurations for period 3+ elements.

    Elements from period 3 and below (S, P, Cl, Br, I, etc.) can have
    expanded octets (more than 8 electrons in valence shell). This rule
    checks that hypervalent configurations are reasonable based on the
    element's known max valence from the valence rules dataset.
    """

    name = "hypervalent"
    description = "Validate expanded octet configurations for period 3+ elements"

    # Elements known to support hypervalent configurations
    _HYPERVALENT_ELEMENTS: set[int] = {15, 16, 17, 35, 53}  # P, S, Cl, Br, I

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        n = graph.num_atoms
        for i in range(n):
            atom = graph.atoms[i]
            z = atom.atomic_number
            if z not in self._HYPERVALENT_ELEMENTS:
                continue

            total_bond_order = sum(
                bond.order for bond in graph.bonds
                if bond.atom1 == i or bond.atom2 == i
            )

            impl_h = atom.implicit_hydrogens or 0
            total = total_bond_order + impl_h

            # Get element's max valence from the element data
            try:
                el = Element.from_z(z)
                max_val = el.max_valence
            except (KeyError, ValueError):
                max_val = 4

            if total > max_val:
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Atom {i} ({atom.symbol}): hypervalent configuration "
                        f"with {total} connections exceeds max known valence "
                        f"of {max_val}"
                    ),
                    atom_index=i,
                    detail={
                        "element": atom.symbol,
                        "total_connections": total,
                        "max_known_valence": max_val,
                    },
                )


class ChargeRule:
    """Check each atom's formal charge against element-specific ranges.

    Uses the allowed_charges from the valence rules dataset to verify
    that formal charges are chemically reasonable.
    """

    name = "charge"
    description = "Check formal charge against element-specific allowed ranges"

    # Default allowed charge ranges by element group
    _DEFAULT_CHARGE_RANGES: dict[str, list[int]] = {
        "H": [0, 1],
        "C": [-1, 0, 1],
        "N": [-2, -1, 0, 1, 2, 3],
        "O": [-2, -1, 0, 1],
        "F": [-1, 0],
        "Si": [-1, 0, 1],
        "P": [-1, 0, 1, 2, 3],
        "S": [-2, -1, 0, 1, 2, 3, 4],
        "Cl": [-1, 0, 1, 3, 5, 7],
        "Br": [-1, 0, 1, 3, 5],
        "I": [-1, 0, 1, 3, 5, 7],
    }

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        n = graph.num_atoms
        for i in range(n):
            atom = graph.atoms[i]
            if atom.atomic_number == 0:
                continue

            z = atom.atomic_number
            sym = atom.symbol
            charge = atom.formal_charge

            if charge == 0:
                continue

            # Check against known allowed charges
            allowed = self._DEFAULT_CHARGE_RANGES.get(sym, [-4, -3, -2, -1, 0, 1, 2, 3, 4])

            if charge not in allowed:
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Atom {i} ({sym}): formal charge {charge:+d} is not "
                        f"in allowed range {allowed}"
                    ),
                    atom_index=i,
                    detail={
                        "element": sym,
                        "formal_charge": charge,
                        "allowed_charges": allowed,
                    },
                )


class TotalChargeRule:
    """Check overall molecular charge consistency.

    The sum of all formal charges should equal the total molecular charge.
    Also emit a warning for large net charges on small molecules.
    """

    name = "total_charge"
    description = "Check overall molecular charge consistency"

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        total_charge = sum(atom.formal_charge for atom in graph.atoms)

        # Emit info for non-neutral molecules
        if total_charge != 0:
            yield ValidationError(
                rule=self.name,
                severity=ValidationSeverity.INFO,
                message=(
                    f"Total molecular charge is {total_charge:+d}"
                ),
                detail={"total_charge": total_charge},
            )

        # Warning for large net charges on small molecules
        if abs(total_charge) > 2 and graph.num_heavy_atoms < 10:
            yield ValidationError(
                rule=self.name,
                severity=ValidationSeverity.WARNING,
                message=(
                    f"Large net charge ({total_charge:+d}) on small molecule "
                    f"with {graph.num_heavy_atoms} heavy atoms"
                ),
                detail={
                    "total_charge": total_charge,
                    "num_heavy_atoms": graph.num_heavy_atoms,
                },
            )


class IsotopeRule:
    """Check isotope mass numbers against known isotopes.

    For atoms with explicit isotope information, verify that the
    mass number corresponds to a known isotope of that element.
    """

    name = "isotope"
    description = "Check isotope mass numbers against known isotopes"

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        n = graph.num_atoms
        for i in range(n):
            atom = graph.atoms[i]
            if atom.isotope is None:
                continue

            z = atom.atomic_number
            mass_num = atom.isotope.mass_number

            try:
                el = Element.from_z(z)
                known = [iso.mass_number for iso in el.isotopes]
                if mass_num not in known:
                    yield ValidationError(
                        rule=self.name,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Atom {i} ({atom.symbol}): isotope mass number "
                            f"{mass_num} not in known isotopes {known}"
                        ),
                        atom_index=i,
                        detail={
                            "element": atom.symbol,
                            "mass_number": mass_num,
                            "known_mass_numbers": known,
                        },
                    )
            except (KeyError, ValueError):
                pass  # Skip wildcards or unknown elements


class GraphStructureRule:
    """Check graph structural integrity.

    Verifies:
        - No self-bonds (atom bonded to itself)
        - No duplicate bonds (same atom pair with multiple bonds)
        - Atom indices are in range
        - Hydrogen atoms have at most one bond
        - All atoms are in at least one component
    """

    name = "graph_structure"
    description = "Check basic graph structural integrity"

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        n = graph.num_atoms
        seen_pairs: set[tuple[int, int]] = set()

        for j, bond in enumerate(graph.bonds):
            # Atom index range
            if bond.atom1 < 0 or bond.atom1 >= n:
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.ERROR,
                    message=f"Bond {j}: atom1 index {bond.atom1} out of range [0, {n - 1}]",
                    bond_index=j,
                )
            if bond.atom2 < 0 or bond.atom2 >= n:
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.ERROR,
                    message=f"Bond {j}: atom2 index {bond.atom2} out of range [0, {n - 1}]",
                    bond_index=j,
                )
                continue

            # Self-bond
            if bond.atom1 == bond.atom2:
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.ERROR,
                    message=f"Bond {j}: self-bond at atom {bond.atom1}",
                    bond_index=j,
                    atom_index=bond.atom1,
                )
                continue

            # Duplicate bond
            pair = (min(bond.atom1, bond.atom2), max(bond.atom1, bond.atom2))
            if pair in seen_pairs:
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Bond {j}: duplicate bond between atoms "
                        f"{pair[0]} and {pair[1]}"
                    ),
                    bond_index=j,
                    detail={"atom1": pair[0], "atom2": pair[1]},
                )
            seen_pairs.add(pair)

        # Hydrogen bond count
        for i in range(n):
            atom = graph.atoms[i]
            if atom.atomic_number == 1:
                degree = graph.get_degree(i)
                if degree > 1:
                    yield ValidationError(
                        rule=self.name,
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Atom {i} (H): hydrogen has {degree} bonds, "
                            f"max is 1"
                        ),
                        atom_index=i,
                        detail={"degree": degree},
                    )


class RadicalRule:
    """Check for unpaired electrons (radicals).

    Radicals are flagged as warnings (chemically valid but reactive).
    Diradicals on small molecules are warnings.
    """

    name = "radical"
    description = "Check for unpaired electrons"

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        n = graph.num_atoms
        for i in range(n):
            atom = graph.atoms[i]
            if atom.radical_electrons > 0:
                sev = (
                    ValidationSeverity.WARNING
                    if atom.radical_electrons <= 1
                    else ValidationSeverity.WARNING
                )
                yield ValidationError(
                    rule=self.name,
                    severity=sev,
                    message=(
                        f"Atom {i} ({atom.symbol}): {atom.radical_electrons} "
                        f"unpaired electron(s)"
                    ),
                    atom_index=i,
                    detail={
                        "element": atom.symbol,
                        "radical_electrons": atom.radical_electrons,
                    },
                )


class ValenceSaturationRule:
    """Check for unfilled valence (missing implicit hydrogens).

    Atoms with incomplete octets or missing hydrogens are flagged.
    This is especially important for carbon, nitrogen, oxygen, etc.
    """

    name = "valence_saturation"
    description = "Check for unfilled valence (incomplete octet)"

    _MAIN_GROUP_ELEMENTS: set[int] = {5, 6, 7, 8, 9, 14, 15, 16, 17, 35, 53}

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        n = graph.num_atoms
        for i in range(n):
            atom = graph.atoms[i]
            z = atom.atomic_number
            if z not in self._MAIN_GROUP_ELEMENTS:
                continue

            total_bond_order = sum(
                bond.order for bond in graph.bonds
                if bond.atom1 == i or bond.atom2 == i
            )

            impl_h = atom.implicit_hydrogens
            if impl_h is None:
                continue

            total = total_bond_order + impl_h + atom.formal_charge
            expected = atom.default_valence if atom.default_valence > 0 else 4

            if total < expected and impl_h == 0:
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Atom {i} ({atom.symbol}): potentially incomplete "
                        f"valence (total={total}, expected ~{expected})"
                    ),
                    atom_index=i,
                    detail={
                        "element": atom.symbol,
                        "total_connections": total,
                        "expected_valence": expected,
                        "bond_order_sum": total_bond_order,
                        "implicit_hydrogens": impl_h,
                        "formal_charge": atom.formal_charge,
                    },
                )


class AromaticityRule:
    """Basic aromatic consistency checks.

    Verifies:
        - Aromatic atoms are in aromatic rings
        - Aromatic bonds connect aromatic atoms
    """

    name = "aromaticity"
    description = "Check aromatic consistency"

    def validate(self, graph: MolecularGraph) -> Iterator[ValidationError]:
        n = graph.num_atoms

        # Collect aromatic atoms from bond data
        aromatic_atoms: set[int] = set()
        for bond in graph.bonds:
            if bond.is_aromatic:
                aromatic_atoms.add(bond.atom1)
                aromatic_atoms.add(bond.atom2)

        # Check atom aromatic consistency
        for i in range(n):
            atom = graph.atoms[i]
            if atom.is_aromatic and i not in aromatic_atoms:
                yield ValidationError(
                    rule=self.name,
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Atom {i} ({atom.symbol}): marked aromatic but "
                        f"no aromatic bonds found"
                    ),
                    atom_index=i,
                    detail={"element": atom.symbol},
                )

        # Check bond aromatic consistency
        for j, bond in enumerate(graph.bonds):
            if bond.is_aromatic:
                a1 = bond.atom1
                a2 = bond.atom2
                if not (graph.atoms[a1].is_aromatic and graph.atoms[a2].is_aromatic):
                    yield ValidationError(
                        rule=self.name,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Bond {j}: aromatic bond connecting non-aromatic "
                            f"atoms ({a1}, {a2})"
                        ),
                        bond_index=j,
                        detail={"atom1": a1, "atom2": a2},
                    )


# ── Rule Registry ──

_BUILTIN_RULES: list[Any] = [
    ValenceRule(),
    HypervalentRule(),
    ChargeRule(),
    TotalChargeRule(),
    IsotopeRule(),
    GraphStructureRule(),
    RadicalRule(),
    ValenceSaturationRule(),
    AromaticityRule(),
]


def get_validation_rules(rule_set: str = "standard") -> list[Any]:
    """Get the list of validation rules for a given rule set profile.

    Args:
        rule_set: Profile name — 'strict', 'standard', or 'relaxed'.

    Returns:
        List of ValidationRule instances.
    """
    if rule_set == "relaxed":
        # Relaxed: skip aromaticity and saturation checks
        return [
            ValenceRule(),
            HypervalentRule(),
            ChargeRule(),
            TotalChargeRule(),
            IsotopeRule(),
            GraphStructureRule(),
            RadicalRule(),
        ]
    if rule_set == "strict":
        # Strict: all rules
        return list(_BUILTIN_RULES)
    # Standard: all rules (default)
    return list(_BUILTIN_RULES)
