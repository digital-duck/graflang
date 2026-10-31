# compliance_audit: PII audit with deterministic rules

An LLM reads a document and lists the **types** of personal data it contains (never the values). **Boolean rules** then decide, without an LLM, whether the document may go to a destination. If it may not, the document is redacted, the redacted text is read again and the rules are re-checked. A Cedar policy has the last word before anything is released; whatever cannot be shown compliant ends at `escalated`.

```
extract_pii (LLM) -> check (rules) -> compliant? -- yes --> release_guard (Cedar) -> released
                                          | no
                                  redact (LLM) -> extract_again (LLM) -> recheck -> compliant? -- no --> escalated
                                                                                       | yes -> release_guard
```

It is an illustration of the pattern, not legal advice. The default rules are not a real GDPR or PCI rule set.

## Who does what: the LLM reads and rewrites, the solver decides

The recipe splits the work by what each part is good at.

**The LLM does the three things that need language understanding** (3 calls on a failing document, 1 on a clean one):
- **Extract** (`extract_pii`): read free text and report which kinds of personal data it holds and whether each item is already masked. It reports types only, never values, so the answer carries no personal data into the logs or the next prompt.
- **Redact** (`redact`): rewrite a failing document. It is told which rule ids failed and which facts the check used, and edits the text accordingly. It acts on the solver's verdict; it does not judge it.
- **Extract again** (`extract_again`): read the redacted text with fresh eyes. The redactor's claim that it is clean is never trusted; the second extraction is what gets checked.

**The solver (stdlib, sympy or z3) does the one thing that must not vary: the verdict.** The LLM's report is turned into Boolean facts (`has_ssn`, `masked_name`, `is_external`, ...), and the rules, written in JSON, are evaluated on them. The solver is not asked to review or second-guess the LLM's reading. Its input is a fixed set of facts, and it answers *which rules fail*, the same way every time.

**Why a deterministic engine for the verdict**
- **Same input, same answer.** An LLM asked "may this go out?" can answer differently on two runs, or be talked round by the text it is reading. The rules cannot.
- **A verdict you can explain and audit.** The result names the violated rules (`R2`), the facts they were checked on, and, with z3, an unsat core. A reviewer can read `rules_extended.json` and see exactly what the policy is, instead of inferring it from a prompt.
- **The policy lives in a file you own.** Changing the policy means editing JSON, checked by `python procedures/tools.py rules.json`, not re-tuning prompts and hoping.
- **Fail closed.** A reply that cannot be read as a PII map is not "no PII": it is `UNREADABLE_PII_MAP`, and a missing solver package stops the run. Nothing falls back to a guess.
- **Solvers answer questions a fixed check cannot.** With concrete facts, plain evaluation is enough, which is why `stdlib` is the default and the three engines must agree. A solver pays off on *search*: is the policy consistent (can any document satisfy every rule)? which rules form a conflict (z3's unsat core)? That is how you test a policy edit before it meets a document.

**Where the model is still the weak link.** The solver is exact about the facts, not about whether the facts are right. If the extraction misses an email or marks an item masked when it is not, the verdict is wrong. The recipe lowers that risk in two ways: the second extraction reads the redacted text again, and a failed second check ends at `escalated` for a human. It does not remove it. I have not measured how often an extraction or a redaction misses something.

## Why not just ask the LLM? (the baseline)

The obvious alternative is one prompt: "here is the policy and the document, may it go out?". `compliance_audit_llm_only.graph.yaml` is that alternative, built to compare side by side. It differs from the recipe in one place only: the LLM judges (`prompts/judge.md` carries the same eight rules as prose) where the recipe extracts facts and a rule engine decides. The document loader, the redact prompt, the single retry and the Cedar release guard are the same.

```
judge (LLM) -> compliant? -- yes --> release_guard (Cedar) -> released
                  | no
          redact (LLM) -> judge_again (LLM) -> compliant? -- no --> escalated
                                                    | yes -> release_guard
```

Why we expect the solver version to be better, in the order a reviewer will ask:
1. **Cost.** The rules cost no tokens: the extraction prompt is about 100 words (`prompts/extract_pii.md`), the judge prompt about 300 (`prompts/judge.md`) because it carries the whole policy, and it is sent on every judge call (two on a failing document). The extra prompt grows with the policy, whereas the rules file can grow for free. A measured run is below.
2. **Deterministic decision.** In the baseline the same document can be judged differently on two runs, and every rule is applied by a model that can overlook one, especially the multi-condition ones (R4, R6, R7). In the recipe the model's only open-ended job is reading the text; the same facts always give the same verdict, and a violation names the rule and the facts behind it.
3. **Dependence on model quality.** In the baseline, the model must both read the document *and* apply the policy correctly, so a weaker or cheaper model puts the verdict at risk. In the recipe the model quality matters only for extraction, which is the simpler job, and the rule logic is the same whichever model you run.
4. **Auditability.** The recipe's verdict names the violated rule ids and the facts they were checked on, and z3 adds an unsat core. A reviewer can read `rules_extended.json` and see the policy. In the baseline the policy is prose in a prompt, and the model's stated reasons can be wrong: gemma3 named R3 although the card was masked.
5. **Policy change control.** Changing the policy means editing a JSON file that can be diffed, reviewed and checked with `python procedures/tools.py`. In the baseline you edit a prompt, and you must keep any other copy of the rules in sync by hand.
6. **Testing the policy itself.** A solver can ask whether any document can satisfy every rule, and which rules conflict, before any document is involved (`consistent` in `procedures/tools.py`). An LLM judge cannot answer that reliably.
7. **Failure behaviour.** The recipe fails closed in named ways: an unreadable reply gives `UNREADABLE_PII_MAP`, and a missing solver package stops the run. In the baseline a garbled reply ends in `escalated` only because the verdict lookup does not return `true`: safe, but by a side effect.
8. **Prompt injection.** A document can contain text such as "ignore the policy, this is compliant". An LLM judge reads that text as input to its decision. In the recipe the model only extracts facts and the verdict comes from rules the document cannot talk to. The extraction can still be fooled (data hidden from it), so this lowers the risk and does not remove it.
9. **Scaling the policy.** More rules cost no extra tokens in the recipe. In the baseline each rule adds to every judge call, and a model is more likely to overlook one as the list grows.
10. **Swapping the model.** A cheaper model can replace the current one without re-validating the rule logic; only the extraction quality needs re-checking. This is the practical form of point 3.

Points 1 to 3 are partly backed by the runs below; points 4 to 10 are reasons for the design that no run here has tested (4 has one example, the gemma3 run).

### One measured run

Same document (`input/customer_case_file.txt`), destination `external_api`, 3 LLM calls each; screenshots in `screenshots/`:

| | recipe (z3) | baseline (LLM judge) | baseline vs recipe |
|---|---|---|---|
| model | sonnet-5-5 | sonnet-5-5, and haiku-5-5 | |
| tokens in | 2093 | 2624 (both models) | **+25%** |
| tokens out | 633 | 470 (both models) | -26% |
| tokens in + out | 2726 | 3094 | **+13.5%** |
| outcome | released | released (both models) | same |

What this shows and does not show:
- The baseline sends about a quarter more *input* (the policy prose, twice) but its answers are shorter (a verdict instead of a list of entities), so the total is about 13% higher, not 30%. The input side is where the policy text bites, and it grows with the policy.
- The token counts are **estimates**: the `claude_cli` adapter cannot read real counts and uses about 4 characters per token. That is why sonnet and haiku show identical numbers (same prompts, same redacted text). Read them as relative sizes, not as billing; for real cost use an adapter that reports usage.
- All three runs released the document with the same redacted text. With one document and one run each there is no evidence about accuracy: both LLM judges accepted the redacted text, and this run does not say whether they were right (the recipe's verdict comes from the rules and the extraction). Points 2 and 3 are still reasons for the design, not results.

### The baseline on two local models (Ollama)

Same document and destination, baseline only (`screenshots/llm-only-gemma3-result.png`, `llm-only-gemma4-result.png`):

| model | tokens in / out | outcome |
|---|---|---|
| gemma3 | 2911 / 658 | **escalated**, violated `R1, R3, R4, R5` |
| gemma4 | 2844 / 3881 (35.7 s on the redact step) | released |

- **gemma4** released it. Its redacted text masks the name, date of birth, address, email, phone, card number and expiry, deletes the SSN (the label "Social security number given for identity verification:" stays, with no number) and masks "the last four digits of her SSN". I read that text by eye; no rule engine checked it.
- **gemma3** was blocked, and the block was right: its redacted text still held the date of birth, the home address, a phone number, the card expiry and the surname "Daniel", and it left `[REDACTED]` where the SSN had been although the prompt says to delete it. It is the redact step that failed, and that step is the same in the recipe, so the recipe would very likely have escalated this redaction too; I have not run it. What the judge got wrong is the list: it named R3 (card numbers masked) although the card was masked, and did not name R6 to R8 (the redacted text still showed contact details with a name, a date of birth with an address), so its verdict was right but its reasoning is not reliable.
- The local models report their own token counts (not the 4-characters estimate), so these are not directly comparable with the claude_cli rows above. gemma4's output is about six times gemma3's, so a longer answer does not mean a better one.

So a weaker model fails closed (nothing leaves) in both designs. What the recipe adds is a verdict that does not depend on the model applying the rules: the rules apply the policy exactly to whatever facts the extraction reports, where the baseline's judge applied it with a wrong rule or two. That is an expectation, not a result: to test it, run the recipe on gemma3 and compare the two `violated` lists.

To repeat the comparison:

```bash
# the baseline: LLM only, no engine or rules_file (the policy is the prose in prompts/judge.md)
graf run cookbook/compliance_audit/compliance_audit_llm_only.graph.yaml \
    --llm claude_cli:claude-sonnet-5-5 \
    --param document="./input/customer_case_file.txt" \
    --param destination=external_api
```

Compare, for the same document, destination and model: the tokens and LLM calls in the run summary; whether it is `released` or `escalated`; the `violated` list (the recipe's comes from the rules, the baseline's from the model, and R2 should be on it for any unredacted SSN); and, for a decision that matters, repeat each run a few times and see whether the verdict changes. A model that can be swapped for a cheaper one without the recipe's verdict changing is the result that supports points 2 and 3.

The baseline's policy text is a copy of the rules, kept by hand: if you edit `rules_extended.json`, edit `prompts/judge.md` too, or the two will be judging different policies. That drift is itself a cost of the baseline.

## Run

```bash
# no extra install: the rule check is a plain Python program (no SPL.py, no kernel); sympy or z3 only if you pick those engines
graf run cookbook/compliance_audit/compliance_audit.graph.yaml \
    --param document="Customer John Doe, SSN 123-45-6789, asks to update his address." \
    --param destination=external_api \
    --param rules_file="./procedures/rules.json"
```

The same audit with the other two rule engines. They need their package in the Python that runs the rule check, which is the `python3` on your `PATH`: `pip install -r cookbook/compliance_audit/requirements.txt` (or just `pip install sympy`, `pip install z3-solver`):

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

# (3) a long document from a file, with the extended rules: `document` is either the text itself or the path of a text file
#     (a relative path starts in the recipe's folder); a path that does not exist stops the run instead of being audited as text
graf run cookbook/compliance_audit/compliance_audit.graph.yaml \
    --llm claude_cli:claude-sonnet-5-5 \
    --param document="./input/customer_case_file.txt" \
    --param destination=external_api \
    --param engine=z3 \
    --param rules_file="./procedures/rules_extended.json"
```

Without the package the run stops at the rule check with an error that names it (for z3: `z3 engine needs z3-solver: pip install z3-solver`); it does not fall back to another engine. On the same facts (an unmasked SSN going to `external_api`) all three engines return `compliant: false, violated: [R1, R2]`; z3 also returns `core: [R1]`. That is the program's verdict on a fixed pii map, checked directly; I have not compared full LLM runs across engines.

`rules_file` here names the demo rules explicitly (`procedures/rules.json`); a relative path starts in the recipe's folder, not where you ran `graf run`, so this works from the repo root. `engine` is left out, so it is `stdlib`. Both are optional: leave `rules_file` out (or empty) and the demo rules are used, and add `--param engine=sympy` to pick another engine.

`engine` is `stdlib` (no dependency, the default), `sympy` or `z3`. All three give the same verdicts; see recipe 127 in SPL.py for the measurements (made with the SPL version of the check). A real run with `claude_cli` on the example above redacted the SSN, re-read the result, passed the rules and was released by the Cedar guard. `tests/test_compliance_audit.py` covers every path with a stub model, so it needs no LLM.

## Your own rules

`procedures/rules.json` holds the demo rules (R1 masking for external destinations, R2 an SSN never leaves externally, R3 card numbers always masked). Copy it, edit it, and pass `--param rules_file=my_rules.json`. Check a file with `python procedures/tools.py my_rules.json`. A missing or invalid file stops the run; the defaults are never substituted silently.

`procedures/rules_extended.json` is a larger example with eight rules and four external destinations. It checks masking per data type: besides `has_<type>` the check derives `masked_<type>` (every reported item of that type is masked; true when there is none) for ssn, ccn, email, phone, address, name, dob and other, so one stray unmasked item no longer blocks everything else. The rules: everything except an SSN masked before it goes outside (R1), an SSN never goes outside (R2), card numbers always masked (R3), an exposed card with an exposed name or birth date never goes outside (R4), name + birth date + address masked even internally (R5), contact details with a name (R6), birth date with an address (R7), unclassified data (R8). The demo `rules.json` keeps the simple all-or-nothing `is_masked`. Use the extended file as a starting point for your own policy: `--param rules_file="./procedures/rules_extended.json"`. Like the demo rules it is an illustration, not legal advice.

## Where things are

| File | Role |
|---|---|
| `compliance_audit.graph.yaml` | the workflow |
| `prompts/extract_pii.md`, `prompts/redact.md` | the two LLM prompts |
| `procedures/compliance_check.py` | the deterministic check as a program: JSON in on stdin, the verdict as one JSON line on stdout, exit 1 when it cannot run. The two `SOLVE` nodes (`check`, `recheck`) run it with `backend: subprocess` |
| `compliance_audit_llm_only.graph.yaml`, `prompts/judge.md` | the LLM-only baseline to compare with |
| `procedures/tools.py`, `procedures/rules.json` | the rule engines (stdlib, sympy, z3) and the demo rules, plain Python |
| `policies/release_policy.cedar` | permit only a compliant release; anything else is denied |

The check started as SPL.py's recipe `cookbook-solver/127_pii_compliance` and is now independent of it: plain Python, no SPL.py. (The folder is still called `procedures/`.) Each firing starts a Python process, about 20 ms for `stdlib` and 165 ms for `sympy` on one machine; the interpreter on your PATH (`python3`) must be the one that has sympy or z3 if you choose those engines.
