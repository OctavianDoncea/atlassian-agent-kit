from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from agentkit.rag.ingest import ingest_documents
from agentkit.rag.retrieve import search, stats
from agentkit.rag.tool import local_rag_search

router = APIRouter(prefix='/api/rag', tags=['rag'])

class IngestBody(BaseModel):
    documents: list[dict]
    replace_source: bool = False


class SearchBody(BaseModel):
    query: str
    k: int | None = None
    sources: list[str] | None = None


@router.post('/ingest')
def ingest(body: IngestBody) -> dict:
    report = ingest_documents(body.documents, replace_source=body.replace_source)
    return {'added': report.added, 'skipped': report.skipped, 'sources': report.sources}

@router.post('/search')
def search_route(body: SearchBody) -> list[dict]:
    return local_rag_search(body.query, k=body.k) if not body.sources else [
        {'source': h.source, 'page': h.page, 'chunk_index': h.chunk_index,
         'score': round(h.score, 4), 'excerpt': h.content[:600]}
        for h in search(body.query, k=body.k, sources=body.sources)
    ]

@router.get('/stats')
def stats_route() -> dict:
    return stats()