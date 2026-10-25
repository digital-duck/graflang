# Data: HumanEval

`HumanEval.jsonl.gz` is the HumanEval benchmark: 164 hand-written Python programming problems, each with a prompt (signature and docstring), a canonical solution, hidden unit tests (`test`) and an `entry_point`.

| | |
|---|---|
| Source | https://github.com/openai/human-eval, file `data/HumanEval.jsonl.gz` (https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz) |
| Paper | Chen et al., *Evaluating Large Language Models Trained on Code*, 2021, https://arxiv.org/abs/2107.03374 |
| License | MIT, Copyright (c) OpenAI; the text is in `LICENSE-human-eval.txt` |
| Retrieved | 2026-10-24, unmodified |
| SHA-256 | `b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef` |
| Size | 43.8 KB, 164 lines |

`tasks.py` reads this file and downloads it from the URL above only if it is missing. To check the copy: `sha256sum HumanEval.jsonl.gz`.

HumanEval has been public since 2021, so models may have seen it in training. Treat pass rates as comparisons between arms on the same model, not as absolute measures of coding ability.
