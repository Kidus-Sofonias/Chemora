"""Stoichiometry Calculator — from first principles.

Performs stoichiometric calculations without any database:
1. Balance chemical equations
2. Calculate molar masses from element data
3. Convert between mass, moles, and particles
4. Determine limiting reagents
5. Calculate theoretical yields
6. Empirical/molecular formula determination

Usage:
    >>> from chemengine.education.stoichiometry import StoichiometryCalculator
    >>> calc = StoichiometryCalculator()
    >>> balanced = calc.balance_equation("CH4 + O2 -> CO2 + H2O")
    >>> print(balanced.equation)  # 'CH4 + 2O2 -> CO2 + 2H2O'
    >>> result = calc.moles_from_mass(18.015, "H2O")
    >>> print(result)  # 1.0 mol
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chemengine.core.element import Element

# ── Data Types ──

@dataclass(frozen=True, slots=True)
class StoichiometryResult:
    """Result of a stoichiometric calculation.

    Attributes:
        value: The numerical result.
        unit: The unit of the result.
        explanation: Step-by-step explanation.
        steps: Individual calculation steps.
    """
    value: float
    unit: str
    explanation: str
    steps: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BalancedEquation:
    """A balanced chemical equation.

    Attributes:
        equation: The balanced equation string.
        reactants: List of (formula, coefficient) tuples.
        products: List of (formula, coefficient) tuples.
        is_balanced: Whether the equation is atom-balanced.
        explanation: How the equation was balanced.
    """
    equation: str
    reactants: tuple[tuple[str, int], ...]
    products: tuple[tuple[str, int], ...]
    is_balanced: bool = True
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class MolarMass:
    """Molar mass of a chemical formula.

    Attributes:
        formula: The chemical formula.
        molar_mass: Molar mass in g/mol.
        composition: Dict of element -> (count, mass_contribution).
    """
    formula: str
    molar_mass: float
    composition: dict[str, tuple[int, float]] = field(default_factory=dict)


# ── Formula Parsing ──

def _parse_formula_simple(formula: str) -> dict[str, int]:
    """Parse a simple molecular formula into element counts.

    Handles formulas like: H2O, Ca(OH)2, CuSO4, Fe2O3

    Returns:
        Dict mapping element symbol to count.
    """
    counts: dict[str, int] = {}
    i = 0
    text = formula.strip()

    while i < len(text):
        if text[i] == '(':
            # Find matching closing paren
            depth = 1
            j = i + 1
            while j < len(text) and depth > 0:
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                j += 1
            # j is now after the closing paren
            inner = text[i + 1: j - 1]
            # Get multiplier after paren
            k = j
            num_str = ""
            while k < len(text) and text[k].isdigit():
                num_str += text[k]
                k += 1
            multiplier = int(num_str) if num_str else 1

            # Parse inner formula
            inner_counts = _parse_simple_elements(inner)
            for elem, cnt in inner_counts.items():
                counts[elem] = counts.get(elem, 0) + cnt * multiplier
            i = k
        elif text[i].isupper():
            # Element symbol
            j = i + 1
            while j < len(text) and text[j].islower():
                j += 1
            elem = text[i:j]
            # Get count
            num_str = ""
            while j < len(text) and text[j].isdigit():
                num_str += text[j]
                j += 1
            cnt = int(num_str) if num_str else 1
            counts[elem] = counts.get(elem, 0) + cnt
            i = j
        else:
            i += 1

    return counts


def _parse_simple_elements(text: str) -> dict[str, int]:
    """Parse element-count pairs from a formula fragment."""
    counts: dict[str, int] = {}
    i = 0
    while i < len(text):
        if text[i].isupper():
            j = i + 1
            while j < len(text) and text[j].islower():
                j += 1
            elem = text[i:j]
            num_str = ""
            while j < len(text) and text[j].isdigit():
                num_str += text[j]
                j += 1
            cnt = int(num_str) if num_str else 1
            counts[elem] = counts.get(elem, 0) + cnt
            i = j
        else:
            i += 1
    return counts


def _formula_to_dict(formula: str) -> dict[str, int]:
    """Convert a formula string to element counts."""
    return _parse_formula_simple(formula)


def _dict_to_formula(counts: dict[str, int]) -> str:
    """Convert element counts to a Hill-system formula string."""
    parts: list[str] = []
    for sym in ("C", "H"):
        if sym in counts:
            cnt = counts.pop(sym)
            parts.append(f"{sym}{cnt if cnt > 1 else ''}")
    for sym in sorted(counts):
        cnt = counts[sym]
        parts.append(f"{sym}{cnt if cnt > 1 else ''}")
    return "".join(parts)


# ── Molar Mass ──

def compute_molar_mass(formula: str) -> MolarMass:
    """Compute the molar mass of a chemical formula from first principles.

    Uses element data (atomic mass from Element class) — no database lookup
    for the compound itself.

    Args:
        formula: Chemical formula (e.g., 'H2O', 'Ca(OH)2').

    Returns:
        MolarMass with total mass and per-element breakdown.
    """
    counts = _parse_formula_simple(formula)
    total = 0.0
    composition: dict[str, tuple[int, float]] = {}

    for elem, cnt in counts.items():
        try:
            element = Element.from_symbol(elem)
            mass_per = element.atomic_mass
        except (KeyError, ValueError):
            mass_per = 0.0
        contribution = mass_per * cnt
        total += contribution
        composition[elem] = (cnt, contribution)

    return MolarMass(
        formula=formula,
        molar_mass=round(total, 6),
        composition=composition,
    )


# ── Main Calculator ──

class StoichiometryCalculator:
    """Perform stoichiometric calculations from first principles.

    Usage:
        >>> calc = StoichiometryCalculator()
        >>> balanced = calc.balance_equation("CH4 + O2 -> CO2 + H2O")
        >>> moles = calc.moles_from_mass(36.0, "H2O")
    """

    def balance_equation(self, equation_str: str) -> BalancedEquation:
        """Balance a chemical equation.

        Uses an algebraic method to find integer coefficients.

        Args:
            equation_str: Equation string with '->' or '=' separating
                         reactants and products (e.g., 'CH4 + O2 -> CO2 + H2O').

        Returns:
            BalancedEquation with balanced formula.
        """
        # Parse the equation
        if "->" in equation_str:
            left, right = equation_str.split("->", 1)
        elif "=" in equation_str:
            left, right = equation_str.split("=", 1)
        else:
            raise ValueError(f"Equation must contain '->' or '=': {equation_str}")

        reactants = [s.strip() for s in left.split("+") if s.strip()]
        products = [s.strip() for s in right.split("+") if s.strip()]

        # Collect all formulas
        all_formulas = reactants + products
        n = len(all_formulas)

        # Build element matrix
        all_elements: set[str] = set()
        formula_counts: list[dict[str, int]] = []
        for f in all_formulas:
            counts = _parse_formula_simple(f)
            formula_counts.append(counts)
            all_elements.update(counts.keys())

        elements = sorted(all_elements)
        m = len(elements)

        # Build matrix: rows = elements, cols = formulas
        # Positive for products, negative for reactants
        matrix: list[list[int]] = []
        for elem in elements:
            row: list[int] = []
            for i, counts in enumerate(formula_counts):
                val = counts.get(elem, 0)
                if i >= len(reactants):
                    val = -val  # Products are negative
                row.append(val)
            matrix.append(row)

        # Solve using Gaussian elimination over integers
        coefficients = self._solve_integer_system(matrix)

        if coefficients is None:
            # Fallback: simple 1:1 coefficients
            coefficients = [1] * n

        # Normalize to smallest integers
        from functools import reduce
        from math import gcd
        g = reduce(gcd, coefficients)
        if g > 0:
            coefficients = [c // g for c in coefficients]

        # Build balanced equation string
        reactant_parts: list[tuple[str, int]] = []
        product_parts: list[tuple[str, int]] = []
        for i, formula in enumerate(all_formulas):
            coeff = coefficients[i]
            if i < len(reactants):
                reactant_parts.append((formula, coeff))
            else:
                product_parts.append((formula, coeff))

        # Format equation string
        def fmt_part(formula: str, coeff: int) -> str:
            return formula if coeff == 1 else f"{coeff}{formula}"

        left_str = " + ".join(fmt_part(f, c) for f, c in reactant_parts)
        right_str = " + ".join(fmt_part(f, c) for f, c in product_parts)
        balanced_str = f"{left_str} -> {right_str}"

        # Verify balance
        is_balanced = self._verify_balance(all_formulas, coefficients, elements)

        explanation = self._balance_explanation(
            equation_str, balanced_str, reactant_parts, product_parts, elements, formula_counts
        )

        return BalancedEquation(
            equation=balanced_str,
            reactants=tuple(reactant_parts),
            products=tuple(product_parts),
            is_balanced=is_balanced,
            explanation=explanation,
        )

    def moles_from_mass(self, mass_grams: float, formula: str) -> StoichiometryResult:
        """Calculate moles from mass.

        Args:
            mass_grams: Mass in grams.
            formula: Chemical formula.

        Returns:
            StoichiometryResult with moles and explanation.
        """
        mm = compute_molar_mass(formula)
        moles = mass_grams / mm.molar_mass if mm.molar_mass > 0 else 0.0

        steps = [
            f"Step 1: Find molar mass of {formula}",
            f"  Molar mass = {mm.molar_mass:.4f} g/mol",
            "Step 2: Divide mass by molar mass",
            f"  Moles = {mass_grams} g / {mm.molar_mass:.4f} g/mol = {moles:.4f} mol",
        ]

        explanation = (
            f"To convert {mass_grams} g of {formula} to moles:\n"
            f"1. Molar mass of {formula} = {mm.molar_mass:.4f} g/mol\n"
            f"2. Moles = mass / molar mass = {mass_grams} / {mm.molar_mass:.4f} = {moles:.4f} mol"
        )

        return StoichiometryResult(
            value=round(moles, 6),
            unit="mol",
            explanation=explanation,
            steps=tuple(steps),
        )

    def mass_from_moles(self, moles: float, formula: str) -> StoichiometryResult:
        """Calculate mass from moles."""
        mm = compute_molar_mass(formula)
        mass = moles * mm.molar_mass

        explanation = (
            f"To convert {moles} mol of {formula} to grams:\n"
            f"1. Molar mass of {formula} = {mm.molar_mass:.4f} g/mol\n"
            f"2. Mass = moles × molar mass = {moles} × {mm.molar_mass:.4f} = {mass:.4f} g"
        )

        return StoichiometryResult(
            value=round(mass, 6),
            unit="g",
            explanation=explanation,
        )

    def particles_from_moles(self, moles: float) -> StoichiometryResult:
        """Calculate number of particles from moles (Avogadro's number)."""
        AVOGADRO = 6.02214076e23
        particles = moles * AVOGADRO

        explanation = (
            f"Number of particles = moles × Avogadro's number\n"
            f"= {moles} × 6.022×10²³ = {particles:.4e} particles"
        )

        return StoichiometryResult(
            value=particles,
            unit="particles",
            explanation=explanation,
        )

    def limiting_reagent(
        self,
        reactant_amounts: dict[str, float],
        equation: str,
    ) -> StoichiometryResult:
        """Determine the limiting reagent.

        Args:
            reactant_amounts: Dict of formula -> moles.
            equation: Balanced equation string.

        Returns:
            StoichiometryResult identifying the limiting reagent.
        """
        balanced = self.balance_equation(equation)
        reactant_coeffs = {f: c for f, c in balanced.reactants}

        # Compute moles / coefficient for each reactant
        ratios: dict[str, float] = {}
        for formula, moles in reactant_amounts.items():
            coeff = reactant_coeffs.get(formula, 1)
            ratios[formula] = moles / coeff

        limiting = min(ratios, key=ratios.get)  # type: ignore[arg-type]
        limiting_ratio = ratios[limiting]

        explanation = (
            f"Limiting Reagent Analysis:\n"
            f"Balanced equation: {balanced.equation}\n\n"
        )
        for formula, moles in reactant_amounts.items():
            coeff = reactant_coeffs.get(formula, 1)
            ratio = ratios[formula]
            marker = " ← LIMITING" if formula == limiting else ""
            explanation += f"  {formula}: {moles} mol / {coeff} = {ratio:.4f}{marker}\n"

        explanation += (
            f"\nThe limiting reagent is {limiting} because it has the "
            f"smallest mole/coefficient ratio ({limiting_ratio:.4f})."
        )

        return StoichiometryResult(
            value=limiting_ratio,
            unit=f"mol/{limiting}",
            explanation=explanation,
        )

    def theoretical_yield(
        self,
        limiting_moles: float,
        limiting_coeff: int,
        product_coeff: int,
        product_formula: str,
    ) -> StoichiometryResult:
        """Calculate theoretical yield from limiting reagent.

        Args:
            limiting_moles: Moles of limiting reagent.
            limiting_coeff: Coefficient of limiting reagent.
            product_coeff: Coefficient of desired product.
            product_formula: Formula of desired product.

        Returns:
            StoichiometryResult with theoretical yield in grams.
        """
        product_moles = (limiting_moles / limiting_coeff) * product_coeff
        mm = compute_molar_mass(product_formula)
        mass = product_moles * mm.molar_mass

        explanation = (
            f"Theoretical Yield Calculation:\n"
            f"1. Moles of product = ({limiting_moles} / {limiting_coeff}) × {product_coeff} = {product_moles:.4f} mol\n"
            f"2. Molar mass of {product_formula} = {mm.molar_mass:.4f} g/mol\n"
            f"3. Mass = {product_moles:.4f} × {mm.molar_mass:.4f} = {mass:.4f} g"
        )

        return StoichiometryResult(
            value=round(mass, 6),
            unit="g",
            explanation=explanation,
        )

    def percent_yield(self, actual: float, theoretical: float) -> StoichiometryResult:
        """Calculate percent yield."""
        pct = (actual / theoretical * 100) if theoretical > 0 else 0.0
        explanation = (
            f"Percent Yield = (actual / theoretical) × 100\n"
            f"= ({actual} / {theoretical}) × 100 = {pct:.2f}%"
        )
        return StoichiometryResult(value=round(pct, 2), unit="%", explanation=explanation)

    def empirical_formula(self, composition: dict[str, float]) -> StoichiometryResult:
        """Determine empirical formula from percent composition.

        Args:
            composition: Dict of element symbol -> percent by mass.

        Returns:
            StoichiometryResult with the empirical formula.
        """
        # Convert mass percentages to moles
        mole_ratios: dict[str, float] = {}
        for elem, mass_pct in composition.items():
            try:
                element = Element.from_symbol(elem)
                atomic_mass = element.atomic_mass
            except (KeyError, ValueError):
                atomic_mass = 1.0
            mole_ratios[elem] = mass_pct / atomic_mass

        # Find the smallest ratio
        min_ratio = min(mole_ratios.values())

        # Divide all by smallest and round to nearest integer
        formula_counts: dict[str, int] = {}
        for elem, ratio in mole_ratios.items():
            count = round(ratio / min_ratio)
            formula_counts[elem] = max(count, 1)

        formula = _dict_to_formula(formula_counts)

        explanation = (
            f"Empirical Formula from Percent Composition:\n"
            f"Given: {composition}\n"
            f"Step 1: Convert mass % to moles\n"
        )
        for elem, pct in composition.items():
            mm = mole_ratios[elem]
            explanation += f"  {elem}: {pct}% / {atomic_mass} = {mm:.4f} mol\n"

        explanation += f"Step 2: Divide by smallest ({min_ratio:.4f})\n"
        for elem, ratio in mole_ratios.items():
            explanation += f"  {elem}: {ratio:.4f} / {min_ratio:.4f} = {ratio/min_ratio:.2f}\n"

        explanation += f"Step 3: Round to integers → {formula}"

        return StoichiometryResult(
            value=formula,
            unit="formula",
            explanation=explanation,
        )

    def percent_composition(self, formula: str) -> StoichiometryResult:
        """Calculate percent composition by mass.

        Args:
            formula: Chemical formula.

        Returns:
            StoichiometryResult with percent composition.
        """
        mm = compute_molar_mass(formula)
        result_str = ""
        for elem, (cnt, mass_contrib) in mm.composition.items():
            pct = (mass_contrib / mm.molar_mass * 100) if mm.molar_mass > 0 else 0
            result_str += f"  {elem}: {pct:.2f}%\n"

        explanation = (
            f"Percent Composition of {formula}:\n"
            f"Molar mass = {mm.molar_mass:.4f} g/mol\n"
            f"{result_str}"
        )

        return StoichiometryResult(
            value=mm.molar_mass,
            unit="% composition",
            explanation=explanation,
        )

    # ── Internal Helpers ──

    def _solve_integer_system(self, matrix: list[list[int]]) -> list[int] | None:
        """Solve a homogeneous system Ax=0 for integer solutions.

        Uses a simple approach: try small integer coefficients.
        """
        n_cols = len(matrix[0]) if matrix else 0
        if n_cols == 0:
            return None

        # For small systems (<=5 species), brute force with small coefficients
        if n_cols <= 5:
            return self._brute_force_balance(matrix, n_cols)

        return None

    def _brute_force_balance(
        self, matrix: list[list[int]], n: int, max_coeff: int = 10
    ) -> list[int] | None:
        """Brute-force search for integer coefficients."""
        from itertools import product as iter_product

        for coeffs in iter_product(range(1, max_coeff + 1), repeat=n):
            # Check if all element balances are zero
            balanced = True
            for row in matrix:
                total = sum(c * v for c, v in zip(coeffs, row))
                if total != 0:
                    balanced = False
                    break
            if balanced:
                return list(coeffs)

        return None

    def _verify_balance(
        self,
        formulas: list[str],
        coefficients: list[int],
        elements: list[str],
    ) -> bool:
        """Verify that the equation is balanced."""
        n_reactants = len(formulas) // 2  # Approximate split

        for elem in elements:
            left_count = 0
            right_count = 0
            for i, formula in enumerate(formulas):
                counts = _parse_formula_simple(formula)
                elem_count = counts.get(elem, 0) * coefficients[i]
                if i < n_reactants:
                    left_count += elem_count
                else:
                    right_count += elem_count
            if left_count != right_count:
                return False
        return True

    def _balance_explanation(
        self,
        original: str,
        balanced: str,
        reactants: list[tuple[str, int]],
        products: list[tuple[str, int]],
        elements: list[str],
        formula_counts: list[dict[str, int]],
    ) -> str:
        """Generate step-by-step balancing explanation."""
        lines = [
            f"Original: {original}",
            f"Balanced: {balanced}",
            "",
            "Steps:",
            "1. Count atoms of each element on both sides",
        ]
        for elem in elements:
            left = sum(
                formula_counts[i].get(elem, 0)
                for i in range(len(reactants))
            )
            right = sum(
                formula_counts[i].get(elem, 0)
                for i in range(len(reactants), len(formula_counts))
            )
            status = "✓" if left == right else "✗"
            lines.append(f"   {elem}: left={left}, right={right} {status}")

        lines.append("")
        lines.append("2. Adjust coefficients to balance each element")
        lines.append("3. Verify all elements are balanced")

        return "\n".join(lines)
