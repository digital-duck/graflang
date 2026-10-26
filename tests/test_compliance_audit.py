"""cookbook/compliance_audit: extract the PII, check deterministic rules, redact and re-check, release through a Cedar guard.

A stub LLM stands in for the model (no network): it finds SSNs and card numbers with regexes and redacts them, so every
path of the graph is exercised and the result does not depend on a model. The rule check is the real program
(procedures/compliance_check.py, run by a SOLVE node with backend: subprocess); no SPL.py is needed.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from graphlang.grafr.cedar_guard import CedarGuard
from graphlang.grafr.runtime import GraphLangRuntime, load_graph

EXAMPLE = Path(__file__).resolve().parent.parent / "cookbook" / "compliance_audit"
GRAPH = EXAMPLE / "compliance_audit.graph.yaml"
SSN_LABELLED = re.compile(r"SSN\s*\d{3}-\d{2}-\d{4},?\s*")
SSN, CARD = re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{4}\b")

CLEAN = "Quarterly note: the office moves to the third floor in March."
WITH_SSN = "Customer John Doe, SSN 123-45-6789, asks to update his address."
WITH_CARD = "Please charge card 4111-1111-1111-1111 for the renewal."


class StubLLM:
    """Plays the model. `redacts=False` is a model that fails to remove the SSN."""
    name, adapter_name, model_override = "stub", "echo", None

    def __init__(self, redacts: bool = True):
        self.redacts, self.calls = redacts, []

    def generate(self, prompt: str, model=None, **opts) -> str:
        document = prompt.split("DOCUMENT:\n", 1)[1]
        if "data-protection analyst" in prompt:                                  # extract_pii
            self.calls.append("extract")
            entities = [{"type": "SSN", "masked": False}] * bool(SSN.search(document))
            entities += [{"type": "CCN", "masked": False}] * bool(CARD.search(document))
            entities += [{"type": "CCN", "masked": True}] * ("[REDACTED]" in document)
            return json.dumps({"entities": entities})
        self.calls.append("redact")                                              # redact
        if not self.redacts:
            return document
        return CARD.sub("[REDACTED]", SSN_LABELLED.sub("", document)).strip()


def run(document, destination, engine="stdlib", llm=None, rules_file=""):
    llm = llm or StubLLM()
    runtime = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False)
    return runtime.execute({"document": document, "destination": destination, "engine": engine, "rules_file": rules_file}), llm


ENGINES = ["stdlib", "sympy", "z3"]


def need(engine):
    from importlib.util import find_spec
    if engine != "stdlib" and find_spec("z3" if engine == "z3" else "sympy") is None:
        pytest.skip(f"{engine} is not installed")


@pytest.mark.parametrize("engine", ENGINES)
def test_a_clean_document_is_released_untouched(engine):
    need(engine)
    out, llm = run(CLEAN, "external_api", engine)
    assert out["safe_document"] == CLEAN and out["audit"] == f"released to external_api ({engine} engine)"
    assert llm.calls == ["extract"]                                              # no redaction was needed


@pytest.mark.parametrize("engine", ENGINES)
def test_an_ssn_for_an_external_api_is_redacted_rechecked_and_released(engine):
    need(engine)
    out, llm = run(WITH_SSN, "external_api", engine)
    assert "123-45-6789" not in out["safe_document"] and "SSN" not in out["safe_document"]
    assert out["audit"].startswith("released to external_api")
    assert llm.calls == ["extract", "redact", "extract"]                         # extract, fix, prove the fix


def test_the_same_ssn_stays_put_when_the_destination_is_internal():
    out, llm = run(WITH_SSN, "internal_db")
    assert out["safe_document"] == WITH_SSN and llm.calls == ["extract"]


def test_a_card_number_is_masked_even_for_an_internal_destination():
    out, llm = run(WITH_CARD, "internal_db")                                     # R3: card numbers are always masked
    assert "4111" not in out["safe_document"] and "[REDACTED]" in out["safe_document"]
    assert llm.calls == ["extract", "redact", "extract"]


def test_a_redaction_that_fails_ends_at_escalated_and_nothing_is_released():
    out, llm = run(WITH_SSN, "external_api", llm=StubLLM(redacts=False))
    assert "safe_document" not in out                                            # no document leaves
    assert out["audit"].startswith("ESCALATED to a human reviewer") and "R2" in out["audit"]


def test_a_model_reply_that_is_not_json_fails_closed():
    class Garbled(StubLLM):
        def generate(self, prompt, model=None, **opts):
            return "Sure! Here is the list: SSN and phone number."
    out, _ = run(CLEAN, "internal_db", llm=Garbled())
    assert "safe_document" not in out and "UNREADABLE_PII_MAP" in out["audit"]   # never 'no PII found'


def test_the_graph_shows_up_in_the_trace_as_expected_nodes():
    runtime = GraphLangRuntime(load_graph(GRAPH), llm=StubLLM(), verbose=False)
    runtime.execute({"document": WITH_SSN, "destination": "external_api", "engine": "stdlib", "rules_file": ""})
    fired = [n for n, count in runtime.fired.items() if count]
    assert {"extract_pii", "check", "redact", "extract_again", "recheck", "release_guard", "released"} <= set(fired)
    assert "escalated" not in fired


# ---- the Cedar guard on its own ------------------------------------------------------------------------------------

POLICY = (EXAMPLE / "policies" / "release_policy.cedar").read_text(encoding="utf-8")
REQUEST = ('Service::"compliance-workflow"', 'Action::"release_document"', 'Destination::"target"')


def decide(context):
    guard = CedarGuard()
    guard.load_policy("p", POLICY)
    return guard.decide("p", *REQUEST, context)


def test_the_policy_permits_a_compliant_release_and_refuses_the_rest():
    assert decide({"compliant": True, "is_external": True}).allowed
    assert decide({"compliant": True, "is_external": False}).allowed
    assert not decide({"compliant": False, "is_external": True}).allowed
    assert not decide({"compliant": False, "is_external": False}).allowed          # default deny: no permit applies


def test_the_policy_fails_closed_when_the_context_is_incomplete():
    assert not decide({}).allowed
    assert not decide({"is_external": True}).allowed
    assert not decide({"compliant": "yes", "is_external": False}).allowed          # a non-boolean never counts as compliant


def test_the_policy_has_no_catch_all_forbid():
    assert not re.search(r"forbid\s*\(\s*principal\s*,\s*action\s*,\s*resource\s*\)\s*;", POLICY)


# ---- the check program on its own ----------------------------------------------------------------------------------

CHECK = EXAMPLE / "procedures" / "compliance_check.py"


def check_program(inputs):
    return subprocess.run([sys.executable, "-I", str(CHECK)], input=json.dumps(inputs), capture_output=True, text=True)


def test_the_check_program_prints_the_verdict_as_one_json_line():
    run_ = check_program({"pii_map": '{"entities": [{"type": "SSN"}]}', "destination": "external_api", "engine": "stdlib"})
    verdict = json.loads(run_.stdout)
    assert run_.returncode == 0 and len(run_.stdout.strip().splitlines()) == 1
    assert verdict["compliant"] is False and verdict["violated"] == ["R1", "R2"]


def test_the_check_program_exits_1_with_the_reason_when_it_cannot_run(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ nope", encoding="utf-8")
    run_ = check_program({"pii_map": "{}", "destination": "x", "engine": "stdlib", "rules_file": str(bad)})
    assert run_.returncode == 1 and run_.stdout == "" and "not valid JSON" in run_.stderr
    run_ = check_program({"pii_map": '{"entities": []}', "destination": "x", "engine": "magic"})
    assert run_.returncode == 1 and "unknown engine" in run_.stderr


def test_the_example_does_not_depend_on_spl():
    data = load_graph(GRAPH)
    assert not any("procedure_ref" in n.get("config", {}) for n in data["nodes"])
    assert "procedures" not in data.get("resources", {})
    assert not list((EXAMPLE / "procedures").glob("*.spl"))
    imports = [line for line in (EXAMPLE / "procedures" / "tools.py").read_text(encoding="utf-8").splitlines()
               if line.startswith(("import ", "from "))]
    assert not any("spl" in line for line in imports)


# ---- your own rules --------------------------------------------------------------------------------------------------

def test_a_rules_file_input_replaces_the_default_rules(tmp_path):
    rules = json.loads((EXAMPLE / "procedures" / "rules.json").read_text(encoding="utf-8"))
    rules["rules"] = [r for r in rules["rules"] if r["id"] != "R2"]               # an SSN may now go out if it is masked
    path = tmp_path / "mine.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    runtime = GraphLangRuntime(load_graph(GRAPH), llm=StubLLM(redacts=False), verbose=False)
    out = runtime.execute({"document": WITH_SSN, "destination": "external_api", "engine": "stdlib", "rules_file": str(path)})
    assert "ESCALATED" in out["audit"] and "R1" in out["audit"] and "R2" not in out["audit"]


def test_a_bad_rules_file_stops_the_run_instead_of_falling_back_to_the_defaults(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ nope", encoding="utf-8")
    with pytest.raises(Exception, match="not valid JSON"):                       # the check program exits 1; nothing is released
        run(CLEAN, "internal_db", rules_file=str(path))


def test_validate_proves_the_release_is_only_reachable_through_the_guard():
    from graphlang.grafr.topology import check
    data = load_graph(GRAPH)
    assert check(data)[0] == []
    data["edges"].append({"source": "compliant_first.pass", "target": "audit_released.trigger", "type": "triggers"})
    data["nodes"] = [{**n, "config": {**n["config"], "risky": True}} if n["id"] == "audit_released" else n for n in data["nodes"]]
    assert any("'audit_released' is risky but can run without passing a GUARD" in m for m in check(data)[0])
