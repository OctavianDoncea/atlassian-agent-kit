from __future__ import annotations
import importlib
import importlib.metadata
import importlib.util
import inspect
import pkgutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from agentkit.config import Settings
from agentkit.plugins.base import IntegrationPlugin

ENTRY_POINT_GROUP = 'agentkit.plugins'

def _from_module(module: Any, source: str) -> Iterator[tuple[str, Any]]:
    attr = getattr(module, 'PLUGIN', None)

    if isinstance(attr, IntegrationPlugin):
        yield source, attr
    
    for obj in vars(module).values():
        if (
            inspect.isclass(obj)
            and issubclass(obj, IntegrationPlugin)
            and obj is not IntegrationPlugin
            and obj.__module__ == module.__name__
            and not inspect.isabstract(obj)
        ):
            yield source, obj

def _builtin_plugins() -> Iterator[tuple[str, Any]]:
    import agentkit.plugins.builtin as builtin_pkg

    for mod_info in pkgutil.iter_modules(builtin_pkg.__path__):
        module = importlib.import_module(f'{builtin_pkg.__name__}.{mod_info.name}')
        yield from _from_module(module, f'builtin:{mod_info.name}')

def _directory_plugins(plugins_dir: Path) -> Iterator[tuple[str, Any]]:
    if not plugins_dir.is_dir():
        return

    for path in sorted(plugins_dir.glob('*.py')):
        if path.name.startswith('_'):
            continue

        spec = importlib.util.spec_from_file_location(f'agentkit_ext_plugin_{path.stem}', path)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield from _from_module(module, f'dir:{path.name}')

def _entry_point_plugins() -> Iterator[tuple[str, Any]]:
    for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
        obj = ep.load()
        yield f'entry_point:{ep.name}', obj

def iter_plugin_classes(settings: Settings) -> Iterator[tuple[str, Any]]:
    yield from _builtin_plugins()
    yield from _directory_plugins(Path(settings.plugins_dir))
    yield from _entry_point_plugins()