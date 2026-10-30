"""The export command of `graf`: export-spl (registered in graphlang/cli.py)."""
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape

from ..grafr.runtime import load_graph
from .graph2spl import GraphToSPLError, graph_to_spl

console = Console(stderr=True)


@click.command("export-spl", short_help="Write a workflow as an SPL (.spl) script.")
@click.argument("graph")
@click.option("-o", "--output", default=None, type=click.Path(dir_okay=False), help="file to write (default: print to the terminal)")
def cmd_export_spl(graph, output):
    """Write GRAPH as SPL source (structure only, no LLM). Run the result with SPL.py's `spl3 run`.

    Control flow comes back as SPL statements, a prompt the graph carries as CREATE FUNCTION, a Python tool as CREATE TOOL_API.
    What SPL has no word for (lifecycle phases, typed ports) is dropped and listed as warnings.
    """
    path = Path(graph)
    if not path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {path}")
        sys.exit(1)
    try:
        text, warnings = graph_to_spl(load_graph(path))
    except (ValueError, GraphToSPLError, OSError) as e:
        console.print(f"[red]✗ Cannot export:[/red] {escape(str(e))}")
        sys.exit(1)
    for w in warnings:
        console.print(f"[yellow]warning:[/yellow] {escape(w)}")
    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]✓[/green] wrote {output}")
    else:
        click.echo(text)
