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
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.ai.provider import AIProvider, AIProviderError, make_provider
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


