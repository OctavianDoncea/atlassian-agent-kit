import httpx
from agentkit.config import Settings
from agentkit.integrations.confluence import ConfluenceClient


def test_list_spaces_follows_v2_cursor():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith('/wiki/api/v2/spaces')
        seen.append(dict(request.url.params))
        if 'cursor' not in request.url.params:
            return httpx.Response(200, json={
                'results': [{'id': '1', 'key': 'EW'}],
                '_links': {'next': '/wiki/api/v2/spaces?cursor=page-2&limit=1'},
            })
        return httpx.Response(200, json={'results': [{'id': '2', 'key': 'DOCS'}], '_links': {}})

    client = ConfluenceClient(
        auth_mode='basic',
        transport=httpx.MockTransport(handler),
        settings=Settings(_env_file=None, atlassian_site_url='https://test.atlassian.net'),
    )
    spaces = client.list_spaces(limit=10)
    assert [s['key'] for s in spaces] == ['EW', 'DOCS']
    assert seen[0]['type'] == 'global'
    assert seen[1]['cursor'] == 'page-2'
