# self_heal

Self-healing extraction. The model extracts a contact as JSON; a **rule** (not another model) checks it; if the check fails the model is shown its own rejected answer and asked again, at most `max_rounds` times. PocketFlow's `pocketflow-self-healing-mermaid` is the same shape (compile the diagram, feed the error back); `cookbook/ts_verify` does it with a compiler.

| | |
|---|---|
| Inputs | `text` (TEXT), `max_rounds` (INTEGER, default 3) |
| Outputs | `record` (TEXT, the JSON), `status` (TEXT: `valid`, or `still invalid after N rounds; the last attempt is shown`) |
| Model calls | 1 when the first answer passes; 1 + one per retry |

```bash
graf run cookbook/self_heal/self_heal.graph.yaml --param text="Please send the invoice to Maria Lopez (maria.lopez@acme.example) by Friday."
graf run cookbook/self_heal/self_heal.graph.yaml --param text="Call Tom Baker about the contract, no email on file."
```

Tried with `claude_cli:claude-haiku-5-5`: the first text passed at once (1 call); the second had no email, the check rejected the empty field, the model was asked again and answered `"email": "unknown"` (2 calls). `tests/test_patterns_recipes.py` covers a valid first answer, a code-fenced answer that is healed, and the give-up path.

The check is `json_get(@in_raw, 'name') != '' AND json_get(@in_raw, 'email') != ''`; `json_get` returns an empty string for text that is not valid JSON, so a code fence or a comment fails the check like a missing field.
