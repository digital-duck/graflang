# code_pipeline (layered, repository-capable)

A spec in, a verified project folder and its documentation out. The build is `cookbook/code_parts`' loop, inside the layered form.

```
code_pipeline.graph.yaml        understand -> build -> finish -> exit          (stop on the error exit `vague`)
  understand/                   is the spec clear enough? (prompt) ; error exit `vague` (E_SPEC_VAGUE)
  build/                        write the project as files, review, then rounds of: improve -> split into files -> RUN them -> retry on failure
  finish/                       document the code, then optionally derive a spec back from it and judge it against the original (SPL procedures 05-07; needs SPL.py)
tools/                          collect_files.py (split the reply into files), verify_project.py (syntax, imports, the project's tests, an optional smoke test)
```

Outputs: `docs` (TEXT), `code` (FILES: real files in `.graf/codes/<run>/`, any layout the model chose, e.g. `backend/` and `frontend/`) and `report` (what the last
verification found, `[PASSED]` or `[FAILED]`). The run's other files (result.json, `nodes/`) are in `.graf/outputs/<run>/`.

```bash
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --bind cookbook_v2/code_pipeline/cheap.bind.yaml          # cheap, capped
graf run cookbook_v2/code_pipeline/code_pipeline.graph.yaml --llm claude_cli:claude-sonnet-5-5 \
    --param spec="a Flask backend with /api/todos (list, add) and a plain HTML/JS frontend that uses it" --param max_cycles=3 --bind <a file with limits.max_llm_calls>
```

`verify_project.py` RUNS the generated code on this machine (a timeout, no sandbox; Python projects only, other languages are reported as not checked). Give a
`smoke` parameter (Python run against the real libraries) to catch a wrong call that a model's own fake-based tests let through. `reference` carries API facts the model
cannot know.

Related: `cookbook_v2/code_gen` is the one-call version (no review, no run); `cookbook_v2/code_pipeline_spl` is the faithful port of `cookbook/code_pipeline` (SPL procedures,
one block of code, no project folder).
