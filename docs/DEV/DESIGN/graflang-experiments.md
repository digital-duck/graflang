# GraphLang experiments: build plan

Status: **plan for review (2026-11-05). Nothing in sections 2 to 4 is built yet.** Two pieces of work: (1) make the compliance batch experiment observable and analysable from a database; (2) repeat the NeurIPS-26 round-trip experiment with GraphLang in the loop, to evaluate GraphLang itself.

## 1. Where things stand (answers to the two questions)

**Does `batch_test.py` record into SQLite?** No. It writes `output/batch_test-<time>/results.jsonl` (one row per document x variant), `summary.md`, and a `runs/<label>/` folder per run (`result.json`, `summary.json`, `nodes/*.md`). There is no store, no cross-batch history, no analysis script. `experiments/code_pipeline/` has the pattern (`batch_store.py`, `analyze.py`); it has not been applied here.

**Is GraphLang ready for observability with `OBSERVE` for benchmarking models and solvers?** Partly.

| Exists | Gap |
|---|---|
| `OBSERVE` node: logs a record and appends to `observations.jsonl` in the run folder; never fails a run | No cross-run store; each run is an island |
| `summary.json` per run: LLM calls, tokens, per-node timings | `claude_cli` token counts are estimates (chars/4), not billed numbers; cost comparisons across adapters are approximate |
| JSONL logs (`~/.graflang/logs`), `graf trace` (timeline or OTLP spans) | Logs are per process, not keyed by experiment cell (doc, variant, model, rep) |
| Per-node outputs saved (`nodes/*.md`), so the solver verdict and the LLM verdict can be compared after the fact | Nothing reads them back into a table |
| Batch scoring (false release, false escalation, over-redaction) in `batch_test.py` | Scoring lives in the script, not in a reusable store |

Conclusion: the recording primitives are enough; the missing part is a **store and an analysis layer**, not new node types. `OBSERVE` need not change for the first version: the batch reads each run folder after the run finishes (`summary.json`, `result.json`, `observations.jsonl`) and writes rows. If it later proves too indirect, a `--record-db` option on `graf run` is the second step, not the first.

## 2. Project A: SQLite store and analysis for the compliance batch

Goal: run the grid (documents x variant x model x repetition) and answer "z3 on or off, which model" with intervals, not impressions.

Build (small, modelled on `experiments/code_pipeline/store.py` and `analyze.py`):

1. `cookbook/compliance_audit/batch_store.py`: tables `batches` (batch_id, host, adapter, model, variants, n_docs, reps, args, started_at, finished_at) and `results` (one row per cell: the existing `results.jsonl` fields plus batch_id, rep, adapter, model). `UNIQUE(doc, variant, rep, adapter, model)` so an interrupted batch resumes without repeating billed calls. A view `variant_summary` (n, correct, false releases, false escalations, over-redaction, mean calls, tokens, seconds per variant and model). Column migration list as in the existing store.
2. `batch_test.py --db PATH` (default `output/experiments.db`): insert each row as it completes; `--resume` skips cells already present. JSONL and `summary.md` stay (no behaviour change without `--db`).
3. `cookbook/compliance_audit/batch_analyze.py`: per variant and model, rate with Wilson interval; paired comparison recipe vs baseline on the same documents (McNemar on correct/incorrect, paired bootstrap on cost); a hygiene section (rows with errors, `ambiguous` documents excluded and counted); a consistency section (same document, several reps, does the verdict change).
4. Tests: store round trip, resume skips present cells, analysis on a hand-made database (offline).

Held equal: same documents, same prompts, same model within a comparison; the only thing that varies between `recipe-*` and `baseline` is the decision step.

Expected result, stated before any run (to be checked, not assumed): the rule engines (`z3`, `stdlib`, `sympy`) agree on every document since they decide the same rules; the baseline (LLM judge) will have more false releases and more run-to-run variation than the recipe; extraction by smaller models over-flags identifiers as `OTHER` on clean documents (seen on R1 and R8), which shows up as over-redaction for the recipe, not as a false release. If the baseline matches the recipe on correctness, the finding is that the solver buys auditability, not accuracy, and the write-up must say so.

Cost: each recipe run is about 3 LLM calls, capped at 4; baseline similar. Grid of 16 documents x 4 variants x 1 rep = about 200 calls per model. Every run keeps `limits.max_llm_calls`.

Open decisions for you: default database location; whether `ambiguous` documents are reported separately or dropped; model list for the first full grid (haiku only, or haiku + sonnet + one local model).

## 3. Project B: the round trip with GraphLang in the loop

### 3.1 What the NeurIPS-26 lab does (as read from `SPL.py/NeurIPS-26-lab/README.md`)

Five PocketFlow recipes (R1 agent, R2 rag, R3 judge, R4 thinking, R5 research), three models (claude_cli sonnet, openrouter qwen, openrouter gemini), a human checkpoint after each generated artifact. Phase 1, the full IR path:

```
S1  describe original PocketFlow recipe      -> spec (1)
S2  text2mmd                                 -> Mermaid chart
S3  mmd2spl                                  -> SPL workflow
S4  compile SPL to PocketFlow python         -> code
S5  describe the generated code              -> spec (2)
S6  compare spec (1) with spec (2)           -> diff and score (judge: claude-opus-4-6)
```

Phase 2 (ablation) bypasses the IR: `spl3 vibe` writes code straight from spec (1) (S7), describe (S8), compare (S9), and S10 compares the two scores (the IR value-add). Closure is judged by the semantic distance between the original spec and the round-trip spec: that distance is the "intent drift" this plan reuses. I have read the README and the first part of `notes.md` (issues were mostly in the generators: Mermaid syntax, SPL fence stripping, WORKFLOW syntax). I have **not** read the R*/src code, the scores, or the later notes, so any claim about the lab's results is out of scope here.

### 3.2 The GraphLang arm

The new arm replaces the SPL middle with a graph, and is the one in which the graph's own checks can act:

```
G1  graf describe (or spl3 splc describe) on the original PocketFlow recipe   -> spec (1)   [same S1 file, reused]
G2  graf create --spec @spec(1)                                              -> NAME.graph.yaml (validated + mock dry run by create)
G3  graf validate                                                            -> gate, recorded, not fixed by hand
G4  graf compile --lang pocketflow                                           -> python code            [NEW]
G5  describe the generated code (same tool as S5)                            -> spec (2)
G6  compare spec (1) with spec (2) (same judge, same prompt as S6)           -> diff and score
G7  (extra, GraphLang only) graf describe on the graph from G2               -> spec (1g), so drift is split in two:
        spec(1) -> graph  (is the graph faithful?)  and  graph -> code  (is the compile faithful?)
```

G7 is the useful new measurement: the SPL arm has one end-to-end number; the GraphLang arm can locate where intent is lost, because `graf describe` is deterministic (no model) when run without `--llm`, so graph -> spec adds no noise.

Arms for the table: `spl` (S1 to S6, taken from the lab), `graflang` (G1 to G6), `vibe` (S7 to S9, no IR), and optionally `graflang-det` where G4 is a template compile (no model) as opposed to an LLM-assisted compile.

### 3.3 Things that must be built (honest list)

1. **`graf compile --lang pocketflow`** (new). `--lang rust` is a stub and `--lang spl` exists (`grafe/graph2spl.py`), so this is a new backend in `grafe/`. Scope for v1: GENERATE, EVALUATE, SOLVE (expression/kernel), ASSERT, LOOP, branches by port, FORK/JOIN; reject (with a clear error) node types with no PocketFlow equivalent (GUARD/Cedar, MUTATE, DECISION, RUN_CODE, QUERY/EMIT). The five recipes are the ground truth for what must be covered; first step is to read the five originals and the lifted `cookbook_pocketflow` graphs and list the node types actually used.
2. **A deterministic template compile first**, LLM-assisted compile only as the second arm. A template compile makes G4 reproducible, so any drift is attributable to G2 (the spec -> graph step) or to the describe/compare tools, not to the compile.
3. **Lifted graphs as a shortcut control**: the PocketFlow recipes were already lifted into GraphLang by `spl2graph` (`cookbook_pocketflow`). Compiling those back (skipping G1 to G3) measures the compile step alone. This is a cheap, model-free baseline and should run first.
4. **A compare runner** that takes two spec files and writes a score row to a SQLite store (same schema family as project A: batches/results, UNIQUE on recipe, arm, model, rep). The lab's `spl3 compare` is the reference; use the same judge, same rubric, and same model for every arm.
5. **A driver** (`experiments/roundtrip/run.py` + `store.py` + `analyze.py`, in the layout of `experiments/code_pipeline/`).

### 3.4 Held equal (non-negotiable, as in `experiments/code_pipeline/README.md`)

Same five recipes and the same S1 spec across arms; same model for the generating step within a comparison; same describe tool for S5/G5; same judge model and rubric; no human edits to a generated artifact in the measured run (the lab's human checkpoints are kept as a separate, unscored pass: a generation that needs repair is recorded as `needed_repair`, not silently fixed). The comparison judge must not be the generating model.

### 3.5 Metrics

- Drift score from the judge (S6/G6/S9) per recipe, arm, model.
- Failure stage: the first step that failed (create validation, `graf validate`, compile, run of the generated code with the lab's test input). Counted, not averaged away.
- Executable: does the generated code run on the recipe's test input (yes/no).
- Cost: LLM calls and tokens per arm.
- Variance: rep count of at least 3 per cell for the LLM steps, since a single run per cell would not separate drift from noise.

Analysis: per-arm mean with bootstrap interval across recipes, paired by recipe; with 5 recipes the intervals will be wide and the write-up should say so.

### 3.6 Expected result, stated before running

I expect: (a) the deterministic compile of an already-lifted graph shows low drift (the graph contains what the original had); (b) the `spec -> graph` step is where most drift appears, since `graf create` follows the guide to build the smallest graph and may drop detail the spec states; (c) the GraphLang arm fails earlier and more visibly (validation errors) where the SPL arm fails late (the generated code does not run), which is an advantage in detectability, not in final score; (d) final drift scores of the `spl` and `graflang` arms are of similar size, and I do not expect a clear win at five recipes. If GraphLang does not beat or at least match the SPL arm, that is a finding to report, not hide. I have no data for any of this.

### 3.7 Risks

- PocketFlow semantics (shared store, node `post` returning an action string) do not map one-to-one to token-passing dataflow; a faithful compile may need a small runtime shim, which would make G4 less "pure".
- The lab's results and judge outputs are in a different repository; reusing them for the `spl` arm needs the files, not a re-run, or the arms differ in model versions. Decision for you: reuse the lab's S1 to S6 outputs, or re-run the SPL arm in the same batch.
- `graf describe` without `--llm` is structure-only; the original recipe's prose context (readme, docstrings) is only there with `--llm` or the lab's `--include-docs`. The two S1 variants must not be mixed across arms.
- The judge is itself a model; one judge model means one set of biases. Mitigation: a second judge on a random 20% subset to report agreement.

## 4. Phases and review points

| Phase | Work | Needs LLM | Stop and review |
|---|---|---|---|
| 0 | Read the five PocketFlow originals, the lifted graphs, and the lab's R*/src; list node types used; correct this plan | no | Yes: you review the corrected scope |
| 1 | Project A: store, `--db`, `--resume`, `analyze.py`, tests | no (tests offline) | After you run the haiku batch |
| 2 | `graf compile --lang pocketflow` (template), compile the five lifted graphs, run the generated code on the lab test inputs | no | Yes: does it run? |
| 3 | Roundtrip driver, compare runner, store; dry run with `mock` | no | Yes |
| 4 | Pilot: one recipe, one model, 3 reps, all arms, capped | yes (small, capped) | Yes: check the judge, the cost, the failure stages |
| 5 | Full grid: 5 recipes x arms x models x reps | yes (billed; budget agreed first) | Yes |
| 6 | Write-up: findings against the stated expectations, including where they were wrong | no | - |

Budget rule: no phase with a billed model starts without an agreed call cap (`limits.max_llm_calls` per run and a total per batch in the driver).

## 5. Decisions needed from you

1. Phase 0 first (read the originals, then fix the scope), or go straight to Project A after your haiku run?
2. `pocketflow` compile: template-only for v1 (my recommendation), or LLM-assisted as well?
3. SPL arm: reuse the lab's existing S1 to S6 files, or re-run it in the same batch for equal model versions (my recommendation if the cost is acceptable)?
4. Models for the pilot (one) and the full grid (the lab used sonnet, qwen, gemini; this repo's default adapter is `claude_cli`).
5. Where the experiment lives: `experiments/roundtrip/` in this repo (my recommendation, next to `code_pipeline`), or in the SPL.py lab.
