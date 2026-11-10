import pytest
from datetime import datetime, timedelta, timezone
from agentkit.db.models import PendingAction
from agentkit.db.session import SessionLocal
from agentkit.hitl.gate import ActionAlreadyDecidedError, ActionExpiredError, decide, execute_with_approval, list_pending
from agentkit.plugins import get_registry


class FakeJira:
    def __init__(self): self.calls = []
    def create_issue(self, inp): self.calls.append(inp); return {'key': 'ENG-99', 'id': '99'}
    def search_issues(self, jql, fields=None, max_results=50): self.calls.append(jql); return []


@pytest.fixture(autouse=True)
def _clean():
    with SessionLocal() as db:
        db.query(PendingAction).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(PendingAction).delete()
        db.commit()

ARGS = {'project_key': 'ENG', 'summary': 'crash', 'issue_type': 'Bug'}

def test_non_destructive_tool_executes_directly():
    reg = get_registry()
    out = execute_with_approval('get_current_time', {'timezone': 'UTC'}, {'time': reg.plugins['time']})
    assert out.pending is False and out.result['timezone'] == 'UTC'

def test_destructive_tool_pauses_and_does_not_execute():
    fake = FakeJira()
    out = execute_with_approval('create_issue', ARGS, {'jira': fake}, session_id='s1')
    assert out.pending is True and fake.calls == []
    assert [p['tool_name'] for p in list_pending()] == ['create_issue']

def test_approve_executes_once_with_result():
    fake = FakeJira()
    out = execute_with_approval('create_issue', ARGS, {'jira': fake})
    res = decide(out.action_id, 'approve', decided_by='test', clients={'jira': fake})
    assert res['status'] == 'executed' and res['result']['key'] == 'ENG-99'
    assert len(fake.calls) == 1

def test_reject_never_executes():
    fake = FakeJira()
    out = execute_with_approval('create_issue', ARGS, {'jira': fake})
    res = decide(out.action_id, 'reject', note='nope', clients={'jira': fake})
    assert res['status'] == 'rejected' and fake.calls == []

def test_double_decide_conflicts():
    fake = FakeJira()
    out = execute_with_approval('create_issue', ARGS, {'jira': fake})
    decide(out.action_id, 'approve', clients={'jira': fake})
    with pytest.raises(ActionAlreadyDecidedError):
        decide(out.action_id, 'approve', clients={'jira': fake})

def test_expired_action_cannot_be_approved():
    fake = FakeJira()
    out = execute_with_approval('create_issue', ARGS, {'jira': fake})
    with SessionLocal() as db:
        row = db.query(PendingAction).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    with pytest.raises(ActionExpiredError):
        decide(out.action_id, 'approve', clients={'jira': fake})
    assert fake.calls == []

def test_pending_display_is_pii_redacted():
    execute_with_approval('create_issue', {**ARGS, 'summary': 'reporter jane.doe@acme.com crashed'}, {'jira': FakeJira()})
    pending = list_pending()
    assert 'jane.doe@acme.com' not in str(pending[0]['arguments'])
    assert '[EMAIL_' in str(pending[0]['arguments'])