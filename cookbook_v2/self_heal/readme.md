# self_heal

Extract a contact (name and email) from free text as JSON, check it, and when the check fails ask the model again with the failure, for a few rounds.

```
self_heal       extract -> heal -> valid? -> record + "valid" | record + "still invalid after N rounds"
  extract/      first attempt (one model call)
  heal/         the loop: check the JSON and the email -> if bad, a fix call that sees the problem         exit invalid (E_STILL_INVALID)
```

Inputs: `text`, `max_rounds` (default 3). Outputs: `record`, `status`. Model calls: 1, plus one per failed check, at most `1 + max_rounds`.

```bash
graf run cookbook_v2/self_heal/self_heal.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 \
    --param text="Please send the invoice to Maria Lopez (maria.lopez@acme.example) by Friday."
graf run cookbook_v2/self_heal/self_heal.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 \
    --param text="Call Tom Baker about the contract, no email on file."          # the check rejects the empty email, the model is asked again
```

Original: `cookbook/self_heal`.
