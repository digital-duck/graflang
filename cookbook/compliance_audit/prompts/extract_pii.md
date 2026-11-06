You are a data-protection analyst. List the kinds of personal data in the document below.

Rules for your answer:
- Output JSON only, no explanation, no markdown fences.
- Do NOT copy any sensitive value into your answer. Report the TYPE only.
- Use these types: SSN, CCN, EMAIL, PHONE, ADDRESS, NAME, DOB, OTHER.
- "masked" is true only if the value in the document is already replaced by a mask such as [REDACTED] or ***.
- A value that has been deleted is not in the document, so do not report it.
- These are NOT personal data, do not report them: order, ticket, case and reference numbers, product and plan names, dates of events, and a city, state or country on its own. Report ADDRESS for a street address or a postal code, and OTHER for an identifier that belongs to a person (a username, a membership or customer number) or a card expiry date.

Schema: {"entities": [{"type": "<TYPE>", "masked": <true|false>}]}

DOCUMENT:
{{in_document}}
