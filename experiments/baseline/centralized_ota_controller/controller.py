#!/usr/bin/env python3
"""SQLite-backed centralized OTA baseline for LedgerGuard strong_eval.

This is intentionally not a blockchain replacement. It is a durable centralized
controller baseline with tables equivalent to the LedgerGuard release metadata,
approval, rollout, outcome, and append-only audit concepts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = Path(__file__).with_name("schema.sql")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_hash(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def audit(conn: sqlite3.Connection, operation: str, actor: str, release_id: int | None, payload: Dict[str, Any]) -> None:
    payload_json = json.dumps(payload, sort_keys=True)
    conn.execute(
        "INSERT INTO audit_log(ts_utc, operation, actor, release_id, payload_json, payload_hash) VALUES (?, ?, ?, ?, ?, ?)",
        (utc_now(), operation, actor, release_id, payload_json, stable_hash(payload)),
    )


def register_release(conn: sqlite3.Connection, payload: Dict[str, Any]) -> int:
    cur = conn.execute(
        """
        INSERT INTO releases(device_type, version, cid_fw, sha256_fw, size_bytes, sbom_hash, provenance_hash, status, created_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'PROPOSED', ?)
        """,
        (
            payload["device_type"],
            int(payload["version"]),
            payload["cid_fw"],
            payload["sha256_fw"],
            int(payload["size_bytes"]),
            payload["sbom_hash"],
            payload["provenance_hash"],
            utc_now(),
        ),
    )
    rid = int(cur.lastrowid)
    audit(conn, "register_release", payload.get("actor", "vendor"), rid, payload)
    return rid


def approve(conn: sqlite3.Connection, release_id: int, signer_role: str, signer_id: str, threshold: int = 2) -> str:
    conn.execute(
        "INSERT OR IGNORE INTO approvals(release_id, signer_role, signer_id, created_at_utc) VALUES (?, ?, ?, ?)",
        (release_id, signer_role, signer_id, utc_now()),
    )
    audit(conn, "approve_release", signer_role, release_id, {"signer_role": signer_role, "signer_id": signer_id})
    roles = {
        row["signer_role"]
        for row in conn.execute("SELECT signer_role FROM approvals WHERE release_id = ?", (release_id,))
    }
    status = "APPROVED" if len(roles) >= threshold else "PROPOSED"
    conn.execute("UPDATE releases SET status = ? WHERE release_id = ?", (status, release_id))
    return status


def start_rollout(conn: sqlite3.Connection, release_id: int, phase: str = "canary") -> None:
    status = conn.execute("SELECT status FROM releases WHERE release_id = ?", (release_id,)).fetchone()
    if not status or status["status"] != "APPROVED":
        raise RuntimeError("cannot start rollout for unapproved release")
    now = utc_now()
    conn.execute(
        "INSERT OR REPLACE INTO rollout_state(release_id, phase, started_at_utc, updated_at_utc) VALUES (?, ?, ?, ?)",
        (release_id, phase, now, now),
    )
    audit(conn, "start_rollout", "operator", release_id, {"phase": phase})


def submit_outcome(conn: sqlite3.Connection, release_id: int, epoch: int, merkle_root: str, success: int, fail: int, rollback: int) -> None:
    conn.execute(
        """
        INSERT INTO outcomes(release_id, epoch, merkle_root, success_count, fail_count, rollback_count, created_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (release_id, epoch, merkle_root, success, fail, rollback, utc_now()),
    )
    audit(
        conn,
        "submit_outcome",
        "operator",
        release_id,
        {"epoch": epoch, "merkle_root": merkle_root, "success": success, "fail": fail, "rollback": rollback},
    )


def reconstruct_audit(conn: sqlite3.Connection, release_id: int) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT audit_id, ts_utc, operation, actor, release_id, payload_hash FROM audit_log WHERE release_id = ? ORDER BY audit_id",
            (release_id,),
        )
    ]


def timed(operation: str, fn, raw_rows: List[Dict[str, Any]], csv_rows: List[Dict[str, Any]], db_path: Path, repetition: int) -> Any:
    start_ns = time.perf_counter_ns()
    start_utc = utc_now()
    result = fn()
    end_ns = time.perf_counter_ns()
    end_utc = utc_now()
    latency_ms = (end_ns - start_ns) / 1_000_000.0
    row = {
        "run_id": f"centralized_sqlite_rep{repetition:02d}",
        "repetition": repetition,
        "operation": operation,
        "metric_type": "centralized_sqlite_operation",
        "latency_ms": f"{latency_ms:.6f}",
        "start_ns": start_ns,
        "end_ns": end_ns,
        "timestamp_start_utc": start_utc,
        "timestamp_end_utc": end_utc,
        "database_path": str(db_path),
        "database_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "status": "success",
        "notes": "SQLite durable centralized baseline with append-only audit log.",
    }
    csv_rows.append(row)
    raw_rows.append({**row, "result": result})
    return result


def run(args: argparse.Namespace) -> None:
    out_csv = Path(args.csv)
    raw_dir = Path(args.raw)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for rep in range(1, args.repetitions + 1):
        db_path = raw_dir / f"centralized_rep{rep:02d}.sqlite"
        if db_path.exists():
            db_path.unlink()
        conn = connect(db_path)
        raw_rows: List[Dict[str, Any]] = []
        with conn:
            payload = {
                "actor": "vendor",
                "device_type": "M4",
                "version": rep,
                "cid_fw": f"bafybaseline{rep:04d}",
                "sha256_fw": hashlib.sha256(f"firmware-{rep}".encode()).hexdigest(),
                "size_bytes": args.artifact_size_bytes,
                "sbom_hash": hashlib.sha256(f"sbom-{rep}".encode()).hexdigest(),
                "provenance_hash": hashlib.sha256(f"provenance-{rep}".encode()).hexdigest(),
            }
            rid = timed("register_release", lambda: register_release(conn, payload), raw_rows, rows, db_path, rep)
            timed("security_approval", lambda: approve(conn, rid, "SECURITY", "security-1"), raw_rows, rows, db_path, rep)
            timed("regulator_approval", lambda: approve(conn, rid, "REGULATOR", "regulator-1"), raw_rows, rows, db_path, rep)
            timed("start_rollout", lambda: start_rollout(conn, rid), raw_rows, rows, db_path, rep)
            timed(
                "submit_outcome_batch",
                lambda: submit_outcome(conn, rid, 1, "0x" + hashlib.sha256(f"root-{rep}".encode()).hexdigest(), 980, 0, 20),
                raw_rows,
                rows,
                db_path,
                rep,
            )
            timed("audit_reconstruction", lambda: reconstruct_audit(conn, rid), raw_rows, rows, db_path, rep)
        with (raw_dir / f"centralized_rep{rep:02d}.jsonl").open("w", encoding="utf-8") as f:
            for row in raw_rows:
                f.write(json.dumps(row, sort_keys=True) + "\n")
        conn.close()

    columns = [
        "run_id", "repetition", "operation", "metric_type", "latency_ms", "start_ns", "end_ns",
        "timestamp_start_utc", "timestamp_end_utc", "database_path", "database_size_bytes", "status", "notes",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=int(os.environ.get("LEDGERGUARD_STRONG_REPETITIONS", "30")))
    parser.add_argument("--artifact-size-bytes", type=int, default=524288)
    parser.add_argument("--csv", default=str(ROOT / "results/csv/centralized_baseline.csv"))
    parser.add_argument("--raw", default=str(ROOT / "results/raw/centralized_baseline"))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
