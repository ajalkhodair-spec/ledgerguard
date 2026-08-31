#!/usr/bin/env python3
"""Build the public sample, checksums, manifest, and full reviewer evidence archive."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from experiments.reviewer_revision.revision_manifest import build_manifest, git_state, CAMPAIGNS


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results" / "reviewer_revision"
SAMPLE = ROOT / "results_sample"
RELEASE = ROOT / "release"
ARCHIVE = RELEASE / "LedgerGuard_Reviewer_Revision_Evidence.zip"
PACKAGE_ROOTS = (
    ROOT / "contracts" / "src",
    ROOT / "contracts" / "test",
    ROOT / "docs",
    ROOT / "experiments" / "reviewer_revision",
    ROOT / "experiments" / "configs",
    ROOT / "scripts",
    ROOT / "runner",
    ROOT / "paper_assets" / "reviewer_revision",
    RESULTS,
)
EXCLUDED_NAMES = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc"}
REPRODUCTION_FILES = (
    "README.md", "REPRODUCIBILITY.md", "requirements.txt", "requirements-reviewer.txt",
    "contracts/foundry.toml", "docker-compose.yml", ".env.example", "poc",
    "LICENSE", "CITATION.cff",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "uncommitted"


def traceability() -> dict:
    fingerprint = json.loads((RESULTS / "validation/protocol_fingerprint.json").read_text())
    freeze = json.loads((RESULTS / "validation/evidence_freeze_status.json").read_text())
    if fingerprint["status"] != "PASS" or freeze["status"] != "PASS":
        raise RuntimeError("technical evidence checks must pass before packaging")
    return {
        "protocol_version": fingerprint["protocol_version"],
        "receipt_schema_version": fingerprint["receipt_schema_version"],
        "source_set_sha256": fingerprint["source_set_sha256"],
        "git_commit_at_execution": fingerprint["git_commit_at_execution"],
        "git_freeze_status": git_state()["status"],
        "revision_commit": git_state()["revision_commit"],
        "fingerprint_capture_git_status": fingerprint["git_freeze_status"],
        "verification_type": fingerprint["verification_type"],
        "linked_timing_rows": fingerprint["linked_timing_rows"],
        "contracts": fingerprint["contracts"],
        "fingerprint_path": "results/reviewer_revision/validation/protocol_fingerprint.json",
        "fingerprint_sha256": sha256(RESULTS / "validation/protocol_fingerprint.json"),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def copy_json(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(source.read_text(encoding="utf-8"))
    destination.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_public_sample() -> None:
    if SAMPLE.exists():
        shutil.rmtree(SAMPLE)
    SAMPLE.mkdir(parents=True)

    fieldnames, rows = read_csv(RESULTS / "csv" / "besu_v2_final_timing_complete.csv")
    run_id = rows[0]["run_id"]
    write_csv(SAMPLE / "besu" / "control_plane_run.csv", fieldnames, [row for row in rows if row["run_id"] == run_id])

    fieldnames, rows = read_csv(RESULTS / "csv" / "http_sqlite_v2_timing.csv")
    baseline_run = rows[0]["run_id"]
    write_csv(SAMPLE / "baseline" / "http_sqlite_run.csv", fieldnames, [row for row in rows if row["run_id"] == baseline_run])

    fieldnames, rows = read_csv(RESULTS / "csv" / "fleet_multiseed_runs.csv")
    fleet = next(row for row in rows if row["fleet_size"] == "100" and row["configured_failure_rate"] == "0.02")
    write_csv(SAMPLE / "fleet" / "fleet_run.csv", fieldnames, [fleet])
    source_receipts = ROOT / fleet["raw_evidence_path"] / "receipts.jsonl"
    (SAMPLE / "fleet" / "receipts.jsonl").write_bytes(source_receipts.read_bytes())

    fieldnames, rows = read_csv(RESULTS / "csv" / "aggregation_completeness_tests.csv")
    write_csv(SAMPLE / "completeness" / "aggregation_cases.csv", fieldnames, rows)
    copy_json(
        RESULTS / "raw" / "completeness" / "selective_omission_denominator.json",
        SAMPLE / "completeness" / "selective_omission_denominator.json",
    )

    fieldnames, rows = read_csv(RESULTS / "statistics" / "gas_summary_final.csv")
    gas_rows = [next(row for row in rows if row["category"] == category) for category in ("deployment", "operation")]
    write_csv(SAMPLE / "gas" / "gas_examples.csv", fieldnames, gas_rows)
    copy_json(RESULTS / "validation" / "validation_report.json", SAMPLE / "validation" / "validation_report.json")

    readme = """# Public Evidence Sample

This compact sample is derived from the preserved reviewer-revision evidence. It includes one successful local Besu control-plane run, one HTTP/SQLite comparison run, one authenticated software-fleet run with signed receipts, all completeness cases, the selective-omission case, gas examples, and the consolidated validation report.

The full raw evidence archive is generated locally with `python experiments/reviewer_revision/generate_evidence_package.py` and is intentionally excluded from Git because it contains large execution artifacts. No physical-device or production-deployment evidence is claimed.

This sample retains generation-time provenance. Its generation can precede the final revision commit; the full release manifest additionally binds the archived sample bytes to that later checkpoint.
"""
    (SAMPLE / "README.md").write_text(readme, encoding="utf-8")

    generated_at = now_utc()
    commit = git_commit()
    entries = []
    for path in sorted(SAMPLE.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            entries.append({
                "path": path.relative_to(SAMPLE).as_posix(),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
                "generated_at_utc": generated_at,
                "source_command": "python experiments/reviewer_revision/generate_evidence_package.py",
                "git_commit": commit,
                "evidence_type": "public_representative_sample",
            })
    manifest = {
        "schema_version": 1,
        "generated_at_utc": generated_at,
        "git_commit": commit,
        "source_traceability": traceability(),
        "files": entries,
    }
    (SAMPLE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def package_files() -> list[Path]:
    files: list[Path] = [ROOT / name for name in REPRODUCTION_FILES]
    for base in PACKAGE_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix in EXCLUDED_SUFFIXES:
                continue
            if any(part in EXCLUDED_NAMES for part in path.parts):
                continue
            files.append(path)
    files.extend(path for path in SAMPLE.rglob("*") if path.is_file())
    return sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())


def build_full_archive(require_frozen: bool = False) -> None:
    RELEASE.mkdir(parents=True, exist_ok=True)
    files = package_files()
    generated_at = now_utc()
    commit = git_commit()
    manifest_entries = []
    checksum_lines = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        digest = sha256(path)
        checksum_lines.append(f"{digest}  {relative}")
        manifest_entries.append({
            "path": relative,
            "sha256": digest,
            "size_bytes": path.stat().st_size,
            "generated_at_utc": generated_at,
            "source_command": "scripts/reproduce_reviewer_revision.sh --full",
            "git_commit": commit,
            "evidence_type": "reviewer_revision_evidence",
        })
    (RELEASE / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    full_manifest = {
        "schema_version": 1,
        "generated_at_utc": generated_at,
        "git_commit": commit,
        "source_traceability": traceability(),
        "campaigns": CAMPAIGNS,
        "file_count": len(manifest_entries),
        "files": manifest_entries,
    }
    manifest_path = RELEASE / "evidence_manifest.json"
    manifest_path.write_text(json.dumps(full_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    revision_path = RELEASE / "revision-v2-evidence-manifest.json"
    revision_path.write_text(json.dumps(build_manifest(manifest_entries, require_frozen), indent=2, sort_keys=True) + "\n")
    checksum_lines.extend(f"{sha256(path)}  {path.name}" for path in (manifest_path, revision_path))
    # The root-level manifest checksums are intended for the extracted archive.
    archive_checksums = "\n".join(checksum_lines) + "\n"
    (RELEASE / "SHA256SUMS").write_text("\n".join(
        line if index < len(manifest_entries) else line.replace("  ", "  release/", 1)
        for index, line in enumerate(checksum_lines)) + "\n")

    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr("SHA256SUMS", archive_checksums)
        archive.write(manifest_path, "evidence_manifest.json")
        archive.write(revision_path, revision_path.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preserve-public-sample", action="store_true")
    parser.add_argument("--require-frozen", action="store_true")
    args = parser.parse_args()
    if args.require_frozen and not args.preserve_public_sample:
        parser.error("--require-frozen requires --preserve-public-sample to keep the committed worktree unchanged")
    if args.require_frozen:
        from experiments.reviewer_revision.validate_evidence_freeze import verify
        verify()
    if not args.preserve_public_sample:
        build_public_sample()
    build_full_archive(args.require_frozen)
    print(
        json.dumps(
            {
                "status": "PASS",
                "public_sample": str(SAMPLE.relative_to(ROOT)),
                "archive": str(ARCHIVE.relative_to(ROOT)),
                "archive_sha256": sha256(ARCHIVE),
                "archive_size_bytes": ARCHIVE.stat().st_size,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
