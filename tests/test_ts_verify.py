"""cookbook/ts_verify: an LLM writes TypeScript, the TypeScript toolchain judges it, the compiler's errors drive the retry.

A scripted model stands in for the LLM (no network). The tools are real: Node runs the generated TypeScript, and tsc
type-checks it when `typescript` is installed in the recipe folder (`npm install` there). Needs Node 22.18+.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from graphlang.grafr.runtime import GraphLangRuntime, load_graph

RECIPE = Path(__file__).resolve().parent.parent / "cookbook" / "ts_verify"
GRAPH = RECIPE / "ts_verify.graph.yaml"


def _node_ok() -> bool:
    node = shutil.which("node")
    if not node:
        return False
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    major, minor = int(version[0]), int(version[1])
    return major >= 24 or (major, minor) >= (23, 6) or (major == 22 and minor >= 18)


pytestmark = pytest.mark.skipif(not _node_ok(), reason="needs Node 22.18+ (it runs TypeScript by stripping the types, and uses --permission)")
needs_tsc = pytest.mark.skipif(not (RECIPE / "node_modules" / "typescript").is_dir(), reason="run `npm install` in cookbook/ts_verify")

SPEC = "slugify(title): lowercase; every run of characters that are not ASCII letters or digits becomes one hyphen; no leading or trailing hyphen"
GOOD = 'export function slugify(title: string): string {\n  return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");\n}'
TYPE_ERROR = 'export function slugify(title: string): number {\n  return title.toLowerCase();\n}'
WRONG = 'export function slugify(title: string): string {\n  return title.toLowerCase().replace(/ /g, "-");\n}'


class Scripted:
    """Plays the model: returns the replies in order (the last one repeats) and keeps every prompt it was sent."""
    name, adapter_name, model_override = "scripted", "echo", None

    def __init__(self, *replies):
        self.replies, self.prompts = replies, []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return self.replies[min(len(self.prompts), len(self.replies)) - 1]


def run(*replies, **inputs):
    llm = Scripted(*replies)
    params = {"spec": SPEC, "function": "slugify", "cases": "examples/slugify.cases.json", **inputs}
    return GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute(params)["result"], llm


@needs_tsc
def test_a_type_error_is_caught_by_the_compiler_and_fed_back_to_the_next_attempt():
    result, llm = run(TYPE_ERROR, GOOD)
    assert result["passed"] is True and result["attempts"] == 2
    assert "None" not in llm.prompts[0]                                          # the first attempt has nothing carried over
    assert "TS2322" in llm.prompts[1] and "title.toLowerCase()" in llm.prompts[1]   # the compiler's error and the old code
    assert "Types:** clean" in result["report"] and "5/5 passed" in result["report"]


def test_without_type_checking_a_wrong_answer_is_caught_by_the_cases():
    result, llm = run(WRONG, GOOD, check_types=False)
    assert result["passed"] is True and result["attempts"] == 2
    assert '"expected":"hello-world"' in llm.prompts[1]                          # the failed case is in the next prompt
    assert "not checked" in result["report"]


@needs_tsc
def test_the_loop_stops_at_max_cycles_and_the_report_says_what_failed():
    result, llm = run(TYPE_ERROR, max_cycles=2)
    assert result["passed"] is False and result["attempts"] == 2 and len(llm.prompts) == 2
    assert "FAILED" in result["report"] and "TS2322" in result["report"]


def test_a_failing_case_is_listed_in_the_report():
    result, _ = run(WRONG, check_types=False, max_cycles=1)
    assert result["passed"] is False
    assert 'f("Hello, World!") expected "hello-world", got "hello,-world!"' in result["report"]


def test_the_code_comes_back_without_the_markdown_fence():
    result, _ = run("Here you go:\n```typescript\n" + GOOD + "\n```\nDone.", check_types=False)
    assert result["passed"] is True and result["code"].startswith("export function slugify") and "```" not in result["code"]


# ---- the tools on their own ----------------------------------------------------------------------------------------

def tool(name, **inputs):
    inputs.setdefault("function", "slugify")
    inputs.setdefault("cases", (RECIPE / "examples" / "slugify.cases.json").read_text(encoding="utf-8"))
    return subprocess.run(["node", str(RECIPE / "tools" / name)], input=json.dumps(inputs), capture_output=True, text=True,
                          cwd=RECIPE, timeout=60)


def test_generated_code_cannot_write_files_or_start_processes(tmp_path):
    target = tmp_path / "pwned.txt"
    evil = (f'import {{ writeFileSync }} from "node:fs";\nexport function slugify(t: string): string {{\n'
            f'  writeFileSync({str(target)!r}, "x");\n  return t;\n}}')
    verdict = json.loads(tool("run_cases.mjs", code=evil).stdout)
    assert not target.exists()
    assert verdict["ok"] is False and all("has been restricted" in f.get("error", "") for f in verdict["failed"])
    spawn = ('import { execSync } from "node:child_process";\nexport function slugify(t: string): string {\n'
             '  return execSync("echo hi").toString();\n}')
    assert all("has been restricted" in f.get("error", "") for f in json.loads(tool("run_cases.mjs", code=spawn).stdout)["failed"])


def test_an_endless_loop_is_killed():
    verdict = json.loads(tool("run_cases.mjs", code="export function slugify(t: string): string { while (true) {} }",
                              timeout_ms=1000).stdout)
    assert verdict["ok"] is False and "timed out" in verdict["error"]


def test_code_that_does_not_export_the_function_is_reported():
    verdict = json.loads(tool("run_cases.mjs", code="export function other(t: string): string { return t; }").stdout)
    assert verdict == {"ok": False, "error": "the module does not export a function named slugify"}


def test_unreadable_test_cases_stop_the_run_with_the_reason():
    run_ = tool("run_cases.mjs", code=GOOD, cases="not json")
    assert run_.returncode == 1 and "cannot read the test cases" in run_.stderr


def test_missing_typescript_fails_closed_instead_of_skipping_the_check(tmp_path):
    shutil.copytree(RECIPE / "tools", tmp_path / "tools")                           # a copy with no node_modules above it
    run_ = subprocess.run(["node", str(tmp_path / "tools" / "typecheck.mjs")], capture_output=True, text=True,
                          input=json.dumps({"code": GOOD, "function": "slugify", "check_types": True}))
    assert run_.returncode == 1 and "typescript is not installed" in run_.stderr and "check_types=false" in run_.stderr


def test_finalize_reports_in_python():
    data = {"code": "```ts\nx\n```", "passed": False, "attempts": ["a", "b"], "case_report": None,
            "type_report": json.dumps({"ok": False, "checked": True, "diagnostics": ["line 1: TS2322: bad"]})}
    out = json.loads(subprocess.run([sys.executable, "-I", str(RECIPE / "tools" / "finalize.py")], input=json.dumps(data),
                                    capture_output=True, text=True).stdout)
    assert out["code"] == "x\n" and out["attempts"] == 2 and "type error, line 1: TS2322: bad" in out["report"]
