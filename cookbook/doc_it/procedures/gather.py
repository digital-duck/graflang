"""Reads a codebase into a bounded digest for the writer, and reads the style guide.

stdin   one JSON object:
          source       a folder (absolute, or relative to where `graf run` was started)
          style_guide  the path of a style file (a .md with an optional front matter: format, template, min_sections) or the guide's text
          budget       characters of source to include (default 60000)
stdout  one line of JSON: {name, root, digest, files, style_guide, format, template, min_sections}
exit    0 when it worked; 1 with the reason on stderr (no such folder, no readable file).

The digest is a file tree and then the files that explain a project, in this order: README, CLAUDE.md / AGENTS.md, build manifests,
docs, changelog, entry points. Each is cut to a share of the budget. Nothing outside `source` is read (a symlink that leaves it is skipped),
binary and very large files are skipped, and no secret-looking file (.env, keys) is read.
"""
import json
import os
import re
import sys
from pathlib import Path

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "output", "outputs", ".claude", ".idea", ".mypy_cache",
               ".pytest_cache", ".tox", "target", ".next", "site-packages", ".egg-info"}
SECRET = re.compile(r"(^\.env|secret|credential|\.pem$|\.key$|id_rsa|\.p12$|token)", re.I)
TEXT_EXT = {".md", ".txt", ".rst", ".toml", ".yaml", ".yml", ".json", ".py", ".js", ".ts", ".rs", ".go", ".sh", ".cfg", ".ini", ".html"}
MANIFESTS = ["pyproject.toml", "package.json", "Cargo.toml", "go.mod", "setup.py", "setup.cfg", "requirements.txt", "Makefile"]
ENTRY = {"cli.py", "main.py", "__main__.py", "app.py", "index.js", "index.ts", "main.rs", "main.go"}
MAX_FILE = 400_000
MAX_TREE = 300


def parse(stdout: str):
    """The graph's parser: the whole JSON object."""
    return json.loads(stdout)


def front_matter(text: str):
    """(settings, body) of a style file; settings are `key: value` lines between two `---` lines."""
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return {}, text
    cfg = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        if k.strip():
            cfg[k.strip()] = v.strip()
    return cfg, text[m.end():]


def readable(path: Path, root: Path) -> bool:
    try:
        real = path.resolve()
        real.relative_to(root)
    except (OSError, ValueError):
        return False                      # a symlink out of the folder
    return path.is_file() and not SECRET.search(path.name) and path.stat().st_size <= MAX_FILE and path.suffix.lower() in TEXT_EXT | {""}


def read_text(path: Path, limit: int) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text if len(text) <= limit else text[:limit] + f"\n[... cut: {len(text) - limit} more characters ...]"


def walk(root: Path):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS and not d.endswith(".egg-info"))
        for f in sorted(files):
            yield Path(dirpath) / f


def build(root: Path, budget: int):
    files = [p for p in walk(root) if readable(p, root)]
    rel = lambda p: p.relative_to(root).as_posix()   # noqa: E731
    tree = [rel(p) for p in files][:MAX_TREE]
    parts, used, picked = [], 0, []

    def add(path: Path, limit: int):
        nonlocal used
        if rel(path) in picked or used >= budget:
            return
        text = read_text(path, min(limit, budget - used))
        if text.strip():
            parts.append(f"=== FILE {rel(path)} ===\n{text}")
            used += len(text)
            picked.append(rel(path))

    top = {p.name.lower(): p for p in files if p.parent == root}
    for name in sorted(top):
        if name.startswith("readme"):
            add(top[name], 14000)
    for name in ("claude.md", "agents.md", "contributing.md"):
        if name in top:
            add(top[name], 7000)
    for name in MANIFESTS:
        if name.lower() in top:
            add(top[name.lower()], 3500)
    docs = sorted((p for p in files if p.suffix.lower() == ".md" and p.parent != root and rel(p).split("/")[0].lower() in ("docs", "doc", "guide", "documentation")),
                  key=lambda p: (len(p.relative_to(root).parts), rel(p)))
    for p in docs[:14]:
        add(p, 3500)
    for name in ("changelog.md", "changes.md", "history.md"):
        if name in top:
            add(top[name], 2500)
    for p in [p for p in files if p.name in ENTRY and len(p.relative_to(root).parts) <= 4][:5]:
        add(p, 3500)
    return tree, "\n\n".join(parts), picked


def main() -> int:
    try:
        job = json.load(sys.stdin)
    except ValueError as e:
        print(f"gather: stdin is not JSON: {e}", file=sys.stderr)
        return 1
    root = Path(str(job.get("source", ""))).expanduser()
    if not root.is_dir():
        print(f"gather: no such folder {str(root)!r} (give a folder, or use `graf docs` for a repository url)", file=sys.stderr)
        return 1
    root = root.resolve()
    budget = int(job.get("budget") or 60000)
    guide_in = str(job.get("style_guide", ""))
    guide_path = Path(guide_in).expanduser() if "\n" not in guide_in and len(guide_in) < 1024 else None
    if guide_path is not None and guide_path.is_file():
        text, base = guide_path.read_text(encoding="utf-8"), guide_path.resolve().parent
    else:
        text, base = guide_in, Path.cwd()
    if not text.strip():
        print("gather: the style guide is empty (give a style file or its text)", file=sys.stderr)
        return 1
    cfg, guide = front_matter(text)
    template = cfg.get("template", "")
    if template:
        tpath = (base / template).resolve()
        if not tpath.is_file():
            print(f"gather: the style's template {template!r} is not beside the style file", file=sys.stderr)
            return 1
        template = str(tpath)
    tree, body, picked = build(root, budget)
    if not picked:
        print(f"gather: found no README, manifest or doc to read in {root}", file=sys.stderr)
        return 1
    digest = f"PROJECT FOLDER: {root.name}\n\nFILE TREE (first {len(tree)} files):\n" + "\n".join(tree) + "\n\n" + body
    print(json.dumps({"name": root.name, "root": str(root), "digest": digest, "files": picked, "style_guide": guide.strip(),
                      "format": cfg.get("format", "markdown"), "template": template, "min_sections": int(cfg.get("min_sections", 3))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
