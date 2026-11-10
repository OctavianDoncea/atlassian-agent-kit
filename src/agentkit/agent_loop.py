"""Multi-turn tool calling agent session with Human-in-the-loop gating and PII boundaries."""
from __future__ import annotations
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from agentkit.config import get_settings
from agentkit.hitl.gate import execute_with_approval, wait_for_decision
from agentkit.llm import chat_completion
from agentkit.pii import get_redactor, restore_any
from agentkit.plugins import get_registry

@dataclass
class SessionSummary:
    session_id: str
    turns: int = 0
    final_answer: str | None = None
    pending_encountered: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    events: list[dict] = field(default_factory=list)


def run_agent_session(prompt: str, auth_mode: str = 'basic', max_turns: int = 4, on_event: Callable[[dict], None] | None = None) -> SessionSummary:
    settings = get_settings()
    registry = get_registry()
    clients = registry.make_clients(auth_mode=auth_mode, settings=settings)
    tools = registry.openai_tools()
    redactor = get_redactor()
    session_id = uuid.uuid4().hex[:8]
    summary = SessionSummary(session_id=session_id)

    def emit(event: dict) -> None:
        summary.events.append(event)

        if on_event:
            on_event(event)

    first = redactor.redact(prompt)
    merged: dict[str, str] = dict(first.mapping)

    if first.count:
        emit({'type': 'pii_redacted', 'count': first.count, 'session_id': session_id})

    messages: list[dict] = [{'role': 'user', 'content': first.text}]

    for turn in range(max_turns):
        result = chat_completion(messages=messages, purpose='agent_loop', tools=tools, temperature=0.0, ref=f'session:{session_id}:turn:{turn}')
        summary.input_tokens += result.usage.input_tokens
        summary.output_tokens += result.usage.output_tokens
        summary.cost_usd += result.usage.cost_usd
        summary.turns += turn + 1
        msg = result.message
        emit ({'type': 'agent_turn', 'session_id': session_id, 'turn': turn, 'cost_usd': round(result.usage.cost_usd, 6)})

        if not msg.tool_calls:
            summary.final_answer = msg.content
            return summary

        messages.append(msg)

        for tc in msg.tool_calls:
            arguments = restore_any(json.loads(tc.function.arguments or '{}'), merged)
            outcome = execute_with_approval(tc.function.name, arguments, clients, session_id=session_id, prompt=first.text, auth_mode=auth_mode)

            if outcome.pending:
                summary.pending_encountered += 1
                emit({'type': 'action_pending', 'session_id': session_id, 'action_id': outcome.action_id, 'tool_name': tc.function.name})
                decided = wait_for_decision(outcome.action_id, on_event=on_event)

                if decided is None:
                    content = 'ERROR: human approval timed out; action expired'
                elif decided['status'] == 'rejected':
                    content = f"ERROR: human rejected this action ({decided.get('decision_note') or 'no_reason'})"
                elif decided.get('error'):
                    content = f"ERROR: {decided['error']}"
                else:
                    content = json.dumps(decided.get('result'), default=str)[:4000]
            else:
                content = json.dumps(outcome.result, default=str)[:4000]

            red = redactor.redact(content)
            merged.update(red.mapping)
            messages.append({'role': 'tool', 'tool_call_id': tc.id, 'content': red.text})

    summary.final_answer = '(max turns reached without a final answer)'
    return summary