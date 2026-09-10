"""Parsing errors with position information.

All parsers in the engine use these error types to report issues with
chemical identifier strings. Every error includes:
    - The position (character index) where the error occurred
    - A human-readable message
    - Optional context (the actual token/character found vs. expected)

Usage:
    >>> raise SmilesSyntaxError("Unclosed bracket", pos=5)
    SmilesSyntaxError: Unclosed bracket at position 5

    >>> raise SmilesValidationError(
    ...     "Carbon valence exceeded",
    ...     pos=3, atom="C", detail="5 bonds, max 4"
    ... )
    SmilesValidationError: Carbon valence exceeded at position 3: 5 bonds, max 4
"""

from __future__ import annotations


class SmilesError(ValueError):
    """Base error for SMILES parsing failures with position information."""

    def __init__(
        self,
        message: str,
        pos: int | None = None,
        *,
        context: str | None = None,
    ) -> None:
        self.pos = pos
        self.context = context
        if pos is not None:
            msg = f"{message} at position {pos}"
        else:
            msg = message
        if context:
            msg = f"{msg}: {context}"
        super().__init__(msg)


class SmilesSyntaxError(SmilesError):
    """Raised when the SMILES string contains invalid syntax.

    Examples:
        - Unknown element symbol
        - Unmatched parentheses or brackets
        - Invalid character
        - Malformed bracket atom
    """

    def __init__(
        self,
        message: str,
        pos: int | None = None,
        *,
        token: str | None = None,
        expected: str | None = None,
        context: str | None = None,
    ) -> None:
        self.token = token
        self.expected = expected
        parts = [message]
        if token is not None:
            parts.append(f"got '{token}'")
        if expected is not None:
            parts.append(f"expected {expected}")
        msg = ", ".join(parts)
        if context:
            msg = f"{msg}: {context}"
        super().__init__(msg, pos=pos, context=None)


class SmilesValidationError(SmilesError):
    """Raised when the parsed SMILES fails chemical validation.

    Examples:
        - Valence exceeded for an element
        - Invalid isotope mass number
        - Self-bond through ring closure
    """

    def __init__(
        self,
        message: str,
        pos: int | None = None,
        *,
        atom: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.atom = atom
        self.detail = detail
        parts = [message]
        if atom is not None:
            parts.append(f"for atom {atom}")
        if detail is not None:
            parts.append(detail)
        super().__init__(": ".join(parts), pos=pos)


class UnclosedBracketError(SmilesSyntaxError):
    """Raised when a bracketed atom is not closed."""


class UnmatchedRingClosureError(SmilesSyntaxError):
    """Raised when a ring closure digit has no partner."""


class UnmatchedBranchError(SmilesSyntaxError):
    """Raised when parentheses are not matched."""


class FormulaParseError(ValueError):
    """Raised when a molecular formula cannot be parsed.

    Structured error carrying:
        - The position (character index) where the error occurred
        - The full formula string that failed to parse

    Examples:
        - Unknown element symbol
        - Unmatched parentheses
        - Invalid characters (anything other than letters, digits,
          parentheses, dots, charge signs, and whitespace)
        - Empty formula
    """

    def __init__(
        self,
        message: str,
        pos: int | None = None,
        *,
        formula: str | None = None,
    ) -> None:
        self.pos = pos
        self.formula = formula
        msg = message
        if pos is not None:
            msg = f"{msg} at position {pos}"
        if formula is not None:
            msg = f"{msg} (formula: '{formula}')"
        super().__init__(msg)
