"""DECISION: a person as a node (interactive mode; docs/DEV/DESIGN/graflang-hitl.md)."""
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from graphlang.cli import main
from graphlang.grafr.decision import DecisionError, check_decision, run_decision
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

COOKBOOK = Path(__file__).resolve().parent.parent / "cookbook"


class Scripted:
    name, adapter_name, model_override = "scripted", "echo", None

    def generate(self, prompt, model=None, **opts):
        return "Demo moves to 3pm."


def node(**cfg):
    return {"id": "approve", "type": "DECISION", "config": cfg, "ports": ["trigger", "answered", "timeout", "in_question", "out_answer", "out_note", "out_by"]}


def asker(*lines):
    it = iter(lines)
    return lambda prompt, timeout: next(it)


def test_a_supplied_answer_is_used_and_carries_who_and_a_note():
    r = run_decision(node(answers=["yes", "no"], question="ok?"), {}, {"approve": "Yes | looks fine"}, by="wen")
    assert r == {"_route": "answered", "out_answer": "yes", "out_note": "looks fine", "out_by": "wen"}


def test_a_supplied_answer_must_be_allowed():
    with pytest.raises(DecisionError, match="not one of"):
        run_decision(node(answers=["yes", "no"], question="ok?"), {}, {"approve": "maybe"})


def test_the_terminal_is_asked_again_after_a_bad_answer():
    r = run_decision(node(answers=["yes", "no"], question="ok?"), {}, {}, ask=asker("what", "no"))
    assert r["out_answer"] == "no"


def test_gives_up_after_max_asks():
    with pytest.raises(DecisionError, match="after 2 tries"):
        run_decision(node(answers=["yes", "no"], question="ok?", max_asks=2), {}, {}, ask=asker("a", "b"))


def test_free_text_answer():
    assert run_decision(node(question="account number?"), {}, {}, ask=asker("  42 | from the invoice"))["out_note"] == "from the invoice"


def test_timeout_takes_the_default_or_the_timeout_port():
    assert run_decision(node(answers=["yes", "no"], default="no", timeout_s=1, question="?"), {}, {}, ask=asker(None))["out_by"] == "default"
    r = run_decision(node(answers=["yes", "no"], timeout_s=1, question="?"), {}, {}, ask=asker(None))
    assert r["_route"] == "timeout"


def test_nobody_to_ask_uses_the_default_or_says_so(monkeypatch):
    monkeypatch.setattr("graphlang.grafr.decision._tty", lambda: False)
    assert run_decision(node(answers=["yes", "no"], default="no", question="?"), {}, {})["out_answer"] == "no"
    with pytest.raises(DecisionError, match="--answer approve="):
        run_decision(node(answers=["yes", "no"], question="?"), {}, {})


def test_validation_rules():
    ports = ["trigger", "answered", "in_question", "out_answer"]
    ok = lambda **c: check_decision({"id": "d", "type": "DECISION", "config": c, "ports": ports})[0]
    assert ok(question="q", answers=["yes", "no"], default="no") == []
    assert any("not one of" in e for e in ok(question="q", answers=["yes", "no"], default="maybe"))
    assert any("only ['interactive']" in e for e in ok(question="q", mode="park"))
    assert any("decider" in e for e in ok(question="q", decider="model"))
    assert any("positive" in e for e in ok(question="q", timeout_s=-1))
    assert any("timeout_s without a default" in e for e in ok(question="q", timeout_s=5))
    assert any("unknown key" in e for e in ok(question="q", bogus=1))
    assert any("needs a question" in e for e in check_decision({"id": "d", "type": "DECISION", "config": {}, "ports": ["trigger", "answered"]})[0])


def _recipe(tmp_path):
    shutil.copytree(COOKBOOK / "release_approval", tmp_path / "r", ignore=shutil.ignore_patterns("output"))
    return tmp_path / "r" / "release_approval.graph.yaml"


def run(path, answers, **kw):
    graph = load_graph(path)
    errors, warnings = check(graph)
    assert errors == [], errors
    rt = GraphLangRuntime(graph, llm=Scripted(), verbose=False, effects=True)
    rt.answers, rt.answered_by = answers, "wen"
    return rt.execute({"topic": "demo"}), warnings


def test_release_approval_yes_publishes(tmp_path):
    path = _recipe(tmp_path)
    out, _ = run(path, {"approve": "yes"})
    assert out == {"result": "Demo moves to 3pm."}
    assert (path.parent / "output" / "announcement.md").read_text().strip() == "Demo moves to 3pm."


def test_release_approval_no_holds_and_writes_nothing(tmp_path):
    path = _recipe(tmp_path)
    out, _ = run(path, {"approve": "no | too early"})
    assert out["result"] == "held, not released: too early"
    assert not (path.parent / "output" / "announcement.md").exists()


def test_a_defaulted_decision_in_front_of_a_risky_node_is_warned_unless_declared_safe(tmp_path):
    path = _recipe(tmp_path)
    assert run(path, {"approve": "no"})[1] == []                       # the recipe says safe_default: true
    text = "\n".join(l for l in path.read_text().splitlines() if "safe_default" not in l) + "\n"
    path.write_text(text)
    _, warnings = run(path, {"approve": "no"})
    assert any("has a default" in w and "publish" in w for w in warnings)


def test_a_delta_cannot_touch_a_decision_node():
    from graphlang.grafr.runtime import SAFETY_TYPES
    assert "DECISION" in SAFETY_TYPES


def test_cli_answer_option(tmp_path):
    path = _recipe(tmp_path)
    res = CliRunner().invoke(main, ["run", str(path), "--adapter", "mock", "--param", "topic=x", "--answer", "approve=no|later", "--no-log", "--no-output"])
    assert res.exit_code == 0, res.output
    assert "held, not released: later" in res.output.replace("\n", " ") or "later" in res.output


# ---- heartbeat: the same graph run beat after beat, remembering the last count in a file ----------------------------
class Summariser:
    name, adapter_name, model_override = "scripted", "echo", None

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, model=None, **opts):
        self.calls += 1
        return "Priya moved staging; Northwind wants SSO answer."


def _beat(path, llm):
    graph = load_graph(path)
    errors, _ = check(graph)
    assert errors == [], errors
    return GraphLangRuntime(graph, llm=llm, verbose=False, effects=True).execute({})["status"]


def test_heartbeat_reports_new_lines_once_and_then_stays_quiet(tmp_path):
    shutil.copytree(COOKBOOK / "heartbeat", tmp_path / "h", ignore=shutil.ignore_patterns("output"))
    path = tmp_path / "h" / "heartbeat.graph.yaml"
    llm = Summariser()
    assert _beat(path, llm).startswith("new: Priya")
    assert (tmp_path / "h" / "output" / "state.txt").read_text().strip() == "2"
    assert _beat(path, llm) == "nothing new (2 messages)" and llm.calls == 1          # a quiet beat costs no model call
    with open(tmp_path / "h" / "input" / "inbox.md", "a") as f:
        f.write("- 10:15 Ops: disk alert\n")
    assert _beat(path, llm).startswith("new:") and llm.calls == 2
    assert (tmp_path / "h" / "output" / "state.txt").read_text().strip() == "3"
    assert len((tmp_path / "h" / "output" / "alerts.md").read_text().splitlines()) >= 2
