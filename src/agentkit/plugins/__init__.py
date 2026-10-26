from agentkit.plugins.base import IntegrationPlugin, ToolSpec
from agentkit.plugins.registry import PluginRegistry

_registry: PluginRegistry | None = None

def get_registry(reload: bool = False, settings = None) -> PluginRegistry:
    global _registry
    if _registry is None or reload:
        _registry = PluginRegistry.discover(settings=settings)

    return _registry

__all__ = ['IntegrationPlugin', 'ToolSpec', 'PluginRegistry', 'get_registry']