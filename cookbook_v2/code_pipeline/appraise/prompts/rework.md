You are an expert {{in_lang}} developer. A finished project was run on a small demo and a reviewer found defects in what it produced.

The specification:
{{in_spec}}

The build plan (deliverables with their quality bars, and the demo):
{{in_plan}}

The whole project now:
{{in_project}}

What the demo produced:
{{in_demo}}

The reviewer's defects (fix every one):
{{in_defects}}

Reference material (empty if there is none):
{{in_reference}}

Fix the defects with the changes that matter. Where content must be written with intelligence (explanations, summaries, narrative), the product calls a model through its injectable
interface and gives it the extracted facts and a clear instruction; it does not enumerate names and docstrings itself. Keep the offline stand-in the demo uses, and keep the demo working.
Update or add tests so that they check substance (they must fail on a listing, not only check that headings exist).

Reply with the files you change or add, whole (a file you do not mention stays as it is). Start every file with a line `=== FILE: path/to/file ===` and then its complete content.
Use only the standard library and pytest, click, streamlit, networkx, pyyaml, jinja2, markdown, requests, rich, flask, fastapi, httpx, pydantic, numpy, pandas; import a model provider's SDK
lazily, inside the function that calls it. No code fences, nothing outside the files.
