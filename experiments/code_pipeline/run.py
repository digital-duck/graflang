"""Run the experiment: for each task, arm and repetition, produce code, score it with the hidden tests, store one row.

    python run.py --verify-oracle                                  # every canonical solution must pass (no LLM)
    python run.py --n 20 --model claude-sonnet-5-5 --dry-run       # show the plan: how many runs, how many already done
    python run.py --tasks 98,107,10,24,35 --model claude-sonnet-5-5  # exactly these five tasks (or: export TASKS=98,107,...)
    python run.py --per-group 20 --model claude-sonnet-5-5      # 20 tasks from each complexity group (60)
python run.py --tasks 98 --existing append                      # task 98 again, as one more repetition after the stored ones
    python run.py --n 2 --arms single,spl,graflang,langgraph --reps 1 --model claude-haiku-5-5 --db results/smoke.db
    python run.py --import-jsonl results/smoke.jsonl               # load rows written by an older version of this script
    python run.py --rescore --db results/try.db                    # score the stored code again with the current oracle

Results go to a SQLite database (default results/experiment.db, tables and view in store.py), one row per (task, arm,
repetition, model). Runs are sequential (the SPL and GraphLang arms write their artifacts to one folder each) and
resumable: a run already in the database is skipped, so the same command picks up where it stopped. The order of arms is
shuffled per task and repetition so drift in the model's behaviour over the session does not favour one arm.

While it runs, each line shows the position (done/total), the verdict, the time of that run, the elapsed time and an
estimate of the time left (from the mean time of the arms already run in this session). At the end a table gives the
time and pass count per arm.
"""
from __future__ import annotations

import json
import random
import shutil
import statistics
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent))

import oracle  # noqa: E402
import store  # noqa: E402
import tasks as T  # noqa: E402
import arms as arms_module  # noqa: E402
from arms import ARMS, ArmResult  # noqa: E402


def verify_oracle() -> int:
    bad = [t["task_id"] for t in T.load_all() if not oracle.check(t, t["prompt"] + t["canonical_solution"]).passed]
    wrong = [t["task_id"] for t in T.load_all() if oracle.check(t, "def " + t["entry_point"] + "(*a, **k):\n    return None\n").passed]
    click.echo(f"canonical solutions failing the oracle: {bad or 'none'}; trivial stub passing it: {wrong or 'none'}")
    return 1 if bad or wrong else 0


class SessionLimit(RuntimeError):
    """The account hit a session or usage limit; the batch stops and is resumed later."""


def hms(seconds: float) -> str:
    seconds = int(round(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s" if m else f"{s}s"


def plan(tasks, seed, arms, reps, model, adapter, done, existing: str = "skip") -> list[tuple]:
    """Every (task, arm, rep) to run, in the order they will run (arm order shuffled per task and repetition).

    existing="skip":   a (task, arm, rep) already stored for this adapter and model is not run again.
    existing="append": the stored runs are kept and `reps` new repetitions are added after the last stored one.
    """
    todo = []
    for rep in range(reps):
        for task in tasks:
            order = arms[:]
            random.Random(f"{task['task_id']}/{rep}/{seed}").shuffle(order)
            for arm in order:
                if existing == "append":
                    stored = [r for t, a, r, ad, m in done if (t, a, ad, m) == (task["task_id"], arm, adapter, model)]
                    todo.append((task, arm, (max(stored) + 1 if stored else 0) + rep))
                elif (task["task_id"], arm, rep, adapter, model) not in done:
                    todo.append((task, arm, rep))
    return todo


def eta(todo_left: list[tuple], seconds_by_arm: dict) -> float | None:
    """Time left: for each remaining run, the mean time of its arm in this session (None until every arm has run once)."""
    if any(arm not in seconds_by_arm for _, arm, _ in todo_left):
        return None
    return sum(statistics.mean(seconds_by_arm[arm]) for _, arm, _ in todo_left)


def timing_table(seconds_by_arm: dict, passes: dict, elapsed: float) -> None:
    click.echo(f"\n{'arm':10} {'runs':>5} {'pass':>5} {'mean':>8} {'median':>8} {'max':>8} {'total':>8}")
    for arm, secs in seconds_by_arm.items():
        click.echo(f"{arm:10} {len(secs):5} {passes[arm]:5} {hms(statistics.mean(secs)):>8} {hms(statistics.median(secs)):>8} "
                   f"{hms(max(secs)):>8} {hms(sum(secs)):>8}")
    click.echo(f"{'all':10} {sum(map(len, seconds_by_arm.values())):5} {sum(passes.values()):5} {'':>8} {'':>8} {'':>8} {hms(elapsed):>8}  (wall time)")


@click.command(context_settings={"help_option_names": ["-h", "--help"]}, help=__doc__.split("\n\n")[0])
@click.option("--verify-oracle", is_flag=True, help="Check the scorer (no LLM) and exit.")
@click.option("--import-jsonl", type=click.Path(exists=True, dir_okay=False), help="Load a .jsonl written by an older version of this script, then exit.")
@click.option("--rescore", is_flag=True, help="Score the stored code again with the current oracle (after fixing the oracle), then exit.")
@click.option("--per-group", type=int, default=None,
              help="Stratified sample: this many tasks from each complexity group (low, medium, high). Overrides --n.")
@click.option("--n", type=int, default=None, help="Size of the fixed random task sample [default: all 164].")
@click.option("--tasks", "task_ids", envvar="TASKS", default=None,
              help="Run exactly these tasks instead: comma-separated numbers or ids, e.g. 98,107,HumanEval/10. Also read from $TASKS.")
@click.option("--existing", type=click.Choice(["skip", "append"]), default="skip", show_default=True,
              help="A task already in the database for this model and arm: skip it (the default; reruns continue where they stopped) "
                   "or append new repetitions after the stored ones (the stored rows are kept).")
@click.option("--seed", type=int, default=0, show_default=True, help="Seed of the task sample.")
@click.option("--arms", default=",".join(ARMS), show_default=True, help="Comma-separated arms to run.")
@click.option("--reps", type=int, default=1, show_default=True, help="Repetitions of every (task, arm).")
@click.option("--adapter", envvar="ADAPTER", default="claude_cli", show_default=True,
              help="LLM adapter for every arm: claude_cli, ollama, ... Also read from $ADAPTER.")
@click.option("--model", default="claude-haiku-5-5", show_default=True, help="Model id, the same for every arm.")
@click.option("--db", default="results/experiment.db", show_default=True, help="SQLite database (created if missing).")
@click.option("--run-dir", default="output", show_default=True, type=click.Path(file_okay=False),
              help="Where each run leaves its code, logs and artifacts: <run-dir>/<adapter>/<model>/<task>/<arm>-rep<N>/.")
@click.option("--dry-run", is_flag=True, help="Show the plan (runs, already done, still to do) and exit without calling a model.")
def main(verify_oracle: bool, import_jsonl, rescore, per_group, n, task_ids, existing, seed, arms, reps, adapter, model, db, run_dir, dry_run) -> None:
    if verify_oracle:
        raise SystemExit(globals()["verify_oracle"]())

    conn = store.connect(db)
    if import_jsonl:
        click.echo(f"imported {store.import_jsonl(conn, import_jsonl)} rows into {db}")
        return

    if rescore:
        by_id = {t["task_id"]: t for t in T.load_all()}
        click.echo(f"{store.rescore(conn, lambda task, code: oracle.check(by_id[task], code))} rows changed in {db}")
        return

    arms_module.ADAPTER = adapter                           # the arms read it when they make their LLM calls
    arm_list = [a.strip() for a in arms.split(",") if a.strip()]
    unknown = [a for a in arm_list if a not in ARMS]
    if unknown:
        raise click.BadParameter(f"unknown arm(s) {unknown}; choose from {sorted(ARMS)}", param_hint="--arms")
    try:
        chosen = T.stratified_sample(per_group, seed) if per_group and not task_ids else T.select(n, seed, task_ids)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--tasks")
    done = store.done_keys(conn)
    todo = plan(chosen, seed, arm_list, reps, model, adapter, done, existing)
    total = len(chosen) * len(arm_list) * reps
    stored = sorted({t for t, a, r, ad, m in done if (ad, m) == (adapter, model) and a in arm_list and t in {c["task_id"] for c in chosen}},
                    key=lambda t: int(t.split("/")[1]))
    click.echo(f"{adapter}/{model}: {len(chosen)} tasks x {len(arm_list)} arms x {reps} rep = {total} runs")
    if stored:
        click.echo(f"already in {db} for this model: {', '.join(t.split('/')[1] for t in stored)}  "
                   f"({'new repetitions are appended' if existing == 'append' else 'skipped'}; --existing to change)")
    click.echo(f"{len(todo)} to do" + (f", {total - len(todo)} skipped" if existing == "skip" and total > len(todo) else ""))
    if dry_run or not todo:
        return

    limit_stop = False
    batch = store.start_batch(conn, adapter=adapter, model=model, arms=arm_list, n_tasks=n, seed=seed, reps=reps,
                              args={"n": n, "seed": seed, "arms": arm_list, "reps": reps, "adapter": adapter, "model": model, "db": db})
    click.echo(f"batch {batch}\n")
    seconds_by_arm: dict = defaultdict(list)
    passes: dict = defaultdict(int)
    started = time.time()
    try:
        for i, (task, arm, rep) in enumerate(todo, start=1):
            run_start = time.time()
            folder = Path(run_dir) / adapter / model / task["task_id"].replace("/", "_") / f"{arm}-rep{rep}"
            shutil.rmtree(folder, ignore_errors=True)            # a rerun replaces the old folder
            folder.mkdir(parents=True)
            try:
                res = ARMS[arm](T.spec_for(task), model, folder.resolve())
            except Exception as e:                      # one failing call must not end a batch that runs unattended
                res = ArmResult(status=f"error:{type(e).__name__}: {str(e)[:150]}")
                (folder / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            verdict = oracle.check(task, res.code)
            took = time.time() - run_start
            # every cycle's code is scored against the hidden tests too, so a trajectory can say when a run got it right
            detail = []
            for c in res.cycles_detail:
                v = oracle.check(task, c["code"])
                detail.append({"cycle": c["cycle"], "verdict": c["verdict"], "hidden_passed": v.passed,
                               "assert_passed": v.assert_passed, "assert_total": v.assert_total, "code": c["code"]})
            store.write_result(conn, batch, {
                "task": task["task_id"], "arm": arm, "rep": rep, "adapter": adapter, "model": model, "passed": verdict.passed,
                "reason": verdict.reason, "status": res.status, "pipeline_verdict": res.pipeline_verdict,
                "cycles": res.cycles, "seconds": round(res.seconds, 1), "code": res.code,
                "assert_passed": verdict.assert_passed, "assert_total": verdict.assert_total,
                "llm_calls": res.llm.get("calls"), "prompt_tokens": res.llm.get("prompt_tokens"),
                "output_tokens": res.llm.get("output_tokens"), "cycles_detail": json.dumps(detail)})
            seconds_by_arm[arm].append(took)
            passes[arm] += verdict.passed
            if arms_module.is_limit_error(res.status) or arms_module.limit_in_folder(folder):
                raise SessionLimit(f"{task['task_id']} {arm}: the account reports a session or usage limit")
            left = eta(todo[i:], seconds_by_arm)
            click.echo(f"[{i:>{len(str(len(todo)))}}/{len(todo)}] {task['task_id']:14} {arm:10} rep{rep} "
                       f"{click.style('PASS', fg='green') if verdict.passed else click.style('fail', fg='red')} "
                       f"{hms(took):>6} cycles={res.cycles}  elapsed {hms(time.time() - started)}"
                       f"{'  left ~' + hms(left) if left is not None else ''}"
                       f"{'  ' + res.status if res.status != 'ok' else ''}")
    except KeyboardInterrupt:
        click.echo("\ninterrupted; the rows written so far are kept, rerun the same command to continue")
    except SessionLimit as e:
        # stop here: every later run would fail at once and be stored as an error. The limit run is stored as an error, so
        # rerunning the same command after the limit resets retries it and the rest of the batch.
        click.echo(f"\nSTOPPED: {e}. The rows so far are kept; the limit run is stored as an error and will be retried. "
                   "Rerun the same command after the limit resets.")
        limit_stop = True
    finally:
        store.finish_batch(conn, batch)        # also on Ctrl-C, so the batch row shows how far it got
        if seconds_by_arm:
            timing_table(seconds_by_arm, passes, time.time() - started)
    if limit_stop:
        raise SystemExit(3)                    # non-zero: the calling script must not start the next model or the report
    click.echo(f"\nsummary: sqlite3 {db} 'SELECT * FROM arm_summary'   or   python analyze.py {db}")


if __name__ == "__main__":
    main()
