"""IUPAC name tokenizer (M33 Phase 11.4).

Tokenizes IUPAC names of the *generator's supported grammar subset*
(see :mod:`chemengine.nomenclature.iupac` for the exact coverage) into
tokens for :class:`chemengine.parsing.iupac.parser.NameParser`.

Token kinds (structured, position-aware):
- ``WORD``       alphabetic run (stem, prefix, ``cyclo``, ``benzene`` …)
- ``LOCANTS``    comma-separated digit run followed by ``-`` (``2,4-``)
- ``SEP``        the ``-`` separator
- ``MULT``       multiplicative prefix merged into the following WORD by
                  the parser (``di``/``tri``/``tetra`` …)
- ``NLOC``       ``N``/``N,N`` locant marker
- ``SPACE``      whitespace (``ethyl ethanoate``)
- ``UNK``        any character outside the expected alphabet (the parser
                  rejects it with its position)

Position-aware errors: :class:`TokenizationError` carries the 0-based
``position`` and the offending character.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class TokenizationError(ValueError):
    """Raised when a name cannot be tokenized.

    Attributes:
        position: 0-based character offset of the offending input.
        char: The offending character.
    """

    def __init__(self, message: str, position: int, char: str) -> None:
        super().__init__(message)
        self.position = position
        self.char = char


@dataclass(frozen=True, slots=True)
class Token:
    """One lexical token of an IUPAC name.

    Attributes:
        kind: Token kind (see module docstring).
        value: The exact substring consumed.
        position: 0-based offset of the token start in the input.
    """

    kind: Literal["WORD", "LOCANTS", "SEP", "NLOC", "SPACE", "UNK"]
    value: str
    position: int


def tokenize(name: str) -> list[Token]:
    """Tokenize an IUPAC name string.

    Args:
        name: The IUPAC name (e.g. ``'2-methylbutane'``,
            ``'N,N-dimethylethanamide'``, ``'buta-1,3-diene'``).

    Returns:
        The token list, ending implicit at end of input.

    Raises:
        TokenizationError: On characters outside the expected alphabet,
            with the exact position.
    """
    tokens: list[Token] = []
    i = 0
    n = len(name)
    while i < n:
        ch = name[i]
        if ch == " ":
            tokens.append(Token("SPACE", ch, i))
            i += 1
            continue
        if ch == "-":
            tokens.append(Token("SEP", ch, i))
            i += 1
            continue
        if ch in "N," and _starts_n_locant(name, i):
            # consume N / N,N (letter N only, never part of a word)
            j = i
            value = ""
            while j < n and (name[j] == "N" or (name[j] == "," and j + 1 < n and name[j + 1] == "N")):
                value += name[j]
                j += 1
            tokens.append(Token("NLOC", value, i))
            i = j
            continue
        if ch.isdigit():
            j = i
            while j < n and name[j].isdigit():
                j += 1
            # locant run: digits followed by '-' or ','
            if j < n and name[j] in "-,":
                value = name[i:j]
                k = j
                while k < n and (name[k].isdigit() or name[k] == ","):
                    if name[k].isdigit():
                        k += 1
                    else:
                        # comma must be followed by a digit to continue
                        if k + 1 < n and name[k + 1].isdigit():
                            k += 1
                        else:
                            break
                value = name[i:k]
                if k < n and name[k] == "-":
                    k += 1
                    value += "-"
                tokens.append(Token("LOCANTS", value, i))
                i = k
                continue
            raise TokenizationError(
                f"digit run not followed by a separator at position {i}", i, ch
            )
        if ch.isalpha():
            j = i
            while j < n and name[j].isalpha():
                j += 1
            tokens.append(Token("WORD", name[i:j], i))
            i = j
            continue
        raise TokenizationError(
            f"unexpected character {ch!r} at position {i}", i, ch
        )
    return tokens


def _starts_n_locant(name: str, i: int) -> bool:
    """Whether the ``N``/``,N`` run at ``i`` is an N-locant marker.

    An ``N`` acts as an N-locant when it is followed by ``-`` or ``,N``
    sequences and is not part of a longer word (e.g. the ``N`` in
    ``Non`` would be a WORD, but names of the supported subset start
    words with lowercase letters — uppercase N standing alone is the
    locant).
    """
    if name[i] != "N":
        return False
    j = i
    seen_n = False
    while j < len(name):
        if name[j] == "N":
            seen_n = True
            j += 1
            if j < len(name) and name[j] == ",":
                if j + 1 < len(name) and name[j + 1] == "N":
                    j += 1
                    continue
                break
            break
        break
    if not seen_n:
        return False
    # must be followed by '-' (the locant separator)
    return j < len(name) and name[j] == "-"
