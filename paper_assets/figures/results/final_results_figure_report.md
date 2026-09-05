# Final Results Figure Report

**Overall status:** PASS

## Files Created

Seven main figures in PDF, SVG, and 600 dpi PNG; thirteen individual panels in the same formats; plot-data CSVs; metadata sidecars; a contact sheet; LaTeX integration; inventory; and validation reports.

## Figure Sources

| Figure | Source sheets | Source files | Rows | Statistic |
|---|---|---|---:|---|
| `fig_results_block_period_sensitivity` | Block Period Raw, Block Period Summary | `results/reviewer_revision/csv/block_period_sensitivity.csv` | 90 | All observations with box summaries; no P95 reported for n=30 |
| `fig_results_success_share_software_cohorts` | Fleet Runs, Fleet Summary | `results/reviewer_revision/csv/fleet_multiseed_runs.csv` | 180 | Mean and 10,000-resample bootstrap 95% confidence interval |
| `fig_results_failure_probability_sensitivity` | Fleet Outcomes, Fleet Runs | `results/reviewer_revision/csv/fleet_multiseed_runs.csv` | 60 | Outcome count divided by expected cohort; mean and 10,000-resample bootstrap 95% confidence interval |
| `fig_results_application_shaped_ipfs_retrieval` | Network Summary, Network Distribution | `results/reviewer_revision/raw/network/application_shaped_fetches.jsonl` | 60 | All observations with box summaries on a logarithmic axis |
| `fig_results_local_cache_reuse` | Cache Trials, Cache Ablation | `results/reviewer_revision/csv/edge_cache_trials.csv` | 20 | Median origin-side transfer and all independent trial retrieval times with box summaries |
| `fig_results_storage_bounded_accountability` | Acct Ablation, Acct Path Statistics, Acct Path Totals, Gas Break Even | `results/reviewer_revision/csv/accountability_ablation.csv`, `results/reviewer_revision/csv/accountability_path_statistics.csv`, `results/reviewer_revision/csv/accountability_path_totals.csv`, `results/reviewer_revision/statistics/gas_break_even.csv` | 36 | Analytical projection normalized to per-device reporting using compiler-layout bytes and executed median logical-path gas |
| `fig_results_validator_crash_faults` | Validator Faults | `results/reviewer_revision/csv/validator_faults.csv` | 20 | Observed-progress trial counts and all per-trial quorum-restoration times |

## Rendering and Validation

- Font: Times New Roman.
- Formats: vector PDF, editable SVG, and 600 dpi PNG.
- Validation: all numerical, terminology, vector, font, DPI, LaTeX, and integrity checks passed.
- Discrepancies: none detected.
- Figures not generated: none.
- Visual limitation: dense accountability labels require full-width placement; individual panel files are supplied for alternate layouts.
- Contact sheet: visually inspected after the final validated generation.
- LaTeX snippet: `paper_assets/figures/results/results_figures.tex`.
- Regenerate: `python3 experiments/analysis/make_results_figures.py --workbook LedgerGuard_Comprehensive_Results.xlsx --output paper_assets/figures/results`.
- Frozen evidence changed: no.
- Git push performed: no.
