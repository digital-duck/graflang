"""Summarize a batch experiment from its SQLite database.

    python batch_analyze.py [--db output/experiments.db ...] [--batch ID] [--model SUBSTRING] [--out FILE]

Sections: per model and variant (rates with 95% Wilson intervals, false releases first); elapsed time (median, p90, model vs rules); per document (which documents trip which
cell); consistency across reps; paired comparison of two variants on the same documents (exact McNemar test on correct / not
correct); hygiene (errors, ambiguous items left in released text, documents counted); cost. Nothing is rescored here: the
scores are the ones batch_test.py stored. For other questions: sqlite3 output/experiments.db "SELECT * FROM variant_summary".
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch_store as store  # noqa: E402


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def quantile(values: List[float], q: float) -> float:
    v = sorted(values)
    if not v:
        return 0.0
    i = (len(v) - 1) * q
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def pct(k: int, n: int) -> str:
    if n == 0:
        return "-"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.0f}% [{100 * lo:.0f}-{100 * hi:.0f}]"


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact p for the discordant counts b (A right, B wrong) and c (A wrong, B right)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def cells(rows: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    out: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        out[(r["llm"], r["variant"])].append(r)
    return dict(sorted(out.items()))


def by_variant(rows: List[dict]) -> str:
    lines = ["## By model and variant", "",
             "Rates over the runs that gave a result; intervals are 95% Wilson. **False release** (personal data left in a released text) is the costly error.", "",
             "| model | variant | runs | errors | correct | **false release** | false escalation | over-redaction | calls/run | tokens/run (est.) | s/run |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for (llm, variant), mine in cells(rows).items():
        ok = [r for r in mine if not r["error"]]
        n = len(ok)
        k = lambda key: sum(bool(r[key]) for r in ok)   # noqa: E731
        calls = sum(r["calls"] or 0 for r in ok) / n if n else 0
        toks = sum((r["tokens_in"] or 0) + (r["tokens_out"] or 0) for r in ok) / n if n else 0
        secs = sum(r["seconds"] or 0 for r in ok) / n if n else 0
        lines.append(f"| {llm} | {variant} | {len(mine)} | {len(mine) - n} | {pct(k('correct'), n)} | **{pct(k('false_release'), n)}** | "
                     f"{pct(k('false_escalation'), n)} | {pct(k('over_redaction'), n)} | {calls:.1f} | {toks:.0f} | {secs:.1f} |")
    return "\n".join(lines) + "\n"


def timing(rows: List[dict]) -> str:
    out = ["## Elapsed time per run (seconds)", "",
           "`wall` is the whole `graf run` (start-up included); `model` is the time inside model calls; `rules etc.` is every other node (rule engine, guard, loading). "
           "Medians and the 90th percentile, since a few slow runs skew a mean.", "",
           "| model | variant | runs | wall median | wall p90 | wall mean | model mean | rules etc. mean | total wall |", "|---|---|---|---|---|---|---|---|---|"]
    for (llm, variant), mine in cells(rows).items():
        ok = [r for r in mine if not r["error"]]
        if not ok:
            continue
        wall = [r["seconds"] or 0 for r in ok]
        m = [r["llm_seconds"] for r in ok if r.get("llm_seconds") is not None]
        o = [r["other_seconds"] for r in ok if r.get("other_seconds") is not None]
        avg = lambda xs: f"{sum(xs) / len(xs):.1f}" if xs else "-"   # noqa: E731
        out.append(f"| {llm} | {variant} | {len(ok)} | {quantile(wall, .5):.1f} | {quantile(wall, .9):.1f} | {avg(wall)} | {avg(m)} | "
                   f"{(f'{sum(o) / len(o):.2f}' if o else '-')} | {sum(wall):.0f} |")
    return "\n".join(out) + "\n"


def by_document(rows: List[dict]) -> str:
    keys = list(cells(rows))
    docs = sorted({r["doc"] for r in rows})
    lines = ["## By document", "", "R released, E escalated; `!` leak, `x` false escalation, `o` over-redaction, `?` error. Several reps: one symbol per rep.", "",
             "| document | " + " | ".join(f"{v} / {m.split(':')[-1]}" for m, v in keys) + " |", "|---|" + "---|" * len(keys)]
    for d in docs:
        row = []
        for m, v in keys:
            sym = []
            for r in sorted((x for x in rows if x["doc"] == d and x["variant"] == v and x["llm"] == m), key=lambda x: x["rep"]):
                if r["error"]:
                    sym.append("?")
                else:
                    sym.append(("R" if r["released"] else "E") + ("!" if r["false_release"] else "") + ("x" if r["false_escalation"] else "")
                               + ("o" if r["over_redaction"] else ""))
            row.append(" ".join(sym))
        lines.append(f"| {d} | " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def consistency(rows: List[dict]) -> str:
    out = ["## Consistency across reps", ""]
    any_reps = False
    lines = ["| model | variant | documents with reps | documents whose outcome changed between reps |", "|---|---|---|---|"]
    for (llm, variant), mine in cells(rows).items():
        per_doc: Dict[str, set] = defaultdict(set)
        count: Dict[str, int] = defaultdict(int)
        for r in mine:
            if not r["error"]:
                per_doc[r["doc"]].add((r["released"], r["false_release"], r["over_redaction"]))
                count[r["doc"]] += 1
        multi = [d for d, c in count.items() if c > 1]
        if multi:
            any_reps = True
            lines.append(f"| {llm} | {variant} | {len(multi)} | {sum(len(per_doc[d]) > 1 for d in multi)} |")
    return "\n".join(out + (lines if any_reps else ["Every cell ran once (`--reps 1`): nothing to compare."])) + "\n"


def paired(rows: List[dict]) -> str:
    out = ["## Paired comparison (same documents, same model)", "",
           "b = first variant correct and second not; c = the reverse. p is the exact McNemar test on b and c (two-sided). Few documents: read the counts, not only p.", "",
           "| model | A | B | pairs | A correct | B correct | b | c | p |", "|---|---|---|---|---|---|---|---|---|"]
    n_rows = 0
    for llm in sorted({r["llm"] for r in rows}):
        variants = sorted({r["variant"] for r in rows if r["llm"] == llm})
        for i, a in enumerate(variants):
            for b_name in variants[i + 1:]:
                ra = {(r["doc"], r["rep"]): r for r in rows if r["llm"] == llm and r["variant"] == a and not r["error"]}
                rb = {(r["doc"], r["rep"]): r for r in rows if r["llm"] == llm and r["variant"] == b_name and not r["error"]}
                keys = sorted(set(ra) & set(rb))
                if not keys:
                    continue
                b = sum(bool(ra[k]["correct"]) and not rb[k]["correct"] for k in keys)
                c = sum(not ra[k]["correct"] and bool(rb[k]["correct"]) for k in keys)
                out.append(f"| {llm} | {a} | {b_name} | {len(keys)} | {sum(bool(ra[k]['correct']) for k in keys)} | "
                           f"{sum(bool(rb[k]['correct']) for k in keys)} | {b} | {c} | {mcnemar_exact(b, c):.3f} |")
                n_rows += 1
    return "\n".join(out if n_rows else out[:2] + ["Fewer than two variants share documents: nothing to pair."]) + "\n"


def across_models(rows: List[dict]) -> str:
    models = sorted({r["llm"] for r in rows})
    if len(models) < 2:
        return ""
    out = ["## Same variant, different models", "", "| variant | " + " | ".join(m.split(":")[-1] for m in models) + " |", "|---|" + "---|" * len(models)]
    for v in sorted({r["variant"] for r in rows}):
        row = []
        for m in models:
            ok = [r for r in rows if r["variant"] == v and r["llm"] == m and not r["error"]]
            row.append(f"{sum(bool(r['correct']) for r in ok)}/{len(ok)} correct, {sum(bool(r['false_release']) for r in ok)} leak" if ok else "")
        out.append(f"| {v} | " + " | ".join(row) + " |")
    return "\n".join(out) + "\n"


def hygiene(rows: List[dict]) -> str:
    errs = [r for r in rows if r["error"]]
    out = ["## Hygiene", "", f"- runs: {len(rows)}, with an error: {len(errs)}; documents: {len({r['doc'] for r in rows})}; models: {len({r['llm'] for r in rows})}"]
    for r in errs[:10]:
        out.append(f"  - {r['variant']} / {r['llm']} / {r['doc']}: {r['error']}")
    amb = sum(bool(r["ambiguous_left"]) for r in rows if not r["error"])
    out.append(f"- released texts that still contain an `ambiguous` item (never scored): {amb}")
    out.append("- token counts for `claude_cli` are estimates (characters / 4), so compare calls and seconds first.")
    return "\n".join(out) + "\n"


def leaks(rows: List[dict]) -> str:
    bad = [r for r in rows if r["false_release"]]
    if not bad:
        return "## Leaks\n\nNo false release in this data.\n"
    out = ["## Leaks (false releases)", "", "| model | variant | document | leaked | run folder |", "|---|---|---|---|---|"]
    for r in bad:
        out.append(f"| {r['llm']} | {r['variant']} | {r['doc']} | {', '.join(r['leaks'])} | {r['result_dir']} |")
    return "\n".join(out) + "\n"


def report(rows: List[dict]) -> str:
    if not rows:
        return "No results.\n"
    parts = [by_variant(rows), across_models(rows), timing(rows), leaks(rows), by_document(rows), consistency(rows), paired(rows), hygiene(rows)]
    return "# Compliance audit batch\n\n" + "\n".join(p for p in parts if p)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", action="append", default=None,
                    help="a database (default output/experiments.db); give --db more than once to compare runs kept in separate files: each model is then "
                         "shown as `model [file name]`, so two prompt versions of the same model sit side by side")
    ap.add_argument("--batch", default=None, help="only this batch id (default: every batch in the database)")
    ap.add_argument("--model", default=None, help="only models whose adapter:model contains this text")
    ap.add_argument("--out", default=None, help="also write the report to this file")
    args = ap.parse_args(argv)
    dbs = args.db or [str(HERE / "output" / "experiments.db")]
    missing = [d for d in dbs if not Path(d).exists()]
    if missing:
        print(f"no database at {', '.join(missing)}; run batch_test.py first")
        return 2
    rows = []
    for d in dbs:
        part = store.load_rows(d, args.batch)
        for r in part:
            if len(dbs) > 1:
                r["llm"] = f"{r['llm']} [{Path(d).stem}]"
        rows += part
    if args.model:
        rows = [r for r in rows if args.model in r["llm"]]
    text = report(rows)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
