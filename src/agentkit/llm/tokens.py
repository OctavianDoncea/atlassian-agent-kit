"""Token estimation: tiktoken when available, char heuristic when not (offline-safe)."""
from __future__ import annotations
import json
from typing import Any

_encoder = None

def get_encoder():
    global _encoder
    if _encoder is None:
        import tiktoken  

        _encoder = tiktoken.get_encoding('cl100k_base')
    
    return _encoder

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    
    try:
        return len(get_encoder().encode(text, disallowed_special=()))
    except Exception:
        return max(1, len(text) // 4)

def estimate_messages_tokens(messages: list[dict]) -> int:
    total = 0
    
    for message in messages:
        total += 4
        content = message.get('content')
        if isinstance(content, str):
            total += estimate_tokens(content)
    
    return total

def estimate_message_tokens(message: Any) -> int:
    total = estimate_tokens(getattr(message, 'content', '') or '')
    
    for tool_call in getattr(message, 'tool_calls', None) or []:
        name = getattr(getattr(tool_call, 'function', None), 'name', '') or ''
        arguments = getattr(getattr(tool_call, 'function', None), 'arguments', '') or ''
        total += estimate_tokens(name + arguments)
    
    return total

def estimate_tools_tokens(tools: list[dict] | None) -> int:
    return estimate_tokens(json.dumps(tools)) if tools else 0