#! /usr/bin/env python3
import argparse
import sys
from rich.console import Console
from rich.table import Table
from agentkit.db.session import SessionLocal
from agentkit.evals.tuner import promote, select_winner, tune_tool, write_report

def main() -> int:
    ap = argparse.ArgumentParser(description="Tune a tool's LLM description via eval-driven A/B tests")
    ap.add_argument('--tool', required=True, help='Tune name, e.g. search_issues')
    ap.add_argument('--trials', type=int, default=3, help='trials per case per variant')
    ap.add_argument('--temperature', type=float, default=0.7, help='Sampling temperature (diversity)')
    ap.add_argument('--dry-run', action='store_true', help='Mock agent responses; no DB writes')
    ap.add_argument('--no-promote', action='store_true', help='Measure only; never flip is_active')
    args = ap.parse_args()

    console = Console()
    console.print(f'\n[bold blue]Tuning descriptions for {args.tool}[/bold blue]'
                  f'(trials={args.trials}, temperature={args.temperature})\n')

    results = tune_tool(args.tool, trials=args.trials, temperature=args.temperature, dry_run=args.dry_run)
    winner, reason = select_winner(results)

    if args.dry_run:
        console.print('[yellow]dry-run: no promotion performed[/yellow]')
    elif args.no_promote:
        console.print('[yellow]--no-promote: measure only[/yellow]')
    else:
        with SessionLocal() as db:
            promote(db, args.tool, winner)
            db.commit()
        console.print(f'[green]Promoted:[/green] {winner.name}')

    console.print(f'[cyan]Decision:[/cyan] {reason}')

    json_path, csv_path = write_report(args.tool, results, winner, reason)

    table = Table(title=f'Description tuning: {args.tool}')
    table.add_column('Variant', style='bold')
    table.add_column('Pass rate', justify='right')
    table.add_column('Trials', justify='right')
    table.add_column('Avg ms', justify='right')
    table.add_column('Status')
    for r in results:
        status = '[green]WINNER[/green]' if r.name == winner.name else ''
        table.add_row(r.name, f'{r.pass_rate:.0%}', str(r.trials), f'{r.avg_ms:.0f}', status)
    console.print(table)
    console.print(f'\nReports: {json_path} , {csv_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())