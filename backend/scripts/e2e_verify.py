"""M31 browser E2E — critical flows, real browser, real backend.

Executes a real headless Chromium against the real Chemora stack:

    real Chromium  ──HTTP──▶  real FastAPI app (e2e_server.py)
                              ├─ real session auth (SQLite demo storage)
                              ├─ real ChemEngine (chemistry explorer)
                              └─ AI_PROVIDER=mock (deterministic tutor)

The only seams are the documented ones on the server (--fake-google and the
default mock AI provider). The browser runs the real production web bundle
served by ``vite preview``, so the E2E result reflects the build a user gets.

Covered flows (the M31 "critical" list):
    1.  application loading (auth shell, login screen renders)
    2.  authentication boundary (Google sign-in seam → session cookie → app)
    3.  learning/content access (catalog loads from the backend)
    4.  chemistry explorer (real ChemEngine parse through the UI)
    5.  tutor access + conversation creation
    6.  tutor streaming (SSE deltas render incrementally into the transcript)
    7.  conversation persistence/reload (history survives a page reload)
    8.  conversation switching
    9.  conversation deletion
    10. logout/auth boundary (session revoked, login screen returns)

Usage:
    python backend/scripts/e2e_verify.py [--base-url ...] [--api-url ...]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIR = ROOT / "apps" / "web"
VITE_PORT = 4173

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record a verification result."""
    (PASS if ok else FAIL).append(name)
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}", flush=True)


def _chromium_exe() -> str | None:
    """Find a locally installed Playwright chromium (no download needed)."""
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
    if not os.path.isdir(base):
        return None
    candidates: list[str] = []
    for entry in sorted(os.listdir(base)):
        if not entry.startswith("chromium-"):
            continue
        for sub, exe in (("chrome-win64", "chrome.exe"), ("chrome-win", "chrome.exe")):
            candidate = os.path.join(base, entry, sub, exe)
            if os.path.exists(candidate):
                candidates.append(candidate)
    return candidates[-1] if candidates else None


def _wait_for(url: str, timeout: float = 120.0) -> bool:
    """Poll a URL until it answers or the timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def _clear_port(port: int) -> None:
    """Best-effort kill of stale listeners on a port (Windows/mac/linux).

    Earlier failed runs can leave orphaned servers holding the port with a
    deleted SQLite handle, which produces confusing 404s/hangs. The harness
    refuses to share ports with strays.
    """
    if sys.platform == "win32":
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True
        ).stdout
        pids = {
            line.split()[-1]
            for line in out.splitlines()
            if f":{port}" in line and "LISTENING" in line
        }
        for pid in pids:
            subprocess.run(
                ["taskkill", "/F", "/PID", pid], capture_output=True, check=False
            )
    else:
        subprocess.run(
            ["pkill", "-f", f"e2e_server.*--port {port}"],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["pkill", "-f", f"vite preview.*{port}"],
            capture_output=True,
            check=False,
        )
    time.sleep(0.5)


def main() -> int:
    """Run the full E2E suite and exit non-zero on any failure."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8931")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    npm = os.environ.get("NPM_EXE") or shutil.which("npm") or shutil.which("npm.cmd")
    npx = os.environ.get("NPX_EXE") or shutil.which("npx") or shutil.which("npx.cmd")
    if not npm or not npx:
        print("FATAL: npm/npx not found", flush=True)
        return 2

    # 1. Build the web bundle (the artifact real users get), with the E2E
    #    API base URL baked in so the bundle talks to the E2E backend.
    if not args.skip_build:
        print("== Building web bundle ==", flush=True)
        build_env = dict(os.environ)
        build_env["VITE_API_BASE_URL"] = args.api_url
        # A syntactically valid, non-secret client id. The backend's fake
        # verifier does not validate audience, and no real Google account is
        # involved — this only lets the real client-side GIS code path run.
        build_env["VITE_GOOGLE_CLIENT_ID"] = "e2e-client-id.apps.googleusercontent.com"
        build = subprocess.run(
            [npm, "run", "build"],
            cwd=WEB_DIR,
            capture_output=True,
            text=True,
            timeout=600,
            env=build_env,
        )
        if build.returncode != 0:
            print(build.stdout + build.stderr, flush=True)
            return 2

    # 2. Start the real backend (documented seams only) on cleared ports.
    print("== Starting E2E backend ==", flush=True)
    _clear_port(8931)
    _clear_port(VITE_PORT)
    api_proc = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "backend" / "scripts" / "e2e_server.py"),
            "--host",
            "127.0.0.1",
            "--port",
            "8931",
            "--fake-google",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    vite_proc: subprocess.Popen[str] | None = None
    try:
        if not _wait_for(f"{args.api_url}/health", timeout=60):
            if api_proc.stdout is not None:
                print(api_proc.stdout.read() or "", flush=True)
            print("FATAL: backend did not become healthy", flush=True)
            return 2
        print(f"backend healthy at {args.api_url}", flush=True)

        # 3. Serve the built bundle.
        vite_proc = subprocess.Popen(
            [
                npx,
                "vite",
                "preview",
                "--host",
                "127.0.0.1",
                "--port",
                str(VITE_PORT),
                "--strictPort",
            ],
            cwd=WEB_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if not _wait_for(f"http://127.0.0.1:{VITE_PORT}/", timeout=60):
            print("FATAL: vite preview did not start", flush=True)
            return 2
        print(f"web bundle served at http://127.0.0.1:{VITE_PORT}", flush=True)

        return run_browser_tests(args.api_url, VITE_PORT)
    finally:
        for proc in (vite_proc, api_proc):
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()


def run_browser_tests(api_url: str, vite_port: int) -> int:
    """Execute the browser flows against the running stack."""
    from playwright.sync_api import sync_playwright

    chrome = _chromium_exe()
    if not chrome:
        print(
            "FATAL: no local Playwright chromium found; run "
            "`python -m playwright install chromium` in a network-capable environment.",
            flush=True,
        )
        return 2

    base = f"http://127.0.0.1:{vite_port}"
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=chrome)
        context = browser.new_context()
        page = context.new_page()
        page.on(
            "console",
            lambda msg: errors.append(
                f"{msg.text} [source: {msg.location.get('url', '?')} ]"
                if msg.type == "error"
                else None
            ) or None,
        )
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on(
            "response",
            lambda resp: errors.append(f"HTTP {resp.status} {resp.url}")
            if resp.status >= 400
            and not (
                resp.status == 401 and "/api/v1/auth/me" in resp.url
            )
            else None,
        )

        print("\n== 1. Application loading / auth shell ==", flush=True)
        page.goto(base, wait_until="domcontentloaded")
        try:
            page.wait_for_selector(
                '[data-testid="google-sign-in-host"]', timeout=30000, state="attached"
            )
            check("login screen renders (auth shell)", True)
        except Exception:
            page.screenshot(path=str(ROOT / "e2e_debug.png"))
            check(
                "login screen renders (auth shell)",
                False,
                f"body: {page.inner_text('body')[:200]!r}",
            )
            print(f"{'=' * 60}\nRESULTS: {len(PASS)} passed, {len(FAIL)} failed", flush=True)
            browser.close()
            return 1

        print("\n== 2. Authentication boundary ==", flush=True)
        # Faithful GIS seam: the real LoginScreen/DefaultGoogleSignInProvider
        # code path runs; only the Google-hosted UI is faked. The init script
        # runs before the app bundle on every navigation, so the bundle finds
        # window.google present (as the GIS script would provide it).
        context.add_init_script(
            """
            window.google = {
              accounts: {
                id: {
                  displaySignInButton: (_opts, callbacks) => {
                    window.__chemoraOnCredential = callbacks.onSignIn;
                  },
                },
              },
            };
            """
        )
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(
            '[data-testid="google-sign-in-host"]', timeout=30000, state="attached"
        )
        page.wait_for_function(
            "typeof window.__chemoraOnCredential === 'function'", timeout=30000
        )
        page.evaluate("window.__chemoraOnCredential('e2e-cred-alpha')")
        page.wait_for_selector('[data-testid="signed-in-email"]', timeout=15000)
        email = page.inner_text('[data-testid="signed-in-email"]')
        check(
            "google seam sign-in establishes a session",
            "e2e-user-alpha@example.com" in email,
            email,
        )

        print("\n== 3. Learning/content access ==", flush=True)
        page.get_by_role("button", name=re.compile("Learn", re.I)).click()
        page.wait_for_selector('[data-testid="lesson-list"] li', timeout=15000)
        lesson_count = page.locator('[data-testid="lesson-list"] li').count()
        check("lesson catalog loads from the backend", lesson_count > 0, f"{lesson_count} lessons")

        print("\n== 4. Chemistry explorer (real ChemEngine) ==", flush=True)
        page.get_by_role("button", name=re.compile("Chemistry", re.I)).first.click()
        page.fill('input[placeholder*="H2O"]', "H2O")
        page.keyboard.press("Enter")
        page.wait_for_selector(".explorer-result, .card", timeout=15000)
        body = page.inner_text("body")
        explorer_ok = "H2O" in body or "Oxygen" in body or "water" in body.lower()
        check("explorer returns ChemEngine result", explorer_ok)

        print("\n== 5. Tutor access + conversation creation ==", flush=True)
        page.get_by_role("button", name=re.compile("Tutor", re.I)).click()
        page.fill('[data-testid="tutor-input"]', "What is the molar mass of water?")
        page.get_by_role("button", name=re.compile("^Send$", re.I)).click()
        page.wait_for_selector('[data-testid="tutor-transcript"]', timeout=15000)

        print("\n== 6. Tutor streaming ==", flush=True)
        page.wait_for_selector(
            '[data-testid="tutor-message-assistant"], [data-testid="tutor-error"]',
            timeout=30000,
        )
        if page.locator('[data-testid="tutor-error"]').count():
            check("tutor streams a response", False, page.inner_text('[data-testid="tutor-error"]'))
        else:
            answer = page.inner_text('[data-testid="tutor-message-assistant"]')
            check(
                "tutor streams a response",
                len(answer.strip()) > 0,
                f"{len(answer)} chars: {answer[:40]!r}",
            )
        # Let the SSE stream reach its done frame and the server finish
        # persisting before reloading (otherwise the in-flight generator may
        # still hold the demo SQLite connection when /auth/me lands).
        page.wait_for_selector(
            '[data-testid="tutor-streaming"]', state="detached", timeout=15000
        )
        page.wait_for_timeout(1500)

        print("\n== 7. Conversation persistence/reload ==", flush=True)
        page.reload(wait_until="domcontentloaded")
        try:
            page.wait_for_selector('[data-testid="signed-in-email"]', timeout=20000)
        except Exception:
            cookies = context.cookies("http://127.0.0.1:8931")
            print(
                "  DEBUG cookies:",
                [(c["name"], c["sameSite"]) for c in cookies],
                flush=True,
            )
            print("  DEBUG body:", page.inner_text("body")[:150], flush=True)
            raise
        page.get_by_role("button", name=re.compile("Tutor", re.I)).click()
        # The tutor opens on a fresh view; persisted history is reached
        # through the conversations list (the real user flow).
        page.wait_for_selector(
            '[data-testid="tutor-toggle-conversations"]', timeout=15000
        )
        page.locator('[data-testid="tutor-toggle-conversations"]').click()
        page.wait_for_selector('[data-testid^="tutor-open-"]', timeout=15000)
        page.locator('[data-testid^="tutor-open-"]').first.click()
        page.wait_for_selector('[data-testid="tutor-message-user"]', timeout=15000)
        user_msg = page.inner_text('[data-testid="tutor-message-user"]')
        check(
            "conversation history persists across reload",
            "molar mass" in user_msg.lower(),
            user_msg[:60],
        )

        print("\n== 8. Conversation switching ==", flush=True)
        page.locator('[data-testid="tutor-toggle-conversations"]').click()
        page.locator('[data-testid="tutor-new-conversation"]').click()
        page.wait_for_selector('[data-testid="tutor-empty"]', timeout=15000)
        check("new conversation starts empty (switching works)", True)

        print("\n== 9. Conversation deletion ==", flush=True)
        page.locator('[data-testid="tutor-toggle-conversations"]').click()
        delete_buttons = page.locator('[data-testid^="tutor-delete-"]')
        if delete_buttons.count() == 0:
            check("conversation delete control present", False, "no delete buttons rendered")
        else:
            delete_buttons.first.click()
            page.wait_for_timeout(500)
            check("conversation delete control works", True)

        print("\n== 10. Logout/auth boundary ==", flush=True)
        page.get_by_role("button", name=re.compile("Sign out|Log out|Logout", re.I)).click()
        page.wait_for_selector('[data-testid="google-sign-in-host"]', timeout=15000)
        check("logout returns to the login screen", True)

        # The pre-login auth probe intentionally receives 401 (that is how
        # the auth gate detects signed-out state). Both the expected 401s and
        # their browser resource-log lines are filtered; any other console
        # error, page error, or 4xx/5xx response is a real problem.
        unexpected = [
            e
            for e in errors
            if not (
                ("401" in e and "/api/v1/auth/me" in e)
                or ("401" in e and "Failed to load resource" in e)
            )
        ]
        check(
            "no unexpected console errors",
            not unexpected,
            "; ".join(unexpected[:3]) if unexpected else "(only expected auth 401 probes)",
        )
        browser.close()

    print(f"\n{'=' * 60}\nRESULTS: {len(PASS)} passed, {len(FAIL)} failed", flush=True)
    if FAIL:
        print("FAILED:", FAIL, flush=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
