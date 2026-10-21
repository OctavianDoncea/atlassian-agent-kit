from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel

class EvalRunOut(BaseModel):
    id: str
    tool_schema_id: str
    created_at: datetime
    tool_name: str
    variant: str | None
    prompt: str
    expected_tool: str
    expected_params: dict | None
    actual_tool: str | None
    actual_params: dict | None
    passed: bool
    judge_provider: str | None
    judge_reasoning: str | None
    duration_ms: int | None


class VariantStatOut(BaseModel):
    tool_name: str
    variant: str | None
    version: int
    is_active: bool
    description: str
    json_schema: dict | None
    trials: int
    passes: int
    pass_rate: float
    avg_duration_ms: float


class TimeseriesPointOut(BaseModel):
    bucket: str
    total: int
    passed: int
    pass_rate: float


class OverviewOut(BaseModel):
    total_runs: int
    overall_pass_rate: float
    active_tools: int
    regressions_last_7d: int
    last_run_at: datetime | None


class RegressionOut(BaseModel):
    id: str
    created_at: datetime
    tool_name: str
    prompt: str
    reasoning: str | None


class RunStateOut(BaseModel):
    running: bool
    started_at: datetime | None
    finished_at: datetime | None
    last_summary: dict[str, Any] | None