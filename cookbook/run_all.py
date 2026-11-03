#!/usr/bin/env python3
"""run_all.py: the GraphLang cookbook runner. The recipes live in cookbook_catalog.yaml; edit that
file to add, remove or change a recipe, not this script.

  conda activate graf
  python cookbook/run_all.py --list                         # what is in the catalog
  python cookbook/run_all.py --list --suite solvers --status lifted
  python cookbook/run_all.py --check                        # does this machine have what the recipes need?
  python cookbook/run_all.py --validate                     # `graf validate` every selected graph (offline, free)
  python cookbook/run_all.py --run --ids 'pocketflow.*'     # `graf run` them for real (calls a model)
  python cookbook/run_all.py --run --llm claude_cli:claude-haiku-5-5 --workers 4 --suite cookbook
  python cookbook/run_all.py --write-readme                 # regenerate the tables in cookbook/README.md

Selecting: --suite, --category, --status, --needs, --ids (comma-separated shell globs on the id), --all
(include entries with `active: false`, e.g. those that wait for keyboard input).
Results of a --run go to cookbook/logs/<stamp>/ (one log per recipe, plus results.yaml).
"""
from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import click
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CATALOG = HERE / "cookbook_catalog.yaml"
DEFAULT_LLM = "claude_cli:claude-sonnet-5-5"
SUITES = {"cookbook": "cookbook", "pocketflow": "cookbook_pocketflow", "solvers": "cookbook_solvers"}
MARK = {"validated": "✅", "ran": "☑️", "lifted": "🔁", "new": "🆕", "broken": "❌"}
BEGIN, END = "<!-- catalog:begin -->", "<!-- catalog:end -->"


def graf_bin() -> str:
    cand = Path(sys.executable).parent / "graf"
    return str(cand) if cand.exists() else (shutil.which("graf") or "graf")


def load(path: Path = CATALOG) -> list[dict]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))["entries"]
    ids = [e["id"] for e in entries]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise click.ClickException(f"duplicate ids in the catalog: {sorted(dup)}")
    for e in entries:
        if not (ROOT / e["graph"]).exists():
            raise click.ClickException(f"{e['id']}: graph not found: {e['graph']}")
    return entries


def select(entries, suite, category, status, needs, ids, include_all):
    def want(e):
        if suite and e["suite"] not in suite.split(","):
            return False
        if category and e.get("category") not in category.split(","):
            return False
        if status and e.get("status") not in status.split(","):
            return False
        if needs and not set(needs.split(",")) <= set(e.get("needs", [])):
            return False
        if ids and not any(fnmatch.fnmatch(e["id"], p.strip()) for p in ids.split(",")):
            return False
        return include_all or ids or e.get("active", True)
    return [e for e in entries if want(e)]


def command(e: dict, llm: str, max_steps: int | None) -> list[str]:
    cmd = [graf_bin(), "run", e["graph"]]
    if "llm" in e.get("needs", []):
        cmd += ["--llm", llm]
    if e.get("bind"):
        cmd += ["--bind", e["bind"]]
    if max_steps:
        cmd += ["--max-steps", str(max_steps)]
    cmd += [str(a) for a in e.get("args", [])]
    for k, v in (e.get("params") or {}).items():
        cmd += ["--param", f"{k}={v}"]
    return cmd


# ── checks ────────────────────────────────────────────────────────────────────

def check_needs(entries) -> list[str]:
    wanted = {n for e in entries for n in e.get("needs", [])}
    problems = []
    def have(label, ok, hint):
        mark = "ok     " if ok else "MISSING"
        print(f"  {mark} {label}" + ("" if ok else f"   ({hint})"))
        if not ok:
            problems.append(label)
    print(f"{len(entries)} recipes selected; they use: {', '.join(sorted(wanted)) or 'nothing external'}")
    have("graf", Path(graf_bin()).exists() or bool(shutil.which("graf")), "conda activate graf")
    if "llm" in wanted:
        have("claude CLI (claude_cli adapter)", bool(shutil.which("claude")), "install Claude Code, or run with --llm ollama:MODEL")
    if "kernel" in wanted or "sagemath" in wanted:
        have("jupyter_client + ipykernel", _can_import("jupyter_client") and _can_import("ipykernel"), "pip install 'graflang[kernel]'")
    if "sagemath" in wanted:
        r = subprocess.run([sys.executable, "-m", "jupyter", "kernelspec", "list"], capture_output=True, text=True)
        have("sagemath kernel", "sagemath" in r.stdout, "jupyter kernelspec list")
    if "spl" in wanted:
        have("SPL.py importable (procedure_ref)", _can_import("spl3"), "pip install 'graflang[spl]'")
    return problems


def _can_import(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


# ── one recipe ────────────────────────────────────────────────────────────────

def run_one(e, cmd, log: Path, timeout: int) -> dict:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        out, rc = (p.stdout or "") + (p.stderr or ""), p.returncode
    except subprocess.TimeoutExpired as exc:
        out, rc = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), -9
        out += f"\nTIMEOUT after {timeout}s"
    log.write_text("$ " + " ".join(cmd) + "\n\n" + out, encoding="utf-8")
    m = re.search(r"(\d+) steps · (\d+) LLM calls?, (\d+) tokens in / (\d+) out", out)
    return {"id": e["id"], "ok": rc == 0, "rc": rc, "seconds": round(time.time() - t0, 1),
            "steps": int(m[1]) if m else None, "llm_calls": int(m[2]) if m else None,
            "tokens_in": int(m[3]) if m else None, "tokens_out": int(m[4]) if m else None,
            "log": str(log.relative_to(ROOT))}


# ── README tables ─────────────────────────────────────────────────────────────

def tables(entries) -> str:
    names = {"cookbook": "Core recipes (`cookbook/`)", "pocketflow": "PocketFlow recipes (`cookbook_pocketflow/`)",
             "solvers": "Solver recipes (`cookbook_solvers/`)"}
    out = []
    for s, title in names.items():
        es = [e for e in entries if e["suite"] == s]
        if not es:
            continue
        counts = {k: sum(1 for e in es if e.get("status") == k) for k in MARK}
        out.append(f"### {title}: {len(es)} graphs\n\n" + ", ".join(f"{MARK[k]} {n} {k}" for k, n in counts.items() if n) + "\n")
        out.append("| Recipe | Graph | Shows | Needs | Status |\n|---|---|---|---|---|")
        for e in es:
            link = f"[`{e['graph'].split('/', 1)[1]}`](../{e['graph']})"
            needs = e.get("requires") or ", ".join(e.get("needs", [])) or "nothing external"
            st = MARK.get(e["status"], "") + " " + e["status"] + (f" ({e['validated']})" if e.get("validated") else "")
            out.append(f"| `{e['id'].split('.', 1)[1]}` | {link} | {e.get('description', '').replace('|', '/')} | {needs.replace('|', '/')} | {st} |")
        out.append("")
    return "\n".join(out)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--catalog", "catalog_file", default=str(CATALOG), show_default=True)
@click.option("--list", "do_list", is_flag=True, help="List the selected recipes.")
@click.option("--check", is_flag=True, help="Check this machine has what the selected recipes need.")
@click.option("--validate", "do_validate", is_flag=True, help="`graf validate` the selected graphs (no model, free).")
@click.option("--run", "do_run", is_flag=True, help="`graf run` the selected graphs (calls models).")
@click.option("--write-readme", is_flag=True, help="Regenerate the tables in cookbook/README.md from the catalog.")
@click.option("--markdown", is_flag=True, help="Print the README tables to stdout.")
@click.option("--suite", default="", help="cookbook,pocketflow,solvers")
@click.option("--category", default="")
@click.option("--status", default="", help="validated,ran,lifted,new,broken")
@click.option("--needs", default="", help="recipes that need all of: llm,kernel,sagemath,spl,stdin")
@click.option("--ids", default="", help="comma-separated globs on the id, e.g. 'pocketflow.*,solvers.lean_*'")
@click.option("--all", "include_all", is_flag=True, help="include entries with active: false")
@click.option("--llm", default=DEFAULT_LLM, show_default=True, help="ADAPTER[:MODEL] for recipes that call a model")
@click.option("--workers", default=1, show_default=True, help="recipes run at once")
@click.option("--timeout", default=600, show_default=True, help="seconds per recipe")
@click.option("--max-steps", default=None, type=int, help="pass --max-steps to graf run")
@click.option("--dry-run", is_flag=True, help="print the commands, run nothing")
def main(catalog_file, do_list, check, do_validate, do_run, write_readme, markdown, suite, category, status,
         needs, ids, include_all, llm, workers, timeout, max_steps, dry_run):
    entries = load(Path(catalog_file))
    if markdown or write_readme:
        text = tables(entries)
        if markdown:
            click.echo(text)
        if write_readme:
            readme = HERE / "README.md"
            body = readme.read_text(encoding="utf-8")
            if BEGIN not in body or END not in body:
                raise click.ClickException(f"README.md has no {BEGIN} ... {END} markers")
            head, rest = body.split(BEGIN, 1)
            tail = rest.split(END, 1)[1]
            readme.write_text(f"{head}{BEGIN}\n\n{text}\n{END}{tail}", encoding="utf-8")
            click.echo(f"wrote the tables into {readme}")
        return
    sel = select(entries, suite, category, status, needs, ids, include_all)
    if not sel:
        raise click.ClickException("no recipe matches")
    if do_list or not (check or do_validate or do_run):
        for e in sel:
            click.echo(f"{MARK.get(e['status'], '?')} {e['id']:<46} {e.get('category', ''):<12} {','.join(e.get('needs', [])):<14} {e['graph']}")
        click.echo(f"\n{len(sel)} of {len(entries)} recipes")
        return
    if check:
        sys.exit(1 if check_needs(sel) else 0)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logdir = HERE / "logs" / stamp
    logdir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for e in sel:
        cmd = [graf_bin(), "validate", e["graph"]] if do_validate and not do_run else command(e, llm, max_steps)
        jobs.append((e, cmd))
        if dry_run:
            click.echo(" ".join(cmd))
    if dry_run:
        return
    results = []
    def work(job):
        e, cmd = job
        r = run_one(e, cmd, logdir / f"{e['id']}.log", timeout)
        click.echo(f"{'ok  ' if r['ok'] else 'FAIL'} {e['id']:<46} {r['seconds']:>6}s" + (f"  {r['llm_calls']} LLM calls" if r["llm_calls"] is not None else ""))
        return r
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(work, jobs))
    (logdir / "results.yaml").write_text(yaml.safe_dump({"llm": llm, "mode": "run" if do_run else "validate", "results": results},
                                                        sort_keys=False), encoding="utf-8")
    bad = [r["id"] for r in results if not r["ok"]]
    click.echo(f"\n{len(results) - len(bad)}/{len(results)} ok; logs in {logdir.relative_to(ROOT)}")
    if bad:
        click.echo("failed: " + ", ".join(bad))
        sys.exit(1)


if __name__ == "__main__":
    main()
