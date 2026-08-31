# LedgerGuard Reviewer-Revision Statistical Protocol

Status: frozen before reviewer-revision full aggregation

## Run Accounting

Preserve attempted, valid, excluded, failed, reverted, and rerun observations.
Never delete a slow or failed valid observation. A rerun receives a new run ID and
does not replace the original.

Allowed exclusions are container crash, corrupted log, incomplete environment
startup, invalid configuration, or interrupted execution. Each exclusion requires
the original evidence path and exact reason.

## Timing Statistics

For each operation and configuration report count, minimum, Q1, median, Q3,
maximum, IQR, mean, sample standard deviation, coefficient of variation, P90, and
P95 only when `n >= 50`.

Calculate 95% bootstrap confidence intervals for mean and median with 10,000
resamples and bootstrap seed `20260828`.

## Local Backend Comparison

For semantically comparable Besu and SQLite operations report median latency ratio,
median absolute difference, bootstrap confidence intervals for both, and Cliff's
delta. Describe this only as a local persistent-backend or governance-path
comparison.

## Block-Period Sensitivity

Report configured block period, submission-to-receipt latency, Spearman
correlation, median latency divided by block period, first-eligible-block fraction,
and later-block fraction. With three deterministic block-period configurations,
use descriptive analysis rather than a significance test.

## Fleet Statistics

For each fleet size, configured failure rate, and seed report median outcome rate,
IQR, minimum, maximum, mean, sample standard deviation, and 95% bootstrap confidence
interval. Do not infer monotonic scaling without dispersion support.

## Formula-Derived Results

Root count, transaction-count reduction, computed byte reduction, and Merkle proof
depth are analytical/configuration-dependent outputs. Do not apply significance
tests or describe them as measured database growth.
