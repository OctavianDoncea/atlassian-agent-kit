#! /usr/bin/env python3
"""Minimal multi-turn tool calling agent over the plugin registry."""
from __future__ import annotations
import argparse
import json
from openai import OpenAI
from agentkit.config import get_settings
from agentkit.plugins import get_registry

def main() -> None:
    ap = argparse.ArgumentParser(description='Run a tool-calling agent over loaded plugins')
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--auth', choices=['basic', 'oauth'], default='basic')
    ap.add_argument('--max-turns', type=int, default=4)
    args = ap.parse_args()

    settings = get_settings()
    registry = get_registry()
    clients = registry.make_clients(auth_mode=args.auth, settings=settings)
    tools = registry.openai_tools()
    print(f'loaded plugins: {sorted(registry.plugins)} | tools: {sorted(registry.tool_specs)}\n')

    llm = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    messages: list[dict] = [{'role': 'user', 'content': args.prompt}]

    for turn in range(args.max_turns):
        resp = llm.chat.completions.create(model=settings.llm_model, messages=messages, tools=tools, tool_choice='auto')
        msg = resp.choices[0].message

        if not msg.tool_calls:
            print(f'\n{msg.content}')
            return

        messages.append(msg)

        for tc in msg.tool_calls:
            arguments = json.loads(tc.function.arguments or '{}')
            print(f'{tc.function.name}({arguments})')
            
            try:
                result = registry.execute_tool(tc.function.name, arguments, clients)
                content = json.dumps(result, default=str)[:4000]
            except Exception as exc:
                content = f'ERROR: {type(exc).__name__}: {exc}'
            
            print(f'  -> {content[:200]}')
            messages.append({'role': 'tool', 'tool_call_id': tc.id, 'content': content})

        print('\nmax turns reached without a final answer')

if __name__ == '__main__':
    main()