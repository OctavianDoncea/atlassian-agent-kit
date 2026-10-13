from urllib.parse import parse_qs, urlsplit
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from agentkit.api.auth_routes import _read_cookie_state
from agentkit.api.main import app
from agentkit.config import get_settings


def test_authorize_cookie_matches_redirect_state(monkeypatch):
    monkeypatch.setenv('TOKEN_ENCRYPTION_KEY', Fernet.generate_key().decode())
    get_settings.cache_clear()
    try:
        resp = TestClient(app).get('/auth/atlassian/authorize', follow_redirects=False)
        assert resp.status_code in (302, 307)
        query = parse_qs(urlsplit(resp.headers['location']).query)
        assert query['audience'] == ['api.atlassian.com']
        assert query['redirect_uri'] == [get_settings().atlassian_redirect_uri]
        assert 'redirect_url' not in query
        assert _read_cookie_state(resp.cookies['oauth_state']) == query['state'][0]
    finally:
        get_settings.cache_clear()
