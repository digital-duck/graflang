"""The four arms end to end on one task, with a fake `claude` command on PATH (no network, no model): every arm must
report the same two cycles (the first test fails, the second passes), the code each cycle tested, and comparable LLM calls.
Needs SPL.py importable (spl3), like the other procedure tests."""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

pytest.importorskip("spl3.executor")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "experiments" / "code_pipeline"))

FAKE_CLAUDE = r'''#!/usr/bin/env python3
# Fake `claude --print`: reads the prompt on stdin. A test prompt gets [FAILED] the first time it is seen in a run folder
# and [PASSED] after that; the code it writes says which step asked for it.
import os, sys
prompt = sys.stdin.read()
if "automated test suite" in prompt:
    marker = os.path.join(os.environ["FAKE_STATE"], "tests")
    n = int(open(marker).read()) if os.path.exists(marker) else 0
    open(marker, "w").write(str(n + 1))
    print("[FAILED]\n- wrong" if n == 0 else "[PASSED]")
elif "data-protection" in prompt:
    print('{"entities": []}')
elif "specification analyst" in prompt:
    print("[READY] clear")
elif "improving code" in prompt:
    print("def count_upper(s):\n    # improved\n    return sum(1 for ch in s if ch in 'AEIOU')\n")
elif "Write clean, correct" in prompt or "expert python developer" in prompt:
    print("def count_upper(s):\n    # generated\n    return 0\n")
else:
    print("ok")
'''


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    cli = bin_dir / "claude"
    cli.write_text(FAKE_CLAUDE)
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_STATE", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("arm", ["single", "spl", "graflang", "langgraph"])
def test_each_arm_reports_its_cycles_and_calls(arm, fake_claude, monkeypatch):
    pytest.importorskip("langgraph")
    import arms
    import tasks as T
    monkeypatch.setattr(arms, "ADAPTER", "claude_cli")
    folder = fake_claude / arm
    folder.mkdir()
    res = arms.ARMS[arm](T.spec_for(T.select(None, 0, "98")[0]), "fake-model", folder)
    assert res.status == "ok", res.status
    assert res.llm["calls"] >= 1 and res.llm["prompt_tokens"] > 0
    if arm == "single":
        assert [c["verdict"] for c in res.cycles_detail] == [""] and res.cycles == 1
        return
    assert [c["verdict"] for c in res.cycles_detail] == ["FAILED", "PASSED"], res.cycles_detail
    assert res.cycles == 2 and res.pipeline_verdict == "PASSED"
    assert res.cycles_detail[-1]["code"] == res.code                       # the last cycle tested the final code
    assert all("# improved" in c["code"] for c in res.cycles_detail)        # each cycle recorded the code it tested
    assert res.llm["calls"] == 11                                          # analyze + 2 x (generate, review, improve, test) + document + extract


@pytest.mark.parametrize("arm", ["graflang", "langgraph"])
def test_a_retry_carries_the_failed_attempt_and_the_improve_step_sees_the_spec(arm, fake_claude, monkeypatch):
    """The fix: the second attempt receives the first attempt's code and test result, and the improve step receives the
    specification (so it keeps the function name). Checked on the prompts each arm actually sent."""
    pytest.importorskip("langgraph")
    import arms
    import tasks as T
    monkeypatch.setattr(arms, "ADAPTER", "claude_cli")
    folder = fake_claude / arm
    folder.mkdir()
    spec = T.spec_for(T.select(None, 0, "98")[0])
    res = arms.ARMS[arm](spec, "fake-model", folder)
    assert res.cycles == 2
    if arm == "graflang":
        prompts = sorted((folder / "prompts").glob("*/coder_*.md"))
        texts = [p.read_text(encoding="utf-8") for p in prompts]
        first, second = texts[0], texts[1]
        assert "Previous attempt (empty on the first attempt):\n\n" in first        # no 'None' on the first attempt
        assert "# generated" not in second or "# improved" in second.split("Previous attempt")[1]
        assert "# improved" in second.split("Previous attempt")[1] and "[FAILED]" in second.split("Its test result")[1]
        improve = sorted((folder / "prompts").glob("*/refactor_*.md"))[0].read_text(encoding="utf-8")
        assert "Specification (the function name and signature must match it exactly)" in improve
        assert "count_upper" in improve.split("Specification")[1].split("Original code")[0]
    else:
        assert res.cycles_detail[0]["verdict"] == "FAILED" and res.cycles_detail[1]["verdict"] == "PASSED"


def test_a_renamed_function_fails_the_attempt_without_calling_the_tester_and_the_retry_is_told(fake_claude, monkeypatch):
    """The deterministic name check: the improve step renames the function on cycle 1; the attempt fails at once (the LLM
    tester is not called for it), and cycle 2 receives the fixed message as the failure it must repair."""
    import arms
    import tasks as T
    renamer = FAKE_CLAUDE.replace("def count_upper(s):\\n    # improved", "def renamed_fn(s):\\n    # improved")
    assert renamer != FAKE_CLAUDE
    cli = fake_claude / "bin" / "claude"
    cli.write_text(renamer)
    monkeypatch.setattr(arms, "ADAPTER", "claude_cli")
    folder = fake_claude / "graflang-rename"
    folder.mkdir()
    res = arms.ARMS["graflang"](T.spec_for(T.select(None, 0, "98")[0]), "fake-model", folder)
    assert res.cycles_detail[0]["code"].count("renamed_fn") == 1
    assert all(c["verdict"] == "FAILED" for c in res.cycles_detail) and res.cycles == 3   # the fake renames on every cycle
    assert sorted((folder / "prompts").glob("*/run_tests_*.md")) == []          # so the tester never saw a renamed attempt
    coder = sorted((folder / "prompts").glob("*/coder_*.md"))[-1].read_text(encoding="utf-8")
    assert "requires a function named `count_upper`" in coder                    # the retry is told what to repair
