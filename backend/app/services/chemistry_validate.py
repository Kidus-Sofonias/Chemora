"""Shared chemistry validation utilities.

Used by both the admin content-validation service (M26) and the student
learning-service answer grading.  Placing them here removes the inappropriate
private-function coupling between ``content_admin`` and ``learning``.
"""

from __future__ import annotations

from chemengine.core.element import Element


def resolve_element(answer: str) -> str | None:
    """Resolve an element answer to a canonical atomic-number string.

    Accepts a symbol (``Na``), name (``sodium``, case-insensitive), or
    atomic number (``11``).  Returns ``None`` if the answer does not resolve
    to a real element — never accepts an unverified guess.
    """
    token = answer.strip()
    if not token:
        return None
    # Atomic-number string (digits only) -> Element.from_z.
    if token.isdigit():
        try:
            return str(Element.from_z(int(token)).atomic_number)
        except Exception:
            return None
    # Symbol or case-insensitive name.
    try:
        return str(Element.from_symbol(token).atomic_number)
    except Exception:
        pass
    try:
        return str(Element.from_name(token.lower()).atomic_number)
    except Exception:
        return None


def canonicalize_formula(answer: str) -> str | None:
    """Canonicalize a molecular formula via ChemEngine's formula parser.

    Returns the canonical Hill-notation formula string, or ``None`` if the
    input is not a valid chemical formula.
    """
    from chemengine.parsing import formula_to_graph

    token = answer.strip()
    if not token:
        return None
    try:
        graph = formula_to_graph(token)
    except Exception:
        return None
    formula = getattr(graph, "molecular_formula", None)
    return formula if isinstance(formula, str) and formula else None
