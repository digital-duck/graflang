"""Running a recipe from library code: what `graf run` assembles, without its console, output folders or bindings file.

    from graphlang.recipes import Recipe, run_recipe

    out = run_recipe("path/to/build.graph.yaml", {"spec": ...}, llm="claude_cli:claude-sonnet-5-5", max_llm_calls=40)
    out.outputs, out.exit, out.error_code, out.llm_calls

    recipe = Recipe("path/to/extract.graph.yaml")          # load once (YAML, schema, parts, policy check) ...
    for doc in docs:
        recipe.run({"text": doc}, llm=my_llm)                # ... run many times; each run works on its own copy

For a package that ships recipes (app-graph, work-graph) and calls them as functions:

* **Nothing is written beside the recipe**, which may sit in a read-only site-packages: node outputs are not saved and FILES
  outputs are not materialized; a recipe writes its real results through its own steps.
* **The model** is an `ADAPTER[:MODEL]` string (a dd-llm adapter, as `graf run --llm`), or any object with
  `generate(prompt, model=None, **opts) -> str` and a `name` (a package's own LLM seam, a scripted model in tests). It is
  wrapped in the call meter, so `max_llm_calls` / `max_cost_usd` stop the run; `llm_options` go to the dd-llm adapter
  (`{"timeout": 900}`), `max_tokens` to every call that sets none itself (a GENERATE's own `max_tokens:` wins).
* **Logging** goes through dd-logging only when `log_dir` is given; otherwise GraphLang logs nothing of its own.
* **Errors**: a run that stops early (a limit, a failed node, a refused graph) raises `RecipeError`, which carries the run's
  summary; exception types named in `passthrough` (a package's "backend limit reached", say) are raised as they are.
  A run that ends at an error exit (`output: ..., exit: name`) is not an exception: `RecipeRun.exit` names it.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple, Type


class RecipeError(RuntimeError):
    """The run stopped before an OUTPUT: a limit, a node that failed, a graph the workflow policy refuses. `summary` says what it
    did up to then; `log_path` is the run's log, if one was written."""

    def __init__(self, message: str, summary: Optional[dict] = None, log_path: Optional[Path] = None):
        super().__init__(message)
        self.summary, self.log_path = summary or {}, log_path


@dataclass
class RecipeRun:
    outputs: Dict[str, Any]
    summary: Dict[str, Any] = field(default_factory=dict)
    log_path: Optional[Path] = None

    @property
    def exit(self) -> Optional[str]:
        """The error exit the run ended at (`exit:` of the OUTPUT it reached), or None for a normal end."""
        return self.summary.get("exit")

    @property
    def error_code(self) -> Optional[str]:
        """That exit's code in `workflow.errors` (E_...), or None."""
        return self.summary.get("error_code")

    @property
    def llm_calls(self) -> int:
        return int((self.summary.get("llm") or {}).get("calls") or 0)


def make_run_llm(llm: Any = "mock", *, max_llm_calls: Optional[int] = None, max_cost_usd: Optional[float] = None,
                 llm_options: Optional[Dict[str, Any]] = None, max_tokens: Optional[int] = None,
                 record: Optional[Path] = None, replay: Optional[Path] = None):
    """The run's model, metered: `llm` as in `run_recipe`; `replay` answers from a cassette instead, `record` writes one."""
    from .grafr.adapters import DefaultsLLM, make_llm
    from .grafr.metering import MeteredLLM, RecordingLLM, ReplayLLM
    if replay:
        inner = ReplayLLM(Path(replay))
    elif isinstance(llm, str):
        adapter, _, model = (llm or "mock").partition(":")       # as dd_llm.parse_llm_spec: only the first ':' splits
        if not adapter.strip():
            raise ValueError(f"invalid LLM spec {llm!r}: expected ADAPTER[:MODEL], e.g. claude_cli:claude-haiku-5-5")
        inner = make_llm(adapter.strip(), model.strip() or None, **(llm_options or {}))
    else:
        inner = llm
    if max_tokens:
        inner = DefaultsLLM(inner, max_tokens=int(max_tokens))
    if record:
        inner = RecordingLLM(inner, Path(record))
    return MeteredLLM(inner, max_llm_calls, max_cost_usd)


class Recipe:
    """A recipe loaded once (YAML, schema, parts, the workflow policy), run once per input set."""

    def __init__(self, path: str | Path, *, bindings: Optional[dict] = None, _graph: Optional[dict] = None):
        from .grafr.capabilities import capability_errors
        from .grafr.resolver import ResourceResolver
        from .grafr.runtime import load_graph
        self.path = Path(path)
        if _graph is None:
            if not self.path.is_file():
                raise RecipeError(f"no recipe at {self.path}")
            _graph = load_graph(self.path)
        self.notes: list = []
        if bindings:
            from .grafr.bindings import bind_graph
            _graph, self.notes = bind_graph(copy.deepcopy(_graph), bindings)
        denied = capability_errors(_graph, ResourceResolver(Path(_graph.get("_source_dir", self.path.parent)), _graph.get("resources")))
        if denied:
            raise RecipeError("the workflow policy does not allow this graph: " + "; ".join(denied))
        self._graph = _graph
        self._fingerprint: Optional[str] = None

    @property
    def name(self) -> str:
        return self._graph["workflow"]["name"]

    @property
    def graph(self) -> dict:
        """A copy of the loaded graph (inputs, outputs, resources, nodes), for checks; changing it changes nothing."""
        return copy.deepcopy(self._graph)

    def with_bindings(self, bindings: dict) -> "Recipe":
        """The same recipe with `bindings` applied (another prompt file, a model per node, ...), without loading it again."""
        return Recipe(self.path, bindings=bindings, _graph=self._graph)

    def fingerprint(self, *extra: str | Path) -> str:
        """A hash of every file in the recipe's folder (and of `extra` files): a cache of model replies can be keyed on it."""
        if self._fingerprint is None or extra:
            folder = self.path.parent
            h = hashlib.sha256()
            for f in sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
                h.update(f.relative_to(folder).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
            for f in extra:
                h.update(b"extra\0" + Path(f).read_bytes())
            if extra:
                return h.hexdigest()[:16]
            self._fingerprint = h.hexdigest()[:16]
        return self._fingerprint

    def run(self, inputs: Dict[str, Any], *, llm: Any = "mock", max_llm_calls: Optional[int] = None,
            max_cost_usd: Optional[float] = None, max_steps: int = 1000, workers: int = 1, wall_time_s: Optional[float] = None,
            checkpoint: Optional[Path] = None, resume: Optional[Path] = None, record: Optional[Path] = None,
            replay: Optional[Path] = None, llm_options: Optional[Dict[str, Any]] = None, max_tokens: Optional[int] = None,
            log_dir: Optional[Path] = None, log_level: str = "info", on_node: Optional[Callable[[dict], None]] = None,
            passthrough: Sequence[Type[BaseException]] = ()) -> RecipeRun:
        """Run to the end and return the outputs. `checkpoint` saves the run's state after each top-level step; `resume` continues
        from such a file (same graph only). See the module docstring for `llm`, `log_dir` and errors."""
        from .grafr.metering import CassetteError, LimitExceeded
        from .grafr.runtime import GraphLangRuntime, RunLimitExceeded
        log_path = None
        if log_dir is not None:
            from .logging_config import setup_logging
            spec = llm if isinstance(llm, str) else getattr(llm, "name", "custom")
            adapter, _, model = str(spec).partition(":")
            log_path = setup_logging(self.path.name.removesuffix(".graph.yaml").removesuffix(".yaml"), adapter=adapter, model=model,
                                     log_dir=Path(log_dir), log_level=log_level, log_format="both")
        run_llm = make_run_llm(llm, max_llm_calls=max_llm_calls, max_cost_usd=max_cost_usd, llm_options=llm_options,
                               max_tokens=max_tokens, record=record, replay=replay)
        runtime = GraphLangRuntime(copy.deepcopy(self._graph), llm=run_llm, adapter=run_llm.name, max_steps=max_steps,
                                   wall_time_s=wall_time_s, workers=workers, verbose=False, node_output=None, on_node=on_node)
        if checkpoint or resume:
            runtime.checkpoint_path = Path(checkpoint or resume)
        keep: Tuple[Type[BaseException], ...] = tuple(passthrough)
        try:
            outputs = runtime.resume(Path(resume)) if resume is not None else runtime.execute(inputs)
        except keep:
            raise
        except (ValueError, RuntimeError, NotImplementedError, CassetteError, LimitExceeded, RunLimitExceeded) as e:
            raise RecipeError(str(e), runtime.summary(), log_path) from e
        return RecipeRun(outputs, runtime.summary(), log_path)


def run_recipe(path: str | Path, inputs: Dict[str, Any], *, bindings: Optional[dict] = None, **run_options: Any) -> RecipeRun:
    """Load the recipe at `path` and run it once (`Recipe(path, bindings=...).run(inputs, **run_options)`)."""
    return Recipe(path, bindings=bindings).run(inputs, **run_options)
