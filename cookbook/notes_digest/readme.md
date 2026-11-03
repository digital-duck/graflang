# notes_digest

Read a notes file, summarise it, record what was read, write the digest to a file and to the terminal. It is the smallest recipe that uses the three nodes that reach **outside** the graph:

| Node | Used for |
|---|---|
| `QUERY` | `read_notes` reads `input/notes.md`, the sample notes bundled in this folder |
| `OBSERVE` | `watch` records the digest in the log and in `observations.jsonl` in the run's output folder, and hands it on |
| `EMIT` | `save` writes `output/digest.md`; `show` prints it |

`QUERY` and `EMIT` are risky, so both sit behind the Cedar `GUARD` `allowed` (`policies/digest.cedar`); `graf validate` refuses the graph if a path goes round it. Paths cannot leave this folder (a `file: ../x` fails `graf validate`). Used as a part of another graph, the notes are still read from this folder, and the digest is written here too.

```bash
graf run cookbook/notes_digest/notes_digest.graph.yaml
graf trace                     # the same run as a timeline
```

Tried with `claude_cli:claude-haiku-5-5`: 1 model call; the digest was written to `output/digest.md` and printed. In the editor's dry run (the mock adapter) the `EMIT` nodes only report what they would have done.

To send the digest by e-mail instead, change `save` to `channel: email` with `recipients`, `sender` and `smtp_host`, and set `GRAF_SMTP_USER` and `GRAF_SMTP_PASSWORD` where it runs. The recipients are fixed in the graph: a model cannot change them (see the user guide, "QUERY, EMIT and OBSERVE").
