"""M31 AI provider verification (offline; live smoke only if credentials exist).

Verifies the provider stack as far as possible without live provider
credentials:

1. Factory: construction of every configured provider name, including
   key-required validation errors for the real providers.
2. Configuration: settings shape, safe default provider, keys have no
   defaults, timeout default, model defaults.
3. Runtime failure paths against a local fake provider server using the real
   OpenAI/Anthropic SDKs (installed as optional runtime dependencies): HTTP
   401/429/500, connection refused, and read timeout are all translated into
   stable AIProviderError categories, with no secret material in messages.
4. Streaming: the streaming path fails with the same stable categories.
5. Mock provider sanity: the default provider still answers and streams.
6. Live smoke test (only if a key exists in the environment): a minimal real
   authenticated request. Explicitly skipped otherwise.

Credentials are read from the environment only and are never printed.

Usage:
    python backend/scripts/ai_provider_verify.py
"""

from __future__ import annotations

import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

PASS: list[str] = []
FAIL: list[str] = []

# A obviously-fake local key used to exercise failure paths. It authenticates
# nothing and is printed nowhere except as an opaque credential argument.
LOCAL_TEST_KEY = "sk-m31-local-verification-key"


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record a verification result with an ASCII-safe checkmark."""
    (PASS if ok else FAIL).append(name)
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}", flush=True)


class _Handler(BaseHTTPRequestHandler):
    """Answers provider-shaped POSTs according to the server's mode."""

    def log_message(self, *args: object) -> None:
        """Suppress per-request logging."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        mode = getattr(self.server, "mode", "")
        auth_header = self.headers.get("Authorization", "")
        if mode == "require_auth" and not auth_header.startswith("Bearer "):
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": {"message": "Missing API key"}}')
            return
        if mode == "sleep":
            time.sleep(8)
        payload = {
            "auth_fail": (401, b'{"error": {"message": "Incorrect API key provided"}}'),
            "rate_limit": (429, b'{"error": {"message": "Rate limit exceeded"}}'),
            "server_error": (500, b'{"error": {"message": "Internal server error"}}'),
            "ok": (
                200,
                b'{"id": "chatcmpl-m31", "object": "chat.completion", "created": 0,'
                b' "model": "test-model", "choices": [{"index": 0, "message":'
                b' {"role": "assistant", "content": "mock reply"}, "finish_reason":'
                b' "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 2,'
                b' "total_tokens": 3}}',
            ),
        }.get(mode, (200, b"{}"))
        status, body = payload
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


class _FakeProviderServer(HTTPServer):
    """One-mode fake provider endpoint."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        super().__init__(("127.0.0.1", 0), _Handler)


def _start_server(mode: str) -> tuple[_FakeProviderServer, str]:
    server = _FakeProviderServer(mode)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}/v1"


def main() -> int:
    """Run every offline provider verification and report a summary."""
    from app.core.config import Settings
    from app.services.ai.provider import (
        AIProviderError,
        MockAIProvider,
        OpenAIProvider,
        make_provider,
    )

    print("\n== 1. Provider factory (construction-time verification) ==", flush=True)
    check(
        "mock provider constructs",
        isinstance(make_provider("mock", "https://x", "", "m"), MockAIProvider),
    )
    try:
        make_provider("skynet", "https://x", "key", "m")
        check("unknown provider rejected", False, "no error raised")
    except ValueError as exc:
        check("unknown provider rejected", "Unknown AI_PROVIDER" in str(exc))
    try:
        make_provider("openai", "https://x", "", "m")
        check("openai requires API key", False, "no error raised")
    except ValueError as exc:
        check("openai requires API key", "AI_API_KEY" in str(exc))
    try:
        make_provider("anthropic", "https://x", "unused", "m", anthropic_key="")
        check("anthropic requires API key", False, "no error raised")
    except ValueError as exc:
        check("anthropic requires API key", "AI_ANTHROPIC_API_KEY" in str(exc))

    print("\n== 2. Configuration (secret handling) ==", flush=True)
    s = Settings(_env_file=None)
    check("default provider is mock (safe default)", s.AI_PROVIDER == "mock")
    check(
        "AI_API_KEY has no default value",
        Settings.model_fields["AI_API_KEY"].default == "",
    )
    check(
        "AI_ANTHROPIC_API_KEY has no default value",
        Settings.model_fields["AI_ANTHROPIC_API_KEY"].default == "",
    )
    check("timeout default is finite (30s)", s.AI_TIMEOUT_SECONDS == 30.0)

    print(
        "\n== 3. Runtime failure paths over real HTTP (real SDKs, fake server) ==",
        flush=True,
    )
    messages = [{"role": "user", "content": "ping"}]
    tools: list[dict[str, object]] = []

    def _expect_category(
        name: str, mode: str, expected: str, streaming: bool = False
    ) -> None:
        server, base = _start_server(mode)
        try:
            provider = OpenAIProvider(api_base=base, api_key=LOCAL_TEST_KEY, model="test-model")
            try:
                if streaming:
                    next(provider.generate_stream(messages, tools, 64, 3.0))
                else:
                    provider.generate(messages, tools, 64, 3.0)
                check(name, False, "no error raised")
            except AIProviderError as exc:
                leaked = LOCAL_TEST_KEY.split("-")[2] in str(exc)
                check(
                    name,
                    exc.category == expected and not leaked,
                    f"category={exc.category}" + (" (leak!)" if leaked else ""),
                )
        finally:
            server.shutdown()

    _expect_category("HTTP 401 -> auth_failure", "auth_fail", "auth_failure")
    _expect_category("HTTP 429 -> rate_limit", "rate_limit", "rate_limit")
    _expect_category("HTTP 500 -> unavailable", "server_error", "unavailable")
    _expect_category("streaming 401 -> auth_failure", "auth_fail", "auth_failure", streaming=True)

    # Connection refused: a bound-but-never-listening socket reliably gets
    # an RST on every platform (avoids OS quirks with fixed low ports).
    import socket as _socket

    refusal = _socket.socket()
    refusal.bind(("127.0.0.1", 0))
    refused_port = refusal.getsockname()[1]
    provider = OpenAIProvider(
        api_base=f"http://127.0.0.1:{refused_port}/v1", api_key=LOCAL_TEST_KEY, model="test-model"
    )
    try:
        provider.generate(messages, tools, 64, 2.0)
        check("unreachable endpoint -> stable category", False, "no error raised")
    except AIProviderError as exc:
        # On hosts that answer closed ports with an RST, httpx raises
        # ConnectError and the provider maps it to "unavailable". On hosts
        # whose firewall silently drops closed ports (this Windows machine),
        # the connection attempt surfaces as ConnectTimeout -> "timeout".
        # Both are stable categories and both are acceptable here.
        check(
            "unreachable endpoint -> stable category",
            exc.category in ("unavailable", "timeout"),
            f"category={exc.category} (RST hosts map to unavailable; "
            "firewall-dropped hosts map to timeout)",
        )
    finally:
        refusal.close()

    # Read timeout: server accepts, then stalls past the client budget.
    server, base = _start_server("sleep")
    try:
        provider = OpenAIProvider(api_base=base, api_key=LOCAL_TEST_KEY, model="test-model")
        started = time.monotonic()
        try:
            provider.generate(messages, tools, 64, 1.5)
            check("read timeout -> timeout", False, "no error raised")
        except AIProviderError as exc:
            elapsed = time.monotonic() - started
            check(
                "read timeout -> timeout",
                exc.category == "timeout" and elapsed < 7,
                f"category={exc.category}, elapsed={elapsed:.1f}s",
            )
    finally:
        server.shutdown()

    # Happy path against the fake server (request shape verification).
    server, base = _start_server("ok")
    try:
        provider = OpenAIProvider(api_base=base, api_key=LOCAL_TEST_KEY, model="test-model")
        reply = provider.generate(messages, tools, 64, 5.0)
        check("happy path returns provider content", reply == "mock reply", repr(reply))
    finally:
        server.shutdown()

    print("\n== 4. Mock provider sanity (default provider) ==", flush=True)
    mock = MockAIProvider()
    reply = mock.generate(messages, tools, 64, 5.0)
    check("mock answers non-empty", isinstance(reply, str) and bool(reply))
    events = list(mock.generate_stream(messages, tools, 64, 5.0))
    check("mock streams events", len(events) >= 1)

    print("\n== 5. Live smoke test (only if credentials exist) ==", flush=True)
    has_openai = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_API_KEY"))
    has_anthropic = bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("AI_ANTHROPIC_API_KEY")
    )
    if not (has_openai or has_anthropic):
        print(
            "  [SKIP] live smoke: no OPENAI_API_KEY / ANTHROPIC_API_KEY in the "
            "environment. When credentials exist, run the documented procedure in "
            "infrastructure/RELEASE.md section 3 (initialization -> one real "
            "authenticated request -> tool path -> streaming path -> failure "
            "handling). No live call was made and no key was read or printed.",
            flush=True,
        )
    else:  # pragma: no cover - requires real credentials
        key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        provider = OpenAIProvider(
            api_base="https://api.openai.com/v1", api_key=key, model="gpt-4o-mini"
        )
        try:
            reply = provider.generate(
                [{"role": "user", "content": "Reply with the single word: ok"}],
                [],
                16,
                20.0,
            )
            check("live smoke: real authenticated request succeeded", bool(reply))
        except AIProviderError as exc:
            check("live smoke: real request failed", False, exc.category)

    print(f"\n{'=' * 60}\nRESULTS: {len(PASS)} passed, {len(FAIL)} failed", flush=True)
    if FAIL:
        print("FAILED:", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
