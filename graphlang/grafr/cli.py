#!/usr/bin/env python3
"""The runtime commands of `graf`: run, validate, info (registered in graphlang/cli.py)."""

import json
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
@click.option("--kernel-name", default="python3", show_default=True,
              help="the Jupyter kernel that `backend: kernel` SOLVE nodes run in (see `jupyter kernelspec list`), e.g. sagemath; "
                   "a node's own `kernel_name` wins")
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
@click.option("--answer", multiple=True, help="an answer for a DECISION node (node=answer or node=answer|note); repeatable; without it the terminal is asked")
@click.option("--by", "answered_by", default=None, help="who gives the --answer values (recorded on the DECISION node's out_by; default the user name)")
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
@click.option("--stream", is_flag=True, help="print each node's result as soon as the node finishes, instead of only the final output (node by node, not token by token)")
@click.option("--log-prompts", type=click.Path(file_okay=False), default=None,
              help="write every prompt sent by a procedure_ref node to DIR/<procedure>/<function>_NNN.md (as spl3 run --log-prompts)")
def cmd_run(graph, llm_spec, adapter, model, max_steps, workers, kernel_name, record_file, replay_file, checkpoint_file, resume_file, bind_file, param, answer, answered_by, log_level, log_format, log_dir, no_log, output_dir, save_nodes,
            no_output, stream, log_prompts):
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
                                   workers=workers or limits.get("concurrency") or 1, kernel_name=kernel_name,
                                   node_output=run_output, on_node=_print_node if stream else None)
        if adapter == "mock":
            console.print("[yellow]adapter: mock (no LLM is called); use --adapter claude_cli, ollama, ... for real output[/yellow]")
        for a in answer:
            if '=' not in a:
                raise click.BadParameter(f"expected node=answer, got {a!r}", param_hint="--answer")
            runtime.answers[a.split('=', 1)[0]] = a.split('=', 1)[1]
        runtime.answered_by = answered_by
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
        trees = {o["name"] for o in graph_data["workflow"].get("outputs", []) if str(o.get("type", "")).upper() == "FILES"}
        run_output.save_result(result, trees)
        run_output.save_summary(summary)
        console.print(f"[dim]output: {run_output.dir}[/dim]")
    if log_path:
        console.print(f"[dim]log: {log_path}[/dim]")


def _print_node(event: dict) -> None:
    """`--stream`: one block per finished node, with its outputs (long text cut), as the run goes."""
    pad = "  " * event["depth"]
    route = f" -> {event['route']}" if event["route"] else ""
    console.print(f"{pad}[green]✓[/green] {event['type']} [bold]{event['node']}[/bold] ({event['ms']} ms){route}")
    for port, value in event["outputs"].items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        shown = text if len(text) <= 600 else text[:600] + f" … [{len(text)} chars]"
        console.print(f"{pad}  [dim]{port}:[/dim] {escape(shown)}")


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
    from graphlang.grafr import partinfo
    caps = partinfo.capabilities(graph_data.get("nodes", []))
    n = caps["llm_calls"]
    if n:
        console.print(f"Model calls per run: {'' if caps['llm_exact'] else 'at least '}{n}"
                      + (f"; suggested limits.max_llm_calls: {partinfo.suggested_cap(n)} (+50%)" if caps["llm_exact"]
                         else "; the count is not exact (a loop without a numeric max_iterations, a BATCH or a procedure): set the cap yourself"))


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
    data.pop("_parts_calls", None)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.sort_base_mapping_type_on_output = False
    yaml.dump(data, sys.stdout)


@click.command("compact", short_help="Print a long-form workflow in its compact (steps:) form: the inverse of expand.")
@click.argument("graph")
@click.option("-o", "--out", "out_file", type=click.Path(dir_okay=False), default=None, help="write to FILE instead of printing")
def cmd_compact(graph, out_file):
    """Write a long-form workflow (nodes/edges) as `steps:`. The result is checked by expanding it again; a node that
    does not come back exactly stays in `nodes:` / `edges:`. Comments and the order of nodes are not kept."""
    from ruamel.yaml import YAML
    from .compactify import NotCompactable, compactify
    graph_path = Path(graph)
    if not graph_path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {graph_path}")
        sys.exit(1)
    data = YAML(typ="safe").load(graph_path.read_text())
    try:
        result, report = compactify(data)
    except (NotCompactable, ValueError) as ex:
        console.print(f"[red]Error:[/red] {ex}")
        sys.exit(1)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.sort_base_mapping_type_on_output = False
    if out_file:
        with open(out_file, "w") as fh:
            yaml.dump(result, fh)
    else:
        yaml.dump(result, sys.stdout)
    click.echo(f"{report['steps']} steps; {report['nodes_kept']} of {report['nodes_total']} nodes and "
               f"{report['edges_kept']} of {report['edges_total']} edges kept in long form; round trip verified.", err=True)


@click.command("parts", short_help="List the parts a workflow uses: where each comes from, its pin, interface, what it touches and costs.")
@click.argument("graph")
def cmd_parts(graph):
    """For each part a workflow uses (SUBGRAPH): the recipe it resolves to, the hash that pins it (`cookbook:name@hash`), its inputs and
    outputs, what it can do outside the graph (files, e-mail, programs) and how many model calls it makes. Also checks `workflow.parts_policy`."""
    from .parts import PartError
    from .partinfo import describe, parts_report
    path = Path(graph)
    if not path.exists():
        console.print(f"[red]Error:[/red] Graph file not found: {path}")
        sys.exit(1)
    try:
        rows = parts_report(path)
    except (PartError, ValueError) as ex:
        console.print(f"[red]Error:[/red] {ex}")
        sys.exit(1)
    if not rows:
        click.echo("no parts used")
        return
    for r in rows:
        ins = ", ".join(f"{i['name']}" + (f" ({i['description']})" if i.get("description") else "") for i in r["inputs"])
        outs = ", ".join(f"{o['name']}" + (f" ({o['description']})" if o.get("description") else "") for o in r["outputs"])
        click.echo(f"{r['use']}: {r['name']}  {r['file']}  hash {r['hash']}{'  (pinned)' if r['pinned'] else ''}\n"
                   f"    takes {ins or '-'}\n    gives {outs or '-'}\n    {describe(r['capabilities'])}")


@click.command("trace", short_help="Read a run's log as a trace: a text timeline, or OpenTelemetry (OTLP/JSON).")
@click.argument("log", required=False, type=click.Path(dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["tree", "otlp"]), default="tree", show_default=True,
              help="tree: a timeline in the terminal; otlp: OpenTelemetry JSON for Jaeger, Tempo, Langfuse or a collector")
@click.option("-o", "--out", "out_file", type=click.Path(dir_okay=False), default=None, help="write to FILE instead of printing")
def cmd_trace(log, fmt, out_file):
    """Turn the .jsonl log of a run (LOG; default the newest in ~/.graflang/logs) into a trace: one span per node firing."""
    from .trace import TraceError, read_events, spans_of, to_otlp, to_tree
    path = Path(log) if log else None
    if path is None:
        logs = sorted(Path(os.environ.get("DD_LOG_DIR") or Path.home() / ".graflang" / "logs").expanduser().glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not logs:
            raise click.ClickException("no .jsonl log found; run a graph first, or give the log's path")
        path = logs[-1]
    try:
        trace = spans_of(read_events(path))
    except (TraceError, OSError) as e:
        raise click.ClickException(str(e)) from None
    text = json.dumps(to_otlp(trace), indent=2) if fmt == "otlp" else to_tree(trace)
    if out_file:
        Path(out_file).write_text(text + "\n", encoding="utf-8")
        click.echo(f"{path.name}: {len(trace['spans']) - 1} node spans -> {out_file}")
    else:
        click.echo(text)


@click.command("watch", short_help="Run a workflow again and again on a schedule (a heartbeat).",
               context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("graph", type=click.Path(dir_okay=False))
@click.option("--every", type=float, default=60.0, show_default=True, help="seconds from the start of one run to the start of the next")
@click.option("--times", type=int, default=10, show_default=True, help="stop after this many runs; 0 means until you press Ctrl-C")
@click.option("--max-failures", type=int, default=3, show_default=True, help="stop after this many failed runs in a row")
@click.pass_context
def cmd_watch(ctx, graph, every, times, max_failures):
    """Run GRAPH every EVERY seconds, as `graf run` does (everything after the options is passed to `graf run`).

    The always-on pattern: a workflow that checks something and acts when it finds work (a QUERY that reads an inbox file, an
    EVALUATE that decides, an EMIT that notifies). Each run is a separate process with its own log and output folder, so one
    bad run does not take the watcher down. Every run is bound by its own limits (give `--bind` a file with `limits`); a watcher
    that calls a real model every minute is billed every minute, which is why the default is ten runs, not forever.

        graf watch checks.graph.yaml --every 300 --times 12 --param folder=inbox --llm claude_cli:claude-haiku-5-5 --bind limits.bind.yaml
    """
    import subprocess
    import time
    from datetime import datetime
    if every <= 0:
        raise click.BadParameter("must be positive", param_hint="--every")
    command = [sys.executable, "-m", "graphlang", "run", graph, *ctx.args]
    runs = failures = 0
    click.echo(f"watching {graph}: every {every:g} s, " + (f"{times} runs" if times else "until stopped") + f"; stops after {max_failures} failures in a row")
    try:
        while not times or runs < times:
            began = time.monotonic()
            result = subprocess.run(command, capture_output=True, text=True)
            runs += 1
            failures = 0 if result.returncode == 0 else failures + 1
            lines = (result.stdout if result.returncode == 0 else result.stdout + result.stderr).strip().splitlines()
            last = lines[-1] if lines else ""
            click.echo(f"{datetime.now():%H:%M:%S} run {runs}: {'ok' if result.returncode == 0 else 'FAILED (exit ' + str(result.returncode) + ')'}  {last}"[:200])
            if failures >= max_failures:
                raise click.ClickException(f"{failures} failed runs in a row; stopped")
            if times and runs >= times:
                break
            time.sleep(max(0.0, every - (time.monotonic() - began)))
    except KeyboardInterrupt:
        click.echo(f"stopped after {runs} runs")
