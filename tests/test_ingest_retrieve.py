import pytest
from agentkit.db.models import DocumentChunk
from agentkit.db.session import SessionLocal
from agentkit.rag.embeddings import hash_embed
from agentkit.rag.ingest import ingest_documents
from agentkit.rag.retrieve import search, stats
from agentkit.rag.tool import local_rag_search

CLIENT = lambda texts: [hash_embed(t) for t in texts]
CORPUS = [
    {'source': 'accounting.md', 'content': 'Journal entries must balance: total debits equal total credits '
     'before posting. Unbalanced or low-confidence entries are held for human review instead of auto-posting.'},
    {'source': 'search.md', 'content': 'Web search uses multiple providers and reranks excerpts to strengthen '
     'retrieval results across the research pipeline.'},
    {'source': 'auth.md', 'content': 'Sessions are private by default with optional public share links and '
     'PostgreSQL-backed history.'},
]

def _cleanup():
    with SessionLocal() as db:
        db.query(DocumentChunk).delete()
        db.commit()

def test_ingest_and_retrieve_top_hit():
    _cleanup()
    try:
        report = ingest_documents(CORPUS, client=CLIENT)
        assert report.added >= 3 and report.skipped == 0
        hits = search('debits equal credits balancing journal entries', k=2, client=CLIENT)
        assert hits and hits[0].source == 'accounting.md'
        assert hits[0].score > hits[-1].score or len(hits) == 1
    finally:
        _cleanup()

def test_reingest_is_idempotent():
    _cleanup()
    try:
        ingest_documents(CORPUS, client=CLIENT)
        second = ingest_documents(CORPUS, client=CLIENT)
        assert second.added == 0 and second.skipped >= 3
    finally:
        _cleanup()

def test_source_filter_and_stats():
    _cleanup()
    try:
        ingest_documents(CORPUS, client=CLIENT)
        hits = search('share links sessions', k=3, sources=['auth.md'], client=CLIENT)
        assert all(h.source == 'auth.md' for h in hits)
        s = stats()
        assert s['chunks'] >= 3 and s['sources'] == 3
    finally:
        _cleanup()

def test_tool_returns_cited_excerpts():
    _cleanup()
    try:
        ingest_documents(CORPUS, client=CLIENT)
        out = local_rag_search('public share links private sessions', k=2, client=CLIENT)
        assert out and {'source', 'page', 'score', 'excerpt'} <= set(out[0])
    finally:
        _cleanup()