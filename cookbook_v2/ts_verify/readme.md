# ts_verify

A model writes a TypeScript function, and tools judge it: the TypeScript compiler (`tsc`) type-checks it and Node runs it on your test cases. The model is asked again, with the
reports, until it passes or the rounds run out. The judges are programs, not a model.

```
ts_verify       repair -> finalize (a program builds the JSON result)
  repair/       the loop: write (model) -> type-check -> run the cases -> stop when both pass
```

Inputs: `spec`, `function` (the name to export), `cases` (a JSON file of calls and expected results), `check_types` (default true), `max_cycles` (default 3).
Output: `result` (JSON: the final code, whether it passed, the attempts, the type and case reports). Model calls: one per round, at most `max_cycles`.

**Needs Node 22.18+ and `npm install` in this folder** (for `tsc`). The tools stay in `tools/` because a command runs from the top graph's folder.

```bash
graf run cookbook_v2/ts_verify/ts_verify.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-sonnet-5-5 \
    --param function=slugify --param cases=examples/slugify.cases.json \
    --param spec="slugify(title): lowercase; treat anything that is not an ASCII letter or digit as a separator; join the words with single hyphens; no leading or trailing hyphen"
```

`examples/` has two case files (`slugify`, `duration`). The offline test skips without Node. Original: `cookbook/ts_verify`, whose readme has the longer experiments.
