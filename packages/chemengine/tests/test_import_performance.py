"""First-import performance regression test (M33 Phase 6, roadmap 15.6).

The roadmap sets a first-import target of <100 ms for ``import chemengine``.
M32 measured ~493 ms; M33's lazy-loading work (PEP 562 lazy public API,
lazy element/dataset tables, lazy plugin discovery) reduced it to ~20 ms.

Methodology (documented, reproducible):
- spawn a fresh interpreter (cold process) with ``-X importtime``
- parse the cumulative microseconds of the final ``chemengine`` import row
  (cumulative = self time + all submodule time; excludes interpreter
  startup, which on this machine adds ~130 ms of unrelated wall time)
- repeat 3 times and take the median (first run can pay Windows file-cache
  costs; the median is the honest cold-start estimate)
- assert against the 100 ms roadmap target with headroom for CI noise
  (CI machines are slower; 100 ms target + generous margin is the gate,
  a separate hard 150 ms guard catches gross regressions)

The test is marked performance and lives with the other benchmark tests so
CI and developers run the same gate.
"""

from __future__ import annotations

import statistics
import subprocess
import sys

import pytest

pytestmark = pytest.mark.benchmark

IMPORT_TARGET_MS = 100.0  # roadmap 15.6 target
REGRESSION_GUARD_MS = 150.0  # gross-regression guard with CI headroom


def _measure_first_import_ms() -> list[float]:
    """Cold-process first-import time of ``chemengine`` (3 samples)."""
    samples: list[float] = []
    for _ in range(3):
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-X", "importtime", "-c", "import chemengine"],
            capture_output=True,
            text=True,
            check=True,
        )
        last = proc.stderr.strip().splitlines()[-1]
        # Format: "import time:<self us>|<cumulative us>|<module>"
        cumulative_us = int(last.split("|")[1])
        samples.append(cumulative_us / 1000.0)
    return samples


class TestFirstImportPerformance:
    """Roadmap 15.6 gate: cold first-import of the package under 100 ms."""

    def test_first_import_under_roadmap_target(self) -> None:
        """Median cold first-import stays under the 100 ms roadmap target."""
        samples = _measure_first_import_ms()
        median = statistics.median(samples)
        assert median < IMPORT_TARGET_MS, (
            f"first import regressed: median {median:.1f} ms "
            f"(target <{IMPORT_TARGET_MS:.0f} ms; samples="
            f"{[f'{s:.1f}' for s in samples]})"
        )

    def test_first_import_no_gross_regression(self) -> None:
        """Hard guard: even on slow CI, import must stay under 150 ms."""
        samples = _measure_first_import_ms()
        assert max(samples) < REGRESSION_GUARD_MS, (
            f"first import exceeded gross-regression guard: max "
            f"{max(samples):.1f} ms (guard <{REGRESSION_GUARD_MS:.0f} ms)"
        )
