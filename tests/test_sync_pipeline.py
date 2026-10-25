import httpx
from agentkit.db.models import PageSnapshot
from agentkit.db.session import SessionLocal
from agentkit.integrations.confluence import AsyncConfluenceClient
from agentkit.integrations.sync_pipeline import sync_space

PAGES = {'101': '<p>one</p>', '102': '<p>two</p>'}

def _client() -> AsyncConfluenceClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith('/api/v2/spaces') and request.url.params.get('keys'):
            return httpx.Response(200, json={'results': [{'id': 'space-1', 'key': request.url.params['keys']}]})
        if path.endswith('/pages'):
            return httpx.Response(200, json={'results': [{'id': i, 'title': f'Page {i}'} for i in PAGES]})

        page_id = path.rsplit('/', 1)[-1]
        return httpx.Response(200, json={'id': page_id, 'title': f'Page {page_id}', 'body': {'storage': {'value': PAGES[page_id]}}})

    return AsyncConfluenceClient(auth_mode='basic', transport=httpx.MockTransport(handler), concurrency=4, settings=__import__('agentkit.config', fromlist=['Settings']).Settings(
        _env_file=None, atlassian_site_url='https://test.atlassian.net'
    ))

def _clean() -> None:
    with SessionLocal() as db:
        db.query(PageSnapshot).filter_by(space_key='TEST').delete()
        db.commit()

def test_sync_is_idempotent_and_change_aware():
    _clean()
    try:
        import asyncio
        async def scenario():
            async with _client() as c:
                first = await sync_space(c, 'TEST')
                second = await sync_space(c, 'TEST')
                PAGES['101'] = '<p>one CHANGED</p>'
                third = await sync_space(c, 'TEST')
                return first, second, third
        first, second, third = asyncio.run(scenario())

        assert (first.created, first.updated, first.unchanged) == (2, 0, 0)
        assert (second.created, second.updated, second.unchanged) == (0, 0, 2)
        assert (third.created, third.updated, third.unchanged) == (0, 1, 1)

        with SessionLocal() as db:
            assert db.query(PageSnapshot).filter_by(space_key='TEST').count() == 2
    finally:
        _clean()
        PAGES['101'] = '<p>one</p>'