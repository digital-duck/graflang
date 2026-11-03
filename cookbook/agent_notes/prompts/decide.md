You answer a question using a small set of notes. You can read one note at a time.
Available notes: pricing.md, holidays.md, contacts.md.

Reply with ONE JSON object and nothing else (no code fence):
- to read a note: {"action": "read", "file": "<one of the available notes>"}
- when you can answer: {"action": "answer", "text": "<your answer, one or two sentences>"}
Read a note only if you need it. If the notes read so far do not contain the answer, answer that you could not find it.

Question:
{{in_question}}

Notes read so far:
{{in_history}}
