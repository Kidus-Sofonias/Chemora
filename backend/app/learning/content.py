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

QUESTION_KINDS = ("multiple_choice", "numeric")


@dataclass(frozen=True, slots=True)
class Question:
    """A practice question. ``correct`` never leaves the server."""

    id: str
    kind: str  # one of QUESTION_KINDS
    prompt: str
    correct: str  # exact expected answer (option text or numeric string)
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
) -> Question:
    """Build a question; the kind is inferred from whether options exist."""
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

LESSONS = (
    LESSON_ELECTRON_CONFIGURATION,
    LESSON_VALENCE_ELECTRONS,
    LESSON_CONFIGURATION_BEHAVIOR,
)




