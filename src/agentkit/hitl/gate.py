"""Approval gate: destructive tools pause until a human decides; execution happens once, at decision time."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from agentkit.config import get_settings
from agentkit.db.models import ActionStatus, PendingAction
from agentkit.db.session import SessionLocal
from agentkit.errors import AgentKitError
from agentkit.hitl.events import publish_event
from agentkit.plugins import get_registry

class ActionExpiredError(AgentKitError): ...
class ActionAlreadyDecidedError(AgentKitError): ...


@dataclass
class GateOutcome:
    pending: bool
    action_id: str | None = None
    result: Any = None


def _requires_approval(tool_name: str) -> bool:
    if not get_settings().hitl_enabled:
        return False

    spec = get_registry().tool_specs.get(tool_name)
    return bool(spec and spec.requires_approval)

def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))

def serialize(row: PendingAction, redact: bool = True) -> dict:
    args = row.arguments

    if redact:
        from agentkit.pii import get_redactor

        args = json.loads(get_redactor().redact(json.dumps(args)).text)

    return {
        'id': str(row.id), 'session_id': row.session_id, 'tool_name': row.tool_name, 'arguments': args, 'status': row.status.value,
        'prompt': row.prompt, 'decided_by': row.decided_by, 'decision_note': row.decision_note, 'result': row.result, 'error': row.error,
        'created_at': row.created_at, 'expires_at': row.expires_at, 'decided_at': row.decided_at, 'executed_at': row.executed_at
    }

def execute_with_approval(tool_name: str, arguments: dict, clients: dict[str, Any], *, session_id: str | None = None, prompt: str | None = None, auth_mode: str = 'basic') -> GateOutcome:
    if not _requires_approval(tool_name):
        return GateOutcome(pending=False, result=get_registry().execute_tool(tool_name, arguments, clients))

    with SessionLocal() as db:
        row = PendingAction(
            session_id=session_id,tool_name=tool_name, arguments=arguments, auth_mode=auth_mode, prompt=prompt,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=get_settings().hitl_ttl_seconds)
        )
        db.add(row)
        db.commit()
        action_id = str(row.id)

    publish_event({'type': 'action_pending', 'action_id': action_id, 'tool_name': tool_name, 'session_id': session_id})

    return GateOutcome(pending=True, action_id=action_id)

def decide(action_id: str, decision: str, *, decided_by: str = 'api', note: str | None, clients: dict[str, Any] | None = None) -> dict:
    if decision not in {'approve', 'reject'}:
        raise ValueError('decision must be "approve" or "reject"')

    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        row = db.query(PendingAction).filter_by(id=UUID(action_id)).one_or_none()

        if row is None:
            raise AgentKitError(f'unknown action {action_id!r}')

        if row.status != ActionStatus.pending:
            raise ActionAlreadyDecidedError(f'action {action_id} already {row.status.value}')

        if row.expires_at < now:
            row.status = ActionStatus.expired
            db.commit()
            raise ActionExpiredError(f'action {action_id} expired at {row.expires_at}')

        row.decided_by, row.decided_at, row.decision_note = decided_by, now, note

        if decision == 'reject':
            row.status = ActionStatus.rejected
            db.commit()
            publish_event({'type': 'action_decided', 'action_id': action_id, 'status': 'rejected'})

            return serialize(row, redact=False)

        row.status = ActionStatus.approved
        db.commit()

    if clients is None:
        clients = get_registry().make_clients(auth_mode=row.auth_mode)
    
    error: str | None = None
    value: Any = None

    try:
        value = get_registry().execute_tool(row.tool_name, row.arguments, clients)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'

    with SessionLocal() as db:
        row = db.query(PendingAction).filter_by(id=UUID(action_id)).one()
        row.status = ActionStatus.executed
        row.result = _jsonable(value) if value is not None else None
        row.error = error
        row.executed_at = datetime.now(timezone.utc)
        db.commit()
        out = serialize(row, redact=False)

    publish_event({'type': 'action_executed', 'action_id': action_id, 'status': 'executed', 'error': error})

    return out

def wait_for_decision(action_id: str, ttl: float | None = None, poll: float = 2.0, on_event = None) -> dict | None:
    deadline = time.time() + (ttl if ttl is not None else get_settings().hitl_ttl_seconds)

    while time.time() < deadline:
        with SessionLocal() as db:
            row = db.query(PendingAction).filter_by(id=UUID(action_id)).one_or_none()

            if row is None:
                return None

            if row.status in (ActionStatus.executed, ActionStatus.rejected, ActionStatus.expired):
                out = serialize(row, redact=False)

                if on_event:
                    on_event({'type': 'action_decided', 'action_id': action_id, 'status': out['status']})

                return out
        time.sleep(poll)

    return None

def list_pending() -> list[dict]:
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        db.query(PendingAction).filter(PendingAction.status == ActionStatus.pending, PendingAction.expires_at < now).update({PendingAction.status: ActionStatus.expired})
        db.commit()
        rows = db.query(PendingAction).filter(PendingAction.status == ActionStatus.pending).order_by(PendingAction.created_at.asc()).all()

        return [serialize(r) for r in rows]

def history(limit: int = 50) -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(PendingAction).filter(PendingAction.status != ActionStatus.pending).order_by(PendingAction.created_at.desc()).limit(limit).all()

        return [serialize(r, redact=False) for r in rows]