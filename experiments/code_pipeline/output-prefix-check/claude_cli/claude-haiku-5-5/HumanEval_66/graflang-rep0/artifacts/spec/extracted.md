# Specification: `digitSum`

*(Despite its name, `digitSum` sums character codes, not digits. The name is kept because the specification requires it.)*

## 1. Purpose

Provide a numeric checksum-like value for a text string. The value is the total of the Unicode code point values of the uppercase Latin letters `A`–`Z` that appear in the string. All other characters contribute nothing. The function is a pure, deterministic mapping from text to a non-negative integer, useful wherever a simple, order-independent score over uppercase ASCII letters is needed.

## 2. Inputs

- **`s`**: a single argument that must be a text string (a value of the language's `str` type, including instances of subclasses of it).
  - Any sequence of Unicode code points is permitted, including the empty string.
  - No length limit is imposed.
  - No normalisation, trimming, case folding or encoding is applied to the input. Each code point is considered individually.
  - Values of other types (including byte strings, lists of characters, numbers, `None`) are not accepted.

## 3. Outputs

- **On success:** a single non-negative integer (exact, unbounded precision).
  - Empty string, or any string containing no characters in `A`–`Z`: result is `0`.
  - Otherwise: the sum of the code point values of every occurrence of `A`–`Z` in `s`. Each occurrence counts separately, so repeated letters add repeatedly. The code point values are 65 (`A`) through 90 (`Z`).
  - Consequently, the result lies in the range `0` to `90 × len(s)` inclusive, and is always a multiple-of-nothing in particular; it has no other arithmetic constraint.
- **On invalid input:** no value is returned. A `TypeError` is raised, with a message naming the function and the actual type of the argument.

## 4. Behaviour

1. **Type check.** If `s` is not a text string, raise `TypeError` with the message `digitSum expects a str, got <TypeName>`, where `<TypeName>` is the name of the argument's type. No other processing occurs.
2. **Selection.** Examine each code point of `s` in order. Select it if and only if it lies in the closed range `A` through `Z` (code points 65–90 inclusive). The comparison is by code point, so:
   - lowercase letters (`a`–`z`) are not selected;
   - non-ASCII uppercase letters (for example `É`, U+00C9) are not selected;
   - digits, whitespace, punctuation and all other characters are not selected.
3. **Accumulation.** Return the sum of the code point values of the selected characters. An empty selection yields `0`.
4. **Order.** The result does not depend on the order of characters in `s`. It is a function of the multiset of uppercase ASCII letters present.
5. **Purity.** The function has no side effects, keeps no state between calls, and returns the same result for the same input.

### Worked examples (from the specification)

| Input | Selected characters | Result |
|---|---|---|
| `""` | none | `0` |
| `"abAB"` | `A`, `B` | `65 + 66 = 131` |
| `"abcCd"` | `C` | `67` |
| `"helloE"` | `E` | `69` |
| `"woArBld"` | `A`, `B` | `131` |
| `"aAaaaXa"` | `A`, `X` | `65 + 88 = 153` |
| `"É"` (U+00C9) | none (non-ASCII) | `0` |
| `["a", "B"]` | — (rejected) | `TypeError`: `digitSum expects a str, got list` |

### Error conditions

- Any non-`str` argument raises `TypeError`. This is the only error the function signals. No other exceptions are expected for any `str` input.

## 5. Assumptions

- **Text model.** Input is a sequence of Unicode code points, not bytes or an encoded form. Code point values are the "ASCII codes" for the purpose of this function, which holds because only the ASCII range is selected.
- **Letter set is fixed.** "Uppercase" means exactly the Latin letters `A`–`Z`. Locale-dependent case rules, Unicode general category, and case-mapping tables are deliberately not consulted.
- **No character normalisation.** Composed and decomposed forms are not reconciled. A letter followed by a combining mark is still counted as the letter alone, and the combining mark is ignored.
- **Integer arithmetic is exact.** The sum never overflows or loses precision, as the result type is unbounded.
- **Caller responsibility.** The caller supplies a string-typed value; the function does not coerce or convert other types. The function does not validate the length or the content of the string beyond the type check.
- **Name is a label only.** The identifier `digitSum` must not be read as meaning "sum of digits". Callers relying on digit semantics will get incorrect results.