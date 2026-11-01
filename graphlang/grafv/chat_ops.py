"""Changing a workflow by talking to it: the model answers with a short list of operations, never a rewritten file.

Each operation goes through the same `GraphEditor` methods the buttons use, so a chat edit is validated like any other, keeps the
file's comments, stays unsaved until Save and can be undone. A prompt file (`prompts/*.md`) is not part of the graph file: a change to
one is staged and written together with the graph on Save. If any operation fails, none of them is applied.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .editor import EditError, GraphEditor

PROMPT_FILE = re.compile(r"^prompts/[A-Za-z0-9_.-]+\.(md|txt)$")
FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
OPS = {
    "add_node": ("id", "type", "ports"),
    "remove_node": ("id",),
    "rename_node": ("old", "new"),
    "set_config": ("node", "key", "value"),
    "delete_config": ("node", "key"),
    "set_ports": ("node", "ports"),
    "add_edge": ("source", "target", "type"),
    "remove_edge": ("source", "target", "type"),
    "write_file": ("path", "text"),
}

GUIDE = """You change a GraphLang workflow by listing operations. Reply with JSON only (no explanation outside it):
{"say": "one or two sentences: what you changed, or why you did not", "ops": [ ... ]}

Operations (every field is required unless marked optional):
- {"op": "add_node", "id": "polish", "type": "GENERATE", "ports": ["trigger", "complete", "in_essay", "out_essay"], "config": {"prompt_ref": "prompts.polish"}}   (config optional)
- {"op": "remove_node", "id": "polish"}
- {"op": "rename_node", "old": "a", "new": "b"}
- {"op": "set_config", "node": "draft", "key": "llm", "value": "claude_cli:claude-haiku-5-5"}
- {"op": "delete_config", "node": "draft", "key": "llm"}
- {"op": "set_ports", "node": "draft", "ports": ["trigger", "complete", "in_topic", "out_essay"]}
- {"op": "add_edge", "source": "draft.complete", "target": "polish.trigger", "type": "triggers"}   (type is triggers or binds)
- {"op": "remove_edge", "source": "draft.complete", "target": "polish.trigger", "type": "triggers"}
- {"op": "write_file", "path": "prompts/draft.md", "text": "the whole new prompt text"}   (only files under prompts/)

Rules: a data (binds) edge goes from an `out_...` port to an `in_...` port; a control (triggers) edge ends in a `trigger` port. A prompt
file is used by a node as `prompt_ref: prompts.<file name without .md>`; to change what a node says to the model, write that file.
Make the smallest change that does what was asked. If the request cannot be done with these operations, return "ops": [] and say why.
"""


def build_prompt(graph_yaml: str, prompt_files: Dict[str, str], instruction: str, node_types: List[str]) -> str:
    files = "\n".join(f"--- {p} ---\n{t.rstrip()}" for p, t in prompt_files.items()) or "(none)"
    return (f"{GUIDE}\nNode types: {', '.join(node_types)}\n\nThe workflow now:\n```yaml\n{graph_yaml.rstrip()}\n```\n\n"
            f"Its prompt files:\n{files}\n\nThe request:\n{instruction.strip()}\n")


def parse_reply(reply: str) -> Tuple[str, List[Dict[str, Any]]]:
    """(what the model said, its operations). A reply that is not the JSON asked for raises EditError."""
    text = str(reply).strip()
    fenced = FENCE.search(text)
    candidates = [fenced.group(1).strip()] if fenced else []
    candidates.append(text)
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("ops", []), list):
            return str(data.get("say", "")), data.get("ops", [])
    raise EditError("the model's reply was not the JSON list of operations that was asked for")


def check_op(op: Any) -> Dict[str, Any]:
    if not isinstance(op, dict) or op.get("op") not in OPS:
        raise EditError(f"unknown operation {op!r}")
    missing = [k for k in OPS[op["op"]] if k not in op]
    if missing:
        raise EditError(f"operation {op['op']} needs {', '.join(missing)}")
    return op


def _strs(value: Any, what: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise EditError(f"{what} must be a list of names")
    return value


def apply_ops(editor: GraphEditor, ops: List[Dict[str, Any]], staged: Dict[str, str]) -> List[str]:
    """Apply the operations in order; all or none. File writes go into `staged` (path -> text). Returns one line per operation."""
    undo_mark, staged_before, done = editor.undo_depth, dict(staged), []
    try:
        for raw in ops:
            op = check_op(raw)
            kind = op["op"]
            if kind == "add_node":
                config = op.get("config")
                if config is not None and not isinstance(config, dict):
                    raise EditError("config must be a mapping")
                editor.add_node(str(op["id"]), str(op["type"]), _strs(op["ports"], "ports"), config)
                done.append(f"added node {op['id']}")
            elif kind == "remove_node":
                editor.remove_node(str(op["id"]))
                done.append(f"removed node {op['id']}")
            elif kind == "rename_node":
                editor.rename_node(str(op["old"]), str(op["new"]))
                done.append(f"renamed {op['old']} to {op['new']}")
            elif kind == "set_config":
                editor.set_config(str(op["node"]), str(op["key"]), op["value"])
                done.append(f"set {op['node']}.{op['key']}")
            elif kind == "delete_config":
                editor.delete_config(str(op["node"]), str(op["key"]))
                done.append(f"deleted {op['node']}.{op['key']}")
            elif kind == "set_ports":
                editor.set_ports(str(op["node"]), _strs(op["ports"], "ports"))
                done.append(f"changed the ports of {op['node']}")
            elif kind == "add_edge":
                editor.add_edge(str(op["source"]), str(op["target"]), str(op["type"]))
                done.append(f"added {op['type']} edge {op['source']} -> {op['target']}")
            elif kind == "remove_edge":
                editor.remove_edge(str(op["source"]), str(op["target"]), str(op["type"]))
                done.append(f"removed {op['type']} edge {op['source']} -> {op['target']}")
            else:                                                             # write_file
                path = str(op["path"]).replace("\\", "/")
                if not PROMPT_FILE.match(path):
                    raise EditError(f"a file may only be written under prompts/ (got {path!r})")
                staged[path] = str(op["text"])
                done.append(f"changed {path}")
    except EditError:
        while editor.undo_depth > undo_mark:
            editor.undo()
        staged.clear()
        staged.update(staged_before)
        raise
    return done


def prompt_files(folder: Path, staged: Dict[str, str]) -> Dict[str, str]:
    """The prompt files beside the graph (with staged changes laid over them), small ones only."""
    found: Dict[str, str] = {}
    for path in sorted((Path(folder) / "prompts").glob("*")) if (Path(folder) / "prompts").is_dir() else []:
        rel = f"prompts/{path.name}"
        if PROMPT_FILE.match(rel) and path.stat().st_size < 20_000:
            found[rel] = path.read_text(encoding="utf-8")
    found.update(staged)
    return found


def write_staged(folder: Path, staged: Dict[str, str]) -> List[Path]:
    """Write the staged prompt files (after the graph itself has been saved). Returns the paths written."""
    written = []
    for rel, text in staged.items():
        if not PROMPT_FILE.match(rel):
            raise EditError(f"refusing to write {rel!r}")
        target = Path(folder) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written
