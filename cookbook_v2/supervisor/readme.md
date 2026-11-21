# supervisor

A worker answers a question and a supervisor reviews the answer. If it is not approved, the worker sees the supervisor's note and tries again, for a few rounds. The whole review
loop is one composite whose outcome is "approved" or an error exit.

```
supervisor      supervise -> approved? -> answer + "approved by the supervisor" | answer + "not approved after N rounds"
  supervise/    first answer (worker), then the loop: review (supervisor) -> if rejected, retry (worker, with the note)       exit unapproved (E_NOT_APPROVED)
```

Inputs: `question`, `max_rounds` (default 3). Outputs: `answer`, `status`. Model calls: 2 when the first answer is approved; each rejected round adds a retry and a review,
at most `1 + 2 * max_rounds`.

```bash
graf run cookbook_v2/supervisor/supervisor.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 --param question="Why is the sky blue?"
```

The rejection and give-up paths are exercised offline by `tests/test_cookbook_v2.py` with a scripted model. Original: `cookbook/supervisor`.
