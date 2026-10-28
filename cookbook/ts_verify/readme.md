# ts_verify: an LLM writes TypeScript, the TypeScript toolchain judges it

A model writes one TypeScript function. The real TypeScript compiler type-checks it, Node runs it against your test cases, and whatever failed goes back to the model for another attempt (up to `max_cycles`). Python puts the result together. Three languages in one graph: the model's text, TypeScript and Python.

Each tool is a program that reads one JSON object on stdin and prints one line of JSON on stdout. A `SOLVE` node with `backend: subprocess` runs it, so any language works the same way, and the graph does not change when you swap one.

```
spec + cases -> write (LLM) -> typecheck (tsc) -> types ok? -- yes --> run_cases (node) -> cases ok? -- yes --> finalize (Python) -> result
                   ^                                  | no                                    | no
                   +------- retry with the last attempt, the compiler errors, the failed cases ------+
```

## Before you start

Run everything from the repository root (`graflang/`), in the environment where GraphLang is installed.

| You need | Check | If it fails |
|---|---|---|
| GraphLang | `graf --help` | `conda activate graf` and `pip install -e ".[dev]"` |
| Node 22.18 or newer (24 is fine) | `node --version`, and `which node` for the one `graf` will use | install a newer Node (for example with nvm). Node runs TypeScript by stripping the types, on by default only from 22.18, and `run_cases` uses its `--permission` flag |
| `python3` on your PATH | `python3 --version` | the `finalize` tool runs `python3`; activating the GraphLang environment is enough |
| A model, for step 4 only | `claude --version` | steps 1 to 3 need no model. Use `--llm ollama:<model>` or another adapter instead if you prefer |

## Walkthrough

### 0. Visualize graph.yaml

```bash
graf viz cookbook/ts_verify/ts_verify.graph.yaml
```

### 1. Check the graph and run the tests (no model, no install)

```bash
graf validate cookbook/ts_verify/ts_verify.graph.yaml
# ✓ Valid GraphLang workflow: ts_verify

pytest tests/test_ts_verify.py -v
```

The tests run the real graph and the real tools with a scripted stand-in for the model. Without step 3 (`npm install`) the tests that need the compiler are skipped, and the rest pass.

### 2. Watch the retry loop

```bash
python cookbook/ts_verify/examples/retry_demo.py     # needs step 3 first
```

A scripted model writes `slugify` with a type error, and you see the compiler's message exactly as the model sees it in its second prompt, then the fix and the report:

```
WHAT THE COMPILER SAID, as the model saw it in its second prompt:
{"ok":false,"checked":true,"diagnostics":["line 2, col 3: TS2322: Type 'string' is not assignable to type 'number'."]}
...
**Result:** PASSED after 2 attempt(s)
**Types:** clean
**Cases:** 5/5 passed
```

### 3. Install the TypeScript compiler (for type checking)

```bash
npm install --prefix cookbook/ts_verify
# added 1 package ... found 0 vulnerabilities
```

This puts `typescript` in `cookbook/ts_verify/node_modules` (git-ignored). It is the only dependency. Skip it, and pass `--param check_types=false` in step 4, to try the first tier: Node runs the code against your cases but nothing checks the types.

### 4. Run it with a real model

```bash
graf run cookbook/ts_verify/ts_verify.graph.yaml --llm claude_cli:claude-sonnet-5-5 \
    --param function=slugify --param cases=examples/slugify.cases.json \
    --param spec="slugify(title): lowercase; treat anything that is not an ASCII letter or digit as a separator; join the words with single hyphens; no leading or trailing hyphen"
```

You should see the loop fire its five nodes once, then `finalize` and `done`:

```
⚡ LOOP repair (#1)
  ⚡ GENERATE write (#1)
  ⚡ SOLVE typecheck (#1)
  ⚡ EVALUATE types_ok (#1)
  ⚡ SOLVE run_cases (#1)
  ⚡ EVALUATE tests_ok (#1)
⚡ SOLVE finalize (#1)
✓ Workflow completed
Output: {'result': {'passed': True, 'attempts': 1, 'code': 'export function slugify(...', 'report': '## ts_verify ... PASSED after 1 attempt(s) ... Types: clean ... Cases: 5/5 passed'}}
```

A real run of this took about 3 seconds. Current models usually pass on the first attempt, so you will rarely see a second one live; step 2 is where the retry path is shown. If a run does need several attempts, `GENERATE write` appears more than once.

### 5. Look at what happened

```bash
ls cookbook/ts_verify/output/                     # one folder per run
python -m json.tool cookbook/ts_verify/output/<run>/result.json
```

`result.json` has the same four fields as the printed output: `passed`, `attempts`, `code` (clean, without the markdown fence) and `report`. To see every attempt and every report, add `--save-nodes` to the run: the run folder then has a `nodes/` folder with one file per node output in firing order (`002-write.out_code.md`, `003-typecheck.out_check.md`, ...). The log (path printed at the end of the run) records each tool call with its duration and a hash of its input and output.

### 6. Change something

```bash
# a second example, with ten cases (a harder spec)
graf run cookbook/ts_verify/ts_verify.graph.yaml --llm claude_cli:claude-haiku-4-5 \
    --param function=formatDuration --param cases=examples/duration.cases.json \
    --param spec="formatDuration(seconds: number): string. Break seconds into days, hours, minutes and seconds. Print only the non-zero units, largest first, separated by single spaces, like '1d 2h 3m 4s'. Zero seconds prints '0s'. Negative values print '0s'. Fractions of a second are dropped (rounded down)."
```

- **Your own function.** Write cases as a JSON list, `[{"args": [...], "expected": ...}, ...]`, and pass the name and a spec. `cases` can be that JSON text itself or a path; a relative path starts in `cookbook/ts_verify/` (where the tools run), not in your current folder. Arguments and results must be JSON values, and the function must be pure: no imports, no `console`, no files.
- **More or fewer attempts.** `--param max_cycles=5`.
- **No type check.** `--param check_types=false`.
- **Another model.** `--llm ollama:<model>`, or `--adapter mock` to see the plumbing without a model (the placeholder text is not code, so the run reports `cannot load the code`).
- **Another language for a tool.** Edit `command:` in the graph. `["node", "tools/run_cases.mjs"]` could be `["deno", "run", "tools/run_cases.ts"]`, a Rust binary or a Python script, as long as it reads the same JSON and prints one JSON line. If the new runtime aborts at start-up, give the node more address space with `memory_mb` (Bun needs `memory_mb: 16384`). If the tool needs a variable from your environment, such as `HOME` or `NODE_PATH`, name it with `env_passthrough: [HOME]`; by default a tool sees only `PATH`.

## What it shows

- **A tool in any language.** `typecheck` and `run_cases` are Node programs, `finalize` is Python. The graph declares only a command, a parser (`first_line`: the tool's one line of JSON) and a type.
- **The toolchain gives better feedback than tests alone.** `tsc --strict` catches a wrong return type before any test runs, with a line and column, and the next prompt contains that error and the code that caused it. A failing case is fed back as the arguments, the expected value and the actual value.
- **Type errors skip the tests.** If `typecheck` fails, `run_cases` does not run in that attempt, and the carried case report is empty.
- **Fail closed.** With `check_types=true` and no `typescript` installed, `typecheck` exits 1 and the run stops with how to fix it. It never says "no errors" because it could not look.
- **Running model-written code, with some limits.** `run_cases` runs the code in a child Node process under Node's permission model: it may read only the candidate and the runner, write no files and start no processes, and it is killed after 10 s. The network and the CPU are not restricted, and the code runs as you. Treat this as a seatbelt, not a sandbox; use a container for a model you do not trust.

## If something goes wrong

| You see | Cause and fix |
|---|---|
| `Run failed: SOLVE node 'typecheck': solver command not found: 'node'` | Node is not on the PATH of the shell running `graf`. Check `node --version` |
| `solver exited 1: ts_verify needs Node 22.18 or newer; this is v20.20.2 (/usr/bin/node)` | an older `node` comes first on your PATH; the message names which one. Put a newer one first (for example `nvm use 24`) |
| `solver exited 1: typescript is not installed: run npm install ...` | do step 3, or pass `--param check_types=false` |
| `solver exited 1: cannot read the test cases: ENOENT ...` | a relative `cases` path starts in `cookbook/ts_verify/`: use `examples/slugify.cases.json`, not `cookbook/ts_verify/examples/...`, or give an absolute path |
| `solver exited 1: "function" must be a JavaScript identifier` | `--param function=` is empty or not a valid name |
| the report says `cannot load the code: ...` | the model's reply was not valid TypeScript that Node can run (prose instead of code, or syntax Node cannot strip such as `enum`). It is fed back like any other failure |
| `the module does not export a function named X` | the model named the function differently; the prompt tells it not to, and the retry says so |
| the report says `timed out after 10 s` | the code never returned (an endless loop) |
| the run stops at once with a session or rate-limit message | your model account is at its limit; wait, or use another `--llm` |
| `Run failed: SOLVE node ...: solver exited -6` (or another negative number) | the runtime was killed, usually by the 2 GB address-space limit; raise `memory_mb` on that node |

## Where things are

| File | Role |
|---|---|
| `ts_verify.graph.yaml` | the workflow (a `LOOP` of write, typecheck, run_cases) |
| `prompts/write_ts.md` | the prompt; on a retry it carries the last attempt and the reports |
| `tools/typecheck.mjs` | `tsc --strict` on the code held in memory; erasable syntax only, so Node can run what it accepts |
| `tools/run_cases.mjs`, `tools/case_runner.ts` | write the code to a temp folder and run the cases in a restricted child; the runner is itself TypeScript, run by Node directly |
| `tools/finalize.py` | clean code (no fence) and a Markdown report |
| `tools/common.mjs` | reading stdin, extracting the code block, printing the verdict |
| `examples/slugify.cases.json`, `examples/duration.cases.json` | test cases for two example functions |
| `examples/retry_demo.py` | the retry loop with a scripted model (step 2) |
| `package.json` | the one dependency, `typescript`, for type checking |
| `../../tests/test_ts_verify.py` | the tests: the whole graph with a scripted model, and each tool on its own |

Limits: the compiler is given the language only, with no DOM or Node typings, so the function must be pure. A tool starts a process per firing (about 70 ms for Node, more for `tsc`).
