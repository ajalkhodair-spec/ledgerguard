#!/usr/bin/env python3
"""Generate PoC results tables/figures from out/ artifacts.

This script is deterministic and uses only the Python stdlib plus matplotlib.

Inputs:
  - /out/metrics.json
  - /out/outcomes_epoch_*.json

Outputs:
  - /out/results.md
  - /out/fig_approval_latency.(png|svg)
  - /out/fig_rollout_success.(png|svg)
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(headers: List[str], rows: List[List[Any]]) -> str:
    # Markdown table generator
    def esc(x: Any) -> str:
        s = str(x)
        return s.replace("\n", " ").replace("|", "\\|")

    header_line = "| " + " | ".join(map(esc, headers)) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = ["| " + " | ".join(map(esc, r)) + " |" for r in rows]
    return "\n".join([header_line, sep_line] + body_lines)


def _write_bar_svg(path: Path, labels: List[str], values: List[float], title: str, ylabel: str) -> None:
    # Minimal, dependency-free SVG bar chart.
    w, h = 640, 360
    pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 50
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    vmax = max(values) if values else 1.0
    vmax = vmax if vmax > 0 else 1.0

    bar_w = chart_w / max(len(values), 1)
    # Slight gap between bars
    gap = bar_w * 0.15
    bar_inner_w = max(bar_w - gap, 1)

    def y(v: float) -> float:
        return pad_t + chart_h * (1.0 - (v / vmax))

    parts: List[str] = []
    parts.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}'>")
    parts.append(f"<text x='{w/2}' y='24' text-anchor='middle' font-family='sans-serif' font-size='16'>{title}</text>")
    # Axes
    x0, y0 = pad_l, pad_t + chart_h
    parts.append(f"<line x1='{x0}' y1='{pad_t}' x2='{x0}' y2='{y0}' stroke='black' stroke-width='1'/>")
    parts.append(f"<line x1='{x0}' y1='{y0}' x2='{pad_l+chart_w}' y2='{y0}' stroke='black' stroke-width='1'/>")
    # Y label
    parts.append(
        f"<text x='16' y='{h/2}' text-anchor='middle' font-family='sans-serif' font-size='12' transform='rotate(-90 16 {h/2})'>{ylabel}</text>"
    )

    for i, (lab, val) in enumerate(zip(labels, values)):
        x = pad_l + i * bar_w + gap / 2
        y_top = y(val)
        height = (pad_t + chart_h) - y_top
        parts.append(f"<rect x='{x}' y='{y_top}' width='{bar_inner_w}' height='{height}' fill='#4c78a8'/>")
        parts.append(f"<text x='{x + bar_inner_w/2}' y='{y0 + 18}' text-anchor='middle' font-family='sans-serif' font-size='11'>{lab}</text>")
        parts.append(f"<text x='{x + bar_inner_w/2}' y='{y_top - 6}' text-anchor='middle' font-family='sans-serif' font-size='11'>{val:.2f}</text>")

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def _write_line_svg(
    path: Path,
    xs: List[int],
    series: List[Tuple[str, List[float]]],
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    # Minimal SVG line chart. Uses a small fixed palette.
    w, h = 640, 360
    pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 50
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b

    all_vals = [v for _, ys in series for v in ys]
    vmin = min(all_vals) if all_vals else 0.0
    vmax = max(all_vals) if all_vals else 1.0
    if vmax == vmin:
        vmax = vmin + 1.0

    xmin = min(xs) if xs else 0
    xmax = max(xs) if xs else 1
    if xmax == xmin:
        xmax = xmin + 1

    def x_map(x: int) -> float:
        return pad_l + chart_w * ((x - xmin) / (xmax - xmin))

    def y_map(v: float) -> float:
        return pad_t + chart_h * (1.0 - ((v - vmin) / (vmax - vmin)))

    palette = ["#4c78a8", "#f58518", "#54a24b", "#e45756"]

    parts: List[str] = []
    parts.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}'>")
    parts.append(f"<text x='{w/2}' y='24' text-anchor='middle' font-family='sans-serif' font-size='16'>{title}</text>")

    # Axes
    x0, y0 = pad_l, pad_t + chart_h
    parts.append(f"<line x1='{x0}' y1='{pad_t}' x2='{x0}' y2='{y0}' stroke='black' stroke-width='1'/>")
    parts.append(f"<line x1='{x0}' y1='{y0}' x2='{pad_l+chart_w}' y2='{y0}' stroke='black' stroke-width='1'/>")
    # Labels
    parts.append(
        f"<text x='{w/2}' y='{h-12}' text-anchor='middle' font-family='sans-serif' font-size='12'>{xlabel}</text>"
    )
    parts.append(
        f"<text x='16' y='{h/2}' text-anchor='middle' font-family='sans-serif' font-size='12' transform='rotate(-90 16 {h/2})'>{ylabel}</text>"
    )

    # X ticks
    for x in xs:
        px = x_map(x)
        parts.append(f"<line x1='{px}' y1='{y0}' x2='{px}' y2='{y0+4}' stroke='black' stroke-width='1'/>")
        parts.append(f"<text x='{px}' y='{y0+18}' text-anchor='middle' font-family='sans-serif' font-size='11'>{x}</text>")

    # Series
    for idx, (name, ys) in enumerate(series):
        color = palette[idx % len(palette)]
        pts = [(x_map(x), y_map(float(y))) for x, y in zip(xs, ys)]
        d = "M " + " L ".join([f"{px:.1f} {py:.1f}" for px, py in pts])
        parts.append(f"<path d='{d}' fill='none' stroke='{color}' stroke-width='2'/>")
        for px, py in pts:
            parts.append(f"<circle cx='{px:.1f}' cy='{py:.1f}' r='3' fill='{color}'/>")
        # Legend item
        lx, ly = pad_l + chart_w - 140, pad_t + 20 + idx * 18
        parts.append(f"<rect x='{lx}' y='{ly-10}' width='12' height='12' fill='{color}'/>")
        parts.append(f"<text x='{lx+18}' y='{ly}' font-family='sans-serif' font-size='12'>{name}</text>")

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def try_make_figures(out_dir: Path, metrics: Dict[str, Any], outcomes: List[Dict[str, Any]]) -> None:
    """Create figures.

    - Prefers matplotlib if available (PNG output).
    - Falls back to dependency-free SVG output.
    """
    have_matplotlib = False
    plt = None
    try:
        import matplotlib.pyplot as _plt  # type: ignore

        plt = _plt
        have_matplotlib = True
    except Exception:
        have_matplotlib = False

    # Figure 1: Approval latency (register -> final approval)
    reg_ms = metrics.get("t_register_ms")
    appr_ms = metrics.get("t_final_approval_ms")
    if isinstance(reg_ms, int) and isinstance(appr_ms, int) and appr_ms >= reg_ms:
        latency_s = (appr_ms - reg_ms) / 1000.0
        if have_matplotlib and plt is not None:
            plt.figure()
            plt.bar(["approval"], [latency_s])
            plt.ylabel("Seconds")
            plt.title("Governance approval latency")
            plt.tight_layout()
            plt.savefig(out_dir / "fig_approval_latency.png", dpi=200)
            plt.close()
        else:
            _write_bar_svg(out_dir / "fig_approval_latency.svg", ["approval"], [latency_s], "Governance approval latency", "Seconds")

    # Figure 2: Rollout outcomes per epoch
    if outcomes:
        epochs = [o["epoch"] for o in outcomes]
        success = [o.get("success", 0) for o in outcomes]
        rollback = [o.get("rollback", 0) for o in outcomes]
        if have_matplotlib and plt is not None:
            plt.figure()
            plt.plot(epochs, success, marker="o", label="SUCCESS")
            plt.plot(epochs, rollback, marker="o", label="ROLLBACK")
            plt.xlabel("Epoch")
            plt.ylabel("Count")
            plt.title("Install outcomes per epoch")
            plt.legend()
            plt.tight_layout()
            plt.savefig(out_dir / "fig_rollout_success.png", dpi=200)
            plt.close()
        else:
            _write_line_svg(
                out_dir / "fig_rollout_success.svg",
                [int(x) for x in epochs],
                [("SUCCESS", [float(v) for v in success]), ("ROLLBACK", [float(v) for v in rollback])],
                "Install outcomes per epoch",
                "Epoch",
                "Count",
            )


def main() -> None:
    out_dir = Path("/out")
    metrics_path = out_dir / "metrics.json"
    if not metrics_path.exists():
        raise SystemExit("metrics.json not found; run the experiment first")

    metrics = load_json(metrics_path)

    outcome_files = sorted(glob.glob(str(out_dir / "outcomes_epoch_*.json")))
    outcomes = [load_json(Path(f)) for f in outcome_files]

    # Tables
    reg_ms = metrics.get("t_register_ms")
    appr_ms = metrics.get("t_final_approval_ms")
    rollout_started_ms = metrics.get("t_rollout_started_ms")

    gov_rows: List[List[Any]] = []
    if isinstance(reg_ms, int):
        gov_rows.append(["registerRelease", reg_ms])
    if isinstance(appr_ms, int):
        gov_rows.append(["final approval", appr_ms])
    if isinstance(rollout_started_ms, int):
        gov_rows.append(["startRollout", rollout_started_ms])

    approval_latency_s = None
    if isinstance(reg_ms, int) and isinstance(appr_ms, int) and appr_ms >= reg_ms:
        approval_latency_s = (appr_ms - reg_ms) / 1000.0

    rollout_rows: List[List[Any]] = []
    for o in outcomes:
        # simulator writes n_receipts; keep backwards compatibility with older key name.
        n = int(o.get("n_receipts", o.get("receipts", 0)))
        succ = int(o.get("success", 0))
        fail = int(o.get("fail", 0))
        rb = int(o.get("rollback", 0))
        succ_rate = (succ / n) if n else 0.0
        rollout_rows.append([
            o.get("epoch"),
            o.get("rollout_percent"),
            n,
            succ,
            fail,
            rb,
            f"{succ_rate:.3f}",
            o.get("merkle_root"),
        ])

    # Write markdown
    md = []
    md.append("# LedgerGuard PoC Results (Auto-generated)\n")
    md.append("## Governance timing summary\n")
    if approval_latency_s is not None:
        md.append(f"Approval latency (register → threshold-approved): **{approval_latency_s:.2f} s**\n")
    md.append(md_table(["Step", "Timestamp (ms since epoch)"], gov_rows) + "\n")

    md.append("## Rollout outcome summary\n")
    if rollout_rows:
        md.append(md_table(
            ["Epoch", "% rollout", "Receipts", "Success", "Fail", "Rollback", "Success rate", "Merkle root"],
            rollout_rows,
        ) + "\n")
    else:
        md.append("No outcomes_epoch_*.json files found.\n")

    # Optional: fleet adoption snapshot (from simulated device state)
    meta_path = out_dir / "release_metadata.json"
    state_path = out_dir / "device_state.json"
    fleet_size = metrics.get("fleet_size")
    if meta_path.exists() and state_path.exists() and isinstance(fleet_size, int) and fleet_size > 0:
        try:
            meta = load_json(meta_path)
            state = load_json(state_path)
            target_version = int(meta.get("version", 0))
            updated = 0
            if isinstance(state, dict):
                for _, v in state.items():
                    try:
                        if int(v) >= target_version:
                            updated += 1
                    except Exception:
                        continue
            adoption = updated / float(fleet_size)
            md.append("## Fleet adoption snapshot\n")
            md.append(
                f"Devices at version ≥ {target_version}: **{updated}/{fleet_size} ({adoption*100:.2f}%)**\n"
            )
        except Exception:
            # Keep results generation robust; adoption snapshot is optional.
            pass

    # Optional: adversarial suite summary
    adv_path = out_dir / "adversarial.json"
    if adv_path.exists():
        adv = load_json(adv_path)
        tests = adv.get("tests", [])
        md.append("## Adversarial validation summary\n")
        if isinstance(tests, list) and tests:
            rows = []
            for t in tests:
                rows.append([
                    t.get("name"),
                    "PASS" if t.get("passed") else "FAIL",
                    t.get("details", ""),
                    t.get("evidence", ""),
                ])
            md.append(md_table(["Test", "Result", "Details", "Evidence"], rows) + "\n")
        else:
            md.append("adversarial.json present but contains no tests.\n")

    md.append("## Artifact integrity checks\n")
    md.append("This PoC verifies firmware payload integrity via sha256 and anchors the content address (IPFS CID) and hashes on-chain.\n")

    # Save
    results_path = out_dir / "results.md"
    results_path.write_text("\n".join(md), encoding="utf-8")

    # Figures
    try_make_figures(out_dir, metrics, outcomes)

    print(f"Wrote {results_path}")


if __name__ == "__main__":
    main()
