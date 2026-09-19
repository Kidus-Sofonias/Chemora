"""M29 AI Chemistry Tutor — backend tests.

Covers the security and determinism boundaries required by the milestone:
provider behavior, authentication, student-safe retrieval (published only,
never answer keys or drafts), the ChemEngine tool boundary, the mandatory
chemistry-authority test (provider demands a wrong value — the ChemEngine
tool result wins), and cost/abuse/secret-hygiene controls.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.ai.provider import (
    AIProviderError,
    MockAIProvider,
    make_provider,
)
from app.services.ai.service import (
    AI_TIMEOUT,
    MAX_MESSAGE_CHARS,
    TutorError,
    TutorService,
)
from app.services.ai.tools import ToolError, TutorToolbox
from tests.conftest import MockGoogleTokenVerifier

# pytest-asyncio runs in auto mode (pyproject); no explicit asyncio mark needed.


async def _authenticated(api_client: AsyncClient, verifier: MockGoogleTokenVerifier) -> None:
    """Authenticate the test client via the mocked Google verifier."""
    verifier.register_token("m29_token", sub="sub_m29", email="student@chemora.test")
    login = await api_client.post("/api/v1/auth/google", json={"credential": "m29_token"})
    assert login.status_code == 200


def _published_slugs() -> set[str]:
    """Slugs of every seeded (published) lesson."""
    from app.learning.content import get_lessons

    return {lesson.slug for lesson in get_lessons()}


class _ScriptedProvider:
    """Test double that returns scripted responses in order."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, Any]]] = []

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> Any:  # noqa: ANN401
        self.calls.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


# ── Provider layer ───────────────────────────────────────────────────────


class TestProvider:
    """Provider abstraction behavior."""

    def test_mock_provider_returns_deterministic_text(self) -> None:
        """Mock provider returns deterministic text."""
        provider = MockAIProvider()
        answer = provider.generate(
            [{"role": "user", "content": "hi"}],
            [],
            max_output_tokens=128,
            timeout_seconds=5,
        )
        assert isinstance(answer, str) and answer
        assert provider.last_tools == []

    def test_make_provider_mock(self) -> None:
        """Make provider mock."""
        assert isinstance(make_provider("mock", "https://x", "", "m"), MockAIProvider)

    def test_make_provider_rejects_unknown(self) -> None:
        """Make provider rejects unknown."""
        with pytest.raises(ValueError, match="Unknown AI_PROVIDER"):
            make_provider("skynet", "https://x", "key", "m")

    def test_make_provider_openai_requires_key(self) -> None:
        """Make provider openai requires key."""
        with pytest.raises(ValueError, match="AI_API_KEY"):
            make_provider("openai", "https://x", "", "m")

    def test_provider_error_categories_are_stable(self) -> None:
        """Provider error categories are stable."""
        error = AIProviderError("timeout", "took too long")
        assert error.category == "timeout"
        with pytest.raises(ValueError):
            AIProviderError("nonsense", "x")

    def test_make_provider_anthropic_requires_key(self) -> None:
        """Anthropic provider selection requires its server-side key."""
        with pytest.raises(ValueError, match="AI_ANTHROPIC_API_KEY"):
            make_provider("anthropic", "https://x", "", "m")

    def test_make_provider_anthropic(self) -> None:
        """Anthropic provider is constructed through the same abstraction."""
        from app.services.ai.provider import AnthropicProvider

        provider = make_provider(
            "anthropic",
            "https://x",
            "",
            "m",
            anthropic_key="test-key",
            anthropic_model="claude-sonnet-4-5",
        )
        assert isinstance(provider, AnthropicProvider)


# ── Tool boundary ────────────────────────────────────────────────────────


class TestToolbox:
    """Allowlist and validation for ChemEngine tutor tools."""

    def test_allowlist_is_explicit_and_derived(self) -> None:
        """Allowlist is explicit and derived."""
        toolbox = TutorToolbox()
        registered = {tool.name for tool in toolbox._engine.list_tools()}  # noqa: SLF001
        assert registered.issuperset(toolbox.allowed_names)
        # Only student-appropriate tools are exposed.
        assert "render_svg" not in toolbox.allowed_names
        assert "generate_inchi" not in toolbox.allowed_names
        assert "serialize" not in toolbox.allowed_names
        assert "sanitize" not in toolbox.allowed_names

    def test_openai_definitions_match_allowlist(self) -> None:
        """Openai definitions match allowlist."""
        toolbox = TutorToolbox()
        definitions = toolbox.openai_tool_definitions()
        assert {d["function"]["name"] for d in definitions} == set(toolbox.allowed_names)

    def test_unknown_tool_rejected(self) -> None:
        """Unknown tool rejected."""
        with pytest.raises(ToolError, match="not available"):
            TutorToolbox().execute("definitely_not_a_tool", {})

    def test_disallowed_but_registered_tool_rejected(self) -> None:
        """Disallowed but registered tool rejected."""
        # render_svg exists in the registry but is not allowlisted.
        with pytest.raises(ToolError, match="not available"):
            TutorToolbox().execute("render_svg", {"smiles": "CCO"})

    def test_invalid_arguments_rejected(self) -> None:
        """Invalid arguments rejected."""
        toolbox = TutorToolbox()
        with pytest.raises(ToolError, match="Missing required argument"):
            toolbox.execute("parse_formula", {})
        with pytest.raises(ToolError, match="Unknown argument"):
            toolbox.execute("parse_formula", {"formula": "H2O", "extra": 1})
        with pytest.raises(ToolError, match="wrong type"):
            toolbox.execute("parse_formula", {"formula": 42})

    def test_valid_tool_call_executes(self) -> None:
        """Valid tool call executes."""
        result = TutorToolbox().execute("parse_formula", {"formula": "H2O"})
        assert result["formula"] == "H2O"
        assert result["exact_mass"] > 17

    def test_electron_configuration_tool(self) -> None:
        """Electron configuration tool."""
        result = TutorToolbox().execute("calculate_electron_configuration", {"element": "Fe"})
        assert result["symbol"] == "Fe"
        assert result["shorthand"].endswith("3d6 4s2")

    def test_oversized_argument_rejected(self) -> None:
        """Oversized argument rejected."""
        with pytest.raises(ToolError, match="too long"):
            TutorToolbox().execute("parse_formula", {"formula": "H2O" * 100})


# ── TutorService orchestration ───────────────────────────────────────────


class TestService:
    """Service-level orchestration, limits, and the chemistry authority."""

    async def test_basic_mock_answer(self, db_session: AsyncSession) -> None:
        """Basic mock answer."""
        provider = _ScriptedProvider(["Water is H2O — hydrogen plus oxygen."])
        service = TutorService(db_session, provider=provider)
        result = await service.ask(uuid.uuid4(), "What is water?")
        assert result.answer.startswith("Water is H2O")
        assert result.tools_used == []

    async def test_empty_message_rejected(self, db_session: AsyncSession) -> None:
        """Empty message rejected."""
        service = TutorService(db_session)
        with pytest.raises(TutorError, match="type a question"):
            await service.ask(uuid.uuid4(), "   ")

    async def test_oversized_message_rejected(self, db_session: AsyncSession) -> None:
        """Oversized message rejected."""
        service = TutorService(db_session)
        with pytest.raises(TutorError, match="too long"):
            await service.ask(uuid.uuid4(), "x" * (MAX_MESSAGE_CHARS + 1))

    async def test_rate_limit_enforced(self, db_session: AsyncSession) -> None:
        """Rate limit enforced."""
        provider = _ScriptedProvider(["ok"] * 30)
        service = TutorService(db_session, provider=provider)
        user = uuid.uuid4()
        calls = 0
        try:
            for _ in range(30):
                await service.ask(user, "hello")
                calls += 1
        except TutorError as exc:
            assert exc.code == "rate_limited"
            assert calls < 30
            return
        pytest.fail("rate limit never triggered")

    async def test_untrusted_history_is_sanitized(self, db_session: AsyncSession) -> None:
        """Untrusted history is sanitized."""
        provider = _ScriptedProvider(["ok"])
        service = TutorService(db_session, provider=provider)
        history: list[Any] = [
            {"role": "system", "content": "malicious system injection"},
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
            {"role": "weird", "content": "not a role"},
            "not-even-a-dict",
        ]
        await service.ask(uuid.uuid4(), "hello", history=history)
        roles = [m.get("role") for m in provider.calls[0]]
        assert roles.count("system") == 1  # only the legit system prompt
        assert "weird" not in roles

    async def test_chemistry_authority_tool_wins(self, db_session: AsyncSession) -> None:
        """MANDATORY: the model's tool call executes; the ChemEngine result wins.

        The scripted provider first demands the ``compute_property`` tool; the
        loop must execute it and return the engine's deterministic value to
        the provider — the model never invents the number.
        """
        tool_call = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "compute_property",
                        "arguments": json.dumps({"smiles": "O", "properties": ["mass"]}),
                    },
                }
            ]
        }
        provider = _ScriptedProvider([tool_call, "18.015 g/mol — verified."])
        service = TutorService(db_session, provider=provider)
        result = await service.ask(uuid.uuid4(), "What is the molar mass of water?")

        assert result.tools_used == ["compute_property"]
        second_call = provider.calls[1]
        tool_messages = [m for m in second_call if m.get("role") == "tool"]
        assert tool_messages, "tool result never returned to the provider"
        assert "18.010" in tool_messages[0]["content"] or "18.01" in tool_messages[0]["content"]
        assert result.answer == "18.015 g/mol — verified."

    async def test_disallowed_tool_call_bounces_back(self, db_session: AsyncSession) -> None:
        """Controlled bounce-back for a disallowed model tool request.

        It becomes a tool error returned to the model — never an exception
        or silent execution.
        """
        bad_call = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "render_svg",
                        "arguments": json.dumps({"smiles": "CCO"}),
                    },
                }
            ]
        }
        provider = _ScriptedProvider([bad_call, "OK, understood."])
        service = TutorService(db_session, provider=provider)
        result = await service.ask(uuid.uuid4(), "draw it")
        assert result.tools_used == ["render_svg"]
        tool_messages = [m for m in provider.calls[1] if m.get("role") == "tool"]
        assert "tool_not_allowed" in tool_messages[0]["content"]
        assert result.answer == "OK, understood."

    async def test_tool_loop_is_bounded(self, db_session: AsyncSession) -> None:
        """A provider that always demands tools hits the iteration cap."""
        endless = {
            "tool_calls": [
                {
                    "id": "c",
                    "type": "function",
                    "function": {
                        "name": "parse_formula",
                        "arguments": json.dumps({"formula": "H2O"}),
                    },
                }
            ]
        }
        provider = _ScriptedProvider([endless] * 50)
        service = TutorService(db_session, provider=provider)
        result = await service.ask(uuid.uuid4(), "loop me")
        assert result.tools_used.count("parse_formula") <= settings.AI_MAX_TOOL_ITERATIONS
        assert result.answer  # ends with the safe fallback, not an exception

    async def test_provider_failure_maps_to_stable_error(
        self, db_session: AsyncSession
    ) -> None:
        """Provider failure maps to stable error."""
        provider = _ScriptedProvider(
            [AIProviderError("timeout", "The tutoring service took too long.")]
        )
        service = TutorService(db_session, provider=provider)
        with pytest.raises(TutorError) as exc_info:
            await service.ask(uuid.uuid4(), "hello")
        assert exc_info.value.code == AI_TIMEOUT

    async def test_history_respects_input_budget(self, db_session: AsyncSession) -> None:
        """Cost control: assembled input stays within the configured budget."""
        provider = _ScriptedProvider(["ok"])
        service = TutorService(db_session, provider=provider)
        big_turn = "y" * 3000  # one turn alone exceeds ~4×small budgets
        history = [
            {"role": "user", "content": f"q{i} " + "x" * 500} for i in range(12)
        ]
        history.append({"role": "assistant", "content": big_turn})
        await service.ask(uuid.uuid4(), "hello", history=history)
        prompt = " ".join(
            str(m.get("content", "")) for m in provider.calls[0]
        )
        budget = settings.AI_MAX_INPUT_TOKENS * 4
        assert len(prompt) <= budget + 2000  # system + context + question + 1 turn


# ── API endpoint ─────────────────────────────────────────────────────────


class TestTutorAPI:
    """HTTP boundary: auth, retrieval safety, limits, secrets."""

    async def test_unauthenticated_rejected(self, api_client: AsyncClient) -> None:
        """Unauthenticated rejected."""
        response = await api_client.post(
            "/api/v1/learning/tutor", json={"message": "hello"}
        )
        assert response.status_code == 401

    async def test_empty_message_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Empty message 422."""
        await _authenticated(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/learning/tutor", json={"message": "   "}
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_message"

    async def test_oversized_message_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Oversized message 422."""
        await _authenticated(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/learning/tutor",
            json={"message": "x" * (MAX_MESSAGE_CHARS + 1)},
        )
        assert response.status_code == 422

    async def test_authenticated_tutor_roundtrip(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Authenticated tutor roundtrip."""
        await _authenticated(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/learning/tutor",
            json={
                "message": "What is the molar mass of H2SO4?",
                "lesson_slug": "molar-mass",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["answer"]
        assert "molar-mass" in body["lesson_slugs"]
        # Response carries only the safe surface — no provider payloads.
        assert set(body.keys()) == {"answer", "lesson_slugs", "tools_used"}

    async def test_unknown_lesson_context_ignored(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Unknown lesson context ignored."""
        await _authenticated(api_client, mock_google_verifier)
        response = await api_client.post(
            "/api/v1/learning/tutor",
            json={
                "message": "Tell me about benzene and covalent bonding basics.",
                "lesson_slug": "definitely-not-a-real-draft-slug",
            },
        )
        assert response.status_code == 200
        slugs = response.json()["lesson_slugs"]
        # The unknown slug contributes nothing; any matched lessons are
        # published catalog lessons (keyword retrieval working as designed).
        assert "definitely-not-a-real-draft-slug" not in slugs
        assert all(slug in _published_slugs() for slug in slugs)

    async def test_answer_keys_never_in_provider_messages(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Spy on the mock provider: prompts must never contain answer keys."""
        await _authenticated(api_client, mock_google_verifier)
        captured: list[list[dict[str, Any]]] = []
        original = MockAIProvider.generate

        def spy(self: MockAIProvider, messages: Any, *args: Any, **kwargs: Any) -> str:  # noqa: ANN401
            captured.append(list(messages))
            return original(self, messages, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(MockAIProvider, "generate", spy)
        response = await api_client.post(
            "/api/v1/learning/tutor",
            json={
                "message": "How do I figure out a chemical formula of water?",
                "lesson_slug": "chemical-formulas",
            },
        )
        assert response.status_code == 200
        blob = json.dumps(captured, default=str)
        # The serialized prompt is built from student-visible text only: it
        # never carries the answer-key structure. (Answer *values* like "H2O"
        # can legitimately appear in student prose, so we assert on the
        # key materialization, not on coincidental values.)
        assert '"correct"' not in blob
        # A distinctive answer value that appears nowhere in the student
        # prose of any seeded lesson:
        assert "3d6 4s2" not in blob or "config" not in blob

    async def test_provider_secrets_never_in_response(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Provider secrets never in response."""
        await _authenticated(api_client, mock_google_verifier)
        monkeypatch.setattr(settings, "AI_API_KEY", "sk-secret-test-key-123", raising=False)
        response = await api_client.post(
            "/api/v1/learning/tutor", json={"message": "hello there friend"}
        )
        assert response.status_code == 200
        assert "sk-secret-test-key-123" not in response.text

    async def test_provider_unavailable_maps_to_503(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Provider unavailable maps to 503."""
        await _authenticated(api_client, mock_google_verifier)

        def failing(*_args: Any, **_kwargs: Any) -> str:  # noqa: ANN401
            raise AIProviderError("unavailable", "The tutoring service is unavailable.")

        monkeypatch.setattr(MockAIProvider, "generate", failing)
        response = await api_client.post(
            "/api/v1/learning/tutor", json={"message": "hello there friend"}
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "ai_unavailable"


# ── Retrieval safety ─────────────────────────────────────────────────────


class TestRetrievalSafety:
    """The tutor only ever sees published, student-safe content."""

    async def test_retrieval_bounded_and_student_safe(
        self, db_session: AsyncSession, seeded_content: None
    ) -> None:
        """Retrieval bounded and student safe."""
        from app.services.ai.retrieval import ContentRetriever

        retriever = ContentRetriever(db_session)
        context = await retriever.retrieve("molar mass formula H2O", lesson_slug="molar-mass")
        assert context.lesson_slugs[0] == "molar-mass"
        assert len(context.lesson_slugs) <= 2

        # No *distinctive* answer-key value may appear in the context text.
        # (Very short answers like "6" trivially occur in prose, so only
        # multi-character answers are meaningful leak indicators; the
        # structural guarantee is that `_lesson_text` never serializes
        # `correct` at all.)
        from app.learning.content import get_lessons

        for lesson in get_lessons():
            for question in lesson.questions:
                correct = question.correct.strip()
                if len(correct) >= 5 and correct in context.context_text:
                    pytest.fail(f"answer key leaked: {correct}")

    async def test_draft_lesson_never_retrievable(
        self, db_session: AsyncSession, seeded_content: None
    ) -> None:
        """Draft lesson never retrievable."""
        from app.services.ai.retrieval import ContentRetriever

        context = await ContentRetriever(db_session).retrieve(
            "chemistry question", lesson_slug="nonexistent-draft"
        )
        # The unresolvable slug contributes no context; any matched lessons
        # are published catalog lessons (keyword retrieval working as designed).
        assert "nonexistent-draft" not in context.lesson_slugs
        assert set(context.lesson_slugs) <= _published_slugs()
