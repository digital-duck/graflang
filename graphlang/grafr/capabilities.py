"""An organisation's rules for what a workflow may contain, written in Cedar and checked before anything runs (design E8).

A workflow names the policy in its header: `workflow: {name: ..., policy: policies.org}`. For every node (LOOP and BATCH bodies
included) `graf validate` and `graf run` ask Cedar whether `Workflow::"<name>"` may do `Action::"run_node"` on `Node::"<id>"`, with
this context:

    type       the node type                       "RUN", "GENERATE", ...
    risky      true for EMIT, QUERY and `risky: true`
    needs      the node's `config.needs`, a list of capability names you choose ("network", "fs_write", "shell", ...)
    executor   "http", "subprocess", "python", or "" (a SOLVE's `backend` counts)
    host       the host of an http RUN, else ""

so a policy can say "nothing may need `shell`", "an http RUN may only call these hosts" or "a node that needs a capability must be
risky (and so sits behind a GUARD)". It is the static counterpart of a GUARD, which asks the same engine at run time.
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List
from urllib.parse import urlparse

from .cedar_guard import CedarGuard, PolicyError
from .resolver import ResourceResolver
from .topology import _risky

PRINCIPAL, ACTION = 'Workflow::"{name}"', 'Action::"run_node"'


def _nodes(nodes: List[Dict], prefix: str = "") -> Iterator[tuple]:
    for n in nodes:
        yield prefix + n["id"], n
        body = n.get("config", {}).get("subgraph")
        if isinstance(body, dict):
            yield from _nodes(body.get("nodes", []), f"{prefix}{n['id']}/")


def node_context(node: Dict) -> Dict[str, Any]:
    cfg = node.get("config", {})
    executor = cfg.get("executor") or cfg.get("backend") or ""
    return {"type": node["type"], "risky": _risky(node), "needs": [str(x) for x in cfg.get("needs", [])], "executor": executor,
            "host": (urlparse(cfg.get("url", "")).hostname or "") if executor == "http" else ""}


def capability_errors(graph_data: Dict[str, Any], resolver: ResourceResolver) -> List[str]:
    """One message per node the workflow's policy does not allow; empty when the workflow names no policy."""
    ref = graph_data["workflow"].get("policy")
    if not ref:
        return []
    try:
        guard = CedarGuard()
        guard.load_policy(ref, resolver.resolve(ref, "policies")["content"])
    except (PolicyError, KeyError, OSError, ValueError) as e:
        return [f"workflow policy {ref!r}: {e}"]
    errors = []
    for qualified, node in _nodes(graph_data["nodes"]):
        decision = guard.decide(ref, PRINCIPAL.format(name=graph_data["workflow"]["name"]), ACTION, f'Node::"{qualified}"', node_context(node))
        if not decision.allowed:
            errors.append(f"{node['type']} {qualified!r} is not allowed by {ref}: {decision.explain()}")
    return errors
