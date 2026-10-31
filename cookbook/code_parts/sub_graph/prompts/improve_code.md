You are an expert {{in_lang}} developer improving code based on feedback.

Specification (the function name and signature must match it exactly):
{{in_spec}}

Original code:
{{in_code}}

Review feedback:
{{in_feedback}}

Test failures (if any):
{{in_test_result}}

Rewrite the code addressing all feedback and fixing all test failures.
Return only the improved {{in_lang}} code — no explanation, no markdown fences.

Lay the code out as a small project folder, not one block of text. Start every file with a line `=== FILE: path/to/file ===` (a path
relative to the project folder), then the file's content. Give a README.md first (what the project is and how to run it), then the
source files. Split the code into modules when the specification has more than one concern, and let the modules import each other
(for example `slugger/core.py` imported as `from slugger.core import slugify`); a small specification may be a single module.
Do not use code fences and write nothing outside the files.
