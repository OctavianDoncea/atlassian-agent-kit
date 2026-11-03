import hashlib
import json
from fastapi.testclient import TestClient
from agentkit.api.main import app
from agentkit.evals.agent import invoke_agent
from agentkit.evals.judges import semantic_judge
from agentkit.pii.redactor import Redactor

class _Message:
    def __init__(self):
        self.tool_calls = None
        self.content = 'ok'


class _Completions:
    def __init__(self):
        self.captured = None

    def create(self, **kwargs):
        self.captured = kwargs
        resp = type('R', (), {})()
        choice = type('C', (), {})()
        choice.message = _Message()
        resp.choices = [choice]
        return resp


class _FakeOpenAI:
    def __init__(self):
        self.chat = type('Chat', (), {})()
        self.chat.completions = _Completions()


def test_invoke_agent_redacts_prompt_at_egress():
    fake = _FakeOpenAI()
    resp = invoke_agent('Bug: user jane.doe@acme.com crashed, call +9999999999', llm_client=fake)
    sent = fake.chat.completions.captured['messages'][0]['content']
    assert 'jane.doe@acme.com' not in sent and '+9999999999' not in sent
    assert '[EMAIL_' in sent and '[PHONE_' in sent
    assert resp.redaction is not None
    assert resp.redaction.restore(sent).count('jane.doe@acme.com') == 1

def test_semantic_judge_payload_redacted():
    fake = _FakeOpenAI()
    fake.chat.completions.create = lambda **kw: _capture(kw, fake)

    captured = {}

    def _capture(kw, f):
        captured.update(kw)
        resp = type('R', (), {})()
        choice = type('C', (), {})()
        msg = type('M', (), {})()
        msg.content = json.dumps({'passed': True, 'reasoning': 'equivalent'})
        msg.tool_calls = None
        choice.message = msg
        resp.choices = [choice]
        return resp

    result = semantic_judge(
        'user jane@acme.com', 'search_issues', {'q': 'jane@acme.com'},
        'search_issues', {'q': 'jane@acme.com'}, llm_client=fake,
    )
    sent = captured['messages'][1]['content']
    assert result.passed is True
    assert 'jane@acme.com' not in sent
    assert '[EMAIL_' in sent

def test_redact_endpoint_does_not_return_secrets():
    value = 'jane@acme.com'
    response = TestClient(app).post('/api/pii/redact', json={'text': f'Mail {value}'})
    body = response.json()
    assert response.status_code == 200
    assert 'mapping' not in body
    assert value not in response.text
    public = hashlib.sha256(value.encode()).hexdigest()[:8]
    assert public not in body['redacted']
    assert '[EMAIL_' in body['redacted']
    assert body['kinds'] == ['EMAIL']

def test_placeholder_is_stable_but_not_a_public_hash():
    value = 'jane.doe@acme.com'
    first = Redactor(enabled=True).redact(value)
    second = Redactor(enabled=True).redact(value)
    assert first.spans[0].placeholder == second.spans[0].placeholder
    assert hashlib.sha256(value.encode()).hexdigest()[:8] not in first.text