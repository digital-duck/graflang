# code_pipeline

The flagship recipe: turn a plain-language spec into code, with review, improvement, a test verdict, a Cedar-guarded retry loop, documentation, and an optional check that the code still matches the spec.

```
analyze -> spec_gate --[READY]--> test_gated_loop -> document -> extract -> closure_gate -> judge -> merge_docs -> wf_exit
              \--(not ready)--> abort_vague (run stops)             (check_closure=false skips the judge)

test_gated_loop, one iteration (repeats until the tests pass, the guard denies, or max_cycles):
    loop_gen -> loop_rev -> loop_imp -> loop_test -> loop_eval --fail--> loop_guard (Cedar: allow_retry)
```

Every step except the gates is an SPL workflow (`00`-`07`, next to the graph), run by SPL.py's executor.

| | |
|---|---|
| Inputs | `spec` (TEXT, required), `lang` (TEXT, default `python`), `max_cycles` (INTEGER, default 3), `check_closure` (BOOL, default true) |
| Output | `docs` (TEXT): the documentation, with the closure report appended when the check ran |
| LLM calls | 1 (analyze) + 4 per loop cycle (generate, review, improve, test) + 1 (document) + 2 (extract, judge), at most 16 with the defaults (3 cycles) |
| Procedures | `00_analyze_spec` `01_generate_code` `02_review_code` `03_improve_code` `04_test_code` `05_document_code` `06_extract_spec` `07_spec_judge` |
| Policy | `graphlang/policies/mutation_safety.cedar`, action `allow_retry` (allowed while `cycle < max_cycles`) |

## Requirements

`procedure_ref` nodes need SPL.py importable, together with the packages SPL.py itself uses (for example `dd-cache`):

```bash
pip install -e /path/to/SPL.py          # or: export SPL_PY_PATH=/path/to/SPL.py
```

## Run

From the repo root. Under `claude_cli` the model is `claude-sonnet-5-5` unless you choose another with `--llm`; under `ollama` always pass one (`--llm ollama:<model>`), because the `.spl` files declare their own model default (`gemma4`) that would otherwise apply.

```bash
# the cheapest real run: one cycle, no closure check (6 calls)
graf run cookbook/code_pipeline/code_pipeline.graph.yaml --llm claude_cli:claude-haiku-5-5 \
    --param spec="a function is_palindrome(s) that ignores case and punctuation" \
    --param max_cycles=1 --param check_closure=false

# the full pipeline
graf run cookbook/code_pipeline/code_pipeline.graph.yaml --llm claude_cli:claude-haiku-5-5 \
    --param spec="a function is_palindrome(s) that ignores case and punctuation" --param lang=python

# local model
graf run cookbook/code_pipeline/code_pipeline.graph.yaml --llm ollama:gemma3 --param spec="..."
```

## What you get

- **Console:** the firing order, with the loop body indented. The loop nodes repeat once per cycle.
- **Result:** `cookbook/code_pipeline/output/code_pipeline-<adapter>[-<model>]-<time>/docs.md` (also `result.json`).
- **The generated code and the SPL artifacts** are written by the procedures into `cookbook/code_pipeline/.grafr/logs/` (git-ignored):

  | File | From |
  |---|---|
  | `spec/analysis.md` | `00_analyze_spec` |
  | `target/<lang>/code.py` | `01_generate_code`, overwritten by `03_improve_code` |
  | `target/<lang>/review.md` | `02_review_code` |
  | `tests/<lang>/result.md` | `04_test_code`: the `[PASSED]` / `[FAILED]` verdict |
  | `target/<lang>/docs.md` | `05_document_code` |
  | `spec/extracted.md` | `06_extract_spec` |

- **Logs:** `~/.graflang/logs/code_pipeline-<adapter>[-<model>]-<time>.log` / `.jsonl` for the graph, and `spl-<procedure>-<time>.log` / `.jsonl` beside them for each procedure run.
- `nodes/` also holds each node's output (analysis, code, feedback, test verdict, docs).

## Things to check

- **Gate:** a clear spec gives `spec_gate` pass (`route=pass` in the `node.done` event); a vague one such as `--param spec="make something"` should end at `abort_vague` with `Output: {}`.
- **Loop:** `loop.end` shows `iterations` at most `max_cycles`. Try `--param max_cycles=1`: if the test verdict is `[FAILED]`, the run still reaches `document` after one cycle.
- **Guard:** `guard.decision` appears only after a failed test. It is `allowed=True` while `cycle < max_cycles`, then a warning with `allowed=False` (the loop stops by `denied`).
- **Closure:** `--param check_closure=false` skips `judge`, and `docs.md` has no closure report; with `true`, the report is appended.
- **Files:** `.grafr/logs/target/python/code.py` is the code that went into the documentation, and `tests/python/result.md` starts with the verdict the gate saw.

## Known limits

- `loop_test` is an LLM acting as a test suite (`04_test_code.spl`): it reviews the code, it does not execute it.
- Not run end to end with a real model when this README was written.
