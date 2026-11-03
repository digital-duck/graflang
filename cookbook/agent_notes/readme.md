# agent_notes

A small **agent**: decide, act, observe, repeat. Each round the model replies with one JSON object: either `{"action": "read", "file": ...}` (a tool call: read one note) or `{"action": "answer", "text": ...}`. What it read is added to its history for the next round. PocketFlow's agent and TAO (thought, action, observation) examples, as a graph.

| | |
|---|---|
| Inputs | `question` (TEXT), `max_steps` (INTEGER, default 4) |
| Output | `answer` (TEXT) |
| Model calls | 1 per round: 2 when it reads one note and answers |

```bash
graf run cookbook/agent_notes/agent_notes.graph.yaml --param question="How much is the Team plan per user, and is single sign-on included?"
graf trace            # the rounds as a timeline
```

Tried with `claude_cli:claude-haiku-5-5`: it read `pricing.md`, then answered "29 euro per user per month, and single sign-on is included" (2 calls).

**What the graph decides, not the model:**

- The note must be on a fixed list (`pricing.md`, `holidays.md`, `contacts.md`): the `wants_read` condition checks it. Any other request (a path like `../policies/read.cedar`, an unknown name) ends the loop with no read, and the graph answers `(no answer within N steps)` instead of passing off nothing as an answer. The same text comes back when the cap is reached.
- The tool is a `QUERY`, behind a Cedar `GUARD` (`policies/read.cedar`). A loop that holds a risky node is itself risky, so the guard sits in front of the whole loop; `QUERY` also keeps every path inside this folder.
- The loop has a cap (`max_steps`), and each note read is recorded by an `OBSERVE` node (`observations.jsonl` in the run's folder).

`tests/test_patterns_recipes.py` covers read-then-answer (the second round sees the first note), a refused file and the cap, with a scripted model.

The agent here has one tool. Adding another (a calculator through a `SOLVE`, a search through a `RUN` http) is a second branch after `wants_read`, each behind its own guard.
