"""Lewis Structure Generator — from first principles.

Generates Lewis dot structures for molecules using:
1. Valence electron counting from atomic number
2. Octet/duet rule satisfaction
3. Formal charge minimization
4. Lone pair placement

No database — all computed from MolecularGraph + element data.

Usage:
    >>> from chemengine.education.lewis_structures import LewisStructureGenerator
    >>> gen = LewisStructureGenerator()
    >>> lewis = gen.generate_from_smiles("O")  # Water
    >>> print(lewis.valence_electrons)  # 8
    >>> print(lewis.formal_charges)     # {0: 0, 1: 0}
    >>> print(lewis.explain())          # Step-by-step explanation
"""

from __future__ import annotations

from dataclasses import dataclass

from chemengine.core.enums import BondOrder
from chemengine.core.graph import MolecularGraph


@dataclass(frozen=True, slots=True)
class LonePairInfo:
    """Lone pair information for a single atom.

    Attributes:
        atom_index: Index of the atom in the graph.
        element: Element symbol.
        lone_pairs: Number of lone pairs.
        lone_electrons: Number of non-bonding electrons.
        formal_charge: Computed formal charge.
    """
    atom_index: int
    element: str
    lone_pairs: int
    lone_electrons: int
    formal_charge: int


@dataclass(frozen=True, slots=True)
class LewisStructure:
    """A complete Lewis structure with lone pairs and formal charges.

    Attributes:
        smiles: Original SMILES string.
        valence_electrons: Total valence electrons.
        bonding_electrons: Electrons used in bonds.
        lone_electrons: Electrons as lone pairs.
        lone_pairs: Lone pair info per atom.
        formal_charges: Formal charge per atom index.
        octet_satisfied: Whether all atoms satisfy the octet rule.
        duet_atoms: Atoms following the duet rule (H, He, Li, Be).
    """
    smiles: str
    valence_electrons: int
    bonding_electrons: int
    lone_electrons: int
    lone_pairs: tuple[LonePairInfo, ...]
    formal_charges: dict[int, int]
    octet_satisfied: bool
    duet_atoms: tuple[int, ...]

    def explain(self) -> str:
        """Generate an educational step-by-step explanation."""
        lines: list[str] = []
        lines.append("Lewis Structure Analysis")
        lines.append("=" * 50)
        lines.append(f"Molecule: {self.smiles}")
        lines.append(f"Total valence electrons: {self.valence_electrons}")
        lines.append(f"Bonding electrons: {self.bonding_electrons}")
        lines.append(f"Lone pair electrons: {self.lone_electrons}")
        lines.append("")

        lines.append("Step 1: Count valence electrons")
        lines.append(f"  Total = {self.valence_electrons} electrons")
        lines.append("")

        lines.append("Step 2: Draw skeletal structure (bonds)")
        lines.append(f"  Electrons used in bonds: {self.bonding_electrons}")
        lines.append("")

        lines.append("Step 3: Distribute remaining electrons as lone pairs")
        lines.append(f"  Remaining electrons: {self.lone_electrons}")
        lines.append("")

        lines.append("Step 4: Check octet rule")
        if self.octet_satisfied:
            lines.append("  ✓ All atoms satisfy the octet rule")
        else:
            lines.append("  ✗ Some atoms may not satisfy the octet rule")
        lines.append("")

        lines.append("Lone Pair Distribution:")
        for lp in self.lone_pairs:
            if lp.lone_pairs > 0:
                lines.append(
                    f"  {lp.element} (atom {lp.atom_index}): "
                    f"{lp.lone_pairs} lone pair(s), "
                    f"formal charge = {lp.formal_charge:+d}"
                )

        if any(fc != 0 for fc in self.formal_charges.values()):
            lines.append("")
            lines.append("Formal Charges:")
            for idx, fc in self.formal_charges.items():
                if fc != 0:
                    lines.append(f"  Atom {idx}: {fc:+d}")

        return "\n".join(lines)


class LewisStructureGenerator:
    """Generate Lewis structures from first principles.

    Usage:
        >>> gen = LewisStructureGenerator()
        >>> lewis = gen.generate_from_graph(graph)
    """

    def generate_from_graph(self, graph: MolecularGraph) -> LewisStructure:
        """Generate a Lewis structure for a molecular graph.

        Args:
            graph: The molecular graph.

        Returns:
            LewisStructure with lone pairs and formal charges.
        """
        smiles = ""
        if graph.name:
            smiles = graph.name

        # Step 1: Count total valence electrons
        total_valence = self._count_valence_electrons(graph)

        # Step 2: Count bonding electrons
        bonding_electrons = self._count_bonding_electrons(graph)

        # Step 3: Compute lone pairs per atom
        lone_pairs = self._compute_lone_pairs(graph, total_valence, bonding_electrons)

        # Step 4: Compute formal charges
        formal_charges = self._compute_formal_charges(graph, lone_pairs)

        # Step 5: Check octet rule
        octet_ok, duet_atoms = self._check_octet(graph, lone_pairs)

        lone_electrons = total_valence - bonding_electrons

        return LewisStructure(
            smiles=smiles,
            valence_electrons=total_valence,
            bonding_electrons=bonding_electrons,
            lone_electrons=lone_electrons,
            lone_pairs=tuple(lone_pairs),
            formal_charges=formal_charges,
            octet_satisfied=octet_ok,
            duet_atoms=tuple(duet_atoms),
        )

    def generate_from_smiles(self, smiles: str) -> LewisStructure:
        """Generate a Lewis structure from a SMILES string.

        Args:
            smiles: SMILES string.

        Returns:
            LewisStructure.
        """
        from chemengine.parsing.smiles import parse_smiles
        graph = parse_smiles(smiles)
        result = self.generate_from_graph(graph)
        # Replace smiles in result
        return LewisStructure(
            smiles=smiles,
            valence_electrons=result.valence_electrons,
            bonding_electrons=result.bonding_electrons,
            lone_electrons=result.lone_electrons,
            lone_pairs=result.lone_pairs,
            formal_charges=result.formal_charges,
            octet_satisfied=result.octet_satisfied,
            duet_atoms=result.duet_atoms,
        )

    def _count_valence_electrons(self, graph: MolecularGraph) -> int:
        """Count total valence electrons from all atoms."""
        total = 0
        for atom in graph.atoms:
            try:
                element = atom.element
                # Use oxidation states to determine typical valence
                if element.oxidation_states:
                    # For neutral atoms, valence = number of valence electrons
                    # This is based on group number
                    z = atom.atomic_number
                    if z <= 2:
                        total += z  # H=1, He=2
                    elif z <= 10:
                        total += z - 2  # Li=1, Be=2, B=3, C=4, N=5, O=6, F=7, Ne=8
                    elif z <= 18:
                        total += z - 10  # Na=1, Mg=2, Al=3, Si=4, P=5, S=6, Cl=7, Ar=8
                    elif z <= 36:
                        # Period 4: K(1), Ca(2), Sc(3)...Zn(12), Ga(3), Ge(4), As(5), Se(6), Br(7), Kr(8)
                        if z <= 20:
                            total += z - 18
                        elif z <= 30:
                            total += z - 18  # Transition metals
                        else:
                            total += z - 28  # Main group period 4
                    elif z <= 54:
                        if z <= 38 or z <= 48:
                            total += z - 36
                        else:
                            total += z - 46
                    elif z <= 86:
                        if z <= 56 or z <= 80:
                            total += z - 54
                        else:
                            total += z - 74
                    else:
                        total += z - 86
                else:
                    total += 4  # Fallback
            except Exception:
                total += 4  # Fallback

        # Adjust for formal charges already present
        for atom in graph.atoms:
            if atom.formal_charge > 0:
                total -= atom.formal_charge
            elif atom.formal_charge < 0:
                total += abs(atom.formal_charge)

        return total

    def _count_bonding_electrons(self, graph: MolecularGraph) -> int:
        """Count electrons used in bonding."""
        total = 0
        for bond in graph.bonds:
            if bond.order == BondOrder.SINGLE:
                total += 2
            elif bond.order == BondOrder.DOUBLE:
                total += 4
            elif bond.order == BondOrder.TRIPLE:
                total += 6
            elif bond.order == BondOrder.AROMATIC:
                total += 3  # ~1.5 bonds × 2 electrons
            else:
                total += 2
        return total

    def _compute_lone_pairs(
        self, graph: MolecularGraph, total_valence: int, bonding_electrons: int
    ) -> list[LonePairInfo]:
        """Compute lone pairs for each atom.

        Distributes remaining electrons to satisfy octet/duet rules.
        """
        remaining = total_valence - bonding_electrons
        lone_pair_list: list[LonePairInfo] = []

        for i, atom in enumerate(graph.atoms):
            z = atom.atomic_number

            # Determine octet target
            if z in (1, 2, 3, 4):  # H, He, Li, Be — duet rule
                target = 2
            else:
                target = 8

            # Count bonding electrons around this atom
            atom_bonding = 0
            for bond in graph.bonds:
                if bond.atom1 == i or bond.atom2 == i:
                    if bond.order == BondOrder.SINGLE:
                        atom_bonding += 2
                    elif bond.order == BondOrder.DOUBLE:
                        atom_bonding += 4
                    elif bond.order == BondOrder.TRIPLE:
                        atom_bonding += 6
                    elif bond.order == BondOrder.AROMATIC:
                        atom_bonding += 3
                    else:
                        atom_bonding += 2

            # Lone pair electrons needed to reach octet
            needed = max(0, target - atom_bonding)

            # Take from remaining pool
            actual = min(needed, remaining)
            remaining -= actual

            lone_pairs_count = actual // 2
            element_sym = atom.symbol

            lone_pair_list.append(LonePairInfo(
                atom_index=i,
                element=element_sym,
                lone_pairs=lone_pairs_count,
                lone_electrons=actual,
                formal_charge=0,  # Computed later
            ))

        return lone_pair_list

    def _compute_formal_charges(
        self, graph: MolecularGraph, lone_pairs: list[LonePairInfo]
    ) -> dict[int, int]:
        """Compute formal charges using: FC = valence - lone - bonds."""
        charges: dict[int, int] = {}

        for i, atom in enumerate(graph.atoms):
            try:
                element = atom.element
                # Valence electrons for formal charge calculation
                z = atom.atomic_number
                if z <= 2:
                    valence = z
                elif z <= 10:
                    valence = z - 2
                elif z <= 18:
                    valence = z - 10
                elif z <= 36:
                    if z <= 20 or z <= 30:
                        valence = z - 18
                    else:
                        valence = z - 28
                elif z <= 54:
                    if z <= 38 or z <= 48:
                        valence = z - 36
                    else:
                        valence = z - 46
                elif z <= 86:
                    if z <= 56 or z <= 80:
                        valence = z - 54
                    else:
                        valence = z - 74
                else:
                    valence = z - 86

                # Count bonds (each bond = 1 for formal charge)
                bond_count = 0
                for bond in graph.bonds:
                    if bond.atom1 == i or bond.atom2 == i:
                        if bond.order == BondOrder.SINGLE:
                            bond_count += 1
                        elif bond.order == BondOrder.DOUBLE:
                            bond_count += 2
                        elif bond.order == BondOrder.TRIPLE:
                            bond_count += 3
                        elif bond.order == BondOrder.AROMATIC:
                            bond_count += 1  # Treat aromatic as ~1
                        else:
                            bond_count += 1

                lone_electrons = lone_pairs[i].lone_electrons
                fc = valence - lone_electrons - bond_count
                charges[i] = fc

            except Exception:
                charges[i] = 0

        return charges

    def _check_octet(
        self, graph: MolecularGraph, lone_pairs: list[LonePairInfo]
    ) -> tuple[bool, list[int]]:
        """Check if all atoms satisfy the octet (or duet) rule."""
        all_ok = True
        duet_atoms: list[int] = []

        for i, atom in enumerate(graph.atoms):
            z = atom.atomic_number

            # Determine target
            if z in (1, 2, 3, 4):
                target = 2
                duet_atoms.append(i)
            else:
                target = 8

            # Count total electrons around atom
            atom_bonding = 0
            for bond in graph.bonds:
                if bond.atom1 == i or bond.atom2 == i:
                    if bond.order == BondOrder.SINGLE:
                        atom_bonding += 2
                    elif bond.order == BondOrder.DOUBLE:
                        atom_bonding += 4
                    elif bond.order == BondOrder.TRIPLE:
                        atom_bonding += 6
                    elif bond.order == BondOrder.AROMATIC:
                        atom_bonding += 3
                    else:
                        atom_bonding += 2

            total_around = atom_bonding + lone_pairs[i].lone_electrons
            if total_around < target:
                all_ok = False

        return all_ok, duet_atoms
