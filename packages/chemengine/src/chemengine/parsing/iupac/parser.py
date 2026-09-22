"""IUPAC name parser (M33 Phase 11.4).

Parses IUPAC names of the *generator's supported grammar subset* (see
:mod:`chemengine.nomenclature.iupac`) into molecular graphs. Round-trips
the generator on that subset:

    SMILES → name → parse → graph → name   (same name, deterministic)

**Coverage boundary (honest).** The parser accepts exactly the name
forms :func:`generate_iupac_name` emits: linear/branched alkanes,
alkenes/alkynes/(di|tri)enes/(di|tri)ynes with locants, alcohols,
aldehydes (incl. dial), ketones, carboxylic acids, esters, amides
(with N-substituents), nitriles, amines (primary/secondary with
N-substituents), cycloalkanes with simple substituents,
benzene-family names (``benzene``/``phenol`` with locanted prefixes),
and the seven common heterocycles. Anything else raises
:class:`NameParseError` with the offending position.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from chemengine.core.enums import BondOrder
from chemengine.core.graph import MolecularGraph, MolecularGraphBuilder
from chemengine.nomenclature.iupac import ALKANE_STEMS, MULTI_PREFIXES, SUBSTITUENT_NAMES
from chemengine.parsing.iupac.tokenizer import tokenize

__all__ = ["NameParse", "NameParseError", "NameParser"]

_STEM_LENGTHS: dict[str, int] = {stem: n for n, stem in ALKANE_STEMS.items()}
# SUBSTITUENT_NAMES maps length -> name; invert it to name -> length.
_SUB_LENGTHS: dict[str, int] = {name: n for n, name in SUBSTITUENT_NAMES.items()}
_PREFIX_SUBS: dict[str, int] = {
    "fluoro": 9, "chloro": 17, "bromo": 35, "iodo": 53,
    "hydroxy": 8, "amino": 7, "thio": 16, "nitro": 7,
}
_ALL_SUBS: set[str] = set(_SUB_LENGTHS) | set(_PREFIX_SUBS)

_HETEROCYCLES: dict[str, tuple[int, list[tuple[int, int]], bool]] = {
    # name -> (ring size, [(z, has_implicit_H)], aromatic)
    "pyridine": (6, [(6, 1)] * 5 + [(7, 0)], True),
    "pyrimidine": (6, [(6, 1)] * 4 + [(7, 0)] * 2, True),
    "pyrrole": (5, [(6, 1)] * 4 + [(7, 1)], True),
    "imidazole": (5, [(6, 1)] * 3 + [(7, 1), (7, 0)], True),
    "furan": (5, [(6, 1)] * 4 + [(8, 0)], True),
    "thiophene": (5, [(6, 1)] * 4 + [(16, 0)], True),
    "pyran": (6, [(6, 1)] * 5 + [(8, 0)], False),
}

_DEFAULT_VALENCE: dict[int, int] = {6: 4, 7: 3, 8: 2, 9: 1, 16: 2, 17: 1, 35: 1, 53: 1}


class NameParseError(ValueError):
    """Raised when a name is outside the parser's grammar or malformed.

    Attributes:
        position: 0-based character offset into the original name
            (``-1`` when the error is structural rather than positional).
    """

    def __init__(self, message: str, position: int = -1) -> None:
        super().__init__(message)
        self.position = position


@dataclass(frozen=True, slots=True)
class Substituent:
    """One prefix substituent instance.

    Attributes:
        locant: 1-based attachment position on the parent (0 = to be
            assigned by the builder, e.g. ester acyl prefixes).
        name: Substituent name (``methyl``, ``chloro``, ...).
        z: Atomic number of the attachment atom.
        on_nitrogen: True for N-locant substituents.
    """

    locant: int
    name: str
    z: int
    on_nitrogen: bool = False


@dataclass(frozen=True, slots=True)
class NameParse:
    """Structured parse of an IUPAC name (supported subset).

    Attributes:
        kind: Parent skeleton kind (``chain``, ``cycloalkane``,
            ``benzene``, ``heterocycle``).
        parent_length: Carbon count of the parent chain/ring.
        unsaturations: (position, bond order) pairs along the parent.
        principal: Principal group descriptor (``ol``, ``one``, ``al``,
            ``oic acid``, ``oate``, ``amide``, ``nitrile``, ``amine``).
        principal_locants: Positions of the principal group.
        substituents: C-attached prefix substituents.
        n_substituents: N-attached substituents (amides/amines).
        alkyl_alkyl: Alkoxy alkyl name for esters.
        heterocycle: Heterocycle parent name, when applicable.
    """

    kind: Literal["chain", "cycloalkane", "benzene", "heterocycle"]
    parent_length: int = 0
    unsaturations: tuple[tuple[int, BondOrder], ...] = ()
    principal: str | None = None
    principal_locants: tuple[int, ...] = ()
    substituents: tuple[Substituent, ...] = field(default_factory=tuple)
    n_substituents: tuple[Substituent, ...] = field(default_factory=tuple)
    alkyl_alkyl: str | None = None
    heterocycle: str | None = None


class NameParser:
    """Parser for the generator's IUPAC grammar subset.

    Usage:
        >>> parser = NameParser()
        >>> graph = parser.parse_to_graph("2-methylbutane")
    """

    def parse(self, name: str) -> NameParse:
        """Parse an IUPAC name into a structured :class:`NameParse`.

        Raises:
            NameParseError: Malformed or unsupported name.
        """
        if not name or not name.strip():
            raise NameParseError("empty name", 0)
        try:
            tokens = tokenize(name.strip())
        except Exception as e:
            raise NameParseError(str(e), getattr(e, "position", -1)) from e
        segs: list[tuple[str, str, int]] = []
        for tok in tokens:
            if tok.kind == "SEP":
                continue
            if tok.kind == "UNK":
                raise NameParseError(f"unexpected character {tok.value!r}", tok.position)
            segs.append((tok.kind, tok.value, tok.position))
        return self._parse_segments(segs)

    def parse_to_graph(self, name: str) -> MolecularGraph:
        """Parse an IUPAC name into a molecular graph (explicit Hs)."""
        return self._build_graph(self.parse(name))

    # ── Segment-stream matching ──

    def _parse_segments(self, segs: list[tuple[str, str, int]]) -> NameParse:
        kind, value, pos = segs[0]

        # Carboxylic acid: [locants ]word+anoic SPACE acid (checked before
        # the ester pattern so "ethanoic acid" is not read as an alkyl group)
        if segs[-1] == ("WORD", "acid", segs[-1][2]) and len(segs) >= 2:
            prev_idx = len(segs) - 2
            if segs[prev_idx][0] == "SPACE":
                prev_idx -= 1
            if prev_idx < 0:
                raise NameParseError("expected <stem>anoic acid", 0)
            prev_kind, prev_word, prev_pos = segs[prev_idx]
            if prev_kind != "WORD" or not prev_word.endswith("anoic"):
                raise NameParseError("expected <stem>anoic acid", prev_pos)
            stem = self._longest_stem_suffix(prev_word[: -len("anoic")], prev_pos)
            prefix = prev_word[: len(prev_word) - len("anoic") - len(stem)]
            head = segs[:prev_idx]
            if prefix and head and head[-1][0] == "LOCANTS":
                # A pending head locant pairs with the glued prefix:
                # '3-' + 'methylpentanoic' -> 3-methylpentanoic acid.
                subs = self._locanted_prefix_subs(head, prefix, prev_pos)
            else:
                subs = self._head_subs(head)
                for mult, sub in self._split_prefix(prefix, prev_pos):
                    subs.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(mult or 1))
            # A single unlocated substituent takes position 2 (the alpha
            # carbon; position 1 is the carboxyl carbon itself).
            if len(subs) == 1 and subs[0].locant == 0:
                subs = [Substituent(2, subs[0].name, subs[0].z)]
            if any(s.locant == 0 for s in subs):
                raise NameParseError(
                    f"substituted acid names require locants: {prev_word!r}", prev_pos
                )
            return NameParse(
                kind="chain", parent_length=_STEM_LENGTHS[stem],
                principal="oic acid", substituents=tuple(subs),
            )

        # Ester: <alkyl> SPACE <[prefix]stem+anoate>
        if len(segs) == 3 and segs[1][0] == "SPACE":
            if kind != "WORD" or value not in _SUB_LENGTHS:
                raise NameParseError(f"unknown ester alkyl group {value!r}", pos)
            acyl_kind, acyl_word, acyl_pos = segs[2]
            if acyl_kind != "WORD" or not acyl_word.endswith("anoate"):
                raise NameParseError("expected <stem>anoate after the alkyl group", acyl_pos)
            stem = self._longest_stem_suffix(acyl_word[: -len("anoate")], acyl_pos)
            prefix = acyl_word[: len(acyl_word) - len("anoate") - len(stem)]
            occurrences = self._split_prefix(prefix, acyl_pos)
            subs_list: list[Substituent] = []
            for mult, sub in occurrences:
                subs_list.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(mult or 1))
            return NameParse(
                kind="chain", parent_length=_STEM_LENGTHS[stem], principal="oate",
                substituents=tuple(subs_list), alkyl_alkyl=value,
            )

        # Heterocycle (bare word)
        if len(segs) == 1 and kind == "WORD" and value in _HETEROCYCLES:
            return NameParse(
                kind="heterocycle", heterocycle=value,
                parent_length=_HETEROCYCLES[value][0],
            )

        # N-locant prefix (amides/amines with N-substituents)
        nloc_count = 0
        if kind == "NLOC":
            nloc_count = value.count("N")
            segs = segs[1:]
            if not segs:
                raise NameParseError("name ends after N-locant", pos)
        return self._match_patterns(segs, nloc_count)

    def _match_patterns(
        self, segs: list[tuple[str, str, int]], nloc_count: int
    ) -> NameParse:
        last_kind, last_word, last_pos = segs[-1]
        if last_kind != "WORD":
            raise NameParseError("name ends with a locant", last_pos)

        if len(segs) >= 2 and segs[-2][0] == "LOCANTS":
            loc_token = segs[-2][1]
            locs = self._parse_locants(loc_token)
            head = segs[:-2]
            head_kind, head_word, head_pos = head[-1] if head else ("WORD", "", last_pos)
            prefix_head = head[:-1] if head else []

            # diol/triol/dione on stem+ane
            if last_word in ("diol", "triol", "dione") and head_kind == "WORD" \
                    and head_word.endswith("ane"):
                stem = self._longest_stem_suffix(head_word[:-3], head_pos)
                principal: str | None = {"diol": "ol", "triol": "ol", "dione": "one"}[last_word]
                return NameParse(
                    kind="chain", parent_length=_STEM_LENGTHS[stem], principal=principal,
                    principal_locants=tuple(locs),
                    substituents=tuple(self._head_subs(prefix_head)),
                )
            # unsaturations on stem or stem+a
            if last_word in ("ene", "yne", "diene", "triene", "diyne", "triyne"):
                if head_kind != "WORD":
                    raise NameParseError("expected a stem before the unsaturation", head_pos)
                stem_word = head_word
                if stem_word.endswith("a") and stem_word[:-1] in _STEM_LENGTHS:
                    stem_word = stem_word[:-1]
                if head_word.endswith("cyclo") and head_word[: -len("cyclo")] in _STEM_LENGTHS:
                    stem_word = head_word[: -len("cyclo")]
                    length = _STEM_LENGTHS[stem_word]
                    return NameParse(
                        kind="cycloalkane", parent_length=length,
                        unsaturations=self._unsats(last_word, locs),
                    )
                if stem_word not in _STEM_LENGTHS:
                    raise NameParseError(f"unknown stem in {head_word!r}", head_pos)
                return NameParse(
                    kind="chain", parent_length=_STEM_LENGTHS[stem_word],
                    unsaturations=self._unsats(last_word, locs),
                    substituents=tuple(self._head_subs(prefix_head)),
                )
            # alkane/cycloalkane with locanted substituents: [loc][sub][stem+ane]
            if last_word.endswith("ane"):
                for stem in sorted(_STEM_LENGTHS, key=len, reverse=True):
                    if not last_word.endswith(stem + "ane"):
                        continue
                    base = last_word[: len(last_word) - len(stem) - 3]
                    cyclo = False
                    if base.endswith("cyclo") and not self._split_prefix(base[: -len("cyclo")], last_pos) :
                        cyclo = True
                        base = ""
                    elif base:
                        if base.endswith("cyclo") and self._splittable_base(base[: -len("cyclo")]):
                            cyclo = True
                            base = base[: -len("cyclo")]
                        elif not self._splittable_base(base):
                            continue
                    subs = self._head_subs(prefix_head)
                    for mult, sub in self._split_prefix(base, last_pos):
                        count = mult or 1
                        assigned = locs if len(locs) == count else [0] * count
                        subs.extend(Substituent(assigned[i], sub, _sub_z(sub)) for i in range(count))
                    if any(s.locant == 0 for s in subs):
                        raise NameParseError(
                            f"substituted parent names require locants: {last_word!r}", last_pos
                        )
                    kind: Literal["chain", "cycloalkane"] = "cycloalkane" if cyclo else "chain"
                    return NameParse(kind=kind, parent_length=_STEM_LENGTHS[stem], substituents=tuple(subs))
            # ol/one/amine on stem+an
            if last_word in ("ol", "one", "amine") and head_kind == "WORD" \
                    and head_word.endswith("an"):
                n_subs: tuple[Substituent, ...] = ()
                stem_head = head_word
                if last_word == "amine" and nloc_count:
                    # head word is [Nsubs][stem]an — the trailing 'an' is
                    # the conjunction, not part of the stem.
                    if not stem_head.endswith("an"):
                        raise NameParseError(
                            f"expected stem+an before 'amine' in {head_word!r}", head_pos
                        )
                    n_subs, stem = self._extract_nsubs(stem_head[:-2], head_pos, nloc_count)
                else:
                    stem = self._longest_stem_suffix(stem_head[:-2], head_pos)
                if nloc_count:
                    # N-substituents were consumed from the head word by
                    # _extract_nsubs; no C-prefix remains.
                    subs = []
                else:
                    # Glued prefix on the parent word ('methylbutan-1-ol') may
                    # pair with a pending head locant ('3-' 'methylbutan' '1-' 'ol').
                    prefix = stem_head[: len(stem_head) - 2 - len(stem)]
                    if prefix and prefix_head and prefix_head[-1][0] == "LOCANTS":
                        subs = self._locanted_prefix_subs(prefix_head, prefix, head_pos)
                    else:
                        subs = self._head_subs(prefix_head)
                        for mult, sub in self._split_prefix(prefix, head_pos):
                            count = mult or 1
                            subs.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(count))
                        if len(subs) == 1 and subs[0].locant == 0:
                            subs = [Substituent(2, subs[0].name, subs[0].z)]
                        if any(s.locant == 0 for s in subs):
                            raise NameParseError(
                                f"substituted parent names require locants: {head_word!r}", head_pos
                            )
                return NameParse(
                    kind="chain", parent_length=_STEM_LENGTHS[stem],
                    principal=last_word, principal_locants=tuple(locs),
                    n_substituents=n_subs,
                    substituents=tuple(subs),
                )
            # en-yne: [stem] [loc] en [loc] yne
            if last_word == "yne" and len(segs) >= 5 and segs[-3][1] == "en":
                stem_word = segs[-5][1]
                if segs[-5][0] != "WORD" or stem_word not in _STEM_LENGTHS:
                    raise NameParseError(f"unknown en-yne stem {stem_word!r}", segs[-5][2])
                ene_loc = self._parse_locants(segs[-4][1])[0]
                yne_loc = locs[0]
                return NameParse(
                    kind="chain", parent_length=_STEM_LENGTHS[stem_word],
                    unsaturations=(
                        (ene_loc, BondOrder.DOUBLE), (yne_loc, BondOrder.TRIPLE),
                    ),
                )
            # locanted benzene/phenol family: [locants][prefix]benzene|phenol
            if last_word.endswith("benzene") or last_word.endswith("phenol"):
                suffix = "benzene" if last_word.endswith("benzene") else "phenol"
                prefix = last_word[: -len(suffix)]
                if (head and head[-1][0] == "WORD" and len(head) >= 2
                        and head[-2][0] == "LOCANTS" and head[-1][1] in _ALL_SUBS):
                    # Trailing head pair is a complete locanted substituent
                    # ('1-' 'chloro' ... '2-' 'methylbenzene').
                    subs = self._head_subs(head)
                    for mult, sub in self._split_prefix(prefix, last_pos):
                        count = mult or 1
                        assigned = locs if len(locs) == count else [0] * count
                        subs.extend(
                            Substituent(assigned[i], sub, _sub_z(sub))
                            for i in range(count)
                        )
                elif (prefix and head and head[-1][0] == "WORD"
                        and len(head) >= 2 and head[-2][0] == "LOCANTS"):
                    # Pending head locant pairs with the glued prefix of the
                    # parent word ('3-' + 'chlorophenol').
                    pending = self._parse_locants(head[-2][1])
                    subs = self._head_subs(head[:-2])
                    for mult, sub in self._split_prefix(prefix, last_pos):
                        count = mult or 1
                        loc = pending[0] if len(pending) == 1 else 0
                        subs.extend(Substituent(loc, sub, _sub_z(sub)) for _ in range(count))
                else:
                    subs = self._head_subs(prefix_head)
                    for mult, sub in self._split_prefix(prefix, last_pos):
                        count = mult or 1
                        assigned = locs if len(locs) == count else [0] * count
                        subs.extend(
                            Substituent(assigned[i], sub, _sub_z(sub))
                            for i in range(count)
                        )
                principal = "ol" if suffix == "phenol" else None
                return NameParse(
                    kind="benzene", parent_length=6, principal=principal,
                    substituents=tuple(subs),
                )
            raise NameParseError(f"unsupported name form near {last_word!r}", last_pos)

        # Single final word (no locant segments)
        # cyclohexanol / cyclohexanamine: [cyclo][stem]anol / [cyclo][stem]anamine
        for conj, principal in (("anol", "ol"), ("anamine", "amine")):
            if last_word.endswith(conj):
                base = last_word[: -len(conj)]
                if base.startswith("cyclo") and base[len("cyclo"):] in _STEM_LENGTHS:
                    return NameParse(
                        kind="cycloalkane",
                        parent_length=_STEM_LENGTHS[base[len("cyclo"):]],
                        principal=principal,
                    )
        # benzene / phenol (with optional glued prefix). A single
        # unlocated prefix on an unsubstituted parent is unambiguous
        # (all ring positions are equivalent) — assign position 1.
        if last_word.endswith("benzene") or last_word.endswith("phenol"):
            suffix = "benzene" if last_word.endswith("benzene") else "phenol"
            prefix = last_word[: -len(suffix)]
            subs = self._head_subs(segs[:-1])
            for mult, sub in self._split_prefix(prefix, last_pos):
                subs.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(mult or 1))
            principal = "ol" if suffix == "phenol" else None
            if principal == "ol" and subs:
                # phenol's OH is position 1; further prefixes need locants
                if any(s.locant == 0 for s in subs):
                    raise NameParseError(
                        f"substituted phenol names require locants: {last_word!r}", last_pos
                    )
            elif len(subs) == 1 and subs[0].locant == 0:
                subs = [Substituent(1, subs[0].name, subs[0].z)]
            elif any(s.locant == 0 for s in subs):
                raise NameParseError(
                    f"substituted benzene names require locants: {last_word!r}", last_pos
                )
            return NameParse(
                kind="benzene", parent_length=6, principal=principal,
                substituents=tuple(subs),
            )
        # amide: [Nsubs][prefix]stem+anamide
        if last_word.endswith("anamide"):
            stripped = self._strip_suffix(last_word, "anamide", last_pos)
            n_subs = ()
            prefix = ""
            if nloc_count:
                # _extract_nsubs consumes the entire [Nsubs] prefix and
                # validates the count, so nothing remains for C-prefixes.
                n_subs, stem = self._extract_nsubs(stripped, last_pos, nloc_count)
            else:
                stem = self._longest_stem_suffix(stripped, last_pos)
                prefix = stripped[: len(stripped) - len(stem)]
            subs = self._head_subs(segs[:-1])
            for mult, sub in self._split_prefix(prefix, last_pos):
                subs.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(mult or 1))
            if len(subs) == 1 and subs[0].locant == 0:
                subs = [Substituent(1, subs[0].name, subs[0].z)]
            if any(s.locant == 0 for s in subs):
                raise NameParseError(
                    f"substituted amide names require locants: {last_word!r}", last_pos
                )
            return NameParse(
                kind="chain", parent_length=_STEM_LENGTHS[stem], principal="amide",
                substituents=tuple(subs), n_substituents=n_subs,
            )
        # nitrile: [prefix]stem+anenitrile
        if last_word.endswith("anenitrile"):
            stripped = self._strip_suffix(last_word, "anenitrile", last_pos)
            stem = self._longest_stem_suffix(stripped, last_pos)
            prefix = stripped[: len(stripped) - len(stem)]
            subs = self._head_subs(segs[:-1])
            for mult, sub in self._split_prefix(prefix, last_pos):
                subs.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(mult or 1))
            if prefix and any(s.locant == 0 for s in subs):
                raise NameParseError(
                    f"substituted nitrile names require locants: {last_word!r}", last_pos
                )
            return NameParse(
                kind="chain", parent_length=_STEM_LENGTHS[stem], principal="nitrile",
                substituents=tuple(subs),
            )
        # aldehyde: stem+anal / stem+anedial
        if last_word.endswith("anedial"):
            stripped = self._strip_suffix(last_word, "anedial", last_pos)
            stem = self._longest_stem_suffix(stripped, last_pos)
            prefix = stripped[: len(stripped) - len(stem)]
            subs = self._head_subs(segs[:-1])
            for mult, sub in self._split_prefix(prefix, last_pos):
                subs.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(mult or 1))
            return NameParse(
                kind="chain", parent_length=_STEM_LENGTHS[stem], principal="al",
                principal_locants=(1, _STEM_LENGTHS[stem]),
                substituents=tuple(subs),
            )
        if last_word.endswith("anal"):
            stripped = self._strip_suffix(last_word, "anal", last_pos)
            stem = self._longest_stem_suffix(stripped, last_pos)
            prefix = stripped[: len(stripped) - len(stem)]
            subs = self._head_subs(segs[:-1])
            for mult, sub in self._split_prefix(prefix, last_pos):
                subs.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(mult or 1))
            if prefix and any(s.locant == 0 for s in subs):
                raise NameParseError(
                    f"substituted aldehyde names require locants: {last_word!r}", last_pos
                )
            return NameParse(
                kind="chain", parent_length=_STEM_LENGTHS[stem], principal="al",
                substituents=tuple(subs),
            )
        # alkane / cycloalkane — checked after longer suffixes
        for stem in sorted(_STEM_LENGTHS, key=len, reverse=True):
            if not last_word.endswith(stem + "ane"):
                continue
            base = last_word[: len(last_word) - len(stem) - 3]
            cyclo = False
            if base.endswith("cyclo"):
                cyclo = True
                base = base[: -len("cyclo")]
            elif base and not self._splittable_base(base):
                continue
            subs = self._head_subs(segs[:-1])
            for mult, sub in self._split_prefix(base, last_pos):
                count = mult or 1
                if count > 1 and cyclo:
                    raise NameParseError(
                        "multi-substituted cycloalkanes require locants", last_pos
                    )
                subs.extend(Substituent(0, sub, _sub_z(sub)) for _ in range(count))
            # A single unlocated substituent takes position 1 (implied).
            if len(subs) == 1 and subs[0].locant == 0:
                subs = [Substituent(1, subs[0].name, subs[0].z)]
            if any(s.locant == 0 for s in subs):
                raise NameParseError(
                    f"substituted parent names require locants: {last_word!r}", last_pos
                )
            kind = "cycloalkane" if cyclo else "chain"
            return NameParse(kind=kind, parent_length=_STEM_LENGTHS[stem], substituents=tuple(subs))
        raise NameParseError(f"unsupported parent name {last_word!r}", last_pos)

    # ── Word helpers ──

    def _splittable_base(self, base: str) -> bool:
        """Whether a glued prefix decomposes entirely into known subs."""
        if not base:
            return False
        try:
            self._split_prefix(base, 0)
            return True
        except NameParseError:
            return False

    def _strip_suffix(self, word: str, suffix: str, position: int) -> str:
        if not word.endswith(suffix):
            raise NameParseError(f"expected {suffix!r} in {word!r}", position)
        return word[: -len(suffix)]

    def _longest_stem_suffix(self, text: str, position: int) -> str:
        """Longest stem that terminates ``text`` (the stem ends the word)."""
        for stem in sorted(_STEM_LENGTHS, key=len, reverse=True):
            if text.endswith(stem):
                return stem
        raise NameParseError(f"unknown parent stem in {text!r}", position)

    def _parse_locants(self, value: str) -> list[int]:
        body = value.rstrip("-")
        try:
            return [int(p) for p in body.split(",")]
        except ValueError as e:
            raise NameParseError(f"malformed locants {value!r}", -1) from e

    def _unsats(self, suffix: str, locs: list[int]) -> tuple[tuple[int, BondOrder], ...]:
        orders: dict[str, tuple[BondOrder, ...]] = {
            "ene": (BondOrder.DOUBLE,), "yne": (BondOrder.TRIPLE,),
            "diene": (BondOrder.DOUBLE, BondOrder.DOUBLE),
            "triene": (BondOrder.DOUBLE,) * 3,
            "diyne": (BondOrder.TRIPLE,) * 2,
            "triyne": (BondOrder.TRIPLE,) * 3,
        }
        seq = orders[suffix]
        if len(seq) != len(locs):
            raise NameParseError(f"{suffix} needs {len(seq)} locant(s), got {len(locs)}", -1)
        return tuple(zip(locs, seq))

    def _head_subs(self, head: list[tuple[str, str, int]]) -> list[Substituent]:
        """Substituents from leading (LOCANTS, WORD) pairs."""
        subs: list[Substituent] = []
        i = 0
        while i + 1 < len(head):
            if head[i][0] != "LOCANTS" or head[i + 1][0] != "WORD":
                raise NameParseError("expected a locanted substituent", head[i][2])
            locs = self._parse_locants(head[i][1])
            word = head[i + 1][1]
            if len(locs) != 1 or word not in _ALL_SUBS:
                raise NameParseError(f"unknown or multi-locant substituent {word!r}", head[i + 1][2])
            subs.append(Substituent(locs[0], word, _sub_z(word)))
            i += 2
        if i != len(head):
            # tolerate a trailing SPACE (e.g. 'ethanoic acid')
            if len(head) - i == 1 and head[i][0] == "SPACE":
                i += 1
            else:
                raise NameParseError("dangling substituent locant", head[i][2] if i < len(head) else -1)
        return subs

    def _locanted_prefix_subs(
        self,
        head: list[tuple[str, str, int]],
        prefix: str,
        position: int,
    ) -> list[Substituent]:
        """Substituents from a head locant paired with a glued prefix.

        ``head`` must end with a pending LOCANTS token. Names like
        ``3-methylpentanoic acid`` or ``4-methyl-1-nitrobenzene`` tokenize
        as a head LOCANTS token followed by a word whose leading letters
        are themselves a substituent prefix. The pending locant(s) apply
        to every prefix substituent parsed from the glued word.
        """
        pending = self._parse_locants(head[-1][1])
        subs = self._head_subs(head[:-1])
        for mult, sub in self._split_prefix(prefix, position):
            count = mult or 1
            for i in range(count):
                if len(pending) == count:
                    loc = pending[i]
                elif len(pending) == 1:
                    loc = pending[0]
                else:
                    loc = 0
                subs.append(Substituent(loc, sub, _sub_z(sub)))
        return subs

    def _split_prefix(self, prefix: str, position: int) -> list[tuple[int | None, str]]:
        """Decompose a glued prefix into (multiplier or None, sub name)."""
        if not prefix:
            return []
        result: list[tuple[int | None, str]] = []
        i = 0
        while i < len(prefix):
            mult_hit = False
            for mult in sorted(MULTI_PREFIXES, reverse=True):
                mp = MULTI_PREFIXES[mult]
                if mult >= 2 and prefix.startswith(mp, i):
                    rest = prefix[i + len(mp):]
                    if rest not in _ALL_SUBS:
                        raise NameParseError(
                            f"unknown substituent after {mp!r}", position
                        )
                    result.append((mult, rest))
                    i = len(prefix)
                    mult_hit = True
                    break
            if mult_hit:
                continue
            best: str | None = None
            for name in _ALL_SUBS:
                if prefix.startswith(name, i):
                    if best is None or len(name) > len(best):
                        best = name
            if best is None:
                raise NameParseError(f"unknown substituent component in {prefix!r}", position)
            result.append((None, best))
            i += len(best)
        return result

    def _extract_nsubs(
        self, word: str, position: int, nloc_count: int
    ) -> tuple[tuple[Substituent, ...], str]:
        """Extract N-substituents from ``[Nsubs][stem]`` words.

        Returns (N-subs, stem). The stem is the longest stem such that
        the prefix decomposes into exactly ``nloc_count`` substituents.
        """
        for stem in sorted(_STEM_LENGTHS, key=len, reverse=True):
            if not word.endswith(stem):
                continue
            prefix = word[: len(word) - len(stem)]
            try:
                occurrences = self._split_prefix(prefix, position)
            except NameParseError:
                continue
            total = sum(m or 1 for m, _ in occurrences)
            if total == nloc_count:
                subs = tuple(
                    Substituent(0, sub, _sub_z(sub), on_nitrogen=True)
                    for m, sub in occurrences
                    for _ in range(m or 1)
                )
                return subs, stem
        raise NameParseError(
            f"cannot extract {nloc_count} N-substituent(s) from {word!r}", position
        )

    # ── Graph construction ──

    def _build_graph(self, parsed: NameParse) -> MolecularGraph:
        builder = MolecularGraphBuilder()
        if parsed.kind == "heterocycle":
            self._add_heterocycle(builder, parsed.heterocycle or "")
        elif parsed.kind == "benzene":
            self._add_benzene(builder, parsed)
        elif parsed.kind == "cycloalkane":
            self._add_cycloalkane(builder, parsed)
        else:
            self._add_chain(builder, parsed)
        return self._add_hydrogens(builder)

    def _attach_sub(self, builder: MolecularGraphBuilder, anchor: int, sub: Substituent) -> None:
        """Attach a prefix substituent branch at ``anchor``."""
        if sub.name == "nitro":
            n1 = builder.add_atom(7, formal_charge=1)
            builder.add_bond(anchor, n1, BondOrder.SINGLE)
            o1 = builder.add_atom(8, formal_charge=-1)
            builder.add_bond(n1, o1, BondOrder.SINGLE)
            od = builder.add_atom(8)
            builder.add_bond(n1, od, BondOrder.DOUBLE)
            return
        if sub.name in _PREFIX_SUBS:
            idx = builder.add_atom(_PREFIX_SUBS[sub.name])
            builder.add_bond(anchor, idx, BondOrder.SINGLE)
            return
        length = _SUB_LENGTHS.get(sub.name)
        if length is None:
            raise NameParseError(f"unsupported substituent {sub.name!r}", -1)
        prev = anchor
        for _ in range(length):
            idx = builder.add_atom(6)
            builder.add_bond(prev, idx, BondOrder.SINGLE)
            prev = idx

    def _add_chain(self, builder: MolecularGraphBuilder, parsed: NameParse) -> None:
        n = parsed.parent_length
        atoms = [builder.add_atom(6) for _ in range(n)]
        unsat = dict(parsed.unsaturations)
        for i in range(n - 1):
            order = unsat.pop(i + 1, BondOrder.SINGLE)
            builder.add_bond(atoms[i], atoms[i + 1], order)
        if unsat:
            raise NameParseError("unsaturation locant beyond the parent chain", -1)

        if parsed.principal == "oic acid":
            o1 = builder.add_atom(8)
            builder.add_bond(atoms[0], o1, BondOrder.DOUBLE)
            o2 = builder.add_atom(8)
            builder.add_bond(atoms[0], o2, BondOrder.SINGLE)
        elif parsed.principal == "oate" and parsed.alkyl_alkyl:
            o1 = builder.add_atom(8)
            builder.add_bond(atoms[0], o1, BondOrder.DOUBLE)
            o2 = builder.add_atom(8)
            builder.add_bond(atoms[0], o2, BondOrder.SINGLE)
            prev = o2
            for _ in range(_SUB_LENGTHS[parsed.alkyl_alkyl]):
                c = builder.add_atom(6)
                builder.add_bond(prev, c, BondOrder.SINGLE)
                prev = c
        elif parsed.principal == "amide":
            o1 = builder.add_atom(8)
            builder.add_bond(atoms[0], o1, BondOrder.DOUBLE)
            n1 = builder.add_atom(7)
            builder.add_bond(atoms[0], n1, BondOrder.SINGLE)
            for sub in parsed.n_substituents:
                self._attach_sub(builder, n1, sub)
        elif parsed.principal == "nitrile":
            n1 = builder.add_atom(7)
            builder.add_bond(atoms[0], n1, BondOrder.TRIPLE)
        elif parsed.principal == "al":
            for loc in parsed.principal_locants or (1,):
                o1 = builder.add_atom(8)
                builder.add_bond(atoms[loc - 1], o1, BondOrder.DOUBLE)
        elif parsed.principal in ("one", "ol"):
            for loc in parsed.principal_locants:
                idx = builder.add_atom(8)
                order = BondOrder.DOUBLE if parsed.principal == "one" else BondOrder.SINGLE
                builder.add_bond(atoms[loc - 1], idx, order)
        elif parsed.principal == "amine":
            loc = parsed.principal_locants[0]
            n1 = builder.add_atom(7)
            builder.add_bond(atoms[loc - 1], n1, BondOrder.SINGLE)
            for sub in parsed.n_substituents:
                self._attach_sub(builder, n1, sub)

        for sub in parsed.substituents:
            if sub.locant == 0:
                raise NameParseError("substituent without an assigned locant", -1)
            self._attach_sub(builder, atoms[sub.locant - 1], sub)

    def _add_cycloalkane(self, builder: MolecularGraphBuilder, parsed: NameParse) -> None:
        n = parsed.parent_length
        atoms = [builder.add_atom(6) for _ in range(n)]

        for i in range(n):
            builder.add_bond(atoms[i], atoms[(i + 1) % n], BondOrder.SINGLE)
        if parsed.unsaturations:
            for pos, order in parsed.unsaturations:
                # Remove the specific ring bond that this unsaturation
                # replaces (pos -> pos+1, wrapping at the ring size), not a
                # positional index into the bond list.
                a1 = atoms[pos - 1]
                a2 = atoms[pos % n]
                for j, bond in enumerate(builder._bonds):
                    pair = {bond.atom1, bond.atom2}
                    if pair == {a1, a2}:
                        builder.remove_bond(j)
                        break
                builder.add_bond(a1, a2, order)
        for sub in parsed.substituents:
            if sub.locant == 0:
                raise NameParseError("cycloalkane substituent without a locant", -1)
            self._attach_sub(builder, atoms[sub.locant - 1], sub)
        if parsed.principal == "ol":
            o = builder.add_atom(8)
            builder.add_bond(atoms[0], o, BondOrder.SINGLE)
        elif parsed.principal == "amine":
            n1 = builder.add_atom(7)
            builder.add_bond(atoms[0], n1, BondOrder.SINGLE)

    def _add_benzene(self, builder: MolecularGraphBuilder, parsed: NameParse) -> None:
        atoms = [builder.add_atom(6, is_aromatic=True) for _ in range(6)]
        for i in range(6):
            builder.add_bond(atoms[i], atoms[(i + 1) % 6], BondOrder.AROMATIC)
        for sub in parsed.substituents:
            if sub.locant == 0:
                raise NameParseError("benzene substituent without a locant", -1)
            self._attach_sub(builder, atoms[sub.locant - 1], sub)
        if parsed.principal == "ol":
            o = builder.add_atom(8)
            builder.add_bond(atoms[0], o, BondOrder.SINGLE)

    def _add_heterocycle(self, builder: MolecularGraphBuilder, name: str) -> None:
        size, template, aromatic = _HETEROCYCLES[name]
        atoms = [builder.add_atom(z) for z, _h in template]
        order = BondOrder.AROMATIC if aromatic else BondOrder.SINGLE
        for i in range(size):
            builder.add_bond(atoms[i], atoms[(i + 1) % size], order)

    def _add_hydrogens(self, builder: MolecularGraphBuilder) -> MolecularGraph:
        """Complete explicit hydrogens from default valences."""
        graph = builder.build()
        pending: list[int] = []
        for i, atom in enumerate(graph.atoms):
            # Formal charge adjusts the valence budget: O(-) bonds once
            # (hydroxide), N(+) bonds four times (nitro nitrogen).
            valence = _DEFAULT_VALENCE.get(atom.atomic_number, 0) \
                + getattr(atom, "formal_charge", 0)
            if valence <= 0:
                continue
            used = 0.0
            for n in graph.get_neighbors(i):
                bond = graph.get_bond(i, n)
                if bond is None:
                    continue
                if bond.is_aromatic:
                    used += 1.5
                else:
                    used += float(getattr(bond.order, "value", 1))
            for _ in range(max(int(valence - used + 0.001), 0)):
                pending.append(i)
        for anchor in pending:
            h = builder.add_atom(1)
            builder.add_bond(anchor, h, BondOrder.SINGLE)
        return builder.build()


def _sub_z(name: str) -> int:
    if name in _SUB_LENGTHS:
        return 6
    return _PREFIX_SUBS.get(name, 6)
