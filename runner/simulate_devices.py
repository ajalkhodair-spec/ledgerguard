#!/usr/bin/env python3
"""LedgerGuard PoC device-fleet simulator (Option-0: Mac-only).

This simulator models the device-side update agent logic for heterogeneous fleets
in a way that's reproducible and fast enough for ~1,000 device instances.

Inputs:
  - out/release_metadata.json  (written by run_experiment.sh)

Outputs (written into out/):
  - receipts_epoch_<N>.jsonl         per-device receipts for the epoch
  - outcomes_epoch_<N>.json          success/fail counts and Merkle root
  - proof_epoch_<N>.json             one sample inclusion proof
  - timings_epoch_<N>.json           verification + fetch timings

No external Python dependencies are required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from merkle import sha256, merkle_root, merkle_proof, verify_proof


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def http_get_bytes(url: str, timeout_s: float = 30.0) -> bytes:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read()


def should_update(device_id: str, release_id: int, percent: int) -> bool:
    # Deterministic eligibility function: sha256(device_id || release_id) mod 100.
    h = hashlib.sha256(f"{device_id}:{release_id}".encode("utf-8")).digest()
    v = int.from_bytes(h[:4], "big") % 100
    return v < percent


def simulate_epoch(
    *,
    out_dir: Path,
    epoch: int,
    n_devices: int,
    rollout_percent: int,
    fail_rate: float,
    seed: int,
    ipfs_gateway: str,
    cid: str,
    expected_sha256_hex: str,
    release_id: int,
    target_version: int,
    device_type: str,
    state: Dict[str, int],
    emit_rejects: bool,
) -> Dict[str, Any]:
    rng = random.Random(seed)

    # Fetch payload once (models: edge cache hit for subsequent devices).
    t0 = time.time()
    payload_url = f"{ipfs_gateway.rstrip('/')}/ipfs/{cid}"
    payload = http_get_bytes(payload_url)
    fetch_s = time.time() - t0

    t1 = time.time()
    sha_hex = hashlib.sha256(payload).hexdigest()
    verify_hash_s = time.time() - t1

    if sha_hex.lower() != expected_sha256_hex.lower():
        raise RuntimeError(
            f"Payload hash mismatch: expected {expected_sha256_hex}, got {sha_hex}"
        )

    receipts_path = out_dir / f"receipts_epoch_{epoch}.jsonl"
    receipts_f = receipts_path.open("w", encoding="utf-8")

    leaves: List[bytes] = []
    success = 0
    fail = 0
    rollback = 0

    for i in range(n_devices):
        device_id = f"{device_type}-{i:06d}"
        eligible = should_update(device_id, release_id, rollout_percent)

        if not eligible:
            # Not participating this epoch.
            continue

        # Anti-rollback / idempotence model:
        # - If device already has target_version, it skips.
        # - If device has a *newer* version than target, it rejects (rollback attempt).
        current_version = int(state.get(device_id, 0))
        if current_version >= target_version:
            if emit_rejects and current_version > target_version:
                status = "REJECTED_ROLLBACK"
                fail += 1
                receipt = {
                    "device_id": device_id,
                    "device_type": device_type,
                    "release_id": release_id,
                    "target_version": target_version,
                    "current_version": current_version,
                    "status": status,
                    "ts": int(time.time() * 1000),
                }
                rbytes = canonical_json_bytes(receipt)
                leaf = sha256(rbytes)
                leaves.append(leaf)
                receipts_f.write(json.dumps(receipt) + "\n")
            continue

        # Simulate A/B state machine outcomes.
        # - With probability fail_rate: stage or post-install fails => rollback
        # - Otherwise success (and device state moves forward)
        is_fail = rng.random() < fail_rate

        if is_fail:
            status = "ROLLBACK"
            rollback += 1
        else:
            status = "SUCCESS"
            success += 1
            state[device_id] = target_version

        receipt = {
            "device_id": device_id,
            "device_type": device_type,
            "release_id": release_id,
            "target_version": target_version,
            "current_version": current_version,
            "status": status,
            "ts": int(time.time() * 1000),
        }

        rbytes = canonical_json_bytes(receipt)
        leaf = sha256(rbytes)
        leaves.append(leaf)
        receipts_f.write(json.dumps(receipt) + "\n")

    receipts_f.close()

    root = merkle_root(leaves)
    root_hex = "0x" + root.hex()

    # Create and verify one sample proof (if leaves exist)
    proof_out: Dict[str, Any] = {}
    if leaves:
        idx = 0
        proof_items = merkle_proof(leaves, idx)
        ok = verify_proof(leaves[idx], proof_items, root)
        proof_out = {
            "leaf_index": idx,
            "leaf": "0x" + leaves[idx].hex(),
            "root": root_hex,
            "proof": [
                {
                    "sibling": "0x" + p.sibling.hex(),
                    "is_left": p.is_left,
                }
                for p in proof_items
            ],
            "verified": ok,
        }

    outcomes = {
        "epoch": epoch,
        "release_id": release_id,
        "device_type": device_type,
        "rollout_percent": rollout_percent,
        "merkle_root": root_hex,
        "success": success,
        "fail": fail,
        "rollback": rollback,
        "n_receipts": len(leaves),
        "timings": {
            "fetch_seconds": fetch_s,
            "hash_verify_seconds": verify_hash_s,
            "payload_bytes": len(payload),
        },
    }

    (out_dir / f"outcomes_epoch_{epoch}.json").write_text(
        json.dumps(outcomes, indent=2), encoding="utf-8"
    )
    (out_dir / f"proof_epoch_{epoch}.json").write_text(
        json.dumps(proof_out, indent=2), encoding="utf-8"
    )

    return outcomes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/out", help="Output directory (mounted)")
    ap.add_argument("--epoch", type=int, required=True)
    ap.add_argument("--devices", type=int, default=1000)
    ap.add_argument("--rollout", type=int, required=True)
    ap.add_argument("--fail-rate", type=float, default=0.02)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--ipfs", default="http://ipfs:8080")
    ap.add_argument("--meta", default="/out/release_metadata.json")
    ap.add_argument(
        "--state",
        default="/out/device_state.json",
        help="Device state file (json map: device_id -> current_version).",
    )
    ap.add_argument(
        "--emit-rejects",
        action="store_true",
        help="Emit receipts for anti-rollback rejects (used for adversarial tests).",
    )
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))

    state_path = Path(args.state)
    if state_path.exists():
        state: Dict[str, int] = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {}

    outcomes = simulate_epoch(
        out_dir=out_dir,
        epoch=args.epoch,
        n_devices=args.devices,
        rollout_percent=args.rollout,
        fail_rate=args.fail_rate,
        seed=args.seed + args.epoch,
        ipfs_gateway=args.ipfs,
        cid=meta["cid"],
        expected_sha256_hex=meta["sha256_hex"],
        release_id=int(meta["release_id"]),
        target_version=int(meta["version"]),
        device_type=meta.get("device_type_str", "M4"),
        state=state,
        emit_rejects=bool(args.emit_rejects),
    )

    # Persist updated state (only successful installs advance version).
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print(json.dumps(outcomes, indent=2))


if __name__ == "__main__":
    main()
