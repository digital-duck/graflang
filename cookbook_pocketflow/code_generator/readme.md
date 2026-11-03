# 054 — Code Generator (Test-Driven)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/054_code_generator` with `spl3 util spl2graph` (AST-direct, no model involved); source `code_generator.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-code-generator](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-code-generator)
**Difficulty:** —
**Category:** agent

## What it does

A test-driven code generation agent: it first generates a test suite for the problem, then generates a solution, and runs a WHILE loop that executes the tests against the solution — analyzing failures, deciding whether to revise the code or regenerate the tests, and iterating until all tests pass or the iteration cap is reached. The `run_tests` tool executes Python test functions in-process via `exec()` with concurrent thread-per-test isolation.

## Real-world use cases

- **Automated code synthesis**: Generate working Python functions from problem descriptions with test-driven correctness guarantees rather than unchecked LLM output
- **Coding challenge solutions**: Solve competitive programming or interview problems by generating tests from the problem statement and iterating until they pass
- **Prototype-to-production scaffolding**: Generate an initial implementation from a natural language spec, with auto-generated tests serving as an acceptance suite
- **LLM capability benchmarking**: Run the same problem across multiple models to compare how many iterations each takes to achieve full test pass

## Key SPL constructs

- `CREATE TOOL_API run_tests(solution, tests)` — executes Python test functions in-process via `exec()` + `ThreadPoolExecutor`; returns JSON with `all_passed`, `passed`, `failed`, `details`
- `CREATE FUNCTION generate_tests(@problem, @failure_analysis)` — LLM writes a pytest-style test suite from the problem description
- `CREATE FUNCTION implement_solution(@problem, @tests, @failure_analysis)` — LLM writes a solution that satisfies the test suite
- `CREATE FUNCTION analyze_failures(@solution, @tests, @test_results)` — LLM interprets failure details and identifies the root cause
- `CREATE FUNCTION decide_revision(@problem, @failure_analysis)` — LLM decides whether to fix code or regenerate tests: returns "code" or "tests"
- `WHILE @i < @max_iterations DO` — TDD loop
- `EVALUATE @all_passed WHEN contains("true")` — exits loop on green test suite

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@problem` | TEXT | _(required)_ | Natural language description of the coding problem |
| `@max_iterations` | INTEGER | 5 | Maximum number of generate-test-revise cycles |

**Output:** `@result TEXT` — the final solution code and test run summary

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/code_generator/code_generator.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add `CALL write_file(@solution_path, @solution, "w")` after the loop to persist the best solution to disk automatically
- Replace the in-process `run_tests` with a sandboxed subprocess runner for safety when testing untrusted code
- Use `CALL PARALLEL` to generate multiple independent solution candidates and take the first one that passes all tests
- Chain with `040_coding_agent` to have the code generator produce a solution and the coding agent handle edge cases discovered post-generation
