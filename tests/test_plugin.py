"""Tests for the PluginManager and PluginProtocol."""


from chemengine.core.events import reset_global_bus
from chemengine.core.plugin import PluginManager


class _TestPlugin:
    """A minimal plugin for testing."""

    @property
    def name(self) -> str:
        return "test-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[str]:
        return []

    def __init__(self):
        self.loaded = False
        self.unloaded = False
        self.engine = None

    def on_load(self, engine) -> None:
        self.loaded = True
        self.engine = engine

    def on_unload(self) -> None:
        self.unloaded = True


class TestPluginManager:
    """Tests for the PluginManager."""

    def setup_method(self):
        reset_global_bus()
        self.mgr = PluginManager()

    def test_initial_state(self):
        assert self.mgr.count == 0
        assert self.mgr.list_loaded() == []

    def test_discover_no_plugins(self):
        """Discover when no plugins are installed returns empty list."""
        plugins = self.mgr.discover()
        assert plugins == [], f"Expected empty plugin list, got {plugins}"

    def test_is_loaded_false_for_unloaded(self):
        assert not self.mgr.is_loaded("test-plugin")

    def test_unload_not_loaded_does_not_raise(self):
        """Unloading a non-existent plugin should not raise."""
        self.mgr.unload("nonexistent")

    def test_repr(self):
        assert "PluginManager" in repr(self.mgr)

    def test_load_and_unload_cycle(self):
        """Manually add a plugin info to simulate load/unload."""
        from chemengine.core.plugin import PluginInfo

        plugin = _TestPlugin()
        # Manually add to test the internals
        self.mgr._plugins["test-plugin"] = PluginInfo(
            name="test-plugin",
            version="1.0.0",
            entry_point=None,  # type: ignore[arg-type]
            instance=plugin,
        )
        assert self.mgr.is_loaded("test-plugin")
        assert self.mgr.count == 1

        self.mgr.unload("test-plugin")
        assert not self.mgr.is_loaded("test-plugin")
        assert self.mgr.count == 0
        assert plugin.unloaded

    def test_list_loaded(self):
        from chemengine.core.plugin import PluginInfo

        plugin = _TestPlugin()
        self.mgr._plugins["test-plugin"] = PluginInfo(
            name="test-plugin",
            version="1.0.0",
            entry_point=None,  # type: ignore[arg-type]
            instance=plugin,
        )
        loaded = self.mgr.list_loaded()
        assert len(loaded) == 1
        assert loaded[0].name == "test-plugin"

    def test_load_all_with_no_plugins(self):
        """load_all with no discovered plugins returns empty list."""
        result = self.mgr.load_all(None)
        assert result == []


class TestPluginProtocol:
    """Tests that the PluginProtocol is structurally sound."""

    def test_plugin_protocol_attributes(self):
        """Ensure a valid plugin has the required attributes."""
        plugin = _TestPlugin()
        assert hasattr(plugin, "name")
        assert hasattr(plugin, "version")
        assert hasattr(plugin, "dependencies")
        assert hasattr(plugin, "on_load")
        assert hasattr(plugin, "on_unload")

    def test_plugin_lifecycle(self):
        """Simulate the plugin lifecycle."""
        plugin = _TestPlugin()
        assert not plugin.loaded
        assert not plugin.unloaded

        plugin.on_load("engine")
        assert plugin.loaded
        assert plugin.engine == "engine"

        plugin.on_unload()
        assert plugin.unloaded
