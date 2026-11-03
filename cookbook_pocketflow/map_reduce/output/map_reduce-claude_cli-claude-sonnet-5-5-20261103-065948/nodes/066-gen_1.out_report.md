# Executive Candidate Screening Report

**Status: no screening results available.** The upstream pipeline returned no candidate data, so this report cannot be populated. I have not estimated or invented any figures.

## 1. Overview

| Metric | Value |
|---|---|
| Candidates screened | 0 |
| Qualified | 0 |
| Rejected | 0 |
| Qualification rate | N/A (no denominator) |

Score statistics (average, min, max) are all N/A. The ranking step failed with "no candidates to rank."

## 2. Top 3 Candidates

Not available. There are no scored candidates to rank.

## 3. Qualification Patterns

Not available. No candidates were classified as qualified or rejected, so there are no strengths or gaps to report.

## 4. Recommended Next Steps

1. **Do not proceed to interviews on this output.** There is no shortlist to act on.
2. **Diagnose the empty input (1-2 days).** Likely causes:
   - The candidate source (ATS export, file, or query) was empty or filtered out everyone.
   - The scoring step failed or timed out, so scores never reached the ranker.
   - Data was not passed between pipeline stages, for example a field-name mismatch or a failed handoff.
3. **Re-run the screening** once the cause is fixed, and confirm that the total count is greater than zero before ranking.
4. **Resume the normal timeline** after a successful run. Interview shortlisting can follow within the usual window.

## 5. Methodology

The intended process is an LLM-based evaluation that scores each candidate against role criteria, applies a qualification threshold, and then ranks and classifies. The score threshold and model used were not included in the inputs, so I can't state them. Because no candidates reached the scoring stage, no evaluation took place.

## Action Required

Please provide the candidate data or the pipeline logs, and I can regenerate the full report. If the screening ran through a graph workflow, the run log (`~/.graflang/logs`) would show which node produced the empty result.