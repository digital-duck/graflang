"""The compliance audit's batch test: the answer keys are consistent with the documents, the scoring is right, and the runner plans and resumes."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "cookbook" / "compliance_audit"
spec = importlib.util.spec_from_file_location("batch_test", ROOT / "batch_test.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

store = bt.store
DOCS = bt.load_manifest(ROOT / "input" / "batch-test" / "manifest.json")


def test_every_document_exists_and_every_key_string_is_in_it():
    assert len(DOCS) >= 15
    for d in DOCS:
        text = bt.norm((ROOT / "input" / "batch-test" / d["file"]).read_text(encoding="utf-8"))
        for kind in ("must_mask", "must_keep", "ambiguous"):
            for s in d[kind]:
                assert bt.norm(s) in text, f"{d['id']}: {kind} string {s!r} is not in {d['file']}"
        assert d.get("expect", "released") in ("released", "escalated") and d["note"]


def test_the_set_covers_the_kinds_of_document_it_claims_to():
    tags = {t for d in DOCS for t in d["tags"]}
    assert {"clean", "ssn", "card", "email", "phone", "address", "dob", "name", "injection", "obfuscated", "non-english", "table", "long", "company-contact"} <= tags
    assert any(not d["must_mask"] for d in DOCS)                                       # clean ones exist: over-redaction can show


def test_ids_are_unique_and_select_by_id_tag_and_limit():
    assert len({d["id"] for d in DOCS}) == len(DOCS)
    assert [d["id"] for d in bt.select(DOCS, ["ssn_plain"], None)] == ["ssn_plain"]
    assert all("clean" in d["tags"] for d in bt.select(DOCS, ["clean"], None))
    assert len(bt.select(DOCS, None, 3)) == 3
    with pytest.raises(ValueError, match="nonesuch"):
        bt.select(DOCS, ["nonesuch"], None)


def doc(**kw):
    return {"id": "d", "must_mask": ["Jane Roe", "123-45-6789"], "must_keep": ["ORD-1"], "ambiguous": ["help@x.example"], **kw}


def test_a_clean_release_is_correct():
    s = bt.score(doc(), True, "Order ORD-1 for [REDACTED], help@x.example")
    assert s["correct"] and not s["false_release"] and not s["over_redaction"] and s["ambiguous_left"] == ["help@x.example"]


def test_a_leak_is_a_false_release_whatever_else_is_right():
    s = bt.score(doc(), True, "ORD-1 jane   roe called")                                # case and spacing do not hide it
    assert s["false_release"] and s["leaks"] == ["Jane Roe"] and not s["correct"]


def test_over_redaction_and_escalation():
    assert bt.score(doc(), True, "ORD- removed [REDACTED]")["over_redaction"]
    esc = bt.score(doc(), False, "")
    assert esc["false_escalation"] and not esc["correct"] and not esc["false_release"]
    assert bt.score(doc(expect="escalated"), False, "")["correct"] and not bt.score(doc(expect="escalated"), False, "")["false_escalation"]
    assert not bt.score(doc(expect="escalated"), True, "ORD-1")["correct"]


def test_ambiguous_items_are_never_scored():
    d = doc(must_mask=[], ambiguous=["help@x.example"])
    assert bt.score(d, True, "ORD-1 help@x.example")["correct"] and bt.score(d, True, "ORD-1")["correct"]


def rows():
    mk = lambda v, m, dname, **kw: {"doc": dname, "variant": v, "llm": m, "released": True, "false_release": False, "false_escalation": False,
                                    "over_redaction": False, "correct": True, "calls": 3, "tokens_in": 100, "tokens_out": 20, "seconds": 5, **kw}
    return [mk("recipe-z3", "a:m1", "x"), mk("recipe-z3", "a:m1", "y", false_release=True, correct=False),
            mk("llm_only", "a:m1", "x"), mk("llm_only", "a:m1", "y", released=False, false_escalation=True, correct=False),
            mk("llm_only", "a:m1", "z", error="boom")]


def test_the_summary_counts_and_the_report():
    s = {(r["variant"], r["llm"]): r for r in bt.summarize(rows())}
    z, b = s[("recipe-z3", "a:m1")], s[("llm_only", "a:m1")]
    assert (z["runs"], z["correct"], z["false_release"], z["tokens"]) == (2, 1, 1, 240)
    assert (b["runs"], b["errors"], b["false_escalation"], b["calls"]) == (3, 1, 1, 6)           # an error is not counted as an outcome
    report = bt.markdown(rows())
    assert "false release" in report and "| y |" in report and "R!" in report and "Ex" in report and "?" in report


def test_the_plan_is_printed_and_nothing_runs_on_dry_run(capsys, monkeypatch):
    monkeypatch.setattr(bt, "one_run", lambda *a, **k: pytest.fail("a run was made on a dry run"))
    assert bt.main(["--llm", "a:m1,a:m2", "--variants", "recipe-z3,llm_only", "--limit", "2", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "documents    2" in out and "runs         8  (2 x 2 x 2 x 1)" in out and "about 24, at most 40" in out and "nothing was run" in out


def test_max_calls_refuses_a_big_plan(capsys, monkeypatch):
    monkeypatch.setattr(bt, "one_run", lambda *a, **k: pytest.fail("ran"))
    assert bt.main(["--llm", "a:m1", "--max-calls", "10"]) == 2
    assert "refused" in capsys.readouterr().out


def test_unknown_variant_is_an_error():
    with pytest.raises(SystemExit):
        bt.main(["--llm", "a:m1", "--variants", "recipe-z4"])


def test_a_batch_writes_results_and_resumes(tmp_path, capsys, monkeypatch):
    calls = []

    def fake(d, variant, llm, args, folder, bind):
        calls.append((d["id"], variant, llm))
        return {"doc": d["id"], "variant": variant, "llm": llm, **bt.score(d, True, "ORD-1"), "calls": 3, "tokens_in": 1, "tokens_out": 1, "seconds": 0.1}
    monkeypatch.setattr(bt, "one_run", fake)
    args = ["--llm", "a:m1", "--variants", "llm_only", "--limit", "3", "--out", str(tmp_path), "--db", str(tmp_path / "e.db")]
    assert bt.main(args) == 0
    assert len(calls) == 3 and len(store.load_rows(tmp_path / "e.db")) == 3 and "By variant" in store.connect(tmp_path / "e.db").execute("SELECT summary FROM batches").fetchone()[0]
    calls.clear()
    assert bt.main(args + ["--resume"]) == 0
    assert calls == []                                                                  # everything was already done
    assert bt.main(["--llm", "a:m1", "--variants", "llm_only", "--limit", "4", "--out", str(tmp_path), "--resume", "--db", str(tmp_path / "e.db")]) == 0
    assert len(calls) == 1 and len(store.load_rows(tmp_path / "e.db")) == 4


# ---- SQLite store and analysis ---------------------------------------------------------------------------------------------
def _load(name):
    sp = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _row(d, variant, llm, **kw):
    base = {"doc": d, "variant": variant, "llm": llm, "destination": "external_api", "seconds": 1.0, "llm_seconds": 0.8, "other_seconds": 0.05, "released": True, "false_release": False,
            "leaks": [], "false_escalation": False, "over_redaction": False, "lost": [], "ambiguous_left": [], "correct": True,
            "audit": "released", "calls": 3, "tokens_in": 10, "tokens_out": 5, "first_compliant": False, "first_violated": ["SSN"],
            "result_dir": "x", "rep": 0}
    return {**base, **kw}


def test_store_round_trip_and_resume_skips_only_finished_cells(tmp_path):
    store = _load("batch_store")
    conn = store.connect(tmp_path / "e.db")
    b = store.start_batch(conn, models=["m"], variants=["llm_only"], n_docs=2, reps=1, args={})
    store.write_result(conn, b, _row("a", "llm_only", "m", false_release=True, leaks=["123-45-6789"], correct=False))
    store.write_result(conn, b, {"doc": "b", "variant": "llm_only", "llm": "m", "seconds": 2.0, "error": "timed out", "rep": 0})
    store.finish_batch(conn, b)
    assert store.done_keys(conn) == {("a", "llm_only", 0, "m")}                      # the error is tried again
    rows = store.load_rows(tmp_path / "e.db")
    assert rows[0]["false_release"] is True and rows[0]["leaks"] == ["123-45-6789"] and rows[1]["error"] == "timed out"
    store.write_result(conn, b, _row("b", "llm_only", "m"))                          # the retry replaces the error row
    assert len(store.load_rows(tmp_path / "e.db")) == 2
    s = conn.execute("SELECT * FROM variant_summary").fetchone()
    assert s["runs"] == 2 and s["false_releases"] == 1 and s["errors"] == 0


def test_analysis_report_covers_the_sections(tmp_path):
    store, an = _load("batch_store"), _load("batch_analyze")
    conn = store.connect(tmp_path / "e.db")
    b = store.start_batch(conn, models=["m1", "m2"], variants=["recipe-z3", "llm_only"], n_docs=3, reps=1, args={})
    for i in range(6):
        store.write_result(conn, b, _row(f"d{i}", "recipe-z3", "m1"))
        store.write_result(conn, b, _row(f"d{i}", "llm_only", "m1", correct=i < 3, false_release=i >= 4, leaks=["x"] if i >= 4 else []))
    store.write_result(conn, b, _row("d0", "llm_only", "m2"))
    text = an.report(store.load_rows(tmp_path / "e.db"))
    for head in ("By model and variant", "Elapsed time per run", "Same variant, different models", "Leaks", "By document", "Paired comparison", "Hygiene"):
        assert head in text
    assert "recipe-z3" in text and "6/6 = 100%" in text
    assert an.mcnemar_exact(0, 0) == 1.0 and an.mcnemar_exact(5, 0) < 0.07
    assert an.quantile([1, 2, 3, 4], .5) == 2.5 and an.quantile([], .9) == 0.0
    assert an.wilson(0, 0) == (0.0, 0.0)
    assert an.main(["--db", str(tmp_path / "missing.db")]) == 2


def test_the_run_cap_comes_from_the_graph_with_a_margin():
    assert bt.calls_per_run("recipe-z3") == (3, 5) and bt.calls_per_run("llm_only", 1.0) == (3, 6) and bt.calls_per_run("llm_only", 0) == (3, 4)
    from graphlang.grafr.partinfo import suggested_cap
    assert suggested_cap(10) == 15 and suggested_cap(1) == 2 and suggested_cap(0, 0.5) == 1


def test_rescore_updates_stored_rows_from_the_run_folder_without_a_model(tmp_path):
    store = _load("batch_store")
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "result.json").write_text(json.dumps({"audit": "released to x", "safe_document": "Order ORD-1 for [REDACTED]"}))
    key = {"id": "d", "file": "d.txt", "must_mask": ["Jane"], "must_keep": ["ORD-1", "Denver"], "ambiguous": []}
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"documents": [key]}))
    conn = store.connect(tmp_path / "e.db")
    b = store.start_batch(conn, models=["m"], variants=["recipe-z3"], n_docs=1, reps=1, args={})
    store.write_result(conn, b, _row("d", "recipe-z3", "m", over_redaction=True, lost=["Denver"], correct=False, result_dir=str(folder)))
    assert bt.main(["--rescore", "--db", str(tmp_path / "e.db"), "--manifest", str(manifest)]) == 0
    assert store.load_rows(tmp_path / "e.db")[0]["over_redaction"] is True              # Denver is still a must_keep: unchanged
    key["must_keep"], key["ambiguous"] = ["ORD-1"], ["Denver"]
    manifest.write_text(json.dumps({"documents": [key]}))
    assert bt.main(["--rescore", "--db", str(tmp_path / "e.db"), "--manifest", str(manifest)]) == 0
    row = store.load_rows(tmp_path / "e.db")[0]
    assert row["over_redaction"] is False and row["correct"] is True


def test_the_analysis_compares_databases_side_by_side(tmp_path):
    store, an = _load("batch_store"), _load("batch_analyze")
    for name, ok in (("v1", False), ("v2", True)):
        conn = store.connect(tmp_path / f"{name}.db")
        b = store.start_batch(conn, models=["m"], variants=["recipe-z3"], n_docs=1, reps=1, args={})
        store.write_result(conn, b, _row("a", "recipe-z3", "m", correct=ok))
    out = tmp_path / "r.md"
    assert an.main(["--db", str(tmp_path / "v1.db"), "--db", str(tmp_path / "v2.db"), "--out", str(out)]) == 0
    text = out.read_text()
    assert "m [v1]" in text and "m [v2]" in text
