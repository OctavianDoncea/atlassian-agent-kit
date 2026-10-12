"""OAuth connect flow"""
from __future__ import annotations
import secrets
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from agentkit.config import get_settings
from agentkit.db.models import Integration
from agentkit.db.session import SessionLocal
from agentkit.errors import AgentKitError
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import DbTokenStore

router = APIRouter(prefix='/auth/atlassian', tags=['auth'])

@router.get('/authorize')
def authorize() -> RedirectResponse:
    am = AuthManager()
    url = am.build_authorize_url()
    state = url.split('state=', 1)[1]
    resp = RedirectResponse(url)
    resp.set_cookie('oauth_state', state, httponly=True, samesite='lax', max_age=get_settings().oauth_state_ttl_seconds)

    return resp

@router.get('/callback')
def callback(request: Request, code: str = '', state: str = '', error: str = '') -> HTMLResponse:
    if error:
        raise HTTPException(status_code=400, detail=f'Atlassian returned error: {error}')
    if not code or not state:
        raise HTTPException(status_code=400, detail='missing code/state')

    cookie_state = request.cookies.get('oauth_state', '')
    if not cookie_state or not secrets.compare_digest(cookie_state, state):
        raise HTTPException(status_code=400, detail='state cookie mismatch (possible CSRF)')

    am = AuthManager()
    try:
        am.verify_state(state)
        tokens = am.exchange_code(code)
        resources = am.discover_resources(tokens.access_token)
        cloud_id, site_url = am.pick_cloud_id(resources)
    except AgentKitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    DbTokenStore().save(cloud_id, site_url, tokens)

    with SessionLocal() as db:
        for row in db.query(Integration).filter(Integration.type.in_(['jira', 'confluence'])).all():
            row.cloud_id = cloud_id
            row.site_url = site_url
        db.commit()

    return HTMLResponse(f'<h1>Connected</h1><p>cloud_id: <code>{cloud_id}</code></p><p>You can close this tab.</p>')

@router.get('/status')
def status() -> dict:
    store = DbTokenStore()
    with SessionLocal() as db:
        rows = db.query(Integration).all()
        return {
            'integrations': [
                {'name': r.name, 'type': r.type.value, 'cloud_id': r.cloud_id, 'connected': bool(r.cloud_id and store.load(r.cloud_id) is not None)}
                for r in rows
            ]
        }