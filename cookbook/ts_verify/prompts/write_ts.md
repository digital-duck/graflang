You write TypeScript. Implement one function from the specification below.

Specification:
{{in_spec}}

Requirements:
- Export a function named `{{in_function}}`: `export function {{in_function}}(...)`.
- Give every parameter and the return value an explicit type. The code is checked with `tsc --strict`.
- Pure code only: no imports, no `console`, no file or network access. Use only the language itself.
- Use only syntax Node can run by erasing types: no `enum`, no `namespace`, no constructor parameter properties.
- Reply with the code only, in one code block.

If the sections below are empty, this is your first attempt. Otherwise your previous attempt failed: fix exactly what the reports say and keep the function name and signature.

Previous attempt:
{{in_prior_code}}

Type errors from the compiler (JSON):
{{in_type_report}}

Failed test cases (JSON):
{{in_case_report}}
