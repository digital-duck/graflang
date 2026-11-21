"""cookbook_v2: recipes ported to the layered form (docs/DEV/DESIGN/graflang-recipes.md). Each one must validate with no errors or warnings, and
behave like the original in cookbook/ (same outputs, same steps run), checked offline with the echo and mock adapters."""
from pathlib import Path

import pytest

import importlib.util

needs_spl = pytest.mark.skipif(importlib.util.find_spec("spl") is None, reason="procedure_ref nodes (the code_pipeline_spl port) need SPL.py importable")

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "cookbook_v2"
GRAPHS = sorted(d / f"{d.name}.graph.yaml" for d in V2.iterdir() if d.is_dir())          # the top graph of each recipe; its composites are checked as part of it (a composite that holds a risky node cannot stand alone: the guard is in the graph that uses it)


@pytest.mark.parametrize("path", GRAPHS, ids=lambda p: str(p.relative_to(V2)))
def test_every_v2_graph_validates_with_no_errors_and_no_warnings(path):
    assert check(load_graph(path)) == ([], [])


# ---- code_pipeline ---------------------------------------------------------------------------------------------------------------

ORIGINAL = ROOT / "cookbook" / "code_pipeline" / "code_pipeline.graph.yaml"
LAYERED = V2 / "code_pipeline_spl" / "code_pipeline_spl.graph.yaml"
# the steps of the original and the node each became in the layered one (ids are `<composite>__<step>`)
SAME_STEPS = {"analyze": "understand__analyze", "spec_gate": "understand__clear", "document": "finish__document", "extract": "finish__extract",
              "closure_gate": "finish__closure", "judge": "finish__judge", "merge_docs": "finish__merge"}
LOOP_STEPS = {"loop_gen": "generate", "loop_rev": "review", "loop_imp": "improve", "loop_test": "test", "loop_eval": "ok", "loop_guard": "retry"}


def run(path, adapter, params, cwd, monkeypatch):
    monkeypatch.chdir(cwd)                                  # the procedures write their logs under the current folder
    rt = GraphLangRuntime(load_graph(path), llm=make_llm(adapter), verbose=False)
    return rt, rt.execute(params)


@needs_spl
@pytest.mark.parametrize("params", [{"spec": "add two numbers", "max_cycles": 2, "check_closure": True},
                                    {"spec": "add two numbers", "max_cycles": 1, "check_closure": False}], ids=["with-closure-check", "without"])
def test_the_layered_pipeline_gives_the_same_output_and_runs_the_same_steps(params, tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    old, out_old = run(ORIGINAL, "echo", params, a, monkeypatch)
    new, out_new = run(LAYERED, "echo", params, b, monkeypatch)
    assert out_new == out_old and "docs" in out_new
    for before, after in SAME_STEPS.items():
        assert new.fired.get(after, 0) == old.fired.get(before, 0), (before, after)
    assert new.loop_iterations["build__attempts"] == old.loop_iterations["test_gated_loop"]


@needs_spl
def test_a_vague_spec_stops_the_run_in_both_and_the_layered_one_names_the_cause(tmp_path, monkeypatch):
    """The mock adapter's analysis has no [READY]: the gate fails. The original aborts through its RECOVER node; the layered one leaves the
    `understand` composite by its `vague` error exit, which carries the code E_SPEC_VAGUE and its catalogue text."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    old, out_old = run(ORIGINAL, "mock", {"spec": "do things"}, a, monkeypatch)
    new, out_new = run(LAYERED, "mock", {"spec": "do things"}, b, monkeypatch)
    assert out_new == out_old and not out_new.get("docs")
    assert old.fired.get("test_gated_loop", 0) == 0 and new.loop_iterations.get("build__attempts", 0) == 0     # neither started building
    (exit_info,) = [x for x in load_graph(LAYERED)["_error_exits"] if x["code"] == "E_SPEC_VAGUE"]
    assert exit_info["use"] == "understand" and "too vague" in exit_info["description"] and exit_info["remedy"]


@needs_spl
def test_the_layered_pipeline_reads_as_three_composites():
    from graphlang.grafv.model import build
    top, _ = build(load_graph(LAYERED), 0)
    names = {n for n in top.nodes}
    assert {"understand", "build", "finish"} <= names and top.number_of_nodes() <= 8          # the top level is a handful of nodes
    assert len(load_graph(LAYERED)["nodes"]) == len(load_graph(ORIGINAL)["nodes"])             # opened, the same graph (the loop body sits inside the loop node)


# ---- the other ports: each runs next to its original, in two copies of the folders, with the same scripted model ---------------------
# The model answers by the number of the call (the two runs make their calls in the same order), so a retry, a revision or an escalation
# is exercised, not only the happy path. Outputs must be equal.
import json
import os
import shutil


class Scripted:
    """An LLM that answers call number N with script[N] (1-based) and otherwise with 'text N'."""

    name = "scripted"
    adapter_name = "echo"                       # a procedure_ref step (SPL) builds its own model from the adapter's name: the echo one

    def __init__(self, script):
        self.script, self.calls = script, 0

    def generate(self, prompt, model=None, **opts):
        self.calls += 1
        return self.script.get(self.calls, f"text {self.calls}")


def copy_recipe(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("output", ".graf", "logs", "__pycache__", ".grafr", "node_modules"))
    modules = ROOT / "cookbook" / src.name / "node_modules"        # the ports share the original's npm install
    if modules.is_dir():
        (dst / "node_modules").symlink_to(modules)
    return dst / f"{src.name}.graph.yaml"


def both(name, params, script, tmp_path, monkeypatch):
    """Run the original and the port in their own copies; return (old output, new output, old llm calls, new llm calls)."""
    results = []
    for who, root in (("old", ROOT / "cookbook"), ("new", V2)):
        graph = copy_recipe(root / name, tmp_path / who / name)
        monkeypatch.chdir(graph.parent)
        llm = Scripted(script)
        out = GraphLangRuntime(load_graph(graph), llm=llm, verbose=False).execute(dict(params))
        results.append((out, llm.calls))
    (old, n_old), (new, n_new) = results
    return old, new, n_old, n_new


SSN = json.dumps({"entities": [{"type": "SSN", "masked": False}]})
NONE = json.dumps({"entities": []})
GOOD = json.dumps({"name": "Maria", "email": "m@x.org"})
BAD = json.dumps({"name": "", "email": ""})

SCRIPTED = {
    # id: (recipe, params, script)
    "supervisor-retries-then-approved": ("supervisor", {"question": "why", "max_rounds": 3}, {2: "REVISE it", 4: "APPROVED"}),
    "supervisor-never-approved": ("supervisor", {"question": "why", "max_rounds": 2}, {}),
    "self_heal-heals": ("self_heal", {"text": "Maria m@x.org"}, {1: BAD, 2: GOOD}),
    "self_heal-gives-up": ("self_heal", {"text": "nothing", "max_rounds": 2}, {1: BAD, 2: BAD, 3: BAD}),
    "agent_notes-reads-then-answers": ("agent_notes", {"question": "price?", "max_steps": 3},
                                       {1: json.dumps({"action": "read", "file": "pricing.md"}), 2: json.dumps({"action": "answer", "text": "39 per user"})}),
    "agent_notes-never-answers": ("agent_notes", {"question": "price?", "max_steps": 2}, {1: json.dumps({"action": "read", "file": "contacts.md"})}),
    "your_book-one-revision": ("your_book", {"subject": "tides", "audience": "intro", "num_chapters": 2}, {3: "REVISION_NEEDED", 6: "fine"}),
    "compliance_audit-released-after-redaction": ("compliance_audit", {"document": "SSN 123-45-6789", "destination": "external_api", "engine": "stdlib"}, {1: SSN, 3: NONE}),
    "compliance_audit-escalated": ("compliance_audit", {"document": "SSN 123-45-6789", "destination": "external_api", "engine": "stdlib"}, {1: SSN, 3: SSN}),
    "compliance_audit-clean-first-time": ("compliance_audit", {"document": "hello", "destination": "internal", "engine": "stdlib"}, {1: NONE}),
    "stock_copy": ("stock_copy", {"tickers": "AAPL,MSFT", "days": 5}, {}),
    "notes_digest": ("notes_digest", {}, {}),
    "chat_memory": ("chat_memory", {"message": "hi, I am Wen"}, {}),
}


@pytest.mark.parametrize("case", sorted(SCRIPTED))
def test_each_port_gives_the_same_output_and_uses_the_same_number_of_model_calls(case, tmp_path, monkeypatch):
    name, params, script = SCRIPTED[case]
    old, new, n_old, n_new = both(name, params, script, tmp_path, monkeypatch)
    assert new == old, (old, new)
    assert n_new == n_old


def test_heartbeat_remembers_the_count_between_beats_like_the_original(tmp_path, monkeypatch):
    """Three beats against a growing inbox, with a model that writes (the echo adapter: the mock only reports what it would write)."""
    runs = {}
    for who, root in (("old", ROOT / "cookbook"), ("new", V2)):
        graph = copy_recipe(root / "heartbeat", tmp_path / who / "heartbeat")
        monkeypatch.chdir(graph.parent)
        outs = []
        for beat in (1, 2, 3):
            if beat == 3:
                with open(graph.parent / "input" / "inbox.md", "a", encoding="utf-8") as f:
                    f.write("one more message\n")
            outs.append(GraphLangRuntime(load_graph(graph), llm=make_llm("echo"), verbose=False).execute({}))
        runs[who] = outs
    assert runs["new"] == runs["old"]
    assert runs["new"][1]["status"].startswith("nothing new") and runs["new"][2]["status"].startswith("new:")


def test_ts_verify_repairs_a_wrong_function_like_the_original(tmp_path, monkeypatch):
    """The model's first try is wrong; the type checker and the cases judge it; the second try passes. Needs node and the typescript package."""
    import shutil as sh
    if not sh.which("node") or not (ROOT / "cookbook" / "ts_verify" / "node_modules" / "typescript").is_dir():
        pytest.skip("needs Node and `npm install` in cookbook/ts_verify")
    wrong = "export function slugify(title: string): string { return title.toLowerCase(); }"
    right = ("export function slugify(title: string): string {\n  return title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');\n}")
    params = {"spec": "slugify(title)", "function": "slugify", "cases": "examples/slugify.cases.json", "max_cycles": 2}
    # the cases include a non-ASCII one the simple code gets wrong too: only the equality of the two runs is asserted
    old, new, n_old, n_new = both("ts_verify", params, {1: wrong, 2: right}, tmp_path, monkeypatch)
    assert new == old and n_new == n_old


def test_the_ports_have_fewer_top_level_steps_than_their_originals_have_nodes():
    """The point of the layering: the top graph is a handful of boxes."""
    for name in ("code_gen", "code_pipeline", "code_pipeline_spl", "compliance_audit", "your_book", "agent_notes", "supervisor", "self_heal", "heartbeat", "stock_copy", "ts_verify", "notes_digest", "chat_memory"):
        top = [n for n in load_graph(V2 / name / f"{name}.graph.yaml", levels=0)["nodes"] if n["type"] != "INPUT"]
        assert len(top) <= 10, (name, len(top))


# ---- code_gen and the repository-capable code_pipeline ---------------------------------------------------------------------------

def reply(*files):
    return "\n".join(f"=== FILE: {path} ===\n{text}" for path, text in files)


APP = ("README.md", "# demo\n")
CORE_BAD = ("demo/core.py", "def add(a, b):\n    return a + b + 1\n")
CORE_OK = ("demo/core.py", "def add(a, b):\n    return a + b\n")
TEST = ("tests/test_core.py", "import unittest\nfrom demo.core import add\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n")


DOCKER_STUB = '''#!{python}
import json, subprocess, sys
args = sys.argv[1:]
if args[0] == "info":
    print("Ubuntu 22.04"); sys.exit(0)
if args[:2] == ["rm", "-f"]:
    sys.exit(0)
i = args.index("graflang-verify:py3.12")
mount = next(a for a in args if a.endswith(":/work:ro")).split(":/work")[0]
open({log!r}, "a").write(json.dumps({{"flags": " ".join(args[:i]), "command": args[i + 1:]}}) + "\\n")
command = [{python!r} if c == "python" else c for c in args[i + 1:]]
sys.exit(subprocess.run(command, stdin=sys.stdin, cwd=mount).returncode)        # runs the program here, in the mounted folder, as the container would
'''


@pytest.fixture
def docker(tmp_path, monkeypatch):
    """A stub `docker` on PATH (no daemon needed): it logs how it was asked to run the program and runs it locally. Returns a function giving the log."""
    import json as _json
    import stat
    import sys
    from graphlang.grafr.solver import _docker_desktop
    bin_dir, log = tmp_path / "bin", tmp_path / "docker.log"
    bin_dir.mkdir()
    stub = bin_dir / "docker"
    stub.write_text(DOCKER_STUB.format(python=sys.executable, log=str(log)))
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    _docker_desktop.cache_clear()
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return lambda: [_json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def run_new(name, params, script, tmp_path, monkeypatch):
    graph = copy_recipe(V2 / name, tmp_path / name)
    monkeypatch.chdir(graph.parent)
    llm = Scripted(script)
    rt = GraphLangRuntime(load_graph(graph), llm=llm, verbose=False)
    return rt, rt.execute(dict(params)), llm


def test_code_gen_splits_the_reply_into_a_project_with_modules_and_a_readme(tmp_path, monkeypatch):
    rt, out, llm = run_new("code_gen", {"spec": "add numbers"}, {1: reply(("backend/app.py", "print(1)\n"), ("frontend/index.html", "<p>hi</p>\n"))}, tmp_path, monkeypatch)
    assert llm.calls == 1 and set(out["code"]) == {"backend/app.py", "backend/__init__.py", "frontend/index.html", "README.md"}      # a README is added from the spec


DELIVERABLES = [{"name": "a demo", "mechanism": "plain functions", "quality_bar": "the answers are right"}]


DEMO = {"description": "shouts a word and writes it to out/x.txt", "files": {"sample/word.txt": "hi"}, "env": {"DEMO_LLM": "offline"}, "outputs": ["out"],
        "command": ["python", "-c", "import pathlib; from demo.cli import shout; pathlib.Path('out').mkdir(); pathlib.Path('out/x.txt').write_text(shout('hi'))"]}


def plan(*tasks, ready=True, deliverables=DELIVERABLES, demo=DEMO):
    doc = {"ready": ready, "summary": "a demo package", "assumptions": [], "deliverables": deliverables, "tasks": list(tasks)}
    if demo is not None:
        doc["demo"] = demo
    return json.dumps(doc)


def task(tid, files, deps=(), description="Implement the module: its public functions with their signatures and behaviour."):
    return {"id": tid, "title": f"task {tid}", "description": description, "files": list(files), "depends_on": list(deps), "acceptance": "its tests pass"}


T1 = task("t1", ["demo/core.py", "tests/test_core.py"])
T2 = task("t2", ["demo/cli.py", "tests/test_cli.py"], ["t1"])
GOOD_PLAN = plan(T1, T2)
THIN_PLAN = plan({"id": "t1", "title": "everything", "description": "do it", "files": ["demo.py"]})          # no acceptance, too thin, no test file
CLI_TEST = ("tests/test_cli.py", "import unittest\nfrom demo.cli import shout\n\nclass T(unittest.TestCase):\n    def test_shout(self):\n        self.assertEqual(shout('a'), 'A!')\n")
CLI_BAD = ("demo/cli.py", "def shout(s):\n    return s.upper()\n")
CLI_OK = ("demo/cli.py", "from demo.core import add\n\ndef shout(s):\n    return s.upper() + '!'\n")
PARAMS = {"spec": "add numbers and shout", "check_closure": False}


def test_the_plan_heals_itself_and_the_project_is_built_task_by_task(docker, tmp_path, monkeypatch):
    script = {1: THIN_PLAN,                                   # draft 1: the checker refuses it, and says why
              2: GOOD_PLAN,                                   # draft 2 (told what was wrong): passes the checker
              3: "[REVISE]\n1. the plan drops the model: add a writer task",       # ... but the reviewer finds it does not deliver the spec
              4: GOOD_PLAN,                                   # draft 3 (told what the reviewer said)
              5: "[APPROVED]",
              6: reply(CORE_OK, TEST),                        # task 1
              7: reply(CLI_BAD, CLI_TEST),                    # task 2: its test fails
              8: reply(CLI_OK),                               # the fix pass
              9: "[ACCEPTED]"}                                # the demo's output is judged good
    prompts = []
    llm_cls = Scripted

    class Recording(llm_cls):
        def generate(self, prompt, model=None, **opts):
            prompts.append(prompt)
            return super().generate(prompt, model, **opts)

    graph = copy_recipe(V2 / "code_pipeline", tmp_path / "cp")
    monkeypatch.chdir(graph.parent)
    llm = Recording(script)
    rt = GraphLangRuntime(load_graph(graph), llm=llm, verbose=False)
    out = rt.execute(dict(PARAMS))
    assert rt.loop_iterations["analyze__planning"] == 3 and rt.loop_iterations["build__tasks"] == 2
    assert "not good enough yet" in prompts[1] and "`acceptance` is missing" in prompts[1]               # the checker's complaints reached the second draft
    assert "a demanding technical reviewer" in prompts[2] and "a demo package" in prompts[2]              # the reviewer saw the plan that passed the checker
    assert "the plan drops the model" in prompts[3]                                                      # and what it said reached the third draft
    assert "Task t1 of 2" in prompts[5] and "(nothing written yet)" in prompts[5]                          # task 1 sees its own task, no files yet
    assert "Task t2 of 2" in prompts[6] and "=== FILE: demo/core.py ===" in prompts[6]                     # task 2 sees what task 1 wrote
    assert "FAILED" in prompts[7] and "Task t2" in prompts[7] and "=== FILE: demo/cli.py ===" in prompts[7]     # the fix pass sees the failure and the project
    assert out["report"].lstrip().startswith("[PASSED]") and llm.calls == 10 and out["appraisal"].startswith("[ACCEPTED]")
    assert "a demanding reviewer of a finished software product" in prompts[8] and '"out/x.txt": "HI!"' in prompts[8]       # the judge saw what the demo really wrote
    assert set(out["code"]) >= {"demo/core.py", "demo/cli.py", "demo/__init__.py", "tests/test_core.py", "tests/test_cli.py", "tests/__init__.py", "README.md"}
    assert out["code"]["demo/cli.py"] == CLI_OK[1] and json.loads(out["plan"])["tasks"][1]["id"] == "t2" and out["docs"]


def test_a_plan_that_never_gets_good_ends_in_the_vague_exit_without_building(docker, tmp_path, monkeypatch):
    rt, out, llm = run_new("code_pipeline", {**PARAMS, "max_plan_rounds": 2}, {1: THIN_PLAN, 2: THIN_PLAN}, tmp_path, monkeypatch)
    assert llm.calls == 2 and rt.loop_iterations["analyze__planning"] == 2 and not out.get("code") and "build__tasks" not in rt.loop_iterations
    assert any(x["code"] == "E_PLAN_VAGUE" and x["use"] == "analyze" for x in load_graph(V2 / "code_pipeline" / "code_pipeline.graph.yaml")["_error_exits"])


def test_a_reviewer_who_never_approves_does_not_stop_the_run(docker, tmp_path, monkeypatch):
    """Out of plan rounds with the reviewer still unhappy: the last draft passed the checker, so it is used and the objections are reported."""
    script = {1: GOOD_PLAN, 2: "[REVISE]\n1. first objection", 3: GOOD_PLAN, 4: "[REVISE]\n1. still not happy",
              5: reply(CORE_OK, TEST), 6: reply(CLI_OK, CLI_TEST), 7: "[ACCEPTED]"}
    rt, out, llm = run_new("code_pipeline", {**PARAMS, "max_plan_rounds": 2}, script, tmp_path, monkeypatch)
    assert rt.loop_iterations["analyze__planning"] == 2 and rt.loop_iterations["build__tasks"] == 2          # built anyway
    assert out["plan_review"].startswith("[REVISE]") and "still not happy" in out["plan_review"] and out["report"].lstrip().startswith("[PASSED]")


def test_an_approving_reviewer_is_reported_as_approved(docker, tmp_path, monkeypatch):
    rt, out, llm = run_new("code_pipeline", PARAMS, {1: GOOD_PLAN, 2: "[APPROVED]\nnote: fine", 3: reply(CORE_OK, TEST), 4: reply(CLI_OK, CLI_TEST), 5: "[ACCEPTED]"}, tmp_path, monkeypatch)
    assert out["plan_review"].startswith("[APPROVED]")


def test_a_planner_that_says_not_ready_is_asked_again(docker, tmp_path, monkeypatch):
    rt, out, llm = run_new("code_pipeline", PARAMS, {1: plan(T1, ready=False), 2: GOOD_PLAN, 3: "[APPROVED]", 4: reply(CORE_OK, TEST), 5: reply(CLI_OK, CLI_TEST), 6: "[ACCEPTED]"}, tmp_path, monkeypatch)
    assert rt.loop_iterations["analyze__planning"] == 2 and out["report"].lstrip().startswith("[PASSED]")


def test_a_task_the_fix_cannot_repair_goes_on_and_the_report_says_failed(docker, tmp_path, monkeypatch):
    script = {1: GOOD_PLAN, 2: "[APPROVED]", 3: reply(CORE_OK, TEST), 4: reply(CLI_BAD, CLI_TEST), 5: reply(CLI_BAD), 6: "[ACCEPTED]"}
    rt, out, llm = run_new("code_pipeline", PARAMS, script, tmp_path, monkeypatch)
    assert llm.calls == 7 and out["report"].lstrip().startswith("[FAILED]") and "demo/cli.py" in out["code"]


def test_a_reply_without_file_markers_goes_into_the_tasks_first_file(docker, tmp_path, monkeypatch):
    one = plan(task("t1", ["demo/core.py", "tests/test_core.py"]))
    rt, out, llm = run_new("code_pipeline", PARAMS, {1: one, 2: "[APPROVED]", 3: "def add(a, b):\n    return a + b\n", 4: "[ACCEPTED]"}, tmp_path, monkeypatch)
    assert out["code"]["demo/core.py"] == "def add(a, b):\n    return a + b\n"


def test_every_verify_runs_in_a_locked_down_container_and_the_preflight_comes_first(docker, tmp_path, monkeypatch):
    run_new("code_pipeline", PARAMS, {1: GOOD_PLAN, 2: "[APPROVED]", 3: reply(CORE_OK, TEST), 4: reply(CLI_BAD, CLI_TEST), 5: reply(CLI_OK), 6: "[ACCEPTED]"}, tmp_path, monkeypatch)
    runs = docker()
    assert [r["command"][1] for r in runs] == ["tools/verify_project.py"] * 4 + ["tools/run_demo.py"], runs     # preflight, task 1, task 2, the fixed task 2, the demo
    for run in runs:
        for flag in ("--network none", "--read-only", "--cap-drop ALL", "--memory 1024m", "--cpus 2", "--pids-limit 256"):
            assert flag in run["flags"], (flag, run["flags"])


def test_a_rejected_product_is_reworked_and_judged_again(docker, tmp_path, monkeypatch):
    script = {1: GOOD_PLAN, 2: "[APPROVED]", 3: reply(CORE_OK, TEST), 4: reply(CLI_OK, CLI_TEST),
              5: "[REWORK]\n1. demo/cli.py: the output is a bare uppercase word, not what the quality bar asks for",
              6: reply(("demo/cli.py", "from demo.core import add\n\ndef shout(s):\n    return s.upper() + '!!'\n"), ("tests/test_cli.py", CLI_TEST[1].replace("'A!'", "'A!!'"))),
              7: "[ACCEPTED]"}
    prompts = []

    class Recording(Scripted):
        def generate(self, prompt, model=None, **opts):
            prompts.append(prompt)
            return super().generate(prompt, model, **opts)

    graph = copy_recipe(V2 / "code_pipeline", tmp_path / "cp")
    monkeypatch.chdir(graph.parent)
    llm = Recording(script)
    rt = GraphLangRuntime(load_graph(graph), llm=llm, verbose=False)
    out = rt.execute(dict(PARAMS))
    assert rt.loop_iterations["appraise__appraisals"] == 2 and llm.calls == 8
    assert "the output is a bare uppercase word" in prompts[5] and "=== FILE: demo/cli.py ===" in prompts[5] and '"out/x.txt": "HI!"' in prompts[5]     # the developer sees defects, project and demo output
    assert out["appraisal"].startswith("[ACCEPTED]") and out["code"]["demo/cli.py"].endswith("'!!'\n") and out["report"].lstrip().startswith("[PASSED]")
    assert '"out/x.txt": "HI!!"' in prompts[6]                                         # the second appraisal saw the reworked product's output


def test_a_demo_that_fails_is_shown_to_the_judge_as_a_defect(docker, tmp_path, monkeypatch):
    broken = dict(DEMO, command=["python", "-c", "raise SystemExit('boom')"], outputs=["out"])
    seen = []

    class Recording(Scripted):
        def generate(self, prompt, model=None, **opts):
            seen.append(prompt)
            return super().generate(prompt, model, **opts)

    graph = copy_recipe(V2 / "code_pipeline", tmp_path / "cp")
    monkeypatch.chdir(graph.parent)
    one = plan(T1, demo=broken)
    llm = Recording({1: one, 2: "[APPROVED]", 3: reply(CORE_OK, TEST), 4: "[ACCEPTED]"})
    GraphLangRuntime(load_graph(graph), llm=llm, verbose=False).execute(dict(PARAMS))
    judged = seen[3]
    assert '"ok": false' in judged and '"returncode": 1' in judged and "boom" in judged and '"missing": ["out"]' in judged


def test_a_broken_container_stops_the_run_before_any_model_call(tmp_path, monkeypatch):
    """No docker on PATH: the preflight fails first, so nothing is billed."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    graph = copy_recipe(V2 / "code_pipeline", tmp_path / "cp")
    monkeypatch.chdir(graph.parent)
    llm = Scripted({1: GOOD_PLAN})
    with pytest.raises(Exception, match="preflight"):
        GraphLangRuntime(load_graph(graph), llm=llm, verbose=False).execute(dict(PARAMS))
    assert llm.calls == 0


# ---- the tools of code_pipeline, on their own ---------------------------------------------------------------------------------------

def tool(name, payload):
    import subprocess
    import sys
    done = subprocess.run([sys.executable, "-I", str(V2 / "code_pipeline" / "tools" / name)], input=json.dumps(payload), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_check_plan_names_what_is_missing():
    assert tool("check_plan.py", {"plan": GOOD_PLAN, "lang": "python"}) == {"ok": True, "report": "[READY] 2 tasks", "tasks": 2}
    bad = tool("check_plan.py", {"plan": THIN_PLAN, "lang": "python"})
    assert not bad["ok"] and all(w in bad["report"] for w in ("`description` is too thin", "`acceptance` is missing", "no task writes a test file"))
    twice = tool("check_plan.py", {"plan": plan(T1, task("t2", ["demo/core.py"], ["t9"])), "lang": "python"})["report"]
    assert "also written by task t1" in twice and "depends_on 't9'" in twice
    assert not tool("check_plan.py", {"plan": "just some words", "lang": "python"})["ok"]
    no_deliverables = tool("check_plan.py", {"plan": plan(T1, T2, deliverables=[]), "lang": "python"})["report"]
    assert "`deliverables` is missing" in no_deliverables
    thin = tool("check_plan.py", {"plan": plan(T1, T2, deliverables=[{"name": "a document", "mechanism": "a template"}]), "lang": "python"})["report"]
    assert "needs a `name`, a `mechanism`" in thin and "`quality_bar`" in thin
    assert tool("check_plan.py", {"plan": "```json\n" + GOOD_PLAN + "\n```", "lang": "python"})["ok"]            # a code fence around the JSON is fine


def test_check_plan_wants_a_runnable_offline_demo():
    for bad, words in ((None, "`demo` is missing"), ({**DEMO, "command": ["pytest"]}, "starting with \"python\""), ({**DEMO, "outputs": []}, "`demo.outputs`"),
                       ({**DEMO, "files": {"../x": "a"}}, "`demo.files`"), ({**DEMO, "description": ""}, "`demo.description`")):
        report = tool("check_plan.py", {"plan": plan(T1, T2, demo=bad), "lang": "python"})["report"]
        assert words in report, (bad, report)


def test_run_demo_reports_the_output_files_and_what_is_missing():
    project = {"p/__init__.py": "", "p/m.py": "def f():\n    return 'made'\n"}
    demo = {"description": "d", "command": ["python", "-c", "import pathlib; from p.m import f; pathlib.Path('o').mkdir(); pathlib.Path('o/a.txt').write_text(f())"], "outputs": ["o", "gone.txt"]}
    got = tool("run_demo.py", {"files": project, "plan": json.dumps({"demo": demo})})
    assert got["returncode"] == 0 and got["outputs"] == {"o/a.txt": "made"} and got["missing"] == ["gone.txt"] and not got["ok"]
    assert tool("run_demo.py", {"files": project, "plan": "{}"})["error"] == "the plan has no demo command"


def test_task_context_shows_one_task_and_the_files_so_far():
    first = tool("task_context.py", {"plan": GOOD_PLAN, "task_index": 0, "files": {}})
    assert "Task t1 of 2" in first["task"] and first["project"] == "(nothing written yet)" and first["first_file"] == "demo/core.py" and not first["last"]
    second = tool("task_context.py", {"plan": GOOD_PLAN, "task_index": 1, "files": {"demo/core.py": "x = 1\n"}})
    assert "Builds on: t1" in second["task"] and "=== FILE: demo/core.py ===\nx = 1" in second["project"] and second["last"] and second["summary"] == "a demo package"


def test_collect_files_adds_to_the_project_and_replaces_a_file_of_the_same_path():
    old = {"a/x.py": "old\n", "b.txt": "keep\n", "README.md": "# mine\n"}
    got = tool("collect_files.py", {"text": reply(("a/x.py", "new\n"), ("a/y.py", "y\n")), "lang": "python", "spec": "s", "files": old})
    assert got["a/x.py"] == "new\n" and got["a/y.py"] == "y\n" and got["b.txt"] == "keep\n" and got["README.md"] == "# mine\n" and "a/__init__.py" in got


def test_code_pipeline_is_self_contained_no_spl_procedures():
    """finish writes the docs and the closure check with prompts: no procedure_ref and no .spl file anywhere in the recipe, so SPL.py is not needed."""
    folder = V2 / "code_pipeline"
    assert not list(folder.rglob("*.spl"))
    for graph in folder.rglob("*.graph.yaml"):
        assert "procedure_ref" not in graph.read_text(encoding="utf-8"), graph
