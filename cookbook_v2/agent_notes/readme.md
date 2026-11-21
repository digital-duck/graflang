# agent_notes

A small agent over a folder of notes (`notes/`: pricing, holidays, contacts). Each round the model either asks to read one listed note or answers. The graph, not the model, decides
what a tool call may do: only the listed files can be read, and the read goes through a Cedar guard.

```
agent_notes     allowed (guard) -> research -> answered? -> answer | gave_up
  research/     the loop: decide (model) -> may it read that note? -> read it -> observe -> add to the history      exit gave_up (E_NO_ANSWER)
```

Inputs: `question`, `max_steps` (default 4). Outputs: `answer`. Model calls: one per round, at most `max_steps`.

```bash
graf run cookbook_v2/agent_notes/agent_notes.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 \
    --param question="How much is the Team plan per user, and is single sign-on included?"
graf trace            # the rounds as a timeline
```

Try a question the notes cannot answer: after `max_steps` rounds the `gave_up` exit fires with code `E_NO_ANSWER`.
Policy: `policies/read.cedar`. Original: `cookbook/agent_notes` (same outputs and calls, checked by `tests/test_cookbook_v2.py`).
