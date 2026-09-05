# Results Figure Validation Report

**Status:** PASS

**Workbook SHA-256:** `4d65d5085065a4baa364e3f83bb5d2b86519ee3195c516f34e098ad0e424d7a4`

## Checks

| Check | Status | Detail |
|---|---|---|
| R1 row count | PASS | observed=90, expected=90 |
| R1 profile counts | PASS | {1: 30, 2: 30, 4: 30} |
| R1 retained long observation | PASS | maximum=31.031609 |
| R1 no excluded observations | PASS | all valid observations are in plot data |
| R1 median 1s | PASS | recomputed=1.046551500 |
| R1 median 2s | PASS | recomputed=2.033573500 |
| R1 median 4s | PASS | recomputed=4.046854000 |
| R1 logarithmic axis visible | PASS | axis label contains log scale |
| R2 total runs | PASS | observed=180 |
| R2 configurations | PASS | {(100, 0.01): 20, (100, 0.02): 20, (100, 0.05): 20, (500, 0.01): 20, (500, 0.02): 20, (500, 0.05): 20, (1000, 0.01): 20, (1000, 0.02): 20, (1000, 0.05): 20} |
| R2 plot points | PASS | observed=9 |
| R2 means and bootstrap intervals | PASS | plot data independently reproduces all nine mean/CI triplets |
| R3 cohort filter | PASS | rows=60 |
| R3 outcomes separate | PASS | ['FAIL', 'ROLLBACK', 'SUCCESS'] |
| R3 point count | PASS | observed=9 |
| R3 means and bootstrap intervals | PASS | SUCCESS, ROLLBACK, and FAIL independently reproduce raw counts |
| R3 rollback not derived as one minus success | PASS | raw rollback and fail fields are distinct and nonzero |
| R4 rows | PASS | observed=60 |
| R4 profile counts | PASS | {'P1': 20, 'P2': 20, 'P3': 20} |
| R4 artifact size | PASS | artifact_size_bytes=537088 |
| R4 retained maximum | PASS | maximum=915.736736 |
| R4 no excluded observations | PASS | all completed observations are in plot data |
| R4 logarithmic axis visible | PASS | axis label contains log scale |
| R5 trials | PASS | OFF=10, ON=10 |
| R5 requests per trial | PASS | all trials contain 1000 requests |
| R5 origin requests | PASS | {'OFF': 1000.0, 'ON': 1.0} |
| R5 cache hits | PASS | ON median=999.0 |
| R5 origin bytes | PASS | {'OFF': 537088000.0, 'ON': 537088.0} |
| R5 integrity | PASS | integrity_failures=0 |
| R5 origin terminology | PASS | visible label uses origin-side transfer |
| R6 grid | PASS | rows=24 |
| R6 plotted approaches | PASS | two aggregation approaches |
| R6 executed gas medians | PASS | {'naive_per_device': 169245, 'v1_integrity_root': 97836, 'v2_complete_witnessed': 434143} |
| R6 N500 B50 transactions | PASS | {'naive_per_device': 500, 'v1_integrity_root': 10, 'v2_complete_witnessed': 30} |
| R6 transaction reductions | PASS | integrity-only=98%, complete-cohort witnessed=94% |
| R6 baseline omitted | PASS | per-device reporting used only as denominator |
| R7 rows and trials | PASS | rows=20 |
| R7 phase counts | PASS | {'zero_validators_stopped': 5, 'one_validator_stopped': 5, 'two_validators_stopped': 5, 'quorum_restored_after_validator_restart': 5} |
| R7 progress counts | PASS | {'zero_validators_stopped': 5, 'one_validator_stopped': 5, 'two_validators_stopped': 0, 'quorum_restored_after_validator_restart': 5} |
| R7 restoration series | PASS | five values in each restoration series |
| Obsolete-value and terminology scan | PASS | scanned 21 visible-output files |
| Tool pdffonts available | PASS | pdffonts available |
| Tool pdfinfo available | PASS | pdfinfo available |
| Tool pdftoppm available | PASS | pdftoppm available |
| Output file count | PASS | observed=60, expected=60 |
| Exists fig_results_block_period_sensitivity.pdf | PASS | paper_assets/figures/results/fig_results_block_period_sensitivity.pdf |
| Checksum fig_results_block_period_sensitivity.pdf | PASS | matches metadata |
| PDF valid fig_results_block_period_sensitivity.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_block_period_sensitivity.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_block_period_sensitivity.pdf | PASS | font_rows=1 |
| PDF info fig_results_block_period_sensitivity.pdf | PASS | width_in=4.698222222222222 |
| Main width fig_results_block_period_sensitivity.pdf | PASS | width_in=4.698222222222222 |
| PDF render fig_results_block_period_sensitivity.pdf | PASS | 150 dpi validation render |
| Exists fig_results_block_period_sensitivity.svg | PASS | paper_assets/figures/results/fig_results_block_period_sensitivity.svg |
| Checksum fig_results_block_period_sensitivity.svg | PASS | matches metadata |
| SVG XML fig_results_block_period_sensitivity.svg | PASS | parsed as XML |
| SVG editable text fig_results_block_period_sensitivity.svg | PASS | contains text elements |
| SVG no raster image fig_results_block_period_sensitivity.svg | PASS | contains no image elements |
| Exists fig_results_block_period_sensitivity.png | PASS | paper_assets/figures/results/fig_results_block_period_sensitivity.png |
| Checksum fig_results_block_period_sensitivity.png | PASS | matches metadata |
| PNG 600 dpi fig_results_block_period_sensitivity.png | PASS | dpi=(599.9988, 599.9988), pixels=(2811, 1931) |
| Exists fig_results_success_share_software_cohorts.pdf | PASS | paper_assets/figures/results/fig_results_success_share_software_cohorts.pdf |
| Checksum fig_results_success_share_software_cohorts.pdf | PASS | matches metadata |
| PDF valid fig_results_success_share_software_cohorts.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_success_share_software_cohorts.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_success_share_software_cohorts.pdf | PASS | font_rows=1 |
| PDF info fig_results_success_share_software_cohorts.pdf | PASS | width_in=4.698222222222222 |
| Main width fig_results_success_share_software_cohorts.pdf | PASS | width_in=4.698222222222222 |
| PDF render fig_results_success_share_software_cohorts.pdf | PASS | 150 dpi validation render |
| Exists fig_results_success_share_software_cohorts.svg | PASS | paper_assets/figures/results/fig_results_success_share_software_cohorts.svg |
| Checksum fig_results_success_share_software_cohorts.svg | PASS | matches metadata |
| SVG XML fig_results_success_share_software_cohorts.svg | PASS | parsed as XML |
| SVG editable text fig_results_success_share_software_cohorts.svg | PASS | contains text elements |
| SVG no raster image fig_results_success_share_software_cohorts.svg | PASS | contains no image elements |
| Exists fig_results_success_share_software_cohorts.png | PASS | paper_assets/figures/results/fig_results_success_share_software_cohorts.png |
| Checksum fig_results_success_share_software_cohorts.png | PASS | matches metadata |
| PNG 600 dpi fig_results_success_share_software_cohorts.png | PASS | dpi=(599.9988, 599.9988), pixels=(2820, 1885) |
| Exists fig_results_failure_probability_sensitivity_a.pdf | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_a.pdf |
| Checksum fig_results_failure_probability_sensitivity_a.pdf | PASS | matches metadata |
| PDF valid fig_results_failure_probability_sensitivity_a.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_failure_probability_sensitivity_a.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_failure_probability_sensitivity_a.pdf | PASS | font_rows=2 |
| PDF info fig_results_failure_probability_sensitivity_a.pdf | PASS | width_in=3.186972222222222 |
| PDF render fig_results_failure_probability_sensitivity_a.pdf | PASS | 150 dpi validation render |
| Exists fig_results_failure_probability_sensitivity_a.svg | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_a.svg |
| Checksum fig_results_failure_probability_sensitivity_a.svg | PASS | matches metadata |
| SVG XML fig_results_failure_probability_sensitivity_a.svg | PASS | parsed as XML |
| SVG editable text fig_results_failure_probability_sensitivity_a.svg | PASS | contains text elements |
| SVG no raster image fig_results_failure_probability_sensitivity_a.svg | PASS | contains no image elements |
| Exists fig_results_failure_probability_sensitivity_a.png | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_a.png |
| Checksum fig_results_failure_probability_sensitivity_a.png | PASS | matches metadata |
| PNG 600 dpi fig_results_failure_probability_sensitivity_a.png | PASS | dpi=(599.9988, 599.9988), pixels=(1914, 1755) |
| Exists fig_results_failure_probability_sensitivity_b.pdf | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_b.pdf |
| Checksum fig_results_failure_probability_sensitivity_b.pdf | PASS | matches metadata |
| PDF valid fig_results_failure_probability_sensitivity_b.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_failure_probability_sensitivity_b.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_failure_probability_sensitivity_b.pdf | PASS | font_rows=2 |
| PDF info fig_results_failure_probability_sensitivity_b.pdf | PASS | width_in=3.21475 |
| PDF render fig_results_failure_probability_sensitivity_b.pdf | PASS | 150 dpi validation render |
| Exists fig_results_failure_probability_sensitivity_b.svg | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_b.svg |
| Checksum fig_results_failure_probability_sensitivity_b.svg | PASS | matches metadata |
| SVG XML fig_results_failure_probability_sensitivity_b.svg | PASS | parsed as XML |
| SVG editable text fig_results_failure_probability_sensitivity_b.svg | PASS | contains text elements |
| SVG no raster image fig_results_failure_probability_sensitivity_b.svg | PASS | contains no image elements |
| Exists fig_results_failure_probability_sensitivity_b.png | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_b.png |
| Checksum fig_results_failure_probability_sensitivity_b.png | PASS | matches metadata |
| PNG 600 dpi fig_results_failure_probability_sensitivity_b.png | PASS | dpi=(599.9988, 599.9988), pixels=(1931, 1755) |
| Exists fig_results_failure_probability_sensitivity_c.pdf | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_c.pdf |
| Checksum fig_results_failure_probability_sensitivity_c.pdf | PASS | matches metadata |
| PDF valid fig_results_failure_probability_sensitivity_c.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_failure_probability_sensitivity_c.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_failure_probability_sensitivity_c.pdf | PASS | font_rows=2 |
| PDF info fig_results_failure_probability_sensitivity_c.pdf | PASS | width_in=3.159194444444444 |
| PDF render fig_results_failure_probability_sensitivity_c.pdf | PASS | 150 dpi validation render |
| Exists fig_results_failure_probability_sensitivity_c.svg | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_c.svg |
| Checksum fig_results_failure_probability_sensitivity_c.svg | PASS | matches metadata |
| SVG XML fig_results_failure_probability_sensitivity_c.svg | PASS | parsed as XML |
| SVG editable text fig_results_failure_probability_sensitivity_c.svg | PASS | contains text elements |
| SVG no raster image fig_results_failure_probability_sensitivity_c.svg | PASS | contains no image elements |
| Exists fig_results_failure_probability_sensitivity_c.png | PASS | paper_assets/figures/results/panels/fig_results_failure_probability_sensitivity_c.png |
| Checksum fig_results_failure_probability_sensitivity_c.png | PASS | matches metadata |
| PNG 600 dpi fig_results_failure_probability_sensitivity_c.png | PASS | dpi=(599.9988, 599.9988), pixels=(1897, 1755) |
| Exists fig_results_failure_probability_sensitivity.pdf | PASS | paper_assets/figures/results/fig_results_failure_probability_sensitivity.pdf |
| Checksum fig_results_failure_probability_sensitivity.pdf | PASS | matches metadata |
| PDF valid fig_results_failure_probability_sensitivity.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_failure_probability_sensitivity.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_failure_probability_sensitivity.pdf | PASS | font_rows=2 |
| PDF info fig_results_failure_probability_sensitivity.pdf | PASS | width_in=7.196666666666666 |
| Main width fig_results_failure_probability_sensitivity.pdf | PASS | width_in=7.196666666666666 |
| PDF render fig_results_failure_probability_sensitivity.pdf | PASS | 150 dpi validation render |
| Exists fig_results_failure_probability_sensitivity.svg | PASS | paper_assets/figures/results/fig_results_failure_probability_sensitivity.svg |
| Checksum fig_results_failure_probability_sensitivity.svg | PASS | matches metadata |
| SVG XML fig_results_failure_probability_sensitivity.svg | PASS | parsed as XML |
| SVG editable text fig_results_failure_probability_sensitivity.svg | PASS | contains text elements |
| SVG no raster image fig_results_failure_probability_sensitivity.svg | PASS | contains no image elements |
| Exists fig_results_failure_probability_sensitivity.png | PASS | paper_assets/figures/results/fig_results_failure_probability_sensitivity.png |
| Checksum fig_results_failure_probability_sensitivity.png | PASS | matches metadata |
| PNG 600 dpi fig_results_failure_probability_sensitivity.png | PASS | dpi=(599.9988, 599.9988), pixels=(4317, 1647) |
| Exists fig_results_application_shaped_ipfs_retrieval.pdf | PASS | paper_assets/figures/results/fig_results_application_shaped_ipfs_retrieval.pdf |
| Checksum fig_results_application_shaped_ipfs_retrieval.pdf | PASS | matches metadata |
| PDF valid fig_results_application_shaped_ipfs_retrieval.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_application_shaped_ipfs_retrieval.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_application_shaped_ipfs_retrieval.pdf | PASS | font_rows=1 |
| PDF info fig_results_application_shaped_ipfs_retrieval.pdf | PASS | width_in=7.065819444444444 |
| Main width fig_results_application_shaped_ipfs_retrieval.pdf | PASS | width_in=7.065819444444444 |
| PDF render fig_results_application_shaped_ipfs_retrieval.pdf | PASS | 150 dpi validation render |
| Exists fig_results_application_shaped_ipfs_retrieval.svg | PASS | paper_assets/figures/results/fig_results_application_shaped_ipfs_retrieval.svg |
| Checksum fig_results_application_shaped_ipfs_retrieval.svg | PASS | matches metadata |
| SVG XML fig_results_application_shaped_ipfs_retrieval.svg | PASS | parsed as XML |
| SVG editable text fig_results_application_shaped_ipfs_retrieval.svg | PASS | contains text elements |
| SVG no raster image fig_results_application_shaped_ipfs_retrieval.svg | PASS | contains no image elements |
| Exists fig_results_application_shaped_ipfs_retrieval.png | PASS | paper_assets/figures/results/fig_results_application_shaped_ipfs_retrieval.png |
| Checksum fig_results_application_shaped_ipfs_retrieval.png | PASS | matches metadata |
| PNG 600 dpi fig_results_application_shaped_ipfs_retrieval.png | PASS | dpi=(599.9988, 599.9988), pixels=(4252, 1829) |
| Exists fig_results_local_cache_reuse_a.pdf | PASS | paper_assets/figures/results/panels/fig_results_local_cache_reuse_a.pdf |
| Checksum fig_results_local_cache_reuse_a.pdf | PASS | matches metadata |
| PDF valid fig_results_local_cache_reuse_a.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_local_cache_reuse_a.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_local_cache_reuse_a.pdf | PASS | font_rows=2 |
| PDF info fig_results_local_cache_reuse_a.pdf | PASS | width_in=3.3603055555555557 |
| PDF render fig_results_local_cache_reuse_a.pdf | PASS | 150 dpi validation render |
| Exists fig_results_local_cache_reuse_a.svg | PASS | paper_assets/figures/results/panels/fig_results_local_cache_reuse_a.svg |
| Checksum fig_results_local_cache_reuse_a.svg | PASS | matches metadata |
| SVG XML fig_results_local_cache_reuse_a.svg | PASS | parsed as XML |
| SVG editable text fig_results_local_cache_reuse_a.svg | PASS | contains text elements |
| SVG no raster image fig_results_local_cache_reuse_a.svg | PASS | contains no image elements |
| Exists fig_results_local_cache_reuse_a.png | PASS | paper_assets/figures/results/panels/fig_results_local_cache_reuse_a.png |
| Checksum fig_results_local_cache_reuse_a.png | PASS | matches metadata |
| PNG 600 dpi fig_results_local_cache_reuse_a.png | PASS | dpi=(599.9988, 599.9988), pixels=(2018, 1696) |
| Exists fig_results_local_cache_reuse_b.pdf | PASS | paper_assets/figures/results/panels/fig_results_local_cache_reuse_b.pdf |
| Checksum fig_results_local_cache_reuse_b.pdf | PASS | matches metadata |
| PDF valid fig_results_local_cache_reuse_b.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_local_cache_reuse_b.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_local_cache_reuse_b.pdf | PASS | font_rows=2 |
| PDF info fig_results_local_cache_reuse_b.pdf | PASS | width_in=3.21475 |
| PDF render fig_results_local_cache_reuse_b.pdf | PASS | 150 dpi validation render |
| Exists fig_results_local_cache_reuse_b.svg | PASS | paper_assets/figures/results/panels/fig_results_local_cache_reuse_b.svg |
| Checksum fig_results_local_cache_reuse_b.svg | PASS | matches metadata |
| SVG XML fig_results_local_cache_reuse_b.svg | PASS | parsed as XML |
| SVG editable text fig_results_local_cache_reuse_b.svg | PASS | contains text elements |
| SVG no raster image fig_results_local_cache_reuse_b.svg | PASS | contains no image elements |
| Exists fig_results_local_cache_reuse_b.png | PASS | paper_assets/figures/results/panels/fig_results_local_cache_reuse_b.png |
| Checksum fig_results_local_cache_reuse_b.png | PASS | matches metadata |
| PNG 600 dpi fig_results_local_cache_reuse_b.png | PASS | dpi=(599.9988, 599.9988), pixels=(1931, 1581) |
| Exists fig_results_local_cache_reuse.pdf | PASS | paper_assets/figures/results/fig_results_local_cache_reuse.pdf |
| Checksum fig_results_local_cache_reuse.pdf | PASS | matches metadata |
| PDF valid fig_results_local_cache_reuse.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_local_cache_reuse.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_local_cache_reuse.pdf | PASS | font_rows=2 |
| PDF info fig_results_local_cache_reuse.pdf | PASS | width_in=7.196666666666666 |
| Main width fig_results_local_cache_reuse.pdf | PASS | width_in=7.196666666666666 |
| PDF render fig_results_local_cache_reuse.pdf | PASS | 150 dpi validation render |
| Exists fig_results_local_cache_reuse.svg | PASS | paper_assets/figures/results/fig_results_local_cache_reuse.svg |
| Checksum fig_results_local_cache_reuse.svg | PASS | matches metadata |
| SVG XML fig_results_local_cache_reuse.svg | PASS | parsed as XML |
| SVG editable text fig_results_local_cache_reuse.svg | PASS | contains text elements |
| SVG no raster image fig_results_local_cache_reuse.svg | PASS | contains no image elements |
| Exists fig_results_local_cache_reuse.png | PASS | paper_assets/figures/results/fig_results_local_cache_reuse.png |
| Checksum fig_results_local_cache_reuse.png | PASS | matches metadata |
| PNG 600 dpi fig_results_local_cache_reuse.png | PASS | dpi=(599.9988, 599.9988), pixels=(4317, 1797) |
| Exists fig_results_storage_bounded_accountability_a.pdf | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_a.pdf |
| Checksum fig_results_storage_bounded_accountability_a.pdf | PASS | matches metadata |
| PDF valid fig_results_storage_bounded_accountability_a.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_storage_bounded_accountability_a.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_storage_bounded_accountability_a.pdf | PASS | font_rows=2 |
| PDF info fig_results_storage_bounded_accountability_a.pdf | PASS | width_in=3.1314166666666665 |
| PDF render fig_results_storage_bounded_accountability_a.pdf | PASS | 150 dpi validation render |
| Exists fig_results_storage_bounded_accountability_a.svg | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_a.svg |
| Checksum fig_results_storage_bounded_accountability_a.svg | PASS | matches metadata |
| SVG XML fig_results_storage_bounded_accountability_a.svg | PASS | parsed as XML |
| SVG editable text fig_results_storage_bounded_accountability_a.svg | PASS | contains text elements |
| SVG no raster image fig_results_storage_bounded_accountability_a.svg | PASS | contains no image elements |
| Exists fig_results_storage_bounded_accountability_a.png | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_a.png |
| Checksum fig_results_storage_bounded_accountability_a.png | PASS | matches metadata |
| PNG 600 dpi fig_results_storage_bounded_accountability_a.png | PASS | dpi=(599.9988, 599.9988), pixels=(1880, 1633) |
| Exists fig_results_storage_bounded_accountability_b.pdf | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_b.pdf |
| Checksum fig_results_storage_bounded_accountability_b.pdf | PASS | matches metadata |
| PDF valid fig_results_storage_bounded_accountability_b.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_storage_bounded_accountability_b.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_storage_bounded_accountability_b.pdf | PASS | font_rows=2 |
| PDF info fig_results_storage_bounded_accountability_b.pdf | PASS | width_in=3.1314166666666665 |
| PDF render fig_results_storage_bounded_accountability_b.pdf | PASS | 150 dpi validation render |
| Exists fig_results_storage_bounded_accountability_b.svg | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_b.svg |
| Checksum fig_results_storage_bounded_accountability_b.svg | PASS | matches metadata |
| SVG XML fig_results_storage_bounded_accountability_b.svg | PASS | parsed as XML |
| SVG editable text fig_results_storage_bounded_accountability_b.svg | PASS | contains text elements |
| SVG no raster image fig_results_storage_bounded_accountability_b.svg | PASS | contains no image elements |
| Exists fig_results_storage_bounded_accountability_b.png | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_b.png |
| Checksum fig_results_storage_bounded_accountability_b.png | PASS | matches metadata |
| PNG 600 dpi fig_results_storage_bounded_accountability_b.png | PASS | dpi=(599.9988, 599.9988), pixels=(1880, 1633) |
| Exists fig_results_storage_bounded_accountability_c.pdf | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_c.pdf |
| Checksum fig_results_storage_bounded_accountability_c.pdf | PASS | matches metadata |
| PDF valid fig_results_storage_bounded_accountability_c.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_storage_bounded_accountability_c.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_storage_bounded_accountability_c.pdf | PASS | font_rows=2 |
| PDF info fig_results_storage_bounded_accountability_c.pdf | PASS | width_in=3.1314166666666665 |
| PDF render fig_results_storage_bounded_accountability_c.pdf | PASS | 150 dpi validation render |
| Exists fig_results_storage_bounded_accountability_c.svg | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_c.svg |
| Checksum fig_results_storage_bounded_accountability_c.svg | PASS | matches metadata |
| SVG XML fig_results_storage_bounded_accountability_c.svg | PASS | parsed as XML |
| SVG editable text fig_results_storage_bounded_accountability_c.svg | PASS | contains text elements |
| SVG no raster image fig_results_storage_bounded_accountability_c.svg | PASS | contains no image elements |
| Exists fig_results_storage_bounded_accountability_c.png | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_c.png |
| Checksum fig_results_storage_bounded_accountability_c.png | PASS | matches metadata |
| PNG 600 dpi fig_results_storage_bounded_accountability_c.png | PASS | dpi=(599.9988, 599.9988), pixels=(1880, 1633) |
| Exists fig_results_storage_bounded_accountability_d.pdf | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_d.pdf |
| Checksum fig_results_storage_bounded_accountability_d.pdf | PASS | matches metadata |
| PDF valid fig_results_storage_bounded_accountability_d.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_storage_bounded_accountability_d.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_storage_bounded_accountability_d.pdf | PASS | font_rows=2 |
| PDF info fig_results_storage_bounded_accountability_d.pdf | PASS | width_in=3.1314166666666665 |
| PDF render fig_results_storage_bounded_accountability_d.pdf | PASS | 150 dpi validation render |
| Exists fig_results_storage_bounded_accountability_d.svg | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_d.svg |
| Checksum fig_results_storage_bounded_accountability_d.svg | PASS | matches metadata |
| SVG XML fig_results_storage_bounded_accountability_d.svg | PASS | parsed as XML |
| SVG editable text fig_results_storage_bounded_accountability_d.svg | PASS | contains text elements |
| SVG no raster image fig_results_storage_bounded_accountability_d.svg | PASS | contains no image elements |
| Exists fig_results_storage_bounded_accountability_d.png | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_d.png |
| Checksum fig_results_storage_bounded_accountability_d.png | PASS | matches metadata |
| PNG 600 dpi fig_results_storage_bounded_accountability_d.png | PASS | dpi=(599.9988, 599.9988), pixels=(1880, 1633) |
| Exists fig_results_storage_bounded_accountability_e.pdf | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_e.pdf |
| Checksum fig_results_storage_bounded_accountability_e.pdf | PASS | matches metadata |
| PDF valid fig_results_storage_bounded_accountability_e.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_storage_bounded_accountability_e.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_storage_bounded_accountability_e.pdf | PASS | font_rows=2 |
| PDF info fig_results_storage_bounded_accountability_e.pdf | PASS | width_in=3.1314166666666665 |
| PDF render fig_results_storage_bounded_accountability_e.pdf | PASS | 150 dpi validation render |
| Exists fig_results_storage_bounded_accountability_e.svg | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_e.svg |
| Checksum fig_results_storage_bounded_accountability_e.svg | PASS | matches metadata |
| SVG XML fig_results_storage_bounded_accountability_e.svg | PASS | parsed as XML |
| SVG editable text fig_results_storage_bounded_accountability_e.svg | PASS | contains text elements |
| SVG no raster image fig_results_storage_bounded_accountability_e.svg | PASS | contains no image elements |
| Exists fig_results_storage_bounded_accountability_e.png | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_e.png |
| Checksum fig_results_storage_bounded_accountability_e.png | PASS | matches metadata |
| PNG 600 dpi fig_results_storage_bounded_accountability_e.png | PASS | dpi=(599.9988, 599.9988), pixels=(1880, 1633) |
| Exists fig_results_storage_bounded_accountability_f.pdf | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_f.pdf |
| Checksum fig_results_storage_bounded_accountability_f.pdf | PASS | matches metadata |
| PDF valid fig_results_storage_bounded_accountability_f.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_storage_bounded_accountability_f.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_storage_bounded_accountability_f.pdf | PASS | font_rows=2 |
| PDF info fig_results_storage_bounded_accountability_f.pdf | PASS | width_in=3.1314166666666665 |
| PDF render fig_results_storage_bounded_accountability_f.pdf | PASS | 150 dpi validation render |
| Exists fig_results_storage_bounded_accountability_f.svg | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_f.svg |
| Checksum fig_results_storage_bounded_accountability_f.svg | PASS | matches metadata |
| SVG XML fig_results_storage_bounded_accountability_f.svg | PASS | parsed as XML |
| SVG editable text fig_results_storage_bounded_accountability_f.svg | PASS | contains text elements |
| SVG no raster image fig_results_storage_bounded_accountability_f.svg | PASS | contains no image elements |
| Exists fig_results_storage_bounded_accountability_f.png | PASS | paper_assets/figures/results/panels/fig_results_storage_bounded_accountability_f.png |
| Checksum fig_results_storage_bounded_accountability_f.png | PASS | matches metadata |
| PNG 600 dpi fig_results_storage_bounded_accountability_f.png | PASS | dpi=(599.9988, 599.9988), pixels=(1880, 1633) |
| Exists fig_results_storage_bounded_accountability.pdf | PASS | paper_assets/figures/results/fig_results_storage_bounded_accountability.pdf |
| Checksum fig_results_storage_bounded_accountability.pdf | PASS | matches metadata |
| PDF valid fig_results_storage_bounded_accountability.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_storage_bounded_accountability.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_storage_bounded_accountability.pdf | PASS | font_rows=2 |
| PDF info fig_results_storage_bounded_accountability.pdf | PASS | width_in=7.189180555555556 |
| Main width fig_results_storage_bounded_accountability.pdf | PASS | width_in=7.189180555555556 |
| PDF render fig_results_storage_bounded_accountability.pdf | PASS | 150 dpi validation render |
| Exists fig_results_storage_bounded_accountability.svg | PASS | paper_assets/figures/results/fig_results_storage_bounded_accountability.svg |
| Checksum fig_results_storage_bounded_accountability.svg | PASS | matches metadata |
| SVG XML fig_results_storage_bounded_accountability.svg | PASS | parsed as XML |
| SVG editable text fig_results_storage_bounded_accountability.svg | PASS | contains text elements |
| SVG no raster image fig_results_storage_bounded_accountability.svg | PASS | contains no image elements |
| Exists fig_results_storage_bounded_accountability.png | PASS | paper_assets/figures/results/fig_results_storage_bounded_accountability.png |
| Checksum fig_results_storage_bounded_accountability.png | PASS | matches metadata |
| PNG 600 dpi fig_results_storage_bounded_accountability.png | PASS | dpi=(599.9988, 599.9988), pixels=(4317, 4429) |
| Exists fig_results_validator_crash_faults_a.pdf | PASS | paper_assets/figures/results/panels/fig_results_validator_crash_faults_a.pdf |
| Checksum fig_results_validator_crash_faults_a.pdf | PASS | matches metadata |
| PDF valid fig_results_validator_crash_faults_a.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_validator_crash_faults_a.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_validator_crash_faults_a.pdf | PASS | font_rows=2 |
| PDF info fig_results_validator_crash_faults_a.pdf | PASS | width_in=3.1013333333333333 |
| PDF render fig_results_validator_crash_faults_a.pdf | PASS | 150 dpi validation render |
| Exists fig_results_validator_crash_faults_a.svg | PASS | paper_assets/figures/results/panels/fig_results_validator_crash_faults_a.svg |
| Checksum fig_results_validator_crash_faults_a.svg | PASS | matches metadata |
| SVG XML fig_results_validator_crash_faults_a.svg | PASS | parsed as XML |
| SVG editable text fig_results_validator_crash_faults_a.svg | PASS | contains text elements |
| SVG no raster image fig_results_validator_crash_faults_a.svg | PASS | contains no image elements |
| Exists fig_results_validator_crash_faults_a.png | PASS | paper_assets/figures/results/panels/fig_results_validator_crash_faults_a.png |
| Checksum fig_results_validator_crash_faults_a.png | PASS | matches metadata |
| PNG 600 dpi fig_results_validator_crash_faults_a.png | PASS | dpi=(599.9988, 599.9988), pixels=(1860, 1686) |
| Exists fig_results_validator_crash_faults_b.pdf | PASS | paper_assets/figures/results/panels/fig_results_validator_crash_faults_b.pdf |
| Checksum fig_results_validator_crash_faults_b.pdf | PASS | matches metadata |
| PDF valid fig_results_validator_crash_faults_b.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_validator_crash_faults_b.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_validator_crash_faults_b.pdf | PASS | font_rows=2 |
| PDF info fig_results_validator_crash_faults_b.pdf | PASS | width_in=3.1314166666666665 |
| PDF render fig_results_validator_crash_faults_b.pdf | PASS | 150 dpi validation render |
| Exists fig_results_validator_crash_faults_b.svg | PASS | paper_assets/figures/results/panels/fig_results_validator_crash_faults_b.svg |
| Checksum fig_results_validator_crash_faults_b.svg | PASS | matches metadata |
| SVG XML fig_results_validator_crash_faults_b.svg | PASS | parsed as XML |
| SVG editable text fig_results_validator_crash_faults_b.svg | PASS | contains text elements |
| SVG no raster image fig_results_validator_crash_faults_b.svg | PASS | contains no image elements |
| Exists fig_results_validator_crash_faults_b.png | PASS | paper_assets/figures/results/panels/fig_results_validator_crash_faults_b.png |
| Checksum fig_results_validator_crash_faults_b.png | PASS | matches metadata |
| PNG 600 dpi fig_results_validator_crash_faults_b.png | PASS | dpi=(599.9988, 599.9988), pixels=(1880, 1706) |
| Exists fig_results_validator_crash_faults.pdf | PASS | paper_assets/figures/results/fig_results_validator_crash_faults.pdf |
| Checksum fig_results_validator_crash_faults.pdf | PASS | matches metadata |
| PDF valid fig_results_validator_crash_faults.pdf | PASS | pdffonts parsed file |
| No Type 3 fig_results_validator_crash_faults.pdf | PASS | no Type 3 font rows |
| Fonts embedded fig_results_validator_crash_faults.pdf | PASS | font_rows=2 |
| PDF info fig_results_validator_crash_faults.pdf | PASS | width_in=7.189180555555556 |
| Main width fig_results_validator_crash_faults.pdf | PASS | width_in=7.189180555555556 |
| PDF render fig_results_validator_crash_faults.pdf | PASS | 150 dpi validation render |
| Exists fig_results_validator_crash_faults.svg | PASS | paper_assets/figures/results/fig_results_validator_crash_faults.svg |
| Checksum fig_results_validator_crash_faults.svg | PASS | matches metadata |
| SVG XML fig_results_validator_crash_faults.svg | PASS | parsed as XML |
| SVG editable text fig_results_validator_crash_faults.svg | PASS | contains text elements |
| SVG no raster image fig_results_validator_crash_faults.svg | PASS | contains no image elements |
| Exists fig_results_validator_crash_faults.png | PASS | paper_assets/figures/results/fig_results_validator_crash_faults.png |
| Checksum fig_results_validator_crash_faults.png | PASS | matches metadata |
| PNG 600 dpi fig_results_validator_crash_faults.png | PASS | dpi=(599.9988, 599.9988), pixels=(4317, 1887) |
| LaTeX integration | PASS | compiled successfully |
| Workbook checksum stable | PASS | sha256=4d65d5085065a4baa364e3f83bb5d2b86519ee3195c516f34e098ad0e424d7a4 |
| Frozen evidence checksums | PASS | checked=857, mismatches=[] |
| No protected Git changes | PASS | [] |
| Contact sheet | PASS | paper_assets/figures/results/previews/results_figure_contact_sheet.png |
| Visual contact-sheet review | PASS | Reviewed for clipping, overlap, panel consistency, grayscale distinctions, visible outliers, and excess whitespace |

## Discrepancies

None. All canonical summaries reproduced the frozen row-level evidence within the declared numerical tolerance.
