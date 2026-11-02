=== Insurance Policy Z3 Inference (r120) | solver=ON ===

## Z3 Inference Report — ComprehensiveAuto_v3

**Query:** `emergency_claim`  
**Customers:** 3  
**Eligible:** 1

| Customer | Eligible | Z3 Proved | Missing / Blocking |
|---|---|---|---|
| alice | ✓ | has_comprehensive, policy_active, deductible_met, emergency_event, claim_covered, eligible_claim, emergency_claim | — |
| bob | ✗ | — | eligible_claim (blocked by: has_comprehensive, policy_active, claim_covered); emergency_event |
| carol | ✗ | has_comprehensive, policy_active, catastrophic_event, claim_covered, eligible_claim | emergency_event |

── Z3 Explanation ───────────────────────────────────────────
**1. Denied customers**
- **Bob:** Not eligible. The machine-listed blockers are `has_comprehensive`, `policy_active`, and `claim_covered`, which block `eligible_claim`. `emergency_event` is also missing.
- **Carol:** `eligible_claim` is proved, but `emergency_event` is missing, so `emergency_claim` cannot be derived. She has `catastrophic_event`, but no stated rule makes it imply `emergency_event`.

**2. Alice qualifies**
Z3 proved the full chain: `has_comprehensive`, `policy_active`, `deductible_met`, `emergency_event`, `claim_covered`, `eligible_claim`, and then `emergency_claim`. Nothing is missing.

**3. Formal verification vs. LLM rule-tracing**
Z3 applies the closed-world assumption strictly: an unstated fact is false. An LLM might approve Carol because "catastrophic" sounds like "emergency". Z3 does not, and it lists the exact missing predicate. This makes the result deterministic and auditable. A gap in the rules shows up as a denial that a human can then review and fix.