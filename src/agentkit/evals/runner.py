from __future__ import annotations
import time
import logging
import yaml
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session
from agentkit.db.models import EvalRun, ToolSchema
from agentkit.db.session import SessionLocal
from agentkit.evals.agent import AgentResponse, invoke_agent
from agentkit.evals.judges import evaluate_case

logger = logging.getLogger(__name__)

def load_cases(path: str = 'evals/cases.yaml') -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    
    return data.get('cases', [])

def get_active_tool_schema_id(db: Session, tool_name: str) -> str | None:
    row = db.query(ToolSchema).filter_by(tool_name=tool_name, is_active=True).first()
    return str(row.id) if row else None

def run_suite(suite_name: str = 'default', dry_run: bool = False, concurrency: int = 1) -> dict[str, Any]:
    cases = load_cases()
    results = {'total': len(cases), 'passed': 0, 'failed': 0, 'regressions': [], 'runs': []}

    def run_case(case: dict) -> dict[str, Any]:
        case_id = case['id']
        prompt = case['prompt']
        expected_tool = case.get('expected_tool')

        print(f'Running: {case_id}...', end='', flush=True)

        start_time = time.time()
        if dry_run:
            agent_resp = AgentResponse(tool_name=expected_tool, arguments=case.get('expected_params', {}))
        else:
            agent_resp = invoke_agent(prompt)
        duration_ms = int((time.time() - start_time) * 1000)

        judge_result = evaluate_case(case, agent_resp.tool_name, agent_resp.arguments, dry_run=dry_run)

        # Sessions are not thread-safe; each worker opens its own.
        is_regression = False
        with SessionLocal() as db:
            if not judge_result.passed:
                last_run = db.query(EvalRun).filter(EvalRun.prompt == prompt, EvalRun.tool_schema_id == get_active_tool_schema_id(db, expected_tool)).order_by(EvalRun.created_at.desc()).first()
                if last_run and last_run.passed:
                    is_regression = True

            tool_schema_id = get_active_tool_schema_id(db, expected_tool or '')
            if tool_schema_id and not dry_run:
                run = EvalRun(
                    tool_schema_id = tool_schema_id,
                    prompt = prompt,
                    expected_tool = expected_tool or '',
                    expected_params = case.get('expected_params'),
                    actual_tool = agent_resp.tool_name,
                    actual_params = agent_resp.arguments,
                    passed = judge_result.passed,
                    judge_provider = 'groq/openai/gpt-oss-20b' if case.get('judge_mode') == 'semantic_jql' else 'deterministic',
                    judge_reasoning = judge_result.reasoning,
                    duration_ms = duration_ms,
                )
                db.add(run)
                db.commit()

        status = 'PASS' if judge_result.passed else 'FAIL'
        if is_regression:
            status += ' (REGRESSION)'
        print(f'{status} ({duration_ms}ms)')

        return {
            'id': case_id, 'passed': judge_result.passed, 'reasoning': judge_result.reasoning, 'regression': is_regression
        }

    if concurrency > 1:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:  # httpx/OpenAI clients are thread-safe
            outcomes = list(ex.map(run_case, cases))
    else:
        outcomes = [run_case(c) for c in cases]

    for outcome in outcomes:
        if outcome['passed']:
            results['passed'] += 1
        else:
            results['failed'] += 1
        if outcome['regression']:
            results['regressions'].append(outcome['id'])
        results['runs'].append(outcome)

    return results