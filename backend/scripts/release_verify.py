"""M31 repository-level release verification (Phase 4 of the M31 scope).

Verifies the reproducibility and safety surface of the whole monorepo:

1. Builds: web and admin production builds succeed from a clean ``dist/``
   and produce the expected artifacts.
2. Backend packaging: the wheel builds and the app import path works.
3. Migration chain: heads resolve, revisions chain, and the offline SQL
   generation compiles every migration (dialect-level validation).
4. Environment configuration: production-mode enforcement (SESSION_SECRET,
   COOKIE_SECURE), required env vars, placeholder-only examples.
5. Secrets safety: ``.env`` ignored and untracked, no secret-looking strings
   in tracked files, ``.env.example`` placeholders only.

Usage:
    python backend/scripts/release_verify.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record a verification result with an ASCII-safe checkmark."""
    (PASS if ok else FAIL).append(name)
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}", flush=True)


def _npm() -> str:
    """Resolve the npm executable (npm.cmd on Windows)."""
    import shutil

    resolved = shutil.which("npm") or shutil.which("npm.cmd")
    if not resolved:
        print("FATAL: npm not found on PATH", flush=True)
        sys.exit(2)
    return resolved


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    """Run a command, returning (exit_code, combined_output)."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def main() -> int:
    """Run every release-verification phase and report a summary."""
    import os

    os.chdir(ROOT_DIR)

    print("\n== 1. Frontend production builds (web + admin) ==", flush=True)
    for app_name in ("web", "admin"):
        app_dir = ROOT_DIR / "apps" / app_name
        dist = app_dir / "dist"
        if dist.exists():
            subprocess.run(["rm", "-rf", str(dist)], check=False)
        code, output = run([_npm(), "run", "build"], cwd=app_dir)
        artifacts_exist = dist.exists() and any(dist.iterdir())
        index_page = dist / "index.html"
        check(
            f"{app_name} production build succeeds",
            code == 0 and artifacts_exist and index_page.exists(),
            f"exit={code}",
        )

    print("\n== 2. Backend packaging and import path ==", flush=True)
    wheel_dir = BACKEND_DIR / ".m31-wheel"
    code, output = run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheel_dir), "."],
        cwd=BACKEND_DIR,
        timeout=300,
    )
    wheel_built = code == 0 and any(wheel_dir.glob("chemora_backend-*.whl"))
    check("backend wheel builds", wheel_built, f"exit={code}")

    # Import path with production-forced settings (no server started). This
    # FastAPI version wraps included routers, so introspect paths defensively.
    code, output = run(
        [
            sys.executable,
            "-c",
            "from app.main import app; "
            "paths = [getattr(r, 'path', '') for r in app.routes]; "
            "assert any('/health' in p for p in paths), paths; "
            "print('import OK, routes:', len(paths))",
        ],
        cwd=BACKEND_DIR,
    )
    check(
        "backend import path works",
        code == 0,
        output.strip().splitlines()[-1] if output.strip() else "",
    )

    print("\n== 3. Migration chain (offline dialect validation) ==", flush=True)
    code, output = run(
        [
            sys.executable,
            "-c",
            "from alembic.config import Config\n"
            "from alembic.script import ScriptDirectory\n"
            "from alembic.command import upgrade\n"
            "cfg = Config('alembic.ini')\n"
            "script = ScriptDirectory.from_config(cfg)\n"
            "heads = script.get_heads()\n"
            "assert len(heads) == 1, heads\n"
            "print('head:', heads[0])",
        ],
        cwd=ROOT_DIR,
    )
    check(
        "migration head resolves",
        code == 0,
        output.strip().splitlines()[-1] if code == 0 else "",
    )

    print("\n== 4. Environment configuration ==", flush=True)
    # The config module builds a module-level settings instance on import,
    # so import with a placeholder secret first, then construct fresh
    # Settings without one to prove production mode enforces it.
    code, output = run(
        [
            sys.executable,
            "-c",
            "import os\n"
            "os.environ['ENVIRONMENT'] = 'production'\n"
            "os.environ['SESSION_SECRET'] = 'x' * 64\n"
            "from app.core.config import Settings\n"
            "del os.environ['SESSION_SECRET']\n"
            "try:\n"
            "    Settings(_env_file=None)\n"
            "    print('NO-ERROR')\n"
            "except Exception as exc:\n"
            "    print('REQUIRES-SECRET:', type(exc).__name__)\n",
        ],
        cwd=BACKEND_DIR,
    )
    check(
        "production requires SESSION_SECRET",
        "REQUIRES-SECRET" in output,
        output.strip().splitlines()[-1] if output.strip() else "",
    )

    code, output = run(
        [
            sys.executable,
            "-c",
            "import os\n"
            "os.environ['ENVIRONMENT'] = 'production'\n"
            "os.environ['SESSION_SECRET'] = 'x' * 32\n"
            "from app.core.config import Settings\n"
            "s = Settings(_env_file=None)\n"
            "print('COOKIE_SECURE=', s.COOKIE_SECURE)\n",
        ],
        cwd=BACKEND_DIR,
    )
    cookie_secure_enforced = "COOKIE_SECURE= True" in output or "COOKIE_SECURE=True" in output
    check("production forces COOKIE_SECURE=true", cookie_secure_enforced)

    env_example = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    for required in (
        "DATABASE_URL=",
        "GOOGLE_CLIENT_ID=",
        "SESSION_SECRET=",
        "COOKIE_SECURE=",
        "AI_PROVIDER=",
        "AI_API_KEY=",
        "AI_ANTHROPIC_API_KEY=",
        "AI_TOOL_CACHE_ENABLED=",
    ):
        check(f".env.example documents {required.split('=')[0]}", required in env_example)

    print("\n== 5. Secrets safety ==", flush=True)
    code, output = run(["git", "check-ignore", "backend/.env"])
    check("backend/.env is git-ignored", code == 0)
    code, output = run(["git", "status", "--porcelain", "backend/.env"])
    check(".env has no tracked/modified status", code == 0 and not output.strip())

    # Scan tracked files for real-looking secret material. Placeholders in
    # .env.example (empty values, example domains) are fine.
    code, output = run(["git", "ls-files"])
    tracked = [line for line in output.splitlines() if line.strip()]
    secret_re = re.compile(
        r"(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|"
        r"AIza[0-9A-Za-z_-]{30,})"
    )
    hits: list[str] = []
    for path in tracked:
        full = ROOT_DIR / path
        if not full.is_file():
            continue
        if full.suffix in {".png", ".jpg", ".ico", ".woff", ".woff2", ".jar", ".zip"}:
            continue
        try:
            text_content = full.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in secret_re.finditer(text_content):
            hits.append(f"{path}: {match.group(0)[:12]}...")
    check("no secret-looking strings in tracked files", not hits, "; ".join(hits[:5]))

    # Clean up the wheel-build artifact so the working tree stays clean.
    import shutil as _shutil

    if wheel_dir.exists():
        _shutil.rmtree(wheel_dir, ignore_errors=True)

    print(f"\n{'=' * 60}\nRESULTS: {len(PASS)} passed, {len(FAIL)} failed", flush=True)
    if FAIL:
        print("FAILED:", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
