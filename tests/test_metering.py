"""Run summary, budgets and cassettes (design E9): count what a run did, and run it again without a model."""
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafr.metering import CassetteError, LimitExceeded, MeteredLLM, RecordingLLM, ReplayLLM
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from test_lifecycle import Scripted

COOKBOOK = Path(__file__).parent.parent / "cookbook"
CHAIN = COOKBOOK / "chain_of_thought" / "chain_of_thought.graph.yaml"
CASSETTE = COOKBOOK / "chain_of_thought" / "chain_of_thought.cassette.jsonl"


class Usage(Scripted):
    def last_usage(self):
        return {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.25}


def test_the_meter_counts_calls_tokens_and_cost():
    llm = MeteredLLM(Usage("a", "b"))
    llm.generate("p1")
    llm.generate("p2")
    snap = llm.snapshot()
    assert (snap["calls"], snap["input_tokens"], snap["output_tokens"], snap["cost_usd"]) == (2, 20, 10, 0.5)


def test_the_meter_stops_a_run_at_a_budget():
    with pytest.raises(LimitExceeded, match="max_llm_calls is 1"):
        llm = MeteredLLM(Usage("a", "b"), max_calls=1)
        llm.generate("p1")
        llm.generate("p2")
    llm = MeteredLLM(Usage("a", "b"), max_cost_usd=0.2)
    llm.generate("p1")
    with pytest.raises(LimitExceeded, match="max_cost_usd"):
        llm.generate("p2")


def test_a_recording_replays_without_the_model(tmp_path):
    cassette = tmp_path / "c.jsonl"
    rec = RecordingLLM(Scripted("one", "two"), cassette)
    assert (rec.generate("q1", model="m"), rec.generate("q2", model="m")) == ("one", "two")
    replay = ReplayLLM(cassette)
    assert replay.generate("q2", model="m") == "two" and replay.generate("q1", model="m") == "one"
    with pytest.raises(CassetteError, match="no recording"):
        replay.generate("q3", model="m")
    with pytest.raises(CassetteError, match="no recording"):
        replay.generate("q1", model="other")                         # the model is part of the key


def test_the_same_call_recorded_twice_replays_in_order(tmp_path):
    cassette = tmp_path / "c.jsonl"
    rec = RecordingLLM(Scripted("first", "second"), cassette)
    rec.generate("q"), rec.generate("q")
    replay = ReplayLLM(cassette)
    assert [replay.generate("q"), replay.generate("q"), replay.generate("q")] == ["first", "second", "second"]


def test_a_missing_or_foreign_cassette_is_named(tmp_path):
    (tmp_path / "x.jsonl").write_text('{"nope": 1}\n')
    with pytest.raises(CassetteError, match="not a graflang cassette"):
        ReplayLLM(tmp_path / "x.jsonl")
    with pytest.raises(CassetteError, match="cannot read"):
        ReplayLLM(tmp_path / "absent.jsonl")


def test_the_shipped_cassette_replays_the_chain_with_no_model():
    """cookbook/chain_of_thought was recorded once with claude_cli (claude-sonnet-5-5); CI replays it."""
    runtime = GraphLangRuntime(load_graph(CHAIN), llm=MeteredLLM(ReplayLLM(CASSETTE)), verbose=False)
    out = runtime.execute({"topic": "solar sails"})
    assert len(out["summary"]) > 100
    summary = runtime.summary()
    assert summary["llm"]["calls"] == 3 and set(summary["nodes"]) >= {"gen_1", "gen_2", "gen_3"}
    assert all(row["n"] == 1 for row in summary["nodes"].values())


def test_graf_run_records_replays_and_writes_a_summary(tmp_path):
    graph = tmp_path / "g.graph.yaml"
    graph.write_text(CHAIN.read_text())
    cassette = tmp_path / "run.jsonl"
    out_dir = tmp_path / "out"
    first = CliRunner().invoke(main, ["run", str(graph), "--adapter", "mock", "--param", "topic=x", "--record", str(cassette),
                                      "--no-log", "--output-dir", str(out_dir)])
    assert first.exit_code == 0 and "3 LLM calls" in first.output
    summary = json.loads(next(out_dir.glob("*/summary.json")).read_text())
    assert summary["llm"]["calls"] == 3 and summary["steps"] == 4
    again = CliRunner().invoke(main, ["run", str(graph), "--replay", str(cassette), "--param", "topic=x", "--no-log", "--no-output"])
    assert again.exit_code == 0 and "3 LLM calls" in again.output
    missing = CliRunner().invoke(main, ["run", str(graph), "--replay", str(cassette), "--param", "topic=other", "--no-log", "--no-output"])
    assert missing.exit_code != 0 and "no recording" in missing.output


def test_a_bindings_budget_stops_the_run(tmp_path):
    graph = tmp_path / "g.graph.yaml"
    graph.write_text(CHAIN.read_text())
    bind = tmp_path / "b.yaml"
    bind.write_text("limits: {max_llm_calls: 1}\n")
    result = CliRunner().invoke(main, ["run", str(graph), "--adapter", "mock", "--bind", str(bind), "--no-log", "--no-output"])
    assert result.exit_code != 0 and "max_llm_calls is 1" in result.output
