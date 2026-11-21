# cookbook_v2: recipes in the layered form

Eleven recipes from `cookbook/`, rewritten as a short top graph plus composites, each composite in its own subfolder with the prompts, procedures and
policies it uses. The originals in `cookbook/` are left alone (the experiments and many tests run them). Status and what each port taught us:
`docs/DEV/DESIGN/graflang-recipes.md`. The design: `docs/DEV/DESIGN/graflang-layers.md`.

| Recipe | Top level reads | Composites |
|---|---|---|
| code_pipeline | understand, build, finish | `understand` (exit `vague`), `build` (the test-gated loop), `finish` |
| compliance_audit | load, assess, remediate, guard, release or escalate | `assess` (used twice), `remediate` (exit `unfixed`) |
| your_book | outline, chapters, compile | `outline`, `chapters` (the loop), `compile` |
| agent_notes | guard, research | `research` (the loop; exit `gave_up`) |
| supervisor | supervise | `supervise` (exit `unapproved`) |
| self_heal | extract, heal | `extract`, `heal` (exit `invalid`) |
| heartbeat | guard, news, announce | `news` (exit `quiet`), `announce`; one extra input `state_file` |
| stock_copy | gather, report | `gather` (the per-ticker loop), `report` |
| ts_verify | repair, finalize | `repair` (the loop); needs Node 22.18+ and `npm install` here |
| notes_digest | guard, read, digest, publish | `read`, `digest`, `publish` |
| chat_memory | guard, recall, reply, remember | `recall`, `reply`, `remember` |

Run a recipe by path (named lookups such as `cookbook:name` and the Browse page only see `cookbook/`). Use the `graf` conda env.

## 1. Offline checks (free, no model)

```bash
pytest tests/test_cookbook_v2.py -q
```

Every top graph validates with no errors or warnings, and each port runs next to its original (each in a copy of its folder) with a scripted model
that forces the retry, revision, approval, give-up, redaction and escalation paths. Outputs and the number of model calls must be equal.
heartbeat runs three beats; the ts_verify check needs Node and skips without it.

## 2. Look at the levels, one recipe at a time

```bash
R=compliance_audit                                               # any recipe above
graf validate cookbook_v2/$R/$R.graph.yaml
graf vis      cookbook_v2/$R/$R.graph.yaml                       # depth 0: the top level, each composite one box
graf vis      cookbook_v2/$R/$R.graph.yaml --depth 1             # open one level; --depth all opens everything
graf describe cookbook_v2/$R/$R.graph.yaml --depth 0 -o -        # the workflow in words, composites as one line each
graf info     cookbook_v2/$R/$R.graph.yaml --depth 1             # node and edge counts at that depth
graf expand   cookbook_v2/$R/$R.graph.yaml --depth all           # the flat graph the runtime runs (ids <use>__<node>)
graf errors   --dir cookbook_v2/$R                               # the error codes this recipe defines
```

## 3. In the editor

```bash
graf vis --edit --src-dir cookbook_v2
```

`--src-dir` is needed: the editor's default work area is `~/.graflang/cookbook`, which does not hold these. On the Edit page try:

- **Level** select (level-0, level-1, level-2, all-levels, as-written): level-0 shows the few top boxes, all-levels the flat graph.
- **Group / Ungroup**: writes a new composite's folder beside the recipe and validates before saving. Do it on a copy, not on a port.
- **Opening a composite file on its own** (e.g. `compliance_audit/assess/assess.graph.yaml`): some report errors by themselves; for example `agent_notes/research`
  holds a risky QUERY whose guard is in the top graph. That is expected.
- **Run from the page** needs the model chosen in Settings and is billed. Not tried on these recipes yet. heartbeat, notes_digest and chat_memory write files
  next to their composites.

The editor was checked only by loading all eleven recipes and drawing the depth-0 view; the clicks above have not been exercised on them.

## 4. Real model runs (billed: always cap them)

Put a `--bind` file with `limits.max_llm_calls` beside the run. One is shipped for `code_pipeline`:

```bash
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --bind cookbook_v2/code_pipeline/cheap.bind.yaml
```

(its `understand` step names `ollama:gemma3` itself, so a local Ollama must be running). For the others, copy that file, change `params`, and set
`max_llm_calls` from what `graf validate` suggests ("Model calls per run").

```bash
graf run cookbook_v2/self_heal/self_heal.graph.yaml --param text="Please mail Maria Lopez (maria@acme.example)" --param max_rounds=2 --llm claude_cli:claude-haiku-5-5
```

Not checked offline: real model output. The equivalence tests show the structure matches the original, not that a real run gives the same text.

## Known differences from the originals

- **heartbeat** has an extra input `state_file` (default `output/state.txt`); its alerts log is in `announce/output/`.
- **notes_digest** reads `read/input/notes.md` and saves `publish/output/digest.md`.
- A subprocess `command` runs from the top graph's folder, so `procedures/`, `tools/` and `examples/` (compliance_audit, stock_copy, ts_verify) stay beside the top graph.
