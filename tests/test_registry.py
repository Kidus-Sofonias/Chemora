"""Tests for the AlgorithmRegistry."""

import pytest

from chemengine.core.registry import (
    AlgorithmEntry,
    AlgorithmRegistry,
    get_global_registry,
    reset_global_registry,
)


def _dummy_algorithm(x: str) -> str:
    return f"processed: {x}"


class TestAlgorithmEntry:
    """Tests for the AlgorithmEntry dataclass."""

    def test_create_entry(self):
        entry = AlgorithmEntry(
            domain="parsing.smiles",
            name="default",
            version="1.0.0",
            algorithm=_dummy_algorithm,
            tags=frozenset({"fast", "standard"}),
        )
        assert entry.domain == "parsing.smiles"
        assert entry.name == "default"
        assert entry.version == "1.0.0"

    def test_entry_immutable(self):
        entry = AlgorithmEntry(
            domain="test", name="test", version="1.0.0",
            algorithm=_dummy_algorithm,
        )
        with pytest.raises((AttributeError, TypeError)):
            entry.version = "2.0.0"

    def test_entry_with_input_output_types(self):
        entry = AlgorithmEntry(
            domain="test", name="test", version="1.0.0",
            algorithm=_dummy_algorithm,
            input_type=str,
            output_type=str,
        )
        assert entry.input_type is str
        assert entry.output_type is str

    def test_entry_with_metadata(self):
        entry = AlgorithmEntry(
            domain="test", name="test", version="1.0.0",
            algorithm=_dummy_algorithm,
            metadata=frozenset({("complexity", "O(n)"), ("author", "test")}),
        )
        assert ("complexity", "O(n)") in entry.metadata


class TestAlgorithmRegistry:
    """Tests for the AlgorithmRegistry."""

    def setup_method(self):
        self.registry = AlgorithmRegistry()

    def _make_entry(self, domain="test", name="default", version="1.0.0",
                    tags=None, algo=None):
        return AlgorithmEntry(
            domain=domain,
            name=name,
            version=version,
            algorithm=algo or _dummy_algorithm,
            tags=frozenset(tags or set()),
        )

    def test_register_and_get(self):
        entry = self._make_entry()
        self.registry.register(entry)
        retrieved = self.registry.get("test", "default")
        assert retrieved is entry
        assert retrieved.domain == "test"

    def test_get_nonexistent_raises(self):
        with pytest.raises(KeyError, match="No algorithm registered"):
            self.registry.get("nonexistent", "default")

    def test_register_duplicate_overwrites(self):
        e1 = self._make_entry(version="1.0.0")
        self.registry.register(e1)
        e2 = self._make_entry(version="2.0.0")
        self.registry.register(e2)  # Should warn but not raise
        retrieved = self.registry.get("test", "default")
        assert retrieved is e2  # Last one wins

    def test_count(self):
        assert self.registry.count == 0
        self.registry.register(self._make_entry(domain="a", name="a1"))
        self.registry.register(self._make_entry(domain="a", name="a2"))
        self.registry.register(self._make_entry(domain="b", name="b1"))
        assert self.registry.count == 3

    def test_list_all(self):
        self.registry.register(self._make_entry(domain="x", name="x1"))
        self.registry.register(self._make_entry(domain="y", name="y1"))
        all_entries = self.registry.list()
        assert len(all_entries) == 2

    def test_list_by_domain(self):
        self.registry.register(self._make_entry(domain="parsing", name="a"))
        self.registry.register(self._make_entry(domain="parsing", name="b"))
        self.registry.register(self._make_entry(domain="detection", name="c"))
        parsing_entries = self.registry.list(domain="parsing")
        assert len(parsing_entries) == 2
        detection_entries = self.registry.list(domain="detection")
        assert len(detection_entries) == 1

    def test_resolve_by_domain_and_name(self):
        entry = self._make_entry()
        self.registry.register(entry)
        resolved = self.registry.resolve(domain="test", name="default")
        assert resolved is entry

    def test_resolve_by_domain_and_tags(self):
        e1 = self._make_entry(domain="parsing", name="fast", tags={"fast"})
        e2 = self._make_entry(domain="parsing", name="slow", tags={"exact"})
        self.registry.register(e1)
        self.registry.register(e2)
        resolved = self.registry.resolve(domain="parsing", tags={"fast"})
        assert resolved is e1

    def test_resolve_no_match_raises(self):
        with pytest.raises(KeyError):
            self.registry.resolve(domain="empty")

    def test_resolve_fastest_preference(self):
        e1 = self._make_entry(domain="parsing", name="slow", tags={"exact"})
        e2 = self._make_entry(domain="parsing", name="fast", tags={"fast", "standard"})
        self.registry.register(e1)
        self.registry.register(e2)
        resolved = self.registry.resolve(domain="parsing", fastest=True)
        assert resolved is e2

    def test_resolve_most_accurate_preference(self):
        e1 = self._make_entry(domain="parsing", name="fast", tags={"fast"})
        e2 = self._make_entry(domain="parsing", name="exact", tags={"exact"})
        self.registry.register(e1)
        self.registry.register(e2)
        resolved = self.registry.resolve(domain="parsing", most_accurate=True)
        assert resolved is e2

    def test_replace(self):
        e1 = self._make_entry(version="1.0.0")
        self.registry.register(e1)
        e2 = self._make_entry(version="2.0.0")
        self.registry.replace(e2)
        retrieved = self.registry.get("test", "default")
        assert retrieved.version == "2.0.0"

    def test_unregister(self):
        self.registry.register(self._make_entry())
        assert self.registry.count == 1
        self.registry.unregister("test", "default")
        assert self.registry.count == 0

    def test_unregister_nonexistent(self):
        """Unregistering a non-existent entry should not raise."""
        self.registry.unregister("nonexistent", "default")

    def test_clear(self):
        self.registry.register(self._make_entry(domain="a", name="a1"))
        self.registry.register(self._make_entry(domain="b", name="b1"))
        self.registry.clear()
        assert self.registry.count == 0

    def test_contains(self):
        self.registry.register(self._make_entry())
        assert ("test", "default") in self.registry
        assert ("test", "other") not in self.registry

    def test_alias_lookup(self):
        entry = self._make_entry()
        self.registry.register(entry, alias="my_algo")
        retrieved = self.registry.get("test", "default")
        assert retrieved is entry

    def test_resolve_returns_highest_version(self):
        e1 = self._make_entry(domain="x", name="a", version="1.0.0")
        e2 = self._make_entry(domain="x", name="a", version="2.0.0")
        self.registry.register(e1)
        self.registry.register(e2)
        resolved = self.registry.resolve(domain="x")
        assert resolved.version == "2.0.0"

    def test_execute_registered_algorithm(self):
        entry = self._make_entry()
        self.registry.register(entry)
        retrieved = self.registry.get("test", "default")
        result = retrieved.algorithm("hello")
        assert result == "processed: hello"

    def test_repr(self):
        assert "AlgorithmRegistry" in repr(self.registry)


class TestGlobalRegistry:
    """Tests for the global AlgorithmRegistry singleton."""

    def teardown_method(self):
        reset_global_registry()

    def test_get_global_registry(self):
        reg = get_global_registry()
        assert isinstance(reg, AlgorithmRegistry)

    def test_global_registry_is_singleton(self):
        r1 = get_global_registry()
        r2 = get_global_registry()
        assert r1 is r2

    def test_reset_global_registry(self):
        r1 = get_global_registry()
        reset_global_registry()
        r2 = get_global_registry()
        assert r1 is not r2
