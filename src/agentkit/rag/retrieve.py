from __future__ import annotations
from dataclasses import dataclass
from agentkit.config import get_settings
from agentkit.db.models import DocumentChunk
from agentkit.db.session import SessionLocal
from agentkit.rag.embeddings import embed_query

@dataclass
class Hit:
    source: str
    content: str
    score: float
    page: int | None = None
    chunk_index: int = 0


def search(query: str, k: int | None = None, sources: list[str] | None = None, min_score: float = 0.0, client = None) -> list[Hit]:
    k = k or get_settings().rag_top_k
    qvec = embed_query(query, client=client)

    with SessionLocal() as db:
        q = db.query(DocumentChunk, DocumentChunk.embedding.cosine_distance(qvec).label('dist'))

        if sources:
            q = q.filter(DocumentChunk.source.in_(sources))

        rows = q.order_by('dist').limit(k).all()

    hits = []
    
    for chunk, dist in rows:
        score = 1.0 - float(dist)
        if score >= min_score:
            hits.append(Hit(source=chunk.source, content=chunk.content, score=score, page=chunk.page, chunk_index=chunk.chunk_index))

    return hits

def stats() -> dict:
    with SessionLocal() as db:
        chunks = db.query(DocumentChunk).count()
        sources = db.query(DocumentChunk.source).distinct().count()

    return {'chunks': chunks, 'sources': sources, 'embed_model': get_settings().rag_embed_model}