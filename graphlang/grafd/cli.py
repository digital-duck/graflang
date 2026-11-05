"""`graf docs`: write a document about a codebase (a folder or a repository url) in a chosen style.

    graf docs . --style demo                                     # a slide deck: graflang.demo.html
    graf docs https://github.com/org/repo --style tutorial       # cloned to the temp area first: repo.tutorial.md
    graf docs ./proj --style custom --prompt "a one-page FAQ"    # your own instructions (--prompt TEXT or @FILE); --format markdown|html

It runs the `cookbook/doc_it` recipe: a program reads the codebase into a digest, a model plans and writes, a program assembles and checks the
page, and a model fixes it once if the check fails. The styles are files (`graphlang/grafd/styles/*.md`): edit them to change a style.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

import click

STYLES_DIR = Path(__file__).resolve().parent / "styles"
STYLES = ("demo", "tutorial", "user-guide", "custom")
URL = re.compile(r"^(https?://|git@|ssh://|git://)|\.git$")


def work_root() -> Path:
    return Path(tempfile.gettempdir()) / "graflang-docs"


def is_url(source: str) -> bool:
    return bool(URL.search(source))


def repo_name(url: str) -> str:
    return re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1].split(":")[-1]) or "repo"


def clone(url: str, ref: Optional[str]) -> Path:
    """Shallow-clone `url` into the temp area (a fresh copy each time) and return the folder."""
    dest = work_root() / f"{repo_name(url)}-{hashlib.sha1((url + (ref or '')).encode()).hexdigest()[:8]}"
    if dest.exists():
        shutil.rmtree(dest)                                  # only ever a folder this function made under work_root()
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1"] + (["--branch", ref] if ref else []) + ["--", url, str(dest)]
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        raise click.ClickException(f"git clone failed: {(done.stderr or done.stdout).strip().splitlines()[-1] if (done.stderr or done.stdout).strip() else 'no output'}")
    return dest


def find_recipe() -> Path:
    """The doc_it recipe: the repository's cookbook, else the work area's copy (~/.graflang/cookbook)."""
    here = Path(__file__).resolve().parents[2] / "cookbook" / "doc_it" / "doc_it.graph.yaml"
    if here.is_file():
        return here
    from ..workspace import default_src_dir
    other = default_src_dir() / "doc_it" / "doc_it.graph.yaml"
    if other.is_file():
        return other
    raise click.ClickException("cannot find the doc_it recipe (cookbook/doc_it); install graflang from the repository, or copy the recipe to ~/.graflang/cookbook")


def style_file(style: str, prompt: Optional[str], fmt: Optional[str], folder: Path) -> Tuple[Path, str]:
    """The style file to give the recipe, and its format. A built-in style is used as it is; `custom` is built from --prompt."""
    if style != "custom":
        if prompt:
            raise click.UsageError("--prompt goes with --style custom")
        path = STYLES_DIR / f"{style}.md"
        got = re.search(r"^format:\s*(\w+)", path.read_text(encoding="utf-8"), re.M)
        return path, got.group(1) if got else "markdown"
    if not prompt:
        raise click.UsageError("--style custom needs --prompt TEXT (or --prompt @FILE) saying how the document should be built and structured")
    text = Path(prompt[1:]).expanduser().read_text(encoding="utf-8") if prompt.startswith("@") else prompt
    fmt = fmt or "markdown"
    body = (STYLES_DIR / "custom.md").read_text(encoding="utf-8").replace("{{PROMPT}}", text.strip())
    path = folder / "custom.md"
    path.write_text(f"---\nformat: {fmt}\nmin_sections: 2\n---\n{body}", encoding="utf-8")
    return path, fmt


def run_gather(recipe: Path, source: Path, guide: Path, budget: int) -> dict:
    job = json.dumps({"source": str(source), "style_guide": str(guide), "budget": budget})
    done = subprocess.run([sys.executable, "-I", str(recipe.parent / "procedures" / "gather.py")], input=job, capture_output=True, text=True)
    if done.returncode != 0:
        raise click.ClickException((done.stderr or "gather failed").strip())
    return json.loads(done.stdout)


@click.command("docs", short_help="Write a document (deck, tutorial, user guide, or your own) about a codebase.")
@click.argument("source")
@click.option("--style", type=click.Choice(STYLES), default="demo", show_default=True, help="demo: a slide deck (HTML); tutorial, user-guide: Markdown; custom: your --prompt")
@click.option("--prompt", default=None, help="with --style custom: how the document should be built and structured (text, or @FILE)")
@click.option("--format", "fmt", type=click.Choice(["markdown", "html"]), default=None, help="with --style custom: markdown (default) or html (a PDF is one print away)")
@click.option("--out", "-o", default=None, help="the file to write (default ./<name>.<style>.html|md)")
@click.option("--force", is_flag=True, help="overwrite --out if it exists")
@click.option("--ref", default=None, help="for a repository url: the branch or tag to clone")
@click.option("--llm", "llm", default=None, metavar="ADAPTER[:MODEL]", help="the model (default: graf run's default, claude_cli with claude-sonnet-5-5; billed)")
@click.option("--budget", type=int, default=60000, show_default=True, help="characters of the source to put in the digest")
@click.option("--margin", type=float, default=0.5, show_default=True, help="safety margin on the model-call cap (cap = ceil(calls x (1 + margin)))")
@click.option("--max-calls", type=int, default=None, help="refuse to run when the cap on model calls is above this")
@click.option("--dry-run", is_flag=True, help="read the codebase and print the plan (files, size, model calls, output file); no model is called")
def cmd_docs(source, style, prompt, fmt, out, force, ref, llm, budget, margin, max_calls, dry_run):
    """Write a document about SOURCE (a folder or a repository url) in a style."""
    from ..grafr import partinfo
    from ..grafr.runtime import load_graph

    recipe = find_recipe()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = work_root() / f"run-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    if is_url(source):
        if dry_run:
            click.echo(f"(cloning {source} into {work_root()} to read it)")
        root = clone(source, ref)
    else:
        if ref:
            raise click.UsageError("--ref goes with a repository url")
        root = Path(source).expanduser().resolve()
        if not root.is_dir():
            raise click.ClickException(f"no such folder: {source}")
    guide, kind = style_file(style, prompt, fmt, folder)
    if fmt and style != "custom":
        raise click.UsageError("--format goes with --style custom (the other styles have their own format)")
    name = root.name
    ext = "html" if kind == "html" else "md"
    target = Path(out) if out else Path.cwd() / f"{name}.{style}.{ext}"
    if target.exists() and not force:
        raise click.ClickException(f"{target} exists (use --force to overwrite, or --out FILE)")

    caps = partinfo.capabilities(load_graph(recipe).get("nodes", []))
    calls, cap = caps["llm_calls"], partinfo.suggested_cap(caps["llm_calls"], margin)
    info = run_gather(recipe, root, guide, budget)
    click.echo("plan")
    click.echo(f"  source       {root}" + (f"  (cloned from {source})" if is_url(source) else ""))
    click.echo(f"  style        {style}  ({kind})")
    click.echo(f"  reads        {len(info['files'])} file(s), {len(info['digest'])} characters of digest")
    click.echo(f"  model calls  {calls} expected, cap {cap}")
    click.echo(f"  writes       {target}")
    if max_calls is not None and cap > max_calls:
        raise click.ClickException(f"the cap {cap} is above --max-calls {max_calls}")
    if dry_run:
        click.echo("dry run: nothing was run")
        for f in info["files"]:
            click.echo(f"    {f}")
        return

    bind = folder / "limits.bind.yaml"
    bind.write_text(f"limits:\n  max_llm_calls: {cap}\n  max_steps: 80\n  wall_time_s: 1800\n")
    cmd = [sys.executable, "-m", "graphlang", "run", str(recipe), "--bind", str(bind), "--output-dir", str(folder / "run"),
           "--param", f"source={root}", "--param", f"style_guide={guide}", "--param", f"budget={budget}"] + (["--llm", llm] if llm else [])
    click.echo(f"running ({calls} model calls expected, cap {cap}) ...")
    done = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if done.returncode != 0:
        raise click.ClickException(f"the run failed (folder {folder / 'run'}):\n" + "\n".join(done.stdout.strip().splitlines()[-12:]))
    results = sorted((folder / "run").glob("*/result.json"))
    if not results:
        raise click.ClickException(f"the run gave no result.json in {folder / 'run'}")
    result = json.loads(results[-1].read_text(encoding="utf-8")).get("result")
    result = json.loads(result) if isinstance(result, str) else result
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result["document"], encoding="utf-8")
    for w in result.get("warnings", []):
        click.echo(f"warning: {w}")
    for e in result.get("errors", []):
        click.echo(f"error: {e}")
    click.echo(f"wrote {target}  ({result.get('sections', 0)} sections; run folder {folder / 'run'})")
    if not result.get("ok"):
        raise click.ClickException("the document was written but it did not pass the check (see the errors above)")
