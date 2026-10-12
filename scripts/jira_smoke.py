from __future__ import annotations
import argparse
from agentkit.config import get_settings
from agentkit.db.models import Integration
from agentkit.db.session import SessionLocal
from agentkit.integrations.jira import CreateIssueInput, JiraClient
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import DbTokenStore

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--auth', choices=['oauth', 'basic'], default='oauth')
    args = ap.parse_args()
    settings = get_settings()
    cloud_id = None

    if args.auth == 'oauth':
        with SessionLocal() as db:
            row = db.query(Integration).filter_by(name='jira').one()
            cloud_id = row.cloud_id
        client = JiraClient(cloud_id=cloud_id, auth_mode='oauth', token_store=DbTokenStore())
    else:
        client = JiraClient(auth_mode='basic')

    issues = client.search_issues('project = ENG ORDER BY created DESC', fields=['summary', 'status'], max_results=10)
    print(f"search: {len(issues)} issue(s); first = {issues[0]['key'] if issues else '-'}")

    created = client.create_issue(CreateIssueInput(project_key='ENG', summary='Smoke test issue', issue_type='Task'))
    key = created['key']
    print(f"created: {key}")

    transitions = client.get_transitions(key)
    print('allowed transitions:', [t['name'] for t in transitions])
    if transitions:
        client.transition_issue(key, transitions[0]['name'])
        after = client.get_issue(key, fields=['status'])
        print(f"transitioned {key} -> {after['fields']['status']['name']}")

if __name__ == '__main__':
    main()