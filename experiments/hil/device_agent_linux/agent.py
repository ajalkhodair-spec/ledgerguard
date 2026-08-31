#!/usr/bin/env python3
"""Linux SBC receipt generator for LedgerGuard HIL runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def receipt_hash(receipt: dict) -> str:
    data = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--device-type", default="linux_sbc")
    parser.add_argument("--release-id", type=int, required=True)
    parser.add_argument("--target-version", type=int, required=True)
    parser.add_argument("--outcome", choices=["SUCCESS", "ROLLBACK", "FAIL", "REJECTED"], required=True)
    parser.add_argument("--proof-hash", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    receipt = {
        "device_id": args.device_id,
        "device_type": args.device_type,
        "release_id": args.release_id,
        "target_version": args.target_version,
        "outcome": args.outcome,
        "timestamp_utc": utc_now(),
        "proof_hash": args.proof_hash,
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    receipt["receipt_hash"] = receipt_hash(receipt)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
