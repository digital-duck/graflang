#!/usr/bin/env python3
"""The compile command of `graf`: one command, one `--lang` per output language (registered in graphlang/cli.py)."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..grafe.graph2spl import GraphToSPLError, graph_to_spl
from ..grafr.topology import check
from .compiler import GraphLangCompiler

console = Console()
err = Console(stderr=True)                    # `--lang spl` prints the script on stdout, so its messages go to stderr


def _problems(graph_data) -> None:
    """The same checks as `graf validate`: print them and stop on an error."""
    errors, warnings = check(graph_data)
    for w in warnings:
        err.print(f"[yellow]warning:[/yellow] {escape(str(w))}")
    for e in errors:
        err.print(f"[red]error:[/red] {escape(str(e))}")
    if errors:
        err.print(f"[red]✗ {len(errors)} problem(s)[/red] in {graph_data['workflow']['name']}: fix them (see `graf validate`) before compiling")
        sys.exit(1)


@click.command("compile", short_help="Compile a workflow to another language (spl, rust).")
@click.argument("graph")
@click.option("--lang", default="rust", type=click.Choice(["rust", "spl"]), show_default=True,
              help="rust: a Cargo project (experimental stub); spl: an SPL script for SPL.py's `spl3 run` (structure only, no LLM)")
@click.option("-o", "--output", default=None,
              help="rust: the project folder (default <name>_compiled); spl: the file to write (default: print it)")
@click.option("--optimize", is_flag=True, help="rust: enable graph optimizations")
@click.option("--dry-run", is_flag=True, help="do every step but write nothing, and say whether the workflow compiles")
def cmd_compile(graph, lang, output, optimize, dry_run):
    """Compile a GraphLang workflow (GRAPH is the path to the .graph.yaml file).

    The workflow is first checked like `graf validate`. Then `--lang rust` writes a Rust project and `--lang spl` writes SPL
    source: control flow as SPL statements, a prompt the graph carries as CREATE FUNCTION, a Python tool as CREATE TOOL_API;
    what SPL has no word for (lifecycle phases, typed ports) is dropped and listed as warnings.
    """
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)
    if lang != "rust" and optimize:
        raise click.UsageError("--optimize applies to --lang rust only")
    if lang == "rust":
        _compile_rust(graph_path, output, optimize, dry_run)
    else:
        _compile_spl(graph_path, output, dry_run)


def _compile_spl(graph_path: Path, output, dry_run: bool) -> None:
    compiler = GraphLangCompiler(graph_path=graph_path)
    try:
        compiler.load_graph()
    except (ValueError, OSError) as e:
        err.print(f"[red]✗ Invalid graph:[/red] {escape(str(e))}")
        sys.exit(1)
    _problems(compiler.graph_data)
    try:
        text, warnings = graph_to_spl(compiler.graph_data)
    except (ValueError, GraphToSPLError, OSError) as e:
        err.print(f"[red]✗ Cannot export:[/red] {escape(str(e))}")
        sys.exit(1)
    for w in warnings:
        err.print(f"[yellow]warning:[/yellow] {escape(w)}")
    if dry_run:
        err.print(f"[bold green]✓[/bold green] Workflow compiles to SPL: {graph_path.name} (dry run, nothing written)")
    elif output:
        Path(output).write_text(text, encoding="utf-8")
        err.print(f"[green]✓[/green] wrote {output}")
    else:
        click.echo(text)


def _compile_rust(graph_path: Path, output, optimize: bool, dry_run: bool) -> None:
    output_dir = Path(output) if output else Path(f"{graph_path.stem}_compiled")

    console.print(f"[bold blue]⚙ Compiling GraphLang workflow:[/bold blue] {graph_path}")
    if not dry_run:
        console.print(f"[bold]Output directory:[/bold] {output_dir}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Compiling...", total=None)

        compiler = GraphLangCompiler(
            graph_path=graph_path,
            output_dir=output_dir,
            target="rust",
            optimize=optimize,
        )

        progress.update(task, description="Loading and validating graph...")
        try:
            compiler.load_graph()
        except (ValueError, OSError) as e:
            progress.stop()
            console.print(f"[red]✗ Invalid graph:[/red] {escape(str(e))}")
            sys.exit(1)
        progress.stop()
        _problems(compiler.graph_data)
        progress.start()

        progress.update(task, description="Resolving resources...")
        try:
            compiler.resolve_resources()
        except (FileNotFoundError, OSError) as e:
            progress.stop()
            console.print(f"[red]✗ Invalid graph:[/red] {escape(str(e))}")
            sys.exit(1)

        progress.update(task, description="Analyzing topology...")
        compiler.analyze()

        progress.update(task, description="Optimizing graph...")
        if optimize:
            compiler.optimize()

        progress.update(task, description="Compiling Cedar policies...")
        compiler.compile_policies()

        progress.update(task, description="Generating Rust code...")
        try:
            compiler.generate_rust()
        except ValueError as e:
            progress.stop()
            console.print(f"[red]✗ Cannot generate Rust:[/red] {escape(str(e))}")
            sys.exit(1)

        if not dry_run:
            progress.update(task, description="Writing output files...")
            compiler.write_output()

    if dry_run:
        console.print(f"\n[bold green]✓[/bold green] Workflow compiles to Rust: {graph_path.name} (dry run, nothing written)")
        return
    console.print(f"\n[bold green]✓ Compilation complete![/bold green]")
    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  cd {output_dir}")
    console.print(f"  cargo build --release")
    console.print(f"  ./target/release/{graph_path.stem}")
