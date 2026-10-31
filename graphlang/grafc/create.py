"""`graf create`: vibe-coding for GraphLang. A specification in plain language goes in; a GraphLang app (a graph, its prompts and a
readme) comes out.

The LLM is asked for the app's files (create_guide.md says how; the examples in create_examples/ are shown to it). What it returns is
checked the way `graf validate` checks a graph, plus a dry run with the mock LLM, and every problem found is sent back with the
previous attempt, for up to `max_rounds` calls. Nothing generated is executed unless `allow_code` is set, and even then a dry run is
skipped when the app has programs: they run when you run the app, not when it is created.
"""
from __future__ import annotations

import json
import posixpath
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..grafr.adapters import MockLLM
from ..grafr.solve_backend import CODE_KEYS
from ..grafr.topology import check
from ..logging_config import get_logger, log_event

_log = get_logger("grafc.create")

HERE = Path(__file__).parent
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
MARK = re.compile(r"^=== FILE: (.+?) ===[ \t]*$", re.M)
FENCE = re.compile(r"\A\s*```[\w+-]*\n([\s\S]*?)\n?```\s*\Z")
EXTENSIONS = {".yaml", ".yml", ".md", ".txt", ".json"}
CODE_EXTENSIONS = {".py"}
MAX_FILES, MAX_BYTES = 30, 300_000
SAFE_TYPES = {"INPUT", "OUTPUT", "GENERATE", "EVALUATE", "ASSERT", "SOLVE", "LOOP"}       # what an app may use without code
CODE_TYPES = SAFE_TYPES | {"RUN"}
SAMPLE = {"TEXT": "sample text", "STRING": "sample text", "INTEGER": 1, "INT": 1, "FLOAT": 1.0, "NUMBER": 1.0, "BOOL": True, "BOOLEAN": True}


class CreateError(RuntimeError):
    """The request cannot be carried out (a bad name, an existing folder, a reply with no files)."""


@dataclass
class Created:
    files: Dict[str, str]
    rounds: int
    problems: List[str]                                     # what is still wrong after the last round (empty when the app checks out)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def check_name(name: str) -> str:
    if not NAME.match(name or ""):
        raise CreateError(f"--name {name!r}: use lower-case letters, digits and underscores, starting with a letter (it names the graph file)")
    return name


def examples_text() -> str:
    """The shipped example apps as `=== FILE ===` blocks (they are validated by the test suite, so they cannot go stale)."""
    blocks = []
    for app in sorted(p for p in (HERE / "create_examples").iterdir() if p.is_dir()):
        for path in sorted(app.rglob("*")):
            if path.is_file():
                blocks.append(f"=== FILE: {path.relative_to(app).as_posix()} ===\n{path.read_text(encoding='utf-8').rstrip()}\n")
        blocks.append("--- end of example app ---\n")
    return "\n".join(blocks)


def build_prompt(name: str, spec: str, allow_code: bool, previous: Optional[Dict[str, str]] = None, problems: Optional[List[str]] = None) -> str:
    guide = (HERE / "create_guide.md").read_text(encoding="utf-8")
    if allow_code:
        guide += (HERE / "create_guide_code.md").read_text(encoding="utf-8")
    parts = [guide, "\n## Example apps (each one is valid; their names are not yours)\n\n" + examples_text(),
             f"\n## Your task\n\nApp name: {name}\nThe graph file is `{name}.graph.yaml` and `workflow.name` is `{name}`.\n\nSpecification:\n{spec.strip()}\n"]
    if previous is not None:
        shown = "\n".join(f"=== FILE: {p} ===\n{t.rstrip()}\n" for p, t in previous.items())
        listed = "\n".join(f"- {p}" for p in (problems or []))
        parts.append(f"\nYour previous attempt:\n\n{shown}\nIt has these problems:\n{listed}\n\nFix every problem and reply with all the files again.\n")
    else:
        parts.append(f"\nReply with the files of the app: `{name}.graph.yaml`, its prompt files and `readme.md`.\n")
    return "\n".join(parts)


def safe_path(path: str) -> str:
    clean = posixpath.normpath(path.strip().replace("\\", "/")).lstrip("/")
    if clean in ("", ".") or clean.startswith(".."):
        raise CreateError(f"the reply names an unsafe path: {path!r}")
    return clean


def parse_files(reply: str) -> Dict[str, str]:
    """The files of a reply: each introduced by `=== FILE: path ===`; a whole-file code fence is removed."""
    marks = list(MARK.finditer(reply or ""))
    if not marks:
        raise CreateError("the reply has no `=== FILE: path ===` lines, so no files could be read from it")
    files: Dict[str, str] = {}
    for i, m in enumerate(marks):
        body = reply[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(reply)].strip("\n")
        fenced = FENCE.match(body)
        files[safe_path(m.group(1))] = (fenced.group(1) if fenced else body).rstrip() + "\n"
    return files


def _nodes(nodes: List[Dict]) -> Any:
    for n in nodes:
        yield n
        body = (n.get("config") or {}).get("subgraph")
        if isinstance(body, dict):
            yield from _nodes(body.get("nodes", []))


def _problems_of_files(name: str, files: Dict[str, str], allow_code: bool) -> List[str]:
    problems = []
    allowed = EXTENSIONS | (CODE_EXTENSIONS if allow_code else set())
    if len(files) > MAX_FILES or sum(len(t) for t in files.values()) > MAX_BYTES:
        problems.append(f"too many or too large files (at most {MAX_FILES} files and {MAX_BYTES // 1000} KB)")
    for path in files:
        if Path(path).suffix.lower() not in allowed:
            problems.append(f"{path}: this kind of file is not allowed" + ("" if allow_code else " (programs need --allow-code)"))
    if f"{name}.graph.yaml" not in files:
        problems.append(f"the file `{name}.graph.yaml` is missing")
    return problems


def _problems_of_graph(name: str, graph: Dict, allow_code: bool) -> List[str]:
    problems = []
    if graph["workflow"].get("name") != name:
        problems.append(f"workflow.name is {graph['workflow'].get('name')!r}, it must be {name!r}")
    types = CODE_TYPES if allow_code else SAFE_TYPES
    for n in _nodes(graph["nodes"]):
        cfg = n.get("config") or {}
        if n["type"] not in types:
            problems.append(f"node {n['id']!r} is a {n['type']}: not allowed in a generated app" + ("" if allow_code or n["type"] != "RUN" else " (needs --allow-code)"))
        if "model" in cfg:
            problems.append(f"node {n['id']!r}: `model` is not a valid key; write `llm: \"adapter:model\"` or leave it out")
        if not allow_code:
            bad = sorted((CODE_KEYS | {"procedure_ref"}) & set(cfg))
            if bad:
                problems.append(f"node {n['id']!r} sets {bad}: that runs code, which needs --allow-code; compute it with GENERATE, EVALUATE or a `solve` expression")
    return problems


def _has_code(graph: Dict) -> bool:
    return any(n["type"] == "RUN" or (CODE_KEYS | {"procedure_ref"}) & set(n.get("config") or {}) for n in _nodes(graph["nodes"]))


def _sample_inputs(graph: Dict) -> Dict[str, Any]:
    return {i["name"]: i["default"] if "default" in i else SAMPLE.get(str(i.get("type", "TEXT")).upper(), "sample text")
            for i in graph["workflow"].get("inputs", [])}


def check_app(name: str, files: Dict[str, str], allow_code: bool = False) -> tuple[List[str], List[str]]:
    """(problems, warnings) of a generated app: its files, its graph as `graf validate` sees it, and a dry run with the mock LLM."""
    from ..grafr.runtime import GraphLangRuntime, load_graph
    problems = _problems_of_files(name, files, allow_code)
    if f"{name}.graph.yaml" not in files:
        return problems, []
    warnings: List[str] = []
    with tempfile.TemporaryDirectory(prefix="graf_create_") as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        try:
            graph = load_graph(root / f"{name}.graph.yaml")
            errors, warns = check(graph)
        except Exception as e:                              # a schema, compact, parts or resource error: the model gets the message
            return problems + [f"{name}.graph.yaml does not load: {type(e).__name__}: {e}"], warnings
        problems += [str(e) for e in errors]
        warnings += [str(w) for w in warns]
        problems += _problems_of_graph(name, graph, allow_code)
        if not problems and not _has_code(graph):
            try:
                out = GraphLangRuntime(graph, llm=MockLLM(), verbose=False, max_steps=300).execute(_sample_inputs(graph))
                if not out:
                    warnings.append("a dry run with the mock LLM reached no OUTPUT (a branch may end without one)")
            except Exception as e:
                problems.append(f"a dry run with the mock LLM failed: {type(e).__name__}: {e}")
    if "readme.md" not in files:
        warnings.append("there is no readme.md (a minimal one is written)")
    return problems, warnings


def create_app(name: str, spec: str, llm, model: Optional[str], *, max_rounds: int = 3, allow_code: bool = False) -> Created:
    """Ask `llm` for the app until it checks out or `max_rounds` calls are used."""
    check_name(name)
    if not (spec or "").strip():
        raise CreateError("the specification is empty")
    files: Dict[str, str] = {}
    problems: List[str] = []
    warnings: List[str] = []
    previous: Optional[Dict[str, str]] = None
    for round_ in range(1, max(1, max_rounds) + 1):
        prompt = build_prompt(name, spec, allow_code, previous, problems if previous is not None else None)
        reply = llm.generate(prompt, model=model)
        log_event(_log, "create.round", round=round_, prompt_chars=len(prompt), reply_chars=len(str(reply)))
        try:
            files = parse_files(str(reply))
        except CreateError as e:
            problems, warnings = [str(e)], []
            previous = previous if previous is not None else {}
            log_event(_log, "create.problems", round=round_, count=1)
            continue
        problems, warnings = check_app(name, files, allow_code)
        log_event(_log, "create.problems", round=round_, count=len(problems))
        if not problems:
            return Created(files, round_, [], warnings)
        previous = files
    return Created(files, max(1, max_rounds), problems, warnings)


def write_app(name: str, spec: str, created: Created, out_dir: Path, llm_spec: str, force: bool = False) -> List[Path]:
    """Write the files (and create.json, what it was made from) into `out_dir`; refuse a folder that already has files unless `force`."""
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        raise CreateError(f"{out_dir} already has files; pick another --out-dir or pass --force to write into it")
    files = dict(created.files)
    if "readme.md" not in files:
        files["readme.md"] = f"# {name}\n\nCreated by `graf create` from this specification:\n\n{spec.strip()}\n\nRun it: `graf run {name}.graph.yaml`\n"
    written = []
    for rel, text in files.items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    meta = out_dir / "create.json"
    meta.write_text(json.dumps({"name": name, "spec": spec, "llm": llm_spec, "rounds": created.rounds, "problems_left": created.problems,
                                "created": datetime.now().isoformat(timespec="seconds")}, indent=2, ensure_ascii=False), encoding="utf-8")
    return written + [meta]
