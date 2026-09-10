"""Plugin architecture for the chemistry engine.

Plugins are discoverable Python packages that extend the engine's capabilities.
They can register new algorithms, datasets, event handlers, and tools.

Discovery uses Python's standard `importlib.metadata.entry_points` mechanism
under the `chemengine.plugins` group. Any installed package can declare itself
as a plugin without modifying the engine's code.

Architecture:
    - PluginProtocol: The contract that every plugin must implement.
    - PluginManager: Discovers, loads, and manages plugins.
    - Entry point discovery: Uses importlib.metadata to find plugins.

Design decisions:
    - Protocol-based: Uses structural subtyping (Protocol) rather than
      inheritance (ABC). This allows plugins to be simple modules or classes.
    - Entry point discovery: No central plugin registry file to maintain.
      Plugins are discovered automatically from installed packages.
    - Lifecycle hooks: on_load() and on_unload() enable clean setup/teardown.
    - Engine API injection: Plugins receive the full ChemEngineAPI on load,
      giving them access to registry, event bus, datasets, and tools.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PluginProtocol(Protocol):
    """The contract that every plugin must implement.

    A plugin is any object with name, version, dependencies, on_load(),
    and on_unload(). The on_load() method receives the ChemEngineAPI
    instance, which it can use to register algorithms, subscribe to events,
    register datasets, and add tools.

    Usage:
        >>> class MyPlugin:
        ...     @property
        ...     def name(self) -> str: return "my-plugin"
        ...     @property
        ...     def version(self) -> str: return "1.0.0"
        ...     @property
        ...     def dependencies(self) -> list[str]: return []
        ...     def on_load(self, engine): ...
        ...     def on_unload(self): ...
    """

    @property
    def name(self) -> str:
        """Human-readable plugin name."""
        ...

    @property
    def version(self) -> str:
        """Plugin version string (SemVer)."""
        ...

    @property
    def dependencies(self) -> list[str]:
        """List of Python package dependencies."""
        ...

    def on_load(self, engine: Any) -> None:
        """Called when the plugin is loaded.

        Args:
            engine: The ChemEngineAPI instance for registering algorithms,
                subscribing to events, registering datasets, and adding tools.
        """
        ...

    def on_unload(self) -> None:
        """Called when the plugin is unloaded. Clean up resources here."""
        ...


@dataclass
class PluginInfo:
    """Information about a loaded plugin.

    Attributes:
        name: Plugin name.
        version: Plugin version.
        entry_point: The entry point that was used to load the plugin.
        instance: The loaded plugin instance.
    """

    name: str
    version: str
    entry_point: EntryPoint
    instance: PluginProtocol


class PluginManager:
    """Discovers, loads, and manages plugins.

    Usage:
        >>> mgr = PluginManager()
        >>> plugins = mgr.discover()
        >>> for p in plugins:
        ...     mgr.load(p.name, engine_api)
        >>> mgr.load_all(engine_api)
    """

    def __init__(self) -> None:
        self._plugins: dict[str, PluginInfo] = {}
        self._entry_points: list[EntryPoint] = []

    def discover(self) -> list[EntryPoint]:
        """Discover all installed plugins via entry points.

        Scans the `chemengine.plugins` entry point group for all installed
        packages that declare themselves as plugins.

        Returns:
            List of discovered EntryPoint objects.
        """
        try:
            eps = entry_points(group="chemengine.plugins")
            self._entry_points = list(eps)
            logger.info(f"Discovered {len(self._entry_points)} plugin(s)")
            return self._entry_points
        except Exception as e:
            logger.warning(f"Failed to discover plugins: {e}")
            return []

    def load(self, name: str, engine: Any) -> PluginProtocol:
        """Load a specific plugin by name.

        Args:
            name: The plugin name (as declared in entry_points).
            engine: The ChemEngineAPI instance to pass to on_load().

        Returns:
            The loaded plugin instance.

        Raises:
            KeyError: If no plugin with that name is discovered.
            ImportError: If the plugin module cannot be imported.
        """
        if name in self._plugins:
            logger.debug(f"Plugin '{name}' already loaded")
            return self._plugins[name].instance

        # Find the entry point
        ep = self._find_entry_point(name)
        if ep is None:
            raise KeyError(f"Plugin '{name}' not found in discovered entry points")

        # Load the plugin module
        try:
            plugin_cls = ep.load()
            instance = plugin_cls() if isinstance(plugin_cls, type) else plugin_cls
        except Exception as e:
            raise ImportError(f"Failed to load plugin '{name}': {e}") from e

        # Call on_load
        try:
            instance.on_load(engine)
        except Exception as e:
            logger.error(f"Plugin '{name}' on_load failed: {e}")
            raise

        # Store
        info = PluginInfo(
            name=instance.name,
            version=instance.version,
            entry_point=ep,
            instance=instance,
        )
        self._plugins[name] = info
        logger.info(f"Loaded plugin: {instance.name} v{instance.version}")

        # Publish event
        try:
            from chemengine.core.events import Event, EventType, get_global_bus
            bus = get_global_bus()
            bus.publish(Event(
                type=EventType.PLUGIN_LOADED,
                payload={"name": instance.name, "version": instance.version},
                source="plugin_manager",
            ))
        except Exception:
            pass

        return instance

    def load_all(self, engine: Any) -> list[PluginProtocol]:
        """Load all discovered plugins.

        Args:
            engine: The ChemEngineAPI instance.

        Returns:
            List of successfully loaded plugin instances.
        """
        if not self._entry_points:
            self.discover()

        loaded: list[PluginProtocol] = []
        for ep in self._entry_points:
            try:
                instance = self.load(ep.name, engine)
                loaded.append(instance)
            except Exception as e:
                logger.warning(f"Failed to load plugin '{ep.name}': {e}")

        logger.info(f"Loaded {len(loaded)}/{len(self._entry_points)} plugins")
        return loaded

    def unload(self, name: str) -> None:
        """Unload a plugin.

        Args:
            name: The plugin name.
        """
        if name not in self._plugins:
            logger.warning(f"Plugin '{name}' is not loaded")
            return

        info = self._plugins[name]
        try:
            info.instance.on_unload()
        except Exception as e:
            logger.error(f"Plugin '{name}' on_unload failed: {e}")

        del self._plugins[name]
        logger.info(f"Unloaded plugin: {name}")

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded."""
        return name in self._plugins

    def list_loaded(self) -> list[PluginInfo]:
        """List all currently loaded plugins."""
        return list(self._plugins.values())

    def _find_entry_point(self, name: str) -> EntryPoint | None:
        """Find an entry point by name."""
        for ep in self._entry_points:
            if ep.name == name:
                return ep
        return None

    @property
    def count(self) -> int:
        """Number of loaded plugins."""
        return len(self._plugins)

    def __repr__(self) -> str:
        return f"PluginManager({self.count} loaded, {len(self._entry_points)} discovered)"
