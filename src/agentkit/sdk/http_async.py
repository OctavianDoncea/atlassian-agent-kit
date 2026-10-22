"""Async Atlassian REST client"""
from __future__ import annotations
import asyncio
import httpx
from collections.abc import AsyncIterator
from typing import Any
from agentkit.config import Settings, get_settings
from agentkit.errors import AtlassianAPIError, NotConnectedError, RateLimitError
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.http import build_base_url
from agentkit.sdk.policy import is_auth_failure, is_rate_limited, retry_after_seconds
from agentkit.sdk.token import TokenStoreProtocol, TokenSet

class AsyncBaseClient:
    product: str = ''

    def __init__(
        self,
        *,
        cloud_id: str | None = None,
        auth_mode: str = 'oauth',
        token_store: TokenStoreProtocol | None = None,
        auth_manager: AuthManager | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = None,
        max_retries: int = 3,
        concurrency: int = 8,
        settings: Settings | None = None
    ):
        if auth_mode not in {'oauth', 'basic'}:
            raise ValueError(f'unknown auth_mode={auth_mode!r}')
        self._s = settings or get_settings()
        self.auth_mode = auth_mode
        self.cloud_id = cloud_id
        self._store = token_store
        self._auth = auth_manager
        self._sleep = sleep or asyncio.sleep
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(concurrency)
        self._refresh_lock = asyncio.Lock()
        self._http = httpx.AsyncClient(transport=transport, timeout=30)
        self._tokens: TokenSet | None = None

    # Lifecycle
    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> 'AsyncBaseClient':
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # Auth plumbing
    def _basic_auth(self) -> tuple[str, str] | None:
        if self.auth_mode != 'basic':
            return None
        
        return (self._s.atlassian_email, self._s.atlassian_api_token)

    async def _headers(self) -> dict[str, str]:
        if self.auth_mode != 'oauth':
            return {'Accept': 'application/json'}
        return {'Accept': 'application/json', 'Authorization': f'Bearer {await self._current_token()}'}

    async def _current_token(self) -> str:
        if self._tokens is None or self._tokens.expired:
            await self._load_or_refresh()
        assert self._tokens is not None
        return self._tokens.access_token

    async def _load_or_refresh(self) -> None:
        async with self._refresh_lock:
            if self._tokens is not None and not self._tokens.expired:
                return
            if self._store is None:
                raise NotConnectedError('No token store configured for oauth mode.')
            
            stored = await asyncio.to_thread(self._store.load, self.cloud_id or '')
            if stored is None:
                raise NotConnectedError(f'No stored tokens for cloud_id={self.cloud_id}.')
            if stored.expired and stored.refresh_token and self._auth is not None:
                new = await asyncio.to_thread(self._auth.refresh, stored.refresh_token)
                await asyncio.to_thread(self._store.save, self.cloud_id or '', self._s.atlassian_site_url, new)
                stored = new
            
            self._tokens = stored

    async def _force_refresh(self) -> None:
        """After a 401: the asyncio.Lock guarantees ONE refresh for N concurrent failures."""
        async with self._refresh_lock:
            self._tokens = None
            if self._store is None or self._auth is None:
                raise NotConnectedError('Cannot refresh without token store + auth manager.')
            
            stored = await asyncio.to_thread(self._store.load, self.cloud_id or '')
            if stored is None or not stored.refresh_token:
                raise NotConnectedError('No refresh token available.')

            new = await asyncio.to_thread(self._auth.refresh, stored.refresh_token)
            await asyncio.to_thread(self._store.save, self.cloud_id or '', self._s.atlassian_site_url, new)
            self._tokens = new

    # Core request (semaphore-bounded)
    async def request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> dict | None:
        async with self._semaphore:
            url = build_base_url(self.product, self.auth_mode, self.cloud_id, self._s)
            allow_auth_retry = self.auth_mode == 'oauth'
            attempts = 0

            while True:
                resp = await self._http.request(method, url, params=params, json=json, headers=await self._headers(), auth=self._basic_auth())

                if is_auth_failure(resp.status_code) and allow_auth_retry:
                    allow_auth_retry = False
                    await self._force_refresh()
                    continue
                if is_rate_limited(resp.status_code) and attempts < self._max_retries:
                    attempts += 1
                    await self._sleep(retry_after_seconds(resp.headers, attempts))
                    continue
                if resp.status_code >= 400:
                    cls = RateLimitError if resp.status_code == 429 else AtlassianAPIError
                    raise cls(resp.status_code, f'{method} {path} failed', body=resp.text[:500], url=str(resp.url))
                if resp.status_code == 204 or not resp.content:
                    return None

                return resp.json()

    # Async pagination
    async def paginate(
        self, 
        path: str, 
        *, 
        params: dict | None = None, 
        items_key: str,
        start_param: str = 'startAt',
        limit_param: str = 'maxResults',
        limit: int = 50,
        max_items: int = 500
    ) -> AsyncIterator[dict]:
        start, yielded = 0, 0
        while yielded < max_items:
            p = dict(params or {})
            p[start_param] = start
            p[limit_param] = min(limit, max_items - yielded)
            data = await self.request('GET', path, params=p)
            items = (data or {}).get(items_key, [])

            for item in items:
                yield item
                yielded += 1
                if yielded >= max_items:
                    return
            
            if not items or len(items) < limit:
                return

            start += len(items)