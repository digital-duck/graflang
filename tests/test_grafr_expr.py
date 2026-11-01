"""The safe expression evaluator used by EVALUATE / ASSERT / LOOP conditions."""
import pytest

from graphlang.grafr.expr import ExpressionError, evaluate, evaluate_condition, variables


def test_conditions_from_the_shipped_graphs():
    assert evaluate_condition("contains(@in_analysis, '[READY]')", {"in_analysis": "ok [READY] go"})
    assert not evaluate_condition("contains(@in_analysis, '[READY]')", {"in_analysis": "vague"})
    assert evaluate_condition("@in_check_closure == TRUE", {"in_check_closure": True})
    assert not evaluate_condition("@in_check_closure == TRUE", {"in_check_closure": False})
    scope = {"test_passed": False, "denied": False, "cycle": 1, "in_max_cycles": 3}
    cond = "NOT @test_passed AND NOT @denied AND @cycle < @in_max_cycles"
    assert evaluate_condition(cond, scope)
    assert not evaluate_condition(cond, {**scope, "cycle": 3})
    assert not evaluate_condition(cond, {**scope, "test_passed": True})
    assert evaluate_condition("@chapter_index < @in_num_chapters", {"chapter_index": 2, "in_num_chapters": 3})


def test_operators_literals_and_functions():
    assert evaluate("1 + 2 * 3") == 7
    assert evaluate("(1 + 2) * 3") == 9
    assert evaluate("7 // 2") == 3 and evaluate("7 % 4") == 3 and evaluate("1 / 4") == 0.25
    assert evaluate("'a' + 'b'") == "ab"
    assert evaluate("1 < 2 < 3") is True and evaluate("1 < 3 < 2") is False
    assert evaluate("@x in [1, 2, 3]", {"x": 2}) is True and evaluate("@x not in (1, 2)", {"x": 5}) is True
    assert evaluate("true and not false") is True and evaluate("null == null") is True      # any case
    assert evaluate("len(@s) > 2 and upper(@s) == 'ABC'", {"s": "abc"}) is True
    assert evaluate("startswith(@s, 'a') OR endswith(@s, 'z')", {"s": "abc"}) is True
    assert evaluate("is_empty(@s)", {"s": ""}) is True and evaluate("is_empty(@s)", {"s": None}) is True
    assert evaluate("contains(@xs, 2)", {"xs": [1, 2]}) is True and evaluate("contains(@s, 'a')", {"s": None}) is False
    assert evaluate("max(@a, @b) - min(@a, @b)", {"a": 3, "b": 10}) == 7
    assert evaluate("int('4') + float('0.5')") == 4.5
    assert evaluate("'[PASSED]' in @r", {"r": "x [PASSED] y"}) is True


def test_short_circuit_does_not_evaluate_the_right_side():
    assert evaluate("false and @missing") is False
    assert evaluate("true or @missing") is True
    with pytest.raises(ExpressionError, match="unknown variable @missing"):
        evaluate("true and @missing")


def test_variables_lists_what_an_expression_uses():
    assert variables("NOT @a AND contains(@b, 'x') OR @c > 1") == {"a", "b", "c"}


@pytest.mark.parametrize("bad", [
    "__import__('os').system('echo hi')",
    "open('/etc/passwd')",
    "@x.__class__",
    "@x.upper()",
    "().__class__.__bases__",
    "[c for c in 'abc']",
    "(lambda: 1)()",
    "2 ** 10",
    "exec('1')",
    "eval('1')",
    "len(@x, key=1)",
    "bare_name",
    "b'bytes'",
    "1j",
    "@x if @y else 1",
    "{'a': 1}",
    "...",
])
def test_anything_outside_the_whitelist_is_rejected(bad):
    with pytest.raises(ExpressionError):
        evaluate(bad, {"x": "abc", "y": 1})


def test_limits_and_errors_are_expression_errors():
    with pytest.raises(ExpressionError, match="empty"):
        evaluate("   ")
    with pytest.raises(ExpressionError, match="longer"):
        evaluate("1 + " * 1000 + "1")
    with pytest.raises(ExpressionError, match="too large"):
        evaluate("+".join(["1"] * 200))
    with pytest.raises(ExpressionError, match="repetition"):
        evaluate("'ab' * 100000")
    with pytest.raises(ExpressionError, match="ZeroDivisionError"):
        evaluate("1 / 0")
    with pytest.raises(ExpressionError, match="TypeError"):
        evaluate("@a < @b", {"a": None, "b": 1})
    with pytest.raises(ExpressionError, match="cannot parse"):
        evaluate("1 +")
    with pytest.raises(ExpressionError, match="unknown variable @nope; available: \\['x'\\]"):
        evaluate("@nope", {"x": 1})


def test_json_get_reads_typed_fields_from_json_text_or_a_dict():
    verdict = '{"compliant": false, "violated": ["R1", "R2"], "facts": {"is_external": true}}'
    assert evaluate("json_get(@v, 'compliant') == FALSE", {"v": verdict}) is True
    assert evaluate("json_get(@v, 'facts.is_external') == TRUE", {"v": verdict}) is True    # a JSON true stays a boolean
    assert evaluate("json_get(@v, 'violated.1')", {"v": verdict}) == "R2"
    assert evaluate("json_get(@v, 'facts.is_external')", {"v": {"facts": {"is_external": True}}}) is True


def test_json_get_tolerates_a_code_fence_and_falls_back_to_the_default():
    assert evaluate("json_get(@v, 'a')", {"v": '```json\n{"a": 1}\n```'}) == 1
    assert evaluate("json_get(@v, 'a', 'none')", {"v": "not json"}) == "none"
    assert evaluate("json_get(@v, 'a.b')", {"v": '{"a": 1}'}) == ""
    assert evaluate("json_get(@v, 'a.5')", {"v": '{"a": [1]}'}) == ""


def test_fields_and_items():
    scope = {"args": {"topic": "tides", "n": 2}, "xs": [10, 20], "d": {"k": 1}}
    assert evaluate("@args.topic", scope) == "tides" and evaluate("@args.n + 1", scope) == 3
    assert evaluate("@xs[1]", scope) == 20 and evaluate("@d['k']", scope) == 1
    for bad in ("@args.missing", "@args.__class__", "@xs[9]", "@xs[0:1]", "@args.topic.upper"):
        with pytest.raises(ExpressionError):
            evaluate(bad, scope)


def test_latest_is_the_value_before_a_loop_until_an_iteration_sets_it():
    assert evaluate("latest(@in_n, @n)", {"in_n": 0, "n": None}) == 0           # zero and empty text are values, not "unset"
    assert evaluate("latest(@in_n, @n)", {"in_n": 0, "n": 2}) == 2
    assert evaluate("latest(@in_s, @s)", {"in_s": "", "s": None}) == ""


# ── f-strings: the lift of SPL's string building (`@trace + f'{@step_no}. {@line}\n'`) ───────────────────────────

SCOPE = {"trace": "T\n", "step_no": 3, "line": "x", "stmt": "a b", "v": 3.14159, "d": {"k": "v"}}


def test_an_f_string_fills_its_fields_from_the_variables():
    assert evaluate("@trace + f'{@step_no}. {@line}\\n'", SCOPE) == "T\n3. x\n"
    assert evaluate("F'{@step_no}'", SCOPE) == "3" and evaluate("f''", SCOPE) == "" and evaluate("f'a' + 'b'") == "ab"
    assert evaluate("f'{@step_no + 1}|{@d[\"k\"]}|{{braces}}'", SCOPE) == "4|v|{braces}"
    assert evaluate("len(f'{@step_no}x')", SCOPE) == 2 and evaluate("contains(f'{@step_no}a', '3a')", SCOPE) is True


def test_an_f_string_may_hold_quotes_of_the_other_kind_and_a_raw_prefix():
    assert evaluate("f\"print(f(r'''{@stmt}'''))\"", SCOPE) == "print(f(r'''a b'''))"
    assert evaluate("rf'\\d{@step_no}'", SCOPE) == "\\d3"
    assert evaluate("'it' + \"'s\" + f'{@step_no}'", SCOPE) == "it's3"


def test_conversions_and_plain_format_specs_work():
    assert evaluate("f'{@v:.2f}|{@step_no:>4}|{@trace!r}|{@v!s:>8}'", SCOPE) == "3.14|   3|'T\\n'| 3.14159"


def test_the_variables_of_an_f_string_are_found_and_the_whitelist_still_applies():
    assert variables("f'{@step_no} {@line}'") == {"step_no", "line"}
    for bad in ("f'{open(1)}'", "f'{__import__(1)}'", "f'{@d.__class__}'", "f'{@v:.2f}'.upper()", "f'{x}'"):
        with pytest.raises(ExpressionError):
            evaluate(bad, SCOPE)


@pytest.mark.parametrize("bad", ["f'{@v:{@step_no}}'", "f'{@v!x}'", "f'{@v=}'", "f'{'", "f'}'", "f'{}'", "f'{@v:99999}'", "bf'x'", "f'{@v:.2f}' * 5000", "f'abc"])
def test_an_f_string_that_is_not_allowed_is_an_error_not_a_crash(bad):
    with pytest.raises(ExpressionError):
        evaluate(bad, SCOPE)


def test_the_helper_functions_of_an_f_string_are_not_listed_to_the_user():
    with pytest.raises(ExpressionError) as e:
        evaluate("nope(1)")
    assert "__fstr" not in str(e.value) and "contains" in str(e.value)


def test_an_f_string_in_a_condition_and_in_a_context_expression_runs_in_a_graph():
    from graphlang.grafr.runtime import GraphLangRuntime
    graph = {"version": "1.0-graph", "workflow": {"name": "t", "inputs": [{"name": "n", "type": "INTEGER", "default": 7}], "outputs": [{"name": "text", "type": "TEXT"}]},
             "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry", "out_n"]},
                       {"id": "c", "type": "CONTEXT", "config": {"action": "set", "expression": "f'step {@in_n}: ' + 'ok'"}, "ports": ["trigger", "complete", "in_n", "out_text"]},
                       {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_text"]}],
             "edges": [{"source": "s.entry", "target": "c.trigger", "type": "triggers"}, {"source": "s.out_n", "target": "c.in_n", "type": "binds"},
                       {"source": "c.out_text", "target": "o.in_text", "type": "binds"}, {"source": "c.complete", "target": "o.trigger", "type": "triggers"}]}
    assert GraphLangRuntime(graph, verbose=False).execute({}) == {"text": "step 7: ok"}
