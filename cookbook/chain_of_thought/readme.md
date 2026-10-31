# chain_of_thought

Research a topic, analyze the findings, summarize the analysis. Three `GENERATE` nodes in a line, each reading the one before; every step also gets the original topic, so the analysis and the brief keep covering what the topic asked for (background and causes, current state, consequences), and each prompt asks for the text only (no preamble, closing offers or next-steps section). It is a graph **lifted from an SPL workflow** (`SPL.py/cookbook/009_chain_of_thought/chain.spl`) by `spl2graph`, kept as an example of that route; the three `CREATE FUNCTION` bodies became the prompts (then edited: see below).

```
wf_entry -> gen_1 (research) -> gen_2 (analyze) -> gen_3 (summarize_analysis) -> wf_exit
   topic ------^------------------------^------------------------^   (the topic reaches all three)
```

| | |
|---|---|
| Input | `topic` (TEXT, default `distributed AI inference`) |
| Output | `summary` (TEXT): a short executive brief |
| LLM calls | 3 |
| Cassette | `chain_of_thought.cassette.jsonl`: the three calls recorded with `claude_cli` |

## Run

From the repo root:

```bash
# replay the recorded answers: no model, no network, same output every time
graf run cookbook/chain_of_thought/chain_of_thought.graph.yaml --replay cookbook/chain_of_thought/chain_of_thought.cassette.jsonl --param topic="solar sails"

# a real model
graf run cookbook/chain_of_thought/chain_of_thought.graph.yaml --llm claude_cli:claude-sonnet-5-5 \
--param topic="russia-ukraine conflict: root cause, current state, potential fallout"

# record a new cassette
graf run cookbook/chain_of_thought/chain_of_thought.graph.yaml --param topic="tidal power" --record my.cassette.jsonl
```

A cassette is keyed by model, prompt and temperature, so `--replay` only answers the topic it was recorded for (`solar sails`, not the graph's default); a different topic or edited prompt is an unrecorded call and fails loudly.

## Things to check

- `graf compile --lang spl` writes the graph back as a `.spl` file with the same three functions.
- The summary's quality depends on the model; the cassette fixes it so the test (`tests/`) can run offline.
