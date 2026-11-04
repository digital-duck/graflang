# batch-test: many different documents, with answer keys

Eighteen documents for testing the compliance audit on **variety**, not on one document run again and again. Extraction varies from model to model and from document to document, so the realistic test is a set of different inputs, each scored against its own answer key. All data is invented (example domains, test card numbers, 555 phone numbers, made-up people).

| kind | documents |
|---|---|
| no personal data (should be released as it is) | `clean_status_report`, `clean_company_contacts`, `already_masked`, `borderline_ids` |
| each type of personal data | `ssn_plain`, `ssn_masked_only`, `email_obfuscated`, `phone_formats`, `address_one_line`, `dob_prose`, `name_titles`, `card_numbers` |
| hard for a different reason | `injection_override` (an order to say "compliant"), `spanish_incident` (not English, with a national id), `csv_table` (six people in a table), `chat_log_long` (data scattered through a long chat) |
| the two earlier demo documents | `../customer_case_file.txt`, `../hard_case_file.txt` |

`manifest.json` holds the key for each document:

- `must_mask`: strings that must **not** appear in a released text. One left behind is a **false release**, the costly error.
- `must_keep`: strings that should survive (ids, amounts, dates the study needs). One missing is **over-redaction**.
- `ambiguous`: items a policy has to rule on (company contacts, an employee id, an IP address, a first name). Reported, never scored.
- `expect`: `released` (default) or `escalated`. A document expected to be released that is escalated is a **false escalation**.

`tests/test_batch_test.py` checks that every key string really is in its document. The keys are my reading of what is personal data under the demo policy; where that is a judgement call the string is `ambiguous`, not scored. Read them critically and change them: the numbers are only as good as the keys.

## Run it

```bash
conda activate graf
cd /path/to/graflang

# the plan only: how many runs and at most how many model calls (nothing is sent)
python cookbook/compliance_audit/batch_test.py --variants recipe-z3,baseline --llm claude_cli:claude-haiku-5-5

# make the calls (a run makes at most 3 model calls and is capped at 4); --max-calls refuses a bigger plan
python cookbook/compliance_audit/batch_test.py --variants recipe-z3,baseline --llm claude_cli:claude-haiku-5-5 --max-calls 120 --yes
```

Results go to `cookbook/compliance_audit/output/batch_test-<time>/`: `results.jsonl` (one line per run, written as it arrives), `summary.md` (a table per variant and model, and a table per document) and the full output folder of every run under `runs/`. A stopped batch continues with `--resume --out <that folder>`.

## What to vary

| dimension | how | what it tests |
|---|---|---|
| **solver on/off** | `--variants recipe-z3,recipe-stdlib,recipe-sympy,baseline` | the three rule engines (they must agree), and the LLM-only baseline (no solver at all) |
| **model** | `--llm claude_cli:claude-haiku-5-5,claude_cli:claude-sonnet-5-5,ollama:gemma4` | how much the extraction and redaction quality depends on the model |
| **rules** | `--rules-file ./procedures/rules.json` or `rules_extended.json` | the simple all-or-nothing rules against per-type masking |
| **destination** | `--destination internal_crm` | external against internal handling (masking is looser inside) |
| **kind of document** | `--docs clean`, `--docs ssn,card`, `--docs injection` (ids or tags) | where a model or a variant is weak |
| **prompts** | edit `prompts/extract_pii.md` or `prompts/redact.md`, run again with another `--out` | whether a prompt change fixes an over-flag without opening a leak |
| **policy** | edit `procedures/rules_extended.json` (for example a rule for company contacts) | the same facts under another policy |
| **the key** | edit `manifest.json` | how sensitive the scores are to the judgement calls |

Not built: a `--repeat N` for the same cell (the point of this batch is variety, but sampling noise per cell is worth knowing once), a per-document answer key for **which items** were found (today only what remains in the released text is scored), and scoring of the redacted text's usefulness for the vendor's study beyond `must_keep`.
