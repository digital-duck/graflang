"""The work area behind `graf vis --edit`: where recipes live, how they are copied, imported and exported, and the LLM settings.

A pip-installed graflang has no repository to point at, so its work area is `~/.graflang/` (or `$GRAFLANG_HOME`):

    ~/.graflang/cookbook/   the shipped recipes (copied here; treated as read-only: editing one first copies it to apps/)
    ~/.graflang/solvers/    the solver recipes ported from SPL.py (also read-only; editing one first copies it to apps/)
    ~/.graflang/pocketflow/ the PocketFlow recipes ported from SPL.py (also read-only; editing one first copies it to apps/)
    ~/.graflang/apps/       your own apps: created, cloned or imported ones
    ~/.graflang/settings.json   provider, model and API keys (readable by you only)

`graf vis --edit --src-dir DIR` works on DIR instead of cookbook/, solvers/, pocketflow/ and apps/: then DIR is the only root and it is writable.
Nothing here overwrites: a name that is taken is an error, and the caller picks another.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, List, MutableMapping, Optional, Tuple

import yaml

GRAPH_SUFFIX = ".graph.yaml"
SKIP_DIRS = {"output", "outputs", "__pycache__", "node_modules"}
MAX_ZIP_FILES, MAX_ZIP_BYTES = 2000, 50_000_000
CODE_KEYS = ("code", "command", "container")
CODE_BACKENDS = ("kernel", "subprocess")


class WorkspaceError(ValueError):
    """A request the work area refuses (a taken name, an unsafe archive); the message says why."""


def home() -> Path:
    return Path(os.environ.get("GRAFLANG_HOME") or Path.home() / ".graflang")


def default_src_dir() -> Path:
    return home() / "cookbook"


def apps_dir() -> Path:
    return home() / "apps"


def solvers_dir() -> Path:
    return home() / "solvers"


def pocketflow_dir() -> Path:
    return home() / "pocketflow"


def images_dir() -> Path:
    return home() / "images"


def save_capture(name: str, pdf_b64: str) -> Path:
    """Write a picture the canvas sent (a base64 PDF) to ~/.graflang/images/<name>-<time>.pdf and return the path. Refuses anything that is
    not a PDF or is over 25 MB; the name is reduced to letters, digits, `_` and `-`."""
    import base64
    import re
    import time
    if len(pdf_b64) > 34_000_000:
        raise WorkspaceError("the picture is too large to save")
    try:
        data = base64.b64decode(pdf_b64, validate=True)
    except ValueError:
        raise WorkspaceError("the picture is not valid base64") from None
    if not data.startswith(b"%PDF-"):
        raise WorkspaceError("the picture is not a PDF")
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).removesuffix(".pdf"))[:60].strip("_") or "graph"
    folder = images_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stem}-{time.strftime('%Y%m%d-%H%M%S')}.pdf"
    n = 1
    while path.exists():
        n += 1
        path = folder / f"{stem}-{time.strftime('%Y%m%d-%H%M%S')}-{n}.pdf"
    path.write_bytes(data)
    return path


def settings_path() -> Path:
    return home() / "settings.json"


# ── roots and recipes ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Root:
    name: str
    path: Path
    writable: bool


@dataclass(frozen=True)
class Recipe:
    root: str
    folder: Path
    graph: Path
    writable: bool

    @property
    def label(self) -> str:
        return f"{self.root}/{self.folder.name}/{self.graph.name.removesuffix(GRAPH_SUFFIX)}"


@dataclass(frozen=True)
class Workspace:
    src_dir: Optional[Path] = None              # an explicit --src-dir; None means the default cookbook/ + apps/ pair

    @property
    def roots(self) -> List[Root]:
        if self.src_dir is not None:
            return [Root("src", self.src_dir, True)]
        return [Root("apps", apps_dir(), True), Root("cookbook", default_src_dir(), False), Root("solvers", solvers_dir(), False),
                Root("pocketflow", pocketflow_dir(), False)]

    @property
    def write_root(self) -> Path:
        return self.roots[0].path

    def recipes(self) -> List[Recipe]:
        """Every `*.graph.yaml` that sits in a folder directly under a root (a graph beside its prompts and procedures)."""
        found: List[Recipe] = []
        for root in self.roots:
            if not root.path.is_dir():
                continue
            for folder in sorted(p for p in root.path.iterdir() if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith(".")):
                for graph in sorted(folder.glob(f"*{GRAPH_SUFFIX}")):
                    found.append(Recipe(root.name, folder, graph, root.writable))
        return found

    def recipe_folder(self, path: Path) -> Path:
        """The recipe a graph file belongs to: the folder directly under a root that holds it (so a graph in a sub-folder, a part for
        example, still belongs to its recipe). A file outside every root belongs to the highest folder above it that holds a graph file."""
        path = Path(path).resolve()
        for root in self.roots:
            try:
                parts = path.relative_to(root.path.resolve()).parts
            except ValueError:
                continue
            if len(parts) > 1:
                return root.path.resolve() / parts[0]
        folder = path.parent                                  # outside every root: climb while the folder above also holds a graph
        for _ in range(3):
            if folder.parent != folder and any(folder.parent.glob(f"*{GRAPH_SUFFIX}")):
                folder = folder.parent
        return folder

    def is_shipped(self, path: Path) -> bool:
        """Is the file inside a read-only root (the cookbook)? A file outside every root, opened by its path, is the user's own."""
        return any(not r.writable and _inside(Path(path), r.path) for r in self.roots)

    def writable_for(self, path: Path) -> bool:
        """May the file be edited in place? Only inside a writable root."""
        path = Path(path).resolve()
        return any(r.writable and _inside(path, r.path) for r in self.roots)


def graphs_in(folder: Path, max_depth: int = 4) -> List[Path]:
    """Every `*.graph.yaml` in a recipe folder and its sub-folders (parts, sub-graphs), the top ones first. Run output is skipped."""
    folder = Path(folder)
    found: List[Path] = []
    for path in folder.rglob(f"*{GRAPH_SUFFIX}"):
        rel = path.relative_to(folder)
        if len(rel.parts) <= max_depth and not any(p in SKIP_DIRS or p.startswith(".") for p in rel.parts[:-1]):
            found.append(path)
    return sorted(found, key=lambda p: (len(p.relative_to(folder).parts), p.relative_to(folder).as_posix()))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


# ── copying, importing, exporting ────────────────────────────────────────────────────────────────

def check_folder_name(name: str) -> str:
    name = (name or "").strip()
    if not name or Path(name).name != name or name.startswith(".") or name in SKIP_DIRS:
        raise WorkspaceError(f"{name!r} is not a usable folder name (a plain name, not starting with a dot)")
    return name


def free_name(root: Path, name: str) -> str:
    """`name`, or `name-2`, `name-3` ... the first one not taken in `root`."""
    candidate, n = name, 2
    while (root / candidate).exists():
        candidate, n = f"{name}-{n}", n + 1
    return candidate


def _ignore(_directory, names):
    return [n for n in names if n in SKIP_DIRS or n.startswith(".") or n.endswith(".pyc")]


def clone_recipe(folder: Path, dest_root: Path, name: Optional[str] = None) -> Path:
    """Copy a whole recipe folder (graph, prompts, procedures) into `dest_root`; never overwrites. Returns the new folder."""
    folder = Path(folder)
    name = check_folder_name(name or folder.name)
    target = Path(dest_root) / name
    if target.exists():
        raise WorkspaceError(f"{target} already exists: pick another name (nothing was overwritten)")
    Path(dest_root).mkdir(parents=True, exist_ok=True)
    shutil.copytree(folder, target, ignore=_ignore)
    return target


def install_cookbook(source: Path, dest: Path) -> Tuple[List[str], List[str]]:
    """Copy each recipe folder of `source` that `dest` does not have yet. Returns (copied, skipped because already there)."""
    source, dest = Path(source), Path(dest)
    if not source.is_dir():
        raise WorkspaceError(f"{source} is not a folder")
    copied, skipped = [], []
    for folder in sorted(p for p in source.iterdir() if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith(".")):
        if not any(folder.glob(f"*{GRAPH_SUFFIX}")):
            continue
        if (dest / folder.name).exists():
            skipped.append(folder.name)
        else:
            clone_recipe(folder, dest)
            copied.append(folder.name)
    if not copied and not skipped:
        raise WorkspaceError(f"{source} holds no recipe (a folder with a *{GRAPH_SUFFIX} file)")
    return copied, skipped


def export_zip(folder: Path) -> bytes:
    """The recipe folder as a zip (graph, prompts, procedures; not run output, caches or hidden files)."""
    folder = Path(folder)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob("*")):
            rel = path.relative_to(folder)
            if path.is_dir() or any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts) or path.suffix == ".pyc":
                continue
            z.write(path, (Path(folder.name) / rel).as_posix())
    return buf.getvalue()


def _safe_members(z: zipfile.ZipFile) -> List[zipfile.ZipInfo]:
    members = [m for m in z.infolist() if not m.is_dir()]
    if len(members) > MAX_ZIP_FILES or sum(m.file_size for m in members) > MAX_ZIP_BYTES:
        raise WorkspaceError(f"the archive is too large (more than {MAX_ZIP_FILES} files or {MAX_ZIP_BYTES // 1_000_000} MB)")
    for m in members:
        p = PurePosixPath(m.filename.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts or stat.S_ISLNK(m.external_attr >> 16) or (p.parts and p.parts[0].endswith(":")):
            raise WorkspaceError(f"the archive holds an unsafe path: {m.filename!r}")
    return members


def import_zip(data: bytes, dest_root: Path, name: Optional[str] = None) -> List[Path]:
    """Unpack an exported recipe, or a whole cookbook, into `dest_root`. Never overwrites, never writes outside `dest_root`.

    A zip with a graph at its top level is one recipe (named `name`, else after the graph); otherwise each top-level folder that
    holds a graph is a recipe. Returns the new folders. Nothing from the archive is run."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise WorkspaceError("that is not a zip file")
    with z, tempfile.TemporaryDirectory() as tmp:
        members = _safe_members(z)
        root = Path(tmp)
        for m in members:
            target = root / m.filename.replace("\\", "/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(m))
        top_graphs = sorted(root.glob(f"*{GRAPH_SUFFIX}"))
        if top_graphs:
            wanted = check_folder_name(name or top_graphs[0].name.removesuffix(GRAPH_SUFFIX))
            return [_move_in(root, Path(dest_root) / wanted)]
        folders = [p for p in sorted(root.iterdir()) if p.is_dir() and any(p.glob(f"*{GRAPH_SUFFIX}"))]
        if not folders:
            raise WorkspaceError(f"the archive holds no recipe (a folder with a *{GRAPH_SUFFIX} file)")
        taken = [f.name for f in folders if (Path(dest_root) / f.name).exists()]
        if taken:
            raise WorkspaceError(f"already in your apps: {', '.join(taken)}; nothing was imported (rename or remove them first)")
        return [_move_in(f, Path(dest_root) / check_folder_name(f.name)) for f in folders]


def _move_in(src: Path, target: Path) -> Path:
    if target.exists():
        raise WorkspaceError(f"{target} already exists: pick another name (nothing was overwritten)")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target, ignore=_ignore)
    return target


def import_graph_file(text: str, filename: str, dest_root: Path, name: Optional[str] = None) -> Path:
    """A lone `*.graph.yaml` (its prompts are not with it): checked as YAML, then written to a new folder of its own."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise WorkspaceError(f"not valid YAML: {e}")
    if not isinstance(doc, dict) or "workflow" not in doc and "steps" not in doc:
        raise WorkspaceError("that does not look like a GraphLang workflow (needs `workflow:`)")
    stem = filename.removesuffix(GRAPH_SUFFIX).removesuffix(".yaml")
    folder = Path(dest_root) / check_folder_name(name or stem)
    if folder.exists():
        raise WorkspaceError(f"{folder} already exists: pick another name (nothing was overwritten)")
    folder.mkdir(parents=True)
    path = folder / f"{stem}{GRAPH_SUFFIX}"
    path.write_text(text, encoding="utf-8")
    return path


def runs_program(node: dict) -> bool:
    """A node that runs a program: `RUN`, a SOLVE with a kernel or subprocess backend, or any node with code, a command or a container."""
    cfg = node.get("config") or {}
    return node.get("type") == "RUN" or cfg.get("backend") in CODE_BACKENDS or any(k in cfg for k in CODE_KEYS)


def program_nodes(graph: dict) -> List[str]:
    """One line for each node of a loaded graph that would run a program when the graph runs."""
    return [f"node {n.get('id')} ({n.get('type')})" for n in graph.get("nodes", []) if isinstance(n, dict) and runs_program(n)]


def scan_for_code(folder: Path) -> List[str]:
    """What in a recipe would run programs: nodes with code or a command, `RUN` nodes, and any .py files. Imported recipes are not trusted."""
    notes: List[str] = []
    folder = Path(folder)
    for graph in sorted(folder.glob(f"*{GRAPH_SUFFIX}")):
        try:
            doc = yaml.safe_load(graph.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            notes.append(f"{graph.name}: not readable as YAML")
            continue
        for node in doc.get("nodes", []) if isinstance(doc, dict) else []:
            if runs_program(node):
                notes.append(f"{graph.name}: node {node.get('id')} runs a program ({node.get('type')})")
        if isinstance(doc, dict) and any(isinstance(s, dict) and any(k in s for k in CODE_KEYS) for s in doc.get("steps", [])):
            notes.append(f"{graph.name}: a step runs a program")
    notes += [f"{p.relative_to(folder).as_posix()}: a Python file" for p in sorted(folder.rglob("*.py")) if "__pycache__" not in p.parts]
    return notes


SECRET = re.compile(r"sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:api[_-]?key|secret|token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}")


def find_secrets(folder: Path) -> List[str]:
    """Files in a recipe that look like they hold a key or a token: check them before you share the recipe."""
    hits = []
    for path in sorted(Path(folder).rglob("*")):
        rel = path.relative_to(folder)
        if not path.is_file() or any(p in SKIP_DIRS or p.startswith(".") for p in rel.parts) or path.stat().st_size > 1_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if SECRET.search(text):
            hits.append(rel.as_posix())
    return hits


def find_repo_cookbook() -> Optional[Path]:
    """The `cookbook/` of a source checkout, when graflang was installed with `pip install -e`; None for a normal install."""
    candidate = Path(__file__).resolve().parent.parent / "cookbook"
    return candidate if candidate.is_dir() else None


# ── LLM settings ─────────────────────────────────────────────────────────────────────────────────

# the environment variables each provider (a dd-llm adapter) reads; claude_cli and gemini_cli use their own CLI login
PROVIDER_VARS: Dict[str, List[str]] = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "gemini": ["GEMINI_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "azure_openai": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    "momagrid": ["MOMAGRID_API_KEY", "MOMAGRID_HUB_URL"],
    "ollama": ["OLLAMA_HOST"],
    "claude_cli": [],
    "gemini_cli": [],
}
MODEL_HINTS: Dict[str, List[str]] = {
    "claude_cli": ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"],
    "anthropic": ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5"],
    "ollama": ["gemma3", "gemma4"],
}
DEFAULT_CANVAS = 800
DEFAULT_SETTINGS = {"provider": "claude_cli", "model": "", "keys": {}, "canvas_height": DEFAULT_CANVAS, "embedding": "auto"}


def is_secret(var: str) -> bool:
    return "KEY" in var.upper() or "TOKEN" in var.upper()


def providers() -> List[str]:
    """The providers to choose from: dd-llm's adapters when it is importable, else the ones this module knows."""
    try:
        from dd_llm.registry import list_adapters
        names = list(list_adapters())
    except Exception:
        names = []
    return sorted(set(names) | set(PROVIDER_VARS)) if names else sorted(PROVIDER_VARS)


def load_settings(path: Optional[Path] = None) -> dict:
    path = Path(path) if path else settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**DEFAULT_SETTINGS, **{k: v for k, v in data.items() if k in DEFAULT_SETTINGS}, "keys": dict(data.get("keys") or {})} if isinstance(data, dict) else dict(DEFAULT_SETTINGS)


def save_settings(settings: dict, path: Optional[Path] = None) -> Path:
    """Write the settings readable by the owner only (the file holds API keys), replacing the old file only when the new one is complete."""
    path = Path(path) if path else settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {"provider": str(settings.get("provider") or "claude_cli"), "model": str(settings.get("model") or ""),
             "keys": {k: v for k, v in (settings.get("keys") or {}).items() if v},
             "canvas_height": _height(settings.get("canvas_height")), "embedding": str(settings.get("embedding") or "auto").strip()}
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".settings.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def _height(value) -> int:
    try:
        return min(1600, max(400, int(value)))
    except (TypeError, ValueError):
        return DEFAULT_CANVAS


def apply_settings(settings: dict, env: Optional[MutableMapping[str, str]] = None) -> List[str]:
    """Put the saved keys into the environment so every call this process makes finds them. A variable already set in the real
    environment wins and is left alone. Returns the names that were set."""
    target: MutableMapping[str, str] = os.environ if env is None else env
    applied = []
    for var, value in (settings.get("keys") or {}).items():
        if value and not target.get(var):
            target[var] = value
            applied.append(var)
    return applied


def llm_spec(settings: dict) -> str:
    provider, model = settings.get("provider") or "claude_cli", settings.get("model") or ""
    return f"{provider}:{model}" if model else provider


def mask(value: str) -> str:
    """A key for display: the last four characters only."""
    return "" if not value else ("•" * 8 + value[-4:] if len(value) > 8 else "•" * len(value))


def long_form_in_place(path: Path) -> Path:
    """Rewrite a compact `steps:` file of your own as its long `nodes:`/`edges:` form, same name (comments are not kept)."""
    from .grafr.compact import expand, is_compact
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not is_compact(doc):
        raise WorkspaceError(f"{path.name} is not in the compact `steps:` form")
    from .yamlfmt import dump_readable
    path.write_text(dump_readable(expand(doc)), encoding="utf-8")
    return path


def long_form_copy(path: Path) -> Path:
    """The editor takes the long `nodes:`/`edges:` form. For a compact `steps:` file, write that form beside it as
    `<name>.long.graph.yaml` (comments are not kept: they belong to the short file, which stays as it is) and return it."""
    from .grafr.compact import expand, is_compact
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not is_compact(doc):
        raise WorkspaceError(f"{path.name} is not in the compact `steps:` form")
    target = path.with_name(path.name.removesuffix(GRAPH_SUFFIX) + ".long" + GRAPH_SUFFIX)
    if target.exists():
        return target
    from .yamlfmt import dump_readable
    target.write_text(dump_readable(expand(doc)), encoding="utf-8")
    return target
