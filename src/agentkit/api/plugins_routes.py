"""Expose the loaded plugin graph for obsservability"""
from __future__ import annotations
from fastapi import APIRouter
from agentkit.plugins import get_registry

router = APIRouter(prefix='/api/plugins', tags=['plugins'])

@router.get('')
def list_plugins() -> dict:
    reg = get_registry()

    return {
        'plugins': [
            {
                'name': p.name,
                'display_name': p.display_name,
                'version': p.version,
                'tools': [s.name for s in p.tools()]
            }
            for p in reg.plugins.values()
        ],
        'load_errors': reg.load_errors
    }