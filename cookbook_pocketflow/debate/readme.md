# 018 — Debate  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/018_debate` with `spl3 util spl2graph` (AST-direct, no model involved); source `debate.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-debate](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-debate)
**Difficulty:** ★☆☆
**Category:** multi-agent

## What it does

Runs a structured two-agent debate: `CALL PARALLEL` dispatches a Proponent and an Opponent LLM simultaneously to generate their opening arguments, then a WHILE loop drives successive rounds where each side rebuts the other's most recent argument. A judge LLM scores each round and issues a winner verdict when one side achieves a decisive lead. This demonstrates how SPL parallelism and multi-agent turn-taking combine in a single workflow.

## Real-world use cases

- **Decision-support systems**: Surface the strongest arguments for and against a business decision before a board meeting, without requiring a human to argue both sides
- **Red-teaming and adversarial review**: Automatically surface weaknesses in a proposal by pitting a defender against a critic, revealing attack vectors that one-sided analysis would miss
- **Educational content generation**: Generate pro/con argument pairs for debate training, policy courses, or interview prep material
- **Research hypothesis testing**: Stress-test a scientific hypothesis by generating a rigorous rebuttal and assessing whether the hypothesis survives the challenge

## Key SPL constructs

- `CALL PARALLEL argue_for(@claim) INTO @pro_argument` / `argue_against(@claim) INTO @con_argument` — simultaneous opening statements
- `WHILE @iteration < @max_iterations DO` — debate round loop
- `GENERATE rebut_pro(@claim, @pro, @con)` / `rebut_con(@claim, @pro, @con)` — sequential rebuttal generation
- `GENERATE judge_debate(@claim, @pro, @con)` — scores the round and signals a winner
- `EVALUATE @winner WHEN contains("winner")` — exits the loop when the judge names a winning side

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@claim` | TEXT | _(required)_ | The proposition to debate |
| `@max_iterations` | INTEGER | 5 | Maximum number of rebuttal rounds |

**Output:** `@verdict TEXT` — the judge's final summary including the winning side and rationale

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/debate/debate.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add a `--param claim=` override to debate arbitrary propositions without editing the workflow
- Use `--adapter momagrid` to dispatch the Proponent and Opponent to different Momagrid worker nodes for true physical separation
- Log each round's arguments to a file with `CALL write_file` for post-debate analysis or training data collection
- Chain with `056_majority_vote` to run three independent debate instances and take the majority verdict
