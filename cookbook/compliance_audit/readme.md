# compliance_audit: PII audit with deterministic rules

An LLM reads a document and lists the **types** of personal data it contains (never the values). **Boolean rules** then decide, without an LLM, whether the document may go to a destination. If it may not, the document is redacted, the redacted text is read again and the rules are re-checked. A Cedar policy has the last word before anything is released; whatever cannot be shown compliant ends at `escalated`.

```
extract_pii (LLM) -> check (rules) -> compliant? -- yes --> release_guard (Cedar) -> released
                                          | no
                                  redact (LLM) -> extract_again (LLM) -> recheck -> compliant? -- no --> escalated
                                                                                       | yes -> release_guard
```

It is an illustration of the pattern, not legal advice. The default rules are not a real GDPR or PCI rule set.

## Run

```bash
pip install -e /path/to/SPL.py            # the rule check is an SPL.py procedure
graf run cookbook/compliance_audit/compliance_audit.graph.yaml \
    --adapter claude_cli --model <id> \
    --param document="Customer John Doe, SSN 123-45-6789, asks to update his address." \
    --param destination=external_api --param engine=stdlib --param rules_file=
```

`engine` is `stdlib` (no dependency, the default), `sympy` or `z3`. All three give the same verdicts; see recipe 127 in SPL.py for the measurements. A real run with `claude_cli` on the example above redacted the SSN, re-read the result, passed the rules and was released by the Cedar guard. `tests/test_compliance_audit.py` covers every path with a stub model, so it needs no LLM.

## Your own rules

`procedures/rules.json` holds the demo rules (R1 masking for external destinations, R2 an SSN never leaves externally, R3 card numbers always masked). Copy it, edit it, and pass `--param rules_file=my_rules.json`. Check a file with `python procedures/tools.py my_rules.json`. A missing or invalid file stops the run; the defaults are never substituted silently.

## Where things are

| File | Role |
|---|---|
| `compliance_audit.graph.yaml` | the workflow |
| `prompts/extract_pii.md`, `prompts/redact.md` | the two LLM prompts |
| `procedures/compliance_check.spl`, `procedures/tools.py`, `procedures/rules.json` | the deterministic check (copied from SPL.py recipe `cookbook-solver/127_pii_compliance`; GraphLang loads `tools.py` next to the procedure) |
| `policies/release_policy.cedar` | permit only a compliant release; anything else is denied |

The procedure files are a copy; when you change one, change it in both places.
