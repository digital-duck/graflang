# heartbeat

One beat of a watcher. It reads a message file, and only if it grew since the last beat, summarises the new messages, prints and logs the summary, and remembers how many it has
seen. Run it on a schedule with `graf watch`.

```
heartbeat       allowed (guard) -> news -> fresh? -> announce | quiet
  news/         how many messages, how many were seen last time, how many are new     quiet exit: nothing new, no model call
  announce/     summarise the new ones (model), print, log, remember the count
```

Inputs: `inbox` (default `input/inbox.md`), `state_file` (default `output/state.txt`, an addition to the original). Output: `status`. Model calls: 1 per beat with news, 0 otherwise.

```bash
graf run cookbook_v2/heartbeat/heartbeat.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5   # first beat: new messages
graf run cookbook_v2/heartbeat/heartbeat.graph.yaml                                                                                      # second beat: nothing new
graf watch cookbook_v2/heartbeat/heartbeat.graph.yaml --every 60 --times 3                                                              # three beats, a minute apart
```

Add a line to `input/inbox.md` between beats to see a new summary. The alerts log is in `announce/output/`. Delete `output/state.txt` to forget what was seen.
Policy: `policies/watch.cedar`. Original: `cookbook/heartbeat` (the equivalence test runs three beats).
