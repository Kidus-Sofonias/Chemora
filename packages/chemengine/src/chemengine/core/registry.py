"""AlgorithmRegistry — centralized registry for all algorithms in the engine.

Every algorithm in the chemistry engine registers itself here. This enables:
    - Discovery: List all available algorithms by domain, tags, or name.
    - Resolution: Find the best algorithm for a task (fastest, most accurate).
    - Hot-swapping: Replace an algorithm at runtime (for plugins).
    - Versioning: Track algorithm versions for reproducibility.

The registry is a singleton-like class. A single global instance is created
at module level, but the class can also be instantiated for testing.

Architecture:
    - AlgorithmEntry: Metadata about a registered algorithm.
    - AlgorithmRegistry: The registry itself, with register/get/resolve/list.
    - Resolution: Algorithms can be resolved by domain + name, or by
      domain + tags with optional speed/accuracy preference.

Design decisions:
    - Domain-based namespacing: "parsing.smiles", "detection.rings", etc.
      prevents naming collisions between different subsystems.
    - Tags for capability-based resolution: "fast", "exact", "approximate"
      enable automatic selection of the right algorithm for the context.
    - Version field: Enables reproducibility and graceful deprecation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AlgorithmEntry:
    """Metadata for a registered algorithm.

    Attributes:
        domain: Namespace for the algorithm (e.g., "parsing.smiles",
            "detection.rings", "generation.constitutional").
        name: Human-readable name within the domain (e.g., "daylight-smiles").
        version: SemVer version string (e.g., "1.0.0").
        algorithm: The callable implementing the algorithm.
        input_type: Expected input type (for validation).
        output_type: Expected output type (for validation).
        metadata: Additional key-value metadata (complexity, citations, etc.).
        tags: Set of tags for capability-based resolution.

    Usage:
        >>> entry = AlgorithmEntry(
        ...     domain="parsing.smiles",
        ...     name="daylight-smiles",
        ...     version="1.0.0",
        ...     algorithm=my_parser,
        ...     tags=frozenset({"fast", "standard"}),
        ... )
    """

    domain: str
    """Namespace for the algorithm (e.g., 'parsing.smiles')."""

    name: str
    """Human-readable name within the domain (e.g., 'daylight-smiles')."""

    version: str
    """SemVer version string (e.g., '1.0.0')."""

    algorithm: Callable[..., Any]
    """The callable implementing the algorithm."""

    input_type: type | None = None
    """Expected input type. None if not constrained."""

    output_type: type | None = None
    """Expected output type. None if not constrained."""

    metadata: frozenset[tuple[str, Any]] = frozenset()
    """Additional metadata (complexity, citations, author, etc.)."""

    tags: frozenset[str] = frozenset()
    """Tags for capability-based resolution (e.g., 'fast', 'exact')."""


class AlgorithmRegistry:
    """Central registry for all algorithms in the chemistry engine.

    Provides registration, lookup, resolution, and hot-swapping of algorithms.
    Algorithms are organized by (domain, name) pairs and can be resolved
    by tags for automatic selection.

    Usage:
        >>> registry = AlgorithmRegistry()
        >>> registry.register(entry)
        >>> algo = registry.get("parsing.smiles", "daylight-smiles")
        >>> result = algo.algorithm("CCO")
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], AlgorithmEntry] = {}
        self._aliases: dict[str, tuple[str, str]] = {}

    def register(
        self,
        entry: AlgorithmEntry,
        *,
        alias: str | None = None,
    ) -> None:
        """Register an algorithm in the registry.

        Args:
            entry: The AlgorithmEntry to register.
            alias: Optional short alias for quick lookup.

        Raises:
            ValueError: If an algorithm with the same (domain, name) exists.
        """
        key = (entry.domain, entry.name)
        if key in self._entries:
            logger.warning(f"Overwriting algorithm {entry.domain}/{entry.name} v{entry.version}")
        self._entries[key] = entry
        if alias:
            self._aliases[alias] = key
        logger.debug(f"Registered algorithm: {entry.domain}/{entry.name} v{entry.version}")

    def get(self, domain: str, name: str) -> AlgorithmEntry:
        """Get an algorithm by domain and name.

        Args:
            domain: The algorithm's domain namespace.
            name: The algorithm's name within the domain.

        Returns:
            The AlgorithmEntry.

        Raises:
            KeyError: If no algorithm is registered with that (domain, name).
        """
        key = (domain, name)
        if key in self._entries:
            return self._entries[key]
        raise KeyError(f"No algorithm registered for {domain}/{name}")

    def resolve(
        self,
        *,
        domain: str | None = None,
        name: str | None = None,
        tags: set[str] | None = None,
        fastest: bool = False,
        most_accurate: bool = False,
    ) -> AlgorithmEntry:
        """Resolve the best algorithm matching the given criteria.

        Resolution priority:
            1. Exact (domain, name) match if both provided.
            2. Domain + tags match (all tags must be present).
            3. Domain-only match (returns the highest version).
            4. If fastest=True, prefer algorithm with 'fast' tag.
            5. If most_accurate=True, prefer algorithm with 'exact' tag.

        Args:
            domain: Optional domain filter.
            name: Optional name filter (requires domain).
            tags: Optional set of required tags.
            fastest: If True, prefer the fastest algorithm.
            most_accurate: If True, prefer the most accurate algorithm.

        Returns:
            The best-matching AlgorithmEntry.

        Raises:
            KeyError: If no algorithm matches the criteria.
        """
        # Exact match
        if domain and name:
            return self.get(domain, name)

        # Filter by domain
        candidates = list(self._entries.values())
        if domain:
            candidates = [e for e in candidates if e.domain == domain]

        if not candidates:
            raise KeyError(f"No algorithms found for domain={domain}")

        # Filter by tags
        if tags:
            candidates = [e for e in candidates if tags.issubset(e.tags)]

        if not candidates:
            raise KeyError(f"No algorithms found matching tags={tags}")

        # Preference filtering
        if fastest:
            fast_candidates = [e for e in candidates if "fast" in e.tags]
            if fast_candidates:
                candidates = fast_candidates

        if most_accurate:
            exact_candidates = [e for e in candidates if "exact" in e.tags]
            if exact_candidates:
                candidates = exact_candidates

        # Return highest version
        candidates.sort(key=lambda e: e.version, reverse=True)
        return candidates[0]

    def list(self, domain: str | None = None) -> list[AlgorithmEntry]:
        """List all registered algorithms, optionally filtered by domain.

        Args:
            domain: Optional domain to filter by.

        Returns:
            List of AlgorithmEntry objects.
        """
        if domain:
            return [e for e in self._entries.values() if e.domain == domain]
        return list(self._entries.values())

    def replace(self, entry: AlgorithmEntry) -> None:
        """Replace an existing algorithm (hot-swap).

        Unlike register(), this silently overwrites without warning.
        Used by plugins to override built-in algorithms.

        Args:
            entry: The new AlgorithmEntry to replace with.
        """
        key = (entry.domain, entry.name)
        self._entries[key] = entry
        logger.info(f"Replaced algorithm: {entry.domain}/{entry.name} v{entry.version}")

    def unregister(self, domain: str, name: str) -> None:
        """Remove an algorithm from the registry.

        Args:
            domain: The algorithm's domain.
            name: The algorithm's name.
        """
        key = (domain, name)
        if key in self._entries:
            del self._entries[key]
            logger.debug(f"Unregistered algorithm: {domain}/{name}")

    def clear(self) -> None:
        """Remove all registered algorithms (for testing)."""
        self._entries.clear()
        self._aliases.clear()

    @property
    def count(self) -> int:
        """Number of registered algorithms."""
        return len(self._entries)

    def __contains__(self, key: tuple[str, str]) -> bool:
        """Check if an algorithm is registered."""
        return key in self._entries

    def __repr__(self) -> str:
        return f"AlgorithmRegistry({self.count} algorithms)"


# Global singleton instance
_global_registry: AlgorithmRegistry | None = None


def get_global_registry() -> AlgorithmRegistry:
    """Get or create the global AlgorithmRegistry singleton.

    Returns:
        The global AlgorithmRegistry instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = AlgorithmRegistry()
    return _global_registry


def reset_global_registry() -> None:
    """Reset the global registry (for testing)."""
    global _global_registry
    _global_registry = None
