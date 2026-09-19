"""Deterministic tool-result cache for the AI tutor (M30).

Caches **only safe, deterministic ChemEngine tool results** — the same tool
name + validated arguments always produce the same chemistry value, so the
result can be reused within its TTL without any correctness risk. This is a
pure cost optimization; the ChemEngine authority is unchanged (cache hits
return the engine's own earlier output).

What is deliberately **never** cached:
- LLM/provider responses (non-deterministic, may embed conversation content)
- conversation or message content (private per-user data)
- anything that failed (only successful results enter the cache)

Bounds: a fixed entry cap plus per-entry TTL. Insertion order eviction keeps
memory bounded; a background-free lazy sweep expires entries on access.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

#: Default time-to-live for a cached tool result (seconds).
DEFAULT_TTL_SECONDS = 600.0
#: Default maximum number of cached entries.
DEFAULT_MAX_ENTRIES = 256


@dataclass(slots=True)
class _Entry:
    """One cached tool result."""

    expires_at: float
    result: dict[str, object]


@dataclass(slots=True)
class _CacheStats:
    """Hit/miss counters for observability (never logged with content)."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    _lock: object = field(default=None, repr=False, compare=False)


class ToolResultCache:
    """Bounded TTL cache keyed by (tool name, canonical arguments)."""

    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        """Initialize with TTL and entry cap (both must be positive)."""
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._entries: dict[str, _Entry] = {}
        self.stats = _CacheStats()

    def cache_key(self, tool_name: str, arguments: dict[str, object]) -> str:
        """Deterministic key: tool name + canonicalized argument JSON.

        Arguments are JSON-serialized with sorted keys so that the same
        logical arguments always map to the same key regardless of dict
        insertion order.
        """
        canonical = json.dumps(
            arguments, sort_keys=True, separators=(",", ":"), default=str
        )
        digest = hashlib.sha256(
            f"{tool_name}|{canonical}".encode()
        ).hexdigest()
        return f"{tool_name}:{digest}"

    def get(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object] | None:
        """Return the cached result, or None on miss/expiration."""
        key = self.cache_key(tool_name, arguments)
        entry = self._entries.get(key)
        now = time.monotonic()
        if entry is None:
            self.stats.misses += 1
            return None
        if now >= entry.expires_at:
            # Lazy expiration.
            del self._entries[key]
            self.stats.expirations += 1
            self.stats.misses += 1
            return None
        self.stats.hits += 1
        return dict(entry.result)

    def put(
        self, tool_name: str, arguments: dict[str, object], result: dict[str, object]
    ) -> None:
        """Store a successful deterministic result (bounds enforced)."""
        key = self.cache_key(tool_name, arguments)
        # Evict oldest entries (insertion order) while at capacity.
        while len(self._entries) >= self._max_entries:
            oldest_key = next(iter(self._entries))
            del self._entries[oldest_key]
            self.stats.evictions += 1
        self._entries[key] = _Entry(
            expires_at=time.monotonic() + self._ttl,
            result=dict(result),
        )

    def clear(self) -> None:
        """Drop every cached entry (used by tests)."""
        self._entries.clear()

    def __len__(self) -> int:
        """Current number of entries (including not-yet-swept expired ones)."""
        return len(self._entries)


#: Module-level shared cache instance used by the tutor toolbox.
shared_tool_cache = ToolResultCache()
