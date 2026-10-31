# concept_book

Build a short concept book on a subject: write an outline, then write, review and (if the reviewer asks) revise one chapter per loop iteration, then compile the final chapters into a book.

```
wf_entry -> generate_outline -> chapter_loop -> compile_book -> wf_exit
                                 |  per iteration:
                                 |  write_chapter -> review_chapter -> needs_revision --[REVISION_NEEDED]--> revise_chapter
                                 |  (the chapter collected is the revision if there was one, else the first draft)
```

| | |
|---|---|
| Inputs | `subject` (TEXT, required), `target_audience` (TEXT, default `beginners`), `num_chapters` (INTEGER, default 5) |
| Output | `book` (TEXT): the compiled book |
| LLM calls | 2 + 2 x `num_chapters` (outline, compile, and a write plus a review per chapter), plus one revision for each chapter the reviewer sends back (at most `num_chapters`) |
| Prompts | `prompts/outline.md`, `chapter.md`, `review.md`, `revise.md`, `compile.md` |

## Chapter numbers

The loop's counter is 0-based, but an outline numbers its chapters from 1. An earlier version of the chapter prompt passed the raw counter ("write chapter 1" for the second chapter), and the second chapter came out as another "Chapter 1: Foundations" (seen in a run on 2026-10-31). A `chapter_number` step (`@in_chapter_index + 1`) now gives the writer the number the outline uses, and the prompt asks for "chapter N of M" under the outline's own heading. In a check run (2 chapters, haiku) chapters 1 and 2 carried the outline's two titles.

## Run

From the repo root:

```bash
# start small: 2 chapters is 6 calls, plus up to 2 revisions, with the default model (claude_cli, claude-sonnet-5-5)
graf run cookbook/concept_book/build_concept_book.graph.yaml \
    --param subject="entropy" --param num_chapters=2

# another model (every node uses it: the graph names none of its own), with a budget of 14 calls
graf run cookbook/concept_book/build_concept_book.graph.yaml --llm claude_cli:claude-haiku-5-5 \
    --bind budget.bind.yaml --param subject="entropy" --param num_chapters=3     # budget.bind.yaml: limits: {max_llm_calls: 14}
```

No node names an `llm:`, so `--llm` decides the model for all of them. To spend differently, add `llm: "adapter:model"` to a node of the loop body: for example a stronger model on `review_chapter` and a cheaper one on `write_chapter`.

## What you get

- **Console:** `generate_outline`, then `chapter_loop`, then the body nodes `write_chapter`, `review_chapter`, `needs_revision` and, when the reviewer sends a chapter back, `revise_chapter`, indented once per iteration, then `compile_book`.
- **Result:** `cookbook/concept_book/output/build_concept_book-<adapter>[-<model>]-<time>/book.md` (also `result.json`).
- **Intermediate text:** `nodes/` holds the outline, every first draft (`write_chapter`), every verdict (`review_chapter.out_verdict`), every revision (`revise_chapter`), the chapters the compile step received (`chapter_loop.out_chapters.json`) and the book, numbered in firing order.
- **Log:** `~/.graflang/logs/build_concept_book-<adapter>[-<model>]-<time>.log` and `.jsonl`; `loop.end` records `iterations`.

## Things to check

- The loop ran exactly `num_chapters` times (`loop.end iterations=3`; with `--log-level debug` there is one `loop.iteration` per cycle). Each chapter prompt gets its 0-based index through `in_chapter_index`.
- `book.md` contains all the chapters in order, and `nodes/` has one draft file per iteration.
- A chapter with a `REVISION_NEEDED` verdict has a `revise_chapter` file after its verdict, and the book holds the revised text; a chapter that was approved has none, and the book holds the draft.
- A non-number such as `--param num_chapters=abc` fails at once with `input 'num_chapters' must be INTEGER, got 'abc'`, before any node fires.

## Revision

The reviewer replies `APPROVED`, or `REVISION_NEEDED` followed by the changes it wants. The `needs_revision` step reads that reply (any case, any formatting around the word) and sends only the chapters that need it to `revise_chapter`, which rewrites the whole chapter from the draft, the feedback, the subject and the outline. In each iteration the loop collects whichever of `write_chapter` and `revise_chapter` wrote last, so `compile_book` receives the final chapters. (That needs a list in `collect`: `chapters: {collect: ["write_chapter.out_chapter", "revise_chapter.out_chapter"]}`.)

One real run on `claude-haiku-5-5` (subject `entropy`, 3 chapters, 11 calls): the reviewer sent back all three chapters with specific factual points (a wrong worked example, a sign error), all three were revised, and the book came to 5,746 words. An earlier run without the revision step took 8 calls and gave 3,687 words. A single run is an anecdote: it shows the wiring works, not how often a revision improves a chapter.

## Known limits

- **One revision per chapter, not re-reviewed.** A revised chapter goes straight into the book. A second review pass (loop until `APPROVED`, bounded by a maximum) would add calls per chapter and is not built.
- **The reviewer decides.** A small model can approve a weak chapter or ask for changes to a good one. Putting a stronger model on `review_chapter` is the cheapest lever.
- **The compile step re-types the whole book.** `compile_book` receives every chapter and writes the book out in full, so it is the largest call of the run (about 34,000 characters of reply in the haiku run), and a model that cuts it short cuts the book. A deterministic concatenation would be exact and free; the graph has no step for it yet.
