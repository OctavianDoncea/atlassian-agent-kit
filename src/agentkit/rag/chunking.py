"""Recursive character chunking with overlap and content-hash dedupe."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from agentkit.config import get_settings

SEPARATORS = ['\n\n', '\n', '. ', ' ', '']

@dataclass
class Chunk:
    source: str
    content: str
    page: int | None = None
    chunk_index: int = 0
    content_hash: str = ''
    token_count: int = 0


def _split(text: str, size: int, sep_idx: int = 0) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []

    sep = SEPARATORS[sep_idx]
    parts = text.split(sep) if sep else list(text)
    out: list[str] = []
    buf = ''

    for p in parts:
        candidate = p if not buf else buf + sep + p

        if len(candidate) <= size:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            if len(p) > size:
                out.extend(_split(p, size, sep_idx + 1))
            else:
                buf = p
    
    if buf:
        out.append(buf)

    return out

def chunk_document(source: str, text: str, page: int | None = None, size: int | None = None, overlap: int | None = None) -> list[Chunk]:
    settings = get_settings()
    size = size or settings.rag_chunk_size
    overlap = overlap or settings.rag_chunk_overlap
    raw = _split(text, size)
    chunks: list[Chunk] = []

    for i, piece in enumerate(raw):
        if i > 0 and overlap:
            piece = raw[i-1][-overlap:] + piece
        
        content = piece.strip()
        if not content:
            continue

        chunks.append(Chunk(
            source=source, content=content, page=page, chunk_index=i, content_hash=hashlib.sha256(content.encode()).hexdigest(),
            token_count=max(1, len(content) // 4)
        ))

    return chunks