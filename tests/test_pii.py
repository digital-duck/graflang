"""has_pii: a deterministic detector for what has a recognisable shape, usable in a GUARD's context_mapping."""
import pytest

from graphlang.grafr.expr import evaluate
from graphlang.grafr.pii import find_pii, has_pii
from graphlang.grafr.runtime import GraphLangRuntime

POLICY = '''forbid(principal == Service::"llm-agent", action == Action::"generate", resource == Model::"public-api")
when { context.contains_pii == true };
permit(principal, action, resource);
'''


@pytest.mark.parametrize("text, kind", [
    ("write to jane.doe+x@example.co.uk now", "email"),
    ("my ssn is 123-45-6789", "ssn"),
    ("card 4111 1111 1111 1111 expires soon", "card"),
    ("call +1 415-555-0132 tomorrow", "phone"),
    ("pay to DE89 3704 0044 0532 0130 00", "iban"),
])
def test_what_has_a_shape_is_found(text, kind):
    assert kind in {k for k, _ in find_pii(text)} and has_pii(text)


@pytest.mark.parametrize("text", [
    "", "The quick brown fox", "version 1.2.3 released on 2026-10-30", "order 4111 1111 1111 1112 failed the checksum",
    "000-12-3456 is not a valid ssn", "x@y", "ratio 3.14159 and 100,000 units", None, 42,
])
def test_ordinary_text_is_clean(text):
    assert not has_pii(text)


def test_values_are_looked_at_as_text():
    assert has_pii({"contact": {"email": "a@b.com"}}) and not has_pii({"n": 1, "ok": True})
    assert evaluate("has_pii(@x)", {"x": "mail me at a@b.com"}) is True


def guard_graph(text_port_value):
    guard = {"id": "g", "type": "GUARD", "ports": ["trigger", "allow", "deny", "in_text"],
             "config": {"policy_ref": "policies.p", "principal": 'Service::"llm-agent"', "action": 'Action::"generate"',
                        "resource": 'Model::"public-api"', "context_mapping": {"contains_pii": "has_pii(@in_text)"}}}
    return {"version": "1.0-graph", "resources": {"policies": {"p": "./p.cedar"}},
            "workflow": {"name": "t", "inputs": [{"name": "text", "type": "TEXT"}], "outputs": [{"name": "r", "type": "TEXT"}]},
            "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry", "out_text"]}, guard,
                      {"id": "yes", "type": "SOLVE", "ports": ["trigger", "complete", "out_r"], "config": {"expression": "'sent'"}},
                      {"id": "no", "type": "SOLVE", "ports": ["trigger", "complete", "out_r"], "config": {"expression": "'blocked'"}},
                      {"id": "o", "type": "OUTPUT", "ports": ["trigger", "in_r"]}],
            "edges": [{"source": "s.entry", "target": "g.trigger", "type": "triggers"},
                      {"source": "s.out_text", "target": "g.in_text", "type": "binds"},
                      {"source": "g.allow", "target": "yes.trigger", "type": "triggers"},
                      {"source": "g.deny", "target": "no.trigger", "type": "triggers"},
                      {"source": "yes.out_r", "target": "o.in_r", "type": "binds"}, {"source": "no.out_r", "target": "o.in_r", "type": "binds"},
                      {"source": "yes.complete", "target": "o.trigger", "type": "triggers"}, {"source": "no.complete", "target": "o.trigger", "type": "triggers"}]}


def test_a_guard_blocks_personal_data_from_a_public_model(tmp_path):
    (tmp_path / "p.cedar").write_text(POLICY)
    g = guard_graph(None)
    g["_source_dir"] = str(tmp_path)
    assert GraphLangRuntime(g, verbose=False).execute({"text": "my ssn is 123-45-6789"}) == {"r": "blocked"}
    assert GraphLangRuntime(g, verbose=False).execute({"text": "tides are caused by the moon"}) == {"r": "sent"}
