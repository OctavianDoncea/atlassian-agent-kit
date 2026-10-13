from __future__ import annotations
import html
import re
from urllib.parse import parse_qs, urlsplit
from pydantic import BaseModel, Field
from agentkit.errors import PageNotFoundError
from agentkit.integrations.confluence_markdown import storage_to_markdown
from agentkit.sdk.http import BaseClient

class ListSpacesInput(BaseModel):
    limit: int = Field(25, ge=1, le=100, description='Maximum number of spaces to return')


class GetPageMarkdownInput(BaseModel):
    page_id: str | None = Field(None, description='Confluence page id (numeric string)')
    space_key: str | None = Field(None, description="Space key, e.g. 'EW' (use with title)")
    title: str | None = Field(None, description='Exact page title (use with space_key)')


class CreatePageInput(BaseModel):
    space_key: str = Field(description='Space key, e.g. "EW"')
    title: str = Field(description='Ttile for the new page')
    markdown: str = Field(description=f'Page content in Markdown (paragraphs and ``` code fences supported)')


def markdown_to_storage(markdown: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", markdown or '') if b.strip()]
    out: list[str] = []

    for block in blocks:
        if block.startswith('```'):
            lines = block.split('\n')
            lang = lines[0][3:].strip()
            code = '\n'.join(lines[1:]).rsplit('```', 1)[0]
            out.append(
                '<ac:structured-macro ac:name="code">'
                f'<ac:parameter ac:name="language">{html.escape(lang)}</ac:parameter>'
                f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
                "</ac:structured-macro>"
            )
        else:
            out.append(f"<p>{html.escape(block).replace(chr(10), '<br/>')}</p>")
    
    return ''.join(out)

class ConfluenceClient(BaseClient):
    product = 'confluence'

    def _collect(self, path: str, params: dict | None = None, limit: int = 25) -> list[dict]:
        items: list[dict] = []
        cursor: str | None = None
        while len(items) < limit:
            query = dict(params or {})
            query['limit'] = min(250, limit - len(items))
            if cursor:
                query['cursor'] = cursor
            data = self.request('GET', path, params=query) or {}
            batch = data.get('results', [])
            items.extend(batch)
            next_link = (data.get('_links') or {}).get('next')
            if not batch or not next_link:
                break
            cursor = (parse_qs(urlsplit(next_link).query).get('cursor') or [None])[0]
            if not cursor:
                break
        return items[:limit]

    def _space_id(self, space_key: str) -> str:
        data = self.request('GET', '/api/v2/spaces', params={'keys': space_key, 'limit': 1}) or {}
        results = data.get('results', [])
        if not results:
            raise PageNotFoundError(f'No Confluence space {space_key!r}')
        return str(results[0]['id'])

    def list_spaces(self, limit: int = 25) -> list[dict]:
        return self._collect('/api/v2/spaces', {'type': 'global'}, limit)

    def list_pages(self, space_key: str, limit: int = 25) -> list[dict]:
        return self._collect(f'/api/v2/spaces/{self._space_id(space_key)}/pages', {'status': 'current'}, limit)

    def find_page(self, space_key: str, title: str) -> dict:
        data = self.request(
            'GET', f'/api/v2/spaces/{self._space_id(space_key)}/pages',
            params={'title': title, 'body-format': 'storage', 'status': 'current', 'limit': 1},
        ) or {}
        results = data.get('results', [])
        if not results:
            raise PageNotFoundError(f'No page titled {title!r} in space {space_key!r}')
        return results[0]

    def get_page(self, page_id: str) -> dict:
        data = self.request('GET', f'/api/v2/pages/{page_id}', params={'body-format': 'storage'})
        assert data is not None
        return data

    def get_page_markdown(self, page_id: str | None = None, space_key: str | None = None, title: str | None = None) -> tuple[str, dict]:
        page = self.get_page(page_id) if page_id else self.find_page(space_key or '', title or '')
        return storage_to_markdown(page['body']['storage']['value']), page

    def create_page(self, inp: CreatePageInput) -> dict:
        data = self.request(
            'POST', '/api/v2/pages',
            json={
                'spaceId': self._space_id(inp.space_key),
                'status': 'current',
                'title': inp.title,
                'body': {'representation': 'storage', 'value': markdown_to_storage(inp.markdown)},
            },
        )
        assert data is not None
        return data


CONFLUENCE_TOOL_MODELS: dict[str, tuple[type(BaseModel), str]] = {
    'list_spaces': (ListSpacesInput, 'List Confluence spaces available to the connected user.'),
    'get_page_markdown': (GetPageMarkdownInput, 'Fetch a Confluence page and return its content as clean Markdown.'),
    'create_page': (CreatePageInput, 'Create a new Confluence page in a space from Markdown content.')
}