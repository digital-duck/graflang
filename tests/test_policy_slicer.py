"""Tests for policy slicing."""

import pytest
from graphlang.grafc.cedar.lexer import CedarLexer
from graphlang.grafc.cedar.parser import CedarParser
from graphlang.grafc.cedar.slicer import PolicySlicer, GuardNodeConfig


MULTI_POLICY = '''
@id("retry-policy")
forbid(
    principal == Service::"llm-agent",
    action == Action::"allow_retry",
    resource == Graph::"execution_topology"
) when {
    context.mutation_count >= context.max_allowed_mutations
};

@id("pii-policy")
forbid(
    principal == Service::"llm-agent",
    action == Action::"generate",
    resource == Model::"public-api"
) when {
    context.contains_pii == true
};

@id("mutate-policy")
forbid(
    principal == Service::"llm-agent",
    action == Action::"mutate_graph",
    resource == Graph::"execution_topology"
) when {
    context.proposed_delta.action == "remove_node"
};

permit(
    principal == Service::"llm-agent",
    action == Action::"allow_retry",
    resource == Graph::"execution_topology"
) when {
    context.human_approval == true
};
'''


def test_slice_by_action():
    """Test slicing by action scope."""
    lexer = CedarLexer(MULTI_POLICY)
    tokens = lexer.tokenize()
    parser = CedarParser(tokens)
    policy_set = parser.parse()
    
    slicer = PolicySlicer(policy_set)
    
    # Guard node with action="allow_retry"
    guard_config = GuardNodeConfig(
        node_id="loop_guard",
        config={
            'action': 'Action::"allow_retry"',
            'principal': 'Service::"llm-agent"',
            'resource': 'Graph::"execution_topology"',
        }
    )
    
    sliced = slicer.slice_for_guard(guard_config)
    
    # Should include retry-policy and the permit policy
    assert len(sliced.policies) == 2
    assert any(p.annotations[0].value == "retry-policy" for p in sliced.policies if p.annotations)


def test_slice_by_principal():
    """Test slicing by principal scope."""
    lexer = CedarLexer(MULTI_POLICY)
    tokens = lexer.tokenize()
    parser = CedarParser(tokens)
    policy_set = parser.parse()
    
    slicer = PolicySlicer(policy_set)
    
    # Guard node with different principal
    guard_config = GuardNodeConfig(
        node_id="user_guard",
        config={
            'action': 'Action::"read"',
            'principal': 'User::"alice"',
            'resource': 'Graph::"execution_topology"',
        }
    )
    
    sliced = slicer.slice_for_guard(guard_config)
    
    # Should include no policies (no match)
    assert len(sliced.policies) == 0


def test_slice_stats():
    """Test slice statistics."""
    lexer = CedarLexer(MULTI_POLICY)
    tokens = lexer.tokenize()
    parser = CedarParser(tokens)
    policy_set = parser.parse()
    
    slicer = PolicySlicer(policy_set)
    
    guard_config = GuardNodeConfig(
        node_id="loop_guard",
        config={
            'action': 'Action::"allow_retry"',
        }
    )
    
    stats = slicer.get_slice_stats(guard_config)
    
    assert stats['total_policies'] == 4
    assert stats['sliced_policies'] == 2
    assert stats['reduction_percent'] == 50.0
    assert stats['forbid_count'] == 1
    assert stats['permit_count'] == 1


def test_slice_by_context_keys():
    """Test slicing by context key usage."""
    lexer = CedarLexer(MULTI_POLICY)
    tokens = lexer.tokenize()
    parser = CedarParser(tokens)
    policy_set = parser.parse()
    
    slicer = PolicySlicer(policy_set)
    
    # Guard node that uses contains_pii context key
    guard_config = GuardNodeConfig(
        node_id="pii_guard",
        config={
            'action': 'Action::"generate"',
            'context_mapping': {'contains_pii': 'check_pii(@data)'},
        }
    )
    
    sliced = slicer.slice_for_guard(guard_config)
    
    # Should include pii-policy
    assert len(sliced.policies) >= 1
    assert any(p.annotations[0].value == "pii-policy" for p in sliced.policies if p.annotations)
