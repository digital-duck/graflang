"""The visualization command of `graf`: vis (registered in graphlang/cli.py)."""
import sys
import webbrowser
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape

from ..grafr.runtime import load_graph
from .engines import DEFAULT_ENGINE, ENGINES, hint, render

console = Console()


@click.command("vis")
@click.argument("graph", required=False)
@click.option("--engine", type=click.Choice(sorted(ENGINES)), default=DEFAULT_ENGINE, show_default=True,
              help="cytoscape: interactive HTML, works offline; graphviz: svg/png/pdf; mermaid, ascii: text; pyvis, graphify: other HTML views (see --list-engines)")
@click.option("--list-engines", is_flag=True, help="show the engines and whether each is ready")
@click.option("-o", "--out", type=click.Path(dir_okay=False), default=None,
              help="output file (default ~/.graflang/vis/<graph>-<engine>.<html|svg|mmd|txt>)")
@click.option("--no-open", is_flag=True, help="write the file but do not open it")
def cmd_vis(graph, engine, list_engines, out, no_open):
    """Draw a GraphLang workflow (GRAPH is the path to the .graph.yaml file) and open it."""
    if list_engines:
        for name, spec in ENGINES.items():
            ok, why = spec["ready"]()
            console.print(f"{name:<10} {'ok ' if ok else '!! '} {hint(spec['about'])}" + ("" if ok else f"  [{hint(why)}]")
                          + ("  (default)" if name == DEFAULT_ENGINE else ""), highlight=False, soft_wrap=True, markup=False)
        return
    if not graph:
        raise click.UsageError("missing GRAPH (the path to a .graph.yaml file)")
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)
    try:
        graph_data = load_graph(graph_path)
    except ValueError as e:
        console.print(f"[red]✗ Invalid graph:[/red] {escape(str(e))}")
        sys.exit(1)
    stem = graph_path.name.removesuffix(".graph.yaml").removesuffix(".yaml")
    target = Path(out) if out else Path.home() / ".graflang" / "vis" / f"{stem}-{engine}{ENGINES[engine]['ext']}"
    try:
        path, note, n = render(graph_data, target, engine)
    except (ValueError, RuntimeError) as e:
        console.print(f"[red]✗ Could not draw:[/red] {escape(str(e))}")
        sys.exit(1)
    console.print(f"{engine}: {n} nodes -> {path}" + (f"\n  {note}" if note else ""), highlight=False, soft_wrap=True, markup=False)
    if ENGINES[engine].get("open", True) and not no_open:
        webbrowser.open(path.resolve().as_uri())
