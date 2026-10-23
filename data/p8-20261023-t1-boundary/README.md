# Exploratory T1 boundary validation

24/24 new headless x500 SITL simulations completed 2026-10-23 19:29:15–20:02:24 UTC+8. No reruns. All infrastructure checks valid; 20 primary/task failures. No remote desktop sessions, maximum applied output age 8 ms. Controller/model/metrics unchanged; original 900 results and metrics hashes unchanged.

Plan and full original row records: plan.json. Code/Lab/binary identity: candidate.json. Git HEAD, original dirty status and binary diff fingerprint: fingerprints.json and preexisting-worktree.patch. Exact commands, times, checks, seeds and outcomes: results.json. Raw flight.ulg, configs, events, safety logs and metrics: runs/<run id>/. batch.log records all start/end events. Driver: boundary.py. Summary and limitations: summary.json.

Baseline primary/task failure counts: contest-T1-s1-k20 3/3; contest-T1-s0-k27 2/3; ours-T1-s0-k21 2/3; ours-T1-s0-k01 3/3. Twelve distinct SHA256-derived simulator seeds; perturbations reuse the same three seeds per case.

Only first restored interval perturbed +/-0.05 s for contest-T1-s1-k20 (0.08/0.13/0.18 s) and ours-T1-s0-k01 (0.06/0.11/0.16 s). Pre/post budget 1/3 s unchanged. Contest failures: 3/3, 3/3, 1/3; ours: 3/3 in all groups. +0.05 s reduced peak tilt for each of the three paired seeds in both cases, but only contest crossed the failure threshold in two seeds.

Important design limitation: negative variants are below the original P8 generator minimum restored interval of 0.1 s. They are runner/safety-budget-valid, independent exploratory inputs, not additions to the original frozen comparison domain. Baselines and positive variants remain in domain. This was identified during final design review, is explicitly retained in the record, and no extra runs were added to replace these cases. Do not interpret negative variants as validating original-domain method coverage.

Inference: some original one-off outcomes are seed-sensitive; within-domain +0.05 s timing changes can move a case across the threshold. Only 3 seeds per input, wall-clock scheduling remains a nuisance. This supports studying recovery-interval coverage, not retuning or claiming a method-ranking change. No real hardware, core-code changes, formal-report edits, commit or push.
