"""The visualization command of `graf`: vis (registered in graphlang/cli.py)."""
import shutil
import sys
import webbrowser
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape

from ..grafr.runtime import load_graph
from .engines import DEFAULT_ENGINE, ENGINES, hint, render

console = Console()


@click.command("vis", short_help="Draw a workflow as a diagram (alias: viz).")
@click.argument("graph", required=False)
@click.option("--engine", type=click.Choice(sorted(ENGINES)), default=DEFAULT_ENGINE, show_default=True,
              help="cytoscape: interactive HTML, works offline; graphviz: svg/png/pdf; mermaid, ascii: text; pyvis, graphify: other HTML views (see --list-engines)")
@click.option("--list-engines", is_flag=True, help="show the engines and whether each is ready")
@click.option("-o", "--out", type=click.Path(dir_okay=False), default=None,
              help="output file (default ~/.graflang/vis/<graph>-<engine>.<html|svg|mmd|txt>)")
@click.option("--no-open", is_flag=True, help="write the file but do not open it")
@click.option("--edit", is_flag=True, help="open the app instead: Create, Edit, Settings and Import/Export pages (saves only a valid graph, keeps "
                                           "your comments); needs `pip install 'graflang[edit]'`. GRAPH is optional with it")
@click.option("--src-dir", type=click.Path(file_okay=False), default=None,
              help="with --edit: the folder of recipes to work in (one folder per recipe, each with its *.graph.yaml); default ~/.graflang/cookbook "
                   "(shipped, read-only) and ~/.graflang/apps (yours). $GRAFLANG_HOME moves ~/.graflang")
@click.option("--host", default="127.0.0.1", show_default=True,
              help="with --edit: the address the app listens on. The app has no login and can read your files and use your saved API keys, "
                   "so keep it on this computer; any other address is your decision")
def cmd_vis(graph, engine, list_engines, out, no_open, edit, src_dir, host):
    """Draw a GraphLang workflow (GRAPH is the path to the .graph.yaml file) and open it."""
    if list_engines:
        for name, spec in ENGINES.items():
            ok, why = spec["ready"]()
            console.print(f"{name:<10} {'ok ' if ok else '!! '} {hint(spec['about'])}" + ("" if ok else f"  [{hint(why)}]")
                          + ("  (default)" if name == DEFAULT_ENGINE else ""), highlight=False, soft_wrap=True, markup=False)
        if shutil.which("dot") is None:
            console.print("\nGraphviz is a system program, not a pip package. Install it with: sudo apt install graphviz (Ubuntu/Debian), "
                          "brew install graphviz (macOS), winget install Graphviz.Graphviz (Windows), "
                          "conda install -c conda-forge graphviz. Then check: dot -V", highlight=False, soft_wrap=True, markup=False)
        return
    if src_dir and not edit:
        raise click.UsageError("--src-dir goes with --edit")
    if edit and not graph:
        _run_editor(None, Path(src_dir) if src_dir else None, host)
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
    if edit:
        _run_editor(graph_path, Path(src_dir) if src_dir else None, host)
        return
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


def _run_editor(graph_path: "Path | None", src_dir: "Path | None", host: str = "127.0.0.1") -> None:
    """Open the Streamlit app, on a long-form workflow if one is given."""
    import os
    import subprocess
    from importlib.util import find_spec

    if find_spec("streamlit") is None:
        console.print("[red]✗ The editor needs Streamlit:[/red] pip install 'graflang\\[edit]'")
        sys.exit(1)
    env = {**os.environ}
    if graph_path is not None:
        from .editor import EditError, GraphEditor
        try:
            GraphEditor(graph_path)
        except (EditError, ValueError) as e:
            console.print(f"[red]✗ Cannot edit:[/red] {escape(str(e))}  (the app opens anyway: the Edit page can make a long-form copy)")
        env["GRAF_EDIT_FILE"] = str(graph_path.resolve())
    if src_dir is not None:
        if not src_dir.is_dir():
            console.print(f"[red]Error:[/red] --src-dir {src_dir} is not a folder")
            sys.exit(1)
        env["GRAF_SRC_DIR"] = str(src_dir.resolve())
    if host not in ("127.0.0.1", "localhost", "::1"):
        console.print(f"[yellow]Warning:[/yellow] listening on {escape(host)}: anyone who can reach this address can use your saved API keys and read your files. "
                      "The app has no login.", highlight=False, soft_wrap=True)
    app = Path(__file__).with_name("app.py")
    from .. import workspace
    where = f"{src_dir}" if src_dir else f"{workspace.default_src_dir()} and {workspace.apps_dir()}"
    console.print(f"editing {graph_path or 'recipes in ' + where}  (Ctrl-C to stop)", highlight=False, markup=False)
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app), "--browser.gatherUsageStats", "false", "--server.address", host], env=env, check=False)
    except KeyboardInterrupt:
        pass
