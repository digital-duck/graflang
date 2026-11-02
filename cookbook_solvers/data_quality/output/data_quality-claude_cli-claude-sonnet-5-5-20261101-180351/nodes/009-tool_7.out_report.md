=== Data Quality Validator (r103) | solver=ON ===

## Data Quality Report — SalesTransactions_v1

**Dataset:** 500 rows  
**Expectations:** 10 total  
**Passed:** 6  
**Failed:** 4  
**Status:** ✗ FAIL

| Expectation | Column | Status | Failures |
|---|---|---|---|
| expect_column_to_exist | transaction_id | PASS | |
| expect_column_to_exist | amount | PASS | |
| expect_column_to_exist | customer_id | PASS | |
| expect_column_to_exist | region | PASS | |
| expect_column_values_to_be_unique | transaction_id | FAIL (4 rows, 0.8%) | |
| expect_column_values_to_not_be_null | transaction_id | PASS | |
| expect_column_values_to_not_be_null | customer_id | FAIL (8 rows, 1.6%) | |
| expect_column_values_to_not_be_null | amount | PASS | |
| expect_column_values_to_be_between | amount | FAIL (12 rows, 2.4%) samples=[-234.82, -479.91, -328.99] | |
| expect_column_values_to_be_in_set | region | FAIL (3 rows, 0.6%) values=['Unknown'] | |

── Business Explanation ────────────────────────────────────
**1. Issues found**
- 4 duplicate transaction IDs (0.8%)
- 8 missing customer IDs (1.6%)
- 12 negative amounts (2.4%)
- 3 regions labeled "Unknown" (0.6%)

**2. Likely causes**
- Duplicates: POS retries or double-uploads during import.
- Missing customers: guest checkouts or loyalty cards not scanned.
- Negative amounts: refunds or returns recorded as sales rows (the samples look like genuine refund values).
- Unknown region: terminals missing store-to-region mapping.

**3. Most urgent**
Duplicate transaction IDs. They break the table's primary key and can inflate revenue, and they undermine joins and deduplication.

**4. Downstream impact**
- Duplicates: overstated revenue and transaction counts.
- Missing customers: understated customer counts and broken lifetime-value or retention analysis.
- Negative amounts: understated net sales if treated as errors, or distorted averages if mixed with sales.
- Unknown region: regional totals don't sum to the overall total, skewing regional comparisons.

Negative amounts are likely legitimate refunds, so rather than deleting them, add a transaction-type column and adjust the expectation.