"""Past runs for the Logs tab: the folders `graf run` (and the editor's Run tab) leave in `<graph folder>/output/`, read back
into the same shape `GraphEditor.run` returns, so one page shows a fresh run and an old one alike."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def run_folders(graph_path: Path) -> List[Path]:
    """The run folders beside a graph (they hold a run.json), newest first."""
    root = Path(graph_path).resolve().parent / "output"
    if not root.is_dir():
        return []
    stem = Path(graph_path).name.removesuffix(".graph.yaml").removesuffix(".yaml")
    found = [d for d in root.iterdir() if d.is_dir() and (d / "run.json").is_file() and d.name.startswith(stem + "-")]
    return sorted(found, key=lambda d: d.name.rsplit("-", 2)[-2:], reverse=True)        # the name ends in -YYYYMMDD-HHMMSS


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_run(folder: Path) -> Dict[str, Any]:
    """{ok, error, inputs, outputs, summary, values, meta} of a saved run; what a file lacks is left empty."""
    folder = Path(folder)
    meta = _json(folder / "run.json") or {}
    values: Dict[str, Dict[str, Any]] = {}
    nodes = folder / "nodes"
    for path in sorted(nodes.iterdir()) if nodes.is_dir() else []:
        step, _, rest = path.name.partition("-")
        if not step.isdigit():
            continue
        stem, _, suffix = rest.rpartition(".")
        node, _, port = stem.rpartition(".")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        values.setdefault(node, {})[port] = json.loads(text) if suffix == "json" and _valid(text) else text
    error = meta.get("error")
    return {"ok": not error, "error": error, "inputs": meta.get("params") or {}, "outputs": _json(folder / "result.json"),
            "summary": _json(folder / "summary.json"), "values": values, "meta": meta}


def _valid(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


def label(folder: Path) -> str:
    """One line for a picker: when, which model, how it went."""
    meta = _json(Path(folder) / "run.json") or {}
    summary = _json(Path(folder) / "summary.json") or {}
    when = str(meta.get("started", folder.name)).replace("T", " ")
    model = ":".join(x for x in (meta.get("adapter"), meta.get("model")) if x)
    calls = (summary.get("llm") or {}).get("calls")
    state = "failed" if meta.get("error") else (f"{calls} calls" if calls is not None else "")
    return " · ".join(x for x in (when, model, state) if x)
