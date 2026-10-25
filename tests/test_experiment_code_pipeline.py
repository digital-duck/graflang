"""The shared code_pipeline experiment's oracle and LangGraph baseline (no LLM, no network)."""
import sys
from pathlib import Path

import json

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "experiments" / "code_pipeline"))

import oracle  # noqa: E402
import analyze  # noqa: E402

TASK = {
    "task_id": "T/0",
    "prompt": "from typing import List\n\n\ndef total(xs: List[int]) -> int:\n    \"\"\"Sum of xs.\"\"\"\n",
    "entry_point": "total",
    "test": "def check(candidate):\n    assert candidate([1, 2, 3]) == 6\n    assert candidate([]) == 0\n",
}


def test_correct_code_passes_even_without_repeating_the_prompts_imports():
    assert oracle.check(TASK, "def total(xs: List[int]) -> int:\n    return sum(xs)\n").passed


@pytest.mark.parametrize("code, reason", [
    ("", "no_code"),
    ("   \n", "no_code"),
    ("def total(xs):\n    return 0\n", "AssertionError"),
    ("def total(xs) return", "SyntaxError"),
    ("def other(xs):\n    return sum(xs)\n", "NameError"),          # the function was renamed
    ("def total(xs):\n    while True:\n        pass\n", ""),          # never finishes
])
def test_everything_else_is_a_failure(code, reason):
    verdict = oracle.check(TASK, code, timeout=2)
    assert not verdict.passed
    assert reason in verdict.reason or verdict.reason == "timeout"


def test_the_oracle_does_not_see_the_environment(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "x")
    code = "import os\n\ndef total(xs):\n    assert 'SECRET_TOKEN' not in os.environ\n    return sum(xs)\n"
    assert oracle.check(TASK, code).passed


def test_the_langgraph_arm_reads_the_same_prompts_as_the_other_arms():
    pytest.importorskip("langgraph")
    import lg_pipeline
    prompts = lg_pipeline.load_prompts()
    assert {"spec_analyst", "coder", "reviewer", "refactor", "run_tests", "write_docs", "reverse_spec"} <= set(prompts)
    text = lg_pipeline.fill(prompts, "coder", spec="make {lang} work", lang="python")
    assert "make {lang} work" in text and "{spec}" not in text         # a value that looks like a placeholder is left alone


def test_the_langgraph_arm_follows_the_pipeline_with_a_scripted_model():
    pytest.importorskip("langgraph")
    import lg_pipeline

    class Scripted:
        def __init__(self, tester):
            self.tester, self.calls = list(tester), []

        def generate(self, prompt, model=None, **opts):
            if "data-protection" in prompt:
                raise AssertionError
            if "automated test suite" in prompt:
                self.calls.append("test")
                return self.tester.pop(0)
            for key, name in (("specification analyst", "analyze"), ("senior", "review"), ("improving code", "improve"),
                              ("expert python developer.\n\nWrite", "generate")):
                if key in prompt:
                    self.calls.append(name)
                    return "[READY]" if name == "analyze" else "def f():\n    return 1"
            self.calls.append("other")
            return "text"

    llm = Scripted(["[FAILED] no", "[PASSED]"])
    final = lg_pipeline.build(llm, "m", lambda t: t).invoke({"spec": "s", "lang": "python", "max_cycles": 3})
    assert final["cycle"] == 2 and final["passed"] is True
    assert llm.calls.count("test") == 2 and llm.calls.count("generate") == 2


# ---- the SQLite store ------------------------------------------------------------------------------------------------

def row(task="T/1", arm="spl", rep=0, model="m", passed=True, seconds=1.5):
    return {"task": task, "arm": arm, "rep": rep, "model": model, "passed": passed, "reason": "pass" if passed else "boom",
            "status": "ok", "pipeline_verdict": "PASSED", "cycles": 1, "seconds": seconds, "code": "def f(): pass"}


def test_results_are_stored_and_read_back_with_a_boolean_verdict(tmp_path):
    import store
    conn = store.connect(tmp_path / "e.db")
    batch = store.start_batch(conn, adapter="claude_cli", model="m", arms=["spl"], n_tasks=1, seed=0, reps=1, args={"x": 1})
    store.write_result(conn, batch, row(passed=False))
    store.finish_batch(conn, batch)
    (r,) = store.load_rows(tmp_path / "e.db")
    assert r["passed"] is False and r["code"] == "def f(): pass" and r["batch_id"] == batch
    assert conn.execute("SELECT runs_done, finished_at IS NOT NULL FROM batches").fetchone()[:] == (1, 1)


def test_the_skip_key_includes_the_model_and_a_rewrite_replaces_the_row(tmp_path):
    import store
    conn = store.connect(tmp_path / "e.db")
    store.write_result(conn, "b", row(model="a"))
    assert ("T/1", "spl", 0, "claude_cli", "a") in store.done_keys(conn) and ("T/1", "spl", 0, "claude_cli", "b") not in store.done_keys(conn)
    store.write_result(conn, "b", row(model="a", passed=False))                  # same key: replaced, not duplicated
    assert conn.execute("SELECT COUNT(*), SUM(passed) FROM results").fetchone()[:] == (1, 0)


def test_arm_summary_groups_by_model_and_arm(tmp_path):
    import store
    conn = store.connect(tmp_path / "e.db")
    for i, passed in enumerate([True, True, False]):
        store.write_result(conn, "b", row(task=f"T/{i}", passed=passed))
    store.write_result(conn, "b", row(model="other", passed=False))
    got = {(r["model"], r["arm"]): (r["runs"], r["passes"]) for r in conn.execute("SELECT * FROM arm_summary")}
    assert got == {("m", "spl"): (3, 2), ("other", "spl"): (1, 0)}
    assert len(store.load_rows(tmp_path / "e.db", model="other")) == 1


def test_an_older_jsonl_is_imported_once(tmp_path):
    import json
    import store
    old = tmp_path / "old.jsonl"
    old.write_text("\n".join(json.dumps(row(task=f"T/{i}")) for i in range(3)) + "\n")
    conn = store.connect(tmp_path / "e.db")
    assert store.import_jsonl(conn, old) == 3
    assert store.import_jsonl(conn, old) == 0
    assert len(store.load_rows(old)) == 3 and len(store.load_rows(tmp_path / "e.db")) == 3


# ---- the runner's command line, progress and timing --------------------------------------------------------------------

def test_hms_and_eta():
    import run
    assert [run.hms(s) for s in (4, 65, 3725)] == ["4s", "1m05s", "1h02m"]
    todo = [({}, "a", 0), ({}, "b", 0)]
    assert run.eta(todo, {"a": [10, 20]}) is None                       # arm b has not run yet
    assert run.eta(todo, {"a": [10, 20], "b": [5]}) == 20


def test_the_plan_skips_runs_already_stored_for_that_model():
    import run
    import tasks as T
    first = run.plan(T.sample(2, 0), 0, ["single", "spl"], 1, "m", "claude_cli", set())
    assert len(first) == 4
    done = {(t["task_id"], arm, rep, "claude_cli", "m") for t, arm, rep in first[:3]}
    assert len(run.plan(T.sample(2, 0), 0, ["single", "spl"], 1, "m", "claude_cli", done)) == 1
    assert len(run.plan(T.sample(2, 0), 0, ["single", "spl"], 1, "other", "claude_cli", done)) == 4
    assert len(run.plan(T.sample(2, 0), 0, ["single", "spl"], 1, "m", "ollama", done)) == 4


def test_the_command_runs_with_progress_a_timing_table_and_resumes(tmp_path, monkeypatch):
    import run
    import store
    from arms import ArmResult
    from click.testing import CliRunner

    calls = []

    def fake(spec, model, *work):
        calls.append(model)
        return ArmResult(code="def f():\n    return 1\n", seconds=0.1, pipeline_verdict="PASSED", cycles=1)

    for arm in ("single", "spl"):
        monkeypatch.setitem(run.ARMS, arm, fake)
    db = tmp_path / "e.db"
    args = ["--n", "2", "--arms", "single,spl", "--model", "m", "--db", str(db)]
    out = CliRunner().invoke(run.main, args)
    assert out.exit_code == 0, out.output
    assert "= 4 runs" in out.output and "[1/4]" in out.output and "[4/4]" in out.output
    assert "left ~" in out.output and "wall time" in out.output and "single" in out.output
    assert len(store.load_rows(db)) == 4 and len(calls) == 4
    again = CliRunner().invoke(run.main, args)                          # same command: nothing to do
    assert again.exit_code == 0 and "0 to do" in again.output and len(calls) == 4
    dry = CliRunner().invoke(run.main, [*args, "--dry-run", "--reps", "2"])
    assert "= 8 runs" in dry.output and "4 to do" in dry.output and len(calls) == 4


def test_an_unknown_arm_is_a_usage_error(tmp_path):
    import run
    from click.testing import CliRunner
    out = CliRunner().invoke(run.main, ["--arms", "nope", "--db", str(tmp_path / "e.db")])
    assert out.exit_code == 2 and "unknown arm" in out.output


def test_a_main_block_in_the_candidate_does_not_run_or_decide_the_verdict():
    code = ("def total(xs):\n    return sum(xs)\n\n\n"
            "if __name__ == '__main__':\n    assert total([1]) == 99          # the model's own wrong self-test\n")
    assert oracle.check(TASK, code).passed
    assert not oracle.check(TASK, "def total(xs):\n    return 0\n\nif __name__ == '__main__':\n    pass\n").passed


def test_rescore_updates_stored_rows_with_the_current_oracle(tmp_path):
    import store
    conn = store.connect(tmp_path / "e.db")
    good = "def total(xs):\n    return sum(xs)\n"
    store.write_result(conn, "b", {**row(task="T/0", passed=False), "code": good})       # stored as a failure, wrongly
    store.write_result(conn, "b", {**row(task="T/1", passed=True), "code": good})        # already right
    changed = store.rescore(conn, lambda task, code: oracle.check(TASK, code))
    assert changed == 2                                   # the second row was right but had no assertion counts yet
    assert [tuple(r) for r in conn.execute("SELECT passed, assert_passed, assert_total FROM results ORDER BY id")] == [(1, 2, 2), (1, 2, 2)]


def test_tasks_can_be_chosen_by_number_or_id():
    import tasks as T
    assert [t["task_id"] for t in T.select(None, 0, "98, HumanEval/107")] == ["HumanEval/98", "HumanEval/107"]
    assert len(T.select(5, 0, None)) == 5
    with pytest.raises(ValueError, match="no such task"):
        T.select(None, 0, "999")


def test_the_command_runs_the_chosen_tasks_and_gives_each_run_its_own_folder(tmp_path, monkeypatch):
    import run
    import store
    from arms import ArmResult
    from click.testing import CliRunner

    seen = []

    def fake(spec, model, folder):
        seen.append(folder)
        (folder / "code.py").write_text("x")
        return ArmResult(code="def f():\n    return 1\n", seconds=0.1, cycles=2)

    monkeypatch.setitem(run.ARMS, "single", fake)
    out = CliRunner().invoke(run.main, ["--tasks", "98,107", "--arms", "single", "--model", "m", "--db", str(tmp_path / "e.db"),
                                        "--run-dir", str(tmp_path / "out")])
    assert out.exit_code == 0, out.output
    assert sorted(f.parent.name for f in seen) == ["HumanEval_107", "HumanEval_98"]
    assert all(f.name == "single-rep0" and (f / "code.py").exists() for f in seen) and "cycles=2" in out.output
    assert {r["task"] for r in store.load_rows(tmp_path / "e.db")} == {"HumanEval/98", "HumanEval/107"}
    bad = CliRunner().invoke(run.main, ["--tasks", "999", "--db", str(tmp_path / "e.db")])
    assert bad.exit_code == 2 and "no such task" in bad.output


def test_failures_are_sorted_into_kinds_and_cycles_are_reported(tmp_path, capsys):
    import analyze
    import store
    entry = {"HumanEval/98": "count_upper"}
    base = {"task": "HumanEval/98", "passed": False, "status": "ok"}
    kind = lambda reason, **kw: analyze.failure_kind({**base, "reason": reason, **kw}, entry)
    assert kind("NameError: name 'count_upper' is not defined") == "renamed"
    assert kind("NameError: name 'helper' is not defined") == "code_error"
    assert kind("AssertionError") == "wrong_answer" and kind("FAILED (failures=1)") == "wrong_answer"
    assert kind("SyntaxError: invalid syntax") == "code_error" and kind("timeout") == "timeout" and kind("no_code") == "no_code"
    assert kind("anything", status="error:exit 1") == "error"
    assert analyze.failure_kind({**base, "passed": True, "reason": "pass"}, entry) == "pass"

    conn = store.connect(tmp_path / "e.db")
    for i, (arm, cycles, passed, reason) in enumerate([("spl", 1, True, "pass"), ("spl", 3, False, "NameError: name 'count_upper' is not defined"),
                                                       ("single", 1, True, "pass")]):
        store.write_result(conn, "b", {**row(task="HumanEval/98", arm=arm, rep=i, passed=passed), "cycles": cycles, "reason": reason})
    analyze.main([str(tmp_path / "e.db")])
    out = capsys.readouterr().out
    assert "'renamed': 1" in out and "Cycles used" in out and "mean 2.00 over 2 runs" in out and "3 cycle(s): 1" in out


# ---- adding tasks later: skip or append --------------------------------------------------------------------------------

def test_append_adds_repetitions_after_the_stored_ones_and_skip_does_not():
    import run
    import tasks as T
    tasks = T.select(None, 0, "98,107")
    done = {("HumanEval/98", "spl", 0, "claude_cli", "m"), ("HumanEval/98", "spl", 1, "claude_cli", "m")}      # task 98 ran twice on spl, nothing else
    skip = run.plan(tasks, 0, ["spl"], 2, "m", "claude_cli", done, "skip")
    assert [(t["task_id"], r) for t, a, r in skip] == [("HumanEval/107", 0), ("HumanEval/107", 1)]
    append = run.plan(tasks, 0, ["spl"], 1, "m", "claude_cli", done, "append")
    assert sorted((t["task_id"], r) for t, a, r in append) == [("HumanEval/107", 0), ("HumanEval/98", 2)]
    assert run.plan(tasks, 0, ["spl"], 1, "other-model", "claude_cli", done, "append")[0][2] == 0       # another model starts at 0


def test_tasks_come_from_the_environment_and_stored_tasks_are_reported_and_skipped(tmp_path, monkeypatch):
    import run
    import store
    from arms import ArmResult
    from click.testing import CliRunner

    calls = []
    monkeypatch.setitem(run.ARMS, "single", lambda spec, model, folder: calls.append(spec) or ArmResult(code="def f():\n    return 1\n"))
    db = tmp_path / "e.db"
    base = ["--arms", "single", "--model", "m", "--db", str(db), "--run-dir", str(tmp_path / "out")]
    first = CliRunner().invoke(run.main, base, env={"TASKS": "98,107"})
    assert first.exit_code == 0 and "2 to do" in first.output and len(calls) == 2
    more = CliRunner().invoke(run.main, base, env={"TASKS": "98,107,10"})               # a task added to the list later
    assert "already in" in more.output and "98, 107" in more.output and "1 to do, 2 skipped" in more.output and len(calls) == 3
    appended = CliRunner().invoke(run.main, [*base, "--existing", "append"], env={"TASKS": "98"})
    assert "new repetitions are appended" in appended.output and len(calls) == 4
    assert sorted(r["rep"] for r in store.load_rows(db) if r["task"] == "HumanEval/98") == [0, 1]
    empty = CliRunner().invoke(run.main, [*base, "--n", "2", "--dry-run"], env={"TASKS": ""})   # TASKS="" means: use --n
    assert empty.exit_code == 0 and "2 tasks" in empty.output


def test_an_arm_that_raises_does_not_stop_the_batch_and_is_retried_on_the_next_run(tmp_path, monkeypatch):
    import run
    import store
    from arms import ArmResult
    from click.testing import CliRunner

    calls = {"n": 0}

    def flaky(spec, model, folder):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("claude exited 1: something unexpected")
        return ArmResult(code="def f():\n    return 1\n")

    monkeypatch.setitem(run.ARMS, "single", flaky)
    args = ["--tasks", "98,107", "--arms", "single", "--model", "m", "--db", str(tmp_path / "e.db"), "--run-dir", str(tmp_path / "out")]
    first = CliRunner().invoke(run.main, args)
    assert first.exit_code == 0 and calls["n"] == 2                    # the second task still ran
    rows = {r["task"]: r for r in store.load_rows(tmp_path / "e.db")}
    assert rows["HumanEval/98"]["status"].startswith("error:RuntimeError") and "something unexpected" in rows["HumanEval/98"]["status"]
    assert (tmp_path / "out" / "claude_cli" / "m" / "HumanEval_98" / "single-rep0" / "error.txt").exists()
    again = CliRunner().invoke(run.main, args)                         # the error row is not "done": only it runs again
    assert "1 to do" in again.output and calls["n"] == 3
    assert {r["status"] for r in store.load_rows(tmp_path / "e.db")} == {"ok"}


# ---- the adapter column ----------------------------------------------------------------------------------------------

def test_the_same_model_on_two_adapters_is_two_runs(tmp_path):
    import store
    conn = store.connect(tmp_path / "e.db")
    store.write_result(conn, "b", {**row(model="gemma4"), "adapter": "claude_cli"})
    store.write_result(conn, "b", {**row(model="gemma4"), "adapter": "ollama"})
    assert conn.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 2
    got = {(r["adapter"], r["model"]): r["runs"] for r in conn.execute("SELECT adapter, model, runs FROM arm_summary")}
    assert got == {("claude_cli", "gemma4"): 1, ("ollama", "gemma4"): 1}
    assert len(store.load_rows(tmp_path / "e.db", adapter="ollama")) == 1


def test_an_old_database_without_the_adapter_column_is_migrated_and_keeps_its_rows(tmp_path):
    import sqlite3
    import store
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE results (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT, hostname TEXT, task TEXT NOT NULL,
            arm TEXT NOT NULL, rep INTEGER NOT NULL, model TEXT NOT NULL, passed INTEGER NOT NULL, reason TEXT, status TEXT,
            pipeline_verdict TEXT, cycles INTEGER, seconds REAL, code TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task, arm, rep, model));
        CREATE TABLE batches (batch_id TEXT PRIMARY KEY, hostname TEXT, model TEXT, arms TEXT, n_tasks INTEGER, seed INTEGER,
            reps INTEGER, args TEXT, started_at TIMESTAMP, finished_at TIMESTAMP, runs_done INTEGER DEFAULT 0);
        CREATE VIEW arm_summary AS SELECT model, arm, COUNT(*) AS runs FROM results GROUP BY model, arm;
        INSERT INTO results (task, arm, rep, model, passed, status, code) VALUES ('HumanEval/98', 'spl', 0, 'gemma4', 1, 'ok', 'x');
    """)
    old.commit()
    old.close()
    conn = store.connect(path)
    assert [tuple(r) for r in conn.execute("SELECT task, arm, adapter, model, passed FROM results")] == \
        [("HumanEval/98", "spl", "claude_cli", "gemma4", 1)]
    assert ("HumanEval/98", "spl", 0, "claude_cli", "gemma4") in store.done_keys(conn)
    store.write_result(conn, "b", {**row(model="gemma4"), "adapter": "ollama"})          # a new adapter no longer collides
    assert conn.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 2
    assert conn.execute("SELECT adapter, runs FROM arm_summary ORDER BY adapter").fetchall()[0][:] == ("claude_cli", 1)
    conn.execute("SELECT adapter FROM batches").fetchall()                                     # batches migrated too
    store.connect(path)                                                                       # a second open changes nothing


# ---- what each run keeps: assertion counts, per-cycle code and verdicts, LLM calls and tokens ---------------------------

def test_the_scorer_counts_assertions_and_still_fails_the_program_on_any_failure():
    full = oracle.check(TASK, "def total(xs: List[int]) -> int:\n    return sum(xs)\n")
    assert (full.passed, full.assert_passed, full.assert_total) == (True, 2, 2)
    half = oracle.check(TASK, "def total(xs: List[int]) -> int:\n    return sum(xs) if xs else 1\n")   # the empty list is wrong
    assert (half.passed, half.assert_passed, half.assert_total) == (False, 1, 2)
    none_ran = oracle.check(TASK, "def other(xs):\n    return 0\n")
    assert none_ran.assert_total == 0 and not none_ran.passed


def test_the_test_prompt_gives_back_the_code_it_was_asked_to_check():
    import arms
    template = (ROOT_TEMPLATE / "04_test_code.spl").read_text(encoding="utf-8")
    body = template[template.index("AS $$") + 6:template.index("$$;")]
    prompt = body.replace("{lang}", "python").replace("{spec}", "SPEC").replace("{code}", "def g(x):\n    return x * 2")
    assert arms._code_in_test_prompt(prompt) == "def g(x):\n    return x * 2"
    assert arms._code_in_test_prompt("no code here") == ""


ROOT_TEMPLATE = Path(__file__).resolve().parent.parent / "cookbook" / "code_pipeline"


def test_spl_cycles_mark_every_cycle_but_the_last_as_failed(tmp_path):
    import arms
    (tmp_path / "prompts").mkdir()
    for i, code in enumerate(["def f():\n    return 1\n", "def f():\n    return 2\n"], start=1):
        (tmp_path / "prompts" / f"run_tests_{i:03d}.md").write_text(
            f"python code to evaluate:\n{code}\n\nEvaluate the code against the specification. Check:\n", encoding="utf-8")
    cycles = arms._spl_cycles(tmp_path, "PASSED", "def f():\n    return 2\n")
    assert [(c["cycle"], c["verdict"]) for c in cycles] == [(1, "FAILED"), (2, "PASSED")]
    assert cycles[0]["code"] == "def f():\n    return 1\n" and cycles[1]["code"] == "def f():\n    return 2\n"


def test_llm_totals_skip_the_orchestrator_record_and_sum_the_sub_workflows():
    import arms
    lines = ["workflow.end workflow=generate_code status=complete llm_calls=1 input_tokens=52 output_tokens=54 ms=1",
             "workflow.end workflow=review_code status=complete llm_calls=2 input_tokens=100 output_tokens=30 ms=1",
             "workflow.end workflow=code_pipeline status=complete llm_calls=3 input_tokens=0 output_tokens=0 ms=9"]
    assert arms._spl_totals(lines, skip="code_pipeline") == {"calls": 3, "prompt_tokens": 152, "output_tokens": 84}


def test_graf_cycles_pair_each_loop_iteration_with_its_saved_code_and_verdict(tmp_path):
    import arms
    logs = tmp_path / "logs"
    logs.mkdir()
    nodes = tmp_path / "graf_out" / "nodes"
    nodes.mkdir(parents=True)
    events = []
    for i, (route, code) in enumerate([("fail", "def f():\n    return 1\n"), ("pass", "def f():\n    return 2\n")]):
        saved = nodes / f"{3 * i + 2:03d}-loop_imp.out_improved_code.md"
        saved.write_text(code, encoding="utf-8")
        events.append({"msg": f"node.saved node=loop_imp port=out_improved_code file={saved} chars={len(code)}", "file": str(saved)})
        events.append({"msg": f"node.done node=loop_eval type=EVALUATE n=1 depth=1 route={route} outputs=[] ms=0"})
    (logs / "code_pipeline-x.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    import json as _json
    cycles = arms._graf_cycles(tmp_path, "PASSED", "def f():\n    return 2\n")
    assert [(c["cycle"], c["verdict"]) for c in cycles] == [(1, "FAILED"), (2, "PASSED")]
    assert cycles[0]["code"] == "def f():\n    return 1\n" and cycles[1]["code"] == "def f():\n    return 2\n"


def test_mcnemar_exact_gives_the_textbook_values():
    import analyze
    assert analyze.mcnemar_exact(0, 0) == 1.0
    assert abs(analyze.mcnemar_exact(0, 5) - 0.0625) < 1e-9          # 5 of 5 discordant pairs in one direction
    assert abs(analyze.mcnemar_exact(3, 3) - 1.0) < 1e-9


def test_code_hygiene_reads_the_signature_and_the_extras():
    import analyze
    prompt = "def total(xs: List[int]) -> int:\n    '''doc'''\n"
    clean = analyze.code_hygiene("def total(xs):\n    return sum(xs)\n", prompt, "total")
    assert clean["name_ok"] and clean["args_ok"] and not clean["main_block"] and clean["other_top_level"] == 0
    messy = analyze.code_hygiene("import unittest\n\ndef total(a, b):\n    print(a)\n    return a\n\n"
                                 "if __name__ == '__main__':\n    unittest.main()\n", prompt, "total")
    assert messy["name_ok"] and not messy["args_ok"] and messy["main_block"] and messy["unittest"] and messy["prints"] == 1
    renamed = analyze.code_hygiene("def other(a, b):\n    return a\n", prompt, "total")
    assert not renamed["name_ok"]
    assert analyze.code_hygiene("def total(:", prompt, "total") is None


def test_the_store_keeps_the_new_columns_and_rescore_refreshes_them(tmp_path):
    import store
    conn = store.connect(tmp_path / "e.db")
    store.write_result(conn, "b", {**row(task="T/0", passed=False), "assert_passed": 1, "assert_total": 2, "llm_calls": 3,
                                   "prompt_tokens": 40, "output_tokens": 9,
                                   "cycles_detail": json.dumps([{"cycle": 1, "code": "def f():\n    return 2\n", "verdict": "FAILED",
                                                                  "hidden_passed": False, "assert_passed": 0, "assert_total": 0}])})
    r = conn.execute("SELECT * FROM results").fetchone()
    assert (r["assert_passed"], r["assert_total"], r["llm_calls"], r["prompt_tokens"], r["output_tokens"]) == (1, 2, 3, 40, 9)
    assert json.loads(r["cycles_detail"])[0]["verdict"] == "FAILED"


# ---- complexity groups and the stratified sample ----------------------------------------------------------------------

def test_complexity_groups_are_thirds_and_cover_all_tasks():
    import tasks as T
    from collections import Counter
    groups = T.complexity_groups()
    assert len(groups) == 164 and set(groups.values()) == {"low", "medium", "high"}
    counts = Counter(groups.values())
    assert max(counts.values()) - min(counts.values()) <= 1                 # 55 / 55 / 54


def test_the_groups_are_ordered_by_branch_count():
    import tasks as T
    groups = T.complexity_groups()
    by_group = {g: [T.complexity(t)["branches"] for t in T.load_all() if groups[t["task_id"]] == g]
                for g in ("low", "medium", "high")}
    assert max(by_group["low"]) <= min(by_group["medium"]) and max(by_group["medium"]) <= min(by_group["high"])


def test_the_stratified_sample_takes_the_same_number_from_each_group_and_is_fixed():
    import tasks as T
    from collections import Counter
    groups = T.complexity_groups()
    sample = T.stratified_sample(20, 0)
    assert len(sample) == 60 and Counter(groups[t["task_id"]] for t in sample) == {"low": 20, "medium": 20, "high": 20}
    assert [t["task_id"] for t in T.stratified_sample(20, 0)] == [t["task_id"] for t in sample]
    assert [t["task_id"] for t in T.stratified_sample(20, 1)] != [t["task_id"] for t in sample]


def test_run_per_group_plans_the_stratified_sample(tmp_path):
    import run
    from click.testing import CliRunner
    out = CliRunner().invoke(run.main, ["--per-group", "20", "--arms", "single", "--model", "m", "--dry-run",
                                        "--db", str(tmp_path / "e.db")])
    assert out.exit_code == 0 and "60 tasks x 1 arms" in out.output


def test_equivalence_by_paired_tost_uses_the_pre_specified_margin():
    import analyze
    assert analyze.EQUIVALENCE_MARGIN == 0.10 and analyze.EQUIVALENCE_ALPHA == 0.05
    d, p = analyze.tost_paired(2, 2, 60)                       # equal, few discordant tasks
    assert d == 0 and p < 0.05
    d, p = analyze.tost_paired(8, 8, 60)                       # equal but very noisy: not shown equivalent
    assert d == 0 and p > 0.05
    d, p = analyze.tost_paired(15, 3, 60)                      # a clear 20-point gap
    assert abs(d - 0.2) < 1e-9 and p > 0.05
    assert analyze.tost_paired(0, 0, 60) == (0.0, 0.0)
    assert analyze.tost_paired(0, 0, 0) == (0.0, 1.0)


def test_the_name_check_reads_the_required_name_and_checks_the_definition():
    import importlib.util
    path = Path(__file__).resolve().parent.parent / "cookbook" / "code_pipeline" / "tools.py"
    spec_ = importlib.util.spec_from_file_location("cp_tools", path)
    tools = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(tools)
    spec = 'def helper(x):\n    return x\n\ndef target(s):\n    """doc"""\n'
    assert tools.required_name(spec) == "target"                                  # the last top-level def is the target
    assert tools.name_verdict(spec, "def target(s):\n    return 1\n") == ""
    assert tools.name_verdict(spec, "def target2(s):\n    return 1\n").startswith("[FAILED]")
    assert tools.name_verdict(spec, "x = 1\n").startswith("[FAILED]")
    assert tools.name_verdict("no function here", "anything") == ""              # nothing to check, nothing to fail


def test_a_session_limit_stops_the_batch_and_the_limit_run_is_retried_later(tmp_path, monkeypatch):
    """The batch must not keep going once the account reports a limit: every later run would fail at once. The limit run is
    stored as an error (so a rerun after the reset retries it), the batch ends with exit code 3, and nothing else runs."""
    import run
    import store
    from arms import ArmResult
    from click.testing import CliRunner

    calls = []

    def hits_limit(spec, model, folder):
        calls.append("limit")
        return ArmResult(status="error:RuntimeError: Claude CLI limit reached: You've hit your session limit")

    def fine(spec, model, folder):
        calls.append("ok")
        return ArmResult(code="def f():\n    return 1\n", seconds=0.1, cycles=1)

    monkeypatch.setitem(run.ARMS, "single", hits_limit)
    monkeypatch.setitem(run.ARMS, "graflang", fine)
    db = tmp_path / "e.db"
    base = ["--tasks", "98,107", "--arms", "single,graflang", "--model", "m", "--db", str(db), "--run-dir", str(tmp_path / "out")]
    out = CliRunner().invoke(run.main, base)
    assert out.exit_code == 3 and "STOPPED" in out.output
    assert calls == ["limit"]                                             # the next run was never started
    rows = store.load_rows(db)
    assert [r["status"][:5] for r in rows] == ["error"]                   # the limit run is stored as an error
    assert store.done_keys(store.connect(db)) == set()                    # ...so it is not 'done' and will be retried
    monkeypatch.setitem(run.ARMS, "single", fine)
    again = CliRunner().invoke(run.main, base)
    assert again.exit_code == 0 and calls == ["limit", "ok", "ok", "ok", "ok"]  # the rerun retries it and finishes the batch


def test_a_limit_printed_only_on_stdout_is_still_detected(tmp_path):
    import arms
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "stdout.txt").write_text("dd-llm [claude_cli] failed: Claude CLI limit reached: session limit", encoding="utf-8")
    assert arms.limit_in_folder(folder)
    done = type("D", (), {"stdout": "limit reached on stdout", "stderr": "", "returncode": 1})()
    status, _ = arms._finish(done, "", 0.0)
    assert "limit reached" in status and arms.is_limit_error(status)
