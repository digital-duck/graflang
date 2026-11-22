You assemble a workflow by choosing ONE recipe from this catalogue to answer the user's question.

Catalogue:
- guardrail: checks that a question is about travel and answers it, or politely declines. Takes `question`, gives `reply`.
- agent_notes: answers a question about the company's pricing, holidays or contacts by reading its notes. Takes `question`, gives `answer`.

Reply with ONE JSON object and nothing else (no code fence), in exactly this shape. Use the output name of the recipe you chose in "feeds" (guardrail: reply, agent_notes: answer):
{"action": "add_part", "payload": {"id": "step1", "part": "<recipe>", "after": "pick.applied", "before": "wf_exit.trigger", "binds": {"question": "wf_entry.out_question"}, "feeds": {"<output name>": ["wf_exit.in_reply"]}}}

Question:
