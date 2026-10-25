"""Jira Cloud connector + LLM tool input models."""
from __future__ import annotations
import asyncio
from pydantic import BaseModel, Field
from agentkit.errors import InvalidTransitionError
from agentkit.sdk.http import BaseClient
from agentkit.sdk.http_async import AsyncBaseClient

class SearchIssuesInput(BaseModel):
    jql: str = Field(description="JQL query string, e.g. 'project = ENG AND status \"to Do\" ORDER BY created DESC'")
    max_results: int = Field(50, ge=1, le=200, description='Maximum number of issues to return')
    fields: list[str] | None = Field(None, description="Field keys to return, e.g. ['summary', 'status', 'priority']")


class GetIssueInput(BaseModel):
    issue_key: str = Field(description='Issue key, e.g. "ENG-12"')
    fields: list[str] | None = Field(None, description='Field keys to return')


class CreateIssueInput(BaseModel):
    project_key: str = Field(description='Project key, e.g. "ENG"')
    summary: str = Field(description='One-line issue summary')
    issue_type: str = Field('Task', description='Issue type name: Task, Bug, or Story')
    description: str | None = Field(None, description='Plain-text issue description')
    priority: str | None = Field(None, description='Priority name: Highest, High, Medium, or Low')


class TransitionIssueInput(BaseModel):
    issue_key: str = Field(description='Issue key, e.g. "ENG-12"')
    transition: str = Field(description="Transition name (e.g. 'Start Progress') or numeric transition id")


class JiraClient(BaseClient):
    product = 'jira'

    def search_issues(self, jql: str, fields: list[str] | None = None, max_results: int = 200) -> list[dict]:
        issues: list[dict] = []
        token: str | None = None
        while len(issues) < max_results:
            body: dict = {'jql': jql, 'maxResults': min(50, max_results - len(issues))}
            if fields:
                body['fields'] = fields
            if token:
                body['nextPageToken'] = token
            data = self.request('POST', '/rest/api/3/search/jql', json=body) or {}
            batch = data.get('issues', [])
            issues.extend(batch)
            token = data.get('nextPageToken')
            if not batch or not token or data.get('isLast'):
                break
        return issues[:max_results]

    def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict:
        params = {'fields': ','.join(fields)} if fields else None
        data = self.request('GET', f'/rest/api/3/issue/{issue_key}', params=params)
        assert data is not None
        return data

    def create_issue(self, inp: CreateIssueInput) -> dict:
        fields: dict = {
            'project': {'key': inp.project_key},
            'summary': inp.summary,
            'issuetype': {'name': inp.issue_type}
        }
        if inp.description:
            fields['description'] = {
                'version': 1,
                'type': 'doc',
                'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': inp.description}]}]
            }
        if inp.priority:
            fields['priority'] = {'name': inp.priority}
        
        data = self.request('POST', '/rest/api/3/issue', json={'fields': fields})
        assert data is not None
        return data

    def get_transitions(self, issue_key: str) -> list[dict]:
        data = self.request('GET', f'/rest/api/3/issue/{issue_key}/transitions')
        return (data or {}).get('transitions', [])

    def transition_issue(self, issue_key: str, transition: str) -> None:
        allowed = self.get_transitions(issue_key)
        match = next((t for t in allowed if str(t['id']) == str(transition) or t['name'].lower() == str(transition).lower()), None)

        if match is None:
            names = ', '.join(t['name'] for t in allowed) or 'none'
            raise InvalidTransitionError(f"Issue {issue_key}: transition '{transition}' is not allowed from its current status. Allowed: {names}")
        self.request('POST', f'/rest/api/3/issue/{issue_key}/transitions', json={'transition': {'id': match['id']}})


class AsyncJiraClient(AsyncBaseClient):
    product = 'jira'

    async def search_issues(self, jql: str, fields: list[str] | None = None, max_results: int = 200) -> list[dict]:
        params: dict = {'jql': jql}
        if fields:
            params['fields'] = ','.join(fields)

        return [i async for i in self.paginate(
            '/rest/api/3/search', params=params, items_key='issues', start_param='startAt', limit_param='maxResults', limit=50, max_items=max_results
        )]

    async def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict:
        params = {'fields': ','.join(fields)} if fields else None
        data = await self.request('GET', f'/rest/api/3/issue/{issue_key}', params=params)
        assert data is not None
        return data

    async def batch_get_issues(self, issue_keys: list[str]) -> list[dict]:
        return list(await asyncio.gather(*(self.get_issue(k) for k in issue_keys)))


JIRA_TOOL_MODELS: dict[str, tuple[type(BaseModel), str]] = {
    'search_issues': (SearchIssuesInput, 'Search Jira issues using a JQL query. Returns matching issues with their fields.'),
    'get_issue': (GetIssueInput, 'Fetch a single Jira issue by key.'),
    'create_issue': (CreateIssueInput, 'Create a new Jira issue in a project.'),
    'transition_issue': (TransitionIssueInput, 'Move a Jira issue through its workflow by applying a valid transition.')
}