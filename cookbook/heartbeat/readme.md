# heartbeat

One **beat** of a heartbeat: is there anything new since the last beat? If so, the model writes a one-line summary, which is printed and appended to `output/alerts.md`; if not, the beat ends and **no model call is made**. `output/state.txt` holds the number of lines seen so far, so each beat remembers the one before. Run the beats on a schedule with `graf watch`. It is PocketFlow's heartbeat example without the mailbox: the inbox is a text file, one message per line.

| | |
|---|---|
| Input | `inbox` (TEXT, default `input/inbox.md`) |
| Output | `status` (TEXT): `new: <summary>` or `nothing new (N messages)` |
| Model calls | 1 on a beat with news, 0 on a quiet one |

```bash
graf watch cookbook/heartbeat/heartbeat.graph.yaml --every 60 --times 5      # a beat a minute, five beats
echo "- 10:15 Ops: disk alert" >> cookbook/heartbeat/input/inbox.md           # the next beat reports it
```

The two `QUERY`s and the three `EMIT`s sit behind the Cedar `GUARD` `allowed` (`policies/watch.cedar`); paths cannot leave this folder. To start over, delete `output/state.txt`. A change that only edits earlier lines of the file is not seen (the beat counts lines).

Tried with `claude_cli:claude-haiku-5-5` under `graf watch`: the first beat summarised both messages in one line and wrote `state.txt` = 2 and the alert; a scripted test (`tests/test_decision.py`) covers the quiet beat and a new line.
