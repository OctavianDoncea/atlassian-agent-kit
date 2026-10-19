#! /usr/bin/env python3
import argparse
import sys
from rich.console import Console
from rich.table import Table
from agentkit.evals.runner import run_suite

def main() -> int:
    parser = argparse.ArgumentParser(description='Run AgentKit Eval Suite')
    parser.add_argument('--dry-run', action='store_true', help='Mock LLM responses to test the framework')
    args = parser.parse_args()

    console = Console()
    console.print('\n[bold blue]AgentKit Evaluation Harness[/bold blue]\n')

    results = run_suite(dry_run=args.dry_run)

    # Summary table
    table = Table(title='Eval Summary')
    table.add_column('Metric', style='cyan')
    table.add_column('Value', style='green')
    table.add_row('Total Cases', str(results['total']))
    table.add_row('Passed', str(results['passed']))
    table.add_row('Failed', str(results['failed']))
    reg_count = len(results['regressions'])
    table.add_row('Regressions', f'[red]{reg_count}[/red]' if reg_count > 0 else '0')
    console.print(table)

    # Detailed results
    detail_table = Table(title='Detailed Results')
    detail_table.add_column('Case ID')
    detail_table.add_column('Status')
    detail_table.add_column('Judge Reasoning', max_width=60)

    runs = results.get('runs', [])
    if not runs:
        console.print('[yellow]No detailed runs were recorded. Check runner.py loop indentation.[/yellow]')
    else:
        for run in runs:
            status = '[green]PASS[/green]' if run['passed'] else '[red]FAIL[/red]'
            if run.get('regression'):
                status += '[bold red](REGRESSION)[/bold red]'

            reasoning = run.get('reasoning', '')
            if len(reasoning) > 60:
                reasoning = reasoning[:60] + '...'

            detail_table.add_row(run['id'], status, reasoning)

    console.print(detail_table)

    return 0 if results['failed'] == 0 else 1

if __name__ == '__main__':
    sys.exit(main())