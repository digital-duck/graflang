"""The compliance audit's batch test: the answer keys are consistent with the documents, the scoring is right, and the runner plans and resumes."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "cookbook" / "compliance_audit"
spec = importlib.util.spec_from_file_location("batch_test", ROOT / "batch_test.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

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
            mk("baseline", "a:m1", "x"), mk("baseline", "a:m1", "y", released=False, false_escalation=True, correct=False),
            mk("baseline", "a:m1", "z", error="boom")]


def test_the_summary_counts_and_the_report():
    s = {(r["variant"], r["llm"]): r for r in bt.summarize(rows())}
    z, b = s[("recipe-z3", "a:m1")], s[("baseline", "a:m1")]
    assert (z["runs"], z["correct"], z["false_release"], z["tokens"]) == (2, 1, 1, 240)
    assert (b["runs"], b["errors"], b["false_escalation"], b["calls"]) == (3, 1, 1, 6)           # an error is not counted as an outcome
    report = bt.markdown(rows())
    assert "false release" in report and "| y |" in report and "R!" in report and "Ex" in report and "?" in report


def test_the_plan_is_printed_and_nothing_runs_without_yes(capsys, monkeypatch):
    monkeypatch.setattr(bt, "one_run", lambda *a, **k: pytest.fail("a run was made without --yes"))
    assert bt.main(["--llm", "a:m1,a:m2", "--variants", "recipe-z3,baseline", "--limit", "2"]) == 0
    out = capsys.readouterr().out
    assert "2 document(s) x 2 variant(s)" in out and "= 8 runs, at most 24 model calls" in out and "nothing was run" in out


def test_max_calls_refuses_a_big_plan(capsys, monkeypatch):
    monkeypatch.setattr(bt, "one_run", lambda *a, **k: pytest.fail("ran"))
    assert bt.main(["--llm", "a:m1", "--max-calls", "10", "--yes"]) == 2
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
    args = ["--llm", "a:m1", "--variants", "baseline", "--limit", "3", "--out", str(tmp_path), "--yes"]
    assert bt.main(args) == 0
    assert len(calls) == 3 and len((tmp_path / "results.jsonl").read_text().splitlines()) == 3 and (tmp_path / "summary.md").is_file()
    calls.clear()
    assert bt.main(args + ["--resume"]) == 0
    assert calls == []                                                                  # everything was already done
    assert bt.main(["--llm", "a:m1", "--variants", "baseline", "--limit", "4", "--out", str(tmp_path), "--yes", "--resume"]) == 0
    assert len(calls) == 1 and len((tmp_path / "results.jsonl").read_text().splitlines()) == 4
