from __future__ import annotations

import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from experiments.reviewer_revision.baseline.http_sqlite_controller import Handler, Store, digest, request


class HttpSqliteControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "baseline.sqlite")
        Handler.store = self.store
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def post(self, path: str, token: str, body: dict | None = None) -> dict:
        return request(self.base, "POST", path, token, body)

    def create_approved_rollout(self, version: int = 1) -> int:
        created = self.post(
            "/releases", "vendor-token",
            {
                "device_type": "M4", "version": version, "cid": f"cid-{version}",
                "firmware_hash": digest(f"fw-{version}"), "sbom_hash": digest(f"sbom-{version}"),
                "provenance_hash": digest(f"prov-{version}"),
            },
        )
        release_id = created["body"]["release_id"]
        self.assertEqual(self.post(f"/releases/{release_id}/approvals", "security-token")["status_code"], 200)
        self.assertEqual(self.post(f"/releases/{release_id}/approvals", "regulator-token")["status_code"], 200)
        started = self.post(
            f"/releases/{release_id}/rollout/start", "operator-token",
            {"rollout_id": f"rollout-{version}", "expected_count": 100},
        )
        self.assertEqual(started["status_code"], 200)
        return release_id

    def test_unauthorized_actor_cannot_approve(self) -> None:
        created = self.post(
            "/releases", "vendor-token",
            {
                "device_type": "M4", "version": 1, "cid": "cid", "firmware_hash": digest("fw"),
                "sbom_hash": digest("sbom"), "provenance_hash": digest("prov"),
            },
        )
        result = self.post(f"/releases/{created['body']['release_id']}/approvals", "operator-token")
        self.assertEqual(result["status_code"], 403)

    def test_duplicate_approval_is_rejected(self) -> None:
        release_id = self.create_approved_rollout()
        result = self.post(f"/releases/{release_id}/approvals", "security-token")
        self.assertEqual(result["status_code"], 409)

    def test_stale_transition_is_rejected(self) -> None:
        release_id = self.create_approved_rollout()
        counts = {"success": 98, "rollback": 1, "fail": 1, "rejected": 0, "missing": 0}
        first = self.post(
            f"/releases/{release_id}/rollout/advance", "operator-token",
            counts | {"expected_phase": "CANARY", "expected_nonce": 1},
        )
        self.assertEqual(first["status_code"], 200)
        stale = self.post(
            f"/releases/{release_id}/rollout/advance", "operator-token",
            counts | {"expected_phase": "CANARY", "expected_nonce": 1},
        )
        self.assertEqual(stale["status_code"], 409)

    def test_missing_devices_are_in_success_denominator(self) -> None:
        release_id = self.create_approved_rollout()
        result = self.post(
            f"/releases/{release_id}/rollout/advance", "operator-token",
            {
                "expected_phase": "CANARY", "expected_nonce": 1, "success": 90,
                "rollback": 0, "fail": 0, "rejected": 0, "missing": 10,
            },
        )
        self.assertEqual(result["status_code"], 409)

    def test_kill_switch_blocks_advance(self) -> None:
        release_id = self.create_approved_rollout()
        self.assertEqual(self.post("/device-types/M4/kill-switch", "security-token")["status_code"], 200)
        result = self.post(
            f"/releases/{release_id}/rollout/advance", "operator-token",
            {
                "expected_phase": "CANARY", "expected_nonce": 1, "success": 98,
                "rollback": 1, "fail": 1, "rejected": 0, "missing": 0,
            },
        )
        self.assertEqual(result["status_code"], 409)

    def test_witness_mismatch_is_rejected(self) -> None:
        release_id = self.create_approved_rollout()
        summary = {
            "rollout_id": "rollout-1", "cohort_id": "cohort-1", "cohort_commitment": digest("cohort"),
            "deadline_ns": time.time_ns(), "merkle_root": digest("root"), "expected_count": 100,
            "received_count": 100, "success_count": 98, "rollback_count": 1, "fail_count": 1,
            "rejected_count": 0, "missing_count": 0,
        }
        proposed = self.post(
            f"/releases/{release_id}/outcomes/propose", "operator-token", summary | {"epoch": 1}
        )
        self.assertEqual(proposed["status_code"], 200)
        mismatch = self.post(
            f"/releases/{release_id}/outcomes/1/confirm", "auditor-token",
            summary | {"success_count": 99, "fail_count": 0},
        )
        self.assertEqual(mismatch["status_code"], 409)


if __name__ == "__main__":
    unittest.main()
