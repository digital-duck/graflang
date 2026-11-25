from click.testing import CliRunner

from graphlang.cli import main

MD = "# Title\n\ntext\n\n```mermaid\n---\nconfig:\n  layout: elk\n---\nflowchart TB\n  A --> B\n```\n"


def test_md2html_writes_page_with_elk_loader(tmp_path):
    src = tmp_path / "a.md"
    src.write_text(MD, encoding="utf-8")
    r = CliRunner().invoke(main, ["util", "md2html", str(src)])
    assert r.exit_code == 0, r.output
    page = (tmp_path / "a.html").read_text(encoding="utf-8")
    assert '<pre class="mermaid">' in page and "layout-elk" in page and "<title>Title</title>" in page


def test_md2html_missing_file(tmp_path):
    r = CliRunner().invoke(main, ["util", "md2html", str(tmp_path / "nope.md")])
    assert r.exit_code != 0
