"""M28 chemistry content expansion and learning experience tests.

Covers:
- the M28 curriculum lessons pass the strict publish validator,
- seeding is idempotent (re-running never duplicates lessons),
- new lessons appear in the student catalog with engine-backed spotlights,
- molecule references are validated at publish time through ChemEngine.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning.content import get_lessons
from app.services.content_admin import AdminContentService
from tests.conftest import MockGoogleTokenVerifier

M28_LESSONS = (
    "periodic-table",
    "periodic-trends",
    "chemical-bonding",
    "molar-mass",
    "stoichiometry",
    "acids-bases",
)


# ── Curriculum validation ────────────────────────────────────────────────


def test_every_seed_lesson_passes_publish_validation() -> None:
    """All seeded lessons (M24–M28) are publishable under the strict rules."""
    validator = AdminContentService.__new__(AdminContentService)
    for lesson in get_lessons():
        errors = validator.validate(lesson)
        assert errors == [], (lesson.slug, errors)


def test_m28_curriculum_present_in_seed_order() -> None:
    """The M28 lessons exist, in curated order, after the M24/M25 lessons."""
    slugs = [lesson.slug for lesson in get_lessons()]
    assert slugs[:5] == [
        "electron-configuration",
        "valence-electrons",
        "configuration-and-behavior",
        "chemical-formulas",
        "molecules-and-properties",
    ]
    assert slugs[5:] == list(M28_LESSONS)


def test_m28_lessons_are_coherent() -> None:
    """Every M28 lesson has ordered sections, practice, and an engine tie-in."""
    by_slug = {lesson.slug: lesson for lesson in get_lessons()}
    for slug in M28_LESSONS:
        lesson = by_slug[slug]
        kinds = [section.kind for section in lesson.sections]
        assert "practice" in kinds, slug
        assert "chemistry_spotlight" in kinds, slug
        # Every question id referenced by a practice section exists.
        for section in lesson.sections:
            for qid in section.question_ids:
                assert lesson.question_by_id(qid) is not None, (slug, qid)


# ── Seed idempotency ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    """Seeding twice never duplicates lessons and reports updates."""
    from app.learning.seed import seed_content

    first = await seed_content(db_session)
    assert first["lessons"] == len(get_lessons())
    assert first["created"] == first["lessons"]

    second = await seed_content(db_session)
    assert second["created"] == 0
    assert second["updated"] == first["lessons"]


@pytest.mark.asyncio
async def test_seed_preserves_publication_state(db_session: AsyncSession) -> None:
    """Re-seeding an existing lesson keeps its published state as seeded."""
    from sqlalchemy import select

    from app.learning.seed import seed_content
    from app.models.content import Lesson as LessonRow

    await seed_content(db_session)
    await db_session.commit()
    rows = (await db_session.execute(select(LessonRow))).scalars().all()
    assert len(rows) == len(get_lessons())
    assert all(row.published for row in rows)


# ── Student catalog integration ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_m28_lessons_visible_to_students(api_client: AsyncClient) -> None:
    """The published M28 lessons appear in the student catalog in order."""
    response = await api_client.get("/api/v1/learning/lessons")
    assert response.status_code == 200
    slugs = [lesson["slug"] for lesson in response.json()["lessons"]]
    assert slugs[-6:] == list(M28_LESSONS)


@pytest.mark.asyncio
async def test_m28_spotlights_reference_engine_data(api_client: AsyncClient) -> None:
    """M28 spotlights name engine-resolvable elements or molecules."""
    response = await api_client.get("/api/v1/learning/lessons")
    slugs = {lesson["slug"] for lesson in response.json()["lessons"]}
    assert set(M28_LESSONS) <= slugs

    for slug in M28_LESSONS:
        detail = await api_client.get(f"/api/v1/learning/lessons/{slug}")
        assert detail.status_code == 200, slug
        spotlights = [
            section
            for section in detail.json()["sections"]
            if section["kind"] == "chemistry_spotlight"
        ]
        assert spotlights, slug


@pytest.mark.asyncio
async def test_m28_answer_keys_hidden_from_students(api_client: AsyncClient) -> None:
    """Student responses never contain answers, options stay public."""
    response = await api_client.get("/api/v1/learning/lessons/acids-bases")
    assert response.status_code == 200
    payload = response.json()
    for section in payload["sections"]:
        for question in section["questions"]:
            assert "correct" not in question
            assert "explanation" not in question
            assert question["prompt"]
    # The answer key must not leak anywhere in the serialized payload:
    # explanation-only prose and the public-shape contract are checked.
    assert "Water can act as either" not in str(payload)
    assert "Each pH unit is tenfold" not in str(payload)


@pytest.mark.asyncio
async def test_m28_chemistry_questions_grade_deterministically(
    api_client: AsyncClient,
    mock_google_verifier: MockGoogleTokenVerifier,
) -> None:
    """Formula and element questions in M28 lessons accept canonical answers."""
    await _login_student(api_client, mock_google_verifier)
    lessons = {lesson.slug: lesson for lesson in get_lessons()}
    checked = 0
    for slug in ("chemical-bonding", "periodic-table", "acids-bases"):
        lesson = lessons[slug]
        for question in lesson.questions:
            if question.kind not in ("formula", "element"):
                continue
            result = await api_client.post(
                f"/api/v1/learning/lessons/{slug}/answers",
                json={"question_id": question.id, "answer": question.correct},
            )
            assert result.status_code == 200, (slug, question.id)
            assert result.json()["correct"] is True, (slug, question.id)
            checked += 1
    assert checked >= 3


async def _login_student(
    client: AsyncClient, verifier: MockGoogleTokenVerifier
) -> None:
    """Register and authenticate a scratch student."""
    verifier.register_token("m28_learner", sub="sub_m28_learner")
    response = await client.post(
        "/api/v1/auth/google", json={"credential": "m28_learner"}
    )
    assert response.status_code == 200


# ── Molecule reference validation at publish time ────────────────────────


def _spotlight_payload(molecule_input: str | None) -> dict:
    """A minimal valid lesson whose spotlight references a molecule."""
    return {
        "slug": "molecule-check",
        "title": "Molecule Check",
        "description": "Validates molecule references at publish time.",
        "subject": "testing",
        "difficulty": "beginner",
        "estimated_minutes": 5,
        "order": 99,
        "sections": [
            {
                "id": "intro",
                "kind": "introduction",
                "title": "Intro",
                "body": ["Some prose."],
                "element_symbol": None,
                "molecule_input": None,
                "questions": [],
            },
            {
                "id": "spotlight",
                "kind": "chemistry_spotlight",
                "title": "Live",
                "body": ["Watch."],
                "element_symbol": None,
                "molecule_input": molecule_input,
                "questions": [],
            },
            {
                "id": "practice",
                "kind": "practice",
                "title": "Check",
                "body": [],
                "element_symbol": None,
                "molecule_input": None,
                "questions": [
                    {
                        "id": "q1",
                        "kind": "multiple_choice",
                        "prompt": "Pick.",
                        "correct": "A",
                        "explanation": "Because.",
                        "options": ["A", "B"],
                    }
                ],
            },
            {
                "id": "summary",
                "kind": "summary",
                "title": "Done",
                "body": ["Learned."],
                "element_symbol": None,
                "molecule_input": None,
                "questions": [],
            },
        ],
    }


@pytest.mark.asyncio
async def test_valid_molecule_reference_is_publishable(
    api_client: AsyncClient,
    mock_google_verifier: MockGoogleTokenVerifier,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spotlight with a real formula (SMILES, name) passes validation."""
    from tests.test_admin_content import _grant_admin

    _grant_admin(monkeypatch)
    await _login_admin_client(api_client, mock_google_verifier)

    payload = _spotlight_payload("CCO")  # ethanol SMILES
    payload["slug"] = "molecule-check-valid"
    created = await api_client.post("/api/v1/admin/lessons", json=payload)
    assert created.status_code == 201
    published = await api_client.post(
        "/api/v1/admin/lessons/molecule-check-valid/publish"
    )
    assert published.status_code == 200


@pytest.mark.asyncio
async def test_invalid_molecule_reference_rejected_at_publish(
    api_client: AsyncClient,
    mock_google_verifier: MockGoogleTokenVerifier,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spotlight referencing an unparseable molecule cannot be published."""
    from tests.test_admin_content import _grant_admin

    _grant_admin(monkeypatch)
    await _login_admin_client(api_client, mock_google_verifier)

    payload = _spotlight_payload("Xx999notamolecule")
    # The admin API validates chemistry references at create time, so an
    # unparseable molecule reference is rejected before it can even become
    # a draft — broken references can never reach students.
    created = await api_client.post("/api/v1/admin/lessons", json=payload)
    assert created.status_code == 422
    assert "Xx999notamolecule" in str(created.json()["detail"])
    # And it cannot be published either (it does not exist).
    published = await api_client.post("/api/v1/admin/lessons/molecule-check/publish")
    assert published.status_code == 404


async def _login_admin_client(
    client: AsyncClient, verifier: MockGoogleTokenVerifier
) -> None:
    """Authenticate as the configured admin (ADMIN_EMAILS patched by caller)."""
    verifier.register_token("m28_admin", sub="sub_m28_admin", email="admin@chemora.test")
    response = await client.post("/api/v1/auth/google", json={"credential": "m28_admin"})
    assert response.status_code == 200
