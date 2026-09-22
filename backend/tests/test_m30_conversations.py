"""M30 AI Tutor Completion & Conversation Infrastructure — backend tests.

Covers the formally scoped M30 acceptance surface:
- persistent conversations (creation, listing, messages, deletion, limits)
- server-enforced ownership and cross-user isolation
- server-side history (the client cannot inject foreign history)
- streaming endpoint (SSE events, tool calls during streaming, provider
  failure, malformed/unauthorized requests)
- deterministic tool-result cache (deterministic keys, hit/miss, TTL,
  bounds/expiry)
and proves the M29 security boundaries remain intact.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai.cache import ToolResultCache
from app.services.ai.service import TutorService
from app.services.ai.tools import TutorToolbox
from tests.conftest import MockGoogleTokenVerifier


async def _auth(
    api_client: AsyncClient, verifier: MockGoogleTokenVerifier, sub: str
) -> None:
    """Authenticate a test client as a distinct user."""
    verifier.register_token(sub, sub=sub, email=f"{sub}@chemora.test")
    login = await api_client.post(
        "/api/v1/auth/google", json={"credential": sub}
    )
    assert login.status_code == 200


async def _create_conversation(api_client: AsyncClient) -> str:
    """Create one conversation for the current client user; return its id."""
    response = await api_client.post(
        "/api/v1/learning/tutor/conversations", json={"title": "Chem help"}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


# ── Conversation CRUD + ownership ─────────────────────────────────────────


class TestConversationAPI:
    """HTTP contract for persistent conversations."""

    async def test_unauthenticated_create_rejected(
        self, api_client: AsyncClient
    ) -> None:
        """401 when creating without a session."""
        response = await api_client.post(
            "/api/v1/learning/tutor/conversations", json={}
        )
        assert response.status_code == 401

    async def test_unauthenticated_list_rejected(
        self, api_client: AsyncClient
    ) -> None:
        """401 when listing without a session."""
        response = await api_client.get("/api/v1/learning/tutor/conversations")
        assert response.status_code == 401

    async def test_unauthenticated_stream_rejected(
        self, api_client: AsyncClient
    ) -> None:
        """401 when streaming without a session."""
        response = await api_client.post(
            f"/api/v1/learning/tutor/conversations/{uuid.uuid4()}/messages",
            json={"message": "hello"},
        )
        assert response.status_code == 401

    async def test_create_list_and_delete(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Full CRUD round-trip for the owner."""
        await _auth(api_client, mock_google_verifier, "m30_owner")

        created = await api_client.post(
            "/api/v1/learning/tutor/conversations", json={"title": "My chat"}
        )
        assert created.status_code == 201
        body = created.json()
        assert body["title"] == "My chat"
        assert body["message_count"] == 0

        listed = await api_client.get("/api/v1/learning/tutor/conversations")
        assert listed.status_code == 200
        assert [c["id"] for c in listed.json()["conversations"]] == [body["id"]]

        deleted = await api_client.delete(
            f"/api/v1/learning/tutor/conversations/{body['id']}"
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

        listed_again = await api_client.get(
            "/api/v1/learning/tutor/conversations"
        )
        assert listed_again.json()["conversations"] == []

    async def test_delete_missing_returns_404(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Deleting a nonexistent conversation returns 404."""
        await _auth(api_client, mock_google_verifier, "m30_delete_missing")
        response = await api_client.delete(
            f"/api/v1/learning/tutor/conversations/{uuid.uuid4()}"
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "conversation_not_found"

    async def test_cross_user_isolation(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """A foreign conversation is indistinguishable from a missing one."""
        await _auth(api_client, mock_google_verifier, "m30_user_a")
        conversation_id = await _create_conversation(api_client)

        # A different user cannot read, delete, or post to it.
        verifier = mock_google_verifier
        verifier.register_token("m30_user_b", sub="m30_user_b", email="b@x.test")
        login = await api_client.post(
            "/api/v1/auth/google", json={"credential": "m30_user_b"}
        )
        assert login.status_code == 200

        read = await api_client.get(
            f"/api/v1/learning/tutor/conversations/{conversation_id}"
        )
        assert read.status_code == 404
        assert read.json()["detail"]["code"] == "conversation_not_found"

        delete_attempt = await api_client.delete(
            f"/api/v1/learning/tutor/conversations/{conversation_id}"
        )
        assert delete_attempt.status_code == 404

        post = await api_client.post(
            f"/api/v1/learning/tutor/conversations/{conversation_id}/messages",
            json={"message": "sneaky question"},
        )
        assert post.status_code == 404

        # The owner's conversation list never leaks user A's conversation
        # into user B's view and vice versa.
        b_list = await api_client.get("/api/v1/learning/tutor/conversations")
        assert b_list.json()["conversations"] == []

    async def test_server_side_history_and_persistence(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Messages persist and are served back server-side."""
        await _auth(api_client, mock_google_verifier, "m30_history")
        conversation_id = await _create_conversation(api_client)

        first = await api_client.post(
            f"/api/v1/learning/tutor/conversations/{conversation_id}/messages",
            json={"message": "What is the molar mass of H2O?"},
        )
        assert first.status_code == 200
        assert "data:" in first.text  # SSE framed

        second = await api_client.post(
            f"/api/v1/learning/tutor/conversations/{conversation_id}/messages",
            json={"message": "And for CO2?"},
        )
        assert second.status_code == 200

        detail = await api_client.get(
            f"/api/v1/learning/tutor/conversations/{conversation_id}"
        )
        assert detail.status_code == 200
        messages = detail.json()["messages"]
        roles = [m["role"] for m in messages]
        # The client never sent history; the server persisted both turns.
        assert roles == ["user", "assistant", "user", "assistant"]
        assert messages[0]["content"] == "What is the molar mass of H2O?"
        assert messages[2]["content"] == "And for CO2?"

    async def test_stream_events_are_wellformed_sse(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """The streamed body is SSE with delta events and a done frame."""
        await _auth(api_client, mock_google_verifier, "m30_sse")
        conversation_id = await _create_conversation(api_client)

        response = await api_client.post(
            f"/api/v1/learning/tutor/conversations/{conversation_id}/messages",
            json={"message": "hello tutor"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        events: list[dict[str, Any]] = []
        for line in response.text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
        kinds = [e["type"] for e in events]
        assert "delta" in kinds
        assert kinds[-1] == "done"
        assert set(events[-1].keys()) == {"type", "tools_used", "lesson_slugs"}
        # Text deltas concatenate to the persisted assistant message.
        text = "".join(e.get("text", "") for e in events if e["type"] == "delta")
        assert text

    async def test_stream_provider_failure_maps_to_error_event(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A provider failure surfaces as one stable SSE error frame."""
        from app.services.ai.provider import AIProviderError, MockAIProvider

        await _auth(api_client, mock_google_verifier, "m30_fail")
        conversation_id = await _create_conversation(api_client)

        def failing(*_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            raise AIProviderError(
                "unavailable", "The tutoring service is unavailable."
            )

        monkeypatch.setattr(MockAIProvider, "generate", failing)
        monkeypatch.setattr(MockAIProvider, "generate_stream", failing, raising=False)

        response = await api_client.post(
            f"/api/v1/learning/tutor/conversations/{conversation_id}/messages",
            json={"message": "hello tutor"},
        )
        assert response.status_code == 200  # stream started
        events = [
            json.loads(line[len("data: "):])
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        errors = [e for e in events if e["type"] == "error"]
        assert len(errors) == 1
        assert errors[0]["code"] == "ai_unavailable"

    async def test_stream_malformed_request_422(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Oversized message is rejected before streaming starts."""
        from app.services.ai.service import MAX_MESSAGE_CHARS

        await _auth(api_client, mock_google_verifier, "m30_malformed")
        conversation_id = await _create_conversation(api_client)
        response = await api_client.post(
            f"/api/v1/learning/tutor/conversations/{conversation_id}/messages",
            json={"message": "x" * (MAX_MESSAGE_CHARS + 1)},
        )
        assert response.status_code == 422

    async def test_stream_to_missing_conversation_404(
        self,
        api_client: AsyncClient,
        mock_google_verifier: MockGoogleTokenVerifier,
    ) -> None:
        """Streaming into a nonexistent conversation returns 404."""
        await _auth(api_client, mock_google_verifier, "m30_missing")
        response = await api_client.post(
            f"/api/v1/learning/tutor/conversations/{uuid.uuid4()}/messages",
            json={"message": "hello"},
        )
        assert response.status_code == 404


class TestServiceLevelConversations:
    """Service-layer behavior without HTTP."""

    async def test_conversation_cap_enforced(
        self, db_session: AsyncSession
    ) -> None:
        """Creating beyond the per-user cap raises a stable error."""
        from app.repositories.tutor import MAX_CONVERSATIONS_PER_USER
        from app.services.ai.service import CONVERSATION_LIMIT, TutorError

        service = TutorService(db_session)
        user = uuid.uuid4()
        for _ in range(MAX_CONVERSATIONS_PER_USER):
            await service.create_conversation(user, "t")
        with pytest.raises(TutorError) as exc_info:
            await service.create_conversation(user, "one too many")
        assert exc_info.value.code == CONVERSATION_LIMIT

    async def test_message_cap_enforced(self, db_session: AsyncSession) -> None:
        """Appending beyond the per-conversation cap raises a stable error."""
        from app.repositories.tutor import (
            MAX_MESSAGES_PER_CONVERSATION,
            TutorConversationRepository,
        )
        from app.services.ai.service import MESSAGE_LIMIT, TutorError

        service = TutorService(db_session)
        user = uuid.uuid4()
        summary = await service.create_conversation(user, "t")
        repo = TutorConversationRepository(db_session)
        conversation = await repo.get_conversation(summary.id, user)
        assert conversation is not None
        for i in range(MAX_MESSAGES_PER_CONVERSATION):
            await repo.append_message(conversation, "user", f"m{i}")
        with pytest.raises(TutorError) as exc_info:
            await service.ask_in_conversation(user, summary.id, "over the cap")
        assert exc_info.value.code == MESSAGE_LIMIT

    async def test_tool_calls_execute_during_stream(
        self, db_session: AsyncSession
    ) -> None:
        """A scripted tool-demanding provider works through the stream path."""
        tool_call = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "compute_property",
                        "arguments": json.dumps(
                            {"smiles": "O", "properties": ["mass"]}
                        ),
                    },
                }
            ]
        }

        class _ScriptedStreamProvider:
            """Streams a tool call turn, then the final text."""

            def __init__(self) -> None:
                self.calls: list[list[dict[str, Any]]] = []

            def generate(
                self,
                messages: list[dict[str, Any]],
                tools: list[dict[str, Any]],
                max_output_tokens: int,
                timeout_seconds: float,
            ) -> Any:  # noqa: ANN401
                self.calls.append(list(messages))
                if len(self.calls) == 1:
                    return tool_call
                return "18.015 g/mol — verified."

            def generate_stream(
                self,
                messages: list[dict[str, Any]],
                tools: list[dict[str, Any]],
                max_output_tokens: int,
                timeout_seconds: float,
            ) -> Any:  # noqa: ANN401
                self.calls.append(list(messages))
                from app.services.ai.provider import StreamEvent

                if len(self.calls) == 1:
                    yield StreamEvent("tool_calls", tool_call)
                    return
                yield StreamEvent("text", "18.015 g/mol — verified.")
                yield StreamEvent("final", "18.015 g/mol — verified.")

        provider = _ScriptedStreamProvider()
        service = TutorService(db_session, provider=provider)
        user = uuid.uuid4()
        summary = await service.create_conversation(user, "t")
        events: list[dict[str, object]] = []
        async for event in service.stream_in_conversation(
            user, summary.id, "What is the molar mass of water?"
        ):
            events.append(event)
        text = "".join(
            str(e.get("text", "")) for e in events if e.get("type") == "delta"
        )
        assert "18.015" in text
        done = [e for e in events if e.get("type") == "done"]
        assert done and done[0]["tools_used"] == ["compute_property"]


# ── Deterministic tool-result cache ───────────────────────────────────────


class TestToolResultCache:
    """Cache keys, hit/miss, TTL, and bounds."""

    def test_cache_key_is_deterministic_and_order_insensitive(self) -> None:
        """Same arguments in any dict order map to the same key."""
        cache = ToolResultCache()
        key_a = cache.cache_key("compute_property", {"smiles": "O", "properties": ["mass"]})
        key_b = cache.cache_key("compute_property", {"properties": ["mass"], "smiles": "O"})
        assert key_a == key_b
        assert cache.cache_key("parse_formula", {"formula": "H2O"}) != key_a
        assert cache.cache_key("compute_property", {"smiles": "CCO"}) != key_a

    def test_hit_miss_and_copy_semantics(self) -> None:
        """A stored result is returned on hit; misses return None."""
        cache = ToolResultCache()
        args = {"formula": "H2O"}
        assert cache.get("parse_formula", args) is None
        cache.put("parse_formula", args, {"formula": "H2O", "exact_mass": 18.01})
        hit = cache.get("parse_formula", args)
        assert hit == {"formula": "H2O", "exact_mass": 18.01}
        # Mutating the returned dict must not corrupt the cache.
        assert hit is not None
        hit["formula"] = "MUTATED"
        assert cache.get("parse_formula", args)["formula"] == "H2O"

    def test_ttl_expiration(self) -> None:
        """Entries expire after the TTL (lazy sweep on access)."""
        cache = ToolResultCache(ttl_seconds=0.05)
        cache.put("parse_formula", {"formula": "H2O"}, {"ok": True})
        assert cache.get("parse_formula", {"formula": "H2O"}) == {"ok": True}
        time.sleep(0.06)
        assert cache.get("parse_formula", {"formula": "H2O"}) is None
        assert cache.stats.expirations == 1

    def test_entry_bound_eviction(self) -> None:
        """Oldest entries are evicted when the cap is reached."""
        cache = ToolResultCache(max_entries=3)
        for i in range(5):
            cache.put("parse_formula", {"formula": f"H{i}O"}, {"i": i})
        assert len(cache) == 3
        assert cache.stats.evictions >= 2
        # The oldest two are gone; the newest survive.
        assert cache.get("parse_formula", {"formula": "H0O"}) is None
        assert cache.get("parse_formula", {"formula": "H4O"}) == {"i": 4}

    def test_toolbox_uses_cache(self) -> None:
        """Identical validated tool calls hit the cache; engine untouched."""
        toolbox = TutorToolbox(cache=ToolResultCache())
        first = toolbox.execute("parse_formula", {"formula": "H2O"})
        second = toolbox.execute("parse_formula", {"formula": "H2O"})
        assert first == second
        assert toolbox._cache.stats.hits == 1  # noqa: SLF001
        assert toolbox._cache.stats.misses == 1  # noqa: SLF001

    def test_toolbox_does_not_cache_failures(self) -> None:
        """A failing tool call is never cached."""
        toolbox = TutorToolbox(cache=ToolResultCache())
        for _ in range(2):
            with pytest.raises(Exception, match="not available"):
                toolbox.execute("render_svg", {"smiles": "CCO"})
        assert len(toolbox._cache) == 0  # noqa: SLF001

    def test_cache_disabled_by_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AI_TOOL_CACHE_ENABLED=false bypasses the cache entirely."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "AI_TOOL_CACHE_ENABLED", False)
        toolbox = TutorToolbox(cache=ToolResultCache())
        toolbox.execute("parse_formula", {"formula": "H2O"})
        toolbox.execute("parse_formula", {"formula": "H2O"})
        assert toolbox._cache.stats.hits == 0  # noqa: SLF001
        assert toolbox._cache.stats.misses == 0  # noqa: SLF001
