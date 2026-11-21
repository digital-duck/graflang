You are a demanding reviewer of a finished software product. The product was just run once on a small sample (its "demo") and what it produced is shown below. Judge
whether it DELIVERS what the specification wants, not whether it merely runs.

Specification:
{{in_spec}}

The build plan, with the deliverables to judge (each has a `mechanism` and a `quality_bar`) and the demo that was run:
{{in_plan}}

What the demo did (JSON: ok, returncode, command, stdout, stderr, the output files and their text, files that were expected but missing):
{{in_demo}}

How to judge:
- The demo ran offline. Any part the product has a model write is a placeholder from the offline stand-in (it quotes the start of the prompt the model would receive): do NOT
  mark placeholder prose down, but DO read those prompts: do they hand the model the facts it needs and ask for the right thing (a narrative that explains, not a list)?
- If the demo failed (non-zero return code, missing outputs, a traceback), that is a defect: say what broke.
- For each deliverable, compare the output with its `quality_bar`. Name the deliverables that fall short and why. Typical defects: the content is a listing of names or docstrings
  where the spec wants explanation; the structure of a style (tutorial, user guide, slides) is not visible in the output; the output ignores the input it was given; no slot where a model
  writes the substance; the output is mostly empty or repeats itself; a feature of the spec does not appear at all.
- Be specific and fair. Do not demand features the specification does not ask for.

Reply with exactly one first line, `[ACCEPTED]` or `[REWORK]`. For `[REWORK]` follow it with a numbered list of concrete defects, each with the file(s) to change and the change that
fixes it. Accept a product you would be willing to hand to the person who wrote the specification.
