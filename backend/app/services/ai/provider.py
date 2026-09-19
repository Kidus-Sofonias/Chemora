"""AI provider abstraction (M29).

The application depends on the :class:`AIProvider` abstraction, never on a
concrete SDK. Two implementations ship with the project:

* :class:`MockAIProvider` — in-process, deterministic, no network. Used for
  automated tests and as the default development configuration (``AI_PROVIDER
  = "mock"``). It is **not** a substitute for a real LLM.
* :class:`OpenAIProvider` — routes completions through an OpenAI-compatible
  HTTP API. Requires ``AI_API_KEY`` and is the production provider.
* :class:`AnthropicProvider` — routes completions through the Anthropic
  Messages API. Requires ``AI_ANTHROPIC_API_KEY``.

Provider secrets (API keys) are read only from server-side settings and are
never logged or returned to clients.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Stable error categories returned to callers/clients. These never carry raw
# provider exceptions or credentials.
TIMEOUT = "timeout"
RATE_LIMIT = "rate_limit"
AUTH_FAILURE = "auth_failure"
UNAVAILABLE = "unavailable"
PROVIDER_ERROR = "provider_error"
BAD_REQUEST = "bad_request"


class AIProviderError(Exception):
    """Stable, client-safe AI provider error.

    Attributes:
        category: One of the stable category constants above.
        message: A user-facing message without internal details.
    """

    CATEGORIES = (TIMEOUT, RATE_LIMIT, AUTH_FAILURE, UNAVAILABLE, PROVIDER_ERROR, BAD_REQUEST)

    def __init__(self, category: str, message: str) -> None:
        """Initialize with a stable category and user-facing message."""
        if category not in self.CATEGORIES:
            raise ValueError(f"Unknown AI provider error category: {category}")
        super().__init__(f"[ai:{category}] {message}")
        self.category = category
        self.message = message


@dataclass(slots=True)
class StreamEvent:
    """One event from a provider's streaming completion.

    Kinds:
        "text": ``payload`` is a str chunk of the assistant's answer.
        "tool_calls": ``payload`` is the OpenAI-shape tool_calls dict — the
            turn requested tools; no more text will follow for this turn.
        "final": ``payload`` is the full accumulated answer text for this
            turn (always emitted last, exactly once).
    """

    kind: str
    payload: Any  # noqa: ANN401


@runtime_checkable
class AIProvider(Protocol):
    """Minimal provider contract for the chemistry tutor.

    ``generate`` is required. ``generate_stream`` is optional: when a
    provider implements it, the tutor streams the answer to the client
    incrementally (M30); otherwise the tutor falls back to ``generate``
    and emits the answer as a single chunk.
    """

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> Any:  # noqa: ANN401
        """Return a chat completion (text or structured tool calls)."""
        ...


class StreamCapableProvider(Protocol):
    """Structural type for providers that also support streaming (M30).

    Every shipped provider implements ``generate_stream``; the tutor checks
    for it so third-party providers without streaming still work through the
    non-streaming path.
    """

    def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> Iterator[StreamEvent]:
        """Yield incremental :class:`StreamEvent` items for one turn."""
        ...


class MockAIProvider:
    """In-process provider used for tests and local development.

    This never calls any external service. It returns a deterministic,
    clearly-labeled response so the full backend wiring (auth → retrieval →
    tool loop → provider) is exercised in automated tests without a real LLM.
    """

    def __init__(self) -> None:
        """Initialize the mock provider."""
        self.last_messages: list[dict[str, Any]] = []
        self.last_tools: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> str:
        """Return a deterministic placeholder response.

        Records what it was called with and never makes tool calls itself.
        """
        self.last_messages = list(messages)
        self.last_tools = list(tools)
        return (
            "[MockAI] I'd be happy to help as your chemistry tutor. This is a "
            "deterministic placeholder response; configure AI_PROVIDER=openai "
            "for a real model."
        )

    def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> Iterator[StreamEvent]:
        """Stream the deterministic placeholder response in fixed chunks.

        Mirrors :meth:`generate` (records the call, never requests tools) so
        the streaming path is fully testable without any external service.
        """
        text = self.generate(messages, tools, max_output_tokens, timeout_seconds)
        chunk_size = 24
        for i in range(0, len(text), chunk_size):
            yield StreamEvent("text", text[i : i + chunk_size])
        yield StreamEvent("final", text)

def make_provider(
    provider_name: str,
    api_base: str,
    api_key: str,
    model: str,
    *,
    anthropic_base: str = "",
    anthropic_key: str = "",
    anthropic_model: str = "",
) -> AIProvider:
    """Factory: select an AIProvider implementation by configured name.

    Args:
        provider_name: ``"mock"``, ``"openai"``, or ``"anthropic"``.
        api_base: OpenAI-compatible endpoint base URL.
        api_key: Server-side API key (never logged).
        model: Model name.
        anthropic_base: Anthropic API base URL.
        anthropic_key: Server-side Anthropic API key (never logged).
        anthropic_model: Anthropic model name.

    Returns:
        An :class:`AIProvider` instance.

    Raises:
        ValueError: If the provider name is unknown or a real provider is
            selected without its API key.
    """
    if provider_name == "mock":
        return MockAIProvider()
    if provider_name == "openai":
        if not api_key:
            raise ValueError("AI_API_KEY must be set when AI_PROVIDER=openai")
        return OpenAIProvider(api_base=api_base, api_key=api_key, model=model)
    if provider_name == "anthropic":
        if not anthropic_key:
            raise ValueError("AI_ANTHROPIC_API_KEY must be set when AI_PROVIDER=anthropic")
        return AnthropicProvider(
            api_base=anthropic_base, api_key=anthropic_key, model=anthropic_model
        )
    raise ValueError(f"Unknown AI_PROVIDER: {provider_name}")

class OpenAIProvider:
    """OpenAI-compatible provider (also works with compatible endpoints).

    Reads its API key and endpoint from server-side settings only. The key is
    held in memory for the lifetime of the instance and is never logged or
    serialized. The HTTP client is created per call and closed deterministically
    (the tutor runs behind asyncio.to_thread, so a sync client is correct).
    """

    def __init__(self, api_base: str, api_key: str, model: str) -> None:
        """Initialize with a server-side base URL, key, and model name."""
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._api_key = api_key

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> Any:  # noqa: ANN401
        """Call the OpenAI-compatible chat completions endpoint.

        Imports the HTTP client lazily so the dependency is only required when
        a real provider is actually configured.

        Raises:
            AIProviderError: With a stable category on any failure.
        """
        try:
            import httpx
            from openai import (
                APITimeoutError,
                AuthenticationError,
                OpenAI,
                OpenAIError,
                RateLimitError,
            )
        except ImportError as exc:  # pragma: no cover - only with real provider
            raise AIProviderError(
                PROVIDER_ERROR,
                "OpenAI provider support is not installed. Install the 'openai' "
                "package or set AI_PROVIDER=mock.",
            ) from exc

        try:
            with httpx.Client(
                base_url=self._api_base,
                timeout=httpx.Timeout(timeout_seconds, read=timeout_seconds),
            ) as http_client:
                client = OpenAI(
                    base_url=self._api_base,
                    api_key=self._api_key,
                    http_client=http_client,
                    max_retries=0,
                )
                response = client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=tools or None,
                    max_tokens=max_output_tokens,
                    timeout=timeout_seconds,
                )
        except (httpx.TimeoutException, APITimeoutError) as exc:
            raise AIProviderError(TIMEOUT, "The tutoring service took too long.") from exc
        except AuthenticationError:
            logger.warning("OpenAI authentication failed")
            raise AIProviderError(
                AUTH_FAILURE, "The tutoring service is misconfigured."
            ) from None
        except RateLimitError:
            raise AIProviderError(
                RATE_LIMIT, "The tutoring service is busy. Please try again shortly."
            ) from None
        except (OpenAIError, httpx.HTTPError) as exc:
            logger.warning("OpenAI provider error: %s", type(exc).__name__)
            raise AIProviderError(
                UNAVAILABLE, "The tutoring service is unavailable."
            ) from None

        try:
            choice = response.choices[0]
            message = choice.message
            if getattr(message, "tool_calls", None):
                # Returned to the orchestration layer for tool execution.
                return {"tool_calls": [tc.model_dump() for tc in message.tool_calls]}
            return message.content or ""
        except (IndexError, AttributeError):
            raise AIProviderError(
                PROVIDER_ERROR,
                "The tutoring service returned an unexpected response.",
            ) from None

    def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> Iterator[StreamEvent]:
        """Stream the completion as incremental :class:`StreamEvent` items.

        Emits ``text`` events for content chunks, a single ``tool_calls``
        event when the turn requests tools, and a ``final`` event with the
        accumulated answer at the end.
        """
        try:
            import httpx
            from openai import (
                APITimeoutError,
                AuthenticationError,
                OpenAI,
                OpenAIError,
                RateLimitError,
            )
        except ImportError as exc:  # pragma: no cover - only with real provider
            raise AIProviderError(
                PROVIDER_ERROR,
                "OpenAI provider support is not installed. Install the 'openai' "
                "package or set AI_PROVIDER=mock.",
            ) from exc

        try:
            with httpx.Client(
                base_url=self._api_base,
                timeout=httpx.Timeout(timeout_seconds, read=timeout_seconds),
            ) as http_client:
                client = OpenAI(
                    base_url=self._api_base,
                    api_key=self._api_key,
                    http_client=http_client,
                    max_retries=0,
                )
                stream = client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=tools or None,
                    max_tokens=max_output_tokens,
                    timeout=timeout_seconds,
                    stream=True,
                )
                collected_tool_calls: dict[int, dict[str, Any]] = {}
                accumulated: list[str] = []
                for chunk in stream:
                    if not getattr(chunk, "choices", None):
                        continue
                    delta = chunk.choices[0].delta
                    for tc in getattr(delta, "tool_calls", None) or []:
                        slot = collected_tool_calls.setdefault(
                            tc.index,
                            {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        if getattr(tc, "id", None):
                            slot["id"] = tc.id
                        if getattr(tc.function, "name", None):
                            slot["function"]["name"] = tc.function.name
                        if getattr(tc.function, "arguments", None):
                            slot["function"]["arguments"] += tc.function.arguments
                    content = getattr(delta, "content", None)
                    if content:
                        accumulated.append(content)
                        yield StreamEvent("text", content)
                if collected_tool_calls:
                    ordered = [
                        collected_tool_calls[i]
                        for i in sorted(collected_tool_calls)
                    ]
                    yield StreamEvent("tool_calls", {"tool_calls": ordered})
                    return
                yield StreamEvent("final", "".join(accumulated))
        except (httpx.TimeoutException, APITimeoutError) as exc:
            raise AIProviderError(TIMEOUT, "The tutoring service took too long.") from exc
        except AuthenticationError:
            logger.warning("OpenAI authentication failed")
            raise AIProviderError(
                AUTH_FAILURE, "The tutoring service is misconfigured."
            ) from None
        except RateLimitError:
            raise AIProviderError(
                RATE_LIMIT, "The tutoring service is busy. Please try again shortly."
            ) from None
        except (OpenAIError, httpx.HTTPError) as exc:
            logger.warning("OpenAI provider error: %s", type(exc).__name__)
            raise AIProviderError(
                UNAVAILABLE, "The tutoring service is unavailable."
            ) from None


class AnthropicProvider:
    """Anthropic Messages-API provider.

    Same contract as :class:`OpenAIProvider`: the OpenAI-style message/tool-call
    shapes produced by the tutor loop are translated to Anthropic's format
    here, so the orchestration layer stays provider-agnostic. The API key is
    held in memory only and is never logged or serialized.
    """

    def __init__(self, api_base: str, api_key: str, model: str) -> None:
        """Initialize with a server-side base URL, key, and model name."""
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._api_key = api_key

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> Any:  # noqa: ANN401
        """Call the Anthropic Messages API.

        Raises:
            AIProviderError: With a stable category on any failure.
        """
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - only with real provider
            raise AIProviderError(
                PROVIDER_ERROR,
                "Anthropic provider support is not installed. Install the "
                "'anthropic' package or set AI_PROVIDER=mock.",
            ) from exc

        system_text, turns = _to_anthropic_messages(messages)
        try:
            with anthropic.Anthropic(
                api_key=self._api_key,
                base_url=self._api_base or None,
                timeout=timeout_seconds,
                max_retries=0,
            ) as client:
                response = client.messages.create(
                    model=self._model,
                    max_tokens=max_output_tokens,
                    system=system_text,
                    messages=turns,
                    tools=tools or anthropic.NOT_GIVEN,
                )
        except (TimeoutError, anthropic.APITimeoutError) as exc:
            raise AIProviderError(TIMEOUT, "The tutoring service took too long.") from exc
        except anthropic.AuthenticationError:
            logger.warning("Anthropic authentication failed")
            raise AIProviderError(
                AUTH_FAILURE, "The tutoring service is misconfigured."
            ) from None
        except anthropic.RateLimitError:
            raise AIProviderError(
                RATE_LIMIT, "The tutoring service is busy. Please try again shortly."
            ) from None
        except anthropic.APIError as exc:
            logger.warning("Anthropic provider error: %s", type(exc).__name__)
            raise AIProviderError(
                UNAVAILABLE, "The tutoring service is unavailable."
            ) from None

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        try:
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    # Re-expressed in the OpenAI function-call shape so the
                    # orchestration layer can stay provider-agnostic.
                    tool_calls.append(
                        {
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": json.dumps(block.input),
                            },
                        }
                    )
        except AttributeError:
            raise AIProviderError(
                PROVIDER_ERROR,
                "The tutoring service returned an unexpected response.",
            ) from None
        if tool_calls:
            return {"tool_calls": tool_calls}
        return "".join(text_parts)

    def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> Iterator[StreamEvent]:
        """Stream the Anthropic Messages API response incrementally."""
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - only with real provider
            raise AIProviderError(
                PROVIDER_ERROR,
                "Anthropic provider support is not installed. Install the "
                "'anthropic' package or set AI_PROVIDER=mock.",
            ) from exc

        system_text, turns = _to_anthropic_messages(messages)
        collected_tools: list[dict[str, Any]] = []
        accumulated: list[str] = []
        try:
            with anthropic.Anthropic(
                api_key=self._api_key,
                base_url=self._api_base or None,
                timeout=timeout_seconds,
                max_retries=0,
            ) as client, client.messages.stream(
                model=self._model,
                max_tokens=max_output_tokens,
                system=system_text,
                messages=turns,
                tools=tools or anthropic.NOT_GIVEN,
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_start"
                        and event.content_block.type == "tool_use"
                    ):
                        collected_tools.append(
                            {
                                "id": event.content_block.id,
                                "type": "function",
                                "function": {
                                    "name": event.content_block.name,
                                    "arguments": "",
                                },
                            }
                        )
                    elif (
                        event.type == "content_block_delta"
                        and event.delta.type == "input_json_delta"
                    ):
                        collected_tools[-1]["function"]["arguments"] += (
                            event.delta.partial_json
                        )
                    elif (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                    ):
                        accumulated.append(event.delta.text)
                        yield StreamEvent("text", event.delta.text)
        except (TimeoutError, anthropic.APITimeoutError) as exc:
            raise AIProviderError(TIMEOUT, "The tutoring service took too long.") from exc
        except anthropic.AuthenticationError:
            logger.warning("Anthropic authentication failed")
            raise AIProviderError(
                AUTH_FAILURE, "The tutoring service is misconfigured."
            ) from None
        except anthropic.RateLimitError:
            raise AIProviderError(
                RATE_LIMIT, "The tutoring service is busy. Please try again shortly."
            ) from None
        except anthropic.APIError as exc:
            logger.warning("Anthropic provider error: %s", type(exc).__name__)
            raise AIProviderError(
                UNAVAILABLE, "The tutoring service is unavailable."
            ) from None
        if collected_tools:
            yield StreamEvent("tool_calls", {"tool_calls": collected_tools})
            return
        yield StreamEvent("final", "".join(accumulated))


def _to_anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Translate OpenAI-style tutor messages to the Anthropic format.

    System messages collapse into one system string; ``tool`` result messages
    become ``user`` turns with ``tool_result`` blocks; assistant tool-call
    messages become ``assistant`` turns with ``tool_use`` blocks. Consecutive
    same-role turns are merged (Anthropic requires strict alternation), and an
    assistant-first transcript gets a deterministic user lead-in.
    """
    system_parts: list[str] = []
    turns: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            if isinstance(content, str) and content:
                system_parts.append(content)
            continue
        if role == "tool":
            turns.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": str(message.get("tool_call_id", "")),
                            "content": str(content),
                        }
                    ],
                }
            )
            continue
        if role == "assistant" and isinstance(message.get("tool_calls"), list):
            blocks: list[dict[str, Any]] = []
            if isinstance(content, str) and content:
                blocks.append({"type": "text", "text": content})
            for call in message["tool_calls"]:
                function = call.get("function", {}) if isinstance(call, dict) else {}
                arguments = function.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments) if arguments.strip() else {}
                    except ValueError:
                        arguments = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": str(call.get("id", "")) if isinstance(call, dict) else "",
                        "name": str(function.get("name", "")),
                        "input": arguments if isinstance(arguments, dict) else {},
                    }
                )
            turns.append({"role": "assistant", "content": blocks})
            continue
        if role in ("user", "assistant") and isinstance(content, str) and content:
            turns.append({"role": role, "content": content})

    # Anthropic requires strictly alternating roles.
    merged: list[dict[str, Any]] = []
    for turn in turns:
        if merged and merged[-1]["role"] == turn["role"]:
            previous = merged[-1]["content"]
            current = turn["content"]
            if isinstance(previous, str) and isinstance(current, str):
                merged[-1]["content"] = f"{previous}\n\n{current}"
            else:
                previous_blocks = (
                    [{"type": "text", "text": previous}]
                    if isinstance(previous, str)
                    else list(previous)
                )
                current_blocks = (
                    [{"type": "text", "text": current}]
                    if isinstance(current, str)
                    else list(current)
                )
                merged[-1]["content"] = previous_blocks + current_blocks
            continue
        merged.append(turn)

    if merged and merged[0]["role"] == "assistant":
        merged.insert(0, {"role": "user", "content": "Continue the conversation."})
    return "\n\n".join(system_parts), merged


__all__ = [
    "AIProvider",
    "AIProviderError",
    "AnthropicProvider",
    "MockAIProvider",
    "OpenAIProvider",
    "StreamCapableProvider",
    "StreamEvent",
    "make_provider",
    "TIMEOUT",
    "RATE_LIMIT",
    "AUTH_FAILURE",
    "UNAVAILABLE",
    "PROVIDER_ERROR",
    "BAD_REQUEST",
]



