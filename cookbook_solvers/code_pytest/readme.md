# Recipe 79 — Code Generation + Pytest Verification

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/079_code_pytest` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> `code_pytest.spl` are SPL workflows that graphs here call (`procedure_ref`); running those graphs also needs SPL.py importable (`pip install 'graflang[spl]'`).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 479 tokens in / 296 out in total); needs SPL.py importable (`procedure_ref`); the generated code passed its 27 tests (VERIFIED). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `pytest` (stdlib in most environments; `pip install pytest` if missing)

## Relationship to Recipe 50

Recipe 50 (`code_pipeline`) is a full software development lifecycle orchestrator: spec analysis, code generation, LLM code review, improvement, testing, documentation, and spec-closure check — across 8 sub-workflows.

Recipe 79 isolates and upgrades the most important step: **testing**. In recipe 50, the "test" is an LLM asked to roleplay as a test runner. In recipe 79, pytest actually executes. These produce fundamentally different verdicts:

| | Recipe 50 (`test_code.spl`) | Recipe 79 (`code_pytest.graph.yaml`) |
|---|---|---|
| How verdict is produced | LLM reviews code against spec, returns `[PASSED]` or `[FAILED]` | pytest runs test cases, returns exit code 0 or non-zero |
| Mode | Probabilistic | **Deterministic** |
| Can be fooled? | Yes — LLM can mistake plausible-looking code for correct code | No — pytest counts actual pass/fail assertions |
| What `ASSERT` certifies | "LLM thought it looked right" | **"All test cases passed"** |

## What this demonstrates

The central claim of the TMLR paper: `ASSERT` in SPL is a **ground-truth oracle**, not a proxy. This recipe makes that concrete in the software domain.

```
GENERATE write_code(spec)          ← probabilistic: LLM writes code from intent
GENERATE write_tests(spec)         ← probabilistic: LLM writes tests from same intent
CALL run_pytest(code, tests)       ← deterministic: subprocess executes, returns JSON
ASSERT all_tests_passed(result)    ← formal gate: execution stops here if any test fails
GENERATE explain_solution(...)     ← probabilistic: LLM explains the verified result
```

**The independence invariant**: both code and tests are generated from the spec, not from each other. Tests written by reading the code under test are circular — they prove nothing. Tests written from the spec are an independent correctness oracle.

This is the same `GENERATE → CALL solver → ASSERT → WHILE repair` pattern as:
- **Recipe 75** (SymPy): symbolic algebra oracle
- **Recipe 78** (PuLP): LP/MIP optimality certificate
- **Recipe 79** (pytest): software correctness certificate

## Setup

pytest is included in most Python development environments. If not present:

```bash
pip install pytest
```

No additional configuration needed. The recipe writes code and tests to a temporary directory, runs pytest as a subprocess, and cleans up — no side effects on the filesystem.

## Run

```bash
# Default spec (merge two sorted lists, O(n+m))
graf run cookbook_solvers/code_pytest/code_pytest.graph.yaml \
    --llm claude_cli

# More repair attempts (default 3)
graf run cookbook_solvers/code_pytest/code_pytest.graph.yaml \
    --llm claude_cli \
    --param max_tries=5

# Custom spec
graf run cookbook_solvers/code_pytest/code_pytest.graph.yaml \
    --llm ollama:gemma3 \
    --param spec="Write a Python function count_words(text) that returns a dict mapping each word to its frequency. Words are case-insensitive and punctuation is stripped."
```

## Execution flow

```
GENERATE write_code(@spec)          -- LLM writes Python module from spec
GENERATE write_tests(@spec)         -- LLM writes pytest cases from same spec (independently)
    │
WHILE @tries < @max_tries:
    CALL run_pytest(@code, @tests)  -- subprocess runs pytest in temp dir
    CALL get_pytest_status(result)  -- "passed" or "failed"
    ├── "passed" → exit loop
    └── "failed"
            │
        CALL get_pytest_output()    -- extract actual failure messages
        GENERATE repair_code(...)   -- LLM rewrites with real error context
        @tries += 1
    │
ASSERT all_tests_passed(@pytest_result)   -- hard gate: AssertionError if any test failed
    │
GENERATE explain_solution(...)      -- LLM explains the verified result
CALL format_report(...)             -- Markdown report
```

## Why this matters for the TMLR argument

ZXT2 argued that SPL's `ASSERT` only tracks "whether code ran" — i.e., execution success. Recipe 79 refutes this directly:

- **Execution success ≠ correctness**: pytest can exit 0 only when all test assertions pass, not just when the code runs without raising an exception. A function that returns `None` for every input will execute successfully but fail all tests.
- **`all_tests_passed()` is a formal correctness certificate** within the test suite's scope: it returns `True` if and only if pytest exit code is 0, failed count is 0, and passed count is > 0.
- **The repair loop is grounded in actual failure output**: the LLM's repair prompt includes the exact pytest traceback — `AssertionError: assert merge_sorted([1,3],[2,4]) == [1,2,3,4]` — not a vague description. This grounds the probabilistic repair in deterministic feedback.

## Connection to software engineering practice

The `GENERATE → test → ASSERT → WHILE repair` loop is a formal implementation of **Test-Driven Development** at the agentic level:
1. Write tests from spec (red)
2. Generate code (green attempt)
3. If tests fail, repair code with failure context (refactor)
4. `ASSERT` certifies the loop converged

In LangChain or PDL (https://github.com/IBM/prompt-declaration-language/tree/main), implementing this loop requires: a subprocess runner tool, a loop construct, conditional branching on exit code, a repair prompt, and manual wiring between all of them. In SPL, it is the natural expression of the language.
