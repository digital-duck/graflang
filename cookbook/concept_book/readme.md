# concept_book

Build a short concept book on a subject: write an outline, then write and review one chapter per loop iteration, then compile the chapters into a book.

```
wf_entry -> generate_outline -> chapter_loop -> compile_book -> wf_exit
                                 |  per iteration:
                                 |  write_chapter -> review_chapter
                                 |  (chapters are collected into out_chapters)
```

| | |
|---|---|
| Inputs | `subject` (TEXT, required), `target_audience` (TEXT, default `beginners`), `num_chapters` (INTEGER, default 5) |
| Output | `book` (TEXT): the compiled book |
| LLM calls | 2 + 2 x `num_chapters` (outline, compile, and a write plus a review per chapter) |
| Prompts | `prompts/outline.md`, `chapter.md`, `review.md`, `compile.md` |

## Run

From the repo root:

```bash
# no LLM, 2 chapters: checks the loop and the output files
graf run cookbook/concept_book/build_concept_book.graph.yaml --adapter mock \
    --param subject="entropy" --param num_chapters=2

# a real model; start small, 5 chapters is 12 calls
graf run cookbook/concept_book/build_concept_book.graph.yaml --llm claude_cli:claude-haiku-5-5 \
    --param subject="entropy" --param num_chapters=3 --save-nodes
```

## What you get

- **Console:** `generate_outline`, then `chapter_loop`, then the body nodes `write_chapter` and `review_chapter` indented once per iteration, then `compile_book`.
- **Result:** `cookbook/concept_book/output/build_concept_book-<adapter>[-<model>]-<time>/book.md` (also `result.json`).
- **Intermediate text:** with `--save-nodes`, `nodes/` holds the outline, every chapter and every review, numbered in firing order.
- **Log:** `~/.graflang/logs/build_concept_book-<adapter>[-<model>]-<time>.log` and `.jsonl`; `loop.end` records `iterations`.

## Things to check

- The loop ran exactly `num_chapters` times (`loop.end iterations=3`; with `--log-level debug` there is one `loop.iteration` per cycle). Each chapter prompt gets its 0-based index through `in_chapter_index`.
- `book.md` contains all the chapters in order, and `nodes/` has one chapter file per iteration.
- A non-number such as `--param num_chapters=abc` fails at once with `input 'num_chapters' must be INTEGER, got 'abc'`, before any node fires.

## Known limit

`review_chapter` writes an `APPROVED` / `REVISION_NEEDED` verdict, but nothing reads it: no chapter is revised, and the verdict only shows up with `--save-nodes`. It is a place to hang a retry (an `EVALUATE` plus a second pass), not a working gate yet.
