# Prompt: coder [call 002]

- model: `qwen2.5-coder:latest`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer.

Write clean, correct, well-structured python code for the following specification.
Return only the code — no explanation, no markdown fences.

Specification:
Implement the following Python function. Return the complete function, including its signature and any imports it needs.


def count_upper(s):
    """
    Given a string s, count the number of uppercase vowels in even indices.
    
    For example:
    count_upper('aBCdEf') returns 1
    count_upper('abcdefg') returns 0
    count_upper('dBBE') returns 0
    """
