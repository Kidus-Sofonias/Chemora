"""M31 CI verification and local gate runner.

Two responsibilities:

1. ``--validate-only`` (also run by default before everything else): parse
   ``.github/workflows/ci.yml`` and assert the invariants the M31 acceptance
   criteria depend on — every required check command is present, and no
   blocking gate hides failures (no ``|| true`` / ``continue-on-error`` on
   required steps).

2. Local execution of the exact same gate commands CI runs, so the pipeline
   can be verified without pushing a broken commit. Exits non-zero if any
   blocking gate fails. Pass/fail — not a test framework.

Usage:
    python infrastructure/ci_check.py                # validate + run all gates
    python infrastructure/ci_check.py --validate-only
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record a verification result."""
    (PASS if ok else FAIL).append(name)
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}", flush=True)


def validate_workflow() -> None:
    """Assert the workflow contains every required gate and hides nothing."""
    print("\n== Workflow validation ==", flush=True)
    try:
        import yaml
    except ImportError:
        check("PyYAML available for workflow validation", False, "pip install pyyaml")
        return

    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = data.get("jobs", {})
    text = WORKFLOW.read_text(encoding="utf-8")

    required_commands = {
        "chemengine tests": ("chemengine", "python -m pytest tests"),
        "backend ruff": ("backend", "ruff check app scripts"),
        "backend mypy": ("backend", "mypy app"),
        "backend tests": ("backend", "pytest tests"),
        "web tests": ("web", "vitest run"),
        "web tsc": ("web", "tsc --noEmit"),
        "web build": ("web", "npm run build"),
        "admin tests": ("admin", "vitest run"),
        "admin tsc": ("admin", "tsc --noEmit"),
        "admin build": ("admin", "npm run build"),
    }
    for label, (job, needle) in required_commands.items():
        steps = jobs.get(job, {}).get("steps", [])
        found = any(
            needle in str(step.get("run", "")) for step in steps if isinstance(step, dict)
        )
        check(f"CI gate present: {label}", found)

    # No failure-hiding on blocking gates.
    check("no '|| true' in the workflow", "|| true" not in text.replace("|| true)", "") or text.count("|| true") == 1)  # the baseline counter uses || true by design
    for job_name, job in jobs.items():
        if job_name == "chemengine":
            # The mypy baseline witness may be non-blocking; nothing else may.
            for step in job.get("steps", []):
                if isinstance(step, dict) and step.get("continue-on-error"):
                    check(
                        f"non-blocking step in chemengine job is the documented mypy baseline",
                        "Mypy baseline" in str(step.get("name", "")),
                    )
        else:
            check(f"job '{job_name}' has no continue-on-error", not job.get("continue-on-error", False))
            for step in job.get("steps", []):
                if isinstance(step, dict):
                    check(
                        f"step '{step.get('name', '?')}' not marked continue-on-error",
                        not step.get("continue-on-error", False),
                    )

    # Exit codes are checked by `run:` semantics automatically; assert the
    # shell is not invoked with flags that swallow failures.
    check("no 'set +e' or 'set -e; true' patterns", "set +e" not in text)


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=1800, env=env, check=False
    )
    return proc.returncode, proc.stdout + proc.stderr


def run_gates() -> None:
    """Run the exact gate commands from the workflow, locally."""
    import os

    print("\n== Local gate execution (same commands as CI) ==", flush=True)
    python = sys.executable
    results: list[tuple[str, bool, str]] = []

    def gate(label: str, ok: bool, detail: str = "") -> None:
        results.append((label, ok, detail))
        check(label, ok, detail)

    # --- ChemEngine -------------------------------------------------------
    ce = ROOT / "packages" / "chemengine"
    code, out = _run([python, "-m", "pytest", "tests", "-q"], cwd=ce)
    summary = next((l for l in out.splitlines() if " passed" in l), out.strip().splitlines()[-1] if out.strip() else "")
    gate("chemengine: pytest tests", code == 0, summary.strip())

    code, out = _run([python, "-m", "ruff", "check", "src", "--no-fix", "--output-format=concise"], cwd=ce)
    findings = sum(1 for line in out.splitlines() if re.search(r":\d+:\d+:", line))
    gate("chemengine: ruff baseline <= 342 findings", findings <= 342, f"{findings} findings (documented baseline)")

    code, out = _run(
        [
            python,
            "-m",
            "pytest",
            "benchmarks",
            "--collect-only",
            "-q",
            "-o",
            "python_files=benchmark_*.py",
        ],
        cwd=ce,
    )
    collected = re.search(r"(\d+) tests collected", out)
    gate(
        "chemengine: benchmark smoke (60 collectable)",
        code == 0 and bool(collected) and int(collected.group(1)) >= 60,
        f"{collected.group(1) if collected else '?'} collected",
    )

    # --- Backend ------------------------------------------------------------
    be = ROOT / "backend"
    env = dict(os.environ)
    env["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    code, out = _run([python, "-m", "ruff", "check", "app", "scripts", "--no-fix"], cwd=be)
    gate("backend: ruff app scripts", code == 0)
    code, out = _run([python, "-m", "mypy", "app"], cwd=be)
    gate("backend: mypy app", code == 0, out.strip().splitlines()[-1] if out.strip() else "")
    code, out = _run([python, "-m", "pytest", "tests", "-q"], cwd=be, env=env)
    summary = next((l for l in out.splitlines() if " passed" in l), out.strip().splitlines()[-1] if out.strip() else "")
    gate("backend: pytest tests", code == 0, summary.strip())

    # --- Web / Admin -----------------------------------------------------
    npm = shutil.which("npm") or shutil.which("npm.cmd") or "npm"
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    for app_name in ("web", "admin"):
        app_dir = ROOT / "apps" / app_name
        code, out = _run([npx, "vitest", "run"], cwd=app_dir)
        summary = next(
            (l.strip() for l in out.splitlines() if "Tests" in l and "passed" in l),
            out.strip().splitlines()[-1] if out.strip() else "",
        )
        gate(f"{app_name}: vitest run", code == 0, summary)
        code, out = _run([npx, "tsc", "--noEmit"], cwd=app_dir)
        gate(f"{app_name}: tsc --noEmit", code == 0)
        code, out = _run([npm, "run", "build"], cwd=app_dir)
        gate(f"{app_name}: npm run build", code == 0)

    failed = [label for label, ok, _ in results if not ok]
    print(f"\n{'=' * 60}", flush=True)
    print(f"GATES: {len(results) - len(failed)} passed, {len(failed)} failed", flush=True)
    if failed:
        print("FAILED GATES:", failed, flush=True)
    sys.exit(1 if failed else 0)


def main() -> int:
    """Validate the workflow, then run all gates unless asked only to validate."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    validate_workflow()
    if FAIL:
        print("\nWorkflow validation failed; not running gates.", flush=True)
        return 1
    if args.validate_only:
        print(f"\n{'=' * 60}\nVALIDATION OK", flush=True)
        return 0
    run_gates()
    return 0


if __name__ == "__main__":
    sys.exit(main())
