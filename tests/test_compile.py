"""`graf compile`: one command, `--lang rust|spl`, `--dry-run`, and the same checks as `graf validate` (there is no `graf check`)."""
import pytest
from click.testing import CliRunner

from graphlang.cli import main

COOKBOOK = __import__("pathlib").Path(__file__).parent.parent / "cookbook"
LIFTED = COOKBOOK / "lifted_tool" / "lifted_tool.graph.yaml"
COMPACT = COOKBOOK / "parts_demo" / "parts_demo.graph.yaml"      # a compact file that uses a part

RACE = """version: "1.0-graph"
workflow: {name: race, inputs: [], outputs: [{name: out, type: TEXT}]}
nodes:
  - {id: s, type: INPUT, ports: [entry]}
  - {id: f, type: FORK, ports: [trigger, a, b]}
  - {id: x, type: SOLVE, config: {expression: "'x'"}, ports: [trigger, complete, out_v]}
  - {id: y, type: SOLVE, config: {expression: "'y'"}, ports: [trigger, complete, out_v]}
  - {id: o, type: OUTPUT, ports: [trigger, exit, in_out]}
edges:
  - {source: s.entry, target: f.trigger, type: triggers}
  - {source: f.a, target: x.trigger, type: triggers}
  - {source: f.b, target: y.trigger, type: triggers}
  - {source: x.complete, target: o.trigger, type: triggers}
  - {source: x.out_v, target: o.in_out, type: binds}
  - {source: y.out_v, target: o.in_out, type: binds}
"""


def run(*args):
    return CliRunner().invoke(main, [str(a) for a in args])


def test_check_and_export_spl_are_gone_and_compile_names_its_languages():
    assert run("check", LIFTED).exit_code == 2 and run("export-spl", LIFTED).exit_code == 2
    help_ = run("compile", "--help").output
    assert "--lang" in help_ and "rust" in help_ and "spl" in help_ and "--dry-run" in help_ and "--target" not in help_
    assert run("compile", LIFTED, "--lang", "go").exit_code == 2


def test_spl_prints_the_script_by_default_and_writes_a_file_with_o(tmp_path):
    printed = run("compile", "--lang", "spl", LIFTED)
    assert printed.exit_code == 0 and "CREATE TOOL_API shout" in printed.output and "WORKFLOW w" in printed.output
    out = tmp_path / "w.spl"
    assert run("compile", "--lang", "spl", LIFTED, "-o", out).exit_code == 0 and "WORKFLOW w" in out.read_text()


def test_dry_run_writes_nothing_and_says_so(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "w.spl"
    result = run("compile", "--lang", "spl", LIFTED, "-o", out, "--dry-run")
    assert result.exit_code == 0 and "dry run, nothing written" in result.output and not out.exists()
    assert "WORKFLOW" not in result.output                                        # the script is not printed either
    pytest.importorskip("jinja2")
    result = run("compile", LIFTED, "--dry-run")                                  # rust is the default language
    assert result.exit_code == 0 and "compiles to Rust" in result.output and list(tmp_path.iterdir()) == []


def test_rust_writes_a_project_folder_unless_dry(tmp_path):
    pytest.importorskip("jinja2")
    out = tmp_path / "proj"
    result = run("compile", LIFTED, "-o", out)
    assert result.exit_code == 0 and (out / "Cargo.toml").exists() and "cargo build" in result.output


@pytest.mark.parametrize("lang", ["rust", "spl"])
def test_an_invalid_workflow_is_refused_with_the_validate_messages(tmp_path, lang):
    bad = tmp_path / "race.graph.yaml"
    bad.write_text(RACE)
    result = run("compile", "--lang", lang, bad, "--dry-run")
    assert result.exit_code == 1 and "both write 'o.in_out'" in result.output and "graf validate" in result.output
    assert run("validate", bad).exit_code == 1                                    # the same verdict as validate


def test_compile_reads_files_the_way_run_does(tmp_path):
    result = run("compile", "--lang", "spl", COMPACT, "--dry-run")               # a compact file with a part: `check` could not load it
    assert result.exit_code == 0, result.output


def test_optimize_belongs_to_rust():
    result = run("compile", "--lang", "spl", LIFTED, "--optimize")
    assert result.exit_code == 2 and "--optimize applies to --lang rust only" in result.output


def test_a_missing_file_is_an_error():
    assert run("compile", "nope.graph.yaml").exit_code == 1
