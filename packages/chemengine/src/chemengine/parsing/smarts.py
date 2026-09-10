"""SMARTS pattern parser and matcher for substructure queries.

Provides:
    - parse_smarts(): Convert SMARTS string to a QueryGraph
    - smarts_match(): Check if a SMARTS pattern matches a molecule
    - smarts_findall(): Find all matches of a SMARTS pattern
    - smarts_count(): Count matches of a SMARTS pattern

Supported SMARTS features:
    Atom properties: element, aromatic, charge, isotope, hcount, degree,
                     ring, chirality, total connections
    Bond types: single, double, triple, aromatic, any (~), not (!)
    Boolean operators: ! (NOT), & (AND), , (OR), ; (AND without implicit AND)
    Atom lists: [N,O], [C,N,O]
    Recursive patterns: [$(...)]
    Ring closures: C1CC1
    Branches: C(C)C
    Disconnected: C.O
"""

from __future__ import annotations

import re
from typing import Any

from chemengine.core.bonds import BondOrder
from chemengine.core.enums import ChiralTag
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder

# ── Query Predicates ──


class QueryAtom:
    """An atom predicate that matches target atoms based on properties."""

    def __init__(self) -> None:
        self.atomic_number: int | None = None  # None = any
        self.is_aromatic: bool | None = None  # None = don't care
        self.formal_charge: int | None = None
        self.isotope: int | None = None
        self.implicit_hydrogens: int | None = None
        self.total_hydrogens: int | None = None
        self.degree: int | None = None  # number of heavy-atom neighbors
        self.total_connections: int | None = None  # X: total connections (incl H)
        self.valence: int | None = None
        self.is_ring: bool | None = None
        self.ring_size: int | None = None  # rN: in ring of size N
        self.chirality: ChiralTag | None = None
        self.isotope_min: int | None = None
        self.isotope_max: int | None = None

        # Negation flags
        self.not_atomic_number: bool = False
        self.not_aromatic: bool = False
        self.not_charge: bool = False
        self.not_ring: bool = False
        self.not_hcount: bool = False
        self.not_degree: bool = False

        # Atom lists (for [N,O] style)
        self.atom_list: list[int] | None = None

        # Recursive query (for [$(...)])
        self.recursive_smarts: str | None = None

        # Matched atom indices from last match (for reporting)
        self.matched_indices: list[int] = []

    def matches(self, graph: MolecularGraph, atom_idx: int) -> bool:
        """Check if this query atom matches a specific atom in the graph."""
        atom = graph.atoms[atom_idx]

        # Atomic number
        if self.atomic_number is not None:
            if self.not_atomic_number:
                if atom.atomic_number == self.atomic_number:
                    return False
            else:
                if atom.atomic_number != self.atomic_number:
                    return False

        # Atom list
        if self.atom_list is not None:
            if atom.atomic_number not in self.atom_list:
                return False

        # Aromaticity
        if self.is_aromatic is not None:
            if self.not_aromatic:
                if atom.is_aromatic == self.is_aromatic:
                    return False
            else:
                if atom.is_aromatic != self.is_aromatic:
                    return False

        # Formal charge
        if self.formal_charge is not None:
            if self.not_charge:
                if atom.formal_charge == self.formal_charge:
                    return False
            else:
                if atom.formal_charge != self.formal_charge:
                    return False

        # Isotope
        if self.isotope is not None:
            # atom.isotope is None (regular) or Isotope object
            if atom.isotope is None:
                atom_iso = 0
            elif hasattr(atom.isotope, 'mass_number'):
                atom_iso = atom.isotope.mass_number
            else:
                atom_iso = int(atom.isotope)
            if atom_iso != self.isotope:
                return False

        # Implicit hydrogen count
        if self.implicit_hydrogens is not None:
            ih = atom.implicit_hydrogens if atom.implicit_hydrogens is not None else 0
            if self.not_hcount:
                if ih == self.implicit_hydrogens:
                    return False
            else:
                if ih != self.implicit_hydrogens:
                    return False

        # Total hydrogen count (implicit + explicit)
        if self.total_hydrogens is not None:
            th = sum(1 for n in graph.get_neighbors(atom_idx)
                     if graph.atoms[n].atomic_number == 1)
            if self.total_hydrogens != th:
                return False

        # Degree (number of heavy-atom neighbors)
        if self.degree is not None:
            deg = sum(1 for n in graph.get_neighbors(atom_idx)
                      if graph.atoms[n].atomic_number != 1)
            if self.not_degree:
                if deg == self.degree:
                    return False
            else:
                if deg != self.degree:
                    return False

        # Total connections (X: total neighbors including H)
        if self.total_connections is not None:
            xc = len(list(graph.get_neighbors(atom_idx)))
            if xc != self.total_connections:
                return False

        # Ring membership
        if self.is_ring is not None:
            # Check if atom is in any ring
            from chemengine.detection.rings import is_ring_atom
            in_ring = is_ring_atom(graph, atom_idx)
            if self.not_ring:
                if in_ring:
                    return False
            else:
                if not in_ring:
                    return False

        # Ring size
        if self.ring_size is not None:
            from chemengine.detection.rings import detect_rings
            rings = detect_rings(graph)
            in_size_ring = any(
                r.size == self.ring_size and atom_idx in r.atom_indices
                for r in rings
            )
            if not in_size_ring:
                return False

        # Chirality
        if self.chirality is not None:
            if atom.stereochemistry != self.chirality:
                return False

        # Recursive query
        if self.recursive_smarts is not None:
            from chemengine.parsing.smarts import smarts_match
            # Build a subgraph around this atom and match
            # For simplicity, match the recursive pattern against the whole molecule
            if not smarts_match(self.recursive_smarts, graph):
                return False

        return True

    def __repr__(self) -> str:
        parts = []
        if self.atomic_number is not None:
            parts.append(f"Z={self.atomic_number}")
        if self.is_aromatic is not None:
            parts.append(f"arom={self.is_aromatic}")
        if self.formal_charge is not None:
            parts.append(f"charge={self.formal_charge}")
        if self.atom_list is not None:
            parts.append(f"list={self.atom_list}")
        if self.recursive_smarts is not None:
            parts.append(f"recurse={self.recursive_smarts}")
        return f"QueryAtom({', '.join(parts)})"


class QueryBond:
    """A bond predicate that matches target bonds based on properties."""

    def __init__(self) -> None:
        self.order: BondOrder | None = None  # None = any
        self.is_aromatic: bool | None = None
        self.not_order: bool = False
        self.is_any: bool = False  # ~: any bond
        self.is_ring: bool | None = None
        self.direction: str | None = None  # / or \\ for cis/trans

    def matches(self, graph: MolecularGraph, bond_idx: int) -> bool:
        """Check if this query bond matches a specific bond in the graph."""
        bond = graph.bonds[bond_idx]

        # Any bond (~)
        if self.is_any:
            return True

        # Bond order
        if self.order is not None:
            if self.not_order:
                if bond.order == self.order:
                    return False
            else:
                if bond.order != self.order:
                    return False

        # Aromatic
        if self.is_aromatic is not None:
            if self.is_aromatic:
                if bond.order != BondOrder.AROMATIC:
                    return False
            else:
                if bond.order == BondOrder.AROMATIC:
                    return False

        # Ring bond
        if self.is_ring is not None:
            from chemengine.detection.rings import is_ring_bond
            in_ring = is_ring_bond(graph, bond_idx)
            if self.is_ring != in_ring:
                return False

        return True

    def __repr__(self) -> str:
        parts = []
        if self.order is not None:
            parts.append(f"order={self.order}")
        if self.is_any:
            parts.append("any")
        return f"QueryBond({', '.join(parts)})"


class QueryGraph:
    """A graph of QueryAtoms connected by QueryBonds for substructure matching.

    This is the internal representation used by the query engine.
    For backward compatibility, parse_smarts() returns a MolecularGraph.
    """

    def __init__(self) -> None:
        self.atoms: list[QueryAtom] = []
        self.bonds: list[tuple[int, int, QueryBond]] = []  # (i, j, query_bond)
        self.adjacency: dict[int, list[int]] = {}

    def add_atom(self, atom: QueryAtom) -> int:
        idx = len(self.atoms)
        self.atoms.append(atom)
        self.adjacency[idx] = []
        return idx

    def add_bond(self, i: int, j: int, bond: QueryBond) -> None:
        self.bonds.append((i, j, bond))
        self.adjacency[i].append(j)
        self.adjacency[j].append(i)

    def get_bond_query(self, i: int, j: int) -> QueryBond | None:
        for a, b, qb in self.bonds:
            if (a == i and b == j) or (a == j and b == i):
                return qb
        return None

    def __repr__(self) -> str:
        return f"QueryGraph(atoms={len(self.atoms)}, bonds={len(self.bonds)})"


# Module-level cache for parsed SMARTS patterns
_query_graph_cache: dict[str, QueryGraph] = {}


# ── Tokenizer ──

# Token types: bracket_atom, simple_atom, bond, ring, branch, dot, recursive
_BRACKET_ATOM_RE = re.compile(r'\[(.+?)\]')
_BOND_RE = re.compile(r'[=#@:~!/\-]')
_RING_RE = re.compile(r'%(\d+)|(\d+)')


def _tokenize(pattern: str) -> list[dict[str, Any]]:
    """Tokenize a SMARTS pattern into a list of tokens."""
    tokens = []
    i = 0

    while i < len(pattern):
        c = pattern[i]

        if c == '[':
            # Bracket atom — find matching ']'
            j = i + 1
            depth = 1
            while j < len(pattern) and depth > 0:
                if pattern[j] == '[':
                    depth += 1
                elif pattern[j] == ']':
                    depth -= 1
                j += 1
            content = pattern[i+1:j-1]
            tokens.append({'type': 'bracket_atom', 'content': content, 'pos': i})
            i = j

        elif c == '(':
            tokens.append({'type': 'branch_open', 'pos': i})
            i += 1

        elif c == ')':
            tokens.append({'type': 'branch_close', 'pos': i})
            i += 1

        elif c == '.':
            tokens.append({'type': 'dot', 'pos': i})
            i += 1

        elif c == '$' and i + 1 < len(pattern) and pattern[i+1] == '(':
            # Recursive pattern — find matching ')'
            j = i + 2
            depth = 1
            while j < len(pattern) and depth > 0:
                if pattern[j] == '(':
                    depth += 1
                elif pattern[j] == ')':
                    depth -= 1
                j += 1
            content = pattern[i+2:j-1]
            tokens.append({'type': 'recursive', 'content': content, 'pos': i})
            i = j

        elif c == '%' and i + 2 < len(pattern) and pattern[i+1:i+3].isdigit():
            # Ring number > 9: %10, %11, etc.
            ring_num = int(pattern[i+1:i+3])
            tokens.append({'type': 'ring', 'number': ring_num, 'pos': i})
            i += 3

        elif c.isdigit():
            # Ring closure digit
            ring_num = int(c)
            tokens.append({'type': 'ring', 'number': ring_num, 'pos': i})
            i += 1

        elif c in ('=', '#', '@', ':', '~', '/', '\\', '-', '!'):
            # Bond symbol (but - is also used for negation in brackets)
            # ! = NOT bond prefix
            if c == '!' and i + 1 < len(pattern) and pattern[i+1] == '=':
                tokens.append({'type': 'bond', 'symbol': '!=', 'pos': i})
                i += 2
            elif c == '!' and i + 1 < len(pattern) and pattern[i+1] == '#':
                tokens.append({'type': 'bond', 'symbol': '!#', 'pos': i})
                i += 2
            elif c == '!' and i + 1 < len(pattern) and pattern[i+1] == ':':
                tokens.append({'type': 'bond', 'symbol': '!:', 'pos': i})
                i += 2
            elif c == '!' and i + 1 < len(pattern) and pattern[i+1] == '~':
                tokens.append({'type': 'bond', 'symbol': '!~', 'pos': i})
                i += 2
            elif c == '-' and i + 1 < len(pattern) and pattern[i+1] in ('(', '[', ')'):
                tokens.append({'type': 'bond', 'symbol': '-', 'pos': i})
                i += 1
            else:
                tokens.append({'type': 'bond', 'symbol': c, 'pos': i})
                i += 1

        elif c == '*':
            # Wildcard atom
            tokens.append({'type': 'wildcard', 'pos': i})
            i += 1

        elif c.isalpha():
            # Simple atom symbol (uppercase = aliphatic, lowercase = aromatic)
            tokens.append({'type': 'simple_atom', 'symbol': c, 'pos': i})
            i += 1

        else:
            i += 1

    return tokens


# ── Bracket Atom Parser ──

def _parse_bracket_content(content: str) -> QueryAtom:
    """Parse the content inside [... ] brackets into a QueryAtom."""
    qa = QueryAtom()
    i = 0

    # Check for negation at start: [!C]
    negated = False
    if i < len(content) and content[i] == '!':
        negated = True
        i += 1

    # Check for properties that start with specific letters
    # R/r = ring, A/a = aliphatic/aromatic, H/h = hydrogen, D = degree,
    # X = total connections, v = valence, +/– = charge, @ = chirality
    # These must be checked BEFORE element parsing
    _PROPERTY_LETTERS = set('RrAaHhDdXxvV+')

    if i < len(content) and content[i] in _PROPERTY_LETTERS:
        # This starts with a property, not an element
        # Don't parse as element — fall through to property parsing below
        pass

    elif i < len(content):
        # Parse element specification
        if content[i] == '#':
            # Atomic number: [#6], [#7]
            i += 1
            num_str = ''
            while i < len(content) and content[i].isdigit():
                num_str += content[i]
                i += 1
            if num_str:
                qa.atomic_number = int(num_str)
                if negated:
                    qa.not_atomic_number = True

        elif content[i].isdigit():
            # Isotope number: [13C], [14N]
            num_str = ''
            while i < len(content) and content[i].isdigit():
                num_str += content[i]
                i += 1
            qa.isotope = int(num_str)
            # After isotope, parse element if present
            if i < len(content) and content[i].isalpha() and content[i] not in _PROPERTY_LETTERS:
                el = content[i]
                i += 1
                if (i < len(content) and content[i].isalpha()
                        and content[i].islower()):
                    candidate = el + content[i]
                    candidate_title = candidate[0].upper() + candidate[1].lower()
                    from chemengine.core.enums import ElementSymbol
                    try:
                        ElementSymbol(candidate_title)
                        el = candidate
                        i += 1
                    except ValueError:
                        pass
                el_title = el[0].upper() + el[1:].lower() if len(el) > 1 else el.upper()
                from chemengine.core.enums import ElementSymbol
                try:
                    z = ElementSymbol(el_title).atomic_number
                    qa.atomic_number = z
                    if negated:
                        qa.not_atomic_number = True
                except ValueError:
                    pass

        elif content[i] == '*':
            # Wildcard: matches any atom (atomic_number stays None = any)
            i += 1

        elif content[i].isalpha() and content[i] not in _PROPERTY_LETTERS:
            # Element symbol or atom list
            # Lowercase first letter = aromatic (e.g., [c] = aromatic carbon)
            elements = []
            aromatic_flags = []
            while i < len(content) and (
                (content[i].isalpha() and content[i] not in _PROPERTY_LETTERS)
                or content[i] == ','
            ):
                if content[i] == ',':
                    i += 1
                    continue
                is_arom_el = content[i].islower()
                el = content[i]
                i += 1
                # Check for second letter of element symbol
                # Must be lowercase and form a valid two-letter element
                if (i < len(content) and content[i].isalpha()
                        and content[i].islower()):
                    # Check if this forms a valid two-letter element
                    candidate = el + content[i]
                    candidate_title = candidate[0].upper() + candidate[1].lower()
                    from chemengine.core.enums import ElementSymbol
                    try:
                        ElementSymbol(candidate_title)
                        # Valid two-letter element, consume it
                        el = candidate
                        i += 1
                    except ValueError:
                        # Not a valid element, don't consume
                        pass
                # Title case for ElementSymbol (e.g., 'br' → 'Br')
                el_title = el[0].upper() + el[1:].lower() if len(el) > 1 else el.upper()
                from chemengine.core.enums import ElementSymbol
                try:
                    z = ElementSymbol(el_title).atomic_number
                    elements.append(z)
                    aromatic_flags.append(is_arom_el)
                except ValueError:
                    pass

            if len(elements) == 1:
                qa.atomic_number = elements[0]
                if aromatic_flags[0]:
                    qa.is_aromatic = True
                if negated:
                    qa.not_atomic_number = True
            elif len(elements) > 1:
                qa.atom_list = elements
        else:
            i += 1

    # Parse remaining properties
    while i < len(content):
        c = content[i]

        if c == 'x':
            # X: total connections (including H)
            i += 1
            num = ''
            while i < len(content) and content[i].isdigit():
                num += content[i]
                i += 1
            if num:
                qa.total_connections = int(num)
            else:
                qa.total_connections = 1  # X alone means 1 connection

        elif c == 'D':
            # D: degree (number of non-H neighbors)
            i += 1
            num = ''
            while i < len(content) and content[i].isdigit():
                num += content[i]
                i += 1
            if num:
                qa.degree = int(num)
            else:
                qa.degree = 1

        elif c == 'H':
            # H: total hydrogen count
            i += 1
            num = ''
            while i < len(content) and content[i].isdigit():
                num += content[i]
                i += 1
            if num:
                qa.total_hydrogens = int(num)
            else:
                qa.total_hydrogens = 1

        elif c == 'h':
            # h: implicit hydrogen count
            i += 1
            num = ''
            while i < len(content) and content[i].isdigit():
                num += content[i]
                i += 1
            if num:
                qa.implicit_hydrogens = int(num)
            else:
                qa.implicit_hydrogens = 1

        elif c == 'R':
            # R: ring atom
            i += 1
            qa.is_ring = True

        elif c == 'r':
            # rN: ring of size N, or r = any ring atom
            i += 1
            num = ''
            while i < len(content) and content[i].isdigit():
                num += content[i]
                i += 1
            if num:
                qa.ring_size = int(num)
            else:
                qa.is_ring = True  # bare r = any ring atom

        elif c == 'v':
            # vN: valence
            i += 1
            num = ''
            while i < len(content) and content[i].isdigit():
                num += content[i]
                i += 1
            if num:
                qa.valence = int(num)

        elif c == '@':
            # Chirality
            i += 1
            if i < len(content) and content[i] == '@':
                qa.chirality = ChiralTag.TH2
                i += 1
            else:
                qa.chirality = ChiralTag.TH1

        elif c == '+':
            # Charge: +, +2, ++, etc.
            i += 1
            if i < len(content) and content[i] == '+':
                qa.formal_charge = 2
                i += 1
            elif i < len(content) and content[i].isdigit():
                num = ''
                while i < len(content) and content[i].isdigit():
                    num += content[i]
                    i += 1
                qa.formal_charge = int(num)
            else:
                qa.formal_charge = 1

        elif c == '-':
            # Charge: -, -2, --, etc.
            i += 1
            if i < len(content) and content[i] == '-':
                qa.formal_charge = -2
                i += 1
            elif i < len(content) and content[i].isdigit():
                num = ''
                while i < len(content) and content[i].isdigit():
                    num += content[i]
                    i += 1
                qa.formal_charge = -int(num)
            else:
                qa.formal_charge = -1

        elif c == 'a':
            # Aromatic (lowercase a in bracket)
            qa.is_aromatic = True
            i += 1

        elif c == 'A':
            # Aliphatic (uppercase A in bracket)
            qa.is_aromatic = False
            i += 1

        elif c == '^':
            # Skip hybridization state (^0, ^1, ^2, ^3, ^4)
            i += 1
            while i < len(content) and content[i].isdigit():
                i += 1

        else:
            i += 1

    return qa


# ── SMARTS Parser ──


def parse_smarts(pattern: str) -> MolecularGraph:
    """Parse a SMARTS pattern into a query MolecularGraph.

    Returns a MolecularGraph for backward compatibility with existing code.
    The graph contains wildcard atoms (atomic_number=0) and aromaticity flags.

    For advanced query predicates (charge, ring, degree, etc.), use
    smarts_match() which internally builds a QueryGraph with full predicates.

    Supports:
        - Element symbols: C, N, O, c, n, o
        - Atomic numbers: [#6], [#7]
        - Bond types: -, =, #, :, ~
        - Branches: C(C)C, CC(=O)O
        - Ring closures: C1CC1, c1ccccc1
        - Disconnected: C.O
        - Wildcard: *

    Args:
        pattern: SMARTS pattern string.

    Returns:
        A MolecularGraph representing the query.
    """
    qg = _parse_query_graph(pattern)
    return _make_query_graph_from_query(qg)


def _parse_query_graph(pattern: str) -> QueryGraph:
    """Parse a SMARTS pattern into a QueryGraph (internal)."""
    # Check cache
    if pattern in _query_graph_cache:
        return _query_graph_cache[pattern]

    tokens = _tokenize(pattern)
    qg = QueryGraph()

    # Stack for branches: (parent_atom_idx, bond_query)
    branch_stack: list[int] = []
    # Current attachment point
    attachment: int | None = None
    # Pending bond query for next connection
    pending_bond: QueryBond | None = None
    # Ring closures: ring_num -> (atom_idx, bond_query)
    ring_closures: dict[int, tuple[int, QueryBond | None]] = {}

    for token in tokens:
        ttype = token['type']

        if ttype == 'bracket_atom':
            qa = _parse_bracket_content(token['content'])
            idx = qg.add_atom(qa)

            if attachment is not None:
                qb = pending_bond or QueryBond()
                qg.add_bond(attachment, idx, qb)
                pending_bond = None

            attachment = idx

        elif ttype == 'wildcard':
            qa = QueryAtom()  # wildcard: matches any atom
            idx = qg.add_atom(qa)

            if attachment is not None:
                qb = pending_bond or QueryBond()
                qg.add_bond(attachment, idx, qb)
                pending_bond = None

            attachment = idx

        elif ttype == 'simple_atom':
            qa = QueryAtom()
            sym = token['symbol']
            if sym.islower():
                from chemengine.core.enums import ElementSymbol
                try:
                    z = ElementSymbol(sym.upper()).atomic_number
                except ValueError:
                    z = 6
                qa.atomic_number = z
                qa.is_aromatic = True
            else:
                from chemengine.core.enums import ElementSymbol
                try:
                    z = ElementSymbol(sym).atomic_number
                except ValueError:
                    z = 6
                qa.atomic_number = z
                qa.is_aromatic = False

            idx = qg.add_atom(qa)

            if attachment is not None:
                qb = pending_bond or QueryBond()
                if (qa.is_aromatic and
                    attachment is not None and
                    qg.atoms[attachment].is_aromatic):
                    qb.order = BondOrder.AROMATIC
                qg.add_bond(attachment, idx, qb)
                pending_bond = None

            attachment = idx

        elif ttype == 'bond':
            sym = token['symbol']
            qb = QueryBond()
            if sym == '-':
                qb.order = BondOrder.SINGLE
            elif sym == '=':
                qb.order = BondOrder.DOUBLE
            elif sym == '#':
                qb.order = BondOrder.TRIPLE
            elif sym == ':':
                qb.order = BondOrder.AROMATIC
            elif sym == '~':
                qb.is_any = True
            elif sym == '!':
                pending_bond = qb
                continue
            elif sym == '!=':
                qb.order = BondOrder.DOUBLE
                qb.not_order = True
            elif sym == '!#':
                qb.order = BondOrder.TRIPLE
                qb.not_order = True
            elif sym == '!:' :
                qb.order = BondOrder.AROMATIC
                qb.not_order = True
            elif sym == '!~':
                qb.is_any = True
                qb.not_order = True
            elif sym == '/':
                qb.direction = '/'
            elif sym == '\\':
                qb.direction = '\\'
            pending_bond = qb

        elif ttype == 'ring':
            ring_num = token['number']
            # Ring 0 is ignored in SMARTS
            if ring_num == 0:
                pending_bond = None
                continue
            if attachment is not None:
                if ring_num not in ring_closures:
                    ring_closures[ring_num] = (attachment, pending_bond)
                    pending_bond = None
                else:
                    prev_idx, prev_bond = ring_closures.pop(ring_num)
                    # Prevent self-bonds
                    if prev_idx != attachment:
                        qb = pending_bond or prev_bond or QueryBond()
                        qg.add_bond(prev_idx, attachment, qb)
                    pending_bond = None

        elif ttype == 'branch_open':
            if attachment is not None:
                branch_stack.append(attachment)
            pending_bond = None

        elif ttype == 'branch_close':
            if branch_stack:
                attachment = branch_stack.pop()
            pending_bond = None

        elif ttype == 'dot':
            attachment = None
            pending_bond = None

        elif ttype == 'recursive':
            qa = QueryAtom()
            qa.recursive_smarts = token['content']
            idx = qg.add_atom(qa)

            if attachment is not None:
                qb = pending_bond or QueryBond()
                qg.add_bond(attachment, idx, qb)
                pending_bond = None

            attachment = idx

    _query_graph_cache[pattern] = qg
    return qg


def _make_query_graph_from_query(qg: QueryGraph) -> MolecularGraph:
    """Convert a QueryGraph to a MolecularGraph (for backward compatibility)."""
    builder = MolecularGraphBuilder()

    atom_map: dict[int, int] = {}  # query_idx -> builder_idx
    for i, qa in enumerate(qg.atoms):
        z = qa.atomic_number if qa.atomic_number is not None else 0
        is_arom = qa.is_aromatic if qa.is_aromatic is not None else False
        idx = builder.add_atom(atomic_number=z, is_aromatic=is_arom)
        atom_map[i] = idx

    for i, j, qb in qg.bonds:
        if qb.order is not None:
            bond_order = qb.order
        elif qb.is_any:
            bond_order = BondOrder.SINGLE
        else:
            bond_order = BondOrder.SINGLE
        builder.add_bond(atom_map[i], atom_map[j], bond_order)

    return builder.build()


# ── Matching Engine ──


def _query_atom_compatible(
    target: MolecularGraph, t_i: int,
    query_graph: QueryGraph, q_i: int,
) -> bool:
    """Check if a target atom is compatible with a query atom."""
    return query_graph.atoms[q_i].matches(target, t_i)


def _query_bond_compatible(
    target: MolecularGraph, t1: int, t2: int,
    query_graph: QueryGraph, q1: int, q2: int,
) -> bool:
    """Check if a target bond is compatible with a query bond."""
    qb = query_graph.get_bond_query(q1, q2)
    if qb is None:
        # No query bond specified — any bond is compatible
        return True

    # Find the bond index in the target
    target_bond = target.get_bond(t1, t2)
    if target_bond is None:
        return False

    # Find the bond index
    bond_idx = None
    for bi, b in enumerate(target.bonds):
        if (b.atom1 == t1 and b.atom2 == t2) or (b.atom1 == t2 and b.atom2 == t1):
            bond_idx = bi
            break

    if bond_idx is None:
        return False

    return qb.matches(target, bond_idx)


def smarts_match(pattern: str, graph: MolecularGraph) -> bool:
    """Check if a SMARTS pattern matches the molecular graph.

    Uses full QueryAtom/QueryBond predicates for matching.

    Args:
        pattern: SMARTS pattern string.
        graph: The molecular graph to search.

    Returns:
        True if the pattern matches at least once.
    """
    qg = _parse_query_graph(pattern)

    if len(qg.atoms) == 0:
        return False

    from chemengine.detection.substructure import find_subgraph_matches

    legacy_query = _make_query_graph_from_query(qg)

    def atom_compat(target: MolecularGraph, t_i: int,
                    query: MolecularGraph, q_i: int) -> bool:
        return _query_atom_compatible(target, t_i, qg, q_i)

    def bond_compat(target: MolecularGraph, t1: int, t2: int,
                    query: MolecularGraph, q1: int, q2: int) -> bool:
        return _query_bond_compatible(target, t1, t2, qg, q1, q2)

    matches = find_subgraph_matches(
        graph, legacy_query,
        atom_compatible=atom_compat,
        bond_compatible=bond_compat,
    )

    return len(matches) > 0


def smarts_findall(pattern: str, graph: MolecularGraph) -> list[dict[int, int]]:
    """Find all matches of a SMARTS pattern in the molecular graph.

    Args:
        pattern: SMARTS pattern string.
        graph: The molecular graph to search.

    Returns:
        List of mappings {query_atom: target_atom} for each match.
    """
    qg = _parse_query_graph(pattern)

    if len(qg.atoms) == 0:
        return []

    from chemengine.detection.substructure import find_subgraph_matches
    legacy_query = _make_query_graph_from_query(qg)

    def atom_compat(target: MolecularGraph, t_i: int,
                    query: MolecularGraph, q_i: int) -> bool:
        return _query_atom_compatible(target, t_i, qg, q_i)

    def bond_compat(target: MolecularGraph, t1: int, t2: int,
                    query: MolecularGraph, q1: int, q2: int) -> bool:
        return _query_bond_compatible(target, t1, t2, qg, q1, q2)

    return find_subgraph_matches(
        graph, legacy_query,
        atom_compatible=atom_compat,
        bond_compatible=bond_compat,
    )


def smarts_count(pattern: str, graph: MolecularGraph) -> int:
    """Count matches of a SMARTS pattern in the molecular graph.

    Args:
        pattern: SMARTS pattern string.
        graph: The molecular graph to search.

    Returns:
        Number of distinct matches.
    """
    return len(smarts_findall(pattern, graph))


# ── Backward-Compatible Wrappers ──
# These adapt the old dict-based internal API to the new implementation.


def _tokenize_smarts(pattern: str) -> list[dict[str, str]]:
    """Tokenize a SMARTS pattern (backward-compatible wrapper).

    Returns a list of dicts with keys matching the old API:
    'atom', 'bond', 'ring', 'branch', 'dot', 'wildcard', etc.
    """
    tokens = _tokenize(pattern)
    result = []
    for t in tokens:
        ttype = t['type']
        if ttype == 'simple_atom':
            result.append({'atom': t['symbol']})
        elif ttype == 'wildcard':
            result.append({'wildcard': '*'})
        elif ttype == 'bracket_atom':
            # Parse bracket content to extract features
            spec = _parse_bracket_content(t['content'])
            d: dict[str, str] = {}
            if (spec.atomic_number == 0 or spec.atomic_number is None) and spec.atom_list is None:
                d['wildcard'] = '*'
            elif spec.atom_list is not None:
                pass  # atom list, no single element
            elif spec.atomic_number is not None:
                from chemengine.core.enums import ElementSymbol
                for el in ElementSymbol:
                    if el.atomic_number == spec.atomic_number:
                        d['element'] = el.name
                        break
            if spec.is_aromatic:
                d['aromatic'] = 'true'
            if spec.formal_charge is not None:
                if spec.formal_charge > 0:
                    d['charge'] = '+' + (str(spec.formal_charge) if spec.formal_charge > 1 else '')
                else:
                    d['charge'] = '-' + (str(abs(spec.formal_charge)) if spec.formal_charge < -1 else '')
            if spec.isotope is not None:
                d['isotope'] = str(spec.isotope)
            if spec.implicit_hydrogens is not None:
                d['hcount'] = 'H' + (str(spec.implicit_hydrogens) if spec.implicit_hydrogens > 1 else '')
            result.append(d)
        elif ttype == 'bond':
            result.append({'bond': t['symbol']})
        elif ttype == 'ring':
            result.append({'ring': str(t['number'])})
        elif ttype == 'branch_open':
            result.append({'branch': '('})
        elif ttype == 'branch_close':
            result.append({'branch': ')'})
        elif ttype == 'dot':
            result.append({'dot': '.'})
        elif ttype == 'recursive':
            result.append({'recursive': t['content']})
    return result


def _parse_bracket_atom(token: dict[str, str]) -> dict[str, Any]:
    """Parse a bracket atom specification from a dict (backward-compatible).

    Takes a dict with keys like 'charge', 'element', 'isotope', 'hcount',
    'chiral', 'wildcard', 'aromatic' and returns a spec dict.
    """
    spec: dict[str, Any] = {"is_aromatic": False, "atomic_number": 0}

    if "wildcard" in token:
        spec["atomic_number"] = 0
    elif "element" in token:
        el = token["element"]
        spec["element"] = el
        from chemengine.core.enums import ElementSymbol
        try:
            spec["atomic_number"] = ElementSymbol(el).atomic_number
        except (ValueError, KeyError):
            spec["atomic_number"] = 0
    elif "aromatic" in token:
        ar = token["aromatic"].upper()
        spec["element"] = ar
        spec["is_aromatic"] = True
        from chemengine.core.enums import ElementSymbol
        try:
            spec["atomic_number"] = ElementSymbol(ar).atomic_number
        except (ValueError, KeyError):
            spec["atomic_number"] = 6
    else:
        spec["atomic_number"] = 0

    if "charge" in token:
        ch = token["charge"]
        if ch.startswith("++"):
            spec["formal_charge"] = 2
        elif ch.startswith("--"):
            spec["formal_charge"] = -2
        elif ch.startswith("+"):
            spec["formal_charge"] = int(ch[1:]) if len(ch) > 1 else 1
        elif ch.startswith("-"):
            spec["formal_charge"] = -int(ch[1:]) if len(ch) > 1 else -1

    if "isotope" in token:
        spec["isotope"] = int(token["isotope"])

    if "hcount" in token:
        h = token["hcount"]
        if h == "H":
            spec["implicit_hydrogens"] = 1
        else:
            spec["implicit_hydrogens"] = int(h[1:])

    if "chiral" in token:
        if token["chiral"] == "@":
            spec["stereochemistry"] = ChiralTag.TH1
        elif token["chiral"] == "@@":
            spec["stereochemistry"] = ChiralTag.TH2

    return spec
