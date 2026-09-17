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
