"""Event system for the chemistry engine.

A lightweight, typed, synchronous pub/sub event bus. Enables loose coupling
between modules — any module can publish events and any module (including
plugins) can subscribe to them.

Architecture:
    - EventType: String constants for all event types.
    - Event: Immutable event payload with correlation ID tracing.
    - SubscriptionToken: Opaque handle for unsubscribing.
    - EventBus: Thread-safe pub/sub bus with priority ordering.

Design decisions:
    - Synchronous: Events are processed immediately in the publisher's thread.
      This avoids the complexity of async event loops and makes debugging
      straightforward. Async support can be added as a wrapper.
    - Correlation IDs: Enable tracing a molecule through a multi-step pipeline
      (parse → detect → compute → render) for debugging and benchmarking.
    - Priority ordering: Higher-priority handlers run first. This allows
      "interceptor" patterns (e.g., caching, logging, validation).
    - Thread-safe: Uses threading.Lock for all mutations.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4


class EventType:
    """String constants for all event types in the engine.

    Convention: <subsystem>.<action> (e.g., "molecule.parsed").
    """

    # Molecule lifecycle
    MOLECULE_PARSED = "molecule.parsed"
    MOLECULE_BUILT = "molecule.built"
    MOLECULE_VALIDATED = "molecule.validated"

    # Property computation
    PROPERTY_COMPUTED = "property.computed"
    PROPERTY_FAILED = "property.failed"

    # Isomer generation
    ISOMER_GENERATED = "isomer.generated"
    ISOMER_ENUMERATION_STARTED = "isomer.enumeration.started"
    ISOMER_ENUMERATION_COMPLETED = "isomer.enumeration.completed"

    # Detection
    RING_DETECTED = "detection.ring.found"
    AROMATICITY_ASSIGNED = "detection.aromaticity.assigned"
    FUNCTIONAL_GROUP_FOUND = "detection.functional_group.found"

    # Stereochemistry
    STEREO_ASSIGNED = "stereo.assigned"
    STEREO_PERCEIVED = "stereo.perceived"

    # Validation
    SANITIZATION_STARTED = "validation.sanitization.started"
    SANITIZATION_COMPLETED = "validation.sanitization.completed"
    SANITIZATION_FAILED = "validation.sanitization.failed"

    # Registry
    ALGORITHM_REGISTERED = "registry.algorithm.registered"
    ALGORITHM_REPLACED = "registry.algorithm.replaced"

    # Plugin lifecycle
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"

    # Dataset
    DATASET_CHANGED = "dataset.changed"
    DATASET_LOADED = "dataset.loaded"

    # Tool execution
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"

    # Error
    ERROR_OCCURRED = "error.occurred"


@dataclass(frozen=True, slots=True)
class Event:
    """An event in the chemistry engine's event system.

    Attributes:
        type: The event type string (from EventType).
        payload: The event data (typed per event type).
        source: The module or component that published the event.
        timestamp: Unix timestamp when the event was created.
        correlation_id: Optional ID for tracing through pipelines.

    Usage:
        >>> event = Event(
        ...     type=EventType.MOLECULE_PARSED,
        ...     payload=graph,
        ...     source="parsing.smiles",
        ...     correlation_id="req-001",
        ... )
    """

    type: str
    """The event type string (from EventType constants)."""

    payload: Any
    """The event data. Type depends on the event type."""

    source: str
    """The module or component that published the event."""

    timestamp: float = field(default_factory=time.time)
    """Unix timestamp when the event was created."""

    correlation_id: str | None = None
    """Optional ID for tracing through multi-step pipelines."""


@dataclass(frozen=True, slots=True)
class SubscriptionToken:
    """Opaque handle for unsubscribing from the event bus.

    Returned by EventBus.subscribe(). Pass to EventBus.unsubscribe() to
    remove the handler.
    """

    _id: UUID = field(default_factory=uuid4)
    """Unique identifier for this subscription."""


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Usage:
        >>> bus = EventBus()
        >>> token = bus.subscribe("molecule.parsed", my_handler)
        >>> bus.publish(Event(type="molecule.parsed", payload=graph, source="test"))
        >>> bus.unsubscribe(token)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: dict[str, list[tuple[int, Callable[[Event], None], SubscriptionToken]]] = {}

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribed handlers.

        Handlers are called in priority order (highest first). If a handler
        raises an exception, it is logged but other handlers are still called.

        Args:
            event: The event to publish.
        """
        with self._lock:
            handlers = list(self._handlers.get(event.type, []))

        # Sort by priority (descending)
        handlers.sort(key=lambda h: h[0], reverse=True)

        for priority, handler, token in handlers:
            try:
                handler(event)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(
                    f"Handler {handler} failed for event {event.type}: {e}"
                )

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Event], None],
        *,
        priority: int = 0,
    ) -> SubscriptionToken:
        """Subscribe a handler to an event type.

        Args:
            event_type: The event type to subscribe to.
            handler: The handler function (takes Event, returns None).
            priority: Priority (higher = called first). Default 0.

        Returns:
            A SubscriptionToken for unsubscribing.
        """
        token = SubscriptionToken()
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append((priority, handler, token))
        return token

    def unsubscribe(self, token: SubscriptionToken) -> None:
        """Unsubscribe a handler using its token.

        Args:
            token: The SubscriptionToken returned by subscribe().
        """
        with self._lock:
            for event_type in list(self._handlers.keys()):
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h[2] != token
                ]
                if not self._handlers[event_type]:
                    del self._handlers[event_type]

    def clear(self) -> None:
        """Remove all subscriptions (for testing)."""
        with self._lock:
            self._handlers.clear()

    @property
    def subscription_count(self) -> int:
        """Total number of active subscriptions."""
        with self._lock:
            return sum(len(h) for h in self._handlers.values())

    def __repr__(self) -> str:
        return f"EventBus({self.subscription_count} subscriptions)"


# Global singleton instance
_global_bus: EventBus | None = None


def get_global_bus() -> EventBus:
    """Get or create the global EventBus singleton.

    Returns:
        The global EventBus instance.
    """
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def reset_global_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _global_bus
    _global_bus = None
