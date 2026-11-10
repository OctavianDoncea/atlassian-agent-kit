"""Approve/reject from the terminal when no API server is running."""
from __future__ import annotations
import argparse
import json
from agentkit.hitl.gate import decide, list_pending

def main() -> None:
    ap = argparse.ArgumentParser(prog='hitl')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    dec = sub.add_parser('decide')
    dec.add_argument('--id', required=True)
    dec.add_argument('--decision', choices=['approve', 'reject'], default='approve')
    dec.add_argument('--by', default='cli')
    dec.add_argument('--note', default=None)
    args = ap.parse_args()

    if args.cmd == 'list':
        print(json.dumps(list_pending(), indent=2, default=str))
    else:
        out = decide(args.id, args.decision, decided_by=args.by, note=args.note)
        print(json.dumps(out, indent=2, default=str))

if __name__ == '__main__':
    main()