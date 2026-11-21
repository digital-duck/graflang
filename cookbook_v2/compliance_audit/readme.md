# compliance_audit

Finds the personal data in a document, checks it against deterministic rules for the destination, redacts and re-checks once if the check fails, and lets a Cedar policy decide
the release. The model only *finds* personal data; the rules are plain programs, so the verdict is repeatable.

```
compliance_audit  load -> assess -> compliant? -> (remediate) -> ask the policy -> release | escalate
  assess/         extract the personal-data map (model) -> check it against the rules (program)     used twice: before and after redaction
  remediate/      redact (model), then assess again                                                   exit unfixed (E_STILL_NONCOMPLIANT)
```

Inputs: `document` (text or a file path), `destination` (e.g. `external_api`), `engine` (`stdlib` default, `sympy`, `z3`), `rules_file` (default: built in).
Outputs: `safe_document`, `audit`. Model calls: 1 when the document passes, 3 when it needs redaction (extract, redact, extract again).

```bash
graf run cookbook_v2/compliance_audit/compliance_audit.graph.yaml --bind cookbook_v2/cap.bind.yaml --llm claude_cli:claude-sonnet-5-5 \
    --param document="./input/customer_case_file.txt" --param destination=external_api
```

`input/` has sample documents (`hard_case_file.txt` is the difficult one). `procedures/` holds the checks (`compliance_check.py`, `tools.py`, `rules.json`,
`rules_extended.json`); a command runs from this folder, so they stay beside the top graph. The `z3` engine needs the `graf` conda env. Policy: `policies/release_policy.cedar`.
The long write-up of the engines and experiments is in `cookbook/compliance_audit/readme.md` (the original, left as is).
