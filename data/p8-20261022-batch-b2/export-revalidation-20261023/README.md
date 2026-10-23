# Final export reconstruction validation

Final 900/900 passed, unchanged 1e-4 tolerance, no unmatched cycles. UTC+8 2026-10-23 18:29:33–18:37:42. See verification.json for exact historical command, hashes, counts and residuals; export.log is the full run log. Corrected portable exports are in ../../../export/ (repository root export/); original raw ULogs remain Thor-only under data/<run>/flight.ulg.

The first attempt (first-attempt-verification.json and first-attempt-export.log) failed on 108 T1 runs after the initial repair; it is preserved. Capture events were then distinguished from continuous T1 profile rows, and explicit read events restore the external source. Full 900 were revalidated. Five timing tests passed. No policy_input-based target selection, tolerance/failure-rule changes or flight reruns.

baseline.json and first-attempt-baseline.json contain historical absolute source paths and evidence hashes. Old results, all 900 metrics, audits, diagnoses and export-failure-scene were unchanged by revalidation. The old STOPPED export-diagnosis.json and b1-b2-summary.json are historical records; final-summary.json in the parent is the current closure summary. Original failed exports remain preserved in export-failure-scene; the first-attempt full exports remain only in the source workspace on Thor.

Existing batch audits were retained rather than rewritten: metric code and flight data were unchanged. Independent output validation and per-row primary/task comparison passed; see verification.json. No commit/push occurred during revalidation.
