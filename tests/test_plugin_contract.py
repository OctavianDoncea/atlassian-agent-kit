import textwrap
import pytest
from pydantic import BaseModel
from agentkit.config import Settings
from agentkit.errors import PluginError
from agentkit.plugins import get_registry
from agentkit.plugins.base import IntegrationPlugin, ToolSpec
from agentkit.plugins.registry import PluginRegistry
from agentkit.sdk.schema import openai_tool

REG = get_registry()

@pytest.mark.parametrize('plugin', REG.plugins.values(), ids=lambda p: p.name)
def test_plugin_contract(plugin: IntegrationPlugin):
    assert plugin.name and plugin.display_name and plugin.version
    specs = plugin.tools()
    assert specs, f'{plugin.name} exposes no tools'
    names = [s.name for s in specs]
    assert len(names) == len(set(names)), f'{plugin.name} has duplicate tool names'

    for spec in specs:
        assert issubclass(spec.model, BaseModel)
        assert callable(spec.invoke)
        tool = openai_tool(spec.name, spec.description, spec.model)
        assert tool['function']['parameters'].get('type') == 'object'

def test_builtin_and_external_loaded():
    assert {'jira', 'confluence', 'time'} <= set(REG.plugins)

def test_global_tool_name_uniqueness():
    names = list(REG.tool_specs)
    assert len(names) == len(set(names))

def test_execute_tool_validates_input():
    clients = {'time': REG.plugins['time']}
    out = REG.execute_tool('get_current_time', {'timezone': 'UTC'}, clients)
    assert out['timezone'] == 'UTC'
    with pytest.raises(Exception):
        REG.execute_tool('get_current_time', {'timezone': 12345}, clients)

def test_external_directory_discovery(tmp_path):
    (tmp_path / 'echo_ext.py').write_text(textwrap.dedent("""
        from pydantic import BaseModel
        from agentkit.plugins.base import IntegrationPlugin, ToolSpec

        class EchoInput(BaseModel):
            text: str


        class EchoPlugin(IntegrationPlugin):
            name = "echo_ext"
            display_name = "Echo external"
            version = "0.1.0"

            def tools(self):
                return [ToolSpec("echo_ext_once", "Echo text back", EchoInput, lambda c, i: {"echo": i.text})]
    """))
    reg = PluginRegistry.discover(Settings(_env_file=None, plugins_dir=str(tmp_path)))
    assert 'echo_ext' in reg.plugins
    assert 'echo_ext_once' in reg.tool_specs
    assert reg.execute_tool('echo_ext_once', {'text': 'hi'}, {'echo_ext': reg.plugins['echo_ext']}) == {'echo': 'hi'}

def test_tool_name_collision_rejected():
    class _M(BaseModel):
        c: int = 1

    class A(IntegrationPlugin):
        name = 'a'
        def tools(self):
            return [ToolSpec('shared_tool', 'd', _M, lambda c, i: None)]


    class B(IntegrationPlugin):
        name = 'b'
        def tools(self):
            return [ToolSpec('shared_tool', 'd', _M, lambda c, i: None)]

    reg = PluginRegistry()
    reg.register(A())

    with pytest.raises(PluginError, match='collision'):
        reg.register(B())

    assert 'b' not in reg.plugins