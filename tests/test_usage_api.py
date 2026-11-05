import pytest
from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from agentkit.api.main import app
from agentkit.db.models import LLMUsage

client = TestClient(app)

@pytest.fixture
def usage_db(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    LLMUsage.__table__.create(engine)
    session = sessionmaker(bind=engine)
    monkeypatch.setattr('agentkit.api.usage_routes.SessionLocal', session)
    return session

def test_usage_summary_shape(usage_db):
    with usage_db() as db:
        db.add(LLMUsage(
            purpose='agent', model='openai/gpt-oss-120b', ref='case-1',
            input_tokens=100, output_tokens=40, total_tokens=140,
            cost_usd=Decimal('0.00003900'), estimated=False, duration_ms=12,
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
    response = client.get('/api/usage/summary?days=7')
    assert response.status_code == 200
    body = response.json()
    assert {'totals', 'by_purpose', 'by_model', 'daily'} <= set(body)
    assert body['totals']['calls'] == 1
    assert body['totals']['input_tokens'] == 100
    assert body['by_purpose'][0]['purpose'] == 'agent'
    assert body['by_model'][0]['model'] == 'openai/gpt-oss-120b'
    assert len(body['daily']) == 7

def test_usage_recent_ok(usage_db):
    response = client.get('/api/usage/recent?limit=5')
    assert response.status_code == 200
    assert response.json() == []