# 056 — Majority Vote  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/056_majority_vote` with `spl3 util spl2graph` (AST-direct, no model involved); source `majority_vote.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-majority-vote](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-majority-vote)
**Difficulty:** —
**Category:** reliability

## What it does

Generates three independent answers to a reasoning question in parallel via `CALL PARALLEL`, tallies the answers with a deterministic vote counter, and returns the majority answer — or the first top candidate if there is a tie. This pattern improves reliability on reasoning tasks where a single LLM sample may be unstable, replacing one probabilistic answer with the most frequent answer across three independent samples.

## Real-world use cases

- **Reliability on ambiguous reasoning**: Reduce answer variance on math word problems, logical deductions, or factual questions by sampling three times and taking the mode
- **Ensemble classification**: Apply majority voting to sentiment classification, topic categorization, or intent detection to reduce single-sample noise
- **Safety-critical decisions**: Use three independent samples for any branching decision where a wrong single-sample answer has high cost (e.g., triage routing, compliance checks)
- **Benchmark evaluation**: Measure how often models agree with themselves across three samples as a proxy for answer confidence without requiring calibration data

## Key SPL constructs

- `CALL PARALLEL attempt_reasoning(@question) INTO @ans1, attempt_reasoning(@question) INTO @ans2, attempt_reasoning(@question) INTO @ans3 END` — three concurrent independent samples
- `CREATE TOOL_API tally_votes(answers)` — `Counter`-based majority vote; returns JSON with `winner`, `first_candidate`, `consensus`
- `CREATE FUNCTION attempt_reasoning(question)` — single-shot answer generation with no chain-of-thought
- `EVALUATE @consensus WHEN contains("yes")` — takes the clear majority `winner`; falls back to `first_candidate` on tie
- String concatenation: `@collected := @ans1 + "\n" + @ans2 + "\n" + @ans3` — assembles answers for the tally tool

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@question` | TEXT | _(required)_ | The reasoning or factual question to answer |

**Output:** `@answer TEXT` — the majority-vote answer across three independent samples

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/majority_vote/majority_vote.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Scale to five samples by adding `@ans4` and `@ans5` to the `CALL PARALLEL` block for a stronger majority on highly ambiguous questions
- Chain with `017_judge` to run the majority-vote answer through a final judge step that evaluates the voted answer for correctness and coherence
- Use different models for each parallel branch (e.g., two fast models + one strong model) by parameterizing the `--llm` per branch
- Combine with `014_thinking` to vote across three independent chain-of-thought solutions rather than single-shot answers
