from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafu.cli import DELEGATED


def test_util_lists_own_and_delegated_commands_without_importing_spl3():
    out = CliRunner().invoke(main, ["util", "-h"], terminal_width=100).output
    for name in ("clean-port", "html2pdf", "md2pdf", "mmd2img", *DELEGATED):
        assert name in out
    assert "..." not in out.replace("[OPTIONS] COMMAND [ARGS]...", "")


def test_mmd2img_html_and_clean_port_dry_run(tmp_path):
    mmd = tmp_path / "t.mmd"
    mmd.write_text("flowchart TD\n A-->B\n")
    r = CliRunner()
    assert r.invoke(main, ["util", "mmd2img", str(mmd), "-f", "html"]).exit_code == 0
    assert (tmp_path / "t.html").is_file()
    res = r.invoke(main, ["util", "clean-port", "--dry-run", "65431"])
    assert res.exit_code == 0 and "nothing listening" in res.output
