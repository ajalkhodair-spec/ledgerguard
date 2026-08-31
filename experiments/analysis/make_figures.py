#!/usr/bin/env python3
"""Generate clean PDF/SVG figures for strong-evaluation status outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

STRONG_EVAL_CSVS = [
    "sqlite_baseline_timing.csv",
    "governance_timing.csv",
    "governance_correctness.csv",
    "distributed_besu_timing.csv",
    "validator_resource_usage.csv",
    "chain_growth.csv",
    "network_sensitivity.csv",
    "edge_cache_ablation.csv",
    "accountability_ablation.csv",
    "adversarial_validation.csv",
    "security_checks.csv",
]

def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--out-dir", default="paper_assets/figures")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    datasets = []
    statuses = []
    for name in STRONG_EVAL_CSVS:
        path = results_dir / "csv" / name
        if not path.exists():
            continue
        rows = read_rows(path)
        status_counts = {}
        for row in rows:
            status = row.get("status") or row.get("evidence_status") or row.get("measurement_status") or "recorded"
            status_counts[status] = status_counts.get(status, 0) + 1
        datasets.append(path.stem.replace("_", " "))
        statuses.append(status_counts)

    if not datasets:
        (out_dir / "strong_eval_status.txt").write_text("No CSV results available.\n", encoding="utf-8")
        return 0

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        svg_path = out_dir / "fig_strong_eval_evidence_status.svg"
        pdf_path = out_dir / "fig_strong_eval_evidence_status.pdf"
        rows = "\n".join(
            f'<text x="30" y="{60 + i * 24}" font-family="Times, serif" font-size="14">{name}: {sum(statuses[i].values())} rows</text>'
            for i, name in enumerate(datasets)
        )
        svg_path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{100 + len(datasets) * 24}">'
            '<rect width="100%" height="100%" fill="white"/>'
            '<text x="30" y="32" font-family="Times, serif" font-size="22">LedgerGuard Strong Evaluation Evidence Status</text>'
            f"{rows}</svg>\n",
            encoding="utf-8",
        )
        pdf_path.write_bytes(_simple_pdf("LedgerGuard Strong Evaluation Evidence Status", datasets))
        (out_dir / "fig_strong_eval_evidence_status.sidecar.json").write_text(
            '{"source_csv_dir":"results/csv","note":"Generated from current CSV files; fallback vector output without matplotlib."}\n',
            encoding="utf-8",
        )
        _write_device_workflow(out_dir)
        print(pdf_path)
        return 0

    status_order = ["measured", "executed", "configured", "scenario", "not_run", "recorded"]
    status_labels = {
        "measured": "collected",
        "executed": "executed",
        "configured": "configured",
        "scenario": "scenario",
        "not_run": "not run",
        "recorded": "recorded",
    }
    colors = {
        "measured": "#1F77B4",
        "executed": "#2CA02C",
        "configured": "#9467BD",
        "scenario": "#FF7F0E",
        "not_run": "#7F7F7F",
        "recorded": "#17BECF",
    }

    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    left = [0] * len(datasets)
    y = list(range(len(datasets)))
    for status in status_order:
        values = [counts.get(status, 0) for counts in statuses]
        if not any(values):
            continue
        ax.barh(y, values, left=left, label=status_labels.get(status, status), color=colors.get(status, "#333333"))
        left = [a + b for a, b in zip(left, values)]

    ax.set_yticks(y, datasets)
    ax.invert_yaxis()
    ax.set_xlabel("Rows")
    ax.set_title("LedgerGuard Strong Evaluation Evidence Status")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right", frameon=True)
    fig.tight_layout()

    for suffix in ("pdf", "svg", "png"):
        fig.savefig(out_dir / f"fig_strong_eval_evidence_status.{suffix}", dpi=300)
    plt.close(fig)
    (out_dir / "fig_strong_eval_evidence_status.sidecar.json").write_text(
        '{"source_csv_dir":"results/csv","note":"Generated from current CSV files."}\n',
        encoding="utf-8",
    )
    _write_device_workflow(out_dir)
    print(out_dir / "fig_strong_eval_evidence_status.pdf")
    return 0


def _simple_pdf(title: str, lines: list[str]) -> bytes:
    text_lines = [title, *lines[:24]]
    commands = ["BT", "/F1 18 Tf", "50 760 Td", f"({title}) Tj"]
    commands.extend(["/F1 11 Tf"])
    for line in text_lines[1:]:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.extend(["0 -18 Td", f"({safe}) Tj"])
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer << /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


def _write_device_workflow(out_dir: Path) -> None:
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="360">
<rect width="100%" height="100%" fill="white"/>
<text x="40" y="36" font-family="Times, serif" font-size="22">Device Update Workflow</text>
<text x="40" y="88" font-family="Times, serif" font-size="16">8. Run health checks / smoke tests</text>
<text x="40" y="136" font-family="Times, serif" font-size="16">9. Health checks passed?</text>
<text x="310" y="116" font-family="Times, serif" font-size="15">Yes: confirm slot B, emit SUCCESS receipt</text>
<text x="310" y="158" font-family="Times, serif" font-size="15">No: rollback to slot A or mark failure, emit ROLLBACK/FAIL receipt</text>
<text x="40" y="232" font-family="Times, serif" font-size="16">10. Aggregate receipts into Merkle tree and submit root + counters on-chain</text>
<path d="M245 132 L300 112" stroke="#174A7C" stroke-width="2" fill="none"/>
<path d="M245 140 L300 154" stroke="#A23A3A" stroke-width="2" fill="none"/>
<path d="M650 112 L650 220 L80 220" stroke="#174A7C" stroke-width="2" fill="none"/>
<path d="M730 154 L730 220 L80 220" stroke="#A23A3A" stroke-width="2" fill="none"/>
</svg>
'''
    (out_dir / "fig_device_update_workflow.svg").write_text(svg, encoding="utf-8")
    (out_dir / "fig_device_update_workflow.pdf").write_bytes(_simple_pdf("Device Update Workflow", [
        "8. Run health checks / smoke tests",
        "9. Health checks passed?",
        "Yes: confirm slot B, emit SUCCESS receipt",
        "No: rollback to slot A or mark failure, emit ROLLBACK/FAIL receipt",
        "10. Aggregate receipts into Merkle tree and submit root + counters on-chain",
    ]))
    (out_dir / "fig_device_update_workflow.sidecar.json").write_text(
        '{"source":"experiments/analysis/make_figures.py","note":"Corrected workflow logic with both branches going to receipt aggregation."}\n',
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
