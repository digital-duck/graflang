"""grafr run results: <graph folder>/output/<run>/ holds the workflow outputs (and, with --save-nodes, every node's
output); LLM text never goes to the log."""
import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.logging_config import disable_logging

SELF_REFINE_DIR = Path(__file__).resolve().parent.parent / "cookbook" / "self_refine"


@pytest.fixture
def app(tmp_path):
    """A copy of the self_refine app, so output/ lands in tmp_path."""
    dest = tmp_path / "app"
    shutil.copytree(SELF_REFINE_DIR, dest, ignore=shutil.ignore_patterns("output", ".grafr", "__pycache__"))
    yield dest
    disable_logging()


def run(app, *extra, log_dir=None):
    args = ["run", str(app / "self_refine.graph.yaml"), "--adapter", "mock", "--param", "topic=ducks",
            "--log-dir", str(log_dir or app.parent / "logs"), *extra]
    return CliRunner().invoke(main, args)


def run_dirs(root):
    return sorted(p for p in root.iterdir() if p.is_dir())


def test_default_output_dir_is_next_to_the_graph(app):
    result = run(app)
    assert result.exit_code == 0, result.output
    (run_dir,) = run_dirs(app / "output")
    assert run_dir.name.startswith("self_refine-mock-")
    assert json.loads((run_dir / "result.json").read_text())["essay"].startswith("[Mock LLM response")
    assert (run_dir / "essay.md").read_text().startswith("[Mock LLM response")
    assert not (run_dir / "nodes").exists()
    assert f"output: {run_dir}" in result.output.replace("\n", "")


def test_output_dir_flag(app, tmp_path):
    result = run(app, "--output-dir", str(tmp_path / "elsewhere"))
    assert result.exit_code == 0, result.output
    assert len(run_dirs(tmp_path / "elsewhere")) == 1 and not (app / "output").exists()


def test_no_output_writes_nothing(app):
    assert run(app, "--no-output").exit_code == 0
    assert not (app / "output").exists()


def test_save_nodes_writes_each_nodes_output_in_firing_order(app):
    assert run(app, "--save-nodes").exit_code == 0
    (run_dir,) = run_dirs(app / "output")
    names = sorted(p.name for p in (run_dir / "nodes").iterdir())
    assert names[0].startswith("001-") and any("draft.out_essay.md" in n for n in names)
    assert any("critique.out_feedback.md" in n for n in names) and any("refine.out_essay.md" in n for n in names)


def test_llm_text_is_in_output_files_not_in_the_log(app):
    assert run(app, "--save-nodes", "--log-format", "jsonl", "--log-level", "info").exit_code == 0
    (log,) = (app.parent / "logs").glob("*.jsonl")
    text = log.read_text()
    assert "Mock LLM response" not in text                       # bodies stay out of the log
    events = [json.loads(line) for line in text.splitlines()]
    saved = [e for e in events if e.get("event") == "node.saved"]
    assert saved and all(Path(e["file"]).is_file() for e in saved)
    out = next(e for e in events if e.get("event") == "run.output")
    assert Path(out["dir"]) == run_dirs(app / "output")[0] and "result.json" in out["files"]


def test_failed_run_writes_no_result_files(app):
    result = CliRunner().invoke(main, ["run", str(app / "self_refine.graph.yaml"), "--adapter", "mock",
                                       "--log-dir", str(app.parent / "logs")])       # required --param missing
    assert result.exit_code != 0
    assert not (app / "output").exists()
