"""Where a run's results go: `<graph folder>/output/<graph>-<adapter>[-<model>]-<timestamp>/`
(the model part is the one asked for with --llm/--model, named the same way as the log files).

    run.json                 what produced it: graph, adapter, model, parameters, start time
    result.json              the workflow outputs (what `graf run` prints as Output)
    <name>.md                one file per text output, e.g. essay.md
    <name>/...               an output declared `type: FILES` (a mapping of relative path to text) as a real folder of files
    nodes/003-draft.out_essay.md    with --save-nodes: every node's output ports, numbered by firing order

LLM text lives here, not in the log (see logging_config.py): the log records that a node produced N chars and,
for saved nodes, the file it went to.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..logging_config import get_logger, log_event

_log = get_logger("grafr.output")


def _slug(text: str) -> str:
    return re.sub(r"[^\w.-]+", "_", str(text)).strip("_") or "x"


def _render(value: Any) -> tuple[str, str]:
    """(suffix, text) for a value: text as .md, anything else as pretty JSON."""
    if isinstance(value, str):
        return ".md", value
    return ".json", json.dumps(value, indent=2, ensure_ascii=False, default=str)


class FilesError(ValueError):
    """An output declared FILES is not a mapping of safe relative paths to text."""


def _tree(name: str, value: Any) -> Dict[str, str]:
    """The files of a FILES output, checked: relative paths that stay inside the folder, text contents."""
    if not isinstance(value, dict) or not value:
        raise FilesError(f"output {name!r} is declared FILES: expected a non-empty mapping of path to text, got {type(value).__name__}")
    files = {}
    for rel, text in value.items():
        path = Path(str(rel))
        if not str(rel).strip() or path.is_absolute() or ".." in path.parts or "\\" in str(rel):
            raise FilesError(f"output {name!r}: {rel!r} is not a relative path inside the folder")
        if not isinstance(text, str):
            raise FilesError(f"output {name!r}: the content of {rel!r} must be text, got {type(text).__name__}")
        files[path.as_posix()] = text
    return files


class RunOutput:
    """One run's output folder; created on first write."""

    def __init__(self, root: Path, stem: str, adapter: str, *, model: str = "", params: Dict[str, Any] | None = None,
                 save_nodes: bool = False):
        now = datetime.now()
        parts = [_slug(stem), _slug(adapter)] + ([re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-")] if model else [])
        self.dir = Path(root) / f"{'-'.join(parts)}-{now:%Y%m%d-%H%M%S}"
        self.save_nodes = save_nodes
        self.meta = {"graph": stem, "adapter": adapter, "model": model or None, "params": params or {},
                     "started": now.isoformat(timespec="seconds")}

    def save_node(self, step: int, node: str, result: Dict[str, Any]) -> List[Path]:
        """Write each non-control output port of a node that fired (no-op unless --save-nodes)."""
        if not self.save_nodes:
            return []
        paths = []
        for port, value in result.items():
            if port.startswith("_"):
                continue
            suffix, text = _render(value)
            path = self.dir / "nodes" / f"{step:03d}-{_slug(node)}.{_slug(port)}{suffix}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            paths.append(path)
            log_event(_log, "node.saved", node=node, port=port, file=str(path), chars=len(text))
        return paths

    def observe(self, step: int, node: str, label: str, values: Dict[str, Any]) -> None:
        """Append one OBSERVE record to observations.jsonl in the run's folder."""
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / "observations.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"step": step, "node": node, "label": label, "values": values}, ensure_ascii=False, default=str) + "\n")

    def save_error(self, message: str) -> Path:
        """run.json with the reason a run failed, so the run shows up in a history of runs."""
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / "run.json"
        path.write_text(json.dumps({**self.meta, "error": message}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return path

    def save_summary(self, summary: Dict[str, Any]) -> Path:
        """summary.json: steps, per-node time, LLM calls, tokens and cost."""
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / "summary.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return path

    def save_result(self, result: Dict[str, Any], trees: frozenset | set = frozenset()) -> List[Path]:
        """Write result.json and one file per output; an output named in `trees` (declared FILES) becomes a folder of files."""
        self.dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for name, value in result.items():
            if name in trees:
                for rel, text in _tree(name, value).items():
                    path = self.dir / _slug(name) / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
                    paths.append(path)
                continue
            suffix, text = _render(value)
            path = self.dir / f"{_slug(name)}{suffix}"
            path.write_text(text, encoding="utf-8")
            paths.append(path)
        run_json = self.dir / "run.json"
        run_json.write_text(json.dumps(self.meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        summary = self.dir / "result.json"
        summary.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        paths += [summary, run_json]
        log_event(_log, "run.output", dir=str(self.dir), files=[p.name for p in paths])
        return paths
