from __future__ import annotations
import httpx
from typing import Any
from agentkit.config import Settings
from agentkit.integrations.jira import JIRA_TOOL_MODELS, AsyncJiraClient, JiraClient
from agentkit.plugins.base import IntegrationPlugin, ToolSpec
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import DbTokenStore, TokenStoreProtocol

_HANDLERS = {
    'search_issues': lambda c, i: c.search_issues(i.jql, i.fields, i.max_results),
    'get_issue': lambda c, i: c.get_issue(i.issue_key, i.fields),
    'create_issue': lambda c, i: c.create_issue(i),
    'transition_issue': lambda c, i: c.transition_issue(i.issue_key, i.transition)
}

class JiraPlugin(IntegrationPlugin):
    name = 'jira'
    display_name = 'Atlassian Jira'
    version = '1.0.0'
    product = 'jira'

    def tools(self) -> list[ToolSpec]:
        return [ToolSpec(name, desc, model, _HANDLERS[name]) for name, (model, desc) in JIRA_TOOL_MODELS.items()]

    def create_client(self, *, auth_mode='oauth', cloud_id=None, transport=None, settings: Settings | None = None, use_async=False,
        concurrency=8, token_store: TokenStoreProtocol | None = None, auth_manager: AuthManager | None = None
    ) -> Any:
        kwargs: dict[str, Any] = {
            'cloud_id': cloud_id, 'auth_mode': auth_mode, 'transport': transport, 'settings': settings
        }

        if auth_mode == 'oauth':
            kwargs['token_store'] = token_store or DbTokenStore()
            kwargs['auth_manager'] = auth_manager or AuthManager(settings=settings)

        if use_async:
            return AsyncJiraClient(concurrency=concurrency, **kwargs)

        return JiraClient(**kwargs)