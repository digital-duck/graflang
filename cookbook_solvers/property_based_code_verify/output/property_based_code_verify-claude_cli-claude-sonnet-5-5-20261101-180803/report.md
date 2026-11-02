# Property-Based Code Verification Report

**Spec:** Write a function merge_sorted(a: list[int], b: list[int]) -> list[int] that takes two ALREADY-SORTED lists of integers and returns a single sorted list containing all elements of both (duplicates included).

**Hypothesis status:** `AllPassed`
**Properties passed / failed:** `9 / 0`
**Round-trip check:** `match`

## Interpretation

**All properties passed.** All 9 Hypothesis properties ran to completion (0 failed, return code 0, 0.48s), so no falsifying example was found.

**What it means:** Across the many generated input pairs, `merge_sorted` satisfied every property tested (likely sortedness, length/element preservation, and duplicate handling). That's strong evidence the implementation is correct, though not a proof. Edge cases the generators rarely hit, or properties the suite doesn't cover, could still slip through.

## Generated Implementation

```python
def merge_sorted(a: list[int], b: list[int]) -> list[int]:
    result: list[int] = []
    i, j = 0, 0
    len_a, len_b = len(a), len(b)
    while i < len_a and j < len_b:
        if a[i] <= b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    result.extend(a[i:])
    result.extend(b[j:])
    return result
```

## Generated Hypothesis Properties

```python
from hypothesis import given, settings, strategies as st


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_output_is_sorted(a, b):
    result = merge_sorted(sorted(a), sorted(b))
    assert all(result[i] <= result[i + 1] for i in range(len(result) - 1))


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_output_length_is_sum_of_inputs(a, b):
    sa, sb = sorted(a), sorted(b)
    result = merge_sorted(sa, sb)
    assert len(result) == len(sa) + len(sb)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_output_is_multiset_union(a, b):
    sa, sb = sorted(a), sorted(b)
    result = merge_sorted(sa, sb)
    assert sorted(result) == sorted(sa + sb)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_matches_sorted_concatenation(a, b):
    sa, sb = sorted(a), sorted(b)
    assert merge_sorted(sa, sb) == sorted(sa + sb)


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_commutative(a, b):
    sa, sb = sorted(a), sorted(b)
    assert merge_sorted(sa, sb) == merge_sorted(sb, sa)


@given(st.lists(st.integers()))
def test_empty_is_identity(a):
    sa = sorted(a)
    assert merge_sorted(sa, []) == sa
    assert merge_sorted([], sa) == sa


@given(st.lists(st.integers()), st.lists(st.integers()))
def test_inputs_not_mutated(a, b):
    sa, sb = sorted(a), sorted(b)
    sa_copy, sb_copy = list(sa), list(sb)
    merge_sorted(sa, sb)
    assert sa == sa_copy
    assert sb == sb_copy


@given(st.lists(st.integers()), st.lists(st.integers()), st.lists(st.integers()))
def test_associative(a, b, c):
    sa, sb, sc = sorted(a), sorted(b), sorted(c)
    assert merge_sorted(merge_sorted(sa, sb), sc) == merge_sorted(sa, merge_sorted(sb, sc))


@given(st.lists(st.integers()), st.integers(min_value=-1000, max_value=1000))
def test_shift_invariance(a, k):
    sa = sorted(a)
    b = sorted(a[::-1])
    shifted_a = [x + k for x in sa]
    shifted_b = [x + k for x in b]
    assert merge_sorted(shifted_a, shifted_b) == [x + k for x in merge_sorted(sa, b)]
```