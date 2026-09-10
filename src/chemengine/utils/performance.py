"""Performance utilities — profiling, enhanced caching, and parallel execution.

Provides:
- Function profiling with timing and call counting
- Enhanced molecular cache with TTL and eviction
- Parallel batch processing for independent operations
- Memory usage tracking
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


# ══════════════════════════════════════════════════════════════════
# PROFILING
# ══════════════════════════════════════════════════════════════════


@dataclass
class ProfileResult:
    """Result of profiling a function call."""
    function_name: str
    total_time_ms: float
    call_count: int
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float

    def __repr__(self) -> str:
        return (
            f"ProfileResult({self.function_name}: "
            f"calls={self.call_count}, "
            f"avg={self.avg_time_ms:.3f}ms, "
            f"total={self.total_time_ms:.3f}ms)"
        )


class Profiler:
    """Function profiler for performance analysis.

    Usage:
        >>> profiler = Profiler()
        >>> @profiler.profile("parse_smiles")
        ... def parse(smi):
        ...     return parse_smiles(smi)
        >>> # ... use the function ...
        >>> print(profiler.get_results())
    """

    def __init__(self) -> None:
        self._timings: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def profile(self, name: str) -> Callable:
        """Decorator to profile a function."""
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000  # ms
                with self._lock:
                    if name not in self._timings:
                        self._timings[name] = []
                    self._timings[name].append(elapsed)
                return result
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        return decorator

    def record(self, name: str, elapsed_ms: float) -> None:
        """Manually record a timing."""
        with self._lock:
            if name not in self._timings:
                self._timings[name] = []
            self._timings[name].append(elapsed_ms)

    def get_result(self, name: str) -> ProfileResult | None:
        """Get profiling result for a function."""
        if name not in self._timings:
            return None
        times = self._timings[name]
        if not times:
            return None
        return ProfileResult(
            function_name=name,
            total_time_ms=sum(times),
            call_count=len(times),
            avg_time_ms=sum(times) / len(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
        )

    def get_results(self) -> list[ProfileResult]:
        """Get all profiling results."""
        results = []
        for name in self._timings:
            result = self.get_result(name)
            if result:
                results.append(result)
        results.sort(key=lambda r: r.total_time_ms, reverse=True)
        return results

    def reset(self) -> None:
        """Reset all profiling data."""
        self._timings.clear()

    def summary(self) -> str:
        """Get a human-readable summary."""
        results = self.get_results()
        if not results:
            return "No profiling data."
        lines = ["Profile Summary:", "-" * 60]
        for r in results:
            lines.append(
                f"  {r.function_name:30s} "
                f"calls={r.call_count:6d} "
                f"avg={r.avg_time_ms:8.3f}ms "
                f"total={r.total_time_ms:8.3f}ms"
            )
        lines.append("-" * 60)
        total = sum(r.total_time_ms for r in results)
        lines.append(f"  {'TOTAL':30s} {'':6s} {'':8s} total={total:8.3f}ms")
        return "\n".join(lines)


# Global profiler instance
_global_profiler = Profiler()


def get_profiler() -> Profiler:
    """Get the global profiler instance."""
    return _global_profiler


# ══════════════════════════════════════════════════════════════════
# ENHANCED CACHING
# ══════════════════════════════════════════════════════════════════


class EnhancedCache:
    """Enhanced molecular cache with TTL, eviction, and size limits.

    Features:
    - LRU eviction when size limit is reached
    - TTL (time-to-live) for cache entries
    - Thread-safe operations
    - Hit/miss statistics
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: float | None = None,
    ) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get a value from the cache."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            value, timestamp = self._cache[key]

            # Check TTL
            if self._ttl is not None:
                age = time.time() - timestamp
                if age > self._ttl:
                    del self._cache[key]
                    self._misses += 1
                    return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: str, value: Any) -> None:
        """Put a value in the cache."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, time.time())

            # Evict oldest if over size limit
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        """Current cache size."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        """Cache statistics."""
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }


# ══════════════════════════════════════════════════════════════════
# BATCH PROCESSING
# ══════════════════════════════════════════════════════════════════


def batch_process(
    items: list[Any],
    func: Callable[[Any], T],
    batch_size: int = 100,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[T]:
    """Process items in batches with optional progress reporting.

    Args:
        items: List of items to process.
        func: Function to apply to each item.
        batch_size: Number of items per batch.
        progress_callback: Called with (completed, total) after each batch.

    Returns:
        List of results.
    """
    results: list[T] = []
    total = len(items)

    for i in range(0, total, batch_size):
        batch = items[i:i + batch_size]
        batch_results = [func(item) for item in batch]
        results.extend(batch_results)

        if progress_callback:
            progress_callback(min(i + batch_size, total), total)

    return results


def parallel_batch_process(
    items: list[Any],
    func: Callable[[Any], T],
    max_workers: int = 4,
    batch_size: int = 100,
) -> list[T]:
    """Process items in parallel batches using threading.

    Note: Due to Python's GIL, true parallelism requires I/O-bound work.
    For CPU-bound work, consider multiprocessing (not implemented here).

    Args:
        items: List of items to process.
        func: Function to apply to each item.
        max_workers: Maximum number of worker threads.
        batch_size: Items per batch.

    Returns:
        List of results (order preserved).
    """
    import concurrent.futures

    results: list[T | None] = [None] * len(items)

    def process_batch(start_idx: int, batch: list[Any]) -> list[tuple[int, T]]:
        return [(start_idx + i, func(item)) for i, item in enumerate(batch)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            futures.append(executor.submit(process_batch, i, batch))

        for future in concurrent.futures.as_completed(futures):
            for idx, result in future.result():
                results[idx] = result

    return results  # type: ignore
