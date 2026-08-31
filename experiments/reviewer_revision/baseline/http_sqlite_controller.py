#!/usr/bin/env python3
"""Persistent loopback HTTP/SQLite baseline for common LedgerGuard V2 semantics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = Path(__file__).with_name("schema.sql")
TOKENS = {
    "vendor-token": ("vendor-1", "VENDOR"),
    "security-token": ("security-1", "SECURITY"),
    "regulator-token": ("regulator-1", "REGULATOR"),
    "operator-token": ("operator-1", "OPERATOR"),
    "auditor-token": ("auditor-1", "AUDITOR"),
}


class BaselineError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA.read_text(encoding="utf-8"))
            for token, (actor_id, role) in TOKENS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO actors(actor_id, role, token_hash, active) VALUES (?, ?, ?, 1)",
                    (actor_id, role, digest(token)),
                )
            conn.execute(
                "INSERT OR IGNORE INTO policies(device_type, approval_threshold, success_threshold_bps) VALUES ('M4', 2, 9500)"
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def actor(conn: sqlite3.Connection, token: str, roles: set[str]) -> sqlite3.Row:
        row = conn.execute(
            "SELECT actor_id, role, active FROM actors WHERE token_hash = ?", (digest(token),)
        ).fetchone()
        if not row or not row["active"]:
            raise BaselineError(401, "inactive or unknown actor")
        if row["role"] not in roles:
            raise BaselineError(403, "actor role is not authorized")
        return row

    @staticmethod
    def audit(
        conn: sqlite3.Connection,
        actor_id: str,
        operation: str,
        release_id: int | None,
        payload: dict[str, Any],
    ) -> None:
        previous = conn.execute("SELECT record_hash FROM audit_log ORDER BY audit_id DESC LIMIT 1").fetchone()
        previous_hash = previous["record_hash"] if previous else "0" * 64
        occurred_at_ns = time.time_ns()
        payload_json = canonical_json(payload)
        record_hash = digest(
            canonical_json(
                {
                    "occurred_at_ns": occurred_at_ns,
                    "actor_id": actor_id,
                    "operation": operation,
                    "release_id": release_id,
                    "payload_json": payload_json,
                    "previous_hash": previous_hash,
                }
            )
        )
        conn.execute(
            "INSERT INTO audit_log(occurred_at_ns, actor_id, operation, release_id, payload_json, previous_hash, record_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (occurred_at_ns, actor_id, operation, release_id, payload_json, previous_hash, record_hash),
        )

    def register_release(self, token: str, body: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            actor = self.actor(conn, token, {"VENDOR"})
            cur = conn.execute(
                "INSERT INTO releases(device_type, version, cid, firmware_hash, sbom_hash, provenance_hash, created_by, created_at_ns) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    body["device_type"], body["version"], body["cid"], body["firmware_hash"],
                    body["sbom_hash"], body["provenance_hash"], actor["actor_id"], time.time_ns(),
                ),
            )
            release_id = int(cur.lastrowid)
            self.audit(conn, actor["actor_id"], "register_release", release_id, body)
            return {"release_id": release_id, "status": "PROPOSED"}

    def approve(self, token: str, release_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            actor = self.actor(conn, token, {"SECURITY", "REGULATOR"})
            try:
                conn.execute(
                    "INSERT INTO approvals(release_id, actor_id, role, created_at_ns) VALUES (?, ?, ?, ?)",
                    (release_id, actor["actor_id"], actor["role"], time.time_ns()),
                )
            except sqlite3.IntegrityError as exc:
                raise BaselineError(409, "duplicate or invalid approval") from exc
            row = conn.execute(
                "SELECT r.device_type, p.approval_threshold FROM releases r JOIN policies p USING(device_type) WHERE release_id = ?",
                (release_id,),
            ).fetchone()
            if not row:
                raise BaselineError(404, "release not found")
            count = conn.execute(
                "SELECT COUNT(DISTINCT role) AS count FROM approvals WHERE release_id = ?", (release_id,)
            ).fetchone()["count"]
            status = "APPROVED" if count >= row["approval_threshold"] else "PROPOSED"
            conn.execute("UPDATE releases SET status = ? WHERE release_id = ?", (status, release_id))
            self.audit(conn, actor["actor_id"], "approve_release", release_id, {"role": actor["role"], "status": status})
            return {"release_id": release_id, "approval_count": count, "status": status}

    def start_rollout(self, token: str, release_id: int, body: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            actor = self.actor(conn, token, {"OPERATOR"})
            row = conn.execute(
                "SELECT r.status, p.kill_switch FROM releases r JOIN policies p USING(device_type) WHERE release_id = ?",
                (release_id,),
            ).fetchone()
            if not row or row["status"] != "APPROVED":
                raise BaselineError(409, "release is not approved")
            if row["kill_switch"]:
                raise BaselineError(409, "kill switch is active")
            try:
                conn.execute(
                    "INSERT INTO rollouts(release_id, rollout_id, phase, transition_nonce, expected_count, updated_at_ns) "
                    "VALUES (?, ?, 'CANARY', 1, ?, ?)",
                    (release_id, body["rollout_id"], body["expected_count"], time.time_ns()),
                )
            except sqlite3.IntegrityError as exc:
                raise BaselineError(409, "rollout already exists") from exc
            self.audit(conn, actor["actor_id"], "start_rollout", release_id, body)
            return {"release_id": release_id, "phase": "CANARY", "transition_nonce": 1}

    def advance_rollout(self, token: str, release_id: int, body: dict[str, Any]) -> dict[str, Any]:
        next_phase = {"CANARY": "BATCH", "BATCH": "GLOBAL", "GLOBAL": "COMPLETED"}
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            actor = self.actor(conn, token, {"OPERATOR"})
            row = conn.execute(
                "SELECT ro.*, p.kill_switch, p.success_threshold_bps FROM rollouts ro "
                "JOIN releases r USING(release_id) JOIN policies p USING(device_type) WHERE release_id = ?",
                (release_id,),
            ).fetchone()
            if not row:
                raise BaselineError(404, "rollout not found")
            if row["kill_switch"]:
                raise BaselineError(409, "kill switch is active")
            if row["phase"] != body["expected_phase"] or row["transition_nonce"] != body["expected_nonce"]:
                raise BaselineError(409, "stale rollout transition")
            if row["phase"] not in next_phase:
                raise BaselineError(409, "rollout cannot advance")
            expected = sum(int(body[name]) for name in ("success", "rollback", "fail", "rejected", "missing"))
            if expected != row["expected_count"]:
                raise BaselineError(422, "outcome counts do not reconcile with expected cohort")
            success_bps = int(body["success"]) * 10000 // expected
            if success_bps < row["success_threshold_bps"]:
                raise BaselineError(409, "success threshold not met")
            phase = next_phase[row["phase"]]
            nonce = row["transition_nonce"] + 1
            conn.execute(
                "UPDATE rollouts SET phase = ?, transition_nonce = ?, updated_at_ns = ? WHERE release_id = ?",
                (phase, nonce, time.time_ns(), release_id),
            )
            self.audit(conn, actor["actor_id"], "advance_rollout", release_id, body | {"new_phase": phase})
            return {"release_id": release_id, "phase": phase, "transition_nonce": nonce}

    def activate_kill_switch(self, token: str, device_type: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            actor = self.actor(conn, token, {"SECURITY", "REGULATOR"})
            cur = conn.execute("UPDATE policies SET kill_switch = 1 WHERE device_type = ?", (device_type,))
            if cur.rowcount != 1:
                raise BaselineError(404, "device policy not found")
            self.audit(conn, actor["actor_id"], "activate_kill_switch", None, {"device_type": device_type})
            return {"device_type": device_type, "kill_switch": True}

    def propose_summary(self, token: str, release_id: int, body: dict[str, Any]) -> dict[str, Any]:
        fields = ("success_count", "rollback_count", "fail_count", "rejected_count")
        received = sum(int(body[name]) for name in fields)
        expected = received + int(body["missing_count"])
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            actor = self.actor(conn, token, {"OPERATOR"})
            rollout = conn.execute("SELECT * FROM rollouts WHERE release_id = ?", (release_id,)).fetchone()
            if not rollout or rollout["rollout_id"] != body["rollout_id"]:
                raise BaselineError(409, "rollout context mismatch")
            if expected != rollout["expected_count"] or body["expected_count"] != expected:
                raise BaselineError(422, "summary does not reconcile with expected cohort")
            if body["missing_count"] and time.time_ns() < body["deadline_ns"]:
                raise BaselineError(409, "missing outcomes cannot be finalized before deadline")
            last_epoch = conn.execute(
                "SELECT COALESCE(MAX(epoch), 0) AS epoch FROM outcome_summaries WHERE release_id = ?", (release_id,)
            ).fetchone()["epoch"]
            if body["epoch"] != last_epoch + 1:
                raise BaselineError(409, "epoch must be sequential")
            conn.execute(
                "INSERT INTO outcome_summaries("
                "release_id, epoch, rollout_id, cohort_id, cohort_commitment, deadline_ns, merkle_root, "
                "expected_count, received_count, success_count, rollback_count, fail_count, rejected_count, "
                "missing_count, aggregator_id, state, created_at_ns"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROPOSED', ?)",
                (
                    release_id, body["epoch"], body["rollout_id"], body["cohort_id"], body["cohort_commitment"],
                    body["deadline_ns"], body["merkle_root"], expected, received, body["success_count"],
                    body["rollback_count"], body["fail_count"], body["rejected_count"], body["missing_count"],
                    actor["actor_id"], time.time_ns(),
                ),
            )
            self.audit(conn, actor["actor_id"], "propose_outcome_summary", release_id, body)
            return {"release_id": release_id, "epoch": body["epoch"], "state": "PROPOSED"}

    def confirm_summary(self, token: str, release_id: int, epoch: int, body: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            actor = self.actor(conn, token, {"AUDITOR"})
            row = conn.execute(
                "SELECT * FROM outcome_summaries WHERE release_id = ? AND epoch = ?", (release_id, epoch)
            ).fetchone()
            if not row or row["state"] != "PROPOSED":
                raise BaselineError(409, "summary is not pending")
            compare = (
                "rollout_id", "cohort_id", "cohort_commitment", "deadline_ns", "merkle_root", "expected_count",
                "received_count", "success_count", "rollback_count", "fail_count", "rejected_count", "missing_count",
            )
            if any(row[name] != body.get(name) for name in compare):
                raise BaselineError(409, "witness summary does not match aggregator summary")
            if row["aggregator_id"] == actor["actor_id"]:
                raise BaselineError(409, "aggregator and witness must be distinct")
            conn.execute(
                "UPDATE outcome_summaries SET witness_id = ?, state = 'FINALIZED', finalized_at_ns = ? "
                "WHERE release_id = ? AND epoch = ?",
                (actor["actor_id"], time.time_ns(), release_id, epoch),
            )
            self.audit(conn, actor["actor_id"], "confirm_outcome_summary", release_id, body | {"epoch": epoch})
            return {"release_id": release_id, "epoch": epoch, "state": "FINALIZED"}

    def reconstruct_audit(self, token: str, release_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            self.actor(conn, token, {"AUDITOR"})
            rows = [dict(row) for row in conn.execute("SELECT * FROM audit_log ORDER BY audit_id")]
        previous_hash = "0" * 64
        valid = True
        for row in rows:
            expected = digest(
                canonical_json(
                    {
                        "occurred_at_ns": row["occurred_at_ns"], "actor_id": row["actor_id"],
                        "operation": row["operation"], "release_id": row["release_id"],
                        "payload_json": row["payload_json"], "previous_hash": previous_hash,
                    }
                )
            )
            valid = valid and row["previous_hash"] == previous_hash and row["record_hash"] == expected
            previous_hash = row["record_hash"]
        return {"release_id": release_id, "record_count": len(rows), "hash_chain_valid": valid}


class Handler(BaseHTTPRequestHandler):
    store: Store

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def respond(self, status: int, value: dict[str, Any]) -> None:
        payload = canonical_json(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        try:
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            parts = [part for part in self.path.split("?")[0].split("/") if part]
            if parts == ["releases"]:
                result = self.store.register_release(token, body)
            elif len(parts) == 3 and parts[0] == "releases" and parts[2] == "approvals":
                result = self.store.approve(token, int(parts[1]))
            elif len(parts) == 4 and parts[0] == "releases" and parts[2:] == ["rollout", "start"]:
                result = self.store.start_rollout(token, int(parts[1]), body)
            elif len(parts) == 4 and parts[0] == "releases" and parts[2:] == ["rollout", "advance"]:
                result = self.store.advance_rollout(token, int(parts[1]), body)
            elif len(parts) == 4 and parts[0] == "releases" and parts[2:] == ["outcomes", "propose"]:
                result = self.store.propose_summary(token, int(parts[1]), body)
            elif len(parts) == 5 and parts[0] == "releases" and parts[2] == "outcomes" and parts[4] == "confirm":
                result = self.store.confirm_summary(token, int(parts[1]), int(parts[3]), body)
            elif len(parts) == 3 and parts[0] == "device-types" and parts[2] == "kill-switch":
                result = self.store.activate_kill_switch(token, parts[1])
            else:
                raise BaselineError(404, "endpoint not found")
            self.respond(200, result)
        except BaselineError as exc:
            self.respond(exc.status, {"error": str(exc)})
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            self.respond(400, {"error": f"invalid request: {exc}"})
        except sqlite3.IntegrityError as exc:
            self.respond(409, {"error": f"state conflict: {exc}"})

    def do_GET(self) -> None:
        try:
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            parts = [part for part in self.path.split("?")[0].split("/") if part]
            if len(parts) == 3 and parts[0] == "releases" and parts[2] == "audit":
                self.respond(200, self.store.reconstruct_audit(token, int(parts[1])))
            else:
                raise BaselineError(404, "endpoint not found")
        except BaselineError as exc:
            self.respond(exc.status, {"error": str(exc)})


def request(base_url: str, method: str, path: str, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = canonical_json(body or {}).encode("utf-8") if method == "POST" else None
    req = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return {"status_code": response.status, "body": json.loads(response.read())}
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read())
        exc.close()
        return {"status_code": exc.code, "body": payload}


def run_experiment(args: argparse.Namespace) -> None:
    db_path = Path(args.database)
    if db_path.exists():
        db_path.unlink()
    store = Store(db_path)
    Handler.store = store
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    rows: list[dict[str, Any]] = []
    raw_path = Path(args.raw)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    def timed(rep: int, operation: str, method: str, path: str, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        start_ns = time.perf_counter_ns()
        result = request(base_url, method, path, token, body)
        end_ns = time.perf_counter_ns()
        row = {
            "run_id": f"http_sqlite_v2_rep{rep:03d}", "repetition": rep, "operation": operation,
            "start_ns": start_ns, "end_ns": end_ns, "latency_ms": (end_ns - start_ns) / 1_000_000,
            "http_status": result["status_code"], "status": "success" if result["status_code"] < 400 else "failed",
            "database_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
            "evidence_type": "local_persistent_backend_measurement",
        }
        rows.append(row)
        with raw_path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(row | {"response": result["body"]}) + "\n")
        if result["status_code"] >= 400:
            raise RuntimeError(f"{operation} failed: {result}")
        return result["body"]

    try:
        for rep in range(1, args.repetitions + 1):
            release = timed(
                rep, "register_release", "POST", "/releases", "vendor-token",
                {
                    "device_type": "M4", "version": rep, "cid": f"bafy-v2-{rep:04d}",
                    "firmware_hash": digest(f"firmware-{rep}"), "sbom_hash": digest(f"sbom-{rep}"),
                    "provenance_hash": digest(f"provenance-{rep}"),
                },
            )
            release_id = release["release_id"]
            timed(rep, "security_approval", "POST", f"/releases/{release_id}/approvals", "security-token")
            timed(rep, "regulator_approval", "POST", f"/releases/{release_id}/approvals", "regulator-token")
            rollout_id = f"rollout-{rep:04d}"
            timed(
                rep, "start_rollout", "POST", f"/releases/{release_id}/rollout/start", "operator-token",
                {"rollout_id": rollout_id, "expected_count": 1000},
            )
            summary = {
                "rollout_id": rollout_id, "cohort_id": f"cohort-{rep:04d}",
                "cohort_commitment": digest(f"cohort-{rep}"), "deadline_ns": time.time_ns(),
                "merkle_root": digest(f"root-{rep}"), "expected_count": 1000, "received_count": 980,
                "success_count": 970, "rollback_count": 5, "fail_count": 3, "rejected_count": 2,
                "missing_count": 20,
            }
            timed(
                rep, "propose_outcome_summary", "POST", f"/releases/{release_id}/outcomes/propose",
                "operator-token", summary | {"epoch": 1},
            )
            timed(
                rep, "confirm_outcome_summary", "POST", f"/releases/{release_id}/outcomes/1/confirm",
                "auditor-token", summary,
            )
            timed(rep, "audit_reconstruction", "GET", f"/releases/{release_id}/audit", "auditor-token")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=50)
    parser.add_argument(
        "--database", default=str(ROOT / "results/reviewer_revision/raw/baseline/http_sqlite_v2.sqlite")
    )
    parser.add_argument(
        "--raw", default=str(ROOT / "results/reviewer_revision/raw/baseline/http_sqlite_v2.jsonl")
    )
    parser.add_argument(
        "--csv", default=str(ROOT / "results/reviewer_revision/csv/http_sqlite_v2_timing.csv")
    )
    run_experiment(parser.parse_args())


if __name__ == "__main__":
    main()
