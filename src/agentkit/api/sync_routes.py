"""Trigger and insoect the concurrent Confluence sync pipeline."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from agentkit.db.models import PageSnapshot
from agentkit.db.session import SessionLocal
from agentkit.integrations.sync_pipeline import sync_space_concurrently

router = APIRouter(prefix='/api/sync', tags=['sync'])
_sync_state: dict[str, Any] = {'running': False, 'last_report': None}

async def _run(space_key: str, concurrency: int, max_pages: int) -> None:
    try:
        report = await sync_space_concurrently(space_key, concurrency=concurrency, max_pages=max_pages)
        _sync_state['last_report'] = report.__dict__
    finally:
        _sync_state['running'] = False

@router.post('/spaces/{space_key}')
def trigger(space_key: str, background: BackgroundTasks, concurrency: int = Query(8, ge=1, le=32), max_pages: int = Query(100, ge=1, le=500)):
    if _sync_state['running']:
        raise HTTPException(409, 'A sync is already in progress')
    _sync_state['running'] = True
    background.add_task(_run, space_key, concurrency, max_pages)
    
    return {'status': 'started', 'space_key': space_key, 'concurrency': concurrency}

@router.get('/status')
def status() -> dict[str, Any]:
    return _sync_state

@router.get('/snapshots')
def snapshots(space: str | None = None, limit: int = Query(50, ge=1, le=200)):
    with SessionLocal() as db:
        q = db.query(PageSnapshot)
        
        if space:
            q = q.filter_by(space_key=space)
        rows = q.order_by(PageSnapshot.synced_at.desc()).limit(limit).all()

        return [{'space_key': r.space_key, 'page_id': r.page_id, 'title': r.title, 'content_hash': r.content_hash[:12], 'synced_at': r.synceed_at} for r in rows]