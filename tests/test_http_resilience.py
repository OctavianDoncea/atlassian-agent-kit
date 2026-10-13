import json
import httpx
import pytest
from datetime import datetime, timedelta, timezone
from agentkit.config import Settings
from agentkit.errors import InvalidTransitionError, RateLimitError
from agentkit.integrations.jira import JiraClient
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import TokenSet

class FakeTokenStore:
    def __init__(self, tokens: TokenSet):
        self.tokens = tokens
        self.saved: list[TokenSet] = []

    def load(self, cloud_id: str) -> TokenSet | None:
        return self.tokens

    def save(self, cloud_id: str, site_url: str, tokens: TokenSet) -> None:
        self.tokens = tokens
        self.saved.append(tokens)


def _settings() -> Settings:
    return Settings(_env_file=None, atlassian_site_url='https://test.atlassian.net', token_encryption_key='')

def _token(expired: bool) -> TokenSet:
    delta = timedelta(minutes=-5) if expired else timedelta(minutes=30)
    return TokenSet(access_token='old-access', refresh_token='old-refresh', expires_at=datetime.now(timezone.utc) + delta, scope='read:jira-work')

def test_401_triggers_single_refresh_with_rotating_token():
    calls = {'api': 0, 'refresh': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == 'auth.atlassian.com':
            calls['refresh'] += 1
            body = json.loads(request.content)
            assert body['grant_type'] == 'refresh_token'
            assert body['refresh_token'] == 'old-refresh'

            return httpx.Response(200, json={'access_token': 'new-access', 'refresh_token': 'new-refresh', 'expires_in': 3600, 'scope': 'read:jira-work'})

        calls['api'] += 1
        auth = request.headers.get('authorization', '')
        if auth == 'Bearer old-access':
            return httpx.Response(401, json={'error': 'expired'})
        assert auth == 'Bearer new-access'

        return httpx.Response(200, json={'key': 'ENG-1', 'fields': {'summary': 'x'}})

    store = FakeTokenStore(_token(expired=False))
    client = JiraClient(cloud_id="cid", auth_mode="oauth", token_store=store,
                        auth_manager=AuthManager(settings=_settings(), http=httpx.Client(transport=httpx.MockTransport(handler))),
                        transport=httpx.MockTransport(handler), sleep=lambda s: None, settings=_settings())
    client._tokens = store.tokens

    issue = client.get_issue('ENG-1')
    assert issue['key'] == 'ENG-1'
    assert calls['refresh'] == 1 and calls['api'] == 2
    assert store.saved and store.saved[-1].refresh_token == 'new-refresh'

def test_429_honors_retry_after_then_succeeds():
    sleeps: list[float] = []
    state = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state['n'] += 1
        if state['n'] == 1:
            return httpx.Response(429, headers={'Retry-After': '2'}, text='slow down')
        return httpx.Response(200, json={'key': 'ENG-2'})

    client = JiraClient(auth_mode='basic', transport=httpx.MockTransport(handler), sleep=sleeps.append, settings=_settings())
    assert client.get_issue('ENG-2')['key'] == 'ENG-2'
    assert sleeps == [2.0]

def test_429_exhausts_retries_and_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={'Retry-After': '1'}, text='slow down')

    client = JiraClient(auth_mode='basic', transport=httpx.MockTransport(handler),
                        sleep=lambda s: None, max_retries=2, settings=_settings())
    with pytest.raises(RateLimitError):
        client.get_issue('ENG-3')


def test_transition_guard_rejects_invalid_transition():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/transitions') and request.method == 'GET':
            return httpx.Response(200, json={'transitions': [
                {'id': '21', 'name': 'Start Progress', 'to': {'name': 'In Progress'}}]})
        return httpx.Response(204)

    client = JiraClient(auth_mode='basic', transport=httpx.MockTransport(handler), settings=_settings())
    with pytest.raises(InvalidTransitionError) as exc:
        client.transition_issue('ENG-4', 'Close')
    assert 'Start Progress' in str(exc.value)

    client.transition_issue('ENG-4', 'start progress')

def test_search_issues_uses_jql_endpoint_and_page_token():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == 'POST'
        assert request.url.path.endswith('/rest/api/3/search/jql')
        body = json.loads(request.content)
        bodies.append(body)
        if 'nextPageToken' not in body:
            return httpx.Response(200, json={'issues': [{'key': 'ENG-1'}], 'nextPageToken': 'page-2', 'isLast': False})
        assert body['nextPageToken'] == 'page-2'
        return httpx.Response(200, json={'issues': [{'key': 'ENG-2'}], 'isLast': True})

    client = JiraClient(auth_mode='basic', transport=httpx.MockTransport(handler), settings=_settings())
    issues = client.search_issues('project = ENG', fields=['summary', 'status'], max_results=10)
    assert [i['key'] for i in issues] == ['ENG-1', 'ENG-2']
    assert bodies[0]['fields'] == ['summary', 'status']
    assert bodies[0]['maxResults'] == 10