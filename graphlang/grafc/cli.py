#!/usr/bin/env python3
"""The compile command of `graf`: one command, one `--lang` per output language (registered in graphlang/cli.py)."""

import os
import sys
from pathlib import Path

import click
from dd_llm import parse_llm_spec
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


@click.command("create", short_help="Generate a GraphLang app from a plain-language spec (vibe-coding).")
@click.option("--name", required=True, help="the app's name: lower-case letters, digits, _ (it names NAME.graph.yaml and workflow.name)")
@click.option("--spec", required=True, help="what the app should do, in plain language; @FILE reads it from a file")
@click.option("--out-dir", type=click.Path(file_okay=False), default=None, help="the folder to write the app into (default ./NAME); it must be empty or new, unless --force")
@click.option("--llm", "llm_spec", default=None, help="the LLM that writes the app, ADAPTER[:MODEL] (default claude_cli:claude-sonnet-5-5)")
@click.option("--max-rounds", type=click.IntRange(1, 10), default=3, show_default=True,
              help="LLM calls at most: the first writes the app, each next one fixes the problems found in the last")
@click.option("--allow-code", is_flag=True, help="let the app contain programs (tools/*.py run by SOLVE or RUN nodes); off by default: nothing generated then runs code")
@click.option("--force", is_flag=True, help="write into a folder that already has files (same-named files are overwritten)")
@click.option("--examples/--no-examples", default=True, show_default=True,
              help="show the model the existing recipes most like the spec (found by meaning, with an embedding model, and by words)")
@click.option("--from", "from_recipe", default=None, metavar="RECIPE",
              help="start from this recipe, shown first to the model: as the Browse page names it, for example cookbook/self_refine")
@click.option("--src-dir", type=click.Path(file_okay=False), default=None,
              help="the recipes to choose examples from (one folder per recipe); default ~/.graflang/cookbook and ~/.graflang/apps")
@click.option("--embedding", default=None, metavar="SPEC",
              help="the embedding model for the search: auto, none, sentence_transformers:MODEL or ollama:MODEL (default: the Settings of the app, else auto)")
@click.option("--log-level", default=None, help="file log level (default info)")
@click.option("--log-dir", type=click.Path(file_okay=False), default=None, help="where log files go (default ~/.graflang/logs)")
@click.option("--no-log", is_flag=True, help="do not write a log file")
def cmd_create(name, spec, out_dir, llm_spec, max_rounds, allow_code, force, examples, from_recipe, src_dir, embedding, log_level, log_dir, no_log):
    """Generate a GraphLang app from a specification.

    The LLM writes the app's files (NAME.graph.yaml, prompts/*.md, readme.md); the result is checked like `graf validate` and with a
    dry run on the mock LLM, and every problem is sent back to the LLM for another try, up to --max-rounds calls (each one is a real,
    billed call). The app is written even if problems remain (exit status 1), so you can fix it by hand.

    \b
    graf create --name triage --spec "classify a support message as urgent or normal, then draft a reply" --out-dir apps/triage
    graf create --name notes --spec @notes_spec.md --llm claude_cli:claude-haiku-5-5
    """
    from ..grafr.adapters import default_model, make_llm
    from ..grafr.metering import MeteredLLM
    from ..logging_config import disable_logging, setup_logging
    from .create import CreateError, check_name, create_app, find_examples, write_app
    try:
        check_name(name)
        if spec.startswith("@"):
            try:
                spec = Path(spec[1:]).read_text(encoding="utf-8")
            except OSError as e:
                raise click.BadParameter(f"cannot read {spec[1:]}: {e}", param_hint="--spec")
        try:
            adapter, model = parse_llm_spec(llm_spec or "claude_cli")
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="--llm")
        explicit = model
        model = model or default_model(adapter)
        dest = Path(out_dir) if out_dir else Path(name)
        if dest.exists() and any(dest.iterdir()) and not force:
            raise CreateError(f"{dest} already has files; pick another --out-dir or pass --force to write into it")
        if no_log:
            disable_logging()
            log_path = None
        else:
            log_path = setup_logging(f"create-{name}", adapter=adapter, model=model or "", log_dir=log_dir or Path.home() / ".graflang" / "logs",
                                     log_level=log_level, log_format=os.environ.get("DD_LOG_FORMAT") or "both")
        try:
            llm = MeteredLLM(make_llm(adapter, explicit), max_calls=max_rounds)
        except Exception as e:                              # dd-llm missing, unknown adapter, no key
            raise CreateError(str(e))
        console.print(f"[bold blue]⚡ Creating[/bold blue] {name} with {adapter}{':' + model if model else ''} (up to {max_rounds} call(s))")
        shown = None
        if examples or from_recipe:
            from .. import workspace as work
            shown = find_examples(spec, work.Workspace(Path(src_dir) if src_dir else None), allow_code=allow_code, chosen=from_recipe,
                                  embedding=embedding or work.load_settings().get("embedding", "auto"))
            if from_recipe and from_recipe not in shown.keys:
                raise CreateError(f"--from {from_recipe!r}: no such recipe (or it runs programs and --allow-code is off); see the Browse page for the names")
            if shown.keys:
                console.print(f"[dim]examples: {', '.join(shown.keys)}  ({shown.note})[/dim]")
            else:
                console.print(f"[dim]no similar recipe to show ({shown.note})[/dim]")
            if shown.words_only and shown.keys:
                console.print("[yellow]note:[/yellow] examples were chosen by words only; an embedding model finds closer ones (--embedding, or the app's Settings)")
        created = create_app(name, spec, llm, model, max_rounds=max_rounds, allow_code=allow_code, references=(shown.text or None) if shown else None)
        written = write_app(name, spec, created, dest, f"{adapter}:{model}" if model else adapter, force)
    except CreateError as e:
        console.print(f"[red]Error:[/red] {escape(str(e))}")
        sys.exit(1)
    for w in created.warnings:
        console.print(f"[yellow]warning:[/yellow] {escape(w)}")
    usage = llm.snapshot()
    for path in written:
        console.print(f"  {path}")
    console.print(f"[dim]{created.rounds} LLM call(s), {usage['input_tokens']} tokens in / {usage['output_tokens']} out[/dim]")
    if log_path:
        console.print(f"[dim]log: {log_path}[/dim]")
    if created.problems:
        for problem in created.problems:
            console.print(f"[red]problem:[/red] {escape(problem)}")
        console.print(f"[red]✗ Written with {len(created.problems)} problem(s) left after {created.rounds} round(s)[/red]: fix them by hand (`graf validate {dest / (name + '.graph.yaml')}`)")
        sys.exit(1)
    graph = dest / f"{name}.graph.yaml"
    console.print(f"[bold green]✓ Created[/bold green] {graph} (it passes `graf validate` and a dry run)")
    console.print(f"[dim]next: graf vis {graph} · graf run {graph} --param ...  (read {dest / 'readme.md'} for the inputs)[/dim]")
