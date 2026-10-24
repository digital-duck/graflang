"""`grafr run --llm ADAPTER[:MODEL]`: one value for --adapter and --model."""
import json
from pathlib import Path

from click.testing import CliRunner

from graphlang.grafr.cli import main

SELF_REFINE = Path(__file__).resolve().parent.parent / "cookbook" / "self_refine" / "self_refine.graph.yaml"


def _run(tmp_path, *flags):
    result = CliRunner().invoke(main, ["run", str(SELF_REFINE), "--param", "topic=ducks", "--log-dir", str(tmp_path),
                                       "--log-format", "jsonl", "--no-output", *flags])
    start = None
    for f in tmp_path.glob("*.jsonl"):
        start = json.loads(f.read_text().splitlines()[0])
    return result, start


def test_llm_sets_adapter_and_model(tmp_path):
    result, start = _run(tmp_path, "--llm", "mock:my-model")
    assert result.exit_code == 0, result.output
    assert start["adapter"] == "mock" and start["model"] == "my-model"


def test_llm_without_model_uses_adapter_default(tmp_path):
    result, start = _run(tmp_path, "--llm", "mock")
    assert result.exit_code == 0, result.output
    assert start["adapter"] == "mock" and start["model"] is None


def test_llm_wins_over_adapter_and_model(tmp_path):
    result, start = _run(tmp_path, "--adapter", "claude_cli", "--model", "claude-x", "--llm", "mock:m2")
    assert result.exit_code == 0, result.output       # would try to call the claude CLI if --adapter won
    assert start["adapter"] == "mock" and start["model"] == "m2"


def test_adapter_and_model_still_work(tmp_path):
    result, start = _run(tmp_path, "--adapter", "mock", "--model", "m3")
    assert result.exit_code == 0, result.output
    assert start["adapter"] == "mock" and start["model"] == "m3"


def test_bad_llm_spec_is_a_usage_error(tmp_path):
    result, _ = _run(tmp_path, "--llm", ":claude-haiku-5-5")
    assert result.exit_code == 2 and "--llm" in result.output and "ADAPTER[:MODEL]" in result.output


def test_model_id_is_in_the_log_file_name(tmp_path):
    result, _ = _run(tmp_path, "--llm", "mock:gemma3:12b")
    assert result.exit_code == 0, result.output
    assert next(tmp_path.glob("*.jsonl")).name.startswith("self_refine-mock-gemma3-12b-")


def test_no_model_leaves_the_log_file_name_as_before(tmp_path):
    result, _ = _run(tmp_path, "--llm", "mock")
    assert next(tmp_path.glob("*.jsonl")).name.startswith("self_refine-mock-2")
