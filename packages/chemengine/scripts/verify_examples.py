"""Execute every example under examples/ and fail if any script fails (M32).

Used by CI (Phase 15.3 gate) and the release checklist:

    python scripts/verify_examples.py

Each example runs in a fresh subprocess with a timeout; a nonzero exit
code, a timeout, or output ending in a traceback fails the verification.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
TIMEOUT_SECONDS = 120


def main() -> int:
    scripts = sorted(EXAMPLES_DIR.glob("*.py"))
    if len(scripts) < 10:
        print(f"::error::expected 10+ examples, found {len(scripts)}")
        return 1

    failures: list[tuple[str, str]] = []
    for script in scripts:
        start = time.monotonic()
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(EXAMPLES_DIR),
            timeout=TIMEOUT_SECONDS,
        )
        elapsed = time.monotonic() - start
        status = "ok" if proc.returncode == 0 else "FAIL"
        print(f"[{status:>4}] {script.name} ({elapsed:.1f}s)")
        if proc.returncode != 0:
            tail = "\n".join(proc.stdout.strip().splitlines()[-5:] + proc.stderr.strip().splitlines()[-10:])
            print(tail)
            failures.append((script.name, tail))

    print(f"\n{len(scripts) - len(failures)}/{len(scripts)} examples passed")
    if failures:
        for name, _ in failures:
            print(f"::error::example failed: {name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
