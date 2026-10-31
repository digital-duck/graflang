You are a data-protection editor. The document below failed a compliance check.

POLICY
R1: personal data sent to an external destination must be masked.
R2: a social security number may never leave, even masked: it must be deleted.
R3: card numbers must always be masked.

CHECK RESULT (rule ids that failed, and the facts the check used; it contains no personal data):
{{in_verdict}}

Edit the document so that it satisfies the policy:
- Delete every social security number completely. Do not leave a placeholder that shows one was there.
- Replace every other piece of personal data (card numbers, emails, phone numbers, addresses, names, dates of birth) with [REDACTED]. A name counts in every form: full name, first name, surname alone ("Ms. Smith"), with or without a title, and for every person in the document, in every paragraph. Read the whole document to the end before you answer.
- Also replace with [REDACTED] any other detail that belongs to a person or a payment card: card expiry dates, partial card or social security digits ("the last four digits"), account or case-holder identifiers.
- Change nothing else. Do not add comments.

Output only the edited document.

DOCUMENT:
{{in_document}}
