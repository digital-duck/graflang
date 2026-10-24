"""Cedar policy evaluation for GUARD and MUTATE nodes, using the official Cedar engine (cedarpy).

Fail closed: a request is allowed only if Cedar says Allow *and* evaluating the policies raised no
error. Cedar skips a policy that errors (for example a `forbid` that reads a context attribute that
is not there), so an error is how a forbid silently stops applying; treating errors as Deny closes
that hole. Callers must therefore pass every attribute the policies read.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

import cedarpy


class PolicyError(ValueError):
    """The policy text is not valid Cedar."""


@dataclass
class Decision:
    allowed: bool
    reasons: List[str] = field(default_factory=list)      # ids of the policies that decided
    errors: List[str] = field(default_factory=list)       # evaluation errors (any error means deny)

    def explain(self) -> str:
        if self.errors:
            return "denied: policy evaluation error: " + "; ".join(self.errors)
        if self.allowed:
            return "allowed by " + (", ".join(self.reasons) or "policy")
        return "denied by " + (", ".join(self.reasons) if self.reasons else "default (no policy permits it)")


def entity_uid(text: str) -> str:
    """Accept `Action::allow_retry` as well as `Action::"allow_retry"`; return the quoted Cedar form."""
    m = re.fullmatch(r'([A-Za-z_][\w:]*)::"?([^"]+)"?', text.strip())
    if not m:
        raise ValueError(f"not an entity id: {text!r} (expected Type::\"name\")")
    return f'{m.group(1)}::"{m.group(2)}"'


class CedarGuard:
    """Holds policy sets by reference name and evaluates requests against them."""

    def __init__(self) -> None:
        self.policies: Dict[str, str] = {}

    def load_policy(self, policy_ref: str, policy_content: str) -> None:
        try:
            cedarpy.format_policies(policy_content)          # parses; raises on invalid Cedar
        except Exception as e:
            raise PolicyError(f"policy {policy_ref!r} is not valid Cedar: {e}") from None
        self.policies[policy_ref] = policy_content

    def decide(self, policy_ref: str, principal: str, action: str, resource: str,
               context: Dict[str, Any]) -> Decision:
        if policy_ref not in self.policies:
            raise KeyError(f"policy {policy_ref!r} is not loaded")
        request = {"principal": entity_uid(principal), "action": entity_uid(action),
                   "resource": entity_uid(resource), "context": context}
        result = cedarpy.is_authorized(request, self.policies[policy_ref], [])
        errors = list(getattr(result.diagnostics, "errors", []) or [])
        reasons = list(getattr(result.diagnostics, "reasons", []) or [])
        allowed = result.decision == cedarpy.Decision.Allow and not errors
        return Decision(allowed, reasons, errors)

    def evaluate(self, policy_ref: str, principal: str, action: str, resource: str, context: Dict[str, Any]) -> bool:
        return self.decide(policy_ref, principal, action, resource, context).allowed
