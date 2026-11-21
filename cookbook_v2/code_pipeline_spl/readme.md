# code_pipeline_spl (layered)

The same workflow as `cookbook/code_pipeline`, written as a short top graph and three composites, each in its own folder with the procedures
and files it uses. The original stays as it is (the experiment arms and several tests run it); this one is the layered form.

```
code_pipeline_spl.graph.yaml        understand -> build -> finish -> exit          (stop on the error exit `vague`)
  understand/                   analyze the spec; error exit `vague` (code E_SPEC_VAGUE) when it is not [READY]
  build/                        the test-gated loop: generate, review, improve, test, guard (+ tools.py, policies/)
  finish/                       document, then optionally extract + judge + merge (the closure check)
graflang.errors.yaml            E_SPEC_VAGUE: what it means and what to do
```

See the levels:

```bash
graf vis cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml                  # depth 0: the top level, four boxes
graf vis cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml --depth 1        # open them
graf describe cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml --depth 0 -o -
graf expand cookbook_v2/code_pipeline_spl/code_pipeline_spl.graph.yaml --depth all   # the flat graph the runtime runs
graf errors E_SPEC_VAGUE --dir cookbook_v2/code_pipeline_spl
```

Same inputs, output and behaviour as the original (see `tests/test_cookbook_v2.py`, which runs both offline and compares). Requirements and the
real-run notes: `cheap.bind.yaml` and `cookbook/code_pipeline/readme.md`.
