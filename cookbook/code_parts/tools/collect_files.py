"""Turn the model's reply into a project folder's files (Python, run by a SOLVE node with backend: subprocess).

stdin   {"text": the reply, "lang": "python", "spec": the specification}
stdout  one line of JSON: {relative path: content, ...}

The reply is a list of files, each introduced by a line `=== FILE: path/to/file.py ===`. A reply with no such line is taken
as the single source file `main.<ext>`. Whole-file code fences are removed, paths are made safe (relative, no `..`), and for
Python every folder that holds .py files gets an `__init__.py`, so the modules can import each other. A README.md is added
from the spec if the reply has none.
"""
import json
import posixpath
import re
import sys

EXT = {"python": "py", "javascript": "js", "typescript": "ts", "go": "go", "rust": "rs", "java": "java", "ruby": "rb", "c": "c", "cpp": "cpp"}
MARK = re.compile(r"^=== FILE: (.+?) ===\s*$", re.M)
FENCE = re.compile(r"\A\s*```[\w+-]*\n([\s\S]*?)\n?```\s*\Z")


def safe(path):
    path = posixpath.normpath(path.strip().replace("\\", "/")).lstrip("/")
    if path in ("", ".") or path.startswith(".."):
        raise ValueError(f"unsafe path in the reply: {path!r}")
    return path


def split(text):
    marks = list(MARK.finditer(text))
    files = {}
    for i, m in enumerate(marks):
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)].strip("\n")
        fenced = FENCE.match(body)
        files[safe(m.group(1))] = (fenced.group(1) if fenced else body).rstrip() + "\n"
    return files


def main():
    data = json.load(sys.stdin)
    text, lang = data.get("text") or "", (data.get("lang") or "python").lower()
    files = split(text)
    if not files:                                          # a single-file reply, no markers
        fenced = FENCE.match(text)
        files = {f"main.{EXT.get(lang, 'txt')}": ((fenced.group(1) if fenced else text).strip() + "\n")}
    if lang == "python":
        for folder in {posixpath.dirname(p) for p in files if p.endswith(".py")} - {""}:
            parts = folder.split("/")
            for n in range(1, len(parts) + 1):
                files.setdefault("/".join(parts[:n]) + "/__init__.py", "")
    if not any(p.lower() == "readme.md" for p in files):
        files["README.md"] = f"# Generated project\n\n## Specification\n\n{(data.get('spec') or '').strip()}\n"
    print(json.dumps(dict(sorted(files.items()))))


if __name__ == "__main__":
    main()
