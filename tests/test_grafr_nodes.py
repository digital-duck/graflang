"""How a GENERATE node puts values into its prompt."""
from graphlang.grafr.nodes.generate import prompt_text


def test_text_is_unchanged_and_none_is_empty():
    assert prompt_text("a\nb") == "a\nb" and prompt_text(None) == "" and prompt_text(3) == "3"


def test_a_list_of_texts_reads_one_after_another_not_as_a_python_repr():
    assert prompt_text(["chapter 1\nline", "chapter 2"]) == "chapter 1\nline\n\nchapter 2"        # no quotes, no \n escapes


def test_other_lists_and_mappings_are_json():
    assert prompt_text({"a": "é", "b": [1, 2]}) == '{\n  "a": "é",\n  "b": [\n    1,\n    2\n  ]\n}'
    assert prompt_text([1, "x"]) == '[\n  1,\n  "x"\n]'
