import pytest
from fastapi.testclient import TestClient
from agentkit.api.main import app
from agentkit.config import get_settings
from agentkit.db.models import DocumentChunk
from agentkit.db.session import SessionLocal

client = TestClient(app)

@pytest.fixture(autouse=True)
def _fallback(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'rag_allow_hash_fallback', True)
    with SessionLocal() as db:
        db.query(DocumentChunk).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(DocumentChunk).delete()
        db.commit()


def test_ingest_search_stats_endpoints():
    r = client.post('/api/rag/ingest', json={'documents': [
        {'source': 'policy.md', 'content': 'Debits must equal credits before posting a journal entry.'}]})
    assert r.status_code == 200 and r.json()['added'] >= 1

    r = client.post('/api/rag/search', json={'query': 'debits equal credits posting', 'k': 2})
    assert r.status_code == 200 and r.json()[0]['source'] == 'policy.md'

    r = client.get('/api/rag/stats')
    assert r.status_code == 200 and r.json()['chunks'] >= 1