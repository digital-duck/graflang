=== Z3 Compliance Checker (r102) | solver=ON ===

## Z3 Eligibility Check — QuickLoan Eligibility Policy v2.1

**Status:** SAT  
**Verdict:** Policy is satisfiable — a qualifying customer profile exists
**Rules checked:** 5

### Qualifying Profile Found by Z3

| Variable | Value |
|---|---|
| age | 18 |
| income | 0 |
| credit_score | 650 |
| months_employed | 0 |
| has_collateral | True |
| self_employed | False |

── Business Explanation ────────────────────────────────────
**1. What Z3 found:** Z3 confirmed the five rules can all be satisfied at once. It produced a concrete applicant who passes every rule: age 18, income $0, credit score 650, no months employed, has collateral, not self-employed.

**2. Business meaning:** The rules are consistent, not contradictory. At least one kind of customer can qualify, so the policy isn't accidentally rejecting everyone.

**3. What's notable:** The sample applicant has zero income and zero employment history. Collateral alone satisfies both the income rule (R2) and the employment rule (R5). So the policy approves someone with no income at all, as long as they have collateral and a 650 credit score. That is probably worth a business review: no rule requires any ability to repay.

**4. Risk of manual tracing:** People checking rules by hand tend to test typical profiles and miss edge cases like this one. They can also miss subtle contradictions between rules when policies grow larger. Z3 checks the whole space of possible applicants, so it finds gaps and conflicts that spot checks can't.