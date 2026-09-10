"""Tests for Phase 14: Performance — profiling, caching, batch processing.
"""

import time

from chemengine.utils.performance import (
    EnhancedCache,
    Profiler,
    batch_process,
    get_profiler,
    parallel_batch_process,
)

# ══════════════════════════════════════════════════════════════════
# PROFILER TESTS
# ══════════════════════════════════════════════════════════════════


class TestProfiler:
    """Tests for the Profiler class."""

    def test_profile_decorator(self):
        """Profile decorator records timing."""
        profiler = Profiler()

        @profiler.profile("test_func")
        def slow_func():
            time.sleep(0.001)
            return 42

        result = slow_func()
        assert result == 42

        profile = profiler.get_result("test_func")
        assert profile is not None
        assert profile.call_count == 1
        assert profile.total_time_ms >= 0.5  # At least 0.5ms

    def test_profile_multiple_calls(self):
        """Multiple calls are recorded."""
        profiler = Profiler()

        @profiler.profile("multi")
        def func():
            return 1

        for _ in range(10):
            func()

        profile = profiler.get_result("multi")
        assert profile is not None
        assert profile.call_count == 10
        assert profile.min_time_ms <= profile.avg_time_ms <= profile.max_time_ms

    def test_manual_record(self):
        """Manual timing recording works."""
        profiler = Profiler()
        profiler.record("manual", 1.5)
        profiler.record("manual", 2.5)

        result = profiler.get_result("manual")
        assert result is not None
        assert result.call_count == 2
        assert result.avg_time_ms == 2.0

    def test_get_results_sorted(self):
        """Results are sorted by total time (descending)."""
        profiler = Profiler()
        profiler.record("fast", 1.0)
        profiler.record("slow", 10.0)
        profiler.record("medium", 5.0)

        results = profiler.get_results()
        assert results[0].function_name == "slow"
        assert results[1].function_name == "medium"
        assert results[2].function_name == "fast"

    def test_summary(self):
        """Summary produces readable output."""
        profiler = Profiler()
        profiler.record("func_a", 5.0)
        profiler.record("func_b", 10.0)

        summary = profiler.summary()
        assert "func_a" in summary
        assert "func_b" in summary
        assert "TOTAL" in summary

    def test_reset(self):
        """Reset clears all data."""
        profiler = Profiler()
        profiler.record("test", 1.0)
        profiler.reset()
        assert profiler.get_result("test") is None

    def test_global_profiler(self):
        """Global profiler is accessible."""
        profiler = get_profiler()
        assert isinstance(profiler, Profiler)


# ══════════════════════════════════════════════════════════════════
# ENHANCED CACHE TESTS
# ══════════════════════════════════════════════════════════════════


class TestEnhancedCache:
    """Tests for EnhancedCache."""

    def test_basic_put_get(self):
        """Basic put and get operations."""
        cache = EnhancedCache(max_size=10)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_miss(self):
        """Cache miss returns None."""
        cache = EnhancedCache()
        assert cache.get("nonexistent") is None

    def test_lru_eviction(self):
        """LRU eviction when cache is full."""
        cache = EnhancedCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_lru_access_prevents_eviction(self):
        """Accessing a key prevents it from being evicted."""
        cache = EnhancedCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.get("a")  # Access "a" — moves to end
        cache.put("d", 4)  # Should evict "b" (least recently used)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_ttl_expiration(self):
        """Cache entries expire after TTL."""
        cache = EnhancedCache(ttl_seconds=0.01)  # 10ms TTL
        cache.put("key", "value")
        time.sleep(0.02)  # Wait 20ms
        assert cache.get("key") is None

    def test_invalidation(self):
        """Invalidation removes specific keys."""
        cache = EnhancedCache()
        cache.put("key", "value")
        assert cache.invalidate("key") is True
        assert cache.get("key") is None
        assert cache.invalidate("nonexistent") is False

    def test_clear(self):
        """Clear removes all entries."""
        cache = EnhancedCache()
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert cache.size == 0

    def test_hit_rate(self):
        """Hit rate is calculated correctly."""
        cache = EnhancedCache()
        cache.put("key", "value")
        cache.get("key")     # hit
        cache.get("key")     # hit
        cache.get("miss")    # miss
        assert cache.hit_rate == 2 / 3

    def test_stats(self):
        """Stats returns correct information."""
        cache = EnhancedCache(max_size=100)
        cache.put("a", 1)
        stats = cache.stats
        assert stats["size"] == 1
        assert stats["max_size"] == 100


# ══════════════════════════════════════════════════════════════════
# BATCH PROCESSING TESTS
# ══════════════════════════════════════════════════════════════════


class TestBatchProcessing:
    """Tests for batch processing functions."""

    def test_basic_batch(self):
        """Basic batch processing works."""
        items = list(range(10))
        results = batch_process(items, lambda x: x * 2, batch_size=3)
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    def test_batch_with_progress(self):
        """Progress callback is called."""
        items = list(range(10))
        progress_calls = []
        batch_process(
            items,
            lambda x: x,
            batch_size=3,
            progress_callback=lambda c, t: progress_calls.append((c, t)),
        )
        assert len(progress_calls) > 0
        assert progress_calls[-1] == (10, 10)

    def test_empty_batch(self):
        """Empty list produces empty results."""
        results = batch_process([], lambda x: x)
        assert results == []

    def test_parallel_batch(self):
        """Parallel batch processing works."""
        items = list(range(20))
        results = parallel_batch_process(items, lambda x: x ** 2, batch_size=5)
        assert results == [x ** 2 for x in range(20)]

    def test_parallel_preserves_order(self):
        """Parallel processing preserves item order."""
        items = list(range(100))
        results = parallel_batch_process(items, lambda x: x * 3, batch_size=10)
        assert results == [x * 3 for x in range(100)]
