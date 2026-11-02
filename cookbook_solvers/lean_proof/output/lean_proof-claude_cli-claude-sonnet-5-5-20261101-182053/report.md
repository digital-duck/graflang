# Lean verification report

**Claim (prose):** addition of natural numbers is commutative

**Formalization:** `∀ a b : Nat, a + b = b + a`

**Faithfulness (LLM judge):** FAITHFUL - It universally quantifies over all natural numbers a and b with no extra hypotheses, stating exactly a + b = b + a.

**Badge:** `machine_proved`

**Kernel-checked proof:**
```lean
theorem spl_claim : ∀ a b : Nat, a + b = b + a := by
  exact fun a b => Nat.add_comm a b
```

**Library search (exact?):** `exact fun a b => Nat.add_comm a b`