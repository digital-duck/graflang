# code_gen

A spec in, a project folder out. One model call writes the files (each introduced by a line `=== FILE: path ===`), and `tools/collect_files.py` splits
the reply into them: paths made safe, an `__init__.py` in every Python folder, a README.md from the spec if the model gave none.

```bash
graf run cookbook_v2/code_gen/code_gen.graph.yaml --llm claude_cli:claude-haiku-5-5 \
    --param spec="a small web app: a Flask backend with /api/todos (list, add) and a plain HTML/JS frontend that uses it" --param lang=python
```

The files appear in `cookbook_v2/code_gen/.graf/codes/<run>/` (any layout: `backend/`, `frontend/`, ...); the run's other files (`result.json`, `nodes/`) are in
`.graf/outputs/<run>/`. One model call. For review, tests and documentation use `cookbook_v2/code_pipeline`.
