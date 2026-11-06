from __future__ import annotations
from agentkit.rag.retrieve import search

TOOL_SCHEMA = {
    'type': 'function',
    'function': {
        'name': 'local_rag_search',
        'description': 'Search the internal document corpus (indexed in pgvector) and return cited excerpts with source, page, and cosine similarity score.',
        'parameters': {
            'type': 'object',
            'properties': {'query': {'type': 'string'}, 'k': {'type': 'integer'}},
            'required': ['query']
        }
    }
}

def local_rag_search(query: str, k: int | None = None, client=None) -> list[dict]:
    hits = search(query, k=k, client=client)

    return [{'source': h.source, 'page': h.page, 'chunk_index': h.chunk_index, 'score': round(h.score, 4), 'excerpt': h.content[:600]} for h in hits]