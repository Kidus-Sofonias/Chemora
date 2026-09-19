"""Tutor service — orchestration for the AI chemistry tutor (M29).

Flow (all server-side; the browser never executes chemistry or talks to a
provider):

    student question
      → student-safe retrieval (published lessons only, no answer keys)
      → controlled provider/tool loop (bounded iterations)
          model tool request → allowlist + schema validation → ChemEngine
      → final assistant text

Boundaries honored:
- ChemEngine is the deterministic chemistry authority; the model is told to
  use tool results verbatim and never to guess computed values.
- The client may *suggest* lesson context; the server verifies it.
- Provider/tool failures become stable client-safe error categories.
- A simple in-process per-user rate limit bounds cost (single-process
  deployments only; a distributed limiter is deliberately out of scope).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.tutor import (
    ConversationLimitError,
    TutorConversationRepository,
)
from app.services.ai.provider import (
    AIProvider,
    AIProviderError,
    StreamCapableProvider,
    StreamEvent,
    make_provider,
)
from app.services.ai.retrieval import ContentRetriever, RetrievedContext
from app.services.ai.tools import ToolError, TutorToolbox

logger = logging.getLogger(__name__)

#: Maximum characters of a single student message (schema enforces this too).
MAX_MESSAGE_CHARS = 1000
#: Maximum client-supplied conversation turns kept in context.
MAX_HISTORY_TURNS = 12
#: Maximum characters per history message kept in context.
MAX_HISTORY_CHARS = 2000
#: Approximate characters-per-token used to bound the assembled prompt
#: (settings.AI_MAX_INPUT_TOKENS is a token budget; input is measured in
#: characters, so a conservative ≈4 chars/token keeps the estimate safe).
_CHARS_PER_TOKEN = 4

# Stable, client-safe error codes (mirrored by the API layer).
INVALID_MESSAGE = "invalid_message"
RATE_LIMITED = "rate_limited"
AI_TIMEOUT = "ai_timeout"
AI_AUTH = "ai_auth"
AI_UNAVAILABLE = "ai_unavailable"
AI_ERROR = "ai_error"
CONVERSATION_NOT_FOUND = "conversation_not_found"
CONVERSATION_LIMIT = "conversation_limit"
MESSAGE_LIMIT = "message_limit"

_CATEGORY_TO_CODE = {
    "timeout": AI_TIMEOUT,
    "rate_limit": AI_UNAVAILABLE,
    "auth_failure": AI_AUTH,
    "unavailable": AI_UNAVAILABLE,
    "provider_error": AI_ERROR,
    "bad_request": AI_ERROR,
}

_FALLBACK_ANSWER = (
    "I couldn't complete that explanation right now. Please try again in a "
    "moment — and remember you can always check values directly in the "
    "Chemistry and Element explorers."
)


class TutorError(Exception):
    """A stable, client-safe tutor error."""

    def __init__(self, code: str, message: str) -> None:
        """Initialize with a stable code and user-facing message."""
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class TutorAnswer:
    """Structured tutor result returned to the API layer."""

    answer: str
    lesson_slugs: list[str]
    tools_used: list[str]


@dataclass(slots=True)
class ConversationSummary:
    """Client-safe conversation metadata (never the messages themselves)."""

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class _RateLimiter:
    """Simple in-process sliding-window limiter keyed by user id."""

    def __init__(self, limit_per_minute: int) -> None:
        """Initialize with the per-minute request cap (0 disables limiting)."""
        self._limit = limit_per_minute
        self._hits: dict[uuid.UUID, deque[float]] = defaultdict(deque)

    def check(self, user_id: uuid.UUID) -> None:
        """Raise :class:`TutorError` if the user exceeded the cap."""
        if self._limit <= 0:
            return
        now = time.monotonic()
        window = self._hits[user_id]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= self._limit:
            raise TutorError(
                RATE_LIMITED,
                "You're sending questions too quickly. Please wait a moment.",
            )
        window.append(now)


class TutorService:
    """Authenticated chemistry-tutor orchestration."""

    def __init__(
        self,
        db: AsyncSession,
        provider: AIProvider | None = None,
        toolbox: TutorToolbox | None = None,
    ) -> None:
        """Initialize with the request session and optional injected parts."""
        self._db = db
        self._provider = provider if provider is not None else self._default_provider()
        self._toolbox = toolbox if toolbox is not None else TutorToolbox()
        self._limiter = _RateLimiter(settings.AI_RATE_LIMIT_PER_MINUTE)

    @staticmethod
    def _default_provider() -> AIProvider:
        """Build the configured provider (mock by default)."""
        return make_provider(
            settings.AI_PROVIDER,
            settings.AI_API_BASE,
            settings.AI_API_KEY,
            settings.AI_MODEL,
            anthropic_base=settings.AI_ANTHROPIC_BASE,
            anthropic_key=settings.AI_ANTHROPIC_API_KEY,
            anthropic_model=settings.AI_ANTHROPIC_MODEL,
        )

    async def ask(
        self,
        user_id: uuid.UUID,
        message: str,
        history: list[dict[str, str]] | None = None,
        lesson_slug: str | None = None,
    ) -> TutorAnswer:
        """Answer one tutoring question for an authenticated student.

        Args:
            user_id: The authenticated user's id (from the Chemora session —
                never accepted from the client).
            message: The student's question.
            history: Optional client-supplied prior turns. Untrusted: only
                well-formed user/assistant text survives.
            lesson_slug: Optional current-lesson context. Verified server-side.

        Returns:
            A dict with ``answer``, ``lesson_slugs`` (context used), and
            ``tools_used`` (allowlisted tool names actually executed).

        Raises:
            TutorError: With a stable client-safe code on any failure.
        """
        self._limiter.check(user_id)
        text = self._validate_message(message)
        clean_history = self._clean_history(history or [])

        retrieval = await ContentRetriever(self._db).retrieve(text, lesson_slug)
        tools_used: list[str] = []
        answer = await self._run_provider_loop(text, clean_history, retrieval, tools_used)
        return TutorAnswer(
            answer=answer,
            lesson_slugs=retrieval.lesson_slugs,
            tools_used=tools_used,
        )

    # ── Provider/tool loop ────────────────────────────────────────

    def _input_budget_chars(self) -> int:
        """Character budget for the assembled prompt (cost control)."""
        return max(settings.AI_MAX_INPUT_TOKENS, 0) * _CHARS_PER_TOKEN

    def _trim_history_to_budget(
        self,
        history: list[dict[str, str]],
        budget: int,
    ) -> list[dict[str, str]]:
        """Keep the most recent history turns that fit the character budget."""
        kept: list[dict[str, str]] = []
        used = 0
        for turn in reversed(history):
            cost = len(turn["content"])
            if used + cost > budget:
                break
            kept.insert(0, turn)
            used += cost
        return kept

    async def _run_provider_loop(
        self,
        question: str,
        history: list[dict[str, str]],
        retrieval: RetrievedContext,
        tools_used: list[str],
    ) -> str:
        """Run the bounded provider/tool loop and return the final text."""
        # Input budget (cost control): reserve room for the system prompt,
        # lesson context, and the question itself; history fills what remains.
        budget = self._input_budget_chars()
        fixed = len(retrieval.system_prompt) + len(question) + len(retrieval.context_text)
        history = self._trim_history_to_budget(history, max(budget - fixed, 0))

        messages: list[dict[str, object]] = [
            {"role": "system", "content": retrieval.system_prompt}
        ]
        if retrieval.context_text:
            messages.append(
                {
                    "role": "system",
                    "content": "Relevant Chemora lesson content:\n"
                    + retrieval.context_text,
                }
            )
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})
        tool_defs = self._toolbox.openai_tool_definitions()

        for _ in range(settings.AI_MAX_TOOL_ITERATIONS):
            result = await self._call_provider(messages, tool_defs)
            if isinstance(result, dict) and result.get("tool_calls"):
                calls = self._extract_tool_calls(result["tool_calls"])
                if not calls:
                    return _FALLBACK_ANSWER
                messages.append({"role": "assistant", "content": "", "tool_calls": calls})
                for call_id, name, arguments in calls:
                    tools_used.append(name)
                    messages.append(self._execute_tool_message(call_id, name, arguments))
                continue
            text = result if isinstance(result, str) else ""
            return text or _FALLBACK_ANSWER

        # Hard loop bound reached — never spin forever.
        logger.warning("Tutor tool loop hit the iteration cap")
        return _FALLBACK_ANSWER

    async def _call_provider(
        self, messages: list[dict[str, object]], tool_defs: list[dict[str, object]]
    ) -> object:
        """Invoke the provider off the event loop, mapping errors."""
        import asyncio

        try:
            return await asyncio.to_thread(
                self._provider.generate,
                messages,
                tool_defs,
                settings.AI_MAX_OUTPUT_TOKENS,
                settings.AI_TIMEOUT_SECONDS,
            )
        except AIProviderError as exc:
            code = _CATEGORY_TO_CODE.get(exc.category, AI_ERROR)
            raise TutorError(code, exc.message) from exc

    def _execute_tool_message(
        self, call_id: str, name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        """Execute one tool call and build the provider tool-result message."""
        try:
            output = self._toolbox.execute(name, dict(arguments))
            return {"role": "tool", "tool_call_id": call_id, "content": str(output)}
        except ToolError as exc:
            # Controlled tool errors go back to the model so it can recover
            # (e.g. retry with a corrected molecule reference).
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "content": f"Tool error ({exc.code}): {exc.message}",
            }

    @staticmethod
    def _extract_tool_calls(
        raw: list[object],
    ) -> list[tuple[str, str, dict[str, object]]]:
        """Normalize provider tool calls to (id, name, args) tuples."""
        calls: list[tuple[str, str, dict[str, object]]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            function = entry.get("function")
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            arguments = function.get("arguments", {})
            call_id = entry.get("id") or f"call_{len(calls)}"
            if isinstance(name, str):
                if isinstance(arguments, str):
                    import json

                    try:
                        arguments = json.loads(arguments) if arguments.strip() else {}
                    except ValueError:
                        arguments = {}
                if isinstance(arguments, dict):
                    calls.append((str(call_id), name, arguments))
        return calls

    # ── Input hygiene ─────────────────────────────────────────────────

    @staticmethod
    def _validate_message(message: str) -> str:
        """Validate and normalize the student's question."""
        text = (message or "").strip()
        if not text:
            raise TutorError(INVALID_MESSAGE, "Please type a question first.")
        if len(text) > MAX_MESSAGE_CHARS:
            raise TutorError(INVALID_MESSAGE, "That question is too long. Please shorten it.")
        return text

    # ── Conversations (M30) ────────────────────────────────────

    @staticmethod
    def _validate_title(title: str | None) -> str:
        """Normalize a client-supplied conversation title (bounded, optional)."""
        return (title or "").strip()[:200]

    async def create_conversation(
        self, user_id: uuid.UUID, title: str | None = None
    ) -> ConversationSummary:
        """Create an empty conversation owned by the authenticated user."""
        repo = TutorConversationRepository(self._db)
        try:
            conversation = await repo.create_conversation(
                user_id, self._validate_title(title)
            )
        except ConversationLimitError as exc:
            code = (
                CONVERSATION_LIMIT
                if exc.code == "conversation_limit"
                else MESSAGE_LIMIT
            )
            raise TutorError(code, exc.message) from exc
        return ConversationSummary(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=0,
        )

    async def list_conversations(
        self, user_id: uuid.UUID
    ) -> list[ConversationSummary]:
        """List the authenticated user's conversations (metadata only)."""
        repo = TutorConversationRepository(self._db)
        rows = await repo.list_conversations(user_id)
        summaries: list[ConversationSummary] = []
        for row in rows:
            summaries.append(
                ConversationSummary(
                    id=row.id,
                    title=row.title,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    message_count=len(row.messages) if row.messages else 0,
                )
            )
        return summaries

    async def get_conversation_messages(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> list[dict[str, str]]:
        """Return one conversation's messages (ownership enforced).

        Raises:
            TutorError: ``conversation_not_found`` when the conversation does
                not exist or belongs to another user (indistinguishable —
                existence is never leaked across users).
        """
        repo = TutorConversationRepository(self._db)
        conversation = await repo.get_conversation(conversation_id, user_id)
        if conversation is None:
            raise TutorError(
                CONVERSATION_NOT_FOUND,
                "That conversation could not be found.",
            )
        messages = await repo.list_messages(conversation.id)
        return [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]

    async def delete_conversation(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> bool:
        """Delete one conversation (ownership enforced).

        Returns False (or raises not-found) when it does not exist or is not
        owned by the user.
        """
        repo = TutorConversationRepository(self._db)
        deleted = await repo.delete_conversation(conversation_id, user_id)
        return deleted

    async def ask_in_conversation(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message: str,
        lesson_slug: str | None = None,
    ) -> TutorAnswer:
        """Ask a question inside a persistent conversation (M30).

        History is loaded **server-side** from the owned conversation — the
        client cannot inject foreign or arbitrary history. The user message
        and the final answer are persisted before returning.
        """
        repo = TutorConversationRepository(self._db)
        conversation = await repo.get_conversation(conversation_id, user_id)
        if conversation is None:
            raise TutorError(
                CONVERSATION_NOT_FOUND,
                "That conversation could not be found.",
            )
        stored = await repo.list_messages(conversation.id)
        server_history = [
            {"role": m.role, "content": m.content}
            for m in stored
            if m.role in ("user", "assistant")
        ]
        text = self._validate_message(message)
        self._limiter.check(user_id)

        await self._append(repo, conversation, "user", text)
        try:
            retrieval = await ContentRetriever(self._db).retrieve(text, lesson_slug)
            tools_used: list[str] = []
            answer = await self._run_provider_loop(
                text, server_history, retrieval, tools_used
            )
        except Exception:
            await self._db.rollback()
            raise
        await self._append(repo, conversation, "assistant", answer)
        await self._db.commit()
        return TutorAnswer(
            answer=answer,
            lesson_slugs=retrieval.lesson_slugs,
            tools_used=tools_used,
        )

    @staticmethod
    async def _append(
        repo: TutorConversationRepository,
        conversation: object,
        role: str,
        content: str,
    ) -> None:
        """Append a message, translating limit errors to stable codes."""
        try:
            await repo.append_message(conversation, role, content)  # type: ignore[arg-type]
        except ConversationLimitError as exc:
            raise TutorError(
                CONVERSATION_LIMIT if exc.code == "conversation_limit"
                else MESSAGE_LIMIT,
                exc.message,
            ) from exc

    async def assert_conversation(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> None:
        """Raise ``conversation_not_found`` unless the user owns the id.

        Used by the API layer to return a real 404 status before a streaming
        response starts. Existence is never leaked across users.
        """
        repo = TutorConversationRepository(self._db)
        conversation = await repo.get_conversation(conversation_id, user_id)
        if conversation is None:
            raise TutorError(
                CONVERSATION_NOT_FOUND,
                "That conversation could not be found.",
            )

    async def stream_in_conversation(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message: str,
        lesson_slug: str | None = None,
        *,
        check_limiter: bool = True,
    ) -> AsyncIterator[dict[str, object]]:
        """Stream a tutoring answer inside a persistent conversation (M30).

        Event protocol (dicts, encoded as SSE by the API layer):
            {"type": "delta", "text": "..."}   — incremental answer chunk
            {"type": "done", "tools_used": [...], "lesson_slugs": [...]}
            {"type": "error", "code": "...", "message": "..."}

        Guarantees:
        - The conversation must exist and belong to the user; the user's
          message is persisted (and committed) before generation starts.
        - Tool calls run through the same bounded, allowlisted loop as the
          non-streaming path; provider tool traffic never reaches the client.
        - The assistant message is persisted in a ``finally`` block, so an
          interrupted stream still leaves the partial answer behind.
        - Provider failures become a single stable ``error`` event.
        """
        repo = TutorConversationRepository(self._db)
        conversation = await repo.get_conversation(conversation_id, user_id)
        if conversation is None:
            raise TutorError(
                CONVERSATION_NOT_FOUND,
                "That conversation could not be found.",
            )
        stored = await repo.list_messages(conversation.id)
        server_history = [
            {"role": m.role, "content": m.content}
            for m in stored
            if m.role in ("user", "assistant")
        ]
        text = self._validate_message(message)
        if check_limiter:
            self._limiter.check(user_id)
        await self._append(repo, conversation, "user", text)
        await self._db.commit()

        retrieval = await ContentRetriever(self._db).retrieve(text, lesson_slug)
        tools_used: list[str] = []
        answer_parts: list[str] = []
        try:
            async for event in self._stream_provider_loop(
                text, server_history, retrieval, tools_used
            ):
                if event.get("type") == "delta":
                    answer_parts.append(str(event.get("text", "")))
                yield event
            yield {
                "type": "done",
                "tools_used": tools_used,
                "lesson_slugs": retrieval.lesson_slugs,
            }
        finally:
            # Persist the accumulated answer whether the stream completed,
            # failed mid-way, or the client disconnected.
            answer = "".join(answer_parts)
            if answer:
                try:
                    await self._append(repo, conversation, "assistant", answer)
                    await self._db.commit()
                except Exception:  # noqa: BLE001 - cleanup must never raise
                    logger.exception("Failed to persist streamed tutor answer")
                    await self._db.rollback()

    async def _stream_provider_loop(
        self,
        question: str,
        history: list[dict[str, str]],
        retrieval: RetrievedContext,
        tools_used: list[str],
    ) -> AsyncIterator[dict[str, object]]:
        """Bounded provider/tool loop that streams the final answer text.

        Non-final turns (tool-call round-trips) are handled silently and
        server-side, exactly like :meth:`_run_provider_loop`. When the
        provider produces answer text, it is yielded incrementally.
        """
        import asyncio
        import queue

        budget = self._input_budget_chars()
        fixed = len(retrieval.system_prompt) + len(question) + len(retrieval.context_text)
        history = self._trim_history_to_budget(history, max(budget - fixed, 0))

        messages: list[dict[str, object]] = [
            {"role": "system", "content": retrieval.system_prompt}
        ]
        if retrieval.context_text:
            messages.append(
                {
                    "role": "system",
                    "content": "Relevant Chemora lesson content:\n"
                    + retrieval.context_text,
                }
            )
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})
        tool_defs = self._toolbox.openai_tool_definitions()
        can_stream = hasattr(self._provider, "generate_stream")

        for _ in range(settings.AI_MAX_TOOL_ITERATIONS):
            if can_stream:
                # Pump the blocking event iterator from a worker thread into
                # a queue so the event loop can await chunks incrementally.
                events: queue.Queue[object] = queue.Queue()
                loop = asyncio.get_running_loop()

                def _pump(iterator: Iterator[StreamEvent], q: queue.Queue[object]) -> None:
                    """Drain the blocking iterator into the queue."""
                    try:
                        for item in iterator:
                            q.put(item)
                    except AIProviderError as exc:
                        q.put(exc)
                    except Exception:  # noqa: BLE001 - never leak internals
                        logger.exception("Streaming provider failure")
                        q.put(AIProviderError("provider_error", "x"))
                    finally:
                        q.put(None)

                stream_provider = cast(
                    "StreamCapableProvider", self._provider
                )
                loop.run_in_executor(
                    None,
                    _pump,
                    _safe_stream_iter(stream_provider, messages, tool_defs),
                    events,
                )
                accumulated: list[str] = []
                while True:
                    raw = await asyncio.to_thread(events.get)
                    if raw is None:
                        break
                    if isinstance(raw, AIProviderError):
                        code = _CATEGORY_TO_CODE.get(raw.category, AI_ERROR)
                        raise TutorError(code, raw.message) from raw
                    item = cast(StreamEvent, raw)
                    if item.kind == "tool_calls":
                        calls = self._extract_tool_calls(
                            item.payload.get("tool_calls", [])
                        )
                        if not calls:
                            yield {"type": "delta", "text": _FALLBACK_ANSWER}
                            return
                        messages.append(
                            {"role": "assistant", "content": "", "tool_calls": calls}
                        )
                        for call_id, name, arguments in calls:
                            tools_used.append(name)
                            messages.append(
                                self._execute_tool_message(call_id, name, arguments)
                            )
                        break  # next loop iteration with the tool results
                    if item.kind == "text":
                        chunk = str(item.payload)
                        accumulated.append(chunk)
                        yield {"type": "delta", "text": chunk}
                else:
                    continue
                if accumulated:
                    # Streaming turn produced text — the answer is done.
                    return
                continue  # tool round-trip happened; loop again
            # Non-streaming provider: reuse the plain loop.
            result = await self._call_provider(messages, tool_defs)
            if isinstance(result, dict) and result.get("tool_calls"):
                calls = self._extract_tool_calls(result["tool_calls"])
                if not calls:
                    yield {"type": "delta", "text": _FALLBACK_ANSWER}
                    return
                messages.append({"role": "assistant", "content": "", "tool_calls": calls})
                for call_id, name, arguments in calls:
                    tools_used.append(name)
                    messages.append(self._execute_tool_message(call_id, name, arguments))
                continue
            text_out = result if isinstance(result, str) else ""
            yield {"type": "delta", "text": text_out or _FALLBACK_ANSWER}
            return

        # Hard loop bound reached — never spin forever.
        logger.warning("Tutor streaming tool loop hit the iteration cap")
        yield {"type": "delta", "text": _FALLBACK_ANSWER}

    @staticmethod
    def _history_for_provider(
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Filter persisted messages to the provider-safe user/assistant form."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]

    @staticmethod
    def _clean_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
        """Filter untrusted client history to safe user/assistant turns."""
        cleaned: list[dict[str, str]] = []
        for entry in history[-MAX_HISTORY_TURNS:]:
            if not isinstance(entry, dict):
                continue
            role = entry.get("role")
            content = entry.get("content")
            if role not in ("user", "assistant") or not isinstance(content, str):
                continue
            cleaned.append({"role": role, "content": content.strip()[:MAX_HISTORY_CHARS]})
        return cleaned


def _safe_stream_iter(
    provider: StreamCapableProvider,
    messages: list[dict[str, object]],
    tool_defs: list[dict[str, object]],
) -> Iterator[StreamEvent]:
    """Call ``generate_stream`` and normalize synchronous setup failures.

    A provider may raise :class:`AIProviderError` while *creating* the
    generator (e.g. a missing SDK); wrapping keeps the pump thread delivering
    the error as a queue item instead of losing it.
    """
    try:
        return provider.generate_stream(
            messages,
            tool_defs,
            settings.AI_MAX_OUTPUT_TOKENS,
            settings.AI_TIMEOUT_SECONDS,
        )
    except AIProviderError as exc:
        return cast("Iterator[StreamEvent]", iter([exc]))


