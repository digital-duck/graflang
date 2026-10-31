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
# no extra install: the rule check is a plain Python program (no SPL.py, no kernel); sympy or z3 only if you pick those engines
graf run cookbook/compliance_audit/compliance_audit.graph.yaml \
    --param document="Customer John Doe, SSN 123-45-6789, asks to update his address." \
    --param destination=external_api \
    --param rules_file="./procedures/rules.json"
```

The same audit with the other two rule engines. They need their package (`pip install sympy`, `pip install z3-solver`) in the Python that runs the rule check, which is the `python3` on your `PATH`:

```bash
# (1) sympy: the rules as symbolic Boolean expressions
graf run cookbook/compliance_audit/compliance_audit.graph.yaml \
    --param document="Customer John Doe, SSN 123-45-6789, asks to update his address." \
    --param destination=external_api \
    --param engine=sympy \
    --param rules_file="./procedures/rules.json"

# (2) z3: an SMT solver; besides the violated rules it reports an unsat core, a set of rules that cannot hold together
graf run cookbook/compliance_audit/compliance_audit.graph.yaml \
    --param document="Customer John Doe, SSN 123-45-6789, asks to update his address." \
    --param destination=external_api \
    --param engine=z3 \
    --param rules_file="./procedures/rules.json"
```

Without the package the run stops at the rule check with an error that names it (for z3: `z3 engine needs z3-solver: pip install z3-solver`); it does not fall back to another engine. On the same facts (an unmasked SSN going to `external_api`) all three engines return `compliant: false, violated: [R1, R2]`; z3 also returns `core: [R1]`. That is the program's verdict on a fixed pii map, checked directly; I have not compared full LLM runs across engines.

`rules_file` here names the demo rules explicitly (`procedures/rules.json`); a relative path starts in the recipe's folder, not where you ran `graf run`, so this works from the repo root. `engine` is left out, so it is `stdlib`. Both are optional: leave `rules_file` out (or empty) and the demo rules are used, and add `--param engine=sympy` to pick another engine.

`engine` is `stdlib` (no dependency, the default), `sympy` or `z3`. All three give the same verdicts; see recipe 127 in SPL.py for the measurements (made with the SPL version of the check). A real run with `claude_cli` on the example above redacted the SSN, re-read the result, passed the rules and was released by the Cedar guard. `tests/test_compliance_audit.py` covers every path with a stub model, so it needs no LLM.

## Your own rules

`procedures/rules.json` holds the demo rules (R1 masking for external destinations, R2 an SSN never leaves externally, R3 card numbers always masked). Copy it, edit it, and pass `--param rules_file=my_rules.json`. Check a file with `python procedures/tools.py my_rules.json`. A missing or invalid file stops the run; the defaults are never substituted silently.

## Where things are

| File | Role |
|---|---|
| `compliance_audit.graph.yaml` | the workflow |
| `prompts/extract_pii.md`, `prompts/redact.md` | the two LLM prompts |
| `procedures/compliance_check.py` | the deterministic check as a program: JSON in on stdin, the verdict as one JSON line on stdout, exit 1 when it cannot run. The two `SOLVE` nodes (`check`, `recheck`) run it with `backend: subprocess` |
| `procedures/tools.py`, `procedures/rules.json` | the rule engines (stdlib, sympy, z3) and the demo rules, plain Python |
| `policies/release_policy.cedar` | permit only a compliant release; anything else is denied |

The check started as SPL.py's recipe `cookbook-solver/127_pii_compliance` and is now independent of it: plain Python, no SPL.py. (The folder is still called `procedures/`.) Each firing starts a Python process, about 20 ms for `stdlib` and 165 ms for `sympy` on one machine; the interpreter on your PATH (`python3`) must be the one that has sympy or z3 if you choose those engines.
