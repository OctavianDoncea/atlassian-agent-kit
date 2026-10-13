from __future__ import annotations
import json
import time
import httpx
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from cryptography.fernet import Fernet, InvalidToken
from agentkit.config import Settings, get_settings
from agentkit.errors import InvalidStateError, TokenRefreshError
from agentkit.sdk.token import TokenSet

class AuthManager:
    def __init__(self, settings: Settings | None = None, http: httpx.Client | None = None):
        self._s = settings or get_settings()
        self._http = http or httpx.Client(timeout=20)
        self._fernet = Fernet(self._s.token_encryption_key.encode()) if self._s.token_encryption_key else None

    def _state_fernet(self) -> Fernet:
        if self._fernet is None:
            raise InvalidStateError('TOKEN_ENCRYPTION_KEY is not set (used to sign OAuth state).')
        return self._fernet

    # Authorize
    def build_authorize_url(self) -> str:
        state = self._state_fernet().encrypt(json.dumps({'iat': time.time(), 'nonce': time.time_ns()}).encode()).decode()
        params = {
            'audience': 'api.atlassian.com',
            'client_id': self._s.atlassian_client_id,
            'scope': self._s.atlassian_scopes,
            'redirect_uri': self._s.atlassian_redirect_uri,
            'state': state,
            'response_type': 'code',
            'prompt': 'consent'
        }
        return f'{self._s.auth_base_url}/authorize?{urlencode(params)}'

    def verify_state(self, state: str) -> None:
        try:
            payload = json.loads(self._state_fernet().decrypt(state.encode()).decode())
        except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidStateError('OAuth state signature invalid.') from exc
        if time.time() - float(payload.get('iat', 0)) > self._s.oauth_state_ttl_seconds:
            raise InvalidStateError('OAuth state expired.')

    # Exchange
    def exchange_code(self, code: str) -> TokenSet:
        resp = self._http.post(
            f'{self._s.auth_base_url}/oauth/token',
            json={
                'grant_type': 'authorization_code',
                'client_id': self._s.atlassian_client_id,
                'client_secret': self._s.atlassian_client_secret,
                'code': code,
                'redirect_uri': self._s.atlassian_redirect_uri
            }
        )
        if resp.status_code != 200:
            raise TokenRefreshError(f'code exchange failed [{resp.status_code}]: {resp.text[:300]}')
        return self._parse(resp.json())

    # Refresh (rotating: response contains a new refresh token)
    def refresh(self, refresh_token: str) -> TokenSet:
        resp = self._http.post(
            f'{self._s.auth_base_url}/oauth/token',
            json={
                'grant_type': 'refresh_token',
                'client_id': self._s.atlassian_client_id,
                'client_secret': self._s.atlassian_client_secret,
                'refresh_token': refresh_token
            }
        )
        if resp.status_code != 200:
            raise TokenRefreshError(f'refresh failed [{resp.status_code}]: {resp.text[:300]}')
        return self._parse(resp.json())

    # Discover
    def discover_resources(self, access_token: str) -> list[dict]:
        resp = self._http.get(f'{self._s.api_base_url}/oauth/token/accessible-resources', headers={'Authorization': f'Bearer {access_token}'})
        resp.raise_for_status()
        return resp.json()

    def pick_cloud_id(self, resources: list[dict]) -> tuple[str, str]:
        target = self._s.atlassian_site_url.rstrip('/')
        for r in resources:
            if str(r.get('url', '')).rstrip('/') == target:
                return r['id'], str(r['url'])
        if resources:
            return resources[0]['id'], str(resources[0].get('url', target))
        raise TokenRefreshError('accessible-resources returned no sites; scopes may be missing.')

    @staticmethod
    def _parse(payload: dict) -> TokenSet:
        if 'refresh_token' not in payload:
            raise TokenRefreshError('Atlassian did not return a refresh token (missing offline_access / prompt=consent?).')
        return TokenSet(
            access_token=payload['access_token'],
            refresh_token=payload['refresh_token'],
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(payload.get('expires_in', 3600))),
            scope=payload.get('scope')
        )