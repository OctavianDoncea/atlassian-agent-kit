from pydantic import BaseModel, Field
from agentkit.sdk.schema import parameter_definitions_tool, openai_tool

class Demo(BaseModel):
    q: str = Field(description='search query')
    limit: int = Field(10, ge=1, description='max rows')
    tag: str | None = Field(None, description='optional tag')


def test_openai_tool_shape():
    tool = openai_tool('demo', 'does things', Demo)
    assert tool['type'] == 'function'
    fn = tool['function']
    assert fn['name'] == 'demo' and fn['description'] == 'does things'
    assert fn['parameters']['required'] == ['q']
    assert set(fn['parameters']['properties']) == {'q', 'limit', 'tag'}

def test_parameter_definitions_tool_shape():
    tool = parameter_definitions_tool('demo', 'does things', Demo)
    pd = tool['parameter_definitions']
    assert pd['q'] == {'type': 'string', 'required': True, 'description': 'search query'}
    assert pd['limit']['type'] == 'integer' and pd['limit']['required'] is False
    assert pd['tag']['type'] == 'string' and pd['tag']['required'] is False