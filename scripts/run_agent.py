#! /usr/bin/env python3
"""CLI wrapper around the gated agent session."""
import argparse
from agentkit.agent_loop import run_agent_session
from agentkit.hitl.events import publish_event

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--auth', choices=['basic', 'oauth'], default='basic')
    ap.add_argument('--max-turns', type=int, default=4)
    args = ap.parse_args()

    def on_event(event: dict) -> None:
        publish_event(event)
        kind = event.get('type')

        if kind == 'agent_turn':
            print(f"turn {event['turn']} (≈${event['cost_usd']:.6f})")
        elif kind == 'pii_redacted':
            print(f"redacted {event['count']} sensitive item(s)")
        elif kind == 'action_pending':
            print(f"HUMAN APPROVAL REQUIRED: {event['tool_name']} (action {event['action_id']})")
            print(f"  approve via dashboard, or: make approve id={event['action_id']}")

    summary = run_agent_session(args.prompt, auth_mode=args.auth, max_turns=args.max_turns, on_event=on_event)

    if summary.final_answer:
        print(f'\n{summary.final_answer}')
    
    print(f'\nsession {summary.session_id}: {summary.turns} turns, '
          f'{summary.input_tokens + summary.output_tokens} tokens ≈ ${summary.cost_usd:.6f}, '
          f'{summary.pending_encountered} approval(s)')

if __name__ == '__main__':
    main()