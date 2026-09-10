"""Tests for the EventBus system."""

import threading

import pytest

from chemengine.core.events import (
    Event,
    EventBus,
    EventType,
    SubscriptionToken,
    get_global_bus,
    reset_global_bus,
)


class TestEvent:
    """Tests for the Event dataclass."""

    def test_event_creation(self):
        event = Event(type="test.event", payload={"key": "value"}, source="test")
        assert event.type == "test.event"
        assert event.payload == {"key": "value"}
        assert event.source == "test"
        assert event.correlation_id is None
        assert event.timestamp > 0

    def test_event_with_correlation_id(self):
        event = Event(
            type="test.event",
            payload="data",
            source="test",
            correlation_id="req-001",
        )
        assert event.correlation_id == "req-001"

    def test_event_immutable(self):
        event = Event(type="test.event", payload="data", source="test")
        with pytest.raises((AttributeError, TypeError)):
            event.type = "changed"

    def test_event_default_timestamp(self):
        event = Event(type="test.event", payload="data", source="test")
        assert isinstance(event.timestamp, float)


class TestEventBus:
    """Tests for the EventBus pub/sub system."""

    def setup_method(self):
        self.bus = EventBus()
        self.received: list[Event] = []

    def _handler(self, event: Event) -> None:
        self.received.append(event)

    def test_subscribe_and_publish(self):
        token = self.bus.subscribe("test.event", self._handler)
        event = Event(type="test.event", payload="hello", source="test")
        self.bus.publish(event)
        assert len(self.received) == 1
        assert self.received[0].type == "test.event"
        assert self.received[0].payload == "hello"

    def test_subscribe_multiple_handlers(self):
        received2: list[Event] = []

        def handler2(e: Event) -> None:
            received2.append(e)

        self.bus.subscribe("test.event", self._handler)
        self.bus.subscribe("test.event", handler2)
        self.bus.publish(Event(type="test.event", payload="data", source="test"))
        assert len(self.received) == 1
        assert len(received2) == 1

    def test_unsubscribe(self):
        token = self.bus.subscribe("test.event", self._handler)
        self.bus.publish(Event(type="test.event", payload="first", source="test"))
        assert len(self.received) == 1

        self.bus.unsubscribe(token)
        self.bus.publish(Event(type="test.event", payload="second", source="test"))
        assert len(self.received) == 1  # Should not increase

    def test_unsubscribe_invalid_token(self):
        """Unsubscribing a non-existent token should not raise."""
        token = SubscriptionToken()
        self.bus.unsubscribe(token)  # Should not raise

    def test_different_event_types(self):
        token1 = self.bus.subscribe("type.a", self._handler)
        token2 = self.bus.subscribe("type.b", self._handler)

        self.bus.publish(Event(type="type.a", payload="a", source="test"))
        assert len(self.received) == 1

        self.bus.publish(Event(type="type.b", payload="b", source="test"))
        assert len(self.received) == 2

    def test_no_handler_for_event_type(self):
        """Publishing to an event type with no handlers should not raise."""
        self.bus.publish(Event(type="unsubscribed", payload="data", source="test"))

    def test_priority_ordering(self):
        results: list[int] = []

        def handler_high(e: Event) -> None:
            results.append(1)

        def handler_low(e: Event) -> None:
            results.append(2)

        self.bus.subscribe("test.event", handler_low, priority=0)
        self.bus.subscribe("test.event", handler_high, priority=100)

        self.bus.publish(Event(type="test.event", payload="data", source="test"))
        assert results == [1, 2], "Higher priority handlers should run first"

    def test_handler_exception(self):
        """A failing handler should not prevent other handlers from running."""

        def failing_handler(e: Event) -> None:
            raise ValueError("Intentional failure")

        self.bus.subscribe("test.event", failing_handler)
        self.bus.subscribe("test.event", self._handler)

        # Should not raise despite failing_handler
        self.bus.publish(Event(type="test.event", payload="data", source="test"))
        assert len(self.received) == 1

    def test_correlation_id_tracing(self):
        events: list[Event] = []

        def collector(e: Event) -> None:
            events.append(e)

        self.bus.subscribe("test.event", collector)
        self.bus.publish(Event(
            type="test.event", payload="step1", source="test",
            correlation_id="trace-001",
        ))
        self.bus.publish(Event(
            type="test.event", payload="step2", source="test",
            correlation_id="trace-001",
        ))
        assert all(e.correlation_id == "trace-001" for e in events)
        assert len(events) == 2

    def test_clear_removes_all_handlers(self):
        self.bus.subscribe("test.event", self._handler)
        self.bus.clear()
        assert self.bus.subscription_count == 0
        self.bus.publish(Event(type="test.event", payload="data", source="test"))
        assert len(self.received) == 0

    def test_subscription_count(self):
        assert self.bus.subscription_count == 0
        t1 = self.bus.subscribe("a", self._handler)
        t2 = self.bus.subscribe("b", self._handler)
        assert self.bus.subscription_count == 2
        self.bus.unsubscribe(t1)
        assert self.bus.subscription_count == 1
        self.bus.unsubscribe(t2)
        assert self.bus.subscription_count == 0

    def test_repr(self):
        assert "EventBus" in repr(self.bus)

    def test_thread_safety(self):
        """Publish from multiple threads should not crash."""
        errors: list[Exception] = []
        lock = threading.Lock()

        def safe_handler(e: Event) -> None:
            with lock:
                self.received.append(e)

        self.bus.subscribe("test.event", safe_handler)

        def publish_thread():
            try:
                for _ in range(100):
                    self.bus.publish(Event(
                        type="test.event", payload="t", source="thread"
                    ))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=publish_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(self.received) == 1000


class TestEventType:
    """Tests for EventType constants."""

    def test_constants_are_strings(self):
        assert EventType.MOLECULE_PARSED == "molecule.parsed"
        assert EventType.TOOL_EXECUTED == "tool.executed"
        assert EventType.PLUGIN_LOADED == "plugin.loaded"

    def test_all_constants_have_values(self):
        for attr_name in dir(EventType):
            if attr_name.isupper():
                val = getattr(EventType, attr_name)
                assert isinstance(val, str), f"{attr_name} should be a string"


class TestGlobalEventBus:
    """Tests for the global EventBus singleton."""

    def teardown_method(self):
        reset_global_bus()

    def test_get_global_bus(self):
        bus = get_global_bus()
        assert isinstance(bus, EventBus)

    def test_global_bus_is_singleton(self):
        bus1 = get_global_bus()
        bus2 = get_global_bus()
        assert bus1 is bus2

    def test_reset_global_bus(self):
        bus1 = get_global_bus()
        reset_global_bus()
        bus2 = get_global_bus()
        assert bus1 is not bus2

    def test_global_bus_works(self):
        bus = get_global_bus()
        received: list[Event] = []
        bus.subscribe("test", lambda e: received.append(e))
        bus.publish(Event(type="test", payload="x", source="test"))
        assert len(received) == 1
        reset_global_bus()
