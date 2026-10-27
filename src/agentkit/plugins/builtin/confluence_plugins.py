from __future__ import annotations
from typing import Any
from agentkit.config import Settings
from agentkit.integrations.confluence import CONFLUENCE_TOOL_MODELS, AsyncConfluenceClient, ConfluenceClient
from agentkit.plugins.base import IntegrationPlugin, ToolSpec
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import DbTokenStore, TokenStoreProtocol

def _get_page_markdown(client: Any, inp: Any) -> dict:
    markdown, page = client.get_page_markdown(inp.page_id, inp.space_key,inp.title)
    return {'page_id': page['id'], 'title': page['title'], 'markdown': markdown}

_HANDLERS = {
    'list_spaces': lambda c, i: c.list_spaces(i.limit),
    'get_page_markdown': _get_page_markdown,
    'create_page': lambda c, i: c.create_page(i)
}

class ConfluencePlugin(IntegrationPlugin):
    name = 'confluence'
    display_name = 'Atlassian Confluence'
    version = '1.0.0'
    product = 'confluence'

    def tools(self) -> list[ToolSpec]:
        return [ToolSpec(name, desc, model, _HANDLERS[name]) for name, (model, desc) in CONFLUENCE_TOOL_MODELS.items()]

    def create_client(self, *, auth_mode='oauth', cloud_id=None, transport=None, settings: Settings | None = None, use_async=False, concurrency=8,
        token_store: TokenStoreProtocol | None = None, auth_manager: AuthManager | None = None
    ) -> Any:
        kwargs: dict[str, any] = {'cloud_id': cloud_id, 'auth_mode': auth_mode, 'transport': transport, 'settings': settings}

        if auth_mode == 'oauth':
            kwargs['token_store'] = token_store or DbTokenStore()
            kwargs['auth_manager'] = auth_manager or AuthManager(settings=settings)

        if use_async:
            return AsyncConfluenceClient(concurrency=concurrency, **kwargs)

        return ConfluenceClient(**kwargs)