import asyncio
import json
import httpx
from datetime import datetime, timedelta, timezone
from agentkit.config import Settings
from agentkit.integrations.confluence import AsyncConfluenceClient
from agentkit.integrations.jira import AsyncJiraClient
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import TokenSet

class FakeTokenStore:
    def __init__(self, tokens: TokenSet) -> None:
        self.tokens = tokens
        self.saved: list[TokenSet] = []

    def load(self, cloud_id):
        return self.tokens

    def save(self, cloud_id: str, site_url: str, tokens: TokenSet):
        self.tokens = tokens
        self.saved.append(tokens)


def _settings() -> Settings:
    return Settings(_env_file=None, atlassian_site_url='https://test.atlassian.net', token_encryption_key='x' * 44)

def _token() -> TokenSet:
    return TokenSet('old-access', 'old-refresh', datetime.now(timezone.utc) + timedelta(minutes=30))

async def test_async_401_triggers_single_rotating_refresh():
    calls = {'api': 0, 'refresh': 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == 'auth.atlassian.com':
            calls['refresh'] += 1
            return httpx.Response(200, json={'access_token': 'new-access', 'refresh_token': 'new-refresh', 'expires_in': 3600, 'scope': 'read:jira-work'})
        
        calls['api'] += 1
        auth = request.headers.get('authorization', '')

        if auth == 'Bearer old-access':
            return httpx.Response(401, json={'error': 'expired'})

        return httpx.Response(200, json={'key': 'ENG-1'})

    store = FakeTokenStore(_token())
    async with AsyncJiraClient(
        cloud_id='cid', auth_mode='oauth', token_store=store, auth_manager=AuthManager(settings=_settings(), httpx=httpx.Client(transport=httpx.MockTransport(handler))),
        transport=httpx.MockTransport(handler), settings=_settings()
    ) as client:
        client._tokens = store.tokens
        issue = await client.get_issue('ENG-1')

    
    assert issue['key'] == 'ENG-1'
    assert calls['refresh'] == 1 and calls['api'] == 2
    assert store.saved[-1].refresh_token == 'new-refresh'

async def test_async_429_honours_injected_sleep():
    sleeps: list[float] = []
    state = {'n': 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        state['n'] += 1
        if state['n'] == 1:
            return httpx.Response(429, headers={'Retry-After': '2'}, text='slow')
        
        return httpx.Response(200, json={'key': 'ENG-2'})

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    async with AsyncJiraClient(auth_mode='basic', transport=httpx.MockTransport(handler), sleep=fake_sleep, settings=_settings()) as client:
        assert (await client.get_issue('ENG-2'))['key'] == 'ENG-2'

    assert sleeps == [2.0]

async def test_semaphore_bounds_inflight_requests():
    state = {'in_flight': 0, 'max_in_flight': 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        state['in_flight'] += 1
        state['max_in_flight'] = max(state['max_in_flight'], state['in_flight'])
        await asyncio.sleep(0.05)
        state['in_flight'] -= 1

        return httpx.Response(200, json={'id': '1', 'title': 't', 'body': {'storage': {'value': '<p>x</p>'}}})

    async with AsyncConfluenceClient(auth_mode='basic', transport=httpx.MockTransport(handler), concurrency=3, settings=_settings()) as client:
        results = await client.batch_fetch_markdown([str(i) for i in range(9)])
    
    assert len(results) == 9
    assert 2 <= state['max_in_flight'] <= 3

async def test_async_pagination_walks_all_pages():
    pages = {'0': ['a', 'b'], '2': ['c', 'd'], '4': ['e']}

    async def handler(request: httpx.Request) -> httpx.Response:
        start = request.url.params.get('startAt', 0)
        return httpx.Response(200, json={'issues': [{'key': k} for k in pages.get(str(start), [])]})

    async with AsyncJiraClient(auth_mode='basic', transport=httpx.MockTransport(handler), settings=_settings()) as client:
        issues = await client.search_issues('project = ENG', max_results=50)
    
    assert [i['key'] for i in issues] == ['a', 'b', 'c', 'd', 'e']