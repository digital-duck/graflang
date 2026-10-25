# Prompt: refactor [call 004]

- model: `qwen2.5-coder:latest`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer improving code based on feedback.

Original code:
def count_upper(s):
    uppercase_vowels = {'A', 'E', 'I', 'O', 'U'}
    count = 0
    for i in range(0, len(s), 2):
        if s[i] in uppercase_vowels:
            count += 1
    return count

Review feedback:
- The function `count_upper` does not handle lowercase vowels or non-alphabetic characters.
- The function only checks every other character in the string, ignoring any characters that are not at an even index.
- The function does not return anything if the input is an empty string.
- The function does not raise an exception if the input is not a string.
- The function name `count_upper` does not clearly indicate that it counts uppercase vowels, as it could be interpreted to count any uppercase characters.

Test failures (if any):


Rewrite the code addressing all feedback and fixing all test failures.
Return only the improved python code — no explanation, no markdown fences.
