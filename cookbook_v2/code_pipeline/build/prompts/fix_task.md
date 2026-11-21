You are an expert {{in_lang}} developer. The project below was just checked by running it, and the check failed.

THE TASK that was being built:
{{in_task}}

The whole project now:
{{in_project}}

The check (syntax, imports, the project's own tests) found:
{{in_report}}

Reference material (empty if there is none):
{{in_reference}}

Fix the failure with the smallest change. Reply with the files you change, whole (a file you do not mention stays as it is). Start every file with a line
`=== FILE: path/to/file ===` and then its complete content. If a test is wrong, fix the test; if the code is wrong, fix the code. Use only the standard library
and pytest, click, streamlit, networkx, pyyaml, jinja2, markdown, requests, rich, flask, fastapi, httpx, pydantic, numpy, pandas. No code fences, nothing outside the files.
