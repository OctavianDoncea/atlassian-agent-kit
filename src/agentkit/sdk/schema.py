from __future__ import annotations
import json
from typing import Any
from pydantic import BaseModel

def _resolve_refs(schema: dict) -> dict:
    defs = schema.pop('$defs', None) or schema.pop('definitions', None) or {}
    if not defs:
        return schema

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if set(node.keys()) == {'$ref'}:
                name = node['$ref'].split('/')[-1]
                return walk(json.loads(json.dumps(defs.get(name, {}))))
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)

def parameters_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    resolved = _resolve_refs(schema)
    resolved.pop('title', None)
    return resolved

def openai_tool(name: str, description: str, model: type[BaseModel]) -> dict:
    return {
        'type': 'function',
        'function': {'name': name, 'description': description, 'parameters': parameters_schema(model)}
    }

def _prop_type(prop: dict) -> str:
    if 'anyOf' in prop:
        types = [v.get('type') for v in prop['anyOf'] if isinstance(v, dict) and v.get('type') != 'null']
        if types:
            return types[0]
    t = prop.get('type', 'string')
    if isinstance(t, list):
        t = next((x for x in t if x != 'null'), 'string')
    return t

_PARAM_TYPE_MAP = {
    'string': 'string',
    'integer': 'integer',
    'number': 'float',
    'boolean': 'boolean',
    'array': 'list',
    'object': 'object'
}

def parameter_definitions_tool(name: str, description: str, model: type[BaseModel]) -> dict:
    params = parameters_schema(model)
    required = set(params.get('required', []))
    definitions: dict[str, Any] = {}

    for prop_name, prop in params.get('properties', {}).items():
        definitions[prop_name] = {
            'type': _PARAM_TYPE_MAP.get(_prop_type(prop), 'string'),
            'required': prop_name in required,
            'description': prop.get('description', '')
        }

    return {'name': name, 'description': description, 'parameter_definitions': definitions}