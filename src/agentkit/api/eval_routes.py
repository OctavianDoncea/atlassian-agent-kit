from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from agentkit.api.schemas import EvalRunOut, OverviewOut, RegressionOut, RunStateOut, TimeseriesPointOut, VariantStatOut
from agentkit.db.models import EvalRun, ToolSchema
from agentkit.db.session import SessionLocal
from agentkit.evals.runner import run_suite

router = APIRouter(prefix='/api', tags=['observability'])
_run_state: dict[str, Any] = {'running': False, 'started_at': None, 'finished_at': None, 'last_summary': None}

# Helpers
def _map_rows(rows: list[tuple[EvalRun, str, str | None]]) -> list[EvalRunOut]:
    return [EvalRunOut(
        id = str(r.id),
        tool_schema_id = str(r.tool_schema_id),
        created_at = r.created_at,
        tool_name = tool_name,
        variant = variant,
        prompt = r.prompt,
        expected_tool = r.expected_tool,
        expected_params = r.expected_params,
        actual_tool = r.actual_tool,
        actual_params = r.actual_params,
        passed = r.passed,
        judge_provider = r.judge_provider,
        judge_reasoning = r.judge_reasoning,
        duration_ms = r.duration_ms,
    ) for r, tool_name, variant in rows]

def _fetch_runs(db: Session, limit: int = 2000, asc: bool = False, tool: str | None = None, passed: bool | None = None) -> list[EvalRunOut]:
    q = db.query(EvalRun, ToolSchema.tool_name, ToolSchema.description_variant).join(ToolSchema, EvalRun.tool_schema_id == ToolSchema.id)
    
    if tool:
        q = q.filter(ToolSchema.tool_name == tool)
    if passed is not None:
        q = q.filter(EvalRun.passed.is_(passed))
    
    q = q.order_by(EvalRun.created_at.asc() if asc else EvalRun.created_at.desc()).limit(limit)
    return _map_rows(q.all())

def detect_regressions(runs_asc: list[EvalRunOut]) -> list[RegressionOut]:
    last_passed: dict[str, bool] = {}
    out: list[RegressionOut] = []

    for run in runs_asc:
        key = f'{run.prompt}::{run.tool_schema_id}'
        if not run.passed and last_passed.get(key, False):
            out.append(RegressionOut(id=run.id, created_at=run.created_at, tool_name=run.tool_name, prompt=run.prompt, reasoning=run.judge_reasoning))
        last_passed[key] = run.passed

    return out

# Endpoints
@router.get('/overview', response_model=OverviewOut)
def overview(days: int = Query(7, ge=1, le=90)) -> OverviewOut:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with SessionLocal() as db:
        total = db.query(func.count(EvalRun.id)).scalar() or 0
        passed = db.query(func.count(EvalRun.id)).filter(EvalRun.passed.is_(True)).scalar() or 0
        active_tools = db.query(func.count(ToolSchema.id)).filter_by(is_active=True).scalar() or 0
        last_run_at = db.query(func.max(EvalRun.created_at)).scalar()
        recent = _fetch_runs(db, limit=5000, asc=True)

    regs = [r for r in detect_regressions(recent) if r.created_at >= cutoff]
    return OverviewOut(
        total_runs = total,
        overall_pass_rate = passed / total if total > 0 else 0.0,
        active_tools = active_tools,
        regressions_last_7d = len(regs),
        last_run_at = last_run_at
    )

@router.get('/evals', response_model=list[EvalRunOut])
def list_evals(limit: int = Query(100, ge=1, le=1000), tool: str | None = None, passed: bool | None = None) -> list[EvalRunOut]:
    with SessionLocal() as db:
        return _fetch_runs(db, limit=limit, tool=tool, passed=passed)

@router.get('/evals/timeseries', response_model=list[TimeseriesPointOut])
def timeseries(days: int = Query(14, ge=1, le=90)) -> list[TimeseriesPointOut]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with SessionLocal() as db:
        rows = db.query(EvalRun).filter(EvalRun.created_at >= cutoff).all()

    buckets: dict[str, dict[str, int]] = {}
    for r in rows:
        b = buckets.setdefault(r.created_at.strftime('%Y-%m-%d'), {'total': 0, 'passed': 0})
        b['total'] += 1
        b['passed'] += 1 if r.passed else 0

    out: list[TimeseriesPointOut] = []
    for i in range(1, days+1):
        day = (cutoff + timedelta(days=i)).strftime('%Y-%m-%d')
        b = buckets.get(day, {'total': 0, 'passed': 0})
        out.append(TimeseriesPointOut(bucket=day, total=b['total'], passed=b['passed'], pass_rate=(b['passed'] / b['total'] if b['total'] else 0.0)))

    return out

@router.get('/tools', response_model=list[VariantStatOut])
def tools() -> list[VariantStatOut]:
    with SessionLocal() as db:
        rows = (db.query(
            ToolSchema, func.count(EvalRun.id), func.sum(case((EvalRun.passed.is_(True), 1), else_=0)), func.avg(EvalRun.duration_ms)
        ).outerjoin(EvalRun, EvalRun.tool_schema_id == ToolSchema.id)
        .group_by(ToolSchema.id)
        .order_by(ToolSchema.tool_name, ToolSchema.version)
        .all()
        )
        out = []

        for schema, trials, passed, avg_ms in rows:
            trials_i, passes_i = int(trials or 0), int(passed or 0)
            out.append(VariantStatOut(
                tool_name = schema.tool_name,
                variant = schema.description_variant,
                version = schema.version,
                is_active = schema.is_active,
                description = schema.description,
                json_schema = schema.json_schema,
                trials = trials_i,
                passes = passes_i,
                pass_rate = passes_i / trials_i if trials_i else 0.0,
                avg_duration_ms = float(avg_ms or 0.0)
            ))

    return out

@router.get('/regressions', response_model=list[RegressionOut])
def regressions(limit: int = Query(3000, ge=10, le=5000)) -> list[RegressionOut]:
    with SessionLocal() as db:
        runs = _fetch_runs(db, limit=limit, asc=True)
    
    return detect_regressions(runs)[::-1][:100]

@router.post('/evals/run', response_model=RunStateOut)
def trigger_run(background: BackgroundTasks, dry_run: bool = False) -> RunStateOut:
    if _run_state['running']:
        raise HTTPException(status_code=409, detail='An eval run is already in progress')
    
    _run_state.update(running=True, started_at=datetime.now(timezone.utc), finished_at=None, last_summary=None)

    def _job() -> None:
        try:
            summary = run_suite(dry_run=dry_run)
            _run_state['last_summary'] = summary
        finally:
            _run_state['running'] = False
            _run_state['finished_at'] = datetime.now(timezone.utc)

    background.add_task(_job)
    
    return RunStateOut(**_run_state)

@router.get('/evals/run/status', response_model=RunStateOut)
def run_status() -> RunStateOut:
    return RunStateOut(**_run_state)