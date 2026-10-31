

def test_json_get_reads_a_field_that_holds_a_code_fence():
    import json
    from graphlang.grafr.expr import FUNCS
    text = json.dumps({"passed": False, "report": "[FAILED]\n```\ntraceback\n```"})
    assert FUNCS["json_get"](text, "report") == "[FAILED]\n```\ntraceback\n```" and FUNCS["json_get"](text, "passed") is False
    assert FUNCS["json_get"]("```json\n{\"a\": 1}\n```", "a") == 1                         # a fence around the JSON still works
