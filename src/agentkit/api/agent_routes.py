"""Run gated agent sessions from the dashboard."""
from __future__ import annotations
import threading
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from agentkit.agent_loop import run_agent_session
from agentkit.hitl.events import publish_event

router = APIRouter(prefix='/api/agent', tags=['agent'])
_lock = threading.Lock()
_sessions: dict[str, dict] = {}

class RunBody(BaseModel):
    prompt: str
    auth_mode: str = 'basic'
    max_turns: int = 4


@router.post('/run')
def run(body: RunBody, background: BackgroundTasks) -> dict:
    with _lock:
        running = [s for s in _sessions.values() if s['status'] == 'running']

        if running:
            raise HTTPException(409, 'An agent session is already running!')

        session_id = 'pending'
        _sessions['pending'] = {'status': 'running', 'events': [], 'summary': None}

    def on_event(event: dict) -> None:
        with _lock:
            for sid, s in _sessions.items():
                if s['status'] == 'running':
                    s['events'].append(event)
                    session_id = sid
                    break
        
        publish_event(event)

    def _job() -> None:
        summary = run_agent_session(body.prompt, auth_mode=body.auth_mode, max_turns=body.max_turns, on_event=on_event)

        with _lock:
            key = summary.session_id
            _sessions[key] = {'status': 'done', 'events': _sessions.pop('pending', {}).get('events', []), 'summary': summary.__dict__}

    background.add_task(_job)
    return {'status': 'started'}

@router.get('/sessions/{session_id}')
def session(session_id: str) -> dict:
    with _lock:
        state = _sessions.get(session_id) or next(
            (s for k, s in _sessions.items() if k != 'pending' and s.get('summary', {}) and s['summary'].get('session_id') == session_id), None
        )

    if state is None:
        raise HTTPException(404, 'unknown session')

    return state