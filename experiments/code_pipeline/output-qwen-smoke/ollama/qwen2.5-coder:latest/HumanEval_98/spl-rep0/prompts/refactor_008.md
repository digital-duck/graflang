# Prompt: refactor [call 008]

- model: `qwen2.5-coder:latest`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer improving code based on feedback.

Original code:
def count_upper(s):
    """
    Given a string s, count the number of uppercase vowels in even indices.
    
    For example:
    count_upper('aBCdEf') returns 1
    count_upper('abcdefg') returns 0
    count_upper('dBBE') returns 0
    """
    vowels = 'AEIOU'
    count = 0
    for i in range(0, len(s), 2):
        if s[i] in vowels:
            count += 1
    return count

Review feedback:
- The function `count_upper` should be case-insensitive when counting uppercase vowels.
- The function should handle empty strings gracefully.
- The function should not count vowels at odd indices, but it currently does not have a condition to ignore them.
- The function name and docstring are consistent in their description, so no change is needed there.
- The variable `vowels` should be defined as a set for faster membership testing, although this is not strictly necessary for this specific function.
- The function does not handle non-alphabetic characters, which might be an edge case depending on the requirements.

Test failures (if any):


Rewrite the code addressing all feedback and fixing all test failures.
Return only the improved python code — no explanation, no markdown fences.
