"""cookbook_v2: recipes ported to the layered form (docs/DEV/DESIGN/graflang-recipes.md). Each one must validate with no errors or warnings, and
behave like the original in cookbook/ (same outputs, same steps run), checked offline with the echo and mock adapters."""
from pathlib import Path

import pytest

pytest.importorskip("spl", reason="procedure_ref nodes need SPL.py importable")

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
LAYERED = V2 / "code_pipeline" / "code_pipeline.graph.yaml"
# the steps of the original and the node each became in the layered one (ids are `<composite>__<step>`)
SAME_STEPS = {"analyze": "understand__analyze", "spec_gate": "understand__clear", "document": "finish__document", "extract": "finish__extract",
              "closure_gate": "finish__closure", "judge": "finish__judge", "merge_docs": "finish__merge"}
LOOP_STEPS = {"loop_gen": "generate", "loop_rev": "review", "loop_imp": "improve", "loop_test": "test", "loop_eval": "ok", "loop_guard": "retry"}


def run(path, adapter, params, cwd, monkeypatch):
    monkeypatch.chdir(cwd)                                  # the procedures write their logs under the current folder
    rt = GraphLangRuntime(load_graph(path), llm=make_llm(adapter), verbose=False)
    return rt, rt.execute(params)


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
import shutil


class Scripted:
    """An LLM that answers call number N with script[N] (1-based) and otherwise with 'text N'."""

    name = "scripted"

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
    for name in ("compliance_audit", "your_book", "agent_notes", "supervisor", "self_heal", "heartbeat", "stock_copy", "ts_verify", "notes_digest", "chat_memory"):
        top = [n for n in load_graph(V2 / name / f"{name}.graph.yaml", levels=0)["nodes"] if n["type"] != "INPUT"]
        assert len(top) <= 10, (name, len(top))
