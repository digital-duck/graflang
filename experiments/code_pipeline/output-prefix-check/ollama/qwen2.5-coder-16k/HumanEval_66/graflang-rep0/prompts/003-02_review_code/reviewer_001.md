# Prompt: reviewer [call 001]

- model: `qwen2.5-coder-16k`
- max_tokens: 1024
- temperature: 0.7

---


You are a senior python code reviewer.

Review the following python code for correctness, clarity, and robustness.
Provide specific, actionable feedback as a bullet list.
Focus on logic errors, missing edge cases, and poor naming.
Do not comment on style preferences or minor formatting.

Code:
def digitSum(s):
    return sum(ord(c) for c in s if c.isupper())
