# hello_world

Writes a "Hello, <name>!" program in a chosen language, then **runs it** and shows what it printed. Two ways to get the program:

- `mode=llm` (default): an LLM writes it. If the reply has no code block, it is run only when it is valid code (so prose, or the mock adapter's placeholder, gives `(not run: ...)`); a fenced block is always run, and a failure is reported in `result`, never raised.
- `mode=solver`: a deterministic program (`tools/hello_world.py`) writes it. No LLM call.

Both then meet at a Cedar `GUARD` (`policies/run.cedar`): only Python and JavaScript are run (the program for any other language is returned, with a note that it was not run). The run itself (the `run_code` step, `grafr/run_code.py`) happens in a throwaway folder with an empty environment, no input and a 10 second limit, and never fails the graph: no code, a missing interpreter, a crash or a timeout come back as a note in `result`. It runs code a model wrote, so it is marked `risky` and sits behind the guard; remove the `run` step if you do not want that.

| | |
|---|---|
| Inputs | `language` (default `Python`), `name` (default `World`), `mode` (`llm` or `solver`, default `llm`) |
| Outputs | `program` (the source code), `result` (what it printed, or why it was not run) |
| Model calls | 1 in `llm` mode, 0 in `solver` mode |

```bash
graf run cookbook/hello_world/hello_world.graph.yaml --param name=Wen
graf run cookbook/hello_world/hello_world.graph.yaml --param name=Wen --param mode=solver --param language=javascript
```

Solver mode writes c, go, java, javascript (alias `js`), python, ruby and rust; an unsupported language or an invalid name name stops that branch with an error.
