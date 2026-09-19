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

# ── M28 curriculum expansion ─────────────────────────────────────────────

LESSON_PERIODIC_TABLE = Lesson(
    id="lesson-periodic-table",
    slug="periodic-table",
    title="The Periodic Table",
    description=(
        "How the table organizes every known element by atomic number and "
        "electron arrangement — and why its shape is no accident."
    ),
    subject="periodic table",
    difficulty="beginner",
    estimated_minutes=7,
    order=6,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="A map of the elements",
            body=(
                "By 1869, chemists had measured the properties of dozens of "
                "elements and noticed patterns repeating with growing atomic "
                "mass. Dmitri Mendeleev arranged them so that similar "
                "elements fell into the same column — and left gaps for "
                "elements nobody had discovered yet.",
                "Today the table is ordered by atomic number (the number of "
                "protons), not mass. It is not an arbitrary convention: the "
                "order is the Aufbau filling order the configuration engine "
                "computes, so the table's block structure is a direct "
                "consequence of electron orbitals.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="Groups, periods, and blocks",
            body=(
                "Columns are groups: elements there share the same number of "
                "valence electrons, which is why they behave alike. Rows are "
                "periods: each one starts filling a new shell. The s-block "
                "(groups 1–2), p-block (groups 13–18), d-block (transition "
                "metals), and f-block (lanthanides and actinides) are named "
                "for the subshell being filled.",
                "Group 18 — the noble gases — have completely filled shells, "
                "which is why they are so unreactive. Everything else in "
                "chemistry is, in a sense, elements trying to reach a noble "
                "gas configuration.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="See it live",
            body=(
                "Neon sits in group 18 with a completely filled outer shell. "
                "Its configuration, shell diagram, and valence count are "
                "computed live by the chemistry engine — compare them with "
                "the reactive elements around it.",
            ),
            element_symbol="Ne",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("pt-1", "pt-2", "pt-3"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "The table is ordered by atomic number; columns share valence "
                "electron counts.",
                "The s/p/d/f blocks mirror the orbital filling order — the "
                "table's shape IS quantum mechanics.",
            ),
        ),
    ),
    questions=(
        _q(
            "pt-1",
            "What property orders the modern periodic table?",
            "atomic number",
            "The modern table orders elements by atomic number — the proton "
            "count — which fixes the electron count and therefore the "
            "chemistry.",
            ("atomic mass", "atomic number", "number of neutrons", "density"),
        ),
        _q(
            "pt-2",
            "Name the element in group 18, period 2 (its symbol).",
            "Ne",
            "Neon is the noble gas of period 2. Its filled 1s2 2s2 2p6 shell "
            "makes it almost entirely unreactive.",
            kind="element",
        ),
        _q(
            "pt-3",
            "How many valence electrons do elements in group 2 have?",
            "2",
            "Group 2 (alkaline earth metals) fills the s subshell with two "
            "electrons — Be, Mg, Ca and friends all share that count.",
        ),
    ),
)

LESSON_PERIODIC_TRENDS = Lesson(
    id="lesson-periodic-trends",
    slug="periodic-trends",
    title="Periodic Trends",
    description=(
        "Atomic size, ionization energy, and electronegativity are not "
        "random — they follow the table's geometry."
    ),
    subject="periodic table",
    difficulty="intermediate",
    estimated_minutes=8,
    order=7,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="Patterns with a cause",
            body=(
                "Move across a period and atoms get smaller; move down a "
                "group and they get larger. These are not memorized facts "
                "but consequences of two competing forces: nuclear attraction "
                "pulling electrons in, and inner-shell shielding pushing "
                "them out.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="The three big trends",
            body=(
                "Atomic radius decreases left to right: protons are added "
                "faster than shielding, so the pull on the valence shell "
                "grows. Radius increases down a group: each period adds a "
                "whole new shell outside the core.",
                "Ionization energy — the energy to remove an electron — "
                "rises left to right (smaller atoms hold electrons tighter) "
                "and falls down a group (outer electrons are farther away "
                "and better shielded). Electronegativity, an atom's pull on "
                "bonding electrons, follows the same pattern; fluorine is "
                "the champion.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Sodium versus chlorine",
            body=(
                "Sodium (group 1) and chlorine (group 17) sit in the same "
                "period but at opposite ends — one hands its electron away, "
                "the other grabs one. Both configurations are computed live "
                "by the engine; notice how close each is to a filled shell.",
            ),
            element_symbol="Na",
        ),
        Section(
            id="spotlight-cl",
            kind="chemistry_spotlight",
            title="The other end of the period",
            body=(
                "Chlorine needs exactly one electron to reach argon's "
                "configuration — that hunger drives its chemistry.",
            ),
            element_symbol="Cl",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("trend-1", "trend-2", "trend-3"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Radius shrinks across a period and grows down a group; "
                "ionization energy and electronegativity do the opposite.",
                "Trends come from nuclear pull versus shielding — learn the "
                "cause and you never memorize the arrows.",
            ),
        ),
    ),
    questions=(
        _q(
            "trend-1",
            "How does atomic radius change from left to right across a period?",
            "it decreases",
            "Each added proton pulls harder on a shell that gains almost no "
            "extra shielding, so atoms contract across a period.",
            ("it increases", "it decreases", "it stays the same"),
        ),
        _q(
            "trend-2",
            "Which element has the highest electronegativity?",
            "F",
            "Fluorine tops the scale: it is small (little shielding) and "
            "one electron short of a filled shell (strong pull).",
            kind="element",
        ),
        _q(
            "trend-3",
            "Why does ionization energy decrease down a group?",
            "the outer electron is farther from the nucleus and better shielded",
            "Each new period adds an inner shell, pushing the valence "
            "electrons out and buffering the nuclear pull.",
            (
                "the outer electron is farther from the nucleus and better shielded",
                "the nucleus loses protons down a group",
                "electrons get heavier down a group",
                "shielding gets weaker down a group",
            ),
        ),
    ),
)

LESSON_CHEMICAL_BONDING = Lesson(
    id="lesson-chemical-bonding",
    slug="chemical-bonding",
    title="Chemical Bonding",
    description=(
        "Why atoms combine: ionic bonds hand electrons over, covalent "
        "bonds share them — and the engine shows both."
    ),
    subject="chemical bonding",
    difficulty="beginner",
    estimated_minutes=9,
    order=8,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="The noble-gas destination",
            body=(
                "Atoms bond for one overriding reason: to reach the "
                "stability of a filled valence shell, like the noble gases "
                "already have. There are two strategies for getting there — "
                "transferring electrons or sharing them.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="Ionic and covalent bonding",
            body=(
                "When a metal meets a nonmetal, electrons transfer. Sodium "
                "gives its lone valence electron to chlorine; both become "
                "ions with noble-gas configurations, and the opposite "
                "charges lock into a crystal lattice — sodium chloride, "
                "table salt.",
                "When two nonmetals meet, neither can easily surrender, so "
                "they share. Two hydrogens and an oxygen share electron "
                "pairs to form water. Sharing can be equal (H2, oxygen gas) "
                "or lopsided (water's oxygen hogs the electrons, making the "
                "molecule polar).",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Salt, live",
            body=(
                "Sodium chloride is the classic ionic compound. Analyse it "
                "with the chemistry engine: the formula, masses, and "
                "structure are computed from the same rules that predicted "
                "the electron transfer.",
            ),
            molecule_input="NaCl",
        ),
        Section(
            id="spotlight-h2o",
            kind="chemistry_spotlight",
            title="Water, live",
            body=(
                "Water is the classic polar covalent molecule — shared "
                "electrons that lean toward oxygen. Its live analysis shows "
                "the polarity in the computed descriptors.",
            ),
            molecule_input="H2O",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("bond-1", "bond-2", "bond-3"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Metal + nonmetal usually means ionic (transfer); nonmetal + "
                "nonmetal means covalent (sharing).",
                "Both bond types drive toward the same goal: a noble-gas "
                "valence shell.",
            ),
        ),
    ),
    questions=(
        _q(
            "bond-1",
            "What kind of bond forms between sodium and chlorine?",
            "ionic bond",
            "Sodium transfers its electron to chlorine; the resulting ions "
            "attract electrostatically — an ionic bond.",
            ("ionic bond", "covalent bond", "metallic bond", "no bond forms"),
        ),
        _q(
            "bond-2",
            "Write the molecular formula of water.",
            "H2O",
            "Two hydrogens share electrons with one oxygen — H2O. The "
            "engine canonicalizes formula answers, so equivalent orderings "
            "like OH2 are accepted too.",
            kind="formula",
        ),
        _q(
            "bond-3",
            "Why do noble gases rarely form bonds?",
            "their valence shells are already full",
            "Bonding exists to reach a filled shell; noble gases already "
            "have one, so they have nothing to gain.",
            (
                "their valence shells are already full",
                "they are too heavy to move",
                "their nuclei repel everything",
                "they have too many protons",
            ),
        ),
    ),
)

LESSON_MOLAR_MASS = Lesson(
    id="lesson-molar-mass",
    slug="molar-mass",
    title="Molar Mass",
    description=(
        "The bridge between the invisible world of atoms and the weighable "
        "world of the lab — computed from atomic masses."
    ),
    subject="stoichiometry",
    difficulty="intermediate",
    estimated_minutes=8,
    order=9,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="Counting by weighing",
            body=(
                "Atoms are absurdly small: a single drop of water contains "
                "more molecules than there are stars in the observable "
                "universe. Nobody counts atoms one by one — chemists count "
                "them by weighing.",
                "The bridge is the mole: 6.022 x 10^23 particles (Avogadro's "
                "number). One mole of any substance has a mass in grams "
                "equal to its atomic or molecular mass in unified atomic "
                "mass units. That number is the molar mass.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="Computing molar mass",
            body=(
                "Molar mass is the sum of every atom's atomic mass in a "
                "formula. Water, H2O: two hydrogens at about 1.008 plus one "
                "oxygen at about 16.00 gives 18.015 g/mol. Glucose, "
                "C6H12O6: six carbons, twelve hydrogens, six oxygens add to "
                "180.16 g/mol.",
                "The Chemora engine computes these sums from tabulated "
                "isotopic abundances every time — never from memorized "
                "values. The average mass shown in each molecule spotlight "
                "below IS the molar mass.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Water, weighed",
            body=(
                "The engine computes water's exact mass from isotopes and "
                "its average mass from natural abundance — the latter is "
                "the 18.015 g/mol you use in the lab.",
            ),
            molecule_input="H2O",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("mm-1", "mm-2", "mm-3"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "One mole = 6.022 x 10^23 particles; molar mass in g/mol "
                "equals the formula's atomic-mass sum.",
                "Convert mass to moles by dividing by molar mass — the "
                "single most-used conversion in chemistry.",
            ),
        ),
    ),
    questions=(
        _q(
            "mm-1",
            "How many particles are in one mole?",
            "6.022e23",
            "Avogadro's number, 6.022 x 10^23, is the counting unit that "
            "connects atomic masses to grams.",
            ("6.022e23", "6.022e22", "3.14e23", "1.602e19"),
        ),
        _q(
            "mm-2",
            "Use the periodic table: what is the molar mass of CO2 in "
            "g/mol, rounded to one decimal? (C: 12.0, O: 16.0)",
            "44.0",
            "12.0 + 2 x 16.0 = 44.0 g/mol. The engine computes the precise "
            "value from isotopic data; the rounded table values give 44.0.",
        ),
        _q(
            "mm-3",
            "Convert 36.0 grams of water to moles (molar mass 18.0 g/mol).",
            "2.0",
            "Moles = mass / molar mass = 36.0 / 18.0 = 2.0 mol.",
        ),
    ),
)

LESSON_STOICHIOMETRY = Lesson(
    id="lesson-stoichiometry",
    slug="stoichiometry",
    title="Stoichiometry",
    description=(
        "Reaction math: balanced equations predict exactly how much "
        "reactant is consumed and product made."
    ),
    subject="stoichiometry",
    difficulty="advanced",
    estimated_minutes=10,
    order=10,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="Recipes for reactions",
            body=(
                "A balanced chemical equation is a recipe with exact "
                "proportions. Methane burning — CH4 + 2 O2 -> CO2 + 2 H2O — "
                "says one methane reacts with two oxygens to make one CO2 "
                "and two waters. Change the proportions and something is "
                "left over or runs short.",
                "Atoms are never created or destroyed, which is exactly why "
                "equations must balance: the same atoms must appear on both "
                "sides, merely rearranged.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="From balanced equation to grams",
            body=(
                "The coefficients give mole ratios. To find how much product "
                "a mass of reactant yields: convert grams to moles (divide "
                "by molar mass), apply the mole ratio from the equation, "
                "then convert moles back to grams (multiply by molar mass).",
                "The limiting reactant is the one that runs out first — it "
                "caps the product. The others are in excess. The Chemora "
                "engine can balance equations and carry out these "
                "conversions deterministically.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Methane, live",
            body=(
                "Methane is the fuel in the classic CH4 + 2 O2 -> CO2 + "
                "2 H2O recipe. Its molar mass — computed live below — is "
                "the conversion factor for the practice questions.",
            ),
            molecule_input="CH4",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("stoich-1", "stoich-2", "stoich-3"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Balance the equation, convert to moles, follow the mole "
                "ratio, convert back — that is all of stoichiometry.",
                "The limiting reactant determines the maximum product.",
            ),
        ),
    ),
    questions=(
        _q(
            "stoich-1",
            "Balance the combustion of methane: __ CH4 + 2 O2 -> 1 CO2 + "
            "2 H2O. What coefficient goes in the blank?",
            "1",
            "One methane supplies the single carbon and all four hydrogens "
            "of the products — the equation is balanced with 1.",
        ),
        _q(
            "stoich-2",
            "In CH4 + 2 O2 -> CO2 + 2 H2O, how many moles of water form "
            "from 2 moles of methane (excess oxygen)?",
            "4",
            "The ratio is 1 CH4 : 2 H2O, so 2 mol methane yields 2 x 2 = "
            "4 mol water.",
        ),
        _q(
            "stoich-3",
            "In that same reaction, 1 mol CH4 reacts with only 1 mol O2. "
            "Which is the limiting reactant? (formula)",
            "O2",
            "Burning 1 mol CH4 needs 2 mol O2, but only 1 is available — "
            "oxygen runs out first and limits the reaction.",
            kind="formula",
        ),
    ),
)

LESSON_ACIDS_BASES = Lesson(
    id="lesson-acids-bases",
    slug="acids-bases",
    title="Acids and Bases",
    description=(
        "Proton donors, hydroxide donors, and the pH scale that measures "
        "the balance between them."
    ),
    subject="acids and bases",
    difficulty="intermediate",
    estimated_minutes=8,
    order=11,
    sections=(
        Section(
            id="intro",
            kind="introduction",
            title="Two families of reactivity",
            body=(
                "Acids taste sour, turn litmus red, and react with metals; "
                "bases feel slippery, turn litmus blue, and neutralize "
                "acids. Arrhenius explained both: acids release H+ ions in "
                "water, bases release OH- ions.",
                "Bronsted and Lowry deepened the idea: an acid is a proton "
                "donor and a base is a proton acceptor — which is why "
                "acids and bases neutralize each other to water and a salt.",
            ),
        ),
        Section(
            id="explain",
            kind="explanation",
            title="The pH scale",
            body=(
                "pH measures the concentration of H+ on a logarithmic "
                "scale: pH = -log10[H+]. Pure water sits at 7 (neutral). "
                "Each whole step is a tenfold change — pH 2 is not twice "
                "but one hundred times more acidic than pH 4.",
                "Strong acids like HCl dissociate completely; weak acids "
                "like acetic acid (CH3COOH, the acid in vinegar) only "
                "partly. The same distinction applies to bases, with "
                "ammonia as the classic weak base.",
            ),
        ),
        Section(
            id="spotlight",
            kind="chemistry_spotlight",
            title="Vinegar's acid, live",
            body=(
                "Acetic acid gives vinegar its sharp taste. Analyse it "
                "live: the engine computes its formula, masses, and "
                "polar descriptors from its structure.",
            ),
            molecule_input="CH3COOH",
        ),
        Section(
            id="spotlight-hcl",
            kind="chemistry_spotlight",
            title="The classic strong acid",
            body=(
                "Hydrochloric acid — one proton donor, the model strong "
                "acid. Its live analysis shows the simplicity behind its "
                "aggressive chemistry.",
            ),
            molecule_input="HCl",
        ),
        Section(
            id="practice",
            kind="practice",
            title="Check your understanding",
            body=(),
            question_ids=("ab-1", "ab-2", "ab-3"),
        ),
        Section(
            id="summary",
            kind="summary",
            title="Key takeaways",
            body=(
                "Acids donate H+, bases accept it (or donate OH- in "
                "Arrhenius terms); neutralization makes water plus salt.",
                "pH is logarithmic: every unit is a tenfold change in "
                "acidity.",
            ),
        ),
    ),
    questions=(
        _q(
            "ab-1",
            "In the Bronsted-Lowry picture, what is an acid?",
            "a proton donor",
            "A Bronsted-Lowry acid donates a proton (H+); a base accepts "
            "it. Water can act as either — it is amphoteric.",
            ("a proton donor", "a proton acceptor", "an electron donor", "a neutron source"),
        ),
        _q(
            "ab-2",
            "A solution has pH 3. Another has pH 5. How many times more "
            "acidic is the first?",
            "100",
            "Each pH unit is tenfold, so two units = 10 x 10 = 100 times "
            "more H+ concentration.",
        ),
        _q(
            "ab-3",
            "Write the formula of hydrochloric acid.",
            "HCl",
            "One proton, one chloride — HCl. The engine canonicalizes "
            "formula answers deterministically.",
            kind="formula",
        ),
    ),
)

LESSONS = (
    LESSON_ELECTRON_CONFIGURATION,
    LESSON_VALENCE_ELECTRONS,
    LESSON_CONFIGURATION_BEHAVIOR,
    LESSON_CHEMICAL_FORMULAS,
    LESSON_MOLECULES_AND_PROPERTIES,
    LESSON_PERIODIC_TABLE,
    LESSON_PERIODIC_TRENDS,
    LESSON_CHEMICAL_BONDING,
    LESSON_MOLAR_MASS,
    LESSON_STOICHIOMETRY,
    LESSON_ACIDS_BASES,
)




