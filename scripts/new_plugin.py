#!/usr/bin/env python3
"""Scaffold a new drop-in plugin so adding an integration is one command."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

TEMPLATE = '''"""Plugin: {title}.

Add tools below, then run: pytest tests/test_plugin_contract.py
The contract suite validates your plugin automatically.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from agentkit.plugins.base import IntegrationPlugin, ToolSpec

class ExampleInput(BaseModel):
    query: str = Field(description="What to look up")


class {cls}Plugin(IntegrationPlugin):
    name = "{slug}"
    display_name = "{title}"
    version = "0.1.0"

    def example_tool(self, inp: ExampleInput) -> dict:
        return {"echo": inp.query}

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "{slug}_example",
                "Describe exactly when an agent should call this tool.",
                ExampleInput,
                lambda c, i: c.example_tool(i)
            )
        ]
'''

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True, help='e.g. github, linear, notion')
    ap.add_argument('--dir', default='plugins')
    args = ap.parse_args()

    slug = re.sub(r'[^a-z0-9]', '_', args.name.lower().strip())
    path = Path(args.dir) / f'{slug}.py'

    if path.exists():
        raise SystemExit(f'refusing to overwrite {path}')

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(slug=slug, title=args.name.title(), cls=slug.title().replace('_', '')))
    print(f'created {path}\nNext:\n 1. implement tools() + real API calls\n 2. pytest tests/test_plugin_contract.py\n 3. python scripts/run_agent.py --prompt "..." to see it live')

if __name__ == '__main__':
    main()