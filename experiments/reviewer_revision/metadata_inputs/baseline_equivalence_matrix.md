# Baseline Semantic-Equivalence Audit

The reviewer-revision baseline is a loopback HTTP service backed by a durable
SQLite WAL database. It enforces authenticated actors, active roles, distinct
threshold approvals, rollout phase/nonces, kill-switch checks, completeness-aware
outcome counters, independent witness confirmation, and append-only audit guards.

Direct timing comparisons are restricted to six common application operations:

- release registration;
- security approval;
- regulator approval;
- rollout start;
- outcome-summary proposal;
- outcome-summary confirmation.

`register_cohort` is separate on Besu but atomic with summary context in the
baseline, so it is excluded. Baseline audit reconstruction is excluded because
the repeated Besu run did not capture a matched event-readback observation.

The baseline does not emulate multi-party consensus or replicated tamper-evident
history. These remain DLT-specific properties and are not included in the local
governance-path latency ratio. The full row-level treatment is recorded in
`baseline_equivalence_matrix.csv`.
