"""Tests for the enhanced Cedar compiler."""

import pytest
from graphlang.grafc.cedar.lexer import CedarLexer
from graphlang.grafc.cedar.parser import CedarParser
from graphlang.grafc.cedar.compiler import CedarCompiler
from graphlang.grafc.cedar.errors import CedarLexError, CedarParseError


SIMPLE_POLICY = '''
permit(
    principal == User::"alice",
    action == Action::"read",
    resource == Document::"doc1"
);
'''

POLICY_WITH_CONDITION = '''
forbid(
    principal,
    action == Action::"delete",
    resource
) when {
    context.contains_pii == true
};
'''

COMPLEX_POLICY = '''
@id("safety-rule-1")
forbid(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.proposed_delta.action == "remove_node" &&
    context.proposed_delta.node_type in ["ASSERT", "SOLVE"]
};
'''


def test_lexer_simple():
    lexer = CedarLexer(SIMPLE_POLICY)
    tokens = lexer.tokenize()
    assert tokens[0].value == "permit"
    assert tokens[-1].value is None  # EOF


def test_parser_simple():
    lexer = CedarLexer(SIMPLE_POLICY)
    tokens = lexer.tokenize()
    parser = CedarParser(tokens)
    policy_set = parser.parse()
    assert len(policy_set.policies) == 1
    assert policy_set.policies[0].effect.value == "permit"


def test_compiler_simple():
    compiler = CedarCompiler()
    rust_code = compiler.compile(SIMPLE_POLICY)
    assert "pub fn evaluate" in rust_code
    assert "permit_0" in rust_code
    assert '"alice"' in rust_code


def test_compiler_with_condition():
    compiler = CedarCompiler()
    rust_code = compiler.compile(POLICY_WITH_CONDITION)
    assert "forbid_0" in rust_code
    assert "contains_pii" in rust_code


def test_compiler_complex():
    compiler = CedarCompiler()
    rust_code = compiler.compile(COMPLEX_POLICY)
    assert "forbid_0" in rust_code
    assert 'Policy: safety-rule-1' in rust_code
    assert '["ASSERT", "SOLVE"]' in rust_code or 'vec![' in rust_code


def test_lexer_error():
    with pytest.raises(CedarLexError):
        lexer = CedarLexer('permit("invalid')
        lexer.tokenize()


def test_parser_error():
    with pytest.raises(CedarParseError):
        lexer = CedarLexer('invalid_syntax')
        tokens = lexer.tokenize()
        parser = CedarParser(tokens)
        parser.parse()


def test_entity_hierarchy():
    policy = '''
    permit(
        principal in Group::"admins",
        action,
        resource
    );
    '''
    compiler = CedarCompiler()
    rust_code = compiler.compile(policy)
    assert "is_in" in rust_code
    assert '"admins"' in rust_code


def test_like_operator():
    policy = '''
    permit(principal, action, resource)
    when { principal.name like "admin*" };
    '''
    compiler = CedarCompiler()
    rust_code = compiler.compile(policy)
    assert "Regex" in rust_code or "regex" in rust_code


def test_has_attribute():
    policy = '''
    permit(principal, action, resource)
    when { context has sensitive_data };
    '''
    compiler = CedarCompiler()
    rust_code = compiler.compile(policy)
    assert "contains_key" in rust_code
