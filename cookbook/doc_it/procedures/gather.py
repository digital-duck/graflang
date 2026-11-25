"""Reads a codebase into a bounded digest for the writer, and reads the style guide.

stdin   one JSON object:
          source       a folder (absolute, or relative to where `graf run` was started)
          style_guide  the path of a style file (a .md with an optional front matter: format, template, min_sections) or the guide's text
          budget       characters of source to include (default 60000)
          extras       optional, JSON: {"examples": [paths], "transcripts": [paths], "set": [{"style": .., "file": ..}]}
stdout  one line of JSON: {name, root, digest, files, style_guide, format, template, min_sections, extras}
exit    0 when it worked; 1 with the reason on stderr (no such folder, no readable file).

The digest is a file tree and then the files that explain a project, in this order: README, the coding agents' instruction files (CLAUDE.md, AGENTS.md, GEMINI.md, codex.md, QWEN.md, CONVENTIONS.md, .cursorrules, .github/copilot-instructions.md), build manifests,
the CLI SURFACE (every command, argument and option the code declares, with its default and help, from click / typer / argparse
declarations: the ground truth for commands, which a cut entry file loses), docs, changelog, entry points. Each is cut to a share of the
budget; the docs share what is left of it instead of a fixed size. Then, when given (`extras`), sections the user chose, outside the source:
HOUSE STYLE EXAMPLES (documents to match in shape and tone, never a source of facts), TRANSCRIPTS (real output the user captured by running
commands: what a tutorial may show as output) and the DOCUMENT SET (the documents written together, to link rather than repeat). Nothing outside `source` is read (a symlink that leaves it is skipped),
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
AGENT_FILES = ("claude.md", "agents.md", "gemini.md", "codex.md", "qwen.md", "conventions.md", ".cursorrules", ".windsurfrules",     # what each coding agent reads
               ".github/copilot-instructions.md")
MANIFESTS = ["pyproject.toml", "package.json", "Cargo.toml", "go.mod", "setup.py", "setup.cfg", "requirements.txt", "Makefile"]
ENTRY = {"cli.py", "main.py", "__main__.py", "app.py", "index.js", "index.ts", "main.rs", "main.go"}
MAX_FILE = 400_000
MAX_TREE = 300
CLI_SHARE = 0.3                 # at most this part of the budget for the CLI surface
CLI_MARK = re.compile(r"@(\w+\.)*(command|group|option|argument)\b|\badd_(argument|parser|subparsers)\(|\bArgumentParser\(|typer\.(Typer|Option|Argument)\b")
EXTRA_EACH, EXTRA_ALL = 12_000, 40_000
DOCSTRING = ('"' * 3, "'" * 3)


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


def _balanced(lines, k):
    """Lines k.. until the brackets opened on line k are closed (a decorator or call written over several lines)."""
    out, depth = [], 0
    for line in lines[k:k + 40]:
        out.append(line)
        depth += line.count("(") + line.count("[") - line.count(")") - line.count("]")
        if depth <= 0:
            break
    return out


STATEMENT = re.compile(r"^\s*(def|class|return|if|elif|else|for|while|with|try|except|import|from|pass|raise)\b")


def _decorators_above(lines, k):
    """The decorator lines (with their continuation lines) directly above line k: up to a blank line or a statement, at most 40 lines."""
    out = []
    for j in range(k - 1, max(-1, k - 41), -1):
        if not lines[j].strip() or STATEMENT.match(lines[j]):
            break
        out.append(lines[j])
    return out if any(x.lstrip().startswith("@") for x in out) else []


def cli_surface(text: str) -> str:
    """The command-line declarations of a Python file, compactly: each decorator or parser call that declares a command, group, argument or
    option (whole, even over several lines), the `def` it decorates and that function's first docstring line. Empty when there are none."""
    lines, out, k = text.splitlines(), [], 0
    while k < len(lines):
        line = lines[k]
        if CLI_MARK.search(line):
            block = _balanced(lines, k)
            out.extend(b.rstrip() for b in block)
            k += len(block)
            continue
        if re.match(r"\s*(async\s+)?def \w+", line) and any(CLI_MARK.search(d) for d in _decorators_above(lines, k)):
            out.append(line.rstrip())
            doc = lines[k + 1].strip() if k + 1 < len(lines) else ""
            if doc.startswith(DOCSTRING):
                out.append("    " + doc.strip("\"'").strip())
            out.append("")
        k += 1
    return "\n".join(out).strip()


def build(root: Path, budget: int):
    files = [p for p in walk(root) if readable(p, root)]
    rel = lambda p: p.relative_to(root).as_posix()   # noqa: E731
    tree = [rel(p) for p in files][:MAX_TREE]
    parts, used, picked, coverage, surfaces = [], 0, [], {}, []

    def add(path: Path, limit: int):
        nonlocal used
        if rel(path) in picked or used >= budget:
            return
        full = read_text(path, MAX_FILE)
        text = read_text(path, min(limit, budget - used))
        if text.strip():
            parts.append(f"=== FILE {rel(path)} ===\n{text}")
            used += len(text)
            picked.append(rel(path))
            coverage[rel(path)] = [min(len(text), len(full)), len(full)]

    top = {p.name.lower(): p for p in files if p.parent == root}
    for name in sorted(top):
        if name.startswith("readme"):
            add(top[name], 14000)
    byrel = {rel(p).lower(): p for p in files}
    for name in AGENT_FILES + ("contributing.md",):
        if name in byrel:
            add(byrel[name], 7000)
    for name in MANIFESTS:
        if name.lower() in top:
            add(top[name.lower()], 3500)
    cli_used, cli_cap = 0, int(budget * CLI_SHARE)
    pyfiles = sorted((p for p in files if p.suffix == ".py" and "test" not in rel(p).lower()),
                     key=lambda p: (not (p.name in ENTRY or "cli" in p.name), len(p.relative_to(root).parts), rel(p)))
    for p in pyfiles:
        if cli_used >= cli_cap or used >= budget:
            break
        src = read_text(p, MAX_FILE)
        surface = cli_surface(src) if CLI_MARK.search(src) else ""
        if surface:
            surface = surface[: min(cli_cap - cli_used, budget - used)]
            parts.append(f"=== CLI SURFACE {rel(p)} (the code's own declarations of commands and options) ===\n{surface}")
            cli_used += len(surface)
            used += len(surface)
            surfaces.append(rel(p))
    docs = sorted((p for p in files if p.suffix.lower() == ".md" and p.parent != root and rel(p).split("/")[0].lower() in ("docs", "doc", "guide", "documentation")),
                  key=lambda p: (len(p.relative_to(root).parts), rel(p)))[:14]
    for k, p in enumerate(docs):
        left = len(docs) - k + 3                                   # the docs still to come, the changelog and some entry points
        add(p, max(3500, (budget - used) // max(1, left)))
    for name in ("changelog.md", "changes.md", "history.md"):
        if name in top:
            add(top[name], 2500)
    for p in [p for p in files if p.name in ENTRY and len(p.relative_to(root).parts) <= 4][:5]:
        add(p, 3500)
    return tree, "\n\n".join(parts), picked, coverage, surfaces


def extra_sections(extras):
    """The user's own additions, outside the source: house-style examples, transcripts, and the document set. Each file is read only when
    it is a regular text file under 400 KB with no secret-looking name; an HTML example keeps its text, not its styles or scripts.
    Returns (sections, notes on what was skipped)."""
    if isinstance(extras, str):
        extras = json.loads(extras) if extras.strip() else {}
    extras = extras or {}
    out, notes, total = [], [], 0
    labels = (("examples", "HOUSE STYLE EXAMPLE {} (another document to match in structure, headings and tone; NEVER a source of facts about this project)"),
              ("transcripts", "TRANSCRIPT {} (real output, captured by running these commands; besides the sources, the only place to take shown output from)"))
    for key, label in labels:
        for raw in extras.get(key) or []:
            path = Path(str(raw)).expanduser()
            if not path.is_file() or SECRET.search(path.name) or path.stat().st_size > MAX_FILE:
                notes.append(f"skipped {key[:-1]} {raw} (not a readable text file)")
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                notes.append(f"skipped {key[:-1]} {raw} (not UTF-8 text)")
                continue
            if path.suffix.lower() in (".html", ".htm"):
                text = re.sub(r"<(style|script)\b.*?</\1\s*>", "", text, flags=re.S | re.I)
            text = text[: max(0, min(EXTRA_EACH, EXTRA_ALL - total))]
            if not text.strip():
                continue
            out.append(f"=== {label.format(path.name)} ===\n{text}")
            total += len(text)
    if extras.get("set"):
        lines = [f"- {d.get('style')}: {d.get('file')}" for d in extras["set"]]
        out.append("=== DOCUMENT SET (the documents written together in this run; link to the others by these file names instead of repeating "
                   "what they cover) ===\n" + "\n".join(lines))
    return "\n\n".join(out), notes


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
    name = str(job.get("name") or "").strip() or root.name      # a friendlier name than the folder's, for titles and the writer
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
    tree, body, picked, coverage, surfaces = build(root, budget)
    if not picked:
        print(f"gather: found no README, manifest or doc to read in {root}", file=sys.stderr)
        return 1
    digest = f"PROJECT: {name} (folder {root.name})\n\nFILE TREE (first {len(tree)} files):\n" + "\n".join(tree) + "\n\n" + body
    try:
        extra, extra_notes = extra_sections(job.get("extras") or {})
    except ValueError as e:
        print(f"gather: extras is not JSON: {e}", file=sys.stderr)
        return 1
    if extra:
        digest += "\n\n" + extra
    print(json.dumps({"name": name, "root": str(root), "digest": digest, "files": picked, "style_guide": guide.strip(),
                      "format": cfg.get("format", "markdown"), "template": template, "min_sections": int(cfg.get("min_sections", 3)),
                      "extras": extra_notes, "coverage": coverage, "surfaces": surfaces}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
