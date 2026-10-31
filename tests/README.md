# Tests

```bash
pytest                 # offline: no model, no network (the default)
pytest --mode llm      # only the tests that call a real model
pytest --mode all      # both
```

`--mode` is the only way to choose by kind; pytest's own `-m` is refused (SPL uses `-m` for `--model`).

## The two modes

| | `pytest` (default) | `pytest --mode llm` |
|---|---|---|
| Runs | every test not marked `llm` | only the tests marked `@pytest.mark.llm` |
| Model | none: stub or recorded models (`Scripted`, cassettes), the `mock` adapter | real `claude_cli`, `claude-sonnet-5-5` |
| Cost | free, about 50 s | billed, about 5 minutes |
| When | every change | before a release, or after touching GENERATE, lifecycle, loops or the adapters |

The real-model tests are small on purpose (a few short calls each, one per feature area). A new feature gets its offline tests first and, where a model changes the result, one `llm` test.

## Writing a test for each mode

```python
def test_something_offline():                 # runs by default
    ...

@pytest.mark.llm
def test_real_llm_does_something():           # runs with --mode llm
    out = GraphLangRuntime(graph, adapter="claude_cli", verbose=False).execute({...})
```

Use a call budget when a real test runs a loop (see `limits.max_llm_calls` in the user guide); a loop that never exits can make hundreds of billed calls.

## Other things to know

- Run with the `graf` environment's Python (`python -m pytest`): the system Python lacks `zinet`.
- 7 tests fail today and are known: `test_cedar_compiler.py` (6) and `test_policy_slicer.py::test_slice_by_context_keys` (1), in the hand-written Cedar compiler that is left alone.
- Some tests skip when something is not installed: Streamlit (editor app), a Docker daemon with `python:3.12-slim` (real container tests), SPL.py (lifting and the PocketFlow corpus), Node 22.18+ (`ts_verify`).
- One file: `pytest tests/test_parts.py -q`; one test: `pytest tests/test_parts.py::test_name -q`.
- `docs/DEV/DESIGN/graflang-verify.md` maps every feature to its test file and gives the manual checks.
