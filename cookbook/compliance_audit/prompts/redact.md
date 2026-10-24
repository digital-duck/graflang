You are a data-protection editor. The document below failed a compliance check.

POLICY
R1: personal data sent to an external destination must be masked.
R2: a social security number may never leave, even masked: it must be deleted.
R3: card numbers must always be masked.

CHECK RESULT (rule ids that failed, and the facts the check used; it contains no personal data):
{{in_verdict}}

Edit the document so that it satisfies the policy:
- Delete every social security number completely. Do not leave a placeholder that shows one was there.
- Replace every other piece of personal data (card numbers, emails, phone numbers, addresses, names, dates of birth) with [REDACTED].
- Change nothing else. Do not add comments.

Output only the edited document.

DOCUMENT:
{{in_document}}
