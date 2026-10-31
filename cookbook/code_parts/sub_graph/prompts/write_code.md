You are an expert {{in_lang}} developer.

Write clean, correct, well-structured {{in_lang}} code for the following specification.
Return only the code — no explanation, no markdown fences.

Specification:
{{in_spec}}

Previous attempt (empty on the first attempt):
{{in_prior_code}}

Its test result (empty on the first attempt):
{{in_prior_test}}

If there is a previous attempt, fix the failures its test result reports. Whatever you write, keep the function name and
the signature exactly as the specification gives them.

Lay the code out as a small project folder, not one block of text. Start every file with a line `=== FILE: path/to/file ===` (a path
relative to the project folder), then the file's content. Give a README.md first (what the project is and how to run it), then the
source files. Split the code into modules when the specification has more than one concern, and let the modules import each other
(for example `slugger/core.py` imported as `from slugger.core import slugify`); a small specification may be a single module.
Do not use code fences and write nothing outside the files.

Reference material (APIs and facts about libraries that the specification relies on; follow it exactly, and never guess a library's
API when it is given here; empty if there is none):
{{in_reference}}
