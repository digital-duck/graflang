"""Where a run's results go: `<graph folder>/output/<graph>-<adapter>-<timestamp>/`.

    result.json              the workflow outputs (what `graf run` prints as Output)
    <name>.md                one file per text output, e.g. essay.md
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


class RunOutput:
    """One run's output folder; created on first write."""

    def __init__(self, root: Path, stem: str, adapter: str, *, save_nodes: bool = False):
        self.dir = Path(root) / f"{_slug(stem)}-{_slug(adapter)}-{datetime.now():%Y%m%d-%H%M%S}"
        self.save_nodes = save_nodes

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

    def save_result(self, result: Dict[str, Any]) -> List[Path]:
        """Write result.json and one file per output."""
        self.dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for name, value in result.items():
            suffix, text = _render(value)
            path = self.dir / f"{_slug(name)}{suffix}"
            path.write_text(text, encoding="utf-8")
            paths.append(path)
        summary = self.dir / "result.json"
        summary.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        paths.append(summary)
        log_event(_log, "run.output", dir=str(self.dir), files=[p.name for p in paths])
        return paths
