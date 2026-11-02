=== pandera Schema Validator (r104) | solver=ON ===

## pandera Schema Report — EmployeePayroll_v1

**Dataset:** 200 rows  
**Status:** ✗ FAIL  
**Violations:** 3 column checks failed

| Column | Check | Failures | Sample Values |
|---|---|---|---|
| department | isin(['Engineering', 'Sales', 'HR', 'Finance', 'Operations']) | 4 | ['Temp', 'Temp', 'Temp'] |
| name | not_nullable | 3 | ['(null)', '(null)', '(null)'] |
| salary | greater_than(0) | 6 | [0.0, 0.0, 0.0] |

── Business Explanation ────────────────────────────────────
1. **Errors found:** 4 rows have department "Temp", which isn't an allowed value. 3 rows have a null employee name. 6 rows have a salary of 0.

2. **Likely causes:** "Temp" looks like a placeholder for contractors or unassigned hires that HR hasn't mapped to a real department. Null names suggest incomplete onboarding records or a failed join. Zero salaries are probably unset defaults, unpaid leave, or interns and contractors paid through another system.

3. **Highest priority:** Salary. Six zero values directly distort payroll totals, budgets, and tax calculations, and may mean employees go unpaid. The other two issues are mainly reporting and identity problems.

4. **Pipeline fix:** Run this pandera schema as a gate at ingestion. Quarantine failing rows instead of loading them. Make the source system require name, department, and salary at entry. Alert the data owner when rows are quarantined.