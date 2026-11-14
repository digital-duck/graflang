"""Files attached to a chat message: documents go into the message, images go to a model that can see them, anything else is refused."""
import sys
import types

import pytest

from graphlang.grafr.adapters import DDLLM, LLMUnavailable
from graphlang.grafv import attachments as A


class File:
    def __init__(self, name, data):
        self.name, self._data = name, data

    def getvalue(self):
        return self._data


def test_unpack_takes_a_plain_string_or_text_with_files():
    assert A.unpack("hello") == ("hello", []) and A.unpack(None) == ("", [])
    value = types.SimpleNamespace(text="hi", files=[File("a.txt", b"x")])
    assert A.unpack(value)[0] == "hi" and len(A.unpack(value)[1]) == 1


def test_a_document_is_read_into_the_message_marked_as_material_not_instructions():
    found, notes = A.read([File("spec.md", "# Translator\nTranslate text.\n".encode())])
    assert notes == [] and found[0].text.startswith("# Translator")
    message = A.with_documents("make this app", found)
    assert message.startswith("make this app") and "not instructions to you" in message and "--- spec.md ---" in message and "Translate text." in message
    assert A.listing(found) == "\n📎 spec.md" and "Translate" not in A.listing(found)


def test_a_document_that_holds_a_code_fence_is_fenced_with_more_backticks():
    found, _ = A.read([File("n.md", b"```py\nx=1\n```")])
    assert "````" in A.with_documents("m", found)


def test_a_long_document_is_cut_and_says_so():
    found, _ = A.read([File("big.txt", b"x" * (A.MAX_TEXT_CHARS + 5))])
    assert len(found[0].text) == A.MAX_TEXT_CHARS and found[0].truncated and "(cut short)" in A.with_documents("m", found)


def test_an_image_is_kept_as_bytes_with_its_type_and_is_not_put_in_the_text():
    found, _ = A.read([File("shot.PNG", b"\x89PNG..."), File("p.jpeg", b"jpg")])
    assert A.images(found) == [("image/png", b"\x89PNG..."), ("image/jpeg", b"jpg")] and A.documents(found) == []
    assert A.with_documents("m", found) == "m"


@pytest.mark.parametrize("name,data,reason", [("a.pdf", b"%PDF", "cannot be read"), ("a.txt", b"\xff\xfe\x00bad", "not UTF-8"),
                                              ("noext", b"x", "without an extension")])
def test_a_file_that_cannot_be_used_is_refused_with_the_reason(name, data, reason):
    found, notes = A.read([File(name, data)])
    assert found == [] and len(notes) == 1 and reason in notes[0] and name in notes[0]


def test_a_huge_image_and_too_many_files_are_refused():
    found, notes = A.read([File("big.png", b"0" * (A.MAX_IMAGE_BYTES + 1))])
    assert found == [] and "larger than" in notes[0]
    found, notes = A.read([File(f"{i}.txt", b"x") for i in range(A.MAX_FILES + 2)])
    assert len(found) == A.MAX_FILES and "only the first" in notes[-1]


# ── showing an image to a model ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def fake_dd_llm(monkeypatch):
    made = {}

    class Adapter:
        def __init__(self):
            self.calls = []

        def call(self, prompt="", *, model="", **kw):
            self.calls.append((prompt, model, kw))
            return types.SimpleNamespace(content="seen", success=True, error_history=None, input_tokens=1, output_tokens=1, cost_usd=0.0)

    def get_adapter(name, **kw):
        made[name] = Adapter()
        return made[name]
    mod = types.ModuleType("dd_llm")
    mod.get_adapter = get_adapter
    mod.model_compatible = lambda name, model: True
    monkeypatch.setitem(sys.modules, "dd_llm", mod)
    return made


def test_an_image_goes_to_an_adapter_that_takes_anthropic_messages_as_a_base64_block(fake_dd_llm):
    llm = DDLLM("anthropic")
    assert llm.generate("describe it", model="m", images=[("image/png", b"abc")]) == "seen"
    prompt, model, kw = fake_dd_llm["anthropic"].calls[0]
    content = kw["messages"][0]["content"]
    assert content[0] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "YWJj"}}
    assert content[1] == {"type": "text", "text": "describe it"}


def test_an_adapter_that_cannot_read_images_says_so_instead_of_dropping_them(fake_dd_llm):
    with pytest.raises(LLMUnavailable, match="cannot read images.*anthropic"):
        DDLLM("openai").generate("describe it", images=[("image/png", b"abc")])
    assert fake_dd_llm["openai"].calls == []                       # no call was made


def test_without_images_nothing_changes(fake_dd_llm):
    DDLLM("claude_cli").generate("plain", model="m")
    assert "messages" not in fake_dd_llm["claude_cli"].calls[0][2]


def test_claude_cli_gets_the_images_as_files_for_its_read_tool(monkeypatch):
    seen = {}

    class Result:
        success, content, error_history = True, "ok", None
        input_tokens = output_tokens = 0
        cost_usd = None

    class Fake:
        def __init__(self, **options):
            seen["options"] = options

        def call(self, prompt, model="", **kw):
            import re
            seen["prompt"] = prompt
            seen["files"] = {p: open(p, "rb").read() for p in re.findall(r"/\S+\.png", prompt)}
            return Result()
    fake = types.SimpleNamespace(get_adapter=lambda name, **options: Fake(**options))
    monkeypatch.setitem(sys.modules, "dd_llm", fake)
    llm = DDLLM("claude_cli")
    assert llm.generate("describe", images=[("image/png", b"PNG1")]) == "ok"
    assert seen["options"] == {"allowed_tools": ["Read"]} and seen["prompt"].endswith("describe")
    assert list(seen["files"].values()) == [b"PNG1"]
    import os
    assert not any(os.path.exists(p) for p in seen["files"])        # the temporary files are gone after the call
