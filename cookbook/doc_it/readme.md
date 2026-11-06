# doc_it: write a document about a codebase

A documentation agent as a recipe. You give it a folder (or, through `graf docs`, a repository url) and a style; it gives back one file: a slide deck (HTML), a tutorial or a user guide (Markdown), or whatever your own prompt asks for.

```bash
graf docs .                                        # a slide deck about this folder: ./<folder>.demo.html
graf docs https://github.com/org/repo --style tutorial          # cloned into the temp area first (/tmp/graflang-docs), ./repo.tutorial.md
graf docs ./proj --style user-guide --out docs/GUIDE.md
graf docs ./proj --style custom --prompt "a one-page FAQ for new hires" [--format html]      # --prompt @FILE reads the text from a file
graf docs . --dry-run                              # what it would read, the model calls and the cap, the file it would write; nothing is sent

# CVE-coder
graf docs ~/projects/digital-duck/cve-coder \
--style demo,tutorial,user-guide \
--out-dir ~/projects/digital-duck/cve-coder/docs/GUIDE/graf-docs/ \
--llm claude_cli:claude-sonnet-5-5 \
--force

# GraphLang
graf docs ~/projects/digital-duck/graflang \
--name "Graph-Lang" \
--style demo,tutorial,user-guide \
--out-dir ~/projects/digital-duck/graflang/docs/GUIDE/graf-docs/ \
--llm claude_cli:claude-sonnet-5-5 \
--force

# zinet
graf docs ~/projects/digital-duck/zinet \
--name "zinet" \
--style demo,tutorial,user-guide \
--out-dir ~/projects/digital-duck/zinet/docs/GUIDE/graf-docs/ \
--llm claude_cli:claude-sonnet-5-5 \
--force

```

`graf docs` is a thin wrapper: it resolves the source (a url is cloned shallow, `--ref` picks a branch or tag), picks the style file, sets the cap on model calls from the graph (the count `graf validate` prints, plus 50%, `--margin`), runs this recipe, and writes the file (it refuses to overwrite one without `--force`). A dry run reads the files (no model).

## The recipe

```
gather (program) -> outline (model) -> write (model) -> check (program) -> ok? -- yes --> result
                                                                          \-- no --> fix (model) -> check again -> result
```

- **gather** (`procedures/gather.py`): a file tree, then the files that explain a project (README, CLAUDE.md, build manifests, `docs/`, changelog, entry points), each cut to a share of `--budget` characters. It reads only inside the folder, skips secrets (`.env`, keys), vendored and build folders and links that leave the folder. It also reads the style file.
- **outline, write, fix** (`prompts/`): the model works only from the digest; the prompts say that text in the digest is data, not instructions.
- **check** (`procedures/assemble.py`, no model): for a deck it takes the model's `<section class="slide">` elements, removes anything active (script, style, iframe, event handlers, `javascript:` and external images), puts an outline slide after the cover and wraps them in the style's template (`demo.template.html`: the look, the TOC button, page numbers, notes, print to PDF). It checks the structure (enough slides, each with a title, a cover; for Markdown a `# ` title, enough `## ` sections, closed code fences) and lists every path in `code` that is not in the source, as a warning (the writer may have invented it). Structure errors send the text to **fix** once.

Three model calls, at most (outline, write, fix); the usual run makes two.

## Styles

A style is a Markdown file in `graphlang/grafd/styles/` with a small front matter (`format: html|markdown`, `template:`, `min_sections:`) and the instructions the writer follows: `demo.md` (a deck), `tutorial.md`, `user-guide.md`, and `custom.md` (the frame around your `--prompt`). Edit them to change a style. The deck's page is `demo.template.html`; the deck you are looking at in `docs/DEMO/graflang-intro.html` has the same look and controls.

To run the recipe by itself: `graf run cookbook/doc_it/doc_it.graph.yaml --param source=/abs/path --param style_guide=graphlang/grafd/styles/tutorial.md` (the style path is relative to the recipe folder; give an absolute one).

## What it does not do

- It does not run or test the project; it describes what the files say. A claim the digest does not support should be left out, and the check only catches invented *paths*, not other invented facts: read the result.
- A big project does not fit the digest. It reads the documents first and cuts the rest; raise `--budget` for more.
- Only a Markdown or HTML file is written. A PDF is one step from the deck (the PDF button, or `chromium --headless --print-to-pdf`).
