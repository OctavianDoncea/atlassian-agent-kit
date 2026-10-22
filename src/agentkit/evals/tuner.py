from __future__ import annotations
import csv
import json
import statistics
import time
from openai.types.responses import Tool
import yaml
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session
from agentkit.db.models import EvalRun, Integration, ToolSchema
from agentkit.db.session import SessionLocal
from agentkit.evals.agent import AgentResponse, invoke_agent, build_tool_schemas
from agentkit.evals.judges import evaluate_case
from agentkit.evals.runner import load_cases
from agentkit.integrations.confluence import CONFLUENCE_TOOL_MODELS
from agentkit.integrations.jira import JIRA_TOOL_MODELS
from agentkit.sdk.schema import openai_tool

TOOL_REGISTRY: dict[str, tuple[type, str]] = {**JIRA_TOOL_MODELS, **CONFLUENCE_TOOL_MODELS}

@dataclass
class VariantResult:
    name: str
    description: str
    schema_id: str | None = None
    trials: int = 0
    passes: int = 0
    duration_ms: list[int] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passes / self.trials) if self.trials else 0.0

    @property
    def avg_ms(self) -> float:
        return statistics.mean(self.duration_ms) if self.duration_ms else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            'variant': self.name,
            'description': self.description,
            'schema_id': self.schema_id,
            'trials': self.trials,
            'passes': self.passes,
            'pass_rate': round(self.pass_rate, 3),
            'avg_duration_ms': round(self.avg_ms, 1),
            'failure_reasons': self.failure_reasons[:5],
        }


def load_variants(path: str = 'evals/variants.yaml') -> dict[str, list[dict]]:
    with open(path) as f:
        return yaml.safe_load(f) or {}

def _wrong_tool(expected: str) -> str:
    return 'create_issue' if expected != 'create_issue' else 'list_spaces'

def register_variant(db: Session, tool_name: str, variant: dict, model: type) -> ToolSchema:
    row = db.query(ToolSchema).filter_by(tool_name=tool_name, description_variant=variant['name']).one_or_none()
    schema = openai_tool(tool_name, variant['description'], model)
    if row is not None:
        row.description = variant['description']
        row.json_schema = schema
        db.flush()

        return row

    max_version = db.query(func.max(ToolSchema.version)).filter_by(tool_name=tool_name).scalar() or 0
    int_name = 'jira' if tool_name in JIRA_TOOL_MODELS else 'confluence'
    integration = db.query(Integration).filter_by(name=int_name).one()
    row = ToolSchema(
        integration_id = integration.id,
        tool_name = tool_name,
        version = int(max_version) + 1,
        description_variant = variant['name'],
        description = variant['description'],
        json_schema = schema,
        is_active = False
    )
    db.add(row)
    db.flush()

    return row

def tune_tool(
    tool_name: str,
    trials: int = 3,
    temperature: float = 0.7,
    dry_run: bool = False,
    variants_path: str = 'evals/variants.yaml',
    cases_path: str = 'evals/cases.yaml'
) -> list[VariantResult]:
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f'Unknown tool {tool_name!r}; registry has {sorted(TOOL_REGISTRY)}')
    variants = load_variants(variants_path).get(tool_name)
    if not variants:
        raise KeyError(f'No variants defined for {tool_name !r} in {variants_path}')
    cases = [c for c in load_cases(cases_path) if c.get('expected_tool') == tool_name]
    if not cases:
        raise KeyError(f'No eval cases target {tool_name!r}; add cases to cases.yaml first')
    model, _ = TOOL_REGISTRY[tool_name]

    results: list[VariantResult] = []
    with SessionLocal() as db:
        for vi, variant in enumerate(variants):
            row = None if dry_run else register_variant(db, tool_name, variant, model)
            res = VariantResult(name=variant['name'], description=variant['description'], schema_id=str(row.id) if row else None)
            tools = build_tool_schemas(description_overrides={tool_name: variant['description']}, use_db=False)

            for case in cases:
                for trial in range(trials):
                    start = time.time()
                    if dry_run:
                        fail = (trial + vi) % 4 == 0
                        resp = AgentResponse(tool_name=_wrong_tool(case['expected_tool']) if fail else case['expected_tool'], arguments=case.get('expected_params', {}))
                    else:
                        resp = invoke_agent(case['prompt'], temperature=temperature, tools=tools)
                    duration_ms = int((time.time() - start) * 1000)

                    judge = evaluate_case(case, resp.tool_name, resp.arguments, dry_run=dry_run)
                    res.trials += 1
                    res.duration_ms.append(duration_ms)
                    if judge.passed:
                        res.passes += 1
                    else:
                        res.failure_reasons.append(f"{case['id']}#{trial}: {judge.reasoning}")

                    if row is not None:
                        db.add(EvalRun(
                            tool_schema_id = row.id,
                            prompt = case['prompt'],
                            expected_tool = case['expected_tool'],
                            expected_params = case.get('expected_params'),
                            actual_tool = resp.tool_name,
                            actual_params = resp.arguments,
                            passed = judge.passed,
                            judge_provider = 'dry-run' if dry_run else ('llm-judge' if case.get('judge_mode') == 'semantic_jql' else 'deterministic'),
                            judge_reasoning = judge.reasoning,
                            duration_ms = duration_ms,
                        ))

            results.append(res)
            print(f'  variant {res.name:>10}: {res.passes}/{res.trials} passed ({res.pass_rate:.0%})')
        if not dry_run:
            db.commit()
    
    return results

def select_winner(results: list[VariantResult], baseline_name: str = 'baseline') -> tuple[VariantResult, str]:
    # Select the best variant based on pass rate and average duration
    baseline = next((r for r in results if r.name == baseline_name), None)
    candidates = [r for r in results if r.name != baseline_name]

    if not candidates:
        if baseline:
            return baseline, 'only baseline defined'
        
        return results[0], 'single variant defined'

    best = min(candidates, key=lambda r: (-r.pass_rate, r.avg_ms))

    if baseline is None:
        return best, f'{best.name} best among candidates ({best.pass_rate:.0%}); no baseline to compare'
    if best.pass_rate > baseline.pass_rate:
        return best, f'{best.name} beats baseline ({best.pass_rate:.0%} vs {baseline.pass_rate:.0%})'
    if best.pass_rate == baseline.pass_rate:
        return baseline, f'tie at {baseline.pass_rate:.0%}; keeping baseline for stability'
    
    return baseline, (
        f'promotion blocked: best candidate {best.name} ({best.pass_rate:.0%}) '
        f'below baseline ({baseline.pass_rate:.0%})'
    )

def promote(db: Session, tool_name: str, winner: VariantResult) -> None:
    # Deactivate all schemas for the tool, activate the winner (caller commits).
    db.query(ToolSchema).filter_by(tool_name=tool_name).update({ToolSchema.is_active: False})
    if winner.schema_id:
        row = db.query(ToolSchema).filter_by(id=UUID(winner.schema_id)).one()
        row.is_active = True

def write_report(tool_name: str, results: list[VariantResult], winner: VariantResult, reason: str, out_dir: str = 'reports') -> tuple[Path, Path]:
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dirp = Path(out_dir)
    dirp.mkdir(exist_ok=True)
    json_path = dirp / f'tuning_{tool_name}_{ts}.json'
    csv_path = dirp / f'tuning_{tool_name}_{ts}.csv'

    json_path.write_text(json.dumps({
        'tool': tool_name,
        'generated_at': ts,
        'winner': winner.name,
        'decision_reason': reason,
        'results': [r.as_dict() for r in results]
    }, indent=2))

    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['variant', 'trials', 'passes', 'pass_rate', 'avg_duration_ms', 'is_winner'])
        for r in results:
            w.writerow([r.name, r.trials, r.passes, f'{r.pass_rate:.3f}', f'{r.avg_ms:.1f}', r.name == winner.name])

    return json_path, csv_path