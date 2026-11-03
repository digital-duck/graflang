# 010 — Multi Agent  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/010_multi_agent` with `spl3 util spl2graph` (AST-direct, no model involved); source `multi_web_search_agent.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-multi-agent](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-multi-agent)
**Difficulty:** ★☆☆
**Category:** multi-agent

## What it does

Implements a two-agent Taboo word-guessing game where a Hinter and a Guesser are distinct LLM personas running inside a single WHILE loop. The Hinter must describe the target word without using it or any forbidden words; the Guesser reads the hint and wrong-guess history and produces a single-word answer. A deterministic exact-match tool decides correctness — separating the probabilistic reasoning from the deterministic outcome check.

## Real-world use cases

- **Training data generation**: Generate diverse adversarial constraint satisfaction examples (one agent constrained, one interpreting) for fine-tuning or evaluation datasets
- **Negotiation simulation**: Model two-party negotiation where each party has private information and must communicate without revealing it directly
- **Puzzle and game design**: Prototype word games, escape room puzzles, or other turn-based scenarios with adversarial LLM agents
- **Multi-agent workflow testing**: Validate that SPL's per-GENERATE isolation keeps agent personas strictly separate across turns

## Key SPL constructs

- `CREATE TOOL_API is_correct_guess(guess, target)` — deterministic exact-match (no LLM) for game outcome
- `CREATE FUNCTION hinter_agent(@target_word, @forbidden_words, @wrong_guesses)` — constrained hint generation
- `CREATE FUNCTION guesser_agent(@hint, @wrong_guesses)` — guess generation with prior-error avoidance
- `WHILE @turn < @max_turns DO` — game loop with force-exit on correct guess
- `EVALUATE @check WHEN contains("correct")` — branches to win vs. accumulate wrong guess
- `CALL list_append(@wrong_guesses, @guess)` — maintains the running wrong-guess list

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@target_word` | TEXT | _(required)_ | The secret word the Guesser must identify |
| `@forbidden_words` | TEXT | _(required)_ | Comma-separated list of words the Hinter must avoid |
| `@max_turns` | INTEGER | 5 | Maximum rounds before the game ends |

**Output:** `@result TEXT` — "Game Won! The target word was: X" or "Game Over: the target word was not guessed."

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/multi_agent/multi_web_search_agent.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add a third `GENERATE judge_hint(@hint, @forbidden_words)` step that validates the Hinter's output before passing it to the Guesser — adding a referee agent to a two-player game
- Wrap with `CALL PARALLEL` to run multiple game instances simultaneously for tournament-style evaluation
- Replace `list_append` with a log to file to collect training examples of successful and failed hint strategies
- Add `EXCEPTION WHEN` handling for cases where the Hinter inadvertently includes the target word
