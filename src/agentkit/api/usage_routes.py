"""Spend totals, per-purpose breakdown, and a daily series for the dashboard."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from agentkit.db.models import LLMUsage
from agentkit.db.session import SessionLocal

router = APIRouter(prefix='/api/usage', tags=['usage'])

@router.get('/summary')
def summary(days: int = Query(30, ge=1, le=365)) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    with SessionLocal() as db:
        rows = db.query(LLMUsage).filter(LLMUsage.created_at >= cutoff).all()

    totals = {'calls': len(rows), 'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0}
    by_purpose: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    daily: dict[str, dict] = {}
    
    for row in rows:
        cost = float(row.cost_usd)
        totals['input_tokens'] += row.input_tokens
        totals['output_tokens'] += row.output_tokens
        totals['cost_usd'] += cost
        purpose = by_purpose.setdefault(row.purpose, {'purpose': row.purpose, 'calls': 0, 'tokens': 0, 'cost_usd': 0.0})
        purpose['calls'] += 1
        purpose['tokens'] += row.total_tokens
        purpose['cost_usd'] += cost
        model = by_model.setdefault(row.model, {'model': row.model, 'calls': 0, 'tokens': 0, 'cost_usd': 0.0})
        model['calls'] += 1
        model['tokens'] += row.total_tokens
        model['cost_usd'] += cost
        bucket = row.created_at.strftime('%Y-%m-%d')
        day = daily.setdefault(bucket, {'bucket': bucket, 'tokens': 0, 'cost_usd': 0.0})
        day['tokens'] += row.total_tokens
        day['cost_usd'] += cost

    filled_daily = []
    for i in range(1, days + 1):
        bucket = (cutoff + timedelta(days=i)).strftime('%Y-%m-%d')
        filled_daily.append(daily.get(bucket, {'bucket': bucket, 'tokens': 0, 'cost_usd': 0.0}))

    totals['cost_usd'] = round(totals['cost_usd'], 6)
    for collection in (by_purpose.values(), by_model.values(), filled_daily):
        for item in collection:
            item['cost_usd'] = round(item['cost_usd'], 6)

    return {
        'totals': totals,
        'by_purpose': sorted(by_purpose.values(), key=lambda item: -item['cost_usd']),
        'by_model': sorted(by_model.values(), key=lambda item: -item['cost_usd']),
        'daily': filled_daily,
    }

@router.get('/recent')
def recent(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(LLMUsage).order_by(LLMUsage.created_at.desc()).limit(limit).all()
    
    return [
        {
            'purpose': row.purpose,
            'model': row.model,
            'ref': row.ref,
            'input_tokens': row.input_tokens,
            'output_tokens': row.output_tokens,
            'cost_usd': float(row.cost_usd),
            'estimated': row.estimated,
            'duration_ms': row.duration_ms,
            'created_at': row.created_at.isoformat(),
        }
        for row in rows
    ]