"""Tests for the DatasetRegistry."""

import json
import tempfile
from pathlib import Path

import pytest

from chemengine.core.datasets import (
    Dataset,
    DatasetRegistry,
    get_global_dataset_registry,
    reset_global_datasets,
)


class TestDataset:
    """Tests for the Dataset dataclass."""

    def test_create_dataset(self):
        ds = Dataset(
            name="elements",
            version="1.0.0",
            source="/path/to/elements.json",
            schema={},
            data={"C": {"mass": 12.011}},
        )
        assert ds.name == "elements"
        assert ds.data["C"]["mass"] == 12.011

    def test_dataset_immutable(self):
        ds = Dataset(name="t", version="1", source="s", schema={}, data={})
        with pytest.raises((AttributeError, TypeError, Exception)):
            ds.name = "changed"


class TestDatasetRegistry:
    """Tests for the DatasetRegistry."""

    def setup_method(self):
        reset_global_datasets()
        self.tmpdir = tempfile.mkdtemp()
        self.registry = DatasetRegistry(self.tmpdir)

    def _create_json_dataset(self, name: str, data: dict, version: str = "1.0.0"):
        path = Path(self.tmpdir) / f"{name}.json"
        full = {"_version": version, **data}
        with open(path, "w") as f:
            json.dump(full, f)
        return path

    def test_empty_registry(self):
        assert self.registry.count == 0
        assert self.registry.list_loaded() == []

    def test_load_json(self):
        self._create_json_dataset("test_data", {"key": "value"})
        ds = self.registry.load("test_data")
        assert ds.name == "test_data"
        assert ds.data["key"] == "value"

    def test_get_cached(self):
        self._create_json_dataset("cached", {"val": 42})
        ds1 = self.registry.get("cached")
        ds2 = self.registry.get("cached")
        assert ds1 is ds2  # Same cached object

    def test_get_value(self):
        self._create_json_dataset("elements", {"C": {"mass": 12.011}})
        val = self.registry.get_value("elements", "C")
        assert val["mass"] == 12.011

    def test_get_value_non_dict_raises(self):
        ds = Dataset(name="list", version="1", source="s", schema={}, data=[1, 2, 3])
        self.registry.register(ds)
        with pytest.raises(TypeError):
            self.registry.get_value("list", "key")

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError, match="Dataset 'missing' not found"):
            self.registry.load("missing")

    def test_list_available(self):
        self._create_json_dataset("a", {"v": 1})
        self._create_json_dataset("b", {"v": 2})
        available = self.registry.list_available()
        assert "a" in available
        assert "b" in available

    def test_register_programmatically(self):
        ds = Dataset(
            name="custom",
            version="2.0.0",
            source="memory",
            schema={},
            data={"custom": "data"},
        )
        self.registry.register(ds)
        assert self.registry.count == 1
        retrieved = self.registry.get("custom")
        assert retrieved.version == "2.0.0"

    def test_reload(self):
        self._create_json_dataset("reloadable", {"val": 1})
        self.registry.load("reloadable")

        # Update the file
        path = Path(self.tmpdir) / "reloadable.json"
        with open(path, "w") as f:
            json.dump({"_version": "2.0.0", "val": 2}, f)

        ds = self.registry.reload("reloadable")
        assert ds.version == "2.0.0"
        assert ds.data["val"] == 2

    def test_reload_notifies_watchers(self):
        self._create_json_dataset("watched", {"val": 1})
        self.registry.load("watched")
        notifications: list[Dataset] = []
        self.registry.on_change("watched", lambda ds: notifications.append(ds))

        path = Path(self.tmpdir) / "watched.json"
        with open(path, "w") as f:
            json.dump({"_version": "2", "val": 2}, f)

        self.registry.reload("watched")
        assert len(notifications) == 1
        assert notifications[0].data["val"] == 2

    def test_clear(self):
        self._create_json_dataset("a", {"v": 1})
        self.registry.load("a")
        assert self.registry.count == 1
        self.registry.clear()
        assert self.registry.count == 0

    def test_version_metadata_removed(self):
        """The _version key should be popped from data."""
        self._create_json_dataset("with_meta", {"value": 1})
        ds = self.registry.load("with_meta")
        assert "_version" not in ds.data

    def test_repr(self):
        assert "DatasetRegistry" in repr(self.registry)


class TestGlobalDatasetRegistry:
    """Tests for the global DatasetRegistry singleton."""

    def teardown_method(self):
        reset_global_datasets()

    def test_get_global(self):
        reg = get_global_dataset_registry()
        assert isinstance(reg, DatasetRegistry)

    def test_global_is_singleton(self):
        r1 = get_global_dataset_registry()
        r2 = get_global_dataset_registry()
        assert r1 is r2

    def test_reset(self):
        r1 = get_global_dataset_registry()
        reset_global_datasets()
        r2 = get_global_dataset_registry()
        assert r1 is not r2
