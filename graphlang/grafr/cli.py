#!/usr/bin/env python3
"""Command-line interface for grafr (GraphLang runtime)."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .runtime import load_graph, GraphLangRuntime
from .topology import check

console = Console()


@click.group(help="GraphLang runtime - Execute topologically grounded agentic workflows")
def main():
    pass


@main.command("run")
@click.argument("graph")
@click.option("--adapter", default="mock", show_default=True,
              help="LLM adapter: mock (no LLM) or an SPL.py adapter such as claude_cli, ollama, openrouter")
@click.option("--model", default=None, help="model for every GENERATE node (overrides the model hints in the graph)")
@click.option("--max-steps", type=int, default=1000, show_default=True,
              help="stop after this many node firings (guards against endless loops)")
@click.option("--param", multiple=True, help="Workflow parameters (key=value); repeatable")
def cmd_run(graph, adapter, model, max_steps, param):
    """Execute a GraphLang workflow (GRAPH is the path to the .graph.yaml file)."""
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)

    console.print(f"[bold blue]⚡ Loading graph:[/bold blue] {graph_path}")
    graph_data = load_graph(graph_path)

    console.print(f"[bold green]✓[/bold green] Graph loaded: {graph_data['workflow']['name']}")
    console.print(f"  Nodes: {len(graph_data['nodes'])}")
    console.print(f"  Edges: {len(graph_data['edges'])}")

    # Parse parameters
    params = {}
    for p in param:
        if '=' not in p:
            raise click.BadParameter(f"expected key=value, got {p!r}", param_hint="--param")
        key, value = p.split('=', 1)
        params[key] = value

    console.print(f"\n[bold blue]▶ Executing workflow...[/bold blue]")

    try:
        runtime = GraphLangRuntime(graph_data, adapter=adapter, model=model, max_steps=max_steps)
        if adapter == "mock":
            console.print("[yellow]adapter: mock (no LLM is called); use --adapter claude_cli, ollama, ... for real output[/yellow]")
        result = runtime.execute(params)
    except (ValueError, RuntimeError, NotImplementedError) as e:
        console.print(f"[red]✗ Run failed:[/red] {e}")
        sys.exit(1)

    if not result:
        console.print("\n[yellow]Workflow ended without reaching an OUTPUT node (a gate routed to a dead end)[/yellow]")
    else:
        console.print(f"\n[bold green]✓ Workflow completed[/bold green]")
    console.print(f"[bold]Output:[/bold] {result}")


@main.command("validate")
@click.argument("graph")
def cmd_validate(graph):
    """Validate a GraphLang workflow against the schema."""
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)

    try:
        graph_data = load_graph(graph_path)
    except Exception as e:
        console.print(f"[red]✗ Validation failed:[/red] {e}")
        sys.exit(1)
    errors, warnings = check(graph_data)
    for w in warnings:
        console.print(f"[yellow]warning:[/yellow] {w}")
    for e in errors:
        console.print(f"[red]error:[/red] {e}")
    if errors:
        console.print(f"[red]✗ {len(errors)} problem(s)[/red] in {graph_data['workflow']['name']}")
        sys.exit(1)
    console.print(f"[bold green]✓[/bold green] Valid GraphLang workflow: {graph_data['workflow']['name']}"
                  + (f" ({len(warnings)} warning(s))" if warnings else ""))


@main.command("info")
@click.argument("graph")
def cmd_info(graph):
    """Display information about a GraphLang workflow."""
    graph_path = Path(graph)
    graph_data = load_graph(graph_path)

    table = Table(title=f"Workflow: {graph_data['workflow']['name']}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Version", graph_data['version'])
    table.add_row("Nodes", str(len(graph_data['nodes'])))
    table.add_row("Edges", str(len(graph_data['edges'])))
    table.add_row("Inputs", ", ".join([i['name'] for i in graph_data['workflow'].get('inputs', [])]))
    table.add_row("Outputs", ", ".join([o['name'] for o in graph_data['workflow'].get('outputs', [])]))

    console.print(table)

    if 'resources' in graph_data:
        console.print("\n[bold]Resources:[/bold]")
        for res_type, res_dict in graph_data['resources'].items():
            console.print(f"  [cyan]{res_type}:[/cyan]")
            for name, path in res_dict.items():
                console.print(f"    {name} → {path}")


if __name__ == "__main__":
    main()
