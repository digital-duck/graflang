"""grafr logging: run/node/loop/mutate/guard events reach the dd-logging JSONL file; the CLI wires the options."""
import json
import logging
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.logging_config import active_settings, disable_logging, setup_logging

ROOT = Path(__file__).resolve().parent.parent
SELF_REFINE = ROOT / "cookbook" / "self_refine" / "self_refine.graph.yaml"


@pytest.fixture(autouse=True)
def _quiet():
    yield
    disable_logging()


def _records(path: Path):
    for h in logging.getLogger("graflang").handlers:
        h.flush()
    return [json.loads(line) for line in path.read_text().splitlines()]


def _events(path: Path, name=None):
    return [r for r in _records(path) if "event" in r and (name is None or r["event"] == name)]


def test_run_emits_lifecycle_and_node_events(tmp_path):
    path = setup_logging("t", log_dir=tmp_path, log_format="jsonl", log_level="debug")
    graph = load_graph(SELF_REFINE)
    rt = GraphLangRuntime(graph, verbose=False)
    rt.execute({"topic": "ducks"})
    names = [e["event"] for e in _events(path)]
    assert names[0] == "run.start" and names[-1] == "run.end"
    assert "node.fire" in names and "node.done" in names and "llm.call" in names
    end = _events(path, "run.end")[0]
    assert end["steps"] == rt.steps and end["workflow"] == graph["workflow"]["name"]
    done = _events(path, "node.done")
    assert all(d["logger"] == "graflang.grafr.runtime" and d["ms"] >= 0 for d in done)


def test_info_level_hides_debug_events(tmp_path):
    path = setup_logging("t", log_dir=tmp_path, log_format="jsonl", log_level="info")
    graph = load_graph(SELF_REFINE)
    GraphLangRuntime(graph, verbose=False).execute({"topic": "ducks"})
    names = {e["event"] for e in _events(path)}
    assert "node.fire" not in names and "llm.text" not in names and "node.done" in names


def test_failure_logs_run_fail_and_node_error(tmp_path):
    path = setup_logging("t", log_dir=tmp_path, log_format="jsonl")
    graph = {"workflow": {"name": "bad"},
             "nodes": [{"id": "a", "type": "EVALUATE", "ports": ["trigger", "pass", "fail"], "config": {}}],
             "edges": []}
    with pytest.raises(ValueError):
        GraphLangRuntime(graph, verbose=False).execute({})
    assert _events(path, "node.error") or _events(path, "run.fail")
    assert _events(path, "run.fail")[0]["level"] == "ERROR"


def test_library_use_is_silent_without_setup(capsys):
    graph = load_graph(SELF_REFINE)
    GraphLangRuntime(graph, verbose=False).execute({"topic": "ducks"})
    assert capsys.readouterr().err == ""
    assert active_settings() is None


def test_cli_writes_text_and_jsonl_by_default(tmp_path):
    result = CliRunner().invoke(main, ["run", str(SELF_REFINE), "--adapter", "mock", "--param", "topic=ducks", "--no-output", "--log-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".jsonl", ".log"]
    jsonl = next(tmp_path.glob("*.jsonl"))
    assert [json.loads(l)["event"] for l in jsonl.read_text().splitlines()][0] == "run.start"
    assert "log:" in result.output


def test_cli_no_log_writes_nothing(tmp_path):
    result = CliRunner().invoke(main, ["run", str(SELF_REFINE), "--adapter", "mock", "--param", "topic=ducks", "--no-output", "--no-log", "--log-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert list(tmp_path.iterdir()) == []


def test_cli_default_dir_is_graflang_logs_in_home(tmp_path, monkeypatch):
    monkeypatch.delenv("DD_LOG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["run", str(SELF_REFINE), "--adapter", "mock", "--param", "topic=ducks", "--no-output", "--log-format", "jsonl"])
    assert result.exit_code == 0, result.output
    assert len(list((tmp_path / ".graflang" / "logs").glob("self_refine-mock-*.jsonl"))) == 1
    assert not (SELF_REFINE.parent / ".grafr").exists()


def test_cli_log_dir_can_be_the_current_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("DD_LOG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["run", str(SELF_REFINE), "--adapter", "mock", "--param", "topic=ducks", "--no-output", "--log-dir", ".", "--log-format", "jsonl"])
    assert result.exit_code == 0, result.output
    assert len(list(tmp_path.glob("self_refine-mock-*.jsonl"))) == 1


def test_cli_env_var_beats_the_default_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DD_LOG_DIR", str(tmp_path / "envlogs"))
    result = CliRunner().invoke(main, ["run", str(SELF_REFINE), "--adapter", "mock", "--param", "topic=ducks", "--no-output", "--log-format", "jsonl"])
    assert result.exit_code == 0, result.output
    assert len(list((tmp_path / "envlogs").glob("*.jsonl"))) == 1


def test_procedure_run_shares_log_settings_with_spl(tmp_path):
    pytest.importorskip("spl3.logging_config", reason="needs an SPL.py with dd-logging support")
    from graphlang.grafr.procedures import _start_spl_logging
    setup_logging("g", log_dir=tmp_path, log_format="jsonl")
    spl_log = _start_spl_logging(Path("flow.spl"))
    try:
        assert spl_log.parent == tmp_path.resolve() and spl_log.name.startswith("spl-flow-")
        assert spl_log.suffix == ".jsonl"
    finally:
        from spl3.logging_config import disable_logging as spl_disable
        spl_disable()
        logging.getLogger("spl").propagate = True


def test_procedure_run_without_graflang_logging_starts_no_spl_log():
    from graphlang.grafr.procedures import _start_spl_logging
    assert _start_spl_logging(Path("flow.spl")) is None
