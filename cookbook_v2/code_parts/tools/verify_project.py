"""Check a generated project by running it (Python, run by a SOLVE node with backend: subprocess).

stdin   {"files": {relative path: text}, "lang": "python", "smoke": "optional Python code run against the real dependencies"}
stdout  one line of JSON: {"passed": bool, "report": Markdown that starts with [PASSED] or [FAILED]}

For Python projects it writes the files to a temporary folder and checks, in order:
  1. syntax        every .py file compiles
  2. imports       every module imports (a missing third-party package is skipped, not a failure)
  3. tests         the project's own tests (pytest if installed, else unittest)
  4. smoke         the optional `smoke` code, run in the folder with the project importable (this is where a call to a real library
                   happens; a model's tests usually fake it, so a wrong call passes the tests and fails here)
Other languages are not checked: the report says so and passes.

This RUNS the generated code on this machine, with a timeout but no sandbox. Use a `container:` on the SOLVE node to confine it.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TAIL = 1800


def tail(text, n=TAIL):
    text = (text or "").strip()
    return text if len(text) <= n else "..." + text[-n:]


def run(args, cwd, timeout, env_extra=None):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(env_extra or {})}
    try:
        done = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return done.returncode, (done.stdout or "") + (done.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout} seconds"


def module_name(path):
    parts = Path(path).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def check_python(files, smoke, root):
    steps, failed = [], False

    def step(name, ok, detail=""):
        nonlocal failed
        failed = failed or not ok
        steps.append(f"- **{name}:** {'ok' if ok else 'FAILED'}" + (f"\n\n```\n{tail(detail)}\n```" if detail and not ok else (f" ({detail})" if detail else "")))

    sources = sorted(p for p in files if p.endswith(".py"))
    errors = []
    for p in sources:
        try:
            compile(files[p], p, "exec")
        except SyntaxError as e:
            errors.append(f"{p}:{e.lineno}: {e.msg}")
    step("syntax", not errors, "\n".join(errors) if errors else f"{len(sources)} files")
    if errors:
        return steps, True

    project_tops = {module_name(p).split(".")[0] for p in sources}
    skip = ("conftest", "setup", "__main__")
    bad, skipped, tried = [], [], 0
    for p in sources:
        mod = module_name(p)
        if not mod or mod.split(".")[-1] in skip or mod.split(".")[0] in ("tests", "test") or Path(p).name.startswith("test_"):
            continue
        tried += 1
        code, out = run([sys.executable, "-c", f"import importlib, sys; sys.path.insert(0, {str(root)!r}); importlib.import_module({mod!r})"], root, 60)
        if code:
            last = out.strip().splitlines()[-1] if out.strip() else ""
            if last.startswith("ModuleNotFoundError") and "'" in last and last.split("'")[1].split(".")[0] not in project_tops:
                skipped.append(last.split("'")[1])
            else:
                bad.append(f"import {mod}\n{tail(out, 900)}")
    note = f"{tried} modules" + (f"; not installed here, skipped: {', '.join(sorted(set(skipped)))}" if skipped else "")
    step("imports", not bad, "\n\n".join(bad) if bad else note)

    if any(Path(p).name.startswith("test_") or Path(p).name.endswith("_test.py") for p in sources):
        have_pytest = run([sys.executable, "-c", "import pytest"], root, 30)[0] == 0
        args = [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"] if have_pytest else \
               [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]
        code, out = run(args, root, 180, {"PYTHONPATH": str(root)})
        step("tests", code in (0, 5), out if code not in (0, 5) else (out.strip().splitlines() or [""])[-1])
    else:
        step("tests", True, "none written")

    if (smoke or "").strip():
        code, out = run([sys.executable, "-c", smoke], root, 180, {"PYTHONPATH": str(root)})
        step("smoke", code == 0, out if code else "ran without error")
    return steps, failed


def main():
    data = json.load(sys.stdin)
    files, lang, smoke = data.get("files") or {}, (data.get("lang") or "python").lower(), data.get("smoke") or ""
    if lang != "python":
        print(json.dumps({"passed": True, "report": f"[PASSED]\n\nNot checked: verification only runs Python projects (lang={lang})."}))
        return
    with tempfile.TemporaryDirectory(prefix="code_parts_") as tmp:
        root = Path(tmp)
        for rel, text in files.items():
            target = (root / rel).resolve()
            if root.resolve() not in target.parents:
                print(json.dumps({"passed": False, "report": f"[FAILED]\n\nunsafe path {rel!r}"}))
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        steps, failed = check_python(files, smoke, root)
    print(json.dumps({"passed": not failed, "report": ("[FAILED]" if failed else "[PASSED]") + "\n\n## Verification\n\n" + "\n".join(steps)}))


if __name__ == "__main__":
    main()
