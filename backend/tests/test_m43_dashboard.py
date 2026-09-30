"""Tests for the M43 student dashboard endpoint.

Covers the read-only dashboard view composed from the existing catalog and
progress data (no new progress models): the empty/new-user state, the
deterministic next-lesson recommendation, continue-learning ordering, progress
by topic, and the practice/results summary. Also exercises the pure
``recommend_next_lesson`` rule directly for tie-break / all-complete cases.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.learning.content import get_lessons
from app.models.learning import LessonProgress
from app.services.learning import recommend_next_lesson

from .conftest import MockGoogleTokenVerifier

DASHBOARD_URL = "/api/v1/learning/dashboard"


async def _login(client: AsyncClient, verifier: MockGoogleTokenVerifier) -> None:
    """Register a token and authenticate the client (cookie stored by httpx)."""
    verifier.register_token("learn_token", sub="sub_learner")
    response = await client.post("/api/v1/auth/google", json={"credential": "learn_token"})
    assert response.status_code == 200


async def _complete_section(client: AsyncClient, slug: str, section_id: str) -> None:
    """Complete one section of a lesson as the authenticated learner."""
    response = await client.post(
        f"/api/v1/learning/lessons/{slug}/sections/{section_id}/complete"
    )
    assert response.status_code == 200


async def _catalog_slugs(client: AsyncClient) -> list[str]:
    """Return the published catalog's lesson slugs in order from the API."""
    catalog = (await client.get("/api/v1/learning/lessons")).json()
    return [lesson["slug"] for lesson in catalog["lessons"]]


@pytest.mark.asyncio
async def test_dashboard_requires_authentication(api_client: AsyncClient) -> None:
    """The dashboard shares the learning endpoints' authentication requirement."""
    response = await api_client.get(DASHBOARD_URL)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_empty_for_new_user(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """A user who has never started anything gets an empty dashboard + a first lesson."""
    await _login(api_client, mock_google_verifier)
    response = await api_client.get(DASHBOARD_URL)
    assert response.status_code == 200
    data = response.json()

    assert data["sections"] == []
    assert data["totals"] == {"started": 0, "in_progress": 0, "completed": 0, "needs_review": 0}
    catalog = await _catalog_slugs(api_client)
    assert data["recommended_slug"] == catalog[0]
    assert "next lesson" in data["recommended_reason"].lower()
    assert len(data["topics"]) == len({t["subject"] for t in data["topics"]})
    assert all(t["progress_percent"] == 0 for t in data["topics"])
    assert all(t["completed"] == 0 for t in data["topics"])
    assert all(t["lesson_count"] >= 1 for t in data["topics"])


@pytest.mark.asyncio
async def test_dashboard_recommends_in_progress_lesson(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """A started-but-incomplete lesson is the recommended resume target."""
    await _login(api_client, mock_google_verifier)
    detail = (await api_client.get("/api/v1/learning/lessons/electron-configuration")).json()
    await _complete_section(api_client, "electron-configuration", detail["sections"][0]["id"])
    data = (await api_client.get(DASHBOARD_URL)).json()
    assert data["recommended_slug"] == "electron-configuration"
    assert data["recommended_reason"] == "Continue where you left off."
    section = next(s for s in data["sections"] if s["lesson_slug"] == "electron-configuration")
    assert section["completed"] is False
    assert section["progress_percent"] == 20
    assert section["questions_attempted"] == 0
    assert section["needs_review"] is False
    completed = {detail["sections"][0]["id"]}
    assert section["resume_section_id"] not in completed
    assert section["resume_section_id"] in {s["id"] for s in detail["sections"]}
    assert section["last_accessed_at"] is not None


@pytest.mark.asyncio
async def test_dashboard_recommends_next_unstarted_after_completion(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Finishing the first lesson advances the recommendation to the next one."""
    await _login(api_client, mock_google_verifier)
    catalog = await _catalog_slugs(api_client)
    detail = (await api_client.get("/api/v1/learning/lessons/electron-configuration")).json()
    for section in detail["sections"]:
        await _complete_section(api_client, "electron-configuration", section["id"])
    data = (await api_client.get(DASHBOARD_URL)).json()
    ec = next(s for s in data["sections"] if s["lesson_slug"] == "electron-configuration")
    assert ec["completed"] is True
    assert ec["progress_percent"] == 100
    assert data["recommended_slug"] == catalog[1]
    assert "next lesson" in data["recommended_reason"].lower()


@pytest.mark.asyncio
async def test_dashboard_practice_summary_and_needs_review(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Server-graded answers surface as an aggregated practice summary."""
    await _login(api_client, mock_google_verifier)
    detail = (await api_client.get("/api/v1/learning/lessons/electron-configuration")).json()
    question = next(
        q
        for q in (
            question
            for section in detail["sections"]
            for question in section["questions"]
        )
        if q["kind"] == "numeric"
    )
    wrong = await api_client.post(
        "/api/v1/learning/lessons/electron-configuration/answers",
        json={"question_id": question["id"], "answer": "7"},
    )
    assert wrong.status_code == 200
    assert wrong.json()["correct"] is False
    data = (await api_client.get(DASHBOARD_URL)).json()
    ec = next(s for s in data["sections"] if s["lesson_slug"] == "electron-configuration")
    assert ec["questions_attempted"] == 1
    assert ec["questions_correct"] == 0
    assert ec["needs_review"] is True
    assert data["totals"]["needs_review"] == 1


@pytest.mark.asyncio
async def test_dashboard_progress_by_topic(
    api_client: AsyncClient, mock_google_verifier: MockGoogleTokenVerifier
) -> None:
    """Topic progress reflects the sections the learner completed in that subject."""
    await _login(api_client, mock_google_verifier)
    detail = (await api_client.get("/api/v1/learning/lessons/electron-configuration")).json()
    await _complete_section(api_client, "electron-configuration", detail["sections"][0]["id"])
    data = (await api_client.get(DASHBOARD_URL)).json()
    topic = next(t for t in data["topics"] if t["subject"] == detail["subject"])
    assert topic["lesson_count"] >= 1
    assert 0 < topic["progress_percent"] <= 100
    assert topic["completed"] == 0


# -- Pure: deterministic recommendation rule ------------------------------


def test_recommend_resumes_in_progress_with_most_progress() -> None:
    """The in-progress lesson with the highest completion is the resume target."""
    lessons = list(get_lessons())
    ec = next(lesson for lesson in lessons if lesson.slug == "electron-configuration")
    ve = next(lesson for lesson in lessons if lesson.slug == "valence-electrons")
    rows = {
        "electron-configuration": _make_progress(
            "electron-configuration",
            [section.id for section in ec.sections[:-1]],
            updated_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        ),
        "valence-electrons": _make_progress(
            "valence-electrons",
            [ve.sections[0].id],
            updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    }
    slug, reason = recommend_next_lesson(lessons, rows)
    assert slug == "electron-configuration"
    assert reason == "Continue where you left off."


def test_recommend_tie_break_prefers_most_recent_activity() -> None:
    """Equal completion breaks the tie toward the most recently active lesson."""
    lessons = list(get_lessons())
    rows = {
        "electron-configuration": _make_progress(
            "electron-configuration", [], updated_at=datetime(2026, 1, 3, tzinfo=timezone.utc)
        ),
        "valence-electrons": _make_progress(
            "valence-electrons", [], updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc)
        ),
    }
    slug, reason = recommend_next_lesson(lessons, rows)
    assert slug == "valence-electrons"
    assert reason == "Continue where you left off."


def test_recommend_none_when_all_completed() -> None:
    """With every catalog lesson completed, there is nothing left to recommend."""
    lessons = list(get_lessons())
    rows = {
        lesson.slug: _make_progress(
            lesson.slug,
            [section.id for section in lesson.sections],
            completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        for lesson in lessons
    }
    slug, reason = recommend_next_lesson(lessons, rows)
    assert slug is None
    assert "every lesson" in reason.lower()


def test_recommend_next_unstarted_after_resume_lesson_completed() -> None:
    """A completed resume lesson yields the next unstarted lesson by order."""
    lessons = list(get_lessons())
    ec = next(lesson for lesson in lessons if lesson.slug == "electron-configuration")
    rows = {
        "electron-configuration": _make_progress(
            "electron-configuration",
            [section.id for section in ec.sections],
            completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    }
    slug, reason = recommend_next_lesson(lessons, rows)
    assert slug == "valence-electrons"
    assert "next lesson" in reason.lower()


def _make_progress(
    slug: str,
    section_ids: list[str],
    completed_at: datetime | None = None,
    answers: dict[str, bool] | None = None,
    updated_at: datetime | None = None,
) -> LessonProgress:
    """Build a transient, in-memory progress row for rule unit tests."""
    row = LessonProgress(
        user_id=uuid.uuid4(),
        lesson_slug=slug,
        completed_sections=list(section_ids),
        answers=dict(answers or {}),
    )
    row.completed_at = completed_at
    row.updated_at = updated_at or datetime(2026, 1, 2, tzinfo=timezone.utc)
    return row
