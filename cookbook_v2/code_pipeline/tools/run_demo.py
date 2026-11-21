"""Run the plan's demo on the built project and report what came out (Python, run by a SOLVE node, in the verify container: no network).

stdin   {"files": {path: text} the project, "plan": the build plan (JSON text), "timeout": seconds (optional)}
stdout  one line of JSON: {"ok": bool, "returncode", "command", "stdout", "stderr", "outputs": {path: text}, "missing": [paths], "error": text}

The demo is the plan's `demo`: {"description", "files": {sample input}, "command": [argv], "env": {...}, "outputs": [files or folders to read afterwards]}. The project and the
sample files are written to a temporary folder, the command runs there (a leading "python" is this interpreter), and the declared outputs are read back, shortened.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TAIL, FILE_CHARS, MAX_FILES, TOTAL = 2500, 8000, 6, 30000


def parse(text):
    if isinstance(text, dict):
        return text
    text = (text or "").strip()
    try:
        return json.loads(text)
    except ValueError:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        return json.loads(fenced.group(1).strip()) if fenced else json.loads(text[text.find("{"):text.rfind("}") + 1])


def tail(text, n=TAIL):
    text = (text or "").strip()
    return text if len(text) <= n else "..." + text[-n:]


def shorten(text):
    return text if len(text) <= FILE_CHARS else text[:FILE_CHARS - 2000] + "\n...[shortened]...\n" + text[-2000:]


def inside(root, rel):
    target = (root / rel).resolve()
    return target if root.resolve() in target.parents or target == root.resolve() else None


def main():
    data = json.load(sys.stdin)
    files, timeout = data.get("files") or {}, min(float(data.get("timeout") or 120), 300)
    try:
        demo = parse(data.get("plan")).get("demo")
    except (ValueError, AttributeError):
        demo = None
    if not isinstance(demo, dict) or not demo.get("command"):
        print(json.dumps({"ok": False, "error": "the plan has no demo command", "outputs": {}, "missing": []}))
        return
    with tempfile.TemporaryDirectory(prefix="demo_") as tmp:
        root = Path(tmp)
        for rel, text in {**files, **(demo.get("files") or {})}.items():
            target = inside(root, rel)
            if target is None:
                print(json.dumps({"ok": False, "error": f"unsafe path {rel!r}", "outputs": {}, "missing": []}))
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        argv = [sys.executable if i == 0 and str(c) == "python" else str(c) for i, c in enumerate(demo["command"])]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(root), "HOME": str(root), **{str(k): str(v) for k, v in (demo.get("env") or {}).items()}}
        try:
            done = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout, env=env)
            code, out, err = done.returncode, done.stdout, done.stderr
        except subprocess.TimeoutExpired:
            code, out, err = 124, "", f"timed out after {timeout:.0f} seconds"
        outputs, missing, used = {}, [], 0
        for rel in demo.get("outputs") or []:
            target = inside(root, rel)
            if target is None or not target.exists():
                missing.append(rel)
                continue
            found = sorted(p for p in target.rglob("*") if p.is_file())[:MAX_FILES] if target.is_dir() else [target]
            for p in found:
                if used >= TOTAL:
                    break
                try:
                    text = shorten(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue
                outputs[p.relative_to(root).as_posix()] = text
                used += len(text)
    ok = code == 0 and not missing
    print(json.dumps({"ok": ok, "returncode": code, "command": argv[1:] if argv and argv[0] == sys.executable else argv, "stdout": tail(out), "stderr": tail(err),
                      "outputs": outputs, "missing": missing}))


if __name__ == "__main__":
    main()
