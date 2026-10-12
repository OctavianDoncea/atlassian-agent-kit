from __future__ import annotations
import html
import re
from pydantic import BaseModel, Field
from sqlalchemy.util.cython import returns
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
    blocks: [b.strip() for b in re.split(r"\n\s*\n", markdown or '') if b.strip()]
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

    def list_spaces(self, limit: int = 25) -> list[dict]:
        return list(self.paginate('/rest/api/space', params={'type': 'global'}, items_key='results', start_param='start', limit_param='limit', limit=limit, max_items=limit))

    def find_page(self, space_key: str, title: str) -> dict:
        data = self.request('GET', '/rest/api/content', params={'spaceKey': space_key, 'title': title, 'expand': 'body.storage,version.space'})
        results = (data or {}).get('results', [])

        if not results:
            raise PageNotFoundError(f'No page titled {title!r} in space {space_key!r}')

        return results[0]

    def get_page(self, self_id: str) -> dict:
        data = self.request('GET', f'/rest/api/content/{self_id}', params={'expand': 'body.storage,version.space'})
        assert data is not None
        return data

    def get_page_markdown(self, page_id: str | None = None, space_key: str | None = None, title: str | None = None) -> tuple[str, dict]:
        page = self.get_page(page_id) if page_id else self.find_page(space_key or '', title or '')
        return storage_to_markdown(page['body']['storage']['value']), page

    def create_page(self, inp: CreatePageInput) -> dict:
        data = self.request(
            'POST', '/rest/api/content',
            json={
                'space': {'key': inp.space_key},
                'title': inp.title,
                'body': {'storage': {'value': markdown_to_storage(inp.markdown), 'representation': 'storage'}}
            }
        )
        assert data is not None
        return data


CONFLUENCE_TOOL_MODELS: dict[str, tuple[type(BaseModel), str]] = {
    'list_spaces': (ListSpacesInput, 'List Confluence spaces available to the connected user.'),
    'get_page_markdown': (GetPageMarkdownInput, 'Fetch a Confluence page and return its content as clean Markdown.'),
    'create_page': (CreatePageInput, 'Create a new Confluence page in a space from Markdown content.')
}