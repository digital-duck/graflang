"""`graf docs` and the doc_it recipe: reading a codebase, assembling and checking a document, the command, and the styles."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.grafd import cli as docs_cli
from graphlang.grafd.cli import cmd_docs

ROOT = Path(__file__).resolve().parent.parent
RECIPE = ROOT / "cookbook" / "doc_it"
STYLES = ROOT / "graphlang" / "grafd" / "styles"


def program(name, job):
    done = subprocess.run([sys.executable, "-I", str(RECIPE / "procedures" / f"{name}.py")], input=json.dumps(job), capture_output=True, text=True)
    return done


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "proj"
    (p / "docs").mkdir(parents=True)
    (p / "src").mkdir()
    (p / "README.md").write_text("# Proj\n\nDoes a thing. Run `proj run`.\n")
    (p / "pyproject.toml").write_text('[project]\nname = "proj"\n')
    (p / "docs" / "guide.md").write_text("# Guide\n\nSee src/main.py.\n")
    (p / "src" / "main.py").write_text("print('hi')\n")
    (p / ".env").write_text("SECRET=1\n")
    (p / "node_modules").mkdir()
    (p / "node_modules" / "x.md").write_text("# not me\n")
    return p


# ---- gather ---------------------------------------------------------------------------------------------------------------
def test_gather_reads_the_project_and_the_style_and_skips_secrets_and_vendored_folders(project):
    done = program("gather", {"source": str(project), "style_guide": str(STYLES / "demo.md")})
    assert done.returncode == 0, done.stderr
    g = json.loads(done.stdout)
    assert g["name"] == "proj" and g["format"] == "html" and g["min_sections"] == 8 and Path(g["template"]).is_file()
    assert g["files"][:2] == ["README.md", "pyproject.toml"] and "docs/guide.md" in g["files"] and "src/main.py" in g["files"]
    assert "SECRET" not in g["digest"] and "not me" not in g["digest"] and ".env" not in g["digest"]
    assert "Run `proj run`" in g["digest"] and "---" not in g["style_guide"].splitlines()[0]


def test_gather_cuts_to_the_budget_and_refuses_a_missing_folder_or_an_empty_guide(project, tmp_path):
    (project / "README.md").write_text("word " * 20000)
    g = json.loads(program("gather", {"source": str(project), "style_guide": "write a faq", "budget": 3000}).stdout)
    assert g["format"] == "markdown" and len(g["digest"]) < 9000 and "[... cut:" in g["digest"]
    assert program("gather", {"source": str(tmp_path / "nope"), "style_guide": "x"}).returncode == 1
    assert program("gather", {"source": str(project), "style_guide": "  "}).returncode == 1
    empty = tmp_path / "empty"
    empty.mkdir()
    assert "no README" in program("gather", {"source": str(empty), "style_guide": "x"}).stderr


def test_gather_does_not_follow_a_link_out_of_the_folder(project, tmp_path):
    (tmp_path / "outside.md").write_text("OUTSIDE SECRET TEXT")
    (project / "docs" / "leak.md").symlink_to(tmp_path / "outside.md")
    g = json.loads(program("gather", {"source": str(project), "style_guide": "x"}).stdout)
    assert "OUTSIDE SECRET TEXT" not in g["digest"]


# ---- assemble -------------------------------------------------------------------------------------------------------------
def gathered(project, style="demo"):
    return program("gather", {"source": str(project), "style_guide": str(STYLES / f"{style}.md")}).stdout


def slides(n, extra=""):
    cover = '<section class="slide"><h1>Proj</h1><aside class="notes">n</aside></section>'
    body = "".join(f'<section class="slide"><h2>Slide {k}</h2><ul><li>point {extra}</li></ul><aside class="notes">n</aside></section>' for k in range(2, n + 1))
    return cover + body


def test_a_deck_is_wrapped_in_the_template_with_an_outline_after_the_cover(project):
    done = program("assemble", {"body": "```html\n" + slides(9) + "\n```", "gathered": gathered(project), "source": str(project)})
    r = json.loads(done.stdout)
    assert r["ok"] and r["sections"] == 9 and not r["errors"]
    doc = r["document"]
    assert doc.count('class="slide"') >= 10 and "{{SLIDES}}" not in doc and "<title>proj</title>" in doc
    assert doc.index("<h1>Proj</h1>") < doc.index('id="outline"') < doc.index("<h2>Slide 2</h2>")
    assert 'id="tocbtn"' in doc


def test_active_content_is_removed_from_the_slides(project):
    evil = slides(9, extra='<img src="http://x.test/a.png"><a href="javascript:alert(1)">x</a>') \
        + "<script>steal()</script><style>*{}</style>"
    evil = evil.replace("<li>", '<li onclick="steal()">', 1)
    r = json.loads(program("assemble", {"body": evil, "gathered": gathered(project), "source": str(project)}).stdout)
    doc = r["document"]
    assert r["ok"] and "steal()" not in doc and "javascript:" not in doc and "x.test" not in doc
    assert any("removed from the slides" in w for w in r["warnings"])


def test_a_deck_with_too_few_slides_or_no_cover_fails_the_check(project):
    r = json.loads(program("assemble", {"body": slides(3), "gathered": gathered(project), "source": str(project)}).stdout)
    assert not r["ok"] and "need at least 8" in r["errors"][0]
    r = json.loads(program("assemble", {"body": "just text", "gathered": gathered(project), "source": str(project)}).stdout)
    assert not r["ok"]


def test_markdown_is_checked_for_title_sections_and_fences(project):
    g = gathered(project, "tutorial")
    good = "# T\n\n" + "".join(f"## Step {k}\n\ntext\n\n```bash\nls\n```\n\n" for k in range(1, 6))
    assert json.loads(program("assemble", {"body": good, "gathered": g, "source": str(project)}).stdout)["ok"]
    bad = json.loads(program("assemble", {"body": "## no title\n```\nopen", "gathered": g, "source": str(project)}).stdout)
    assert not bad["ok"] and len(bad["errors"]) == 3


def test_paths_that_are_not_in_the_source_are_a_warning_and_real_ones_are_not(project):
    g = gathered(project, "tutorial")
    body = "# T\n\n" + "".join(f"## S{k}\n\nSee `src/main.py`, `docs/guide.md`, `README.md` and `src/invented.py`, also `proj run`, `if/else`, `a/b` and `https://x.test/a.b`.\n\n" for k in range(5))
    r = json.loads(program("assemble", {"body": body, "gathered": g, "source": str(project)}).stdout)
    assert r["ok"] and len(r["warnings"]) == 1 and "src/invented.py" in r["warnings"][0] and "src/main.py" not in r["warnings"][0]


def test_the_template_script_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    page = (STYLES / "demo.template.html").read_text()
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    done = subprocess.run([node, "--check", "-"], input=script, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


# ---- the command ----------------------------------------------------------------------------------------------------------
def invoke(*args):
    return CliRunner().invoke(cmd_docs, list(args), catch_exceptions=False)


def test_dry_run_prints_the_plan_and_calls_nothing(project, tmp_path):
    r = invoke(str(project), "--style", "tutorial", "--dry-run", "--out", str(tmp_path / "t.md"))
    assert r.exit_code == 0 and "style        tutorial  (markdown)" in r.output and "3 expected, cap 5" in r.output and "dry run" in r.output
    assert "README.md" in r.output and not (tmp_path / "t.md").exists()


def test_default_output_name_has_the_style_as_its_infix(project, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert f"{tmp_path}/proj.demo.html" in invoke(str(project), "--dry-run").output
    assert f"{tmp_path}/proj.user-guide.html" in invoke(str(project), "--style", "user-guide", "--dry-run").output
    assert f"{tmp_path}/proj.user-guide.md" in invoke(str(project), "--style", "user-guide", "--format", "markdown", "--dry-run").output


def test_custom_needs_a_prompt_and_other_styles_refuse_one(project):
    assert invoke(str(project), "--style", "custom", "--dry-run").exit_code == 2
    assert invoke(str(project), "--style", "demo", "--prompt", "x", "--dry-run").exit_code == 2
    assert invoke(str(project), "--style", "demo", "--format", "markdown", "--dry-run").exit_code == 1      # a deck is html only
    r = invoke(str(project), "--style", "custom", "--prompt", "a one page faq", "--format", "html", "--dry-run")
    assert r.exit_code == 0 and "custom  (html)" in r.output and "proj.custom.html" in r.output


def test_an_existing_output_needs_force_and_a_bad_source_or_cap_is_refused(project, tmp_path):
    out = tmp_path / "o.md"
    out.write_text("old")
    assert "exists" in invoke(str(project), "--style", "tutorial", "--out", str(out), "--dry-run").output
    assert invoke(str(tmp_path / "nope"), "--dry-run").exit_code == 1
    assert "above --max-calls 2" in invoke(str(project), "--max-calls", "2", "--dry-run").output
    assert invoke(str(project), "--ref", "v1", "--dry-run").exit_code == 2


def test_url_detection_and_a_clone_of_a_local_repository(project, tmp_path, monkeypatch):
    assert docs_cli.is_url("https://github.com/o/r") and docs_cli.is_url("git@github.com:o/r.git") and not docs_cli.is_url("./r") and not docs_cli.is_url("/a/b")
    assert docs_cli.repo_name("https://github.com/o/r.git") == "r" and docs_cli.repo_name("git@github.com:o/r") == "r"
    git = ["git", "-C", str(project), "-c", "user.email=a@b.c", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "README.md", "pyproject.toml"], check=True)
    subprocess.run(git + ["commit", "-qm", "x"], check=True)
    monkeypatch.setattr(docs_cli, "work_root", lambda: tmp_path / "work")
    dest = docs_cli.clone(str(project), None)
    assert (dest / "README.md").is_file() and dest.parent == tmp_path / "work"
    assert docs_cli.clone(str(project), None) == dest                   # a second clone replaces the first
    with pytest.raises(Exception, match="git clone failed"):
        docs_cli.clone(str(tmp_path / "not-a-repo"), None)


def test_a_run_with_the_mock_model_flows_through_every_step(project, tmp_path, monkeypatch):
    monkeypatch.setattr(docs_cli, "work_root", lambda: tmp_path / "work")
    r = invoke(str(project), "--llm", "mock", "--out", str(tmp_path / "m.html"))
    assert r.exit_code == 1 and "did not pass the check" in r.output                                 # the mock's text is not a deck
    assert (tmp_path / "m.html").is_file() and "found 0 slide(s)" in r.output
    runs = sorted((tmp_path / "work").glob("run-*/run/*/summary.json"))
    assert json.loads(runs[-1].read_text())["llm"]["calls"] == 3         # outline, write, fix: the failed check sent it to the fix once


def test_the_styles_are_files_with_a_format_and_the_demo_template_exists():
    for name, fmt in (("demo", "html"), ("tutorial", "markdown"), ("user-guide", "markdown")):
        text = (STYLES / f"{name}.md").read_text()
        assert re.search(rf"^format: {fmt}$", text, re.M) and "source digest" in text
    assert "{{PROMPT}}" in (STYLES / "custom.md").read_text() and "{{SLIDES}}" in (STYLES / "demo.template.html").read_text()


# ---- Contents with links, and Markdown to HTML (graf docs tutorial|user-guide with an .html name) ----

def _assemble_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("doc_it_assemble", Path(__file__).resolve().parent.parent / "cookbook/doc_it/procedures/assemble.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DOC = "# T\n\nintro\n\n## One\n\n```\n## not a heading\n```\n\n### Sub `x`\n\n## Two\n\n## Two\n\n## Three: it's\n"


def test_add_toc_inserts_linked_contents_and_dedupes():
    out = _assemble_mod().add_toc(DOC)
    assert "## Contents\n\n- [One](#one)\n  - [Sub `x`](#sub-x)\n- [Two](#two)\n- [Two](#two-1)\n- [Three: it's](#three-its)\n" in out
    assert "not a heading" not in out.split("## One")[0]


def test_add_toc_fills_the_writers_own_contents():
    doc = "# T\n\n## Contents\n\n- One\n- Two\n\n## One\n\n## Two\n\n## Three\n"
    out = _assemble_mod().add_toc(doc)
    assert out.count("## Contents") == 1 and "- [One](#one)" in out and "- One\n" not in out
    assert "[Contents]" not in out


def test_add_toc_leaves_short_documents():
    assert _assemble_mod().add_toc("# T\n\n## A\n\n## B\n") == "# T\n\n## A\n\n## B\n"


def test_md2html_links_match_ids_and_escapes():
    from graphlang.grafd.md2html import convert
    page = convert(_assemble_mod().add_toc(DOC) + "\n| a | b |\n|---|---|\n| `<x>` | **y** |\n\n<script>alert(1)</script>\n\n[bad](javascript:alert(1))\n")
    assert page.startswith("<!DOCTYPE html>") and '<h2 id="two-1">' in page and 'href="#two-1"' in page
    assert "<table>" in page and "<code>&lt;x&gt;</code>" in page and "<strong>y</strong>" in page
    assert "<script>" not in page and "javascript:" not in page


def test_html_name_on_a_markdown_style_is_kept(project, tmp_path):
    r = invoke(str(project), "--style", "tutorial", "--dry-run", "--out", str(tmp_path / "t.htm"))
    assert r.exit_code == 0 and str(tmp_path / "t.htm") in r.output and "note:" not in r.output


def test_md2html_renders_mermaid_blocks():
    from graphlang.grafd.md2html import convert
    page = convert("# T\n\n## Architecture\n\n```mermaid\nflowchart LR\n  A[\"a <b>\"] --> B\n```\n")
    assert '<pre class="mermaid">flowchart LR' in page and "mermaid.esm.min.mjs" in page and "a &lt;b&gt;" in page
    assert "mermaid.esm" not in convert("# T\n\n```py\nx\n```\n")


def test_path_check_skips_names_that_appear_in_the_source(tmp_path):
    (tmp_path / "README.md").write_text("The run writes `output/run-1/report.yaml` for each job.\n")
    (tmp_path / "old.tutorial.md").write_text("see `ghost/made-up.yaml`")
    got = _assemble_mod().paths_not_found("`output/run-1/report.yaml` `ghost/made-up.yaml` `README.md`", tmp_path)
    assert got == ["ghost/made-up.yaml"]


def test_several_styles_go_to_one_folder(project, tmp_path):
    out = tmp_path / "docs" / "graf-docs"
    r = invoke(str(project), "--style", "demo,tutorial,user-guide", "--out-dir", str(out), "--dry-run")
    assert r.exit_code == 0 and r.output.count("== ") == 3 and r.output.count("dry run") == 3
    for n in ("proj.demo.html", "proj.tutorial.html", "proj.user-guide.html"):
        assert str(out / n) in r.output
    assert invoke(str(project), "--style", "demo,tutorial", "--out", str(tmp_path / "x.html"), "--dry-run").exit_code == 2
    assert invoke(str(project), "--style", "tutorial,nope", "--dry-run").exit_code == 2


def test_markdown_format_skips_the_deck_among_several_and_reports_it(project, tmp_path):
    r = CliRunner().invoke(cmd_docs, [str(project), "--style", "demo,tutorial", "--format", "markdown", "--out-dir", str(tmp_path), "--dry-run"])
    assert r.exit_code == 1 and "only comes as html" in r.output and str(tmp_path / "proj.tutorial.md") in r.output and "not written: demo" in r.output


def test_name_flag_sets_file_names_and_is_cleaned(project, tmp_path):
    r = invoke(str(project), "--style", "tutorial,demo", "--name", "My Proj/v2", "--out-dir", str(tmp_path), "--dry-run")
    assert r.exit_code == 0 and str(tmp_path / "My-Proj-v2.tutorial.html") in r.output and str(tmp_path / "My-Proj-v2.demo.html") in r.output
    assert invoke(str(project), "--name", "///", "--dry-run").exit_code == 2
    assert "proj.demo.html" in invoke(str(project), "--out-dir", str(tmp_path), "--dry-run").output


def test_gather_reads_every_coding_agents_instruction_file(tmp_path):
    (tmp_path / "README.md").write_text("# p\n")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text("COPILOT-RULES")
    for n, t in (("CLAUDE.md", "CLAUDE-RULES"), ("GEMINI.md", "GEMINI-RULES"), ("codex.md", "CODEX-RULES"), ("AGENTS.md", "AGENTS-RULES"), (".cursorrules", "CURSOR-RULES")):
        (tmp_path / n).write_text(t)
    job = json.dumps({"source": str(tmp_path), "style_guide": str(docs_cli.STYLES_DIR / "tutorial.md"), "budget": 60000})
    out = subprocess.run([sys.executable, "-I", str(Path(docs_cli.__file__).resolve().parents[2] / "cookbook/doc_it/procedures/gather.py")], input=job, capture_output=True, text=True)
    d = json.loads(out.stdout)["digest"]
    for t in ("CLAUDE-RULES", "GEMINI-RULES", "CODEX-RULES", "AGENTS-RULES", "CURSOR-RULES", "COPILOT-RULES"):
        assert t in d
