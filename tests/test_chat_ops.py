"""Chat edits: the model's operations go through the editor, all or none, and a prompt file is staged until Save."""
import shutil
from pathlib import Path

import pytest

from graphlang.grafv import chat_ops as C
from graphlang.grafv.editor import EditError, GraphEditor

SELF_REFINE = Path(__file__).parent.parent / "cookbook" / "self_refine"


@pytest.fixture
def ed(tmp_path):
    dest = tmp_path / "self_refine"
    shutil.copytree(SELF_REFINE, dest, ignore=shutil.ignore_patterns("output"))
    return GraphEditor(dest / "self_refine.graph.yaml")


def test_parse_reply_reads_plain_fenced_and_wrapped_json():
    plain = '{"say": "done", "ops": [{"op": "remove_node", "id": "a"}]}'
    assert C.parse_reply(plain) == ("done", [{"op": "remove_node", "id": "a"}])
    assert C.parse_reply(f"```json\n{plain}\n```")[0] == "done"
    assert C.parse_reply(f"Sure! {plain} Hope that helps.")[0] == "done"
    assert C.parse_reply('{"say": "cannot", "ops": []}') == ("cannot", [])


@pytest.mark.parametrize("reply", ["no json here", '{"say": "x", "ops": "nope"}', "[1, 2]", ""])
def test_parse_reply_refuses_anything_else(reply):
    with pytest.raises(EditError, match="JSON"):
        C.parse_reply(reply)


def test_ops_change_the_graph_keep_the_comments_and_can_be_undone(ed):
    staged = {}
    done = C.apply_ops(ed, [
        {"op": "set_config", "node": "draft", "key": "llm", "value": "claude_cli:claude-haiku-5-5"},
        {"op": "add_node", "id": "polish", "type": "GENERATE", "ports": ["trigger", "complete", "in_essay", "out_essay"],
         "config": {"prompt_inline": "Polish {{in_essay}}"}},
        {"op": "add_edge", "source": "refine.complete", "target": "polish.trigger", "type": "triggers"},
    ], staged)
    assert done == ["set draft.llm", "added node polish", "added triggers edge refine.complete -> polish.trigger"]
    assert ed.changed and "polish" in ed.node_ids() and ed.node("draft")["config"]["llm"] == "claude_cli:claude-haiku-5-5"
    assert "# Control flow" in ed._dump()
    while ed.undo():
        pass
    assert not ed.changed


def test_one_bad_operation_applies_none_of_them(ed):
    before = ed._dump()
    staged = {"prompts/keep.md": "kept"}
    with pytest.raises(EditError):
        C.apply_ops(ed, [
            {"op": "set_config", "node": "draft", "key": "llm", "value": "x:y"},
            {"op": "write_file", "path": "prompts/new.md", "text": "n"},
            {"op": "remove_node", "id": "no_such_node"},
        ], staged)
    assert ed._dump() == before and not ed.changed and staged == {"prompts/keep.md": "kept"}


@pytest.mark.parametrize("op", [{"op": "format_disk"}, {"op": "remove_node"}, "remove_node", {"op": "add_node", "id": "x", "type": "GENERATE", "ports": "trigger"}])
def test_unknown_or_incomplete_operations_are_refused(ed, op):
    with pytest.raises(EditError):
        C.apply_ops(ed, [op], {})
    assert not ed.changed


@pytest.mark.parametrize("path", ["../evil.md", "prompts/../evil.md", "/etc/passwd", "draft.graph.yaml", "prompts/sub/x.md", "prompts/x.py"])
def test_a_file_may_only_be_written_under_prompts(ed, path):
    staged = {}
    with pytest.raises(EditError, match="prompts/"):
        C.apply_ops(ed, [{"op": "write_file", "path": path, "text": "x"}], staged)
    assert staged == {}


def test_a_prompt_file_is_staged_then_written_only_when_asked(ed):
    folder = ed.path.parent
    staged = {}
    C.apply_ops(ed, [{"op": "write_file", "path": "prompts/draft.md", "text": "NEW PROMPT"}], staged)
    original = (folder / "prompts" / "draft.md").read_text()
    assert original != "NEW PROMPT" and C.prompt_files(folder, staged)["prompts/draft.md"] == "NEW PROMPT"
    C.write_staged(folder, staged)
    assert (folder / "prompts" / "draft.md").read_text() == "NEW PROMPT"


def test_the_prompt_shows_the_graph_the_files_and_the_request(ed):
    p = C.build_prompt(ed._dump(), C.prompt_files(ed.path.parent, {}), "make it shorter", ["GENERATE", "LOOP"])
    assert "make it shorter" in p and "prompts/draft.md" in p and "in_topic" in p and "Node types: GENERATE, LOOP" in p
