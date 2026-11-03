# release_approval

A model drafts an announcement, **a person decides**, a Cedar guard checks the decision, and only then is the file written. It is the first recipe with a `DECISION` node (a step whose decider is a person).

| | |
|---|---|
| Input | `topic` (TEXT) |
| Output | `result` (TEXT): the announcement when released, else `held, not released: <the person's note>` |
| Model calls | 1 |

```bash
graf run cookbook/release_approval/release_approval.graph.yaml --param topic="Friday demo moved to 3pm"            # asks at the terminal: yes / no, with an optional note after |
graf run cookbook/release_approval/release_approval.graph.yaml --param topic="..." --answer "approve=yes|ok" --by wen   # for scripts and CI
```

- The `DECISION` node `approve` shows the draft (`in_context`) with the question and accepts `yes` or `no` (anything else is asked again, three times at most). Its `default` is `no`, so with no terminal and no `--answer` the announcement is held, not released.
- The answer is data. The `allowed` GUARD feeds `@in_answer == 'yes'` to Cedar as `human_approval`; `policies/release.cedar` permits the publish only when it is true, and the `EMIT` sits behind that guard's `allow` port as `graf validate` requires. A person's yes does not replace the guard.
- `graf validate` warns when a `DECISION` has a default and can reach a risky node, as a reminder that the default is what happens if nobody answers. Here `safe_default: true` says that `no` is the safe answer and silences it.
- Only the interactive mode exists. A parked run (the process exits, a pending file waits for `graf answer`, `--resume` continues) is designed in `docs/DEV/DESIGN/graflang-hitl.md` but not built.

Tried with `claude_cli:claude-haiku-5-5` and `--answer`: it drafted, the file was written. Without a terminal and no `--answer`, the run took the default and held the draft.
