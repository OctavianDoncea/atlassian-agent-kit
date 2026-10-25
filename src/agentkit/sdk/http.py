"""Base Atlassian REST client: auth injection, 401-refresh, 429-backoff, pagination."""
from __future__ import annotations
import threading
import time
import httpx
from collections.abc import Iterator
from typing import Any
from agentkit.config import Settings, get_settings
from agentkit.errors import AtlassianAPIError, AuthError, NotConnectedError, RateLimitError
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.policy import is_auth_failure, is_rate_limited, retry_after_seconds
from agentkit.sdk.token import TokenSet, TokenStoreProtocol

class BaseClient:
    product: str = ''

    def __init__(
        self,
        *,
        cloud_id: str | None = None,
        auth_mode: str = 'oauth',
        token_store: TokenStoreProtocol | None = None,
        auth_manager: AuthManager | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
        max_retries: int = 3,
        settings: Settings | None = None
    ):
        if auth_mode not in {'oauth', 'basic'}:
            raise AuthError(f'unknown auth_mode={auth_mode!r}')
        self._s = settings or get_settings()
        self.auth_mode = auth_mode
        self.cloud_id = cloud_id
        self._store = token_store
        self._auth = auth_manager
        self._sleep = sleep
        self._max_retries = max_retries
        self._http = httpx.Client(transport=transport, timeout=30)
        self._refresh_lock = threading.Lock()
        self._tokens: TokenSet | None = None

    # URL building
    def _base(self) -> str:
        return build_base_url(self.product, self.auth_mode, self.cloud_id, self._s)

    # Auth plumbing
    def _basic_auth(self) -> tuple[str, str] | None:
        if self.auth_mode != 'basic':
            return None
        return (self._s.atlassian_email, self._s.atlassian_api_token)

    def _headers(self) -> dict[str, str]:
        if self.auth_mode != 'oauth':
            return {'Accept': 'application/json'}
        return {'Accept': 'application/json', 'Authorization': f'Bearer {self._current_token()}'}

    def _current_token(self) -> str:
        if self._tokens is None or self._tokens.expired:
            self._load_or_refresh(proactive=True)
        assert self._tokens is not None
        return self._tokens.access_token

    def _load_or_refresh(self, *, proactive: bool) -> None:
        with self._refresh_lock:
            if self._tokens is not None and not self._tokens.expired:
                return
            if self._store is None:
                raise NotConnectedError('No token store configured for oauth mode.')
            stored = self._store.load(self.cloud_id or '')
            if stored is None:
                raise NotConnectedError(f'No stored tokens for cloud_id={self.cloud_id}. Visit /auth/atlassian/authorize.')
            if stored.expired and stored.refresh_token and self._auth is not None:
                stored = self._auth.refresh(stored.refresh_token)
                self._store.save(self.cloud_id or '', self._s.atlassian_site_url, stored)
            self._tokens = stored

    def _force_refresh(self) -> None:
        """Called after 401"""
        with self._refresh_lock:
            self._tokens = None
            if self._store is None or self._auth is None:
                raise NotConnectedError('Cannot refresh without token store + auth manager.')
            stored = self._store.load(self.cloud_id or '')
            if stored is None or not stored.refresh_token:
                raise NotConnectedError('No refresh token available.')
            new = self._auth.refresh(stored.refresh_token)
            self._store.save(self.cloud_id or '', self._s.atlassian_site_url, new)
            self._tokens = new

    # Core request
    def request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> dict | None:
        url = self._base() + path
        allow_auth_retry = self.auth_mode == 'oauth'
        attempts = 0
        while True:
            resp = self._http.request(method, url, params=params, json=json, headers=self._headers(), auth=self._basic_auth())

            if is_auth_failure(resp.status_code) and allow_auth_retry:
                allow_auth_retry = False
                self._force_refresh()
                continue

            if is_rate_limited(resp.status_code) and attempts < self._max_retries:
                attempts += 1
                self._sleep(retry_after_seconds(resp.headers, attempts))
                continue

            if resp.status_code >= 400:
                cls = RateLimitError if is_rate_limited(resp.status_code) else AtlassianAPIError
                raise cls(resp.status_code, f'{method} {path} failed', body=resp.text[:500], url=str(resp.url))

            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()

    # Pagination
    def paginate(
        self,
        path: str,
        *,
        params: dict | None = None,
        items_key: str,
        start_param: str = 'startAt',
        limit_param: str = 'maxResults',
        limit: int = 50,
        max_items: int = 500
    ) -> Iterator[dict]:
        start, yielded = 0, 0
        while yielded < max_items:
            p = dict(params or {})
            p[start_param] = start
            p[limit_param] = min(limit, max_items - yielded)
            data = self.request('GET', path, params=p)
            items = (data or {}).get(items_key, [])
            for item in items:
                yield item
                yielded += 1
                if yielded >= max_items:
                    return
            if not items or len(items) < limit:
                return
            start += len(items)


def build_base_url(product: str, auth_mode: str, cloud_id: str | None, settings: Settings) -> str:
    api = settings.api_base_url.rstrip('/')
    site = settings.atlassian_site_url.rstrip('/')
    if auth_mode == 'oauth':
        if not cloud_id:
            raise NotConnectedError('cloud_id is missing: complete the OAuth connect flow first.')
        base = f'{api}/ex/{product}/{cloud_id}'
    else:
        if not site:
            raise AuthError('ATLASSIAN_SITE_URL is required for basic auth mode.')
        base = site
    
    if product == 'confluence':
        base += '/wiki'

    return base