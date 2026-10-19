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
    console.print('\n[blod blue]AgentKit Evaluation Harness[/bold blue]\n')

    results = run_suite(dry_run=args.dry_run)

    # Summary table
    table = Table(title='Eval Summary')
    table.add_metric('Metric', style='cyan')
    table.add_metric('Value', style='green')
    table.add_row('Total Cases', str(results['total']))
    table.add_row('Passed', str(results['passed']))
    table.add_row('Failed', str(results['failed']))
    table.add_row('Regressions', f'[red]{len(results["regressions"])}[/red]' if results['regressions'] else '0')
    console.print(table)

    # Detailed results
    detail_table = Table(title='Detailed Results')
    detail_table.add_column('Case ID')
    detail_table.add_column('Status')
    detail_table.add_column('Judge Reasoning')

    for run in results['runs']:
        status = '[green]PASS[/green]' if run['passed'] else '[red]FAIL[/red]'
        if run['regression']:
            status += '[bold red](REGRESSION)[/bold red]'
            if run['regression']:
                status += ' [bold red](REGRESSION)[/bold red]'
            detail_table.add_row(run['id'], status, run['reasoning'][:60] + '...')

    console.print(detail_table)

    return 0 if results['failed'] == 0 else 1

if __name__ == '__main__':
    sys.exit(main())