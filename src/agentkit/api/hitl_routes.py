from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agentkit.errors import AgentKitError
from agentkit.hitl import bus
from agentkit.hitl.gate import decide, list_pending, history

router = APIRouter(prefix='/api/hitl', tags=['hitl'])

class DecideBody(BaseModel):
    decision: str
    note: str | None = None
    decided_by: str = 'dashboard'


@router.get('/pending')
def pending() -> dict:
    return {'pending': list_pending()}

@router.get('/history')
def hist(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    return history(limit)

@router.post('/{action_id}/decide')
def decide_router(action_id: str, body: DecideBody) -> dict:
    try:
        return decide(action_id, body.decision, decided_by=body.decided_by, note=body.note)
    except AgentKitError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

@router.get('/stream')
async def stream(request: Request) -> StreamingResponse:
    q = bus.subscribe()

    async def gen():
        try:
            yield 'event: snapshot\ndata: ' + json.dumps({'pending': list_pending()}) + '\n\n'

            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15)
                    yield f'event: hitl\ndata: {json.dumps(payload, default=str)}\n\n'
                except asyncio.TimeoutError:
                    yield ': heartbeat\n\n'
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})