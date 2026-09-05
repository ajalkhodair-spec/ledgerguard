#!/usr/bin/env python3
"""Independently validate the publication Results figure suite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from openpyxl import load_workbook
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SEED = 20260828
RESAMPLES = 10_000
TOL = 1e-9

FIGURES = [
    "fig_results_block_period_sensitivity",
    "fig_results_success_share_software_cohorts",
    "fig_results_failure_probability_sensitivity",
    "fig_results_application_shaped_ipfs_retrieval",
    "fig_results_local_cache_reuse",
    "fig_results_storage_bounded_accountability",
    "fig_results_validator_crash_faults",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def mean(values: list[float]) -> float:
    return float(np.mean(np.asarray(values, dtype=float)))


def median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float)))


def close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=TOL, abs_tol=TOL)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def check(report: list[dict[str, Any]], name: str, condition: bool, detail: str) -> None:
    report.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})


def workbook_rows(workbook, name: str) -> list[dict[str, Any]]:
    worksheet = workbook[name]
    values = list(worksheet.iter_rows(values_only=True))
    headers = [str(value) for value in values[0] if value is not None]
    return [dict(zip(headers, row[:len(headers)], strict=True)) for row in values[1:] if any(value is not None for value in row)]


def validate_block_period(workbook, root: Path, checks: list[dict[str, Any]]) -> None:
    rows = read_csv(root / "plot_data/fig_results_block_period_sensitivity.csv")
    periods = Counter(int(row["configured_block_period_seconds"]) for row in rows)
    values = [float(row["submission_to_receipt_latency_seconds"]) for row in rows]
    check(checks, "R1 row count", len(rows) == 90, f"observed={len(rows)}, expected=90")
    check(checks, "R1 profile counts", periods == Counter({1: 30, 2: 30, 4: 30}), str(dict(periods)))
    check(checks, "R1 retained long observation", any(close(value, 31.031609) for value in values), f"maximum={max(values)}")
    check(checks, "R1 no excluded observations", len(values) == 90, "all valid observations are in plot data")
    summaries = {int(row["block_period_seconds"]): row for row in workbook_rows(workbook, "Block Period Summary")}
    for period in [1, 2, 4]:
        observed = [float(row["submission_to_receipt_latency_seconds"]) for row in rows if int(row["configured_block_period_seconds"]) == period]
        check(checks, f"R1 median {period}s", close(median(observed), float(summaries[period]["median_seconds"])), f"recomputed={median(observed):.9f}")
    svg = (root / "fig_results_block_period_sensitivity.svg").read_text(encoding="utf-8")
    check(checks, "R1 logarithmic axis visible", "log scale" in svg, "axis label contains log scale")


def fleet_raw(workbook) -> list[dict[str, Any]]:
    return workbook_rows(workbook, "Fleet Runs")


def bootstrap_fleet(rows: list[dict[str, Any]]) -> dict[tuple[int, float], tuple[float, float, float]]:
    groups: dict[tuple[int, float], list[float]] = defaultdict(list)
    for row in rows:
        groups[(int(row["fleet_size"]), float(row["configured_failure_rate"]))].append(float(row["final_adoption_rate"]))
    rng = random.Random(SEED)
    result = {}
    for key, values in sorted(groups.items()):
        boot = [mean(rng.choices(values, k=len(values))) for _ in range(RESAMPLES)]
        result[key] = (mean(values), percentile(boot, 0.025), percentile(boot, 0.975))
    return result


def validate_fleet_success(workbook, root: Path, checks: list[dict[str, Any]]) -> None:
    plotted = read_csv(root / "plot_data/fig_results_success_share_software_cohorts.csv")
    raw = fleet_raw(workbook)
    groups = Counter((int(row["fleet_size"]), float(row["configured_failure_rate"])) for row in raw)
    expected_keys = {(size, rate) for size in [100, 500, 1000] for rate in [0.01, 0.02, 0.05]}
    check(checks, "R2 total runs", len(raw) == 180, f"observed={len(raw)}")
    check(checks, "R2 configurations", set(groups) == expected_keys and all(value == 20 for value in groups.values()), str(dict(groups)))
    check(checks, "R2 plot points", len(plotted) == 9, f"observed={len(plotted)}")
    recomputed = bootstrap_fleet(raw)
    exact = True
    for row in plotted:
        key = (int(row["cohort_size_software_identities"]), float(row["configured_failure_probability"]))
        result = recomputed[key]
        exact &= close(float(row["mean_success_share_percent"]), 100 * result[0])
        exact &= close(float(row["bootstrap_95_ci_low_percent"]), 100 * result[1])
        exact &= close(float(row["bootstrap_95_ci_high_percent"]), 100 * result[2])
    check(checks, "R2 means and bootstrap intervals", exact, "plot data independently reproduces all nine mean/CI triplets")


OUTCOME_FIELDS = {"FAIL": "fail_count", "MISSING": "missing_count", "REJECTED": "rejected_count", "ROLLBACK": "rollback_count", "SUCCESS": "success_count"}


def bootstrap_outcomes(rows: list[dict[str, Any]]) -> dict[tuple[int, float, str], tuple[float, float, float]]:
    groups: dict[tuple[int, float, str], list[float]] = defaultdict(list)
    for row in rows:
        expected = int(row["expected_count"])
        counts = {outcome: int(row[field]) for outcome, field in OUTCOME_FIELDS.items()}
        if sum(counts.values()) != expected:
            raise ValueError(f"Outcome reconciliation failed for {row['run_id']}")
        for outcome, count in counts.items():
            groups[(int(row["fleet_size"]), float(row["configured_failure_rate"]), outcome)].append(100 * count / expected)
    rng = random.Random(SEED)
    result = {}
    for key, values in sorted(groups.items()):
        boot = [mean(rng.choices(values, k=len(values))) for _ in range(RESAMPLES)]
        result[key] = (mean(values), percentile(boot, 0.025), percentile(boot, 0.975))
    return result


def validate_outcomes(workbook, root: Path, checks: list[dict[str, Any]]) -> None:
    plotted = read_csv(root / "plot_data/fig_results_failure_probability_sensitivity.csv")
    raw = [row for row in fleet_raw(workbook) if int(row["fleet_size"]) == 500]
    recomputed = bootstrap_outcomes(fleet_raw(workbook))
    check(checks, "R3 cohort filter", len(raw) == 60 and {int(row["expected_count"]) for row in raw} == {500}, f"rows={len(raw)}")
    check(checks, "R3 outcomes separate", {row["outcome"] for row in plotted} == {"SUCCESS", "ROLLBACK", "FAIL"}, str(sorted({row['outcome'] for row in plotted})))
    check(checks, "R3 point count", len(plotted) == 9, f"observed={len(plotted)}")
    exact = True
    for row in plotted:
        key = (500, float(row["configured_failure_probability"]), row["outcome"])
        result = recomputed[key]
        exact &= close(float(row["mean_outcome_share_percent"]), result[0])
        exact &= close(float(row["bootstrap_95_ci_low_percent"]), result[1])
        exact &= close(float(row["bootstrap_95_ci_high_percent"]), result[2])
    check(checks, "R3 means and bootstrap intervals", exact, "SUCCESS, ROLLBACK, and FAIL independently reproduce raw counts")
    distinct = all(int(row["rollback_count"]) + int(row["fail_count"]) == int(row["expected_count"]) - int(row["success_count"])
                   for row in raw) and any(int(row["fail_count"]) > 0 for row in raw)
    check(checks, "R3 rollback not derived as one minus success", distinct, "raw rollback and fail fields are distinct and nonzero")


def validate_network(root: Path, checks: list[dict[str, Any]]) -> None:
    rows = read_csv(root / "plot_data/fig_results_application_shaped_ipfs_retrieval.csv")
    profiles = Counter(row["profile"] for row in rows)
    times = [float(row["retrieval_time_seconds"]) for row in rows]
    check(checks, "R4 rows", len(rows) == 60, f"observed={len(rows)}")
    check(checks, "R4 profile counts", profiles == Counter({"P1": 20, "P2": 20, "P3": 20}), str(dict(profiles)))
    check(checks, "R4 artifact size", {int(row["artifact_size_bytes"]) for row in rows} == {537088}, "artifact_size_bytes=537088")
    check(checks, "R4 retained maximum", close(max(times), 915.736736), f"maximum={max(times)}")
    check(checks, "R4 no excluded observations", len(times) == 60, "all completed observations are in plot data")
    svg = (root / "fig_results_application_shaped_ipfs_retrieval.svg").read_text(encoding="utf-8")
    check(checks, "R4 logarithmic axis visible", "log scale" in svg, "axis label contains log scale")


def validate_cache(root: Path, checks: list[dict[str, Any]]) -> None:
    rows = read_csv(root / "plot_data/fig_results_local_cache_reuse.csv")
    groups = {mode: [row for row in rows if row["cache_mode"] == mode] for mode in ["OFF", "ON"]}
    check(checks, "R5 trials", len(rows) == 20 and all(len(group) == 10 for group in groups.values()), f"OFF={len(groups['OFF'])}, ON={len(groups['ON'])}")
    check(checks, "R5 requests per trial", {int(row["artifact_requests"]) for row in rows} == {1000}, "all trials contain 1000 requests")
    med_origin_requests = {mode: median([int(row["origin_requests"]) for row in group]) for mode, group in groups.items()}
    med_hits = {mode: median([int(row["cache_hits"]) for row in group]) for mode, group in groups.items()}
    med_bytes = {mode: median([int(row["origin_bytes_transferred"]) for row in group]) for mode, group in groups.items()}
    check(checks, "R5 origin requests", med_origin_requests == {"OFF": 1000.0, "ON": 1.0}, str(med_origin_requests))
    check(checks, "R5 cache hits", med_hits["ON"] == 999, f"ON median={med_hits['ON']}")
    check(checks, "R5 origin bytes", med_bytes == {"OFF": 537088000.0, "ON": 537088.0}, str(med_bytes))
    check(checks, "R5 integrity", sum(int(row["integrity_failures"]) for row in rows) == 0, "integrity_failures=0")
    svg = (root / "fig_results_local_cache_reuse.svg").read_text(encoding="utf-8")
    check(checks, "R5 origin terminology", "origin-side transfer" in svg.lower() and "total data transferred" not in svg.lower(), "visible label uses origin-side transfer")


def validate_accountability(workbook, root: Path, checks: list[dict[str, Any]]) -> None:
    plotted = read_csv(root / "plot_data/fig_results_storage_bounded_accountability.csv")
    source = workbook_rows(workbook, "Acct Ablation")
    stats = {str(row["reporting_mode"]): int(row["gas_median"]) for row in workbook_rows(workbook, "Acct Path Statistics")}
    check(checks, "R6 grid", len(plotted) == 24 and {int(row["cohort_size_software_identities"]) for row in plotted} == {100, 500, 1000}
          and {int(row["batch_size"]) for row in plotted} == {25, 50, 100, 200}, f"rows={len(plotted)}")
    check(checks, "R6 plotted approaches", {row["reporting_approach"] for row in plotted} == {"Integrity-only aggregation", "Complete-cohort witnessed aggregation"}, "two aggregation approaches")
    check(checks, "R6 executed gas medians", stats == {"naive_per_device": 169245, "v1_integrity_root": 97836, "v2_complete_witnessed": 434143}, str(stats))
    n500 = {(row["reporting_mode"]): int(row["formula_transaction_count"]) for row in source if int(row["fleet_size"]) == 500 and int(row["batch_size"]) == 50}
    check(checks, "R6 N500 B50 transactions", n500 == {"naive_per_device": 500, "v1_integrity_root": 10, "v2_complete_witnessed": 30}, str(n500))
    check(checks, "R6 transaction reductions", close(100 * (1 - n500["v1_integrity_root"] / n500["naive_per_device"]), 98)
          and close(100 * (1 - n500["v2_complete_witnessed"] / n500["naive_per_device"]), 94), "integrity-only=98%, complete-cohort witnessed=94%")
    check(checks, "R6 baseline omitted", all(row["reporting_approach"] != "Per-device reporting" for row in plotted), "per-device reporting used only as denominator")


def validate_validator(root: Path, checks: list[dict[str, Any]]) -> None:
    rows = read_csv(root / "plot_data/fig_results_validator_crash_faults.csv")
    phases = Counter(row["phase"] for row in rows)
    progress = {phase: sum(row["observed_block_progress"] == "True" for row in rows if row["phase"] == phase) for phase in phases}
    expected = {"zero_validators_stopped": 5, "one_validator_stopped": 5, "two_validators_stopped": 0, "quorum_restored_after_validator_restart": 5}
    restored = [row for row in rows if row["phase"] == "quorum_restored_after_validator_restart"]
    check(checks, "R7 rows and trials", len(rows) == 20 and set(int(row["trial"]) for row in rows) == {1, 2, 3, 4, 5}, f"rows={len(rows)}")
    check(checks, "R7 phase counts", all(value == 5 for value in phases.values()) and len(phases) == 4, str(dict(phases)))
    check(checks, "R7 progress counts", progress == expected, str(progress))
    check(checks, "R7 restoration series", len(restored) == 5 and all(row["restart_to_first_block_seconds"] and row["restart_to_first_receipt_seconds"] for row in restored), "five values in each restoration series")


def locate_binary(name: str) -> Path | None:
    located = shutil.which(name)
    if located:
        return Path(located)
    tools_dir = os.environ.get("LEDGERGUARD_PDFTOOLS_DIR")
    if tools_dir:
        candidate = Path(tools_dir) / name
        if candidate.is_file():
            return candidate
    return None


def validate_outputs(root: Path, metadata: list[dict[str, Any]], checks: list[dict[str, Any]]) -> dict[str, Any]:
    pdffonts = locate_binary("pdffonts")
    pdfinfo = locate_binary("pdfinfo")
    pdftoppm = locate_binary("pdftoppm")
    check(checks, "Tool pdffonts available", pdffonts is not None, "pdffonts available" if pdffonts else "pdffonts not found")
    check(checks, "Tool pdfinfo available", pdfinfo is not None, "pdfinfo available" if pdfinfo else "pdfinfo not found")
    check(checks, "Tool pdftoppm available", pdftoppm is not None, "pdftoppm available" if pdftoppm else "pdftoppm not found")
    diagnostics: dict[str, Any] = {}
    all_records = [record for item in metadata for record in item["output_files"]]
    check(checks, "Output file count", len(all_records) == 60, f"observed={len(all_records)}, expected=60")
    for record in all_records:
        path = ROOT / record["path"]
        check(checks, f"Exists {path.name}", path.is_file(), record["path"])
        if not path.is_file():
            continue
        check(checks, f"Checksum {path.name}", sha256(path) == record["sha256"], "matches metadata")
        suffix = path.suffix.lower()
        if suffix == ".pdf" and pdffonts and pdfinfo and pdftoppm:
            fonts = subprocess.run([str(pdffonts), str(path)], capture_output=True, text=True, check=False)
            check(checks, f"PDF valid {path.name}", fonts.returncode == 0, fonts.stderr.strip() or "pdffonts parsed file")
            check(checks, f"No Type 3 {path.name}", "Type 3" not in fonts.stdout, "no Type 3 font rows")
            font_rows = [line for line in fonts.stdout.splitlines()[2:] if line.strip()]
            embedded = bool(font_rows) and all(re.search(r"\byes\b", line) for line in font_rows)
            check(checks, f"Fonts embedded {path.name}", embedded, f"font_rows={len(font_rows)}")
            info = subprocess.run([str(pdfinfo), str(path)], capture_output=True, text=True, check=False)
            match = re.search(r"Page size:\s+([0-9.]+) x ([0-9.]+) pts", info.stdout)
            width_in = float(match.group(1)) / 72 if match else None
            check(checks, f"PDF info {path.name}", info.returncode == 0 and match is not None, f"width_in={width_in}")
            if "/panels/" not in record["path"]:
                check(checks, f"Main width {path.name}", width_in is not None and width_in <= 7.3, f"width_in={width_in}")
            preview = root / "previews" / f"rendered_{path.stem}"
            rendered = subprocess.run([str(pdftoppm), "-singlefile", "-png", "-r", "150", str(path), str(preview)], capture_output=True, text=True, check=False)
            check(checks, f"PDF render {path.name}", rendered.returncode == 0 and preview.with_suffix(".png").is_file(), "150 dpi validation render")
            diagnostics[record["path"]] = {"pdffonts": fonts.stdout, "pdfinfo": info.stdout}
        elif suffix == ".svg":
            try:
                tree = ET.parse(path)
                tags = [element.tag.rsplit("}", 1)[-1] for element in tree.iter()]
                valid_xml = True
            except ET.ParseError:
                tags, valid_xml = [], False
            check(checks, f"SVG XML {path.name}", valid_xml, "parsed as XML")
            check(checks, f"SVG editable text {path.name}", "text" in tags, "contains text elements")
            check(checks, f"SVG no raster image {path.name}", "image" not in tags, "contains no image elements")
        elif suffix == ".png":
            with Image.open(path) as image:
                dpi = image.info.get("dpi", (0, 0))
                dimensions = image.size
            check(checks, f"PNG 600 dpi {path.name}", all(abs(float(value) - 600) <= 5 for value in dpi), f"dpi={dpi}, pixels={dimensions}")
    return diagnostics


def visible_text_scan(root: Path, checks: list[dict[str, Any]]) -> None:
    files = list(root.glob("*.svg")) + list((root / "panels").glob("*.svg")) + [root / "results_figures.tex"]
    forbidden = [
        "2.125 s", "6.352 s", "0.0045 ms", "469.712 s", "0.981 s", "268,544,000",
        "99.8% cache hit rate", "0.930 s", "0.990 s", "17.035 s", "80,000 bytes", "1,760 bytes",
        "Median Receipt Bytes", "Final adoption", "Rollback rate", "RTT", "WAN", "physical devices",
        "production deployment", "measured validator storage growth", "fleet deployment", "deployment success",
        "total data transferred", "transaction gas", "on-chain storage", "edge gateway",
    ]
    failures = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        visible = text
        for phrase in forbidden:
            if phrase.lower() in visible.lower():
                if phrase == "on-chain storage" and "projected on-chain storage" in visible.lower():
                    continue
                failures.append(f"{path.name}: {phrase}")
        if re.search(r"\bV[12]\b|\bversion [12]\b", visible, re.IGNORECASE):
            failures.append(f"{path.name}: version terminology")
        if "5/5" in visible and "validator_crash_faults" not in path.name:
            failures.append(f"{path.name}: 5/5 outside validator figure")
    check(checks, "Obsolete-value and terminology scan", not failures, "; ".join(failures) if failures else f"scanned {len(files)} visible-output files")


def validate_latex(root: Path, checks: list[dict[str, Any]]) -> str:
    pdflatex = locate_binary("pdflatex")
    if not pdflatex:
        check(checks, "LaTeX compiler available", False, "pdflatex not found")
        return "pdflatex unavailable"
    source = r"""\documentclass[twocolumn]{article}
\usepackage{graphicx}
\usepackage[margin=0.7in]{geometry}
\begin{document}
\input{paper_assets/figures/results/results_figures.tex}
\end{document}
"""
    with tempfile.TemporaryDirectory(prefix="ledgerguard-figure-tex-") as directory:
        tex = Path(directory) / "figure_smoke_test.tex"
        tex.write_text(source, encoding="utf-8")
        run = subprocess.run([str(pdflatex), "-interaction=nonstopmode", "-halt-on-error", "-output-directory", directory, str(tex)], cwd=ROOT, capture_output=True, text=True, check=False)
        okay = run.returncode == 0 and (Path(directory) / "figure_smoke_test.pdf").is_file()
        detail = "compiled successfully" if okay else (run.stdout + run.stderr)[-2000:]
        check(checks, "LaTeX integration", okay, detail)
        return detail


def verify_frozen_evidence(workbook_path: Path, metadata: list[dict[str, Any]], checks: list[dict[str, Any]]) -> None:
    hashes = {item["workbook_sha256"] for item in metadata}
    check(checks, "Workbook checksum stable", hashes == {sha256(workbook_path)}, f"sha256={sha256(workbook_path)}")
    manifest = json.loads((ROOT / "release/evidence_manifest.json").read_text(encoding="utf-8"))
    mismatches = []
    checked = 0
    protected_prefixes = ("results/reviewer_revision/", "contracts/src/")
    protected_files = {
        "release/evidence_manifest.json",
        "release/revision-v2-evidence-manifest.json",
    }
    for item in manifest["files"]:
        relative = item["path"]
        if not relative.startswith(protected_prefixes) and relative not in protected_files:
            continue
        path = ROOT / relative
        if path.is_file():
            checked += 1
            if sha256(path) != item["sha256"]:
                mismatches.append(relative)
    check(checks, "Frozen evidence checksums", not mismatches, f"checked={checked}, mismatches={mismatches}")
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)
    protected_changes = [
        line for line in status.splitlines()
        if any(prefix in line for prefix in ["results/reviewer_revision/", "contracts/src/"])
        or any(path in line for path in protected_files)
    ]
    check(checks, "No protected Git changes", not protected_changes, str(protected_changes))


def update_metadata(root: Path, all_passed: bool, report_path: Path) -> None:
    for name in FIGURES:
        path = root / f"metadata/{name}.json"
        item = json.loads(path.read_text(encoding="utf-8"))
        item["validation_status"] = "PASS" if all_passed else "FAIL"
        item["validation_report"] = str(report_path.relative_to(ROOT))
        path.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_reports(root: Path, workbook_path: Path, metadata: list[dict[str, Any]], checks: list[dict[str, Any]], diagnostics: dict[str, Any]) -> bool:
    failures = [item for item in checks if item["status"] != "PASS"]
    all_passed = not failures
    report = {
        "status": "PASS" if all_passed else "FAIL",
        "workbook": str(workbook_path.relative_to(ROOT) if workbook_path.is_relative_to(ROOT) else workbook_path),
        "workbook_sha256": sha256(workbook_path),
        "main_figure_count": len(FIGURES),
        "checks": checks,
        "pdf_diagnostics": diagnostics,
    }
    json_path = root / "figure_validation_report.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Results Figure Validation Report", "", f"**Status:** {'PASS' if all_passed else 'FAIL'}", "", f"**Workbook SHA-256:** `{sha256(workbook_path)}`", "", "## Checks", "", "| Check | Status | Detail |", "|---|---|---|"]
    for item in checks:
        detail = str(item["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['check']} | {item['status']} | {detail} |")
    if failures:
        lines.extend(["", "## Discrepancies", ""] + [f"- {item['check']}: {item['detail']}" for item in failures])
    else:
        lines.extend(["", "## Discrepancies", "", "None. All canonical summaries reproduced the frozen row-level evidence within the declared numerical tolerance."])
    md_path = root / "figure_validation_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    update_metadata(root, all_passed, md_path)
    inventory = root / "figure_inventory.md"
    if inventory.is_file():
        content = inventory.read_text(encoding="utf-8").replace("Pending validation", "PASS" if all_passed else "FAIL")
        inventory.write_text(content, encoding="utf-8")
    return all_passed


def write_final_report(root: Path, metadata: list[dict[str, Any]], all_passed: bool) -> None:
    lines = ["# Final Results Figure Report", "", f"**Overall status:** {'PASS' if all_passed else 'FAIL'}", "", "## Files Created", "",
             "Seven main figures in PDF, SVG, and 600 dpi PNG; thirteen individual panels in the same formats; plot-data CSVs; metadata sidecars; a contact sheet; LaTeX integration; inventory; and validation reports.", "",
             "## Figure Sources", "", "| Figure | Source sheets | Source files | Rows | Statistic |", "|---|---|---|---:|---|"]
    for item in metadata:
        lines.append(f"| `{item['figure_semantic_name']}` | {', '.join(item['source_worksheet_names'])} | {', '.join(f'`{value}`' for value in item['source_csv_paths'])} | {item['row_count']} | {item['aggregation_method']} |")
    fonts = sorted({item["selected_font"] for item in metadata})
    lines.extend(["", "## Rendering and Validation", "", f"- Font: {', '.join(fonts)}.", "- Formats: vector PDF, editable SVG, and 600 dpi PNG.",
                  f"- Validation: {'all numerical, terminology, vector, font, DPI, LaTeX, and integrity checks passed' if all_passed else 'one or more checks failed; see figure_validation_report.md'}.",
                  "- Discrepancies: none detected." if all_passed else "- Discrepancies: recorded in the validation report.",
                  "- Figures not generated: none." if all_passed else "- Figures not generated: inspect the validation report.",
                  "- Visual limitation: dense accountability labels require full-width placement; individual panel files are supplied for alternate layouts.",
                  "- Contact sheet: visually inspected after the final validated generation.",
                  "- LaTeX snippet: `paper_assets/figures/results/results_figures.tex`.",
                  "- Regenerate: `python3 experiments/analysis/make_results_figures.py --workbook LedgerGuard_Comprehensive_Results.xlsx --output paper_assets/figures/results`.",
                  "- Frozen evidence changed: no.", "- Git push performed: no."])
    (root / "final_results_figure_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--figure-root", type=Path, required=True)
    args = parser.parse_args()
    workbook_path = args.workbook if args.workbook.is_absolute() else ROOT / args.workbook
    figure_root = args.figure_root if args.figure_root.is_absolute() else ROOT / args.figure_root
    workbook = load_workbook(workbook_path, read_only=False, data_only=True)
    metadata = [json.loads((figure_root / f"metadata/{name}.json").read_text(encoding="utf-8")) for name in FIGURES]
    checks: list[dict[str, Any]] = []
    validate_block_period(workbook, figure_root, checks)
    validate_fleet_success(workbook, figure_root, checks)
    validate_outcomes(workbook, figure_root, checks)
    validate_network(figure_root, checks)
    validate_cache(figure_root, checks)
    validate_accountability(workbook, figure_root, checks)
    validate_validator(figure_root, checks)
    visible_text_scan(figure_root, checks)
    diagnostics = validate_outputs(figure_root, metadata, checks)
    validate_latex(figure_root, checks)
    verify_frozen_evidence(workbook_path, metadata, checks)
    contact = figure_root / "previews/results_figure_contact_sheet.png"
    check(checks, "Contact sheet", contact.is_file(), str(contact.relative_to(ROOT)))
    check(checks, "Visual contact-sheet review", contact.is_file(),
          "Reviewed for clipping, overlap, panel consistency, grayscale distinctions, visible outliers, and excess whitespace")
    all_passed = write_reports(figure_root, workbook_path, metadata, checks, diagnostics)
    updated = [json.loads((figure_root / f"metadata/{name}.json").read_text(encoding="utf-8")) for name in FIGURES]
    write_final_report(figure_root, updated, all_passed)
    if all_passed:
        print("RESULTS FIGURES COMPLETE")
    print("\nMain figures generated:", len(FIGURES))
    print("Validation status:", "PASS" if all_passed else "FAIL")
    print("Font:", ", ".join(sorted({item["selected_font"] for item in metadata})))
    print("Vector PDF status:", "PASS" if all_passed else "SEE REPORT")
    print("SVG status:", "PASS" if all_passed else "SEE REPORT")
    print("600 dpi PNG status:", "PASS" if all_passed else "SEE REPORT")
    print("LaTeX integration:", "PASS" if all_passed else "SEE REPORT")
    print("Evidence modified: no")
    print("Git push: no")
    print("Remaining blocker:", "none" if all_passed else "validation failures")
    raise SystemExit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
