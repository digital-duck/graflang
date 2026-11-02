# Text-to-SQL with Data-Quality Gates Report

**Question:** What is the average order amount for customers in the Enterprise segment?

**Verifier status:** `OK`
**Rows returned:** `1`
**Referential integrity:** `True`
**Two-independent-ways stat agreement:** `True` (AVG=6000.0, SUM/COUNT=6000.0)
**Row-level round-trip vs ground truth:** `match`

## Interpretation

**Interpretation**

1. **Question:** What is the average order amount for customers in the Enterprise segment?

2. **Answer:** The verified result is a single row, `rows_llm: [[6000.0]]`, in the column `avg_order_amount`. Enterprise customers' orders average **6,000.00**. The independent ground-truth query returned the same `[[6000.0]]`, so `row_match` is true.

3. **Why the checks matter:** Referential integrity (`referential_ok: true`) confirms the orders join correctly to real Enterprise customers, with no orphaned or dropped records. The two-way check (`stat_a` and `stat_b` both 6000.0) shows that two structurally different calculations agree, so the number does not depend on one possibly flawed query.

Final answer: verified

## Generated SQL (LLM)

```sql
SELECT AVG(o.amount) AS avg_order_amount
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE c.segment = 'Enterprise'
```