#!/usr/bin/env python3
"""The runtime commands of `graf`: run, validate, info (registered in graphlang/cli.py)."""

import os
import sys
from pathlib import Path

import click
from dd_llm import parse_llm_spec
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ..logging_config import disable_logging, setup_logging
from .adapters import default_model, make_llm
from .metering import CassetteError, LimitExceeded, MeteredLLM, RecordingLLM, ReplayLLM
from .bindings import bind_graph, load_bindings
from .output import RunOutput
from .runtime import load_graph, GraphLangRuntime
from .topology import check

console = Console()


def _load_or_exit(graph_path: Path) -> dict:
    """load_graph, with a message and exit code 1 (not a traceback) for a bad or wrong-kind file."""
    try:
        return load_graph(graph_path)
    except (ValueError, OSError) as e:
        console.print(f"[red]✗ Invalid graph:[/red] {escape(str(e))}")
        sys.exit(1)


@click.command("run", short_help="Run a workflow; results go to <graph folder>/output.")
@click.argument("graph")
@click.option("--llm", "llm_spec", default=None, metavar="ADAPTER[:MODEL]",
              help="adapter and model in one value, e.g. claude_cli:claude-haiku-5-5 or ollama:gemma3:12b; wins over --adapter/--model")
@click.option("--adapter", default=None,
              help="LLM adapter: claude_cli (default), mock (no LLM, placeholder text), or another dd-llm adapter such as ollama, openrouter")
@click.option("--model", default=None,
              help="model for every GENERATE node (overrides the model hints in the graph); default claude-sonnet-5-5 "
                   "for claude_cli, none for other adapters")
@click.option("--max-steps", type=int, default=None,
              help="stop after this many node firings (guards against endless loops; default 1000)")
@click.option("--workers", type=int, default=None,
              help="run nodes released together (the branches of a FORK, ...) on this many threads; default 1, or limits.concurrency "
                   "of a --bind file. Results are applied in a fixed order, so a run does not depend on which call finishes first")
@click.option("--record", "record_file", type=click.Path(dir_okay=False), default=None,
              help="write every GENERATE call to this cassette (JSON lines) while running")
@click.option("--replay", "replay_file", type=click.Path(exists=True, dir_okay=False), default=None,
              help="answer GENERATE calls from a cassette made with --record: no model is called")
@click.option("--checkpoint", "checkpoint_file", type=click.Path(dir_okay=False), default=None,
              help="save the run's state to this file before every step, so a failed run can be continued with --resume")
@click.option("--resume", "resume_file", type=click.Path(exists=True, dir_okay=False), default=None,
              help="continue a run from a --checkpoint file (the same graph; kernel variables are not restored)")
@click.option("--bind", "bind_file", type=click.Path(dir_okay=False), default=None,
              help="bindings file: the model, files and limits for this environment (llm, llms, params, resources, limits)")
@click.option("--param", multiple=True, help="Workflow parameters (key=value); repeatable")
@click.option("--log-level", type=click.Choice(["debug", "info", "warning", "error"]), default=None,
              help="file log level (default info, or $DD_LOG_LEVEL); debug adds every node firing and LLM text previews")
@click.option("--log-format", type=click.Choice(["text", "jsonl", "both"]), default=None,
              help="log file format (default both, or $DD_LOG_FORMAT): .log for people, .jsonl for tools")
@click.option("--log-dir", type=click.Path(file_okay=False), default=None,
              help="where log files go (default ~/.graflang/logs, or $DD_LOG_DIR); e.g. --log-dir . for the current folder")
@click.option("--no-log", is_flag=True, help="do not write a log file")
@click.option("--output-dir", type=click.Path(file_okay=False), default=None,
              help="where results go (default: the output/ folder next to the .graph.yaml): a folder per run with result.json and one file per output")
@click.option("--save-nodes/--no-save-nodes", default=True, show_default=True,
              help="save every node's output (LLM responses included) under <run folder>/nodes/ (--no-save-nodes keeps only the workflow outputs)")
@click.option("--no-output", is_flag=True, help="do not write result files")
@click.option("--log-prompts", type=click.Path(file_okay=False), default=None,
              help="write every prompt sent by a procedure_ref node to DIR/<procedure>/<function>_NNN.md (as spl3 run --log-prompts)")
def cmd_run(graph, llm_spec, adapter, model, max_steps, workers, record_file, replay_file, checkpoint_file, resume_file, bind_file, param, log_level, log_format, log_dir, no_log, output_dir, save_nodes,
            no_output, log_prompts):
    """Execute a GraphLang workflow (GRAPH is the path to the .graph.yaml file)."""
    if log_prompts:
        from .procedures import PROMPT_LOG_ENV
        os.environ[PROMPT_LOG_ENV] = str(Path(log_prompts).resolve())
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)

    bindings = {}
    if bind_file:
        try:
            bindings = load_bindings(Path(bind_file))
        except (ValueError, OSError) as e:
            raise click.BadParameter(str(e), param_hint="--bind")
        if not llm_spec and not adapter and not model and bindings.get("llm"):
            llm_spec = bindings["llm"]
    if llm_spec:
        try:
            adapter, model = parse_llm_spec(llm_spec)
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="--llm")
    adapter = adapter or "claude_cli"
    limits = bindings.get("limits", {})
    max_steps = max_steps or limits.get("max_steps") or 1000

    explicit_model = model                           # what the user chose: the run-wide model, used by a node that names none of its own
    model = model or default_model(adapter)          # the name used in log and result folders (claude_cli: claude-sonnet-5-5)

    if no_log:
        disable_logging()
        log_path = None
    else:
        if log_dir is None and "DD_LOG_DIR" not in os.environ:
            log_dir = Path.home() / ".graflang" / "logs"
        log_path = setup_logging(graph_path.name.removesuffix(".graph.yaml").removesuffix(".yaml"), adapter=adapter, model=model or "",
                                 log_dir=log_dir, log_level=log_level, log_format=log_format or os.environ.get("DD_LOG_FORMAT") or "both")

    console.print(f"[bold blue]⚡ Loading graph:[/bold blue] {graph_path}")
    graph_data = _load_or_exit(graph_path)
    if bindings:
        graph_data, notes = bind_graph(graph_data, bindings)
        for note in notes:
            console.print(f"[yellow]warning:[/yellow] {escape(note)}")

    from .capabilities import capability_errors
    from .resolver import ResourceResolver
    denied = capability_errors(graph_data, ResourceResolver(Path(graph_data.get("_source_dir", ".")), graph_data.get("resources")))
    if denied:
        for message in denied:
            console.print(f"[red]error:[/red] {escape(message)}")
        console.print("[red]✗ The workflow policy does not allow this graph; nothing was run[/red]")
        sys.exit(1)

    console.print(f"[bold green]✓[/bold green] Graph loaded: {graph_data['workflow']['name']}")
    console.print(f"  Nodes: {len(graph_data['nodes'])}")
    console.print(f"  Edges: {len(graph_data['edges'])}")

    # Parse parameters
    params = dict(bindings.get("params", {}))
    for p in param:
        if '=' not in p:
            raise click.BadParameter(f"expected key=value, got {p!r}", param_hint="--param")
        key, value = p.split('=', 1)
        params[key] = value

    run_output = None
    if not no_output:
        run_output = RunOutput(output_dir or graph_path.resolve().parent / "output",
                               graph_path.name.removesuffix(".graph.yaml").removesuffix(".yaml"), adapter,
                               model=model or "", params=params, save_nodes=save_nodes)

    console.print(f"\n[bold blue]▶ Executing workflow...[/bold blue]")

    try:
        if record_file and replay_file:
            raise click.UsageError("use --record or --replay, not both")
        llm = ReplayLLM(Path(replay_file)) if replay_file else make_llm(adapter, explicit_model)
        if record_file:
            llm = RecordingLLM(llm, Path(record_file))
        llm = MeteredLLM(llm, limits.get("max_llm_calls"), limits.get("max_cost_usd"))
        runtime = GraphLangRuntime(graph_data, llm=llm, adapter=adapter, model=model, max_steps=max_steps, wall_time_s=limits.get("wall_time_s"),
                                   workers=workers or limits.get("concurrency") or 1,
                                   node_output=run_output if save_nodes else None)
        if adapter == "mock":
            console.print("[yellow]adapter: mock (no LLM is called); use --adapter claude_cli, ollama, ... for real output[/yellow]")
        if checkpoint_file or resume_file:
            runtime.checkpoint_path = Path(checkpoint_file or resume_file)
        result = runtime.resume(Path(resume_file)) if resume_file else runtime.execute(params)
    except (ValueError, RuntimeError, NotImplementedError, CassetteError, LimitExceeded) as e:
        console.print(f"[red]✗ Run failed:[/red] {escape(str(e))}")
        if log_path:
            console.print(f"[dim]log: {log_path}[/dim]")
        sys.exit(1)

    if not result:
        console.print("\n[yellow]Workflow ended without reaching an OUTPUT node (a gate routed to a dead end)[/yellow]")
    else:
        console.print(f"\n[bold green]✓ Workflow completed[/bold green]")
    console.print(f"[bold]Output:[/bold] {escape(str(result))}")
    summary = runtime.summary()
    console.print(f"[dim]{_summary_line(summary)}[/dim]")        # values may hold [brackets], not markup
    if run_output and result:
        run_output.save_result(result)
        run_output.save_summary(summary)
        console.print(f"[dim]output: {run_output.dir}[/dim]")
    if log_path:
        console.print(f"[dim]log: {log_path}[/dim]")


def _summary_line(summary: dict) -> str:
    """One line: steps, LLM calls with tokens and cost, and the slowest node."""
    parts = [f"{summary['steps']} steps"]
    llm = summary.get("llm")
    if llm and llm["calls"]:
        usage = f"{llm['calls']} LLM calls"
        if llm["input_tokens"] or llm["output_tokens"]:
            usage += f", {llm['input_tokens']} tokens in / {llm['output_tokens']} out"
        if llm["cost_usd"]:
            usage += f", ${llm['cost_usd']:.4f}"
        parts.append(usage)
    if summary["nodes"]:
        slowest, row = next(iter(summary["nodes"].items()))
        parts.append(f"slowest: {slowest} {row['ms'] / 1000:.1f}s")
    return " · ".join(parts)


@click.command("validate", short_help="Check a workflow against the schema and wiring rules.")
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
        console.print(f"[red]✗ Validation failed:[/red] {escape(str(e))}")
        sys.exit(1)
    errors, warnings = check(graph_data)
    for w in warnings:
        console.print(f"[yellow]warning:[/yellow] {escape(str(w))}")
    for e in errors:
        console.print(f"[red]error:[/red] {escape(str(e))}")
    if errors:
        console.print(f"[red]✗ {len(errors)} problem(s)[/red] in {graph_data['workflow']['name']}")
        sys.exit(1)
    console.print(f"[bold green]✓[/bold green] Valid GraphLang workflow: {graph_data['workflow']['name']}"
                  + (f" ({len(warnings)} warning(s))" if warnings else ""))


@click.command("info", short_help="Show a workflow's nodes, edges, inputs and outputs.")
@click.argument("graph")
def cmd_info(graph):
    """Display information about a GraphLang workflow."""
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)
    graph_data = _load_or_exit(graph_path)

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



@click.command("expand", short_help="Print a compact (steps:) workflow in its long nodes/edges form.")
@click.argument("graph")
def cmd_expand(graph):
    """Print the long form of a workflow written with `steps:`; a file already in long form prints as it is."""
    from ruamel.yaml import YAML
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)
    data = _load_or_exit(graph_path)
    data.pop("_source_dir", None)
    data.pop("_part_of", None)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.sort_base_mapping_type_on_output = False
    yaml.dump(data, sys.stdout)
