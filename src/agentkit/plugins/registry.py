from __future__ import annotations
import inspect
from typing import Any
from pydantic import BaseModel
from agentkit import integrations
from agentkit.config import Settings, get_settings
from agentkit.errors import PluginError
from agentkit.plugins.base import IntegrationPlugin, ToolSpec
from agentkit.sdk.token import DbTokenStore

class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, IntegrationPlugin] = {}
        self._tools: dict[str, tuple[ToolSpec, IntegrationPlugin]] = {}
        self.load_errors: list[str] = []

    # Loading
    @classmethod
    def discover(cls, settings: Settings | None = None, strict: bool = True) -> 'PluginRegistry':
        reg = cls()
        reg.load(settings=settings, strict=strict)

        return reg

    def load(self, settings: Settings | None = None, strict: bool = False) -> None:
        from agentkit.plugins.discovery import iter_plugin_classes

        for source, candidate in iter_plugin_classes(settings or get_settings()):
            label = f"{source}:{getattr(candidate, '__name__', type(candidate).__name__)}"
            try:
                plugin = candidate() if inspect.isclass(candidate) else candidate
                self.register(plugin)
            except PluginError as exc:
                if strict:
                    raise
                self.load_errors.append(f'{label}: {exc}')

    def register(self, plugin: IntegrationPlugin) -> None:
        """Validate everything first -> commit only if fully valid"""
        if not getattr(plugin, 'name', ''):
            raise PluginError(f'{type(plugin).__name__} defines no `name`')
        if plugin.name in self._plugins:
            raise PluginError(f'duplicate plugin name {plugin.name!r}')

        specs = plugin.tools()
        if not specs:
            raise PluginError(f'plugin {plugin.name!r} exposes no tools')

        pending: dict[str, tuple[ToolSpec, IntegrationPlugin]] = {}
        for spec in specs:
            if not (inspect.isclass(spec.model) and issubclass(spec.model, BaseModel)):
                raise PluginError(f'{plugin.name}:{spec.name} input model is not a pydantic BaseModel')
            if not callable(spec.invoke):
                raise PluginError(f'{plugin.name}:{spec.name} invoke is not callable')
            if spec.name in self._tools or spec.name in pending:
                raise PluginError(
                    f'tool name collision: {spec.name!r} from plugin {plugin.name!r} '
                    f'(tool names are global across plugins because they share one LLM namespace)'
                )
            pending[spec.name] = (spec, plugin)
        
        self._tools.update(pending)
        self._plugins[plugin.name] = plugin

    # Views
    @property
    def plugins(self) -> dict[str, IntegrationPlugin]:
        return dict(self._plugins)

    @property
    def tool_specs(self) -> dict[str, ToolSpec]:
        return {name: spec for name, (spec, _p) in self._tools.items()}

    def tool_models(self) -> dict[str, tuple[type[BaseModel], str]]:
        return {name: (spec.model, spec.description) for name, (spec, _p) in sorted(self._tools.items())}

    def plugin_for_tool(self, tool_name: str) -> IntegrationPlugin:
        if tool_name not in self._tools:
            raise PluginError(f'unknown tool {tool_name!r}; loaded: {sorted(self._tools)}')

        return self._tools[tool_name][1]

    # Schema emission
    def openai_tools(self, overrides: dict[str, str] | None = None, active_descriptions: dict[str, str] | None = None) -> list[dict]:
        from agentkit.sdk.schema import openai_tool

        return [openai_tool(name, (overrides or {}).get(name) or (active_descriptions or {}).get(name) or spec.description, spec.model) for name, (spec, _p) in sorted(self._tools.items())]

    def parameter_definitions_tools(self, overrides: dict[str, str] | None = None, active_descriptions: dict[str, str] | None = None) -> list[dict]:
        from agentkit.sdk.schema import parameter_definitions_tool

        return [parameter_definitions_tool(name, (overrides or {}).get(name) or (active_descriptions or {}).get(name) or spec.description, spec.model) for name, (spec, _p) in sorted(self._tools.items())]

    # Clients & dispatch
    def make_clients(self, *, auth_mode: str = 'basic', transport: Any = None, settings: Settings | None = None, concurrency: int = 8) -> dict[str, Any]:
        from agentkit.db.models import Integration
        from agentkit.db.session import SessionLocal
        from agentkit.sdk.auth import AuthManager
        from agentkit.sdk.token import DbTokenStore

        settings = settings or get_settings()
        cloud_ids: dict[str, str | None] = {}
        token_store = auth_manager = None

        if auth_mode == 'oauth':
            with SessionLocal() as db:
                cloud_ids = {row.name: row.cloud_id for row in db.query(Integration).all()}
            token_store = DbTokenStore()
            auth_manager = AuthManager(settings=settings)

        clients: dict[str, Any] = {}
        for name, plugin in self._plugins.items():
            clients[name] = plugin.create_client(
                auth_mode = auth_mode,
                cloud_id = cloud_ids.get(name),
                transport = transport,
                settings = settings,
                concurrency = concurrency,
                token_store = token_store,
                auth_manager = auth_manager
            )
            
        return clients

    def execute_tool(self, tool_name: str, arguments: dict | None, clients: dict[str, Any]) -> Any:
        spec, plugin = self._tools.get(tool_name, (None, None))
        if spec is None:
            raise PluginError(f'unknown tool {tool_name!r}; loaded: {sorted(self._tools)}')

        client = clients.get(plugin.name)
        if client is None:
            raise PluginError(f'no client built for plugin {plugin.name!r}')

        validated = spec.model(**(arguments or {}))

        return spec.invoke(client, validated)