# Raw data locality and portable records

Repository records are in runs/<run id>/. plan.json/results.json use repository-relative paths. original-plan.json/original-results.json retain the exact historical local paths and commands; these are provenance, not portable entry points.

The 24 original flight.ulg, gz-motor, telemetry/resources and rootfs/cli remain only on Thor under /home/car/Documents/Codex/2026-10-22/task/p8-t1-boundary-20261023/runs/. They are intentionally excluded by the repository data policy. metadata.json records original ULog hashes. Reproducing raw analysis requires those local files; the remote repository does not contain full raw data.

The original full dirty worktree diff stays only in the source directory (preexisting-worktree.patch); fingerprints.json records its SHA-256. The scoped publication diff is reviewable in Git. This avoids duplicating unrelated source/history content in the exploration evidence.
