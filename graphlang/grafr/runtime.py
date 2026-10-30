"""GraphLang runtime: executes a graph by passing control tokens along `triggers` edges.

Model (kept deliberately small):

* A node *fires* when a control token reaches it over a `triggers` edge. The exception is a `JOIN`,
  a barrier: it fires once a token has arrived over every one of its incoming `triggers` edges.
* A fired node reads its `in_*` ports from the `binds` edges that end at it (the latest value written
  to the source port), runs its executor, and stores the executor's outputs on its `out_*` ports.
* It then emits control tokens on its control output ports (ports that are not `in_*`/`out_*`/`trigger`):
  the one named by the executor's `_route`, else every control port for a `FORK`, else the first of
  `complete`, `exit`, `entry`.
* Nodes may fire any number of times, so a retry wire back to an earlier node is a real loop. A run
  is stopped after `max_steps` firings (shared by LOOP bodies), so a loop that never exits cannot hang.
* A `LOOP` node runs its `subgraph` once per iteration (see `_run_loop`, and the design notes `claude/readme-design.md` described in docs/DEV/readme.md).

The graph is a `networkx.MultiDiGraph`: a `triggers` edge and a `binds` edge between the same two
nodes, or several edges of the same kind on different ports, are all kept.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx
from jsonschema import ValidationError, validate
from rich.console import Console
from ruamel.yaml import YAML

from .adapters import make_llm
from .cedar_guard import CedarGuard
from .pii import has_pii
from .compact import expand, is_compact
from .expr import ExpressionError, evaluate, evaluate_condition
from ..formats import require_graphlang
from ..logging_config import DEBUG, ERROR, INFO, WARNING, get_logger, log_event
from .kernel import KernelPool
from .lifecycle import run_phases
from .output import RunOutput
from .parts import flatten_parts
from .ports import apply_input_types, check_value, normalize_ports
from .resolver import ResourceResolver
from .run_node import run_run
from .solve_backend import CODE_KEYS, code_keys_in, run_backend
from .topology import invariants

console = Console()
_log = get_logger("grafr.runtime")

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "graflang-ir.json"
DELTA_SCHEMA_PATH = SCHEMA_PATH.with_name("graph_delta.schema.json")
IMMUTABLE_KEYS = {"id", "type", "ports"}            # update_config may not touch these
PROTECTED_TYPES = {"INPUT", "OUTPUT"}               # remove_node may not remove the workflow's ends
SAFETY_TYPES = {"GUARD", "MUTATE"}                  # the safety layer: a delta may not remove these nor change their config
SAFETY_KEYS = {"risky"}                             # nor mark or unmark any node as risky
DEFAULT_MAX_MUTATIONS = 3
DEFAULT_EMIT = ("complete", "exit", "entry")
DEFAULT_MAX_STEPS = 1000
DEFAULT_LOOP_MAX = 100
TRUE_WORDS, FALSE_WORDS = {"true", "1", "yes", "y"}, {"false", "0", "no", "n"}


def load_graph(graph_path: Path) -> Dict:
    """Load a GraphLang YAML file and validate it against the schema. A missing schema is an error:
    silently skipping validation would let invalid graphs through."""
    graph_path = Path(graph_path)
    with open(graph_path, "r", encoding="utf-8") as f:
        graph_data = YAML(typ="safe").load(f)
    if is_compact(graph_data):
        graph_data = expand(graph_data)
    graph_data["_source_dir"] = str(graph_path.resolve().parent)
    flatten_parts(graph_data)                           # SUBGRAPH nodes become the part's own nodes
    require_graphlang(graph_data, graph_path)
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"GraphLang schema not found at {SCHEMA_PATH}")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        validate(instance=graph_data, schema=schema)
    except ValidationError as e:
        where = "/".join(str(p) for p in e.absolute_path) or "<root>"
        raise ValueError(f"Schema validation failed at {where}: {e.message}") from e
    graph_data["_source_dir"] = str(graph_path.resolve().parent)
    normalize_ports(graph_data["nodes"])
    apply_input_types(graph_data)
    return graph_data


def split_ref(ref: str) -> tuple[str, str]:
    """'node.port' -> ('node', 'port'). Node ids contain no dots (the schema forbids them)."""
    node, _, port = ref.partition(".")
    if not node or not port:
        raise ValueError(f"expected 'node.port', got {ref!r}")
    return node, port


def coerce(name: str, value: Any, type_name: str) -> Any:
    """Command-line parameters arrive as text; convert them to the declared type. Other values pass through."""
    if not isinstance(value, str):
        return value
    t = (type_name or "TEXT").upper()
    try:
        if t in ("INTEGER", "INT"):
            return int(value)
        if t in ("FLOAT", "NUMBER", "REAL"):
            return float(value)
        if t in ("BOOL", "BOOLEAN"):
            if value.strip().lower() in TRUE_WORDS:
                return True
            if value.strip().lower() in FALSE_WORDS:
                return False
            raise ValueError("not a boolean")
    except ValueError:
        raise ValueError(f"input {name!r} must be {t}, got {value!r}") from None
    return value


class RunLimitExceeded(RuntimeError):
    """The run fired more nodes than `max_steps` allows (probably a loop that never exits)."""


class _Budget:
    def __init__(self, max_steps: int, wall_time_s: Optional[float] = None):
        self.max_steps, self.steps, self.mutations = max_steps, 0, 0
        self.deadline = time.monotonic() + wall_time_s if wall_time_s else None
        self._lock = threading.Lock()                   # BATCH iterations spend from several threads
        self.wall_time_s = wall_time_s

    def spend(self, fired: Dict[str, int]) -> None:
        with self._lock:
            self.steps += 1
            steps = self.steps
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise RunLimitExceeded(f"stopped after {self.wall_time_s}s of wall time (limits.wall_time_s) at step {steps}")
        if steps > self.max_steps:
            raise RunLimitExceeded(f"stopped after {self.max_steps} node firings; "
                                   f"most fired: {sorted(fired.items(), key=lambda x: -x[1])[:3]}")


class GraphLangRuntime:
    """Execute a GraphLang workflow."""

    def __init__(self, graph_data: Dict, adapter: str = "mock", max_steps: int = DEFAULT_MAX_STEPS,
                 verbose: bool = True, model: Optional[str] = None, llm=None,
                 node_output: Optional[RunOutput] = None, wall_time_s: Optional[float] = None, workers: int = 1, *,
                 _parent: "GraphLangRuntime | None" = None, _nodes: Optional[List[Dict]] = None,
                 _edges: Optional[List[Dict]] = None, _boundary: Optional[Dict[str, Any]] = None,
                 _scope: Optional[Dict[str, Any]] = None):
        self.graph_data = graph_data
        flatten_parts(graph_data)
        normalize_ports(graph_data["nodes"])
        apply_input_types(graph_data)
        self.verbose = verbose
        self.G = nx.MultiDiGraph()
        self.values: Dict[tuple, Any] = {}              # (node, port) -> latest value
        self._stamp: Dict[tuple, int] = {}              # (node, port) -> when it was written (for "last writer wins")
        self._clock = 0
        self.fired: Dict[str, int] = {}                 # node -> times fired
        self.emitted: set = set()                       # (node, control port) that sent a token
        self.outputs: Dict[str, Any] = {}
        self.loop_iterations: Dict[str, int] = {}
        self._pending_join: Dict[str, set] = {}          # JOIN tokens that have arrived, per node
        self.checkpoint_path: Optional[Path] = None      # set by the caller (graf run --checkpoint) on the top-level runtime
        self._checkpoint_failed = False
        self.boundary = _boundary or {}                 # in_* values a LOOP hands to its subgraph
        self.scope = _scope or {}                       # loop state (cycle, previous outputs)
        if _parent is None:
            self.llm = llm or make_llm(adapter, model)
            self.context: Dict[str, Any] = {}           # CONTEXT nodes' persistent state
            self.budget = _Budget(max_steps, wall_time_s)
            self.stats: Dict[str, Dict[str, Any]] = {}  # node -> {type, n, ms}, shared with LOOP and BATCH bodies
            self._stats_lock = threading.Lock()
            self.workers = max(1, int(workers))         # >1: nodes released together run concurrently (_drain_waves)
            self.resolver = ResourceResolver(Path(graph_data.get("_source_dir", ".")), graph_data.get("resources"))
            self.depth = 0
            self.node_output = node_output              # --save-nodes: where each node's outputs are written
            self.kernels = KernelPool()                 # kernel SOLVE nodes' Python kernels, closed when the run ends
        else:
            self.llm, self.context, self.budget = _parent.llm, _parent.context, _parent.budget
            self.workers = _parent.workers
            self.stats, self._stats_lock = _parent.stats, _parent._stats_lock
            self.resolver, self.depth = _parent.resolver, _parent.depth + 1
            self.node_output = _parent.node_output
            self.kernels = _parent.kernels
        self.mutated = False                            # a MUTATE changed this runtime's graph (a LOOP can carry it on)
        self._build_graph(_nodes if _nodes is not None else graph_data["nodes"],
                          _edges if _edges is not None else graph_data["edges"])

    @property
    def steps(self) -> int:
        return self.budget.steps

    # ---- graph ------------------------------------------------------------------------------
    def _build_graph(self, nodes: List[Dict], edges: List[Dict]) -> None:
        ids = set()
        for node in nodes:
            if node["id"] in ids:
                raise ValueError(f"duplicate node id {node['id']!r}")
            ids.add(node["id"])
            self.G.add_node(node["id"], **node)
        for edge in edges:
            (src, sport), (tgt, tport) = split_ref(edge["source"]), split_ref(edge["target"])
            for end, port in ((src, sport), (tgt, tport)):
                if end not in ids:
                    raise ValueError(f"edge {edge['source']} -> {edge['target']} names unknown node {end!r}")
                if port not in self.G.nodes[end]["ports"]:
                    raise ValueError(f"edge {edge['source']} -> {edge['target']}: node {end!r} has no port {port!r}")
            self.G.add_edge(src, tgt, source_port=sport, target_port=tport, type=edge["type"])

    def _trigger_edges_in(self, node: str) -> List[tuple]:
        return [(u, k) for u, _, k, d in self.G.in_edges(node, keys=True, data=True) if d["type"] == "triggers"]

    def _entry_nodes(self) -> List[str]:
        """INPUT nodes that nothing triggers or feeds."""
        return [n for n, d in self.G.nodes(data=True) if d["type"] == "INPUT" and not self.G.in_degree(n)]

    def _start_nodes(self) -> List[str]:
        """Nodes nothing triggers: where each iteration of a LOOP body begins."""
        return [n for n in self.G.nodes if not self._trigger_edges_in(n)]

    # ---- execution --------------------------------------------------------------------------
    def execute(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the workflow and return its outputs: a dict keyed by the workflow's declared output name."""
        wf = self.graph_data["workflow"]["name"]
        log_event(_log, "run.start", workflow=wf, nodes=self.G.number_of_nodes(), inputs=sorted(inputs or {}),
                  adapter=self.llm.name, model=getattr(self.llm, "model_override", None))
        started = time.perf_counter()
        try:
            outputs = self._execute(inputs)
        except Exception as e:
            log_event(_log, "run.fail", level=ERROR, workflow=wf, steps=self.steps, error=f"{type(e).__name__}: {e}",
                      ms=round((time.perf_counter() - started) * 1000))
            raise
        finally:
            self.kernels.close()                    # also on Ctrl-C: no kernel outlives its run
        log_event(_log, "run.end", workflow=wf, steps=self.steps, outputs=sorted(outputs),
                  reached_output=bool(outputs), mutations=self.budget.mutations,
                  ms=round((time.perf_counter() - started) * 1000))
        return outputs

    def summary(self) -> Dict[str, Any]:
        """What the last run did: steps, per-node firings and time, and the LLM's calls, tokens and cost when it is metered."""
        llm = self.llm.snapshot() if hasattr(self.llm, "snapshot") else None
        return {"steps": self.steps, "mutations": self.budget.mutations, "llm": llm,
                "nodes": {k: dict(v) for k, v in sorted(self.stats.items(), key=lambda kv: -kv[1]["ms"])}}

    # ---- checkpoint and resume -------------------------------------------------------------------
    def _graph_id(self) -> str:
        """Identifies the graph as loaded, so a checkpoint is never resumed on a different one."""
        return hashlib.sha256(json.dumps([self.graph_data["nodes"], self.graph_data["edges"]], sort_keys=True, default=str).encode()).hexdigest()[:16]

    def _checkpoint(self, queue: deque) -> None:
        """Save the run's state before the next node is taken, so a run that fails there can be resumed from here. Top level only:
        a LOOP or BATCH is one step, and a failure inside one re-runs that node. Kernel variables are not saved."""
        if self.checkpoint_path is None or self.depth or self._checkpoint_failed:
            return
        state = {"checkpoint": 1, "workflow": self.graph_data["workflow"]["name"], "graph_id": self._graph_id(), "clock": self._clock,
                 "values": [[n, p, v, self._stamp[(n, p)]] for (n, p), v in self.values.items()],
                 "fired": self.fired, "emitted": sorted(self.emitted), "outputs": self.outputs, "context": self.context,
                 "steps": self.budget.steps, "mutations": self.budget.mutations,
                 "queue": [[node, list(key) if key else None] for node, key in queue],
                 "pending_join": {n: [list(k) for k in keys] for n, keys in self._pending_join.items()},
                 "loop_iterations": self.loop_iterations}
        if self.budget.mutations:
            nodes, edges = self._lists(self.G)
            state["graph"] = {"nodes": nodes, "edges": edges}
        try:
            text = json.dumps(state, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            self._checkpoint_failed = True
            log_event(_log, "checkpoint.skipped", level=WARNING, reason=f"a value is not JSON: {e}")
            return
        tmp = self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self.checkpoint_path)                       # a crash while writing never leaves a half file

    def resume(self, path: Path) -> Dict[str, Any]:
        """Continue a run from a checkpoint made by this same graph and return its outputs."""
        try:
            state = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"cannot read checkpoint {path}: {e}") from None
        if state.get("checkpoint") != 1:
            raise ValueError(f"{path} is not a graflang checkpoint")
        if state.get("graph_id") != self._graph_id():
            raise ValueError(f"checkpoint {Path(path).name} was made by a different graph (or a different version of this one)")
        if "graph" in state:                                    # a MUTATE had changed the graph by then
            self.G.clear()
            self._build_graph(state["graph"]["nodes"], state["graph"]["edges"])
        self._clock, self.fired, self.outputs = state["clock"], state["fired"], state["outputs"]
        self.values = {(n, p): v for n, p, v, _ in state["values"]}
        self._stamp = {(n, p): t for n, p, _, t in state["values"]}
        self.emitted = {tuple(e) for e in state["emitted"]}
        self.context.update(state["context"])
        self.budget.steps, self.budget.mutations = state["steps"], state["mutations"]
        self.loop_iterations = state.get("loop_iterations", {})
        self._pending_join = {n: {tuple(k) for k in keys} for n, keys in state["pending_join"].items()}
        queue = deque((node, tuple(key) if key else None) for node, key in state["queue"])
        log_event(_log, "run.resume", workflow=state["workflow"], steps=state["steps"], queued=len(queue))
        try:
            self._drain(queue)
        finally:
            self.kernels.close()
        return self.outputs

    def _execute(self, inputs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        inputs = dict(inputs or {})
        declared = {p["name"]: p for p in self.graph_data["workflow"].get("inputs", [])}
        unknown = set(inputs) - set(declared)
        if unknown:
            raise ValueError(f"unknown workflow input(s) {sorted(unknown)}; declared: {sorted(declared)}")
        for name, p in declared.items():
            if name not in inputs and "default" in p:
                inputs[name] = p["default"]
        missing = [n for n in declared if n not in inputs]
        if missing:
            raise ValueError(f"missing workflow input(s): {missing}")
        inputs = {n: coerce(n, v, declared[n].get("type", "TEXT")) for n, v in inputs.items()}

        entries = self._entry_nodes()
        if not entries:
            raise ValueError("no entry node: need an INPUT node with no incoming edges")
        queue: deque = deque()
        for n in entries:
            for name, value in inputs.items():
                self._write(n, f"out_{name}", value)
            self._emit(n, {}, queue)
        self._drain(queue)
        return self.outputs

    def _drain(self, queue: deque) -> None:
        if self.workers > 1:
            return self._drain_waves(queue)
        pending_join = self._pending_join
        while queue:
            self._checkpoint(queue)
            node = self._take(queue, pending_join)
            if node is not None:
                self._fire(node, queue)

    def _take(self, queue: deque, pending_join: Dict[str, set]) -> Optional[str]:
        """The next node that fires from the queue, or None (a token for a removed node, or a JOIN still waiting)."""
        node, edge_key = queue.popleft()
        if node not in self.G:                          # removed by a MUTATE while the token was in flight
            return None
        if self.G.nodes[node]["type"] == "JOIN" and edge_key is not None:
            need = set(self._trigger_edges_in(node))
            got = pending_join.setdefault(node, set())
            got.add(edge_key)
            if got < need:
                return None
            pending_join[node] = set()
        self.budget.spend(self.fired)
        return node

    def _drain_waves(self, queue: deque) -> None:
        """Concurrent mode (workers > 1). All tokens waiting in the queue form a wave: the nodes in it are released together.
        GENERATE and slow SOLVE nodes in a wave run on a thread pool, reading the values from before the wave started; every
        other node runs in token order when its turn comes. Results are applied (written, routed) strictly in token order, so
        a run does not depend on which call finishes first. With one worker none of this applies."""
        pending_join = self._pending_join
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            while queue:
                self._checkpoint(queue)
                wave = []
                while queue:
                    node = self._take(queue, pending_join)
                    if node is not None:
                        wave.append(node)
                jobs: Dict[int, Any] = {}
                for i, node in enumerate(wave):                    # submit the slow ones first, so they overlap
                    data = self.G.nodes[node]
                    if self._concurrent(data):
                        began = self._begin(node)
                        jobs[i] = (began, pool.submit(self._execute_node, data["type"], data, began[0]))
                try:
                    for i, node in enumerate(wave):
                        if node not in self.G:
                            continue
                        data = self.G.nodes[node]
                        began, future = jobs[i] if i in jobs else (self._begin(node), None)
                        self._complete(node, data, began, future, queue)
                finally:
                    for _, future in jobs.values():                # on an error let the other calls finish before the pool closes
                        future.cancel()

    @staticmethod
    def _concurrent(data: Dict) -> bool:
        cfg = data.get("config", {})
        return data["type"] in ("GENERATE", "RUN") or (data["type"] == "SOLVE" and (cfg.get("backend") == "subprocess" or "procedure_ref" in cfg))

    def _fire(self, node: str, queue: deque) -> None:
        data = self.G.nodes[node]
        self._complete(node, data, self._begin(node), None, queue)

    def _begin(self, node: str) -> tuple:
        """Count the firing and read the node's inputs now; returns (inputs, start time)."""
        data = self.G.nodes[node]
        self.fired[node] = self.fired.get(node, 0) + 1
        if self.verbose:
            console.print(f"{'  ' * self.depth}[cyan]⚡[/cyan] {data['type']} {node} (#{self.fired[node]})")
        in_data = self._gather_inputs(node)
        log_event(_log, "node.fire", level=DEBUG, node=node, type=data["type"], n=self.fired[node], depth=self.depth,
                  inputs=sorted(in_data))
        return in_data, time.perf_counter()

    def _complete(self, node: str, data: Dict, began: tuple, future, queue: deque) -> None:
        """Get the node's result (run it now, or wait for its future), then write it, save it and route the token."""
        in_data, started = began
        try:
            result = (future.result() if future is not None else self._execute_node(data["type"], data, in_data)) or {}
        except Exception as e:
            log_event(_log, "node.error", level=ERROR, node=node, type=data["type"], n=self.fired[node],
                      depth=self.depth, error=f"{type(e).__name__}: {e}")
            raise
        ms = round((time.perf_counter() - started) * 1000)
        log_event(_log, "node.done", node=node, type=data["type"], n=self.fired[node], depth=self.depth,
                  route=result.get("_route"), outputs=sorted(p for p in result if not p.startswith("_")), ms=ms)
        with self._stats_lock:
            row = self.stats.setdefault(node, {"type": data["type"], "n": 0, "ms": 0})
            row["n"] += 1
            row["ms"] += ms
        for port, value in result.items():
            if not port.startswith("_"):
                check_value(data, port, value)
                self._write(node, port, value)
        if self.node_output:
            self.node_output.save_node(self.steps, node, result)
        if data["type"] == "OUTPUT":
            self._collect_outputs(in_data)
        self._emit(node, result, queue)

    def _write(self, node: str, port: str, value: Any) -> None:
        self._clock += 1
        self.values[(node, port)] = value
        self._stamp[(node, port)] = self._clock

    def _gather_inputs(self, node: str) -> Dict[str, Any]:
        """in_* ports: the latest value on the source port of each `binds` edge that ends here (if several
        edges feed one port, the most recently written source wins); inside a
        LOOP body, a port nothing is bound to falls back to the loop's own input of that name, then to a
        loop-state variable of that name (so `in_chapter_index` reads `chapter_index`)."""
        in_data: Dict[str, Any] = {}
        newest: Dict[str, int] = {}
        for src, _, d in self.G.in_edges(node, data=True):
            key = (src, d["source_port"])
            if d["type"] == "binds" and key in self.values and self._stamp[key] > newest.get(d["target_port"], 0):
                in_data[d["target_port"]] = self.values[key]
                newest[d["target_port"]] = self._stamp[key]
        for port in self.G.nodes[node]["ports"]:
            if port.startswith("in_") and port not in in_data:
                latest = self.scope.get(port[3:])
                if latest is not None:                           # loop state (the previous iteration's output) beats the loop's own input of that name
                    in_data[port] = latest
                elif port in self.boundary:
                    in_data[port] = self.boundary[port]
                elif port[3:] in self.scope:
                    in_data[port] = self.scope[port[3:]]
        return in_data

    def _control_ports(self, node: str) -> List[str]:
        return [p for p in self.G.nodes[node]["ports"]
                if p != "trigger" and not p.startswith(("in_", "out_"))]

    def _emit(self, node: str, result: Dict, queue: deque) -> None:
        """Send a control token over the `triggers` edges that leave the chosen control port(s)."""
        ports = self._control_ports(node)
        route = result.get("_route")
        if result.get("_halt"):                           # RECOVER action halt: this branch ends here
            chosen = []
        elif route is not None:
            if route not in ports:
                raise ValueError(f"node {node!r} routed to {route!r}, which is not one of its ports {ports}")
            chosen = [route]
        elif self.G.nodes[node]["type"] == "FORK":
            chosen = ports
        else:
            chosen = [next((p for p in DEFAULT_EMIT if p in ports), None)]
            chosen = [p for p in chosen if p] or ports
        for p in chosen:
            self.emitted.add((node, p))
        for _, tgt, key, d in self.G.out_edges(node, keys=True, data=True):
            if d["type"] == "triggers" and d["source_port"] in chosen:
                queue.append((tgt, (node, key)))

    def _collect_outputs(self, in_data: Dict[str, Any]) -> None:
        names = list(in_data)
        declared = [p["name"] for p in self.graph_data["workflow"].get("outputs", [])]
        if len(names) == 1 and len(declared) == 1:
            self.outputs[declared[0]] = in_data[names[0]]
        else:
            for port, value in in_data.items():
                self.outputs[port.removeprefix("in_")] = value

    def _execute_node(self, node_type: str, node_data: Dict, in_data: Dict) -> Dict:
        if node_type == "LOOP":                       # control structures: they need the runtime, not an executor
            return self._run_loop(node_data, in_data)
        if node_type == "BATCH":
            return self._run_batch(node_data, in_data)
        if node_type == "MUTATE":
            return self._run_mutate(node_data, in_data)
        if node_type == "RUN":
            run = lambda data: run_run(node_data, data, self.resolver, self.kernels)
        elif node_type == "SOLVE" and node_data.get("config", {}).get("backend"):
            run = lambda data: run_backend(node_data, data, self.resolver, self.kernels)
        else:
            from .nodes import get_node_executor
            executor = get_node_executor(node_type)
            run = lambda data: executor.execute(node_data, data, self.context, self.resolver, self.llm)
        return run_phases(node_data, in_data, run)

    # ---- LOOP ---------------------------------------------------------------------------------
    def _run_loop(self, node_data: Dict, in_data: Dict[str, Any]) -> Dict:
        """Run the node's `subgraph` once per iteration.

        config:
          condition       keep looping while true; checked before every iteration (optional)
          max_iterations  a number or an expression such as "@in_max_cycles" (default 100)
          index_var       name of the iteration counter, 0-based (default `cycle`)
          outputs         the LOOP's out_* ports, each one of
                            {from: "node.out_port"}     the value the latest iteration wrote; if that iteration wrote none, the
                                                        previous one (it starts as the LOOP's input of the same name). A list
                                                        of ports: whichever wrote last, for a variable set on exclusive branches
                            {collect: "node.out_port"}  a list, one value per iteration
                            {fired: "node.port"}        true if a token left that port in the latest iteration
          persist_mutations  true: what a MUTATE in the body changed stays for the next iterations (default: each
                          iteration starts from the body as written; the mutation budget is still shared)
          subgraph        {nodes, edges}: the body. Nodes nothing triggers start each iteration, and an
                          in_* port with no `binds` edge reads the LOOP's input of that name, else a
                          loop-state variable of that name.

        Condition and max_iterations see: the LOOP's in_* values (as @in_x), the previous outputs (as @name,
        without `out_`), and the counter. Returns the out_* values and routes to `exit`.
        """
        cfg = node_data.get("config", {})
        body = cfg.get("subgraph")
        if not body:
            raise ValueError(f"LOOP {node_data['id']!r} has no subgraph")
        if "condition" not in cfg and "max_iterations" not in cfg:
            raise ValueError(f"LOOP {node_data['id']!r} needs a condition or max_iterations")
        index_var = cfg.get("index_var", "cycle")
        specs: Dict[str, Dict] = cfg.get("outputs", {})
        state: Dict[str, Any] = {}
        for name, spec in specs.items():
            kinds = [k for k in ("from", "collect", "fired") if k in spec]
            if len(kinds) != 1:
                raise ValueError(f"LOOP {node_data['id']!r} output {name!r} needs exactly one of from/collect/fired")
            # a `from` variable starts as the LOOP's input of the same name (its value before the loop), if there is one
            state[name] = [] if kinds[0] == "collect" else False if kinds[0] == "fired" else in_data.get(f"in_{name}")

        persist = bool(cfg.get("persist_mutations"))
        body = {"nodes": body["nodes"], "edges": body.get("edges", [])}
        cycle = 0
        while True:
            scope = {**in_data, **state, index_var: cycle, "cycle": cycle}
            try:
                limit = cfg.get("max_iterations", DEFAULT_LOOP_MAX)
                limit = int(evaluate(limit, scope)) if isinstance(limit, str) else int(limit)
                if cycle >= limit or ("condition" in cfg and not evaluate_condition(cfg["condition"], scope)):
                    break
            except ExpressionError as e:
                raise ValueError(f"LOOP {node_data['id']!r}: {e}") from None
            log_event(_log, "loop.iteration", level=DEBUG, node=node_data["id"], cycle=cycle, depth=self.depth)
            sub = GraphLangRuntime(self.graph_data, _parent=self, _nodes=body["nodes"], _edges=body["edges"],
                                   _boundary=in_data, _scope=scope, verbose=self.verbose)
            queue: deque = deque((n, None) for n in sub._start_nodes())
            sub._drain(queue)
            if persist and sub.mutated:
                nodes, edges = self._lists(sub.G)
                body = {"nodes": nodes, "edges": edges}
                log_event(_log, "loop.persisted", level=DEBUG, node=node_data["id"], cycle=cycle, nodes=len(nodes), depth=self.depth)
            for name, spec in specs.items():
                if "from" in spec:
                    refs = [split_ref(r) for r in ([spec["from"]] if isinstance(spec["from"], str) else spec["from"])]
                    written = [k for k in refs if k in sub.values]
                    if written:                                      # an iteration that sets it on no branch leaves it as it was
                        state[name] = sub.values[max(written, key=lambda k: sub._stamp[k])]
                elif "collect" in spec:
                    state[name].append(sub.values.get(split_ref(spec["collect"])))
                else:
                    state[name] = split_ref(spec["fired"]) in sub.emitted
            cycle += 1
        self.loop_iterations[node_data["id"]] = cycle
        log_event(_log, "loop.end", node=node_data["id"], iterations=cycle, depth=self.depth)
        result = {f"out_{name}": value for name, value in state.items()}
        result["_route"] = "exit"
        return result

    # ---- BATCH --------------------------------------------------------------------------------
    def _run_batch(self, node_data: Dict, in_data: Dict[str, Any]) -> Dict:
        """Run the node's `subgraph` once per item of a list and collect one value per item (design E5, map).

        config:
          over         the in_* port holding the list (default: the node's first in_* port); a JSON text is parsed
          item_var     name of the current item inside the body (default `item`; `index` is its position)
          concurrency  items processed at the same time (default: the run's workers); results keep the item order
          max_items    refuse longer lists (default 1000)
          outputs      the BATCH's out_* ports, each {collect: "node.out_port"}: the list of that value, one per item
          subgraph     {nodes, edges}: the body, as in LOOP. An in_* port with no `binds` edge reads the BATCH's input of
                       that name, else `item` / `index`.

        Every item runs in a fresh copy of the body, like a LOOP iteration, so items cannot see each other. Routes to `exit`.
        """
        cfg, nid = node_data.get("config", {}), node_data["id"]
        body = cfg.get("subgraph")
        if not body:
            raise ValueError(f"BATCH {nid!r} has no subgraph")
        over = cfg.get("over") or next((p for p in node_data["ports"] if p.startswith("in_")), None)
        items = in_data.get(over)
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except json.JSONDecodeError:
                pass
        if not isinstance(items, (list, tuple)):
            raise ValueError(f"BATCH {nid!r}: {over!r} must hold a list, got {type(items).__name__}")
        if len(items) > int(cfg.get("max_items", 1000)):
            raise ValueError(f"BATCH {nid!r}: {len(items)} items is over max_items ({cfg.get('max_items', 1000)})")
        specs: Dict[str, Dict] = cfg.get("outputs", {})
        for name, spec in specs.items():
            if set(spec) != {"collect"}:
                raise ValueError(f"BATCH {nid!r} output {name!r} must be {{collect: node.out_port}}")
        item_var = cfg.get("item_var", "item")
        concurrency = max(1, int(cfg.get("concurrency", self.workers)))

        def one(index: int, item: Any) -> Dict[str, Any]:
            scope = {**in_data, item_var: item, "index": index}
            sub = GraphLangRuntime(self.graph_data, _parent=self, _nodes=body["nodes"], _edges=body["edges"],
                                   _boundary=in_data, _scope=scope, verbose=self.verbose)
            if concurrency > 1:
                sub.workers = 1                                     # the items are the parallelism
            sub._drain(deque((n, None) for n in sub._start_nodes()))
            return {name: sub.values.get(split_ref(spec["collect"])) for name, spec in specs.items()}

        if concurrency == 1 or len(items) < 2:
            rows = [one(i, item) for i, item in enumerate(items)]
        else:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                rows = list(pool.map(lambda pair: one(*pair), enumerate(items)))
        log_event(_log, "batch.end", node=nid, items=len(items), concurrency=concurrency, depth=self.depth)
        result: Dict[str, Any] = {f"out_{name}": [row[name] for row in rows] for name in specs}
        result["_route"] = "exit"
        return result

    # ---- MUTATE ------------------------------------------------------------------------------
    def _run_mutate(self, node_data: Dict, in_data: Dict[str, Any]) -> Dict:
        """Apply a graph delta proposed on port `in_delta` (a dict, or the JSON text an LLM wrote).

        A delta is applied only if, in this order: it parses; it matches graph_delta.schema.json; it keeps the
        graph well formed (known nodes and ports, right port kinds, no duplicates); the Cedar policy
        `config.policy_ref` allows it; and fewer than `config.max_mutations` (default 3) were applied so far.
        Self-revision is deny-by-default: no `policy_ref`, no mutation. Routes to `applied` or `rejected`
        (the node must declare both ports) and writes the reason on `out_reason` if the node has that port.
        """
        node_id, cfg = node_data["id"], node_data.get("config", {})
        policy_ref = cfg.get("policy_ref")
        if not policy_ref:
            raise ValueError(f"MUTATE node {node_id!r} has no config.policy_ref (self-revision is deny-by-default)")
        missing = [p for p in ("applied", "rejected") if p not in node_data["ports"]]
        if missing:
            raise ValueError(f"MUTATE node {node_id!r} must declare the ports {missing}")

        def outcome(applied: bool, reason: str) -> Dict:
            log_event(_log, "mutate.applied" if applied else "mutate.rejected", level=INFO if applied else WARNING,
                      node=node_id, reason=reason, mutations=self.budget.mutations, depth=self.depth)
            if self.verbose:
                console.print(f"{'  ' * self.depth}  [{'green' if applied else 'red'}]{'applied' if applied else 'rejected'}[/]: {reason}")
            res: Dict[str, Any] = {"_route": "applied" if applied else "rejected"}
            if "out_reason" in node_data["ports"]:
                res["out_reason"] = reason
            return res

        try:
            delta = self._parse_delta(in_data.get("in_delta"))
            validate(instance=delta, schema=json.loads(DELTA_SCHEMA_PATH.read_text(encoding="utf-8")))
            self._check_delta(delta)
        except ValidationError as e:
            return outcome(False, f"delta does not match the schema: {e.message}")
        except ValueError as e:
            return outcome(False, str(e))

        guard = CedarGuard()
        guard.load_policy(policy_ref, self.resolver.resolve(policy_ref, "policies")["content"])
        decision = guard.decide(policy_ref, cfg.get("principal", 'Service::"llm-agent"'),
                                cfg.get("action", 'Action::"mutate_graph"'),
                                cfg.get("resource", 'Graph::"execution_topology"'),
                                self._delta_context(delta, cfg))
        if not decision.allowed:
            return outcome(False, decision.explain())
        broken = self._broken_by(delta)
        if broken:
            return outcome(False, "the delta would break the graph: " + "; ".join(broken))
        self._apply_delta(delta)
        self.mutated = True
        self.budget.mutations += 1
        return outcome(True, f"{delta['action']} {json.dumps(delta['payload'], sort_keys=True)}")

    @staticmethod
    def _parse_delta(raw: Any) -> Dict:
        if raw is None:
            raise ValueError("no delta was provided on in_delta")
        if isinstance(raw, dict):
            return raw
        text = str(raw).strip()
        if text.startswith("```"):                                   # LLMs like to wrap JSON in a code fence
            text = text.split("\n", 1)[1] if "\n" in text else ""
            text = text.rsplit("```", 1)[0]
        try:
            value = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"delta is not valid JSON: {e}") from None
        if not isinstance(value, dict):
            raise ValueError("delta must be a JSON object")
        return value

    def _port_kind_ok(self, edge_type: str, sport: str, tport: str) -> Optional[str]:
        if edge_type == "triggers":
            if sport == "trigger" or sport.startswith(("in_", "out_")) or tport != "trigger":
                return "a triggers edge goes from a control port (complete, pass, ...) to a trigger port"
        elif not (sport.startswith("out_") and tport.startswith("in_")):
            return "a binds edge goes from an out_ port to an in_ port"
        return None

    def _check_delta(self, delta: Dict) -> None:
        """Raise ValueError if applying the delta would leave the graph malformed."""
        a, p = delta["action"], delta["payload"]
        # What runs (a SOLVE's backend, code, result, command, parser) comes from the graph file only. Refused here,
        # before any policy is consulted, so no policy can grant it; the scan reaches into nested values such as a
        # LOOP's `subgraph`, which would otherwise be a way to add a node.
        smuggled = code_keys_in(p.get("config")) if a == "add_node" else code_keys_in(p.get("value")) if a == "update_config" else []
        if a == "update_config" and p["key"] in CODE_KEYS:
            smuggled.append(p["key"])
        if smuggled:
            raise ValueError(f"a delta may not add or change what runs ({', '.join(sorted(set(smuggled)))}); "
                             f"code comes only from the graph file")
        if a == "add_node":
            if p["id"] in self.G:
                raise ValueError(f"node {p['id']!r} already exists")
        elif a == "remove_node":
            if p["id"] not in self.G:
                raise ValueError(f"no node {p['id']!r}")
            if self.G.nodes[p["id"]]["type"] in PROTECTED_TYPES | SAFETY_TYPES:
                raise ValueError(f"{self.G.nodes[p['id']]['type']} nodes cannot be removed")
        elif a in ("add_edge", "remove_edge"):
            (src, sport), (tgt, tport) = split_ref(p["source"]), split_ref(p["target"])
            for n, port in ((src, sport), (tgt, tport)):
                if n not in self.G:
                    raise ValueError(f"no node {n!r}")
                if port not in self.G.nodes[n]["ports"]:
                    raise ValueError(f"node {n!r} has no port {port!r}")
            exists = any(t == tgt and d["type"] == p["type"] and d["source_port"] == sport and d["target_port"] == tport
                         for _, t, d in self.G.out_edges(src, data=True))
            if a == "add_edge":
                if (why := self._port_kind_ok(p["type"], sport, tport)):
                    raise ValueError(why)
                if exists:
                    raise ValueError("that edge already exists")
            elif not exists:
                raise ValueError("no such edge to remove")
        else:                                                         # update_config
            if p["node_id"] not in self.G:
                raise ValueError(f"no node {p['node_id']!r}")
            if p["key"] in IMMUTABLE_KEYS:
                raise ValueError(f"config key {p['key']!r} cannot be changed")
            if self.G.nodes[p["node_id"]]["type"] in SAFETY_TYPES or p["key"] in SAFETY_KEYS:
                raise ValueError(f"the safety layer cannot be changed by a delta ({p['node_id']!r}.{p['key']})")

    def _delta_context(self, delta: Dict, cfg: Dict) -> Dict[str, Any]:
        """The Cedar context. Every attribute the shipped policies read is always present (a missing one makes
        Cedar skip a `forbid`), with "" for what does not apply."""
        a, p = delta["action"], delta["payload"]

        def endpoint(ref: str) -> Dict[str, str]:
            node, port = split_ref(ref)
            return {"id": node, "type": self.G.nodes[node]["type"], "port": port}

        info = {"action": a, "node_id": "", "node_type": "", "source_port": "", "target_port": "",
                "source": {"id": "", "type": "", "port": ""}, "target": {"id": "", "type": "", "port": ""}}
        if a == "add_node":
            info.update(node_id=p["id"], node_type=p["type"])
        elif a == "remove_node":
            info.update(node_id=p["id"], node_type=self.G.nodes[p["id"]]["type"])
        elif a in ("add_edge", "remove_edge"):
            src, tgt = endpoint(p["source"]), endpoint(p["target"])
            info.update(source=src, target=tgt, source_port=f"{src['type']}.{src['port']}",
                        target_port=f"{tgt['type']}.{tgt['port']}")
        else:
            info.update(node_id=p["node_id"], node_type=self.G.nodes[p["node_id"]]["type"])
        return {"proposed_delta": info, "mutation_count": self.budget.mutations,
                "max_allowed_mutations": int(cfg.get("max_mutations", DEFAULT_MAX_MUTATIONS)),
                "human_approval": bool(cfg.get("human_approval", False)),
                "contains_pii": has_pii(delta["payload"])}

    @staticmethod
    def _lists(G: "nx.MultiDiGraph") -> tuple[List[Dict], List[Dict]]:
        nodes = [dict(d) for _, d in G.nodes(data=True)]
        edges = [{"source": f"{u}.{d['source_port']}", "target": f"{v}.{d['target_port']}", "type": d["type"]}
                 for u, v, d in G.edges(data=True)]
        return nodes, edges

    def _broken_by(self, delta: Dict) -> List[str]:
        """Errors the delta would add to topology.invariants (empty if it keeps the graph valid). The delta is tried on a
        copy, so an accepted mutation never leaves the guarantees `graf validate` gave the loaded graph."""
        trial = copy.deepcopy(self.G)
        self._apply_delta(delta, trial)
        before, after = set(invariants(*self._lists(self.G))), invariants(*self._lists(trial))
        return [m for m in after if m not in before]

    def _apply_delta(self, delta: Dict, G: Optional["nx.MultiDiGraph"] = None) -> None:
        G = self.G if G is None else G
        a, p = delta["action"], delta["payload"]
        if a == "add_node":
            G.add_node(p["id"], id=p["id"], type=p["type"], ports=list(p["ports"]), config=dict(p.get("config", {})))
        elif a == "remove_node":
            G.remove_node(p["id"])
        elif a == "add_edge":
            (src, sport), (tgt, tport) = split_ref(p["source"]), split_ref(p["target"])
            G.add_edge(src, tgt, source_port=sport, target_port=tport, type=p["type"])
        elif a == "remove_edge":
            (src, sport), (tgt, tport) = split_ref(p["source"]), split_ref(p["target"])
            for _, t, key, d in list(G.out_edges(src, keys=True, data=True)):
                if t == tgt and d["type"] == p["type"] and d["source_port"] == sport and d["target_port"] == tport:
                    G.remove_edge(src, tgt, key)
                    break
        else:
            node = G.nodes[p["node_id"]]
            node.setdefault("config", {})[p["key"]] = p["value"]
