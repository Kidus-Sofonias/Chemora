"""Tests for the Learning Core API (M24).

Covers the lesson catalog/detail, server-side deterministic answer validation,
and authenticated progress tracking with resume behaviour. All content comes
from the real backend content layer; no chemistry is computed here - lessons
reference live ChemEngine element data via the existing elements API.

Uses the shared ``api_client`` fixture (in-memory SQLite + mock Google
verifier) so progress persistence and authentication are exercised for real.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .conftest import MockGoogleTokenVerifier


async def _login(
    client: AsyncClient, verifier: MockGoogleTokenVerifier
) -> None:
    """Register a token and authenticate the client (cookie stored by httpx)."""
    verifier.register_token("learn_token", sub="sub_learner")
    response = await client.post(
        "/api/v1/auth/google", json={"credential": "learn_token"}
    )
    assert response.status_code == 200


# -- Catalog & lesson retrieval (public content) ---------------------------


@pytest.mark.asyncio
async def test_lesson_catalog(api_client: AsyncClient) -> None:
    """The catalog lists the seeded lessons in order with counts."""
    response = await api_client.get("/api/v1/learning/lessons")
    assert response.status_code == 200
    lessons = response.json()["lessons"]
    assert [lesson["slug"] for lesson in lessons] == [
        "electron-configuration",
        "valence-electrons",
        "configuration-and-behavior",
        "chemical-formulas",
        "molecules-and-properties",
        # M28 curriculum expansion.
        "periodic-table",
        "periodic-trends",
        "chemical-bonding",
        "molar-mass",
        "stoichiometry",
        "acids-bases",
    ]
    first = lessons[0]
    assert set(first.keys()) == {
        "id",
        "slug",
        "title",
        "description",
        "subject",
        "difficulty",
        "estimated_minutes",
        "section_count",
        "question_count",
    }
    assert first["section_count"] == 5
    assert first["question_count"] == 2


@pytest.mark.asyncio
async def test_lesson_detail_sections(api_client: AsyncClient) -> None:
    """Lesson detail returns ordered sections incl. a chemistry spotlight."""
    response = await api_client.get("/api/v1/learning/lessons/electron-configuration")
    assert response.status_code == 200
    lesson = response.json()
    assert lesson["slug"] == "electron-configuration"
    kinds = [s["kind"] for s in lesson["sections"]]
    assert kinds == [
        "introduction",
        "explanation",
        "chemistry_spotlight",
        "practice",
        "summary",
    ]
    spotlight = lesson["sections"][2]
    assert spotlight["element_symbol"] == "O"
    assert spotlight["body"]


@pytest.mark.asyncio
async def test_lesson_detail_hides_answer_keys(api_client: AsyncClient) -> None:
    """Questions are exposed without correct answers or explanations."""
    response = await api_client.get("/api/v1/learning/lessons/electron-configuration")
    for section in response.json()["sections"]:
        for question in section["questions"]:
            assert set(question.keys()) == {"id", "kind", "prompt", "options"}
            assert "correct" not in question
    practice = response.json()["sections"][3]
    mc = next(q for q in practice["questions"] if q["kind"] == "multiple_choice")
    assert len(mc["options"]) == 3


@pytest.mark.asyncio
async def test_unknown_lesson_404(api_client: AsyncClient) -> None:
    """An unknown slug yields a structured 404."""
    response = await api_client.get("/api/v1/learning/lessons/no-such-lesson")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "lesson_not_found"


# -- Authentication requirements -------------------------------------------


@pytest.mark.asyncio
async def test_progress_requires_authentication(api_client: AsyncClient) -> None:
    """Progress endpoints are authenticated; anonymous access gets 401."""
    response = await api_client.get("/api/v1/learning/lessons/electron-configuration/progress")
    assert response.status_code == 401
    submit = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/answers",
        json={"question_id": "ec-1", "answer": "6"},
    )
    assert submit.status_code == 401
    complete = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/sections/intro/complete"
    )
    assert complete.status_code == 401


# -- Progress: creation, update, completion, resume ------------------------


@pytest.mark.asyncio
async def test_progress_starts_empty(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """First access creates an empty progress row (resume from zero)."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.get(
        "/api/v1/learning/lessons/electron-configuration/progress"
    )
    assert response.status_code == 200
    progress = response.json()
    assert progress == {
        "lesson_slug": "electron-configuration",
        "completed_sections": [],
        "answers": {},
        "progress_percent": 0,
        "completed": False,
    }


@pytest.mark.asyncio
async def test_complete_section_updates_progress(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Completing one of five sections moves progress to 20%."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/sections/intro/complete"
    )
    assert response.status_code == 200
    progress = response.json()
    assert progress["completed_sections"] == ["intro"]
    assert progress["progress_percent"] == 20
    assert progress["completed"] is False


@pytest.mark.asyncio
async def test_complete_all_sections_completes_lesson(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Completing every section auto-completes the lesson at 100%."""
    await _login(api_client, mock_google_verifier)
    slug = "electron-configuration"
    for section_id in ("intro", "explain", "spotlight", "practice", "summary"):
        response = await api_client.post(
            f"/api/v1/learning/lessons/{slug}/sections/{section_id}/complete"
        )
        assert response.status_code == 200
    final = response.json()
    assert final["progress_percent"] == 100
    assert final["completed"] is True


@pytest.mark.asyncio
async def test_progress_resumes_after_leaving(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Progress persists: returning user sees previously completed sections."""
    await _login(api_client, mock_google_verifier)
    slug = "electron-configuration"
    await api_client.post(f"/api/v1/learning/lessons/{slug}/sections/intro/complete")
    await api_client.post(f"/api/v1/learning/lessons/{slug}/sections/explain/complete")
    # A fresh request round-trip (new session) still sees the saved state.
    response = await api_client.get(f"/api/v1/learning/lessons/{slug}/progress")
    progress = response.json()
    assert progress["completed_sections"] == ["intro", "explain"]
    assert progress["progress_percent"] == 40


@pytest.mark.asyncio
async def test_complete_unknown_section_404(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """An unknown section id yields a structured 404."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/sections/nope/complete"
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "section_not_found"


# -- Answer validation ------------------------------------------------------


@pytest.mark.asyncio
async def test_correct_answer_is_validated_server_side(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """A correct answer returns correct=True with the explanation."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/answers",
        json={"question_id": "ec-1", "answer": "6"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["question_id"] == "ec-1"
    assert result["correct"] is True
    assert "6 electrons" in result["explanation"]
    assert result["progress"]["answers"] == {"ec-1": True}
    # The answer key itself is never echoed back.
    assert "correct_answer" not in result


@pytest.mark.asyncio
async def test_incorrect_answer_returns_feedback_not_answer(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """An incorrect answer is marked wrong; the key is not revealed."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/answers",
        json={"question_id": "ec-1", "answer": "4"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["correct"] is False
    assert result["progress"]["answers"] == {"ec-1": False}


@pytest.mark.asyncio
async def test_answer_matching_is_normalized(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Validation is deterministic: case and surrounding whitespace ignored."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/answers",
        json={"question_id": "ec-2", "answer": "  hund's RULE  "},
    )
    assert response.status_code == 200
    assert response.json()["correct"] is True


@pytest.mark.asyncio
async def test_answer_outcome_persists_in_progress(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Recorded answers show up when the user later fetches progress."""
    await _login(api_client, mock_google_verifier)
    slug = "electron-configuration"
    await api_client.post(
        f"/api/v1/learning/lessons/{slug}/answers",
        json={"question_id": "ec-1", "answer": "6"},
    )
    progress = (
        await api_client.get(f"/api/v1/learning/lessons/{slug}/progress")
    ).json()
    assert progress["answers"] == {"ec-1": True}


@pytest.mark.asyncio
async def test_unknown_question_404(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """A question from another lesson is rejected with a structured 404."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/answers",
        json={"question_id": "ve-1", "answer": "6"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "question_not_found"


@pytest.mark.asyncio
async def test_blank_answer_rejected(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Empty/whitespace answers are rejected by request validation."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/answers",
        json={"question_id": "ec-1", "answer": "   "},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_progress_unknown_lesson_404(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Progress for an unknown lesson yields a structured 404."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.get("/api/v1/learning/lessons/no-such-lesson/progress")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "lesson_not_found"
# -- Expanded content and richer practice (M25) -----------------------------
#
# M25 adds two lessons and two ChemEngine-backed question kinds. Grading for
# `formula` and `element` delegates to the engine (canonical formula / element
# resolution), so equivalent notation is accepted while chemically different
# answers are rejected — never silently accepted.


@pytest.mark.asyncio
async def test_catalog_reports_expanded_lesson_counts(api_client: AsyncClient) -> None:
    """The two M25 lessons appear with their real section/question counts."""
    response = await api_client.get("/api/v1/learning/lessons")
    lessons = {lesson["slug"]: lesson for lesson in response.json()["lessons"]}
    assert lessons["chemical-formulas"]["question_count"] == 2
    assert lessons["chemical-formulas"]["section_count"] == 5
    assert lessons["molecules-and-properties"]["question_count"] == 2
    assert lessons["molecules-and-properties"]["subject"] == "molecular properties"


@pytest.mark.asyncio
async def test_molecule_spotlight_exposes_input_for_live_analysis(
    api_client: AsyncClient,
) -> None:
    """A molecule spotlight names its input; the client computes it live."""
    response = await api_client.get("/api/v1/learning/lessons/chemical-formulas")
    assert response.status_code == 200
    spotlight = next(
        section
        for section in response.json()["sections"]
        if section["kind"] == "chemistry_spotlight"
    )
    assert spotlight["molecule_input"] == "H2O"
    assert spotlight["element_symbol"] is None


@pytest.mark.asyncio
async def test_element_spotlight_leaves_molecule_input_unset(
    api_client: AsyncClient,
) -> None:
    """Element spotlights carry an element symbol and no molecule input."""
    response = await api_client.get("/api/v1/learning/lessons/electron-configuration")
    spotlight = next(
        section
        for section in response.json()["sections"]
        if section["kind"] == "chemistry_spotlight"
    )
    assert spotlight["element_symbol"] == "O"
    assert spotlight["molecule_input"] is None


@pytest.mark.asyncio
async def test_expanded_lessons_hide_answer_keys(api_client: AsyncClient) -> None:
    """New lessons never serialize correct answers or explanations."""
    for slug in ("chemical-formulas", "molecules-and-properties"):
        response = await api_client.get(f"/api/v1/learning/lessons/{slug}")
        assert response.status_code == 200
        for section in response.json()["sections"]:
            for question in section["questions"]:
                assert set(question.keys()) == {"id", "kind", "prompt", "options"}


@pytest.mark.asyncio
async def test_formula_answers_are_canonicalized_by_the_engine(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Equivalent formula spellings grade identically (ChemEngine canonical)."""
    await _login(api_client, mock_google_verifier)
    for answer in ("H2O", "HOH"):
        response = await api_client.post(
            "/api/v1/learning/lessons/chemical-formulas/answers",
            json={"question_id": "fm-1", "answer": answer},
        )
        assert response.status_code == 200, answer
        assert response.json()["correct"] is True, answer


@pytest.mark.asyncio
async def test_chemically_different_formula_is_incorrect(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """A different composition is rejected rather than normalized away."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/chemical-formulas/answers",
        json={"question_id": "fm-1", "answer": "CO2"},
    )
    assert response.status_code == 200
    assert response.json()["correct"] is False


@pytest.mark.asyncio
async def test_unparseable_formula_is_invalid_answer(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Non-formula text is a client-safe 422, never silently graded."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/chemical-formulas/answers",
        json={"question_id": "fm-1", "answer": "banana"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_answer"
@pytest.mark.asyncio
async def test_element_answers_accept_symbol_name_and_atomic_number(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Symbol, case-insensitive name, and atomic number all resolve."""
    await _login(api_client, mock_google_verifier)
    for answer in ("Na", "sodium", "SODIUM", "11"):
        response = await api_client.post(
            "/api/v1/learning/lessons/molecules-and-properties/answers",
            json={"question_id": "mp-1", "answer": answer},
        )
        assert response.status_code == 200, answer
        assert response.json()["correct"] is True, answer


@pytest.mark.asyncio
async def test_real_but_different_element_is_incorrect(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """A valid element that is not the expected one is simply wrong."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/molecules-and-properties/answers",
        json={"question_id": "mp-1", "answer": "Mg"},
    )
    assert response.status_code == 200
    assert response.json()["correct"] is False


@pytest.mark.asyncio
async def test_non_element_answer_is_invalid(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """A token that is not an element is invalid, not graded as wrong."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.post(
        "/api/v1/learning/lessons/molecules-and-properties/answers",
        json={"question_id": "mp-1", "answer": "unobtainium"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_answer"


@pytest.mark.asyncio
async def test_every_chemistry_question_accepts_its_expected_answer(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Every seeded formula/element question is objectively answerable.

    Submitting the canonical expected answer must be graded correct. This
    guards against a misconfigured question that could never be answered —
    the failure mode a broken canonicalization would otherwise hide.
    """
    from app.learning.content import get_lessons

    await _login(api_client, mock_google_verifier)
    checked = 0
    for lesson in get_lessons():
        for question in lesson.questions:
            if question.kind not in ("formula", "element"):
                continue
            response = await api_client.post(
                f"/api/v1/learning/lessons/{lesson.slug}/answers",
                json={"question_id": question.id, "answer": question.correct},
            )
            assert response.status_code == 200, question.id
            assert response.json()["correct"] is True, question.id
            checked += 1
    assert checked >= 2


# -- M28: catalog progress for resume -------------------------------------


@pytest.mark.asyncio
async def test_progress_list_starts_empty(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """A user who has not started anything gets an empty progress list."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.get("/api/v1/learning/progress")
    assert response.status_code == 200
    assert response.json() == {"progress": []}


@pytest.mark.asyncio
async def test_progress_list_requires_authentication(api_client: AsyncClient) -> None:
    """The catalog progress endpoint requires authentication."""
    response = await api_client.get("/api/v1/learning/progress")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_progress_list_reports_started_lessons(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Lessons the user started appear with derived percentages."""
    await _login(api_client, mock_google_verifier)
    await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/sections/intro/complete"
    )
    response = await api_client.get("/api/v1/learning/progress")
    assert response.status_code == 200
    rows = response.json()["progress"]
    by_slug = {row["lesson_slug"]: row for row in rows}
    assert by_slug["electron-configuration"]["progress_percent"] == 20
    assert by_slug["electron-configuration"]["completed"] is False


@pytest.mark.asyncio
async def test_progress_list_hides_unpublished_lessons(
    api_client: AsyncClient,
    mock_google_verifier: MockGoogleTokenVerifier,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Progress rows pointing at unpublished lessons are omitted.

    A student completes a lesson, the lesson is later unpublished, and the
    catalog progress must stop advertising it — drafts stay invisible.
    """
    from tests.test_admin_content import (  # noqa: PLC0415
        ADMIN_EMAIL,
        _grant_admin,
        _lesson_payload,
    )

    slug = "progress-hidden-lesson"
    payload = _lesson_payload(slug=slug, order=99)
    payload["sections"] = payload["sections"][:1]  # single-section lesson

    # Admin creates and publishes a scratch lesson.
    _grant_admin(monkeypatch)
    mock_google_verifier.register_token(
        "m28_admin_token", sub="sub_m28_admin", email=ADMIN_EMAIL
    )
    await api_client.post("/api/v1/auth/google", json={"credential": "m28_admin_token"})
    created = await api_client.post("/api/v1/admin/lessons", json=payload)
    assert created.status_code == 201
    published = await api_client.post(f"/api/v1/admin/lessons/{slug}/publish")
    assert published.status_code == 200

    # A student completes the lesson's only section.
    mock_google_verifier.register_token(
        "m28_student_token", sub="sub_m28_student", email="student@chemora.test"
    )
    await api_client.post("/api/v1/auth/google", json={"credential": "m28_student_token"})
    complete = await api_client.post(
        f"/api/v1/learning/lessons/{slug}/sections/intro/complete"
    )
    assert complete.status_code == 200
    rows = (await api_client.get("/api/v1/learning/progress")).json()["progress"]
    assert any(row["lesson_slug"] == slug for row in rows)

    # Admin unpublishes the lesson.
    await api_client.post("/api/v1/auth/google", json={"credential": "m28_admin_token"})
    unpublished = await api_client.post(f"/api/v1/admin/lessons/{slug}/unpublish")
    assert unpublished.status_code == 200

    # The student's catalog progress no longer lists the unpublished lesson.
    await api_client.post("/api/v1/auth/google", json={"credential": "m28_student_token"})
    rows = (await api_client.get("/api/v1/learning/progress")).json()["progress"]
    assert not any(row["lesson_slug"] == slug for row in rows)
