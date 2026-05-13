"""Click CLI for cu-migrate.

Commands:
  inventory  — List analyzers and migration readiness
  migrate    — Run Preview→GA migration (dry-run / export / apply)
  report     — Generate reports from a previous migration run
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from cu_migrate.client import CUClient
from cu_migrate.executor import execute
from cu_migrate.inventory import build_inventory
from cu_migrate.models import MigrationReadiness, RunMode
from cu_migrate.reports import write_reports

console = Console()


@click.group()
@click.option("--endpoint", required=True, envvar="CU_ENDPOINT", help="CU resource endpoint URL")
@click.option("--key", default=None, envvar="CU_KEY", help="Subscription key (omit for Entra ID)")
@click.pass_context
def main(ctx: click.Context, endpoint: str, key: str | None) -> None:
    """CU Migrate — Azure Content Understanding Preview-to-GA migration assistant."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = CUClient(endpoint=endpoint, subscription_key=key)


@main.command()
@click.pass_context
def inventory(ctx: click.Context) -> None:
    """List analyzers and their migration readiness."""
    client: CUClient = ctx.obj["client"]
    items = build_inventory(client)

    table = Table(title="Analyzer Inventory")
    table.add_column("Analyzer ID", style="bold")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Readiness")

    readiness_style = {
        MigrationReadiness.READY: "[green]✅ Ready[/green]",
        MigrationReadiness.REVIEW_NEEDED: "[yellow]⚠️ Review[/yellow]",
        MigrationReadiness.BLOCKED: "[red]❌ Blocked[/red]",
    }

    for item in items:
        table.add_row(
            item.analyzer_id,
            item.base_analyzer_type or "—",
            item.status or "—",
            readiness_style.get(item.migration_readiness, str(item.migration_readiness)),
        )

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(items)}  "
                  f"[green]Ready:[/green] {sum(1 for i in items if i.migration_readiness == MigrationReadiness.READY)}  "
                  f"[yellow]Review:[/yellow] {sum(1 for i in items if i.migration_readiness == MigrationReadiness.REVIEW_NEEDED)}  "
                  f"[red]Blocked:[/red] {sum(1 for i in items if i.migration_readiness == MigrationReadiness.BLOCKED)}")


@main.command()
@click.option("--analyzer", "-a", multiple=True, help="Analyzer ID(s) to migrate (omit for all)")
@click.option("--mode", "-m", type=click.Choice(["dry_run", "export", "apply"]), default="dry_run", help="Execution mode")
@click.option("--output", "-o", type=click.Path(), default="./cu_migration_output", help="Output directory for artifacts")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation for apply mode")
@click.pass_context
def migrate(ctx: click.Context, analyzer: tuple[str, ...], mode: str, output: str, yes: bool) -> None:
    """Run Preview→GA migration."""
    client: CUClient = ctx.obj["client"]
    run_mode = RunMode(mode)
    output_dir = Path(output)
    analyzer_ids = list(analyzer) if analyzer else None

    if run_mode == RunMode.APPLY and not yes:
        click.confirm(
            "⚠️  Apply mode will CREATE new GA analyzers. Continue?",
            abort=True,
        )

    console.print(f"[bold]Running migration[/bold] — mode: {run_mode.value}, scope: {len(analyzer_ids) if analyzer_ids else 'all'} analyzer(s)")

    run = execute(client, analyzer_ids, run_mode, output_dir)

    # Print summary
    console.print(f"\n[bold green]✅ Passed:[/bold green] {run.success_count}")
    console.print(f"[bold yellow]⚠️  Warnings:[/bold yellow] {run.warning_count}")
    console.print(f"[bold red]❌ Failed:[/bold red] {run.failure_count}")

    # Write reports
    if run_mode in (RunMode.EXPORT, RunMode.APPLY, RunMode.DRY_RUN):
        written = write_reports(run, output_dir)
        console.print(f"\n[bold]Reports written:[/bold]")
        for p in written:
            console.print(f"  📄 {p}")


@main.command()
@click.option("--analyzer", "-a", multiple=True, help="Analyzer ID(s) to report on (omit for all)")
@click.option("--output", "-o", type=click.Path(), default="./cu_migration_output", help="Output directory")
@click.pass_context
def report(ctx: click.Context, analyzer: tuple[str, ...], output: str) -> None:
    """Generate reports from a dry-run migration."""
    ctx.invoke(migrate, analyzer=analyzer, mode="dry_run", output=output, yes=False)
