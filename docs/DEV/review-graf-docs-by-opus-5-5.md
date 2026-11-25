# `graf docs`: review against a hand-made documentation set (Opus 5.5, 2026-11-25)

The question: does `graf docs` (`graphlang/grafd/`, `cookbook/doc_it/`) reproduce, in its prompting, what I did by hand when I wrote
book-graph's documentation set: `docs/GUIDE/Setup.md`, `Tutorial.md`, `User-Guide.md` and `docs/DEMO/book-graph-v1.demo.html`?

## 1. What I did, and what `graf docs` did

| Step of the hand-made set | `graf docs` before this review |
|---|---|
| Read every command's `--help`, so the commands, options and defaults are the code's | `cli.py` cut to its first 3,500 characters: **2 of book-graph's 19 commands** reached the model |
| Took the verified numbers from `docs/DEV/review-by-opus-5-5.md` | that file arrived at **4%** (3,583 of 88,707 characters); every doc capped at 3,500 characters while 18k of the 60k budget went unused |
| Read the sibling apps' guides first and followed their structure, section names and tone | no way to give it an example |
| Ran every tutorial command in a scratch library and quoted the **real** output | it runs nothing (rightly); the tutorial style shows output "only if the sources show it", but had no way to receive output |
| Wrote the four documents as a linked set | each style ran alone, unaware of the others; **no setup style** |
| Named them as the family does: `docs/GUIDE/Setup.md`, `docs/DEMO/<name>-v1.demo.html` | `<name>.<style>.html` |
| Said what was not verified (the mock model, no live `extract`) | not asked for |
| Rendered the deck in Chromium and fixed a clipped code line | only structural checks; a clipped `<pre>` passed |
| Reused the family's deck frame | **already aligned**: `demo.template.html`'s CSS and script are identical to work-graph's deck |

## 2. Changes

- **`gather.py`:**
  - **CLI surface:** the code's own declarations of commands, arguments and options (click, typer, argparse), with defaults, help and
    the first docstring line, as a `=== CLI SURFACE path ===` section of up to 30% of the budget. On book-graph, **all 19 commands**
    now reach the model.
  - **Docs share what is left of the budget** instead of a fixed 3,500 characters (book-graph: 69k characters of digest, up from 42k).
  - **Labelled extras from outside the folder:** `HOUSE STYLE EXAMPLE` (match its shape and tone; never a source of facts),
    `TRANSCRIPT` (real command output) and `DOCUMENT SET`. Files are read only when they are regular text under 400 KB with no
    secret-looking name, and an HTML example loses its styles and scripts.
  - **It reports** per-file `coverage` and the CLI `surfaces`.
- **The prompts** (`outline.md`, `write.md`, `fix.md`) explain the labelled sections:
  - the CLI surface is the ground truth: follow the code when a doc disagrees;
  - examples give shape only;
  - shown output comes only from a transcript or a file;
  - link the other documents of the set.
- **The styles:**
  - **all:** the CLI surface is authoritative; quote measured figures exactly, with what they measured; say what was not tested or
    run; follow a house-style example; link the document set;
  - **`setup` (new):** prerequisites as a table with check commands, getting the code in dependency order, install, verify,
    configuration by environment-variable name, where things are written, troubleshooting;
  - **`tutorial`:** a scratch area so the reader's real data is untouched; the cheapest offline option first, saying what changes
    with the real one; say which outputs are real;
  - **`user-guide`:** every command in the reference; every configuration key and environment variable;
  - **`demo`:** a measured-results slide, a demo-commands slide and a status slide; fit limits that match the template.
- **`assemble.py`** checks the **fit** of a deck: a code line wider than its box, or a block over 20 lines, is an error, so it goes to
  the fix step. The limits were measured in Chromium per layout: 114 characters full width, 53 in a column, 47 or 60 in the narrow or
  wide column of `cols wide-*`. More than 8 bullets on a slide is a warning. Calibrated on book-graph's deck: the deck as shipped
  passes, and the one line that really clipped (54 characters where 53 fit) is caught.
- **`demo.template.html`: the text now scales with the slide.** The font was a fixed 26 px while the slide scales with the window,
  so what fitted depended on the screen:

  | Viewport | Code characters in a column |
  |---|---:|
  | 1280×720 | 43 |
  | 1600×900 | 55 |
  | 1920×1080 | 67 |

  No fixed limit could be right. It is now `font: calc(min(96vw, 158vh) / 54.7)`, exactly 26 px at 1600×900, so the capacity is the
  same on every screen (verified at 1024×768, 1280×720, 1600×900 and 1920×1080). Print keeps its fixed 24 px page. **The same issue
  exists in the hand-written decks** (app-graph, work-graph, data-graph, and book-graph's before I fixed it): a deck checked at
  1600×900 clips on a 1280×720 projector.
- **The CLI:**
  - the `setup` style;
  - `--like FILE` and `--transcript FILE`, both repeatable;
  - `--layout guide`, which writes `GUIDE/Setup.md`, `GUIDE/Tutorial.md` and `GUIDE/User-Guide.md` (Markdown) and
    `DEMO/<name>-v1.demo.html` under `--out-dir` (default `docs`);
  - several styles in one run each get the others as their `DOCUMENT SET`, with relative links;
  - the dry run prints the extras, the links, the CLI surface and each file's coverage.

## 3. Verified

- `tests/test_doc_it.py`: **33 passed**. The 27 existing tests pass unchanged, and 6 are new:
  - the CLI surface, whole (19 commands with options, defaults and docstrings) even when the entry file is cut;
  - docs sharing the budget;
  - extras, with an HTML example's script and style removed and a secret-looking file skipped;
  - the fit check in a plain column, at full width, and in the narrow column of `wide-left`;
  - the scaling template;
  - the setup style, the guide layout, the links and the coverage in a dry run.
- `tests/test_cookbook_core_v2.py`: 28 passed. `graf validate cookbook/doc_it/doc_it.graph.yaml` passes (3 model calls).
- A dry run on book-graph with `--style setup,tutorial,user-guide,demo --layout guide --like …/work-graph/docs/GUIDE/Tutorial.md
  --transcript …` plans the four family file names, the links between them, the example, the transcript, and the CLI surface.

## 4. Not done, or out of reach

- **No real model run.** The prompts changed and no live run was made (it costs about 3 calls per style). Run it once on
  book-graph and compare with the hand-made set.
- **Running commands is still the user's job.** `graf docs` does not, and should not, execute a project's code, since the source may be
  an untrusted repository. A tutorial with real output needs `--transcript`.
- **Large documents still do not fit.** A file larger than the budget (book-graph's 88k-character review) is still mostly cut. The dry
  run now shows how much of each file is taken; raise `--budget` when an important file is mostly cut.
- **Label spoofing.** The labelled sections are plain text, so a project file that contains `=== TRANSCRIPT ===` could pose as one.
  The prompts still treat the whole digest as data, never as instructions, so the effect is limited to what may be quoted.
- **Rendering is approximated.** The fit check is a character count calibrated on the template. A slide's *vertical* overflow from
  long prose is only approximated by the bullet warning; rendering in a browser would be exact, but needs Chromium.
