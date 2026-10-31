
## Programs the app may run (this run allows code)

A step may run a program you write in `tools/NAME.py` (Python 3, standard library only): it reads one JSON object on stdin and prints one line of JSON on stdout.

```yaml
  - check: {node: SOLVE, in: {text: draft.text}, ports: [trigger, complete, in_text, out_result],
            out: result, backend: subprocess, command: ["python3", "-I", "tools/check.py"], out_type: JSON, timeout: 30}
```

The JSON on stdin has one key per `in:` name. A step's output can be read as `check.result`; for a field of it use `solve: "json_get(@in_result, 'field')"` or `json_get(@in_result, 'field') == TRUE` in a condition. Keep programs small and deterministic: no network, no files outside the app folder, no subprocesses.
