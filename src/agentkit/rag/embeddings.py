"""Local embeddings via Ollama; injectable client for tests."""
from __future__ import annotations
import hashlib
import json
import math
import urllib.request
from agentkit.config import get_settings

class RAGError(Exception):
    pass


def _tokens(text: str) -> list[str]:
    return [t for t in text.lower().replace('.', ' ').replace(',', ' ').split() if len(t) > 2]

def hash_embed(text: str, dim: int | None = None) -> list[float]:
    """Deterministic bag-of-words hash embedding."""
    dim = dim or get_settings().rag_embed_dim
    vec = [0.0] * dim

    for tok in _tokens(text):
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0

    norm = math.sqrt(sum(v * v for v in vec))

    return [v / norm for v in vec]

def _ollama_embed(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    payload = json.dumps({'model': settings.rag_embed_model, 'input': texts}).encode()
    req = urllib.request.Request(f'{settings.ollama_base_url}/api/embed', data=payload, headers={'Content-Type': 'application/json'})

    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp)['embeddings']

def embed_texts(texts: list[str], client=None, allow_fallback: bool | None = None) -> list[list[float]]:
    if not texts:
        return []

    if client is not None:
        return client(texts)

    try:
        return _ollama_embed(texts)
    except Exception:
        fallback = get_settings().rag_allow_hash_fallback if allow_fallback is None else allow_fallback

        if not fallback:
            raise RAGError('Ollama embeddings unavailable and hash fallback disabled.')

        return [hash_embed(text) for text in texts]

def embed_query(text: str, client=None) -> list[float]:
    return embed_texts([text], client=client)[0]