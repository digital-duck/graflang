"""`graf viz` is an alias of `graf vis`."""
from pathlib import Path

from click.testing import CliRunner

from graphlang.cli import main

GRAPH = Path(__file__).resolve().parent.parent / "cookbook" / "self_refine" / "self_refine.graph.yaml"


def test_viz_and_vis_draw_the_same_graph(tmp_path):
    a, b = tmp_path / "a.html", tmp_path / "b.html"
    r1 = CliRunner().invoke(main, ["vis", "--no-open", "-o", str(a), str(GRAPH)])
    r2 = CliRunner().invoke(main, ["viz", "--no-open", "-o", str(b), str(GRAPH)])
    assert r1.exit_code == 0 and r2.exit_code == 0, (r1.output, r2.output)
    assert a.read_text() == b.read_text()


def test_help_names_the_alias_on_the_vis_line_and_viz_help_works():
    listing = CliRunner().invoke(main, ["--help"]).output
    assert " vis " in listing and "(alias: viz)" in listing and "\n  viz " not in listing
    assert CliRunner().invoke(main, ["viz", "--help"]).exit_code == 0


def test_every_command_has_a_complete_one_line_summary_in_help():
    """No truncated summaries ("...") in `graf --help`: each command sets its own short_help."""
    result = CliRunner().invoke(main, ["--help"], terminal_width=80)
    listing = result.output.split("Commands:")[1]
    assert "..." not in listing and "…" not in listing
    for name, cmd in main.commands.items():
        if not cmd.hidden:
            assert cmd.short_help and name in listing


def test_help_links_to_the_base_package():
    out = CliRunner().invoke(main, ["--help"], terminal_width=80).output
    assert "https://www.piwheels.org/project/zinet/" in out
