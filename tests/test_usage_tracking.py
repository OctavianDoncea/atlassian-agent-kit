import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from agentkit.db.models import LLMUsage
from agentkit.llm.gateway import chat_completion
from agentkit.llm.tokens import estimate_tokens

@pytest.fixture
def usage_db(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    LLMUsage.__table__.create(engine)
    session = sessionmaker(bind=engine)
    monkeypatch.setattr('agentkit.llm.usage.SessionLocal', session)
    return session

class _Message:
    def __init__(self, content='ok', tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Completions:
    def __init__(self, response):
        self.response = response

    def create(self, **kwargs):
        return self.response


def _client(response):
    client = type('Client', (), {})()
    client.chat = type('Chat', (), {})()
    client.chat.completions = _Completions(response)
    return client

def _response(content='ok', prompt_tokens=None, completion_tokens=None):
    response = type('R', (), {})()
    choice = type('C', (), {})()
    choice.message = _Message(content)
    response.choices = [choice]
    if prompt_tokens is None:
        response.usage = None
    else:
        response.usage = type('U', (), {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens, 'prompt_tokens_details': None})()
    return response

def _price(model, input_tokens, output_tokens, **kwargs):
    return (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000

def test_gateway_records_provider_usage(monkeypatch, usage_db):
    monkeypatch.setattr('agentkit.llm.gateway.cost_usd', _price)
    result = chat_completion(
        messages=[{'role': 'user', 'content': 'hi'}],
        purpose='usage-test-priced',
        ref='case-1',
        client=_client(_response(prompt_tokens=11, completion_tokens=7)),
    )
    assert result.usage.estimated is False
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7
    assert result.usage.cost_usd == pytest.approx((11 * 0.15 + 7 * 0.60) / 1_000_000)
    with usage_db() as db:
        saved = db.query(LLMUsage).filter_by(purpose='usage-test-priced', ref='case-1').one()
        assert saved.input_tokens == 11
        assert saved.total_tokens == 18
        assert saved.estimated is False
        db.delete(saved)
        db.commit()

def test_gateway_estimates_when_usage_is_missing(monkeypatch, usage_db):
    monkeypatch.setattr('agentkit.llm.gateway.cost_usd', _price)
    text = 'tell me a long story about spaceships ' * 20
    result = chat_completion(
        messages=[{'role': 'user', 'content': text}],
        purpose='usage-test-estimated',
        client=_client(_response(content='this is a reply')),
    )
    assert result.usage.estimated is True
    assert result.usage.input_tokens >= estimate_tokens(text)
    assert result.usage.output_tokens >= 1
    with usage_db() as db:
        saved = db.query(LLMUsage).filter_by(purpose='usage-test-estimated').one()
        assert saved.estimated is True
        db.delete(saved)
        db.commit()

def test_persist_failure_does_not_break_the_call(monkeypatch):
    monkeypatch.setattr('agentkit.llm.gateway.cost_usd', _price)

    def boom():
        raise RuntimeError('ledger down')

    monkeypatch.setattr('agentkit.llm.usage.SessionLocal', boom)
    result = chat_completion(
        messages=[{'role': 'user', 'content': 'hi'}],
        purpose='usage-test-unpersisted',
        client=_client(_response(prompt_tokens=3, completion_tokens=1)),
    )
    assert result.usage.input_tokens == 3
    assert result.usage.output_tokens == 1