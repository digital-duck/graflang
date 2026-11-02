# Code Generation Report

**Status:** `VERIFIED` — 27 passed / 0 failed

**Spec:** Write a Python function merge_sorted(a, b) that merges two sorted lists into one sorted list without using sorted() or list.sort(). Both input lists contain integers and are already sorted ascending. The function must run in O(n+m) time.

## Generated Code

```python
def merge_sorted(a, b):
    result = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    while i < len(a):
        result.append(a[i])
        i += 1
    while j < len(b):
        result.append(b[j])
        j += 1
    return result
```

## Generated Tests (from spec, independent of code)

```python
def test_both_empty():
    assert merge_sorted([], []) == []


def test_first_empty():
    assert merge_sorted([], [1, 2, 3]) == [1, 2, 3]


def test_second_empty():
    assert merge_sorted([1, 2, 3], []) == [1, 2, 3]


def test_basic_interleaved():
    assert merge_sorted([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]


def test_all_a_before_b():
    assert merge_sorted([1, 2, 3], [4, 5, 6]) == [1, 2, 3, 4, 5, 6]


def test_all_b_before_a():
    assert merge_sorted([4, 5, 6], [1, 2, 3]) == [1, 2, 3, 4, 5, 6]


def test_single_elements_ordered():
    assert merge_sorted([1], [2]) == [1, 2]


def test_single_elements_reversed():
    assert merge_sorted([2], [1]) == [1, 2]


def test_single_element_each_equal():
    assert merge_sorted([5], [5]) == [5, 5]


def test_duplicates_across_lists():
    assert merge_sorted([1, 2, 2, 3], [2, 3, 4]) == [1, 2, 2, 2, 3, 3, 4]


def test_duplicates_within_list():
    assert merge_sorted([1, 1, 1], [1, 1]) == [1, 1, 1, 1, 1]


def test_identical_lists():
    assert merge_sorted([1, 2, 3], [1, 2, 3]) == [1, 1, 2, 2, 3, 3]


def test_negative_numbers():
    assert merge_sorted([-5, -3, -1], [-4, -2, 0]) == [-5, -4, -3, -2, -1, 0]


def test_mixed_negative_positive():
    assert merge_sorted([-2, 0, 2], [-1, 1, 3]) == [-2, -1, 0, 1, 2, 3]


def test_different_lengths_a_longer():
    assert merge_sorted([1, 2, 3, 4, 5, 6], [3]) == [1, 2, 3, 3, 4, 5, 6]


def test_different_lengths_b_longer():
    assert merge_sorted([3], [1, 2, 3, 4, 5, 6]) == [1, 2, 3, 3, 4, 5, 6]


def test_a_tail_remaining():
    assert merge_sorted([1, 10, 20], [2]) == [1, 2, 10, 20]


def test_b_tail_remaining():
    assert merge_sorted([2], [1, 10, 20]) == [1, 2, 10, 20]


def test_large_values():
    assert merge_sorted([10**12, 10**15], [10**13]) == [10**12, 10**13, 10**15]


def test_zeros():
    assert merge_sorted([0, 0], [0]) == [0, 0, 0]


def test_returns_list_type():
    assert isinstance(merge_sorted([1], [2]), list)


def test_result_length():
    assert len(merge_sorted([1, 3, 5], [2, 4])) == 5


def test_does_not_mutate_first_input():
    a = [1, 3, 5]
    merge_sorted(a, [2, 4])
    assert a == [1, 3, 5]


def test_does_not_mutate_second_input():
    b = [2, 4]
    merge_sorted([1, 3, 5], b)
    assert b == [2, 4]


def test_result_is_sorted_large():
    a = list(range(0, 2000, 2))
    b = list(range(1, 2000, 2))
    assert merge_sorted(a, b) == list(range(2000))


def test_large_input_performance_linear():
    import time
    a = list(range(0, 400000, 2))
    b = list(range(1, 400000, 2))
    start = time.time()
    result = merge_sorted(a, b)
    elapsed = time.time() - start
    assert result[:3] == [0, 1, 2] and elapsed < 5


def test_does_not_call_sorted(monkeypatch):
    import builtins

    def fail(*args, **kwargs):
        raise AssertionError("sorted() must not be used")

    monkeypatch.setattr(builtins, "sorted", fail)
    assert merge_sorted([1, 3], [2, 4]) == [1, 2, 3, 4]
```

## Pytest Output

```
[1m============================= test session starts ==============================[0m
collected 27 items

test_solution.py [32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m                             [100%][0m

[32m============================== [32m[1m27 passed[0m[32m in 0.10s[0m[32m ==============================[0m
```

## Explanation

The function merges two already-sorted lists by keeping one pointer in each list and repeatedly comparing the two items they point at. The smaller item is appended to the result and that pointer moves forward, so each element is looked at and copied exactly once, which gives O(n+m) time with no call to sorted() or list.sort(). When one list runs out, the two trailing loops copy over whatever remains of the other list, since those leftovers are already sorted and are all at least as large as everything placed so far. Edge cases covered by this structure include empty inputs (either or both lists, since the main loop is skipped and the leftover loops handle it), lists of unequal length, lists with no overlap in values, and duplicates, which are kept and kept stable because the comparison uses <= and so takes from the first list on ties. The pytest run shows all 27 tests passing with none failing, which proves the function produces correct output on those specific cases, but it does not by itself prove correctness for every possible input or measure the O(n+m) running time; that guarantee comes from reading the code, where each loop advances a pointer on every iteration.