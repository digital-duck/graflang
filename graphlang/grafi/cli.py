"""The import command of `graf`: import-spl (registered in graphlang/cli.py)."""
from pathlib import Path

import click


@click.command("import-spl", short_help="Lift each SPL workflow into a *.graph.yaml.")
@click.argument("spl_files", nargs=-1, required=True, metavar="SPL_FILE...")
@click.option("--out-dir", default=None, metavar="DIR", help="Output directory (default: next to each input).")
@click.option("--workflow", default=None, metavar="NAME", help="Workflow to lift (default: the last one defined in the file).")
@click.option("--stdout", "to_stdout", is_flag=True, help="Print the YAML instead of writing a file.")
def cmd_import_spl(spl_files, out_dir, workflow, to_stdout):
    """Lift each .spl workflow into a GraphLang graph (reads the SPL syntax tree; no LLM).

    Writes <name>.graph.yaml: INPUT/OUTPUT nodes, one node per statement, `triggers` edges for control flow and
    `binds` edges for @var data flow. Statements with no GraphLang equivalent are skipped and reported as warnings.
    Needs SPL.py importable (`pip install -e ".[spl]"`).

    \b
    Examples:
      graf import-spl cookbook/005_self_refine/self_refine.spl
      graf import-spl workflow.spl --workflow main --out-dir graphs/
    """
    try:
        from .spl2graph import NoWorkflowError, graph_to_yaml, spl_to_graph
    except ImportError as e:
        raise click.ClickException(f"import-spl needs SPL.py ({e}); install it with: pip install -e \".[spl]\"") from None

    errors = 0
    for spl_file in spl_files:
        path = Path(spl_file).resolve()
        if not path.exists():
            click.echo(f"MISSING: {spl_file}", err=True)
            errors += 1
            continue
        try:
            graph, warnings = spl_to_graph(path.read_text(encoding="utf-8"), workflow,
                                           source_name=path.name, source_dir=path.parent)
        except NoWorkflowError as exc:
            click.echo(f"WARN: {path.name} - {exc}", err=True)
            continue
        except Exception as exc:
            click.echo(f"FAILED: {spl_file} - {exc}", err=True)
            errors += 1
            continue
        for w in warnings:
            click.echo(f"WARN: {path.name} - {w}", err=True)
        text = graph_to_yaml(graph)
        if to_stdout:
            click.echo(text)
            continue
        dest_dir = Path(out_dir).resolve() if out_dir else path.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{path.stem}.graph.yaml"
        dest.write_text(text, encoding="utf-8")
        click.echo(f"{dest}  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")
    if errors:
        raise SystemExit(1)
