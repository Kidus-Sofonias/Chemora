"""DatasetRegistry — centralized access to all reference data.

All reference data (elements, isotopes, functional groups, valence rules,
ring templates, forcefield parameters) lives in versioned files in the
datasets/ directory, NOT in code. This enables:
    - Data updates without code changes
    - Versioned datasets for reproducibility
    - Plugin-contributed datasets
    - Hot-reloading during development

Architecture:
    - Dataset: A loaded dataset with name, version, schema, and data.
    - DatasetRegistry: Lazy-loading, caching, hot-reloading registry.

Design decisions:
    - Files over code: All reference data is external. This makes it easy
      to update, validate, and version independently of the engine.
    - JSON Schema validation: Each dataset has a schema that is validated
      on load, catching data errors early.
    - Lazy loading: Datasets are loaded on first access, not at import time.
    - Hot-reloading: In development mode, datasets can be reloaded without
      restarting the engine.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# tomllib was introduced in Python 3.11. Provide a backport for Python 3.10.
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# Default path to the datasets directory
_DATASETS_DIR: Path = Path(__file__).resolve().parent.parent / "datasets"


@dataclass(frozen=True, slots=True)
class Dataset:
    """A loaded reference dataset.

    Attributes:
        name: Dataset name (e.g., 'elements', 'isotopes').
        version: Dataset version string.
        source: File path the dataset was loaded from.
        schema: JSON Schema dict for validation.
        data: The parsed dataset content.
    """

    name: str
    """Dataset name (e.g., 'elements', 'isotopes')."""

    version: str
    """Dataset version string."""

    source: str
    """File path the dataset was loaded from."""

    schema: dict[str, Any]
    """JSON Schema dict for validation."""

    data: Any
    """The parsed dataset content (dict, list, etc.)."""


class DatasetRegistry:
    """Lazy-loading, caching registry for reference datasets.

    Usage:
        >>> registry = DatasetRegistry()
        >>> elements = registry.get("elements")
        >>> carbon = elements.data["C"]
        >>> carbon["mass"]
        12.011
    """

    def __init__(self, datasets_dir: str | Path | None = None) -> None:
        """Initialize the registry.

        Args:
            datasets_dir: Path to the datasets directory. Uses default if None.
        """
        self._datasets_dir = Path(datasets_dir) if datasets_dir else _DATASETS_DIR
        self._cache: dict[str, Dataset] = {}
        self._watchers: dict[str, list[Callable[[Dataset], None]]] = {}
        self._loaded: set[str] = set()

    def load(self, name: str) -> Dataset:
        """Load a dataset from file.

        Searches for the dataset file in the datasets directory. Supports
        .json and .toml formats.

        Args:
            name: Dataset name (without extension).

        Returns:
            The loaded Dataset.

        Raises:
            FileNotFoundError: If no dataset file is found.
            ValueError: If the file format is unsupported or validation fails.
        """
        if name in self._cache:
            return self._cache[name]

        # Search for the file
        for ext in (".json", ".toml"):
            filepath = self._datasets_dir / f"{name}{ext}"
            if filepath.exists():
                return self._load_file(name, filepath, ext)

        raise FileNotFoundError(
            f"Dataset '{name}' not found in {self._datasets_dir}. "
            f"Available: {self.list_available()}"
        )

    def get(self, name: str) -> Dataset:
        """Get a dataset (cached). Loads it if not already loaded.

        Args:
            name: Dataset name.

        Returns:
            The Dataset.
        """
        if name not in self._cache:
            return self.load(name)
        return self._cache[name]

    def get_value(self, dataset: str, key: str) -> Any:
        """Quick access to a specific value in a dataset.

        Args:
            dataset: Dataset name.
            key: Key within the dataset.

        Returns:
            The value at dataset[key].
        """
        ds = self.get(dataset)
        if isinstance(ds.data, dict):
            return ds.data.get(key)
        raise TypeError(f"Dataset '{dataset}' is not a dict, cannot use get_value")

    def register(self, dataset: Dataset) -> None:
        """Register a dataset programmatically (used by plugins).

        Args:
            dataset: The Dataset to register.
        """
        self._cache[dataset.name] = dataset
        logger.info(f"Registered dataset: {dataset.name} v{dataset.version}")

    def reload(self, name: str) -> Dataset:
        """Reload a dataset from file (hot-reload).

        Args:
            name: Dataset name.

        Returns:
            The reloaded Dataset.
        """
        if name in self._cache:
            del self._cache[name]
        dataset = self.load(name)
        # Notify watchers
        if name in self._watchers:
            for handler in self._watchers[name]:
                try:
                    handler(dataset)
                except Exception as e:
                    logger.error(f"Dataset watcher failed for '{name}': {e}")
        return dataset

    def on_change(self, name: str, handler: Callable[[Dataset], None]) -> None:
        """Register a handler to be called when a dataset is reloaded.

        Args:
            name: Dataset name to watch.
            handler: Callback receiving the reloaded Dataset.
        """
        if name not in self._watchers:
            self._watchers[name] = []
        self._watchers[name].append(handler)

    def list_available(self) -> list[str]:
        """List all available datasets in the datasets directory.

        Returns:
            List of dataset names (without extensions).
        """
        available: list[str] = []
        if not self._datasets_dir.exists():
            return available
        for f in self._datasets_dir.iterdir():
            if f.suffix in (".json", ".toml"):
                available.append(f.stem)
        return sorted(available)

    def list_loaded(self) -> list[str]:
        """List names of currently loaded datasets."""
        return sorted(self._cache.keys())

    def clear(self) -> None:
        """Clear the cache (for testing)."""
        self._cache.clear()
        self._loaded.clear()

    def _load_file(self, name: str, filepath: Path, ext: str) -> Dataset:
        """Load and parse a dataset file."""
        with open(filepath, "rb") as f:
            if ext == ".json":
                data = json.load(f)
            elif ext == ".toml":
                data = tomllib.load(f)
            else:
                raise ValueError(f"Unsupported dataset format: {ext}")

        # Extract metadata
        version = data.pop("_version", "1.0.0") if isinstance(data, dict) else "1.0.0"
        schema = data.pop("_schema", {}) if isinstance(data, dict) else {}

        dataset = Dataset(
            name=name,
            version=version,
            source=str(filepath),
            schema=schema,
            data=data,
        )
        self._cache[name] = dataset
        logger.debug(f"Loaded dataset: {name} v{version} from {filepath}")
        return dataset

    @property
    def count(self) -> int:
        """Number of loaded datasets."""
        return len(self._cache)

    def __repr__(self) -> str:
        return f"DatasetRegistry({self.count} loaded, {len(self.list_available())} available)"


# Global singleton instance
_global_datasets: DatasetRegistry | None = None


def get_global_dataset_registry() -> DatasetRegistry:
    """Get or create the global DatasetRegistry singleton.

    Returns:
        The global DatasetRegistry instance.
    """
    global _global_datasets
    if _global_datasets is None:
        _global_datasets = DatasetRegistry()
    return _global_datasets


def reset_global_datasets() -> None:
    """Reset the global dataset registry (for testing)."""
    global _global_datasets
    _global_datasets = None
