#!/usr/bin/env python3
"""The compiler commands of `graf`: compile, check (registered in graphlang/cli.py)."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn

from .compiler import GraphLangCompiler

console = Console()


@click.command("compile", short_help="Compile a workflow to Rust (experimental stub).")
@click.argument("graph")
@click.option("-o", "--output", default=None, help="Output directory for Rust project")
@click.option("--target", default="rust", type=click.Choice(["rust"]), show_default=True, help="Compilation target")
@click.option("--optimize", is_flag=True, help="Enable graph optimizations")
def cmd_compile(graph, output, target, optimize):
    """Compile a GraphLang workflow to Rust (GRAPH is the path to the .graph.yaml file)."""
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)

    output_dir = Path(output) if output else Path(f"{graph_path.stem}_compiled")

    console.print(f"[bold blue]⚙ Compiling GraphLang workflow:[/bold blue] {graph_path}")
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
            target=target,
            optimize=optimize,
        )

        progress.update(task, description="Loading and validating graph...")
        try:
            compiler.load_graph()
        except (ValueError, OSError) as e:
            console.print(f"[red]✗ Invalid graph:[/red] {escape(str(e))}")
            sys.exit(1)

        progress.update(task, description="Resolving resources...")
        compiler.resolve_resources()

        progress.update(task, description="Analyzing topology...")
        compiler.analyze()

        progress.update(task, description="Optimizing graph...")
        if optimize:
            compiler.optimize()

        progress.update(task, description="Compiling Cedar policies...")
        compiler.compile_policies()

        progress.update(task, description="Generating Rust code...")
        compiler.generate_rust()

        progress.update(task, description="Writing output files...")
        compiler.write_output()

    console.print(f"\n[bold green]✓ Compilation complete![/bold green]")
    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  cd {output_dir}")
    console.print(f"  cargo build --release")
    console.print(f"  ./target/release/{graph_path.stem}")


@click.command("check", short_help="Check whether a workflow can be compiled.")
@click.argument("graph")
def cmd_check(graph):
    """Check if a GraphLang workflow can be compiled."""
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)

    try:
        compiler = GraphLangCompiler(graph_path=graph_path)
        compiler.load_graph()
        compiler.resolve_resources()
        compiler.analyze()
        console.print(f"[bold green]✓[/bold green] Workflow is compilable: {graph_path.name}")
    except Exception as e:
        console.print(f"[red]✗ Compilation check failed:[/red] {escape(str(e))}")
        sys.exit(1)

