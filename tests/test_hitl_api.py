import pytest
from fastapi.testclient import TestClient
from agentkit.api.main import app
from agentkit.db.models import PendingAction
from agentkit.db.session import SessionLocal
from agentkit.hitl.gate import execute_with_approval
from agentkit.plugins import get_registry

client = TestClient(app)


class FakeJira:
    def create_issue(self, inp):
        return {'key': 'ENG-77'}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    with SessionLocal() as db:
        db.query(PendingAction).delete()
        db.commit()
    monkeypatch.setattr(type(get_registry()), 'make_clients', lambda self, **kw: {'jira': FakeJira()})
    yield
    with SessionLocal() as db:
        db.query(PendingAction).delete()
        db.commit()


def test_pending_decide_and_history_flow():
    out = execute_with_approval('create_issue', {'project_key': 'ENG', 'summary': 'x'}, {'jira': FakeJira()})
    r = client.get('/api/hitl/pending')
    assert r.status_code == 200 and len(r.json()['pending']) == 1

    r = client.post(f'/api/hitl/{out.action_id}/decide', json={'decision': 'approve', 'note': 'ok'})
    assert r.status_code == 200 and r.json()['status'] == 'executed'

    r = client.get('/api/hitl/history')
    assert r.status_code == 200 and r.json()[0]['result']['key'] == 'ENG-77'

    r = client.post(f'/api/hitl/{out.action_id}/decide', json={'decision': 'reject'})
    assert r.status_code == 409
