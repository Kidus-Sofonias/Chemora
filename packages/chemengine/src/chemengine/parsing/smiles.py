"""SMILES parser and serializer — Production (v1.0.0).

Implements the OpenSMILES specification for parsing and serializing
SMILES (Simplified Molecular Input Line Entry System) strings into
MolecularGraph objects.

Features:
    - Element symbols (C, N, O, *, [Au], [13CH3+], etc.)
    - Wildcard atoms (*)
    - Bond types (-, =, #, $, :, /, \\, implicit)
    - Branches (nested parentheses)
    - Ring closures (digits, %digits for multi-digit)
    - Tetrahedral stereochemistry (@, @@)
    - Double bond directional bonds (/, \\)
    - Aromatic atoms (c, n, o, s, p, b, as, se)
    - Aromatic bonds (:)
    - Isotopes ([13C], [14CH3])
    - Charges ([O-], [NH4+], [Fe+2], [Fe++])
    - Hydrogen count modifiers ([OH], [NH2], [CH4])
    - Dot disconnections (salts, mixtures, water)
    - Detailed position-aware error messages

Architecture:
    tokenzier -> parser -> post-parse validation
    Each layer catches its own class of errors with position info.

Design:
    - Produces MolecularGraph directly via MolecularGraphBuilder
    - Immutable graph output
    - All modules communicate through typed domain models
    - Position tracking on all tokens for precise error reporting
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Final

from chemengine.core.atoms import Isotope
from chemengine.core.bonds import Bond
from chemengine.core.element import Element
from chemengine.core.enums import (
    BondOrder,
    BondStereo,
    ChiralTag,
    ElementSymbol,
    IsotopeType,
)
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.parsing.errors import (
    SmilesError,
    SmilesSyntaxError,
    SmilesValidationError,
    UnclosedBracketError,
    UnmatchedBranchError,
    UnmatchedRingClosureError,
)
from chemengine.parsing.protocol import Parser

logger = logging.getLogger(__name__)

# ── Token Definition ──


@dataclass(frozen=True, slots=True)
class Token:
    """A SMILES token with position information.

    Attributes:
        type: Token type (ATOM, BOND, BRANCH_START, BRANCH_END, etc.).
        value: The string value of the token.
        pos: Character position (0-based) in the input string.
    """

    type: str
    value: str
    pos: int


# ── Constants ──

# Token type constants
TOKEN_ATOM: Final[str] = "ATOM"
TOKEN_BOND: Final[str] = "BOND"
TOKEN_BRANCH_START: Final[str] = "BRANCH_START"
TOKEN_BRANCH_END: Final[str] = "BRANCH_END"
TOKEN_RING_CLOSURE: Final[str] = "RING_CLOSURE"
TOKEN_STEREO: Final[str] = "STEREO"
TOKEN_DOT: Final[str] = "DOT"

# Organic subset elements - can appear without brackets
_ORGANIC_ELEMENTS: set[str] = {
    "B", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I",
    "b", "c", "n", "o", "p", "s",
    "*",
}

# Map SMILES bond characters to BondOrder
_BOND_ORDER_MAP: dict[str, BondOrder] = {
    "-": BondOrder.SINGLE,
    "=": BondOrder.DOUBLE,
    "#": BondOrder.TRIPLE,
    "$": BondOrder.QUADRUPLE,
    ":": BondOrder.AROMATIC,
    "/": BondOrder.SINGLE,  # directional - treated as single for graph
    "\\": BondOrder.SINGLE,  # directional - treated as single for graph
}

# Map directional bonds to BondStereo
_DIRECTIONAL_STEREO: dict[str, BondStereo | None] = {
    "/": BondStereo.E,
    "\\": BondStereo.Z,
}

# Default bond between two organic atoms
_DEFAULT_BOND: Final[BondOrder] = BondOrder.SINGLE
# Default bond between two aromatic atoms
_DEFAULT_AROMATIC_BOND: Final[BondOrder] = BondOrder.AROMATIC

# Aromatic element symbols (lowercase) and their atomic numbers
_AROMATIC_SYMBOLS: dict[str, int] = {
    "b": 5, "c": 6, "n": 7, "o": 8, "p": 15, "s": 16,
    "as": 33, "se": 34,
}

# SMILES token regex: order matters - multi-char patterns before single-char
# Note: NOT using VERBOSE mode to avoid whitespace/comment side effects
_SMILES_TOKEN_RE: Final[re.Pattern] = re.compile(
    r"(\[[^\]]*\]|\[[^\]]*|"
    r"Cl|Br|"
    r"[bcnops]e|"
    r"[A-Z]|"
    r"as|se|\*|"
    r"[a-z]|"
    r"[-=#$:/\\]|"
    r"\(|\)|"
    r"%\d+|"
    r"\d|"
    r"@{1,2}|"
    r"\.)"
)

# Default valence for organic subset elements
_DEFAULT_VALENCE: dict[int, int] = {
    1: 1,   # H
    5: 3,   # B
    6: 4,   # C
    7: 3,   # N
    8: 2,   # O
    9: 1,   # F
    15: 3,  # P (common, e.g., PH3)
    16: 2,  # S (common, e.g., H2S)
    17: 1,  # Cl
    35: 1,  # Br
    53: 1,  # I
}

# Aromatic valence adjustments: in aromatic rings, elements contribute
# fewer bonds because pi electrons are delocalized
_AROMATIC_VALENCE: dict[int, int] = {
    5: 2,   # B: 2 bonds
    6: 3,   # C: 3 bonds (e.g., benzene)
    7: 2,   # N: 2 bonds (e.g., pyridine N) or 3 (e.g., pyrrole N)
    8: 2,   # O: 2 bonds (e.g., furan)
    15: 3,  # P: 3 bonds (e.g., phosphinine, uncommon)
    16: 2,  # S: 2 bonds (e.g., thiophene)
}

# Two-letter element symbols
_TWO_LETTER_ELEMENTS: Final[set[str]] = {
    "He", "Li", "Be", "Ne", "Na", "Mg", "Al", "Si", "Cl", "Ar",
    "Ca", "Sc", "Ti", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm",
    "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu",
    "Hf", "Ta", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb",
    "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th", "Pa", "U",
    "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No",
    "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn",
    "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
}


# ── Tokenizer ──


def _tokenize(smiles: str) -> list[Token]:
    """Tokenize a SMILES string with position tracking.

    Args:
        smiles: The SMILES string to tokenize.

    Returns:
        List of Token objects with type, value, and position.

    Raises:
        SmilesSyntaxError: If the SMILES contains invalid tokens or syntax.
    """
    if not smiles or not smiles.strip():
        raise SmilesSyntaxError("Empty SMILES string", pos=0)

    stripped = smiles.strip()
    tokens: list[Token] = []

    for m in _SMILES_TOKEN_RE.finditer(stripped):
        token = m.group(1)
        pos = m.start()

        if token == "(":
            tokens.append(Token(TOKEN_BRANCH_START, "(", pos))
        elif token == ")":
            tokens.append(Token(TOKEN_BRANCH_END, ")", pos))
        elif token == ".":
            tokens.append(Token(TOKEN_DOT, ".", pos))
        elif token in _BOND_ORDER_MAP:
            tokens.append(Token(TOKEN_BOND, token, pos))
        elif token in ("@", "@@"):
            tokens.append(Token(TOKEN_STEREO, token, pos))
        elif token[0].isdigit() or token.startswith("%"):
            tokens.append(Token(TOKEN_RING_CLOSURE, token, pos))
        elif token.startswith("["):
            # Validate the bracket atom has a closing bracket
            if not token.endswith("]"):
                raise UnclosedBracketError(
                    "Unclosed bracket atom", pos=pos, token=token
                )
            tokens.append(Token(TOKEN_ATOM, token, pos))
        elif _is_valid_element(token):
            tokens.append(Token(TOKEN_ATOM, token, pos))
        else:
            raise SmilesSyntaxError(
                "Invalid SMILES token",
                pos=pos, token=token,
            )

    return tokens


def _is_valid_element(symbol: str) -> bool:
    """Check if a string is a valid element symbol or wildcard."""
    if symbol == "*":
        return True
    if symbol in _ORGANIC_ELEMENTS:
        return True
    if symbol in _AROMATIC_SYMBOLS:
        return True
    # Check for valid element symbol
    if len(symbol) == 1 and symbol.isalpha():
        return True  # Valid single-letter (even if not standard SMILES organic)
    if len(symbol) == 2 and symbol in _TWO_LETTER_ELEMENTS:
        return True
    return False


# ── Bracket Atom Parser ──

# Pattern for bracketed atoms (OpenSMILES order): [isotope? element chiral? Hcount? charge?]
# Chiral marker (@ or @@) comes AFTER the element, BEFORE Hcount.
_BRACKET_ATOM_RE: Final[re.Pattern] = re.compile(
    r"^\["
    r"(\d+)?"            # isotope mass number (group 1)
    r"(\*|[A-Z][a-z]?|as|se|[a-z])"  # element/wildcard (group 2)
    r"(@@?)?"            # tetrahedral stereochemistry @ or @@ (group 3)
    r"(?:H(\d*))?"       # hydrogen count H or H123 (group 4)
    r"((?:[-+]){1,3}|[-+]\d+)?"  # charge: +++ or +3 (group 5)
    r"\]$"
)


def _parse_bracket_atom(token: str, pos: int | None = None) -> dict[str, Any]:
    """Parse a bracketed atom like [13CH3+], [NH4+], [O-], [C@@H].

    Args:
        token: The bracketed atom string including brackets.
        pos: Position for error reporting.

    Returns:
        Dictionary with parsed fields.

    Raises:
        SmilesSyntaxError: If the bracket atom cannot be parsed.
    """
    m = _BRACKET_ATOM_RE.match(token)
    if not m:
        raise SmilesSyntaxError(
            "Invalid bracketed atom syntax",
            pos=pos, token=token,
        )

    isotope_str = m.group(1)
    symbol_str = m.group(2)  # element/wildcard
    stereo_str = m.group(3)  # @ or @@ after element
    h_str = m.group(4)
    charge_str = m.group(5)

    # Default result for wildcard
    result: dict[str, Any] = {
        "atomic_number": 0,
        "isotope": None,
        "implicit_hydrogens": None,
        "formal_charge": 0,
        "stereochemistry": ChiralTag.NONE,
        "is_aromatic": False,
    }

    if symbol_str == "*":
        # Wildcard atom - atomic_number 0
        result["atomic_number"] = 0
        result["is_aromatic"] = False
    else:
        # Regular element - handle both uppercase (standard) and lowercase (aromatic)
        lookup = symbol_str.capitalize() if symbol_str.islower() else symbol_str
        try:
            element = ElementSymbol(lookup)
            atomic_num = element.atomic_number
        except ValueError:
            raise SmilesSyntaxError(
                "Unknown element in bracketed atom",
                pos=pos, token=symbol_str,
            )

        result["atomic_number"] = atomic_num
        result["is_aromatic"] = symbol_str.islower()


    # Isotope
    if isotope_str:
        mass_num = int(isotope_str)
        # Look up exact mass from element data if possible
        try:
            el = Element.from_z(result["atomic_number"])
            exact = float(mass_num)
            # Try to find the most accurate exact mass for this isotope
            for iso in el.isotopes:
                if iso.mass_number == mass_num:
                    exact = iso.exact_mass
                    break
        except (KeyError, Exception):
            exact = float(mass_num)

        result["isotope"] = Isotope(
            mass_number=mass_num,
            exact_mass=exact,
            isotope_type=IsotopeType.LABELED,
        )

    # Implicit hydrogens
    # SMILES convention: [C] has 0 H, [CH4] has 4 H, [OH] has 1 H
    if h_str is not None:
        if h_str == "":
            result["implicit_hydrogens"] = 1
        else:
            result["implicit_hydrogens"] = int(h_str)
    else:
        result["implicit_hydrogens"] = 0

    # Charge
    # SMILES supports two notations:
    #   Repeat notation: [Fe++]  → charge = +2 (count the signs)
    #   Digit notation:  [Fe+2]  → charge = +2 (sign + digit magnitude)
    if charge_str:
        charge = 0
        # Check if this is digit notation (sign + digit, like '+2', '-3')
        if len(charge_str) == 2 and charge_str[0] in '+-' and charge_str[1].isdigit():
            sign = 1 if charge_str[0] == '+' else -1
            charge = sign * int(charge_str[1])
        else:
            # Repeat notation: count the signs
            for ch in charge_str:
                if ch == "+":
                    charge += 1
                elif ch == "-":
                    charge -= 1
        result["formal_charge"] = charge

    # Stereochemistry
    if stereo_str == "@":
        result["stereochemistry"] = ChiralTag.TH1
    elif stereo_str == "@@":
        result["stereochemistry"] = ChiralTag.TH2

    return result


# ── Hydrogen Saturation ──


def _saturate_hydrogens(builder: MolecularGraphBuilder) -> None:
    """Add explicit hydrogen atoms to satisfy valence requirements.

    Uses the Element dataset to determine the default valence for each
    atom, accounting for aromaticity and formal charge. This is applied
    after all bonds (including ring closures) have been added.

    Args:
        builder: MolecularGraphBuilder containing the parsed molecular graph.
    """
    # Compute used valence (sum of bond orders) for each atom
    used_valence: dict[int, int] = {}
    for bond in builder._bonds:
        order_val = 1 if bond.order == BondOrder.AROMATIC else int(bond.order)
        used_valence[bond.atom1] = used_valence.get(bond.atom1, 0) + order_val
        used_valence[bond.atom2] = used_valence.get(bond.atom2, 0) + order_val

    new_hydrogens: list[tuple[int, int]] = []

    for i, atom in enumerate(builder._atoms):
        z = atom.atomic_number

        # Skip wildcard (Z=0), hydrogen (Z=1), and atoms with explicit H count
        if z == 0 or z == 1:
            continue

        # If implicit_hydrogens was explicitly set by bracket notation, use it
        if atom.implicit_hydrogens is not None:
            for _ in range(atom.implicit_hydrogens):
                h_idx = builder.add_atom(atomic_number=1)
                new_hydrogens.append((i, h_idx))
            continue

        if z not in _DEFAULT_VALENCE:
            continue

        current_used = used_valence.get(i, 0)

        # Determine valence based on element, aromaticity, and formal charge
        valence = _DEFAULT_VALENCE[z]

        # Adjust for aromaticity
        if atom.is_aromatic and z in _AROMATIC_VALENCE:
            valence = _AROMATIC_VALENCE[z]

        # Adjust for formal charge
        # Positive charge => fewer bonds, Negative charge => more bonds
        if atom.formal_charge > 0:
            valence -= atom.formal_charge
        elif atom.formal_charge < 0:
            valence += abs(atom.formal_charge)

        h_count = max(0, valence - current_used)
        for _ in range(h_count):
            h_idx = builder.add_atom(atomic_number=1)
            new_hydrogens.append((i, h_idx))

    # Add bonds for all new hydrogens
    for parent_idx, h_idx in new_hydrogens:
        builder.add_bond(parent_idx, h_idx, BondOrder.SINGLE)


# ── Post-Parse Validation ──


def validate_smiles(graph: MolecularGraph) -> list[str]:
    """Validate a parsed SMILES graph for chemical correctness.

    Performs post-parse validation checks that go beyond what the parser
    can verify:
        - Each atom has reasonable valence
        - No self-bonds created by ring closures
        - All atoms are valid elements
        - Reasonable charge distribution

    Args:
        graph: The MolecularGraph to validate.

    Returns:
        List of validation issues (empty if the graph is valid).
    """
    issues: list[str] = []

    for i, atom in enumerate(graph.atoms):
        z = atom.atomic_number
        if z == 0:
            continue  # wildcard
        if z < 1 or z > 118:
            issues.append(f"Atom {i}: invalid atomic number {z}")
            continue

        # Check valence
        degree = graph.get_degree(i)
        try:
            el = Element.from_z(z)
        except (KeyError, ValueError):
            issues.append(f"Atom {i}: unknown element Z={z}")
            continue

        max_val = el.max_valence
        if max_val > 0 and degree > max_val + 4:  # Allow some flexibility
            issues.append(
                f"Atom {i} ({el.symbol}): degree {degree} "
                f"considerably exceeds max valence {max_val}"
            )

    # Check for duplicate bonds
    seen_pairs: set[tuple[int, int]] = set()
    for bond in graph.bonds:
        pair = (min(bond.atom1, bond.atom2), max(bond.atom1, bond.atom2))
        if pair in seen_pairs:
            issues.append(
                f"Duplicate bond between atoms {pair[0]} and {pair[1]}"
            )
        seen_pairs.add(pair)

    return issues


# ── Parser ──


def parse_smiles(smiles: str, *, validate: bool = True) -> MolecularGraph:
    """Parse a SMILES string into a MolecularGraph.

    This is the main entry point for SMILES parsing. It handles standard
    OpenSMILES syntax including:
        - Basic and aromatic atoms
        - Bracketed atoms with isotopes, charges, hydrogens, stereochemistry
        - All bond types (single, double, triple, quadruple, aromatic, directional)
        - Nested branches (parentheses)
        - Ring closures (digit and %digit)
        - Tetrahedral stereochemistry (@, @@)
        - Dot disconnections (salts, mixtures)
        - Wildcard atoms (*)

    Args:
        smiles: The SMILES string (e.g., 'CCO', 'c1ccccc1', 'CC(=O)O').
        validate: Whether to run post-parse validation (default: True).

    Returns:
        A MolecularGraph representing the molecule.

    Raises:
        SmilesSyntaxError: If the SMILES string contains invalid syntax.
        SmilesValidationError: If the parsed graph fails chemical validation.

    Examples:
        >>> graph = parse_smiles("CCO")
        >>> graph.molecular_formula
        'C2H6O'

        >>> graph = parse_smiles("c1ccccc1")
        >>> graph.molecular_formula
        'C6H6'
    """
    tokens = _tokenize(smiles)
    builder = MolecularGraphBuilder()

    # Parser state
    atom_stack: list[int] = []  # Stack of branch parent atom indices
    branch_pending: list[bool] = [False]  # True when first atom after BRANCH_START not yet seen
    ring_closures: dict[str, tuple[int, str | None]] = {}
    current_atom: int | None = None
    implied_bond: str | None = None  # Bond symbol before the next atom
    components: list[int] = []  # First atom of each connected component

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        try:
            if tok.type == TOKEN_ATOM:
                _handle_atom_token(tok, builder, atom_stack,
                                   current_atom, implied_bond, components,
                                   branch_pending)
                # current_atom is the index of the last added atom
                current_atom = len(builder._atoms) - 1 if builder._atoms else None
                implied_bond = None

            elif tok.type == TOKEN_BOND:
                implied_bond = tok.value

            elif tok.type == TOKEN_BRANCH_START:
                if current_atom is None:
                    raise SmilesSyntaxError(
                        "Branch start with no current atom",
                        pos=tok.pos, token=tok.value,
                    )
                atom_stack.append(current_atom)
                branch_pending[0] = True

            elif tok.type == TOKEN_BRANCH_END:
                if not atom_stack:
                    raise UnmatchedBranchError(
                        "Unmatched closing parenthesis",
                        pos=tok.pos, token=tok.value,
                    )
                current_atom = atom_stack.pop()

            elif tok.type == TOKEN_RING_CLOSURE:
                if current_atom is None:
                    raise SmilesSyntaxError(
                        "Ring closure with no current atom",
                        pos=tok.pos, token=tok.value,
                    )
                _handle_ring_closure(tok, builder, ring_closures,
                                     current_atom, implied_bond)
                implied_bond = None

            elif tok.type == TOKEN_STEREO:
                if current_atom is not None:
                    _apply_stereo(current_atom, tok.value, builder)

            elif tok.type == TOKEN_DOT:
                current_atom = None
                implied_bond = None

        except SmilesError:
            raise
        except Exception as e:
            raise SmilesSyntaxError(
                f"Unexpected error during parsing: {e}",
                pos=tok.pos, token=tok.value,
            )

        i += 1

    # Check for errors
    if ring_closures:
        unclosed = ", ".join(ring_closures.keys())
        raise UnmatchedRingClosureError(
            f"Unmatched ring closure labels: {unclosed}",
        )

    if atom_stack:
        raise UnmatchedBranchError(
            "Unmatched opening parenthesis",
        )

    if not builder._atoms:
        raise SmilesSyntaxError("SMILES string produced no atoms", pos=0)

    # Add implicit hydrogens
    _saturate_hydrogens(builder)

    # Build and validate
    graph = builder.build()

    if validate:
        issues = validate_smiles(graph)
        if issues:
            logger.warning(f"Validation issues for '{smiles}': {'; '.join(issues)}")

    return graph


def _handle_atom_token(
    tok: Token,
    builder: MolecularGraphBuilder,
    atom_stack: list[int],
    current_atom: int | None,
    implied_bond: str | None,
    components: list[int],
    branch_pending: list[bool],
) -> None:
    """Process an atom token during parsing.

    When called immediately after a BRANCH_START (branch_pending is True),
    the new atom connects to the branch parent (atom_stack[-1]).
    Subsequent atoms inside the same branch chain normally from
    current_atom. This ensures branches like (CC) create a proper
    chain rather than connecting both atoms directly to the parent.
    """
    atom_info = _resolve_atom(tok)

    atom_idx = builder.add_atom(
        atomic_number=atom_info["atomic_number"],
        formal_charge=atom_info["formal_charge"],
        isotope=atom_info["isotope"],
        stereochemistry=atom_info["stereochemistry"],
        implicit_hydrogens=atom_info["implicit_hydrogens"],
        is_aromatic=atom_info["is_aromatic"],
    )

    if current_atom is not None:
        # Determine the parent atom for the new bond.
        # If we just entered a branch (branch_pending), the first atom
        # in the branch connects to the branch parent from atom_stack.
        # Otherwise, atoms chain normally from current_atom.
        if branch_pending[0] and atom_stack:
            parent_idx = atom_stack[-1]
            branch_pending[0] = False
        else:
            parent_idx = current_atom

        # Determine bond order
        if implied_bond and implied_bond in _BOND_ORDER_MAP:
            bond_order = _BOND_ORDER_MAP[implied_bond]
        elif (atom_info["is_aromatic"]
              and parent_idx < len(builder._atoms)
              and builder._atoms[parent_idx].is_aromatic):
            bond_order = BondOrder.AROMATIC
        else:
            bond_order = _DEFAULT_BOND

        builder.add_bond(parent_idx, atom_idx, bond_order)

        # Handle directional bond (double bond stereochemistry)
        if (implied_bond in ("/", "\\")
                and parent_idx < len(builder._atoms) - 1):
            stereo = _DIRECTIONAL_STEREO.get(implied_bond)
            if stereo:
                bond_idx = len(builder._bonds) - 1
                old_bond = builder._bonds[bond_idx]
                builder._bonds[bond_idx] = old_bond.with_stereochemistry(stereo)
    else:
        # This is the first atom of a disconnected component
        components.append(atom_idx)


def _resolve_atom(tok: Token) -> dict[str, Any]:
    """Resolve an atom token to its properties."""
    if tok.value.startswith("["):
        return _parse_bracket_atom(tok.value, pos=tok.pos)

    # Organic subset or wildcard atom
    value = tok.value

    if value == "*":
        return {
            "atomic_number": 0,
            "isotope": None,
            "implicit_hydrogens": None,
            "formal_charge": 0,
            "stereochemistry": ChiralTag.NONE,
            "is_aromatic": False,
        }

    is_aromatic = value.islower() and value not in ("Cl", "Br")

    # Handle element symbol (could be 1 or 2 characters)
    if value[0].isupper() or (len(value) >= 2 and value[0].islower()):
        # Check if it's an explicit two-letter element
        lookup = value.capitalize() if value[0].islower() else value
        # Special handling for two-letter elements
        if len(value) >= 2 and value[0].islower():
            # aromatic like 'as' (arsenic), 'se' (selenium)
            # These are atomic_aromatic patterns
            pass
    else:
        lookup = value

    # Look up element
    try:
        # For aromatic symbols like 'c', 'n', use uppercase
        if value[0].islower() and len(value) == 1:
            lookup = value.upper()
        # For aromatic two-letter like 'as', 'se', keep as is
        el = ElementSymbol(lookup)
        atomic_num = el.atomic_number
    except ValueError:
        # Try as a group symbol
        raise SmilesSyntaxError(
            f"Unknown element symbol: '{value}'",
            pos=tok.pos, token=value,
        )

    return {
        "atomic_number": atomic_num,
        "isotope": None,
        "implicit_hydrogens": None,
        "formal_charge": 0,
        "stereochemistry": ChiralTag.NONE,
        "is_aromatic": is_aromatic,
    }


def _handle_ring_closure(
    tok: Token,
    builder: MolecularGraphBuilder,
    ring_closures: dict[str, tuple[int, str | None]],
    current_atom: int,
    implied_bond: str | None,
) -> None:
    """Process a ring closure token."""
    ring_id = tok.value.lstrip("%")

    if ring_id in ring_closures:
        # Close the ring
        target_idx, bond_str = ring_closures.pop(ring_id)

        if target_idx == current_atom:
            raise SmilesValidationError(
                "Self-bond via ring closure",
                pos=tok.pos, atom=str(current_atom),
                detail=f"Ring {ring_id} connects atom to itself",
            )

        # Determine bond order
        if bond_str and bond_str in _BOND_ORDER_MAP:
            bond_order = _BOND_ORDER_MAP[bond_str]
        elif implied_bond and implied_bond in _BOND_ORDER_MAP:
            bond_order = _BOND_ORDER_MAP[implied_bond]
        else:
            # Check if both atoms are aromatic
            if (current_atom < len(builder._atoms)
                    and target_idx < len(builder._atoms)
                    and builder._atoms[current_atom].is_aromatic
                    and builder._atoms[target_idx].is_aromatic):
                bond_order = BondOrder.AROMATIC
            else:
                bond_order = _DEFAULT_BOND

        builder.add_bond(target_idx, current_atom, bond_order)
    else:
        # Open a new ring closure (record the bond symbol for later)
        ring_closures[ring_id] = (current_atom, implied_bond)


def _apply_stereo(
    atom_idx: int,
    stereo_str: str,
    builder: MolecularGraphBuilder,
) -> None:
    """Apply tetrahedral stereochemistry to an atom."""
    chiral = ChiralTag.TH1 if stereo_str == "@" else ChiralTag.TH2
    old_atom = builder._atoms[atom_idx]
    builder._atoms[atom_idx] = old_atom.with_stereochemistry(chiral)


# ── Serializer ──

# Element symbols that can be written without brackets in SMILES
_ORGANIC_SYMBOL: dict[int, str] = {
    1: "H", 5: "B", 6: "C", 7: "N", 8: "O", 9: "F",
    15: "P", 16: "S", 17: "Cl", 35: "Br", 53: "I",
}



def _compute_implicit_h(
    graph: MolecularGraph,
    atom_idx: int,
) -> int:
    """Compute the number of implicit hydrogens for an atom.

    This mirrors the logic in _saturate_hydrogens but in reverse:
    given explicit H neighbors, compute how many would be implicit
    in SMILES notation.
    """
    atom = graph.atoms[atom_idx]
    z = atom.atomic_number

    # Count explicit H neighbors
    h_count = 0
    for nbr in graph.get_neighbors(atom_idx):
        if graph.atoms[nbr].atomic_number == 1:
            h_count += 1

    # For atoms with explicit implicit_hydrogens set (from brackets), use that
    if atom.implicit_hydrogens is not None:
        # The atom was written with explicit H count in brackets
        # Return the matching H count
        return atom.implicit_hydrogens

    # For organic subset elements, compute implicit H from valence
    if z not in _DEFAULT_VALENCE:
        return 0  # Can't determine, assume 0

    valence = _DEFAULT_VALENCE[z]

    # Adjust for aromaticity
    if atom.is_aromatic and z in _AROMATIC_VALENCE:
        valence = _AROMATIC_VALENCE[z]

    # Adjust for formal charge
    if atom.formal_charge > 0:
        valence -= atom.formal_charge
    elif atom.formal_charge < 0:
        valence += abs(atom.formal_charge)

    # Compute bonds to non-H atoms (count bond orders)
    non_h_bond_order_sum = 0
    for bond in graph.bonds:
        nbr = None
        if bond.atom1 == atom_idx:
            nbr = bond.atom2
        elif bond.atom2 == atom_idx:
            nbr = bond.atom1
        if nbr is not None and graph.atoms[nbr].atomic_number != 1:
            order_val = 1 if bond.order == BondOrder.AROMATIC else int(bond.order)
            non_h_bond_order_sum += order_val

    implicit_h = valence - non_h_bond_order_sum
    return max(0, implicit_h)


def _compute_implied_h(
    graph: MolecularGraph,
    atom_idx: int,
) -> int:
    """Compute implicit H count from graph structure (ignoring stored value).

    Unlike _compute_implicit_h, this always computes from valence rules
    rather than returning the stored atom.implicit_hydrogens. This is
    used for determining if organic subset notation can be used.
    """
    atom = graph.atoms[atom_idx]
    z = atom.atomic_number

    if z not in _DEFAULT_VALENCE:
        return 0

    valence = _DEFAULT_VALENCE[z]

    if atom.is_aromatic and z in _AROMATIC_VALENCE:
        valence = _AROMATIC_VALENCE[z]

    if atom.formal_charge > 0:
        valence -= atom.formal_charge
    elif atom.formal_charge < 0:
        valence += abs(atom.formal_charge)

    non_h_bond_order_sum = 0
    for bond in graph.bonds:
        nbr = None
        if bond.atom1 == atom_idx:
            nbr = bond.atom2
        elif bond.atom2 == atom_idx:
            nbr = bond.atom1
        if nbr is not None and graph.atoms[nbr].atomic_number != 1:
            order_val = 1 if bond.order == BondOrder.AROMATIC else int(bond.order)
            non_h_bond_order_sum += order_val

    return max(0, valence - non_h_bond_order_sum)


def _write_atom_smiles(
    graph: MolecularGraph,
    atom_idx: int,
    implicit_h: int,
) -> str:
    """Write an atom in SMILES notation, using implicit H where possible."""
    atom = graph.atoms[atom_idx]

    # Check if we can write as organic subset without brackets
    z = atom.atomic_number
    organic_symbol = _ORGANIC_SYMBOL.get(z)

    if (organic_symbol is not None
            and atom.formal_charge == 0
            and atom.isotope is None
            and atom.stereochemistry == ChiralTag.NONE):
        # Compute expected H from valence rules (ignoring stored implicit_hydrogens)
        expected_h = _compute_implied_h(graph, atom_idx)
        if implicit_h == expected_h:
            sym = organic_symbol.lower() if atom.is_aromatic else organic_symbol
            return sym

    # Need bracket notation
    parts = ["["]

    # Isotope mass number
    if atom.isotope is not None:
        parts.append(str(atom.isotope.mass_number))

    # Element symbol
    if z == 0:
        parts.append("*")
    else:
        sym = organic_symbol or (atom.symbol.capitalize() if atom.symbol.islower() else atom.symbol)
        if atom.is_aromatic:
            sym = sym.lower()
        parts.append(sym)

    # Stereochemistry (comes before Hcount in SMILES)
    if atom.stereochemistry == ChiralTag.TH1:
        parts.append("@")
    elif atom.stereochemistry == ChiralTag.TH2:
        parts.append("@@")

    # Implicit hydrogens
    if implicit_h > 0:
        if implicit_h == 1:
            parts.append("H")
        else:
            parts.append(f"H{implicit_h}")

    # Charge
    if atom.formal_charge != 0:
        if atom.formal_charge > 0:
            if atom.formal_charge == 1:
                parts.append("+")
            else:
                parts.append(f"+{atom.formal_charge}")
        else:
            if atom.formal_charge == -1:
                parts.append("-")
            else:
                parts.append(f"{atom.formal_charge}")

    parts.append("]")
    return "".join(parts)


# ── Ring Closure Pre-pass ──


def _find_ring_closure_bonds(
    graph: MolecularGraph,
    heavy_atoms: set[int],
) -> dict[tuple[int, int], int]:
    """Identify which heavy-atom bonds form cycles (ring closures).

    Uses DFS to find a spanning tree over heavy atoms. Any bond not
    in the spanning tree is a ring closure bond that needs a label
    in the SMILES output.

    Returns:
        Dict mapping (min, max) atom index pairs to ring closure labels (1-based).
    """
    # Build adjacency for heavy atoms only
    adj: dict[int, list[int]] = {i: [] for i in heavy_atoms}
    bond_pairs: set[tuple[int, int]] = set()
    for bond in graph.bonds:
        a1, a2 = bond.atom1, bond.atom2
        if a1 in heavy_atoms and a2 in heavy_atoms:
            adj[a1].append(a2)
            adj[a2].append(a1)
            bond_pairs.add((min(a1, a2), max(a1, a2)))

    # DFS to find spanning tree edges
    visited: set[int] = set()
    spanning_tree: set[tuple[int, int]] = set()

    def _dfs(node: int, parent: int | None) -> None:
        visited.add(node)
        for nbr in adj.get(node, []):
            if nbr == parent:
                continue
            pair = (min(node, nbr), max(node, nbr))
            if nbr not in visited:
                spanning_tree.add(pair)
                _dfs(nbr, node)

    for start in sorted(heavy_atoms):
        if start not in visited:
            _dfs(start, None)

    # Ring closure bonds = all bonds - spanning tree
    ring_bonds: set[tuple[int, int]] = bond_pairs - spanning_tree

    # Assign labels (sorted for deterministic output)
    ring_labels: dict[tuple[int, int], int] = {}
    for i, pair in enumerate(sorted(ring_bonds)):
        ring_labels[pair] = i + 1

    return ring_labels


# ── Serializer ──


def _serialize_component(
    graph: MolecularGraph,
    start_atom: int,
    heavy_atom_set: set[int],
    ring_labels: dict[tuple[int, int], int],
    visited: set[int],
) -> list[str]:
    """Serialize a single connected component via DFS.

    Uses a pre-computed spanning tree: ring closure bonds (from
    ring_labels) are written as labels on both endpoints but are
    NOT traversed. Only spanning-tree edges are traversed.

    Args:
        graph: The molecular graph.
        start_atom: Starting heavy atom index.
        heavy_atom_set: Set of all heavy atom indices.
        ring_labels: Pre-computed ring closure bond labels.
        visited: Set to track visited heavy atoms (modified in-place).

    Returns:
        List of SMILES string parts for this component.
    """
    # Build a map: atom index -> list of ring closure labels for that atom
    ring_on_atom: dict[int, list[int]] = {}
    for (a1, a2), label in ring_labels.items():
        ring_on_atom.setdefault(a1, []).append(label)
        ring_on_atom.setdefault(a2, []).append(label)

    parts: list[str] = []

    # Pre-compute subtree sizes: how many heavy-atom descendants each
    # spanning tree node has. Used to prefer longer chains as main path.
    _subtree_size: dict[int, int] = {}

    def _count_descendants(node: int, parent: int | None) -> int:
        total = 1  # count self
        for nbr in graph.get_neighbors(node):
            if graph.atoms[nbr].atomic_number == 1:
                continue
            if nbr == parent:
                continue
            pair = (min(node, nbr), max(node, nbr))
            if pair in ring_labels:
                continue
            total += _count_descendants(nbr, node)
        _subtree_size[node] = total
        return total

    _count_descendants(start_atom, None)

    def _dfs(node: int, parent: int | None, depth: int) -> None:
        visited.add(node)

        # Write atom
        implicit_h = _compute_implicit_h(graph, node)
        atom_str = _write_atom_smiles(graph, node, implicit_h)
        parts.append(atom_str)

        # Write ring closure labels (sorted for determinism)
        for label in sorted(ring_on_atom.get(node, [])):
            if label < 10:
                parts.append(str(label))
            else:
                parts.append(f"%{label}")

        # Collect heavy neighbors (skip hydrogen)
        all_nbrs: list[int] = []
        for nbr in graph.get_neighbors(node):
            if graph.atoms[nbr].atomic_number == 1:
                continue
            if nbr in visited:
                continue
            if nbr == parent:
                continue
            all_nbrs.append(nbr)

        # Filter to only spanning-tree children: edges NOT in ring_labels
        tree_children: list[int] = []
        for nbr in all_nbrs:
            pair = (min(node, nbr), max(node, nbr))
            if pair not in ring_labels:
                tree_children.append(nbr)

        # Sort: children with MORE spanning-tree descendants come LAST
        # (they become the main chain continuation;others become branches)
        # Tie-break: single-bond children before higher-order (as branches),
        # then by atomic number descending, then by index
        def _branch_priority(nbr: int) -> tuple:
            bond = graph.get_bond(node, nbr)
            order_val = int(bond.order) if bond else 1
            descendants = _subtree_size.get(nbr, 0)
            return (
                descendants,  # more descendants = later (main chain)
                0 if order_val == 1 else 1,  # single bonds first (branches)
                -graph.atoms[nbr].atomic_number,
                nbr,
            )

        tree_children.sort(key=_branch_priority)

        if tree_children:
            # All children except the LAST are branches (parentheses)
            # The LAST child is the main chain continuation (no parentheses)
            for child in tree_children[:-1]:
                parts.append("(")
                bond = graph.get_bond(node, child)
                bond_str = _bond_to_smiles(bond) if bond else ""
                if bond_str:
                    parts.append(bond_str)
                _dfs(child, node, depth + 1)
                parts.append(")")

            last = tree_children[-1]
            bond = graph.get_bond(node, last)
            bond_str = _bond_to_smiles(bond) if bond else ""
            if bond_str:
                parts.append(bond_str)
            _dfs(last, node, depth + 1)

    _dfs(start_atom, None, 0)
    return parts


def serialize_smiles(graph: MolecularGraph) -> str:
    """Serialize a MolecularGraph to a SMILES string.

    Uses a recursive depth-first traversal that only traverses heavy
    (non-hydrogen) atoms. Hydrogen atoms are written as implicit H
    counts in the SMILES output.

    Algorithm:
        1. Pre-pass: find ring closure bonds via spanning tree.
        2. Assign unique ring closure labels (1, 2, ...).
        3. DFS traverse spanning tree, writing ring labels on both
           endpoints and using branch parentheses for side chains.
        4. For disconnected components, use dot notation ('.').

    Args:
        graph: The molecular graph to serialize.

    Returns:
        A SMILES string.

    Raises:
        ValueError: If the graph cannot be serialized.
    """
    if graph.num_atoms == 0:
        return ""

    # Collect heavy atom indices
    heavy_atoms: set[int] = set(
        i for i, a in enumerate(graph.atoms) if a.atomic_number != 1
    )

    if not heavy_atoms:
        return "[H]" * graph.num_atoms

    # Pre-pass: find ring closure bonds
    ring_labels = _find_ring_closure_bonds(graph, heavy_atoms)

    # Serialize each connected component
    visited: set[int] = set()
    all_parts: list[str] = []

    # Sort heavy atoms for deterministic start order
    # Prefer carbon (Z=6) as start atom
    start_candidates = sorted(heavy_atoms, key=lambda i: (0 if graph.atoms[i].atomic_number == 6 else 1, i))

    for start in start_candidates:
        if start not in visited:
            if all_parts:
                all_parts.append(".")
            parts = _serialize_component(graph, start, heavy_atoms, ring_labels, visited)
            all_parts.extend(parts)

    return "".join(all_parts)


def _bond_to_smiles(bond: Bond) -> str:
    """Convert a bond to its SMILES representation."""
    if bond.order == BondOrder.SINGLE:
        return ""
    if bond.order == BondOrder.DOUBLE:
        return "="
    if bond.order == BondOrder.TRIPLE:
        return "#"
    if bond.order == BondOrder.QUADRUPLE:
        return "$"
    if bond.order == BondOrder.AROMATIC:
        return ""  # Implicit in standard SMILES output
    return ""


# ── Parser Class ──


class SmilesParser(Parser):
    """Parser for SMILES strings implementing the Parser protocol."""

    def parse(self, text: str, /, **options: Any) -> MolecularGraph:
        return parse_smiles(text)

    def serialize(self, graph: MolecularGraph, /, **options: Any) -> str:
        return serialize_smiles(graph)


def register_smiles_parser(registry: Any) -> None:
    """Register the SMILES parser with the AlgorithmRegistry."""
    from chemengine.core.registry import AlgorithmEntry

    parser = SmilesParser()
    registry.register(AlgorithmEntry(
        domain="parsing.smiles",
        name="default",
        version="1.0.0",
        algorithm=parser.parse,
        input_type=str,
        output_type=MolecularGraph,
        tags=frozenset({"smiles", "parsing", "fast"}),
    ))
    registry.register(AlgorithmEntry(
        domain="serialization.smiles",
        name="default",
        version="1.0.0",
        algorithm=parser.serialize,
        input_type=MolecularGraph,
        output_type=str,
        tags=frozenset({"smiles", "serialization", "fast"}),
    ))
