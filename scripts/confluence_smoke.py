from __future__ import annotations
import argparse
from agentkit.db.models import Integration
from agentkit.db.session import SessionLocal
from agentkit.integrations.confluence import ConfluenceClient
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import DbTokenStore

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--auth', choices=['oauth', 'basic'], default='oauth')
    ap.add_argument('--space', default='EW')
    args = ap.parse_args()

    cloud_id = None
    if args.auth == 'oauth':
        with SessionLocal() as db:
            cloud_id = db.query(Integration).filter_by(name='confluence').one().cloud_id
        client = ConfluenceClient(cloud_id=cloud_id, auth_mode='oauth', token_store=DbTokenStore(), auth_manager=AuthManager())
    else:
        client = ConfluenceClient(auth_mode='basic')

    spaces = client.list_spaces(limit=10)
    print('spaces:', [s['key'] for s in spaces])

    data = client.request('GET', '/rest/api/content', params={'spaceKey': args.space, 'limit': 1, 'expand': 'body.storage'})
    results = (data or {}).get('results', [])
    if not results:
        print(f'no pages in space {args.space}')
        return
    markdown, page = client.get_page_markdown(page_id=results[0]['id'])
    print(f"page: {page['title']} ({len(markdown)} chars of markdown)")
    print('Preview')
    print('\n'.join(markdown.splitlines()[:25]))

if __name__ == '__main__':
    main()