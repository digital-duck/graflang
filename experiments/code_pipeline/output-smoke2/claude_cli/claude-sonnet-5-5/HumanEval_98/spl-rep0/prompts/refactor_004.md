# Prompt: refactor [call 004]

- model: `claude-sonnet-5-5`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer improving code based on feedback.

Original code:
def count_upper(s):
    vowels = "AEIOU"
    return sum(1 for i in range(0, len(s), 2) if s[i] in vowels)

Review feedback:
Review of `count_upper`:

- **Logic matches the likely intent, but the intent isn't stated.** The function counts uppercase vowels at even indices (0, 2, 4, …). That is the known HumanEval/98 spec, but nothing in the code or a docstring says so. The name `count_upper` suggests "count uppercase letters", which is misleading. Rename it (e.g. `count_uppercase_vowels_at_even_indices`) or add a docstring stating the contract.

- **Uppercase letters outside `"AEIOU"` are ignored by design, but there's no way to tell.** `'É'`, `'Å'` and other accented or non-ASCII uppercase vowels are not counted. If the input can be non-English text, say that this is ASCII-only. If it can't, document that.

- **Substring membership is a subtle trap.** `s[i] in vowels` works here because `s[i]` is always one character. Still, `in` on a string is a substring test, so it would silently change meaning if someone later slices instead of indexing (e.g. `s[i:i+2]`). Use a `frozenset("AEIOU")` as a module-level constant. That makes the intent clear and gives O(1) lookups. It also avoids rebuilding `vowels` on every call.

- **No input validation.** `None` raises `TypeError` from `len`. A non-string iterable such as a list of single characters happens to work. Other types fail confusingly, and an `int` fails inside `len`. If this is a public function, either validate with a clear error or document that `s` must be `str`.

- **Edge cases are handled correctly but untested.** The empty string returns 0 and a single character works. Add tests for:
  - `""`
  - `"A"` (returns 1)
  - `"a"` (returns 0)
  - `"aBCdEf"` (returns 1)
  - `"AbEcIdOfU"` (index 8 is `'U'`, so it returns 4)
  - lowercase vowels at even indices
  - uppercase vowels only at odd indices

- **Simplify the iteration.** `s[::2]` yields exactly the even-index characters, so `sum(ch in VOWELS for ch in s[::2])` removes the index arithmetic and the `range`/`len` pairing. Index-based code is the usual place for off-by-one errors. The slice copies the string, which is negligible unless `s` is huge. If that matters, use `itertools.islice(s, 0, None, 2)`.

- **Naming of the loop variable.** `i` is fine as an index, but with the slice approach, `ch` conveys more.

Suggested version:

```python
_UPPER_VOWELS = frozenset("AEIOU")

def count_upper(s: str) -> int:
    """Count uppercase vowels (A, E, I, O, U) at even indices of s."""
    return sum(ch in _UPPER_VOWELS for ch in s[::2])
```

No correctness bugs found; the concerns are naming, documentation, and robustness.

Test failures (if any):


Rewrite the code addressing all feedback and fixing all test failures.
Return only the improved python code — no explanation, no markdown fences.
