"""Seeded learning content.

CONTENT OWNERSHIP (important architectural rule):
- Educational content (lessons, sections, questions, explanations) belongs to
  the application/backend layer, NOT to ChemEngine and NOT to the frontend.
- Chemistry *values* displayed in lessons are never hardcoded here. Sections
  of kind ``chemistry_spotlight`` reference an element by symbol, and the
  client renders live ChemEngine data through the existing
  ``GET /api/v1/elements/{symbol}`` endpoint (M23). Prose explains the
  chemistry; the engine computes it.

This module is the clearly isolated seed layer. It can later be migrated into
PostgreSQL / an admin CMS without changing the learning API contract or the
frontend learning architecture. Correct answers are stored server-side only
and are never serialized to clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SECTION_KINDS = (
    "introduction",
    "explanation",
    "chemistry_spotlight",
    "practice",
    "summary",
)

QUESTION_KINDS = (
    "multiple_choice",
    "numeric",
    "formula",
    "element",
)


@dataclass(frozen=True, slots=True)
class Question:
    """A practice question. ``correct`` never leaves the server.

    Validation by kind (see ``services.learning``):
    - ``multiple_choice`` / ``numeric``: normalized exact comparison.
    - ``formula``: the answer is canonicalized by ChemEngine (Hill notation),
      so equivalent element orderings (``HOH`` vs ``H2O``) are accepted while
      chemically different formulas are rejected. Unparseable answers are a
      client-safe ``invalid_answer`` error, never a silent "correct".
    - ``element``: the answer must resolve to the expected element — exact-case
      symbol (``Cl``), case-insensitive full name (``chlorine``), or atomic
      number (``17``) — mirroring the Element Explorer lookup rules.
    """

    id: str
    kind: str  # one of QUESTION_KINDS
    prompt: str
    correct: str  # expected answer (canonical form for chemistry kinds)
    explanation: str
    options: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Section:
    """One lesson section.

    ``element_symbol`` is only set for ``chemistry_spotlight`` sections and
    tells the client which element's live ChemEngine data to display.
    """

    id: str
    kind: str  # one of SECTION_KINDS
    title: str
    body: tuple[str, ...]
    element_symbol: str | None = None
    # ``molecule_input`` (chemistry_spotlight only): a formula/SMILES/InChI
    # string the client analyses live via the existing chemistry explore API
    # (M22). Never stored as precomputed values — the engine computes it.
    molecule_input: str | None = None
    question_ids: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Lesson:
    """A learning lesson with ordered sections and questions."""

    id: str
    slug: str
    title: str
    description: str
    subject: str
    difficulty: str
    estimated_minutes: int
    order: int
    sections: tuple[Section, ...]
    questions: tuple[Question, ...]

    def question_by_id(self, question_id: str) -> Question | None:
        """Return the question with the given id, if present."""
        for question in self.questions:
            if question.id == question_id:
                return question
        return None


def _q(
    qid: str,
    prompt: str,
    correct: str,
    explanation: str,
    options: tuple[str, ...] = (),
    kind: str | None = None,
) -> Question:
    """Build a question; the kind is inferred unless given explicitly."""
    if kind is None:
        kind = "multiple_choice" if options else "numeric"
    return Question(
        id=qid,
        kind=kind,
        prompt=prompt,
        correct=correct,
        explanation=explanation,
        options=options,
    )


LESSONS: tuple[Lesson, ...] = ()  # populated at the bottom of this module


def get_lessons() -> tuple[Lesson, ...]:
    """Return all lessons in their curated order."""
    return tuple(sorted(LESSONS, key=lambda lesson: lesson.order))


def get_lesson_by_slug(slug: str) -> Lesson | None:
    """Return the lesson with the given slug, or None."""
    for lesson in LESSONS:
        if lesson.slug == slug:
            return lesson
    return None


# ── Seeded lessons ────────────────────────────────────────────────────────

LESSON_ELECTRON_CONFIGURATION = Lesson(
    id="lesson-electron-configuration",
    slug="electron-configuration",
    title="Electron Configurations",
    description=(
        "How electrons arrange themselves around a nucleus — and how "
        "Chemora computes that arrangement from first principles."
    ),
    subject="atomic structure",
    difficulty="beginner",
    estimated_minutes=8,
    order=1,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="Why arrangements matter",
            body=(
                "Every atom contains electrons, and where those electrons sit "
                "determines almost everything about how the element behaves "
                "in chemistry.",
                "Electrons fill orbitals following three simple rules: the "
                "Aufbau principle (lowest energy first), the Pauli exclusion "
                "principle (at most two electrons per orbital), and Hund's "
                "rule (degenerate orbitals fill singly before pairing).",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="Reading a configuration",
            body=(
                "A configuration like 1s2 2s2 2p4 is a list of subshells and "
                "how many electrons each holds. The number is the shell "
                "(energy level), the letter is the subshell type (s holds 2, "
                "p holds 6, d holds 10, f holds 14), and the superscript is "
                "the electron count.",
                "The filling order is not simply 1s, 2s, 2p, 3s, 3p, 3d — "
                "the Madelung order inserts 4s before 3d, which is why the "
                "periodic table has its recognizable shape.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="See it live",
            body=(
                "Pick an element below. Its configuration, shells, and "
                "orbital diagram are computed live by the Chemora chemistry "
                "engine — not stored as text.",
            ),
            element_symbol="O",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("ec-1", "ec-2"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Configurations follow Aufbau, Pauli, and Hund's rules.",
                "The engine computes every configuration from the atomic "
                "number — including well-known exceptions like chromium and "
                "copper.",
            ),
        ),
    ),
    questions=(
        _q(
            "ec-1",
            "How many electrons can a single 2p subshell hold at most?",
            "6",
            "A p subshell has three degenerate orbitals of two electrons "
            "each, so it holds up to 6 electrons.",
        ),
        _q(
            "ec-2",
            "Which rule says degenerate orbitals fill singly before pairing?",
            "Hund's rule",
            "Hund's rule maximizes total spin: electrons spread across "
            "equal-energy orbitals before any orbital receives a second "
            "electron.",
            ("Aufbau principle", "Hund's rule", "Pauli exclusion principle"),
        ),
    ),
)

LESSON_VALENCE_ELECTRONS = Lesson(
    id="lesson-valence-electrons",
    slug="valence-electrons",
    title="Valence Electrons",
    description=(
        "The outermost electrons do the chemistry. Learn to count them from "
        "any configuration."
    ),
    subject="atomic structure",
    difficulty="beginner",
    estimated_minutes=6,
    order=2,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="The outer shell matters most",
            body=(
                "Valence electrons are the electrons in the outermost shell. "
                "They are the ones gained, lost, or shared when elements "
                "react.",
                "Core electrons sit closer to the nucleus and are rarely "
                "involved in bonding.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="Counting valence electrons",
            body=(
                "Take the highest shell number in the configuration and add "
                "up the electrons in its subshells. For oxygen (1s2 2s2 2p4) "
                "the highest shell is n=2, holding 2 + 4 = 6 valence "
                "electrons.",
                "Every element in the same periodic-table group shares the "
                "same valence count — that is why they behave similarly.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Count them yourself",
            body=(
                "Select elements and compare the highest-shell electron "
                "counts shown by the engine.",
            ),
            element_symbol="Na",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("ve-1",),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Valence electrons = electrons in the highest shell.",
                "The engine reports valence and core counts separately for "
                "every element.",
            ),
        ),
    ),
    questions=(
        _q(
            "ve-1",
            "Oxygen has the configuration 1s2 2s2 2p4. How many valence "
            "electrons does it have?",
            "6",
            "The highest shell is n=2, which holds 2s2 + 2p4 = 6 electrons. "
            "The engine reports exactly this for oxygen.",
        ),
    ),
)

LESSON_CONFIGURATION_BEHAVIOR = Lesson(
    id="lesson-configuration-behavior",
    slug="configuration-and-behavior",
    title="From Configuration to Chemical Behavior",
    description=(
        "Connect electron configurations to reactivity — why some elements "
        "are inert and others react eagerly."
    ),
    subject="periodic behavior",
    difficulty="intermediate",
    estimated_minutes=10,
    order=3,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="One configuration, one personality",
            body=(
                "Noble gases are famously unreactive because their outermost "
                "shells are full. Alkali metals are famously reactive because "
                "a single valence electron is easy to lose.",
                "Chemistry is largely the pursuit of full outer shells.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="Unpaired electrons and reactivity",
            body=(
                "Unpaired electrons in the outer shell are bonding "
                "opportunities. Oxygen has two unpaired 2p electrons, which "
                "is why it forms two bonds in water.",
                "Halogens need just one electron to complete their outer "
                "shell, so they aggressively take one — making them strong "
                "oxidizers.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Compare two elements",
            body=(
                "Compare a noble gas with a halogen: look at the unpaired "
                "electron counts and the fullness of the outer shell in the "
                "live engine data.",
            ),
            element_symbol="Cl",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("cb-1", "cb-2"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Full outer shells mean inert; nearly empty or nearly full "
                "means reactive.",
                "Valence and unpaired electron counts from the engine predict "
                "bonding behaviour.",
            ),
        ),
    ),
    questions=(
        _q(
            "cb-1",
            "Why are noble gases chemically inert?",
            "Their outermost electron shells are full",
            "A full outer shell leaves no energetically favourable way to "
            "bond, so noble gases rarely react.",
            (
                "They have no electrons",
                "Their outermost electron shells are full",
                "They are radioactive",
            ),
        ),
        _q(
            "cb-2",
            "How many unpaired electrons does oxygen have in its ground "
            "state?",
            "2",
            "Oxygen's 2p4 arrangement pairs two of the three 2p orbitals, "
            "leaving two orbitals with single electrons — the engine reports "
            "2 unpaired electrons.",
        ),
    ),
)

LESSON_CHEMICAL_FORMULAS = Lesson(
    id="lesson-chemical-formulas",
    slug="chemical-formulas",
    title="Chemical Formulas",
    description=(
        "What a formula tells you — atom counts, molecular mass, and why a "
        "formula deliberately says nothing about shape."
    ),
    subject="chemical formulas",
    difficulty="beginner",
    estimated_minutes=9,
    order=4,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="A formula is a count, not a map",
            body=(
                "A chemical formula such as H2O tells you which elements are "
                "present and how many atoms of each. It does not tell you how "
                "the atoms are connected — that is a structural question.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="From counts to mass",
            body=(
                "Because a formula lists exact atom counts, it determines the "
                "molecular mass: add up the average atomic masses. The engine "
                "also computes the exact mass from isotopic masses — these are "
                "two different numbers, and Chemora keeps them distinct.",
                "Equivalent orderings describe the same composition: HOH and "
                "H2O are the same formula. Chemora's engine canonicalizes any "
                "formula to one standard form, which is how practice answers "
                "are graded fairly.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Analyse a formula live",
            body=(
                "The engine parses the formula below and reports its "
                "composition and molecular properties, computed on demand — "
                "nothing here is stored text.",
            ),
            molecule_input="H2O",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("fm-1", "fm-2"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Formulas encode composition, not connectivity.",
                "The engine canonicalizes formulas, so equivalent spellings "
                "grade identically while different compositions grade "
                "differently.",
            ),
        ),
    ),
    questions=(
        _q(
            "fm-1",
            "Which chemical formula represents a molecule with two hydrogen "
            "atoms and one oxygen atom?",
            "H2O",
            "Water is H2O: two hydrogen atoms and one oxygen atom. The engine "
            "accepts any valid formula notation and canonicalizes it for fair "
            "grading, so equivalent spellings like HOH map to the same formula.",
            kind="formula",
        ),
        _q(
            "fm-2",
            "What does a chemical formula like H2O NOT tell you?",
            "How the atoms are connected",
            "A formula lists element counts — it says nothing about how atoms "
            "are bonded or arranged spatially. Connectivity and shape come from "
            "the molecular structure, which the engine can derive from a SMILES "
            "string.",
            (
                "How the atoms are connected",
                "How many atoms of each element are present",
                "The molecular mass",
            ),
        ),
    ),
)

LESSON_MOLECULES_AND_PROPERTIES = Lesson(
    id="lesson-molecules-and-properties",
    slug="molecules-and-properties",
    title="Molecules and Their Properties",
    description=(
        "From molecular structure to predictable behaviour — descriptors the "
        "engine computes deterministically."
    ),
    subject="molecular properties",
    difficulty="intermediate",
    estimated_minutes=10,
    order=5,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="Structure determines behaviour",
            body=(
                "Two molecules built from the same atoms can behave very "
                "differently when bonded differently. Chemora's engine derives "
                "structure from notation such as SMILES, then computes "
                "properties from that structure — deterministically.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="Descriptors that predict behaviour",
            body=(
                "Polar surface area (TPSA) and hydrogen-bond donors and "
                "acceptors hint at water solubility. LogP hints at whether a "
                "molecule crosses fatty membranes. None of these are opinions "
                "— the engine computes each from the molecular graph.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Inspect ethanol",
            body=(
                "Ethanol (SMILES: CCO) is small but instructive: an -OH group "
                "gives it a hydrogen-bond donor and an acceptor, which is why "
                "it mixes with water. Check the live engine data below.",
            ),
            molecule_input="CCO",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("mp-1", "mp-2"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Structure → descriptors → behaviour, all computed "
                "deterministically by the engine.",
            ),
        ),
    ),
    questions=(
        _q(
            "mp-1",
            "Which element has exactly 11 protons in every atom?",
            "Na",
            "Atomic number 11 is sodium (Na). Answer with the symbol, the "
            "name, or the atomic number — all resolve to the same element.",
            kind="element",
        ),
        _q(
            "mp-2",
            "Which descriptor is most directly related to a molecule's "
            "ability to dissolve in water?",
            "Total polar surface area",
            "Polar surfaces interact favourably with polar water molecules; "
            "TPSA summarizes exactly that. The engine computes it from the "
            "structure.",
            (
                "Total polar surface area",
                "Exact monoisotopic mass",
                "Fraction of C(sp3) atoms",
            ),
        ),
    ),
)

LESSONS = (
    LESSON_ELECTRON_CONFIGURATION,
    LESSON_VALENCE_ELECTRONS,
    LESSON_CONFIGURATION_BEHAVIOR,
    LESSON_CHEMICAL_FORMULAS,
    LESSON_MOLECULES_AND_PROPERTIES,
)




