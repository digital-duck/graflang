# notes_digest

Reads a notes file, has a model write a digest (what happened, the decisions with owners and dates, the open questions), records the digest, saves it and prints it.
Everything that touches a file sits behind a Cedar guard.

```
notes_digest    allowed (guard) -> read -> digest -> publish
  read/         read input/notes.md (QUERY)
  digest/       summarise (one model call), then OBSERVE the digest into the run log
  publish/      save to output/digest.md and print (EMIT)
```

Inputs: none. Output: `digest`. Model calls: 1.

```bash
graf run cookbook_v2/notes_digest/notes_digest.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5
graf trace                     # the same run as a timeline
```

Edit `read/input/notes.md` to digest your own notes; the result is `publish/output/digest.md`. Policy: `policies/digest.cedar`. Original: `cookbook/notes_digest`.
