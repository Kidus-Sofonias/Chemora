"""Tests for the admin content-management API (M26).

Covers authorization (unauthenticated -> 401, normal user -> 403, admin -> 200),
the create/publish surface, content validation on publish, duplicate-slug
protection, slug immutability, answer-key exposure, and publication visibility:
drafts must be invisible to students.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .conftest import MockGoogleTokenVerifier

ADMIN_EMAIL = "admin@chemora.test"
USER_EMAIL = "user@chemora.test"


def _lesson_payload(
    slug: str = "new-lesson",
    order: int = 6,
    question: dict | None = None,
    element_symbol: str | None = "O",
) -> dict:
    """Build a structurally valid lesson payload for admin tests."""
    question = question or {
        "id": "q1",
        "kind": "multiple_choice",
        "prompt": "Which element has atomic number 8?",
        "correct": "O",
        "explanation": "Oxygen is element 8.",
        "options": ["O", "N"],
    }
    return {
        "slug": slug,
        "title": "New Lesson",
        "description": "A lesson used by the admin tests.",
        "subject": "testing",
        "difficulty": "beginner",
        "estimated_minutes": 5,
        "order": order,
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
                "title": "Live data",
                "body": ["Watch the engine compute."],
                "element_symbol": element_symbol,
                "molecule_input": None,
                "questions": [],
            },
            {
                "id": "practice",
                "kind": "practice",
                "title": "Check yourself",
                "body": [],
                "element_symbol": None,
                "molecule_input": None,
                "questions": [question],
            },
            {
                "id": "summary",
                "kind": "summary",
                "title": "Takeaways",
                "body": ["You learned something."],
                "element_symbol": None,
                "molecule_input": None,
                "questions": [],
            },
        ],
    }


async def _login(
    client: AsyncClient,
    verifier: MockGoogleTokenVerifier,
    email: str,
    token: str,
) -> None:
    """Authenticate as a user with the given verified email."""
    verifier.register_token(token, sub=f"sub_{token}", email=email)
    response = await client.post("/api/v1/auth/google", json={"credential": token})
    assert response.status_code == 200


async def _login_admin(
    client: AsyncClient, verifier: MockGoogleTokenVerifier
) -> None:
    """Authenticate as a configured admin."""
    await _login(client, verifier, ADMIN_EMAIL, "admin_token")


def _grant_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow ADMIN_EMAIL to be provisioned as an admin for this test."""
    monkeypatch.setattr("app.core.config.settings.ADMIN_EMAILS", [ADMIN_EMAIL])


# -------------------------------------------------------------------
# Authorization
# -------------------------------------------------------------------


class TestAuthorization:
    """Unauthenticated -> 401; normal user -> 403; admin -> 200."""

    async def test_unauthenticated_list_returns_401(
        self, api_client: AsyncClient
    ) -> None:
        response = await api_client.get("/api/v1/admin/lessons")
        assert response.status_code == 401

    async def test_unauthenticated_get_returns_401(
        self, api_client: AsyncClient
    ) -> None:
        response = await api_client.get(
            "/api/v1/admin/lessons/electron-configuration"
        )
        assert response.status_code == 401

    async def test_normal_user_list_returns_403(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        await _login(api_client, mock_google_verifier, USER_EMAIL, "user_token")
        response = await api_client.get("/api/v1/admin/lessons")
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "forbidden"

    async def test_normal_user_get_returns_403(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        await _login(api_client, mock_google_verifier, USER_EMAIL, "user_token")
        response = await api_client.get(
            "/api/v1/admin/lessons/electron-configuration"
        )
        assert response.status_code == 403

    async def test_normal_user_create_returns_403(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        await _login(api_client, mock_google_verifier, USER_EMAIL, "user_token")
        response = await api_client.post(
            "/api/v1/admin/lessons", json=_lesson_payload()
        )
        assert response.status_code == 403

    async def test_normal_user_publish_returns_403(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        await _login(api_client, mock_google_verifier, USER_EMAIL, "user_token")
        response = await api_client.post(
            "/api/v1/admin/lessons/electron-configuration/publish"
        )
        assert response.status_code == 403

    async def test_admin_list_returns_200(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.get("/api/v1/admin/lessons")
        assert response.status_code == 200
        assert "lessons" in response.json()


# -------------------------------------------------------------------
# List Lessons (Admin)
# -------------------------------------------------------------------


class TestAdminListLessons:
    """Admin catalog includes drafts, section counts, question counts."""

    async def test_admin_list_includes_all_seeded_lessons(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.get("/api/v1/admin/lessons")
        assert response.status_code == 200
        slugs = [l["slug"] for l in response.json()["lessons"]]
        assert "electron-configuration" in slugs
        assert "valence-electrons" in slugs
        assert "chemical-formulas" in slugs

    async def test_admin_summary_includes_published_flag(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.get("/api/v1/admin/lessons")
        for lesson in response.json()["lessons"]:
            assert "published" in lesson
            assert "section_count" in lesson
            assert "question_count" in lesson


# -------------------------------------------------------------------
# Get Single Lesson (Admin)
# -------------------------------------------------------------------


class TestAdminGetLesson:
    """Admin can see drafts and answer keys."""

    async def test_admin_get_includes_answer_keys(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.get(
            "/api/v1/admin/lessons/electron-configuration"
        )
        assert response.status_code == 200
        data = response.json()
        practice = [s for s in data["sections"] if s["kind"] == "practice"][0]
        for q in practice["questions"]:
            assert "correct" in q
            assert "explanation" in q

    async def test_admin_get_includes_sections_ordering(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.get(
            "/api/v1/admin/lessons/electron-configuration"
        )
        assert response.status_code == 200
        data = response.json()
        assert "published" in data
        assert "sections" in data
        assert len(data["sections"]) > 0

    async def test_admin_get_nonexistent_lesson_returns_404(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.get("/api/v1/admin/lessons/nonexistent-slug")
        assert response.status_code == 404


# -------------------------------------------------------------------
# Create Lesson
# -------------------------------------------------------------------


class TestAdminCreateLesson:
    """Creating a lesson saves it as an unpublished draft."""

    async def test_create_lesson_returns_201(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload()
        response = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "new-lesson"
        assert data["published"] is False

    async def test_created_lesson_appears_in_admin_catalog(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="catalog-test", order=99)
        await api_client.post("/api/v1/admin/lessons", json=payload)
        response = await api_client.get("/api/v1/admin/lessons")
        slugs = [l["slug"] for l in response.json()["lessons"]]
        assert "catalog-test" in slugs

    async def test_created_lesson_invisible_to_student_api(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="draft-only", order=100)
        await api_client.post("/api/v1/admin/lessons", json=payload)
        response = await api_client.get("/api/v1/learning/lessons")
        slugs = [l["slug"] for l in response.json()["lessons"]]
        assert "draft-only" not in slugs

    async def test_duplicate_slug_returns_409(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="dup-slug")
        r1 = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert r1.status_code == 201
        r2 = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert r2.status_code == 409
        assert r2.json()["detail"]["code"] == "duplicate_slug"

    async def test_invalid_slug_format_returns_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="INVALID_SLUG!")
        response = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert response.status_code == 422


# -------------------------------------------------------------------
# Update Lesson
# -------------------------------------------------------------------


class TestAdminUpdateLesson:
    """Updating replaces content but preserves publish state and slug."""

    async def test_update_preserves_published_state(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="update-test")
        await api_client.post("/api/v1/admin/lessons", json=payload)
        await api_client.post("/api/v1/admin/lessons/update-test/publish")
        updated = _lesson_payload(slug="update-test")
        updated["title"] = "Updated Title"
        response = await api_client.put(
            "/api/v1/admin/lessons/update-test", json=updated
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"
        assert response.json()["published"] is True

    async def test_slug_mismatch_returns_400(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="original-slug")
        await api_client.post("/api/v1/admin/lessons", json=payload)
        mismatched = _lesson_payload(slug="different-slug")
        response = await api_client.put(
            "/api/v1/admin/lessons/original-slug", json=mismatched
        )
        assert response.status_code == 400

    async def test_update_nonexistent_lesson_returns_404(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="no-such-lesson")
        response = await api_client.put(
            "/api/v1/admin/lessons/no-such-lesson", json=payload
        )
        assert response.status_code == 404


# -------------------------------------------------------------------
# Publish / Unpublish
# -------------------------------------------------------------------


class TestAdminPublish:
    """Publishing validates content first; unpublish returns to draft."""

    async def test_publish_makes_lesson_visible_to_students(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="publish-test", order=50)
        await api_client.post("/api/v1/admin/lessons", json=payload)
        # Initially invisible
        student_resp = await api_client.get("/api/v1/learning/lessons")
        assert "publish-test" not in [
            l["slug"] for l in student_resp.json()["lessons"]
        ]
        # Publish
        response = await api_client.post(
            "/api/v1/admin/lessons/publish-test/publish"
        )
        assert response.status_code == 200
        assert response.json()["published"] is True
        # Now visible
        student_resp = await api_client.get("/api/v1/learning/lessons")
        assert "publish-test" in [
            l["slug"] for l in student_resp.json()["lessons"]
        ]

    async def test_unpublish_returns_to_draft(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload(slug="unpublish-test", order=51)
        await api_client.post("/api/v1/admin/lessons", json=payload)
        await api_client.post("/api/v1/admin/lessons/unpublish-test/publish")
        response = await api_client.post(
            "/api/v1/admin/lessons/unpublish-test/unpublish"
        )
        assert response.status_code == 200
        assert response.json()["published"] is False
        student_resp = await api_client.get("/api/v1/learning/lessons")
        assert "unpublish-test" not in [
            l["slug"] for l in student_resp.json()["lessons"]
        ]

    async def test_publish_nonexistent_returns_404(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/admin/lessons/nonexistent/publish"
        )
        assert response.status_code == 404

    async def test_unpublish_nonexistent_returns_404(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/admin/lessons/nonexistent/unpublish"
        )
        assert response.status_code == 404


# -------------------------------------------------------------------
# Content Validation
# -------------------------------------------------------------------


class TestContentValidation:
    """Invalid content is rejected at create/publish time."""

    async def test_empty_sections_returns_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload()
        payload["sections"] = []
        response = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert response.status_code == 422

    async def test_invalid_section_kind_returns_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload()
        payload["sections"][0]["kind"] = "nonexistent_kind"
        response = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert response.status_code == 422

    async def test_practice_without_questions_returns_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload()
        for section in payload["sections"]:
            if section["kind"] == "practice":
                section["questions"] = []
        response = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert response.status_code == 422

    async def test_invalid_difficulty_returns_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        payload = _lesson_payload()
        payload["difficulty"] = "impossible"
        response = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert response.status_code == 422

    async def test_multiple_choice_with_one_option_returns_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        bad_question = {
            "id": "q-bad",
            "kind": "multiple_choice",
            "prompt": "Pick one",
            "correct": "A",
            "explanation": "Because.",
            "options": ["A"],
        }
        payload = _lesson_payload(question=bad_question)
        response = await api_client.post("/api/v1/admin/lessons", json=payload)
        assert response.status_code == 422


# -------------------------------------------------------------------
# Answer Key Exposure
# -------------------------------------------------------------------


class TestAnswerKeyExposure:
    """Answer keys appear in admin API but not in student API."""

    async def test_student_lesson_detail_hides_answer_keys(
        self, api_client: AsyncClient
    ) -> None:
        response = await api_client.get(
            "/api/v1/learning/lessons/electron-configuration"
        )
        assert response.status_code == 200
        for section in response.json()["sections"]:
            for q in section.get("questions", []):
                assert "correct" not in q
                assert "explanation" not in q

    async def test_admin_lesson_detail_shows_answer_keys(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _grant_admin(monkeypatch)
        await _login_admin(api_client, mock_google_verifier)
        response = await api_client.get(
            "/api/v1/admin/lessons/electron-configuration"
        )
        assert response.status_code == 200
        has_answer = False
        for section in response.json()["sections"]:
            for q in section.get("questions", []):
                if "correct" in q:
                    has_answer = True
        assert has_answer, "Admin API should expose answer keys"
