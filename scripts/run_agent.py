#! /usr/bin/env python3
"""Minimal multi-turn tool calling agent over the plugin registry."""
from __future__ import annotations
import argparse
import json
from uuid import uuid4
from agentkit.config import get_settings
from agentkit.llm import chat_completion
from agentkit.llm.usage import UsageRecord
from agentkit.plugins import get_registry
from agentkit.pii import get_redactor, restore_any

def main() -> None:
    ap = argparse.ArgumentParser(description='Run a tool-calling agent over loaded plugins')
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--auth', choices=['basic', 'oauth'], default='basic')
    ap.add_argument('--max-turns', type=int, default=5)
    args = ap.parse_args()

    settings = get_settings()
    registry = get_registry()
    clients = registry.make_clients(auth_mode=args.auth, settings=settings)
    tools = registry.openai_tools()

    print(f'loaded plugins: {sorted(registry.plugins)} | tools: {sorted(registry.tool_specs)}\n')
    print(f'tools: {sorted(registry.tool_specs)}\n')

    redactor = get_redactor()
    first = redactor.redact(args.prompt)
    merged: dict[str, str] = dict(first.mapping)
    if first.count:
        print(f'redacted {first.count} sensitive item(s) before LLM egress')
    messages: list[dict] = [{'role': 'user', 'content': first.text}]
    session_id = uuid4().hex[:8]
    usages: list[UsageRecord] = []

    for turn in range(args.max_turns):
        result = chat_completion(messages=messages, purpose='agent_loop', tools=tools, temperature=0.0, ref=f'{session_id}/turn-{turn}')
        usages.append(result.usage)
        msg = result.message
        print(f"#{turn} {result.usage.model} in={result.usage.input_tokens} out={result.usage.output_tokens} ${result.usage.cost_usd:.6f}")

        if not msg.tool_calls:
            print(f'\n{msg.content}')
            _print_spend(usages)
            return

        messages.append(msg)

        for tc in msg.tool_calls:
            arguments = json.loads(tc.function.arguments or '{}')
            arguments = restore_any(arguments, merged)
            print(f'{tc.function.name}({arguments})')
            
            try:
                result = registry.execute_tool(tc.function.name, arguments, clients)
                content = json.dumps(result, default=str)[:4000]
            except Exception as exc:
                content = f'ERROR: {type(exc).__name__}: {exc}'
            
            redacted_result = redactor.redact(content)
            merged.update(redacted_result.mapping)
            print(f'  -> {redacted_result.text[:200]}')
            messages.append({'role': 'tool', 'tool_call_id': tc.id, 'content': redacted_result.text})

    print('\nmax turns reached without a final answer')
    _print_spend(usages)

def _print_spend(usages: list[UsageRecord]) -> None:
    total_in = sum(item.input_tokens for item in usages)
    total_out = sum(item.output_tokens for item in usages)
    total_cost = sum(item.cost_usd for item in usages)
    print(f'session spend: {total_in} in + {total_out} out = ${total_cost:.6f}')

if __name__ == '__main__':
    main()