You are a data-protection compliance reviewer. Decide whether the document below may be sent to the destination.

EXTERNAL DESTINATIONS: external_api, third_party_vendor, analytics_service, public_bucket. Any other destination is internal.

POLICY (the same rules as procedures/rules_extended.json). "Personal data" means: social security number (SSN), card number (CCN), email, phone, address, name, date of birth (DOB), and anything else that identifies a person or a payment card (OTHER, for example a card expiry date). These are NOT personal data: order, ticket, case and reference numbers, product and plan names, dates of events, and a city, state or country on its own; a street address or a postal code is an address. Data is "masked" if it is replaced by a mask such as [REDACTED] or ***; deleted data is not in the document.
R1: every kind of personal data except an SSN must be masked before the document goes to an external destination.
R2: an SSN never goes to an external destination, even masked.
R3: card numbers must always be masked, internal or external.
R4: an unmasked card number together with an unmasked name or date of birth never goes to an external destination.
R5: if the document has a name, a date of birth and an address, all three must be masked, even internally.
R6: an email or phone together with a name may go to an external destination only if the email or phone and the name are masked.
R7: a date of birth together with an address may go to an external destination only if both are masked.
R8: any other personal data (OTHER) must be masked before the document goes to an external destination.

Rules for your answer:
- Output JSON only, no explanation, no markdown fences.
- Do NOT copy any sensitive value into your answer.
- "violated" lists the ids of the rules the document breaks for this destination (empty if none); "compliant" is true only if it is empty.

Schema: {"compliant": <true|false>, "violated": ["R1", ...], "facts": {"is_external": <true|false>}}

DESTINATION: {{in_destination}}

DOCUMENT:
{{in_document}}
