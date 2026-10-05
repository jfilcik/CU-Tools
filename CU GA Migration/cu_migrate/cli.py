"""Offline inventory, migration planning and reports from official CLI exports."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from cu_migrate.executor import execute
from cu_migrate.inventory import build_inventory, load_sources
from cu_migrate.models import RunMode
from cu_migrate.reports import generate_report

console = Console()


def local_inputs(command):
    command = click.option(
        "--source-id", help="Explicit ID for one standalone definition that omits its analyzer ID",
    )(command)
    return click.option(
        "--input", "-i", "inputs", multiple=True, required=True,
        type=click.Path(exists=True, path_type=Path),
        help="Local analyzer JSON export or directory of JSON exports; repeat for multiple inputs",
    )(command)


@click.group()
def main() -> None:
    """CU Migrate: OFFLINE Preview-to-GA schema planning.

    Export analyzers and create reviewed replacements using the official cu CLI.
    This tool never authenticates, connects to Azure, or deploys analyzers.
    """


@main.command()
@local_inputs
@click.option("--include-prebuilt", is_flag=True, help="Include built-in analyzers in the inventory")
@click.option("--json", "as_json", is_flag=True, help="Print inventory as JSON")
def inventory(inputs: tuple[Path, ...], source_id: str | None, include_prebuilt: bool, as_json: bool) -> None:
    """Inventory only the analyzers present in local exports."""
    try:
        items = build_inventory(load_sources(inputs, source_id), include_prebuilt)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        import json
        click.echo(json.dumps([item.model_dump(mode="json") for item in items], indent=2))
        return
    table = Table(title="Local analyzer inventory (not service-validated)")
    for name in ("Analyzer ID", "Type", "Definition", "Readiness"):
        table.add_column(name)
    for item in items:
        table.add_row(
            item.analyzer_id, item.base_analyzer_type or "—",
            "available" if item.definition_available else "list metadata only",
            item.migration_readiness.value,
        )
    console.print(table)
    click.echo(f"Total local analyzers: {len(items)}. No service calls were made.")


def _plan(
    inputs: tuple[Path, ...], source_id: str | None, analyzer: tuple[str, ...],
    mode: str, output: Path | None,
) -> None:
    try:
        run = execute(
            load_sources(inputs, source_id), list(analyzer) if analyzer else None,
            RunMode(mode), output,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if mode == RunMode.DRY_RUN.value:
        click.echo(generate_report(run))
        click.echo("Dry run: no files written. Use --mode export --output NEW_DIRECTORY to save a review bundle.")
    else:
        click.echo(f"Review bundle exported to: {output.resolve()}")
        click.echo("Review migration_report.md and official_cu_commands.md. Nothing was deployed.")
    click.echo(f"Offline checks: {run.success_count} passed, {run.warning_count} need review, {run.failure_count} failed.")
    if run.failure_count:
        raise click.ClickException(f"{run.failure_count} analyzer(s) failed migration checks; no create commands were generated for them")


@main.command()
@local_inputs
@click.option("--analyzer", "-a", multiple=True, help="Local analyzer ID to plan; repeat, or omit for all custom analyzers")
@click.option("--mode", "-m", type=click.Choice(["dry_run", "export"]), default="dry_run", show_default=True)
@click.option("--output", "-o", type=click.Path(path_type=Path), help="New output directory; required for export and forbidden for dry_run")
def migrate(
    inputs: tuple[Path, ...], source_id: str | None, analyzer: tuple[str, ...],
    mode: str, output: Path | None,
) -> None:
    """Propose local GA schemas. dry_run writes nothing; export saves evidence."""
    _plan(inputs, source_id, analyzer, mode, output)


@main.command()
@local_inputs
@click.option("--analyzer", "-a", multiple=True, help="Local analyzer ID(s); omit for all custom analyzers")
@click.option("--output", "-o", required=True, type=click.Path(path_type=Path), help="New review-bundle directory")
def report(
    inputs: tuple[Path, ...], source_id: str | None,
    analyzer: tuple[str, ...], output: Path,
) -> None:
    """Generate a complete offline report bundle (same as migrate --mode export)."""
    _plan(inputs, source_id, analyzer, RunMode.EXPORT.value, output)
