# your_book

Writes a short book on a subject: an outline, then the chapters one at a time (each written, reviewed, and revised if the review asks), then one pass that compiles them.

```
your_book       outline -> chapters -> compile
  outline/      the chapter plan (one model call)
  chapters/     the loop, one chapter per round: write -> review -> revise if needed
  compile/      one call joins the chapters into the book
```

Inputs: `subject`, `audience` (default `intro`), `style`, `num_chapters` (default 5). Output: `book`. Model calls: 1 outline + 2 to 3 per chapter + 1 compile, so about
`3 * num_chapters + 2` at most. A small first try:

```bash
graf run cookbook_v2/your_book/your_book.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-haiku-5-5 \
    --param subject="entropy" --param num_chapters=2
```

Set `max_llm_calls` in the bind file from the formula before a bigger book. In the editor's Run tab the cap is the "Most model calls" box (a bind file is not read there): 5 chapters need about 17. Original: `cookbook/your_book`, whose readme explains the loop state.
