"""LRU cache for expensive molecular computations."""

from collections import OrderedDict
from typing import Any


class MolecularCache:
    """LRU cache keyed by graph hash for expensive computations."""

    def __init__(self, maxsize: int = 1024):
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Any | None:
        """Return the cached value for ``key``, or ``None`` on a miss.

        A hit refreshes the entry's recency (LRU semantics).
        """
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Insert or refresh an entry, evicting the least recently used
        entry when the cache exceeds ``maxsize``."""
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)
