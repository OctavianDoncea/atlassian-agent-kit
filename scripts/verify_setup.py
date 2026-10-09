from __future__ import annotations
import sys
import httpx
from sqlalchemy import text
from agentkit.config import get_settings
from agentkit.db.session import engine

RESULTS: list[tuple[str, bool, str]] = []

def record(name: str, ok: bool, detail: str = '') -> None:
    RESULTS.append((name, ok, detail))

def check_database() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        record('PostgreSQL reachable', True, engine.url.render_as_string(hide_password=True))
    except Exception as e:
        record('PostgreSQL reachable', False, f'{type(e).__name__}: {e}')

def check_migrations() -> None:
    try:
        with engine.connect() as conn:
            version = conn.execute(text('SELECT version_num FROM alembic_version')).scalar()
        if version:
            record('Alembic at head', True, f'revision={version}')
        else:
            record('Alembic at head', False, 'alembic_version empty: run `alembic upgrade head`')
    except Exception as e:
        record('Alembic at head', False, f'{type(e).__name__}: {e}')

def check_tables() -> None:
    expected = {'integrations', 'tool_schemas', 'eval_runs'}
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            found = {r[0] for r in rows}
        missing = expected - found
        record('Core tables exist', not missing, f'missing={missing}' if missing else f'found={sorted(expected)}')
    except Exception as e:
        record('Core tables exist', False, str(e))

def check_env() -> None:
    s = get_settings()
    values = {
        'ATLASSIAN_CLIENT_ID': s.atlassian_client_id,
        'ATLASSIAN_CLIENT_SECRET': s.atlassian_client_secret,
        'ATALSSIAN_REDIRECT_URI': s.atlassian_redirect_uri,
        'ATLASSIAN_SITE_URL': s.atlassian_site_url
    }
    missing = [k for k, v in values.items() if not v]
    record('Atlassian env vars set', not missing, f'missing={missing}' if missing else 'all present')

def check_atlassian_api() -> None:
    s = get_settings()
    if not (s.atlassian_email and s.atlassian_api_token and s.atlassian_site_url):
        record('Atlassian API smoke test', False, 'skipped: set ATLASSIAN_EMAIL / ATLASSIAN_API_TOKEN / ATLASSIAN_SITE_URL')
        return
    auth = (s.atlassian_email, s.atlassian_api_token)
    base = s.atlassian_site_url.rstrip('/')
    try:
        r = httpx.get(f'{base}/rest/api/3/myself', auth=auth, timeout=15)
        r.raise_for_status()
        display = r.json().get('displayName', '?')
        r2 = httpx.get(f'{base}/wiki/api/v2/spaces', auth=auth, timeout=15, params={'limit': 1})
        r2.raise_for_status()
        record('Atlassian API smoke test', True, f'Jira myself OK ({display}); Confluence spaces OK')
    except Exception as e:
        record('Atlassian API smoke test', False, f'{type(e).__name__}: {e}')

def main() -> int:
    check_database()
    check_migrations()
    check_tables()
    check_env()
    check_atlassian_api()

    width = max(len(n) for n, _, _ in RESULTS)
    failed = 0
    for name, ok, detail in RESULTS:
        failed += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail}")
    print(f'\nVerification:', 'COMPLETE' if failed == 0 else f'{failed} check(s) FAILED')
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())