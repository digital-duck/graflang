- **Unicode leak in `isupper()`:** The task asks for ASCII codes, but `str.isupper()` is Unicode-aware. `digitSum("É")` returns 201 and `digitSum("Ⅻ")` returns the code point of a Roman numeral, which isn't an ASCII letter. If the intent is ASCII only, use an explicit range check such as `if 'A' <= c <= 'Z'`. If Unicode uppercase is intended, the docstring should say "ASCII" is not what's computed.

- **Misleading name:** `digitSum` suggests digits, but the function sums the ASCII codes of uppercase letters. A name like `sum_upper_ascii` says what it does. The camelCase also doesn't match Python convention, though that's a minor point.

- **Docstring spec is ambiguous and has a typo:** The stray `'` after "only" is a typo. The spec doesn't say what happens for non-ASCII input, which is the case the `isupper()` issue above depends on. Stating the intended character set explicitly would settle it.

- **Examples aren't executable:** The `=>` notation can't run as doctests, so the examples can silently drift from the code. Switching to `>>> digitSum("abAB")` followed by `131` makes them checkable with `python -m doctest`. I checked all six examples by hand against the implementation and they match, so this is about keeping them verified, not a current bug.

- **No input validation or documented failure mode:** `digitSum(None)` raises a `TypeError` from iteration, which is acceptable, but a non-string iterable like `["a", "B"]` will also run without error. Either document that the input must be `str` or add an `isinstance` check that raises a clear error.

- **Edge cases that are handled correctly:** The empty string returns 0 because `sum` of an empty generator is 0, and the single-argument generator is fine for long inputs. No logic bug in the current examples.