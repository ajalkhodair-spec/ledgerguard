#!/usr/bin/env python3
"""Execute final-ABI governance lifecycle operations for gas characterization."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from experiments.reviewer_revision.run_accountability_v2 import bytes32, submit_batch


ROOT = Path(__file__).resolve().parents[2]
DEVICE_TYPE = "0x" + "4d34" + "00" * 30


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument("--cast", default=os.environ.get("CAST_BIN", "cast"))
    parser.add_argument(
        "--deployment",
        default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/deployment.json"),
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/governance_lifecycle_transactions.jsonl"),
    )
    args = parser.parse_args()

    keys = {
        "owner": os.environ.get("LEDGERGUARD_DEPLOYER_PRIVATE_KEY", ""),
        "security": os.environ.get("LEDGERGUARD_SECURITY_PRIVATE_KEY", ""),
    }
    if not all(keys.values()):
        raise RuntimeError("deployer and security private-key environment variables are required")

    deployment = json.loads(Path(args.deployment).read_text(encoding="utf-8"))
    actors = deployment["actors"]
    contracts = {name: item["deployedTo"] for name, item in deployment["contracts"].items()}
    output = Path(args.out)
    if output.exists():
        raise RuntimeError("governance lifecycle output already exists; archive it before rerunning")
    output.parent.mkdir(parents=True, exist_ok=True)

    measured: list[dict] = []
    batches = [
        (
            "activate_kill_switch",
            keys["security"],
            actors["security"],
            contracts["FirmwareRegistry"],
            [
                (
                    "activate_kill_switch",
                    "setKillSwitch(bytes32,bool)",
                    [bytes32(100_000 + index), "true"],
                )
                for index in range(args.samples)
            ],
        ),
        (
            "deprecate_release",
            keys["security"],
            actors["security"],
            contracts["FirmwareRegistry"],
            [
                ("deprecate_release", "deprecateRelease(uint256)", [str(index + 1)])
                for index in range(args.samples)
            ],
        ),
        (
            "set_or_replace_governance_signer",
            keys["owner"],
            actors["deployer"],
            contracts["KeyManager"],
            [
                (
                    "set_or_replace_governance_signer",
                    "setSigner(address,uint8,bool)",
                    [f"0x{200_000 + index:040x}", "4", "true"],
                )
                for index in range(args.samples)
            ],
        ),
    ]
    for _name, key, actor, target, calls in batches:
        measured.extend(submit_batch(args.cast, args.rpc, key, actor, target, calls))

    initial_identity_calls = [
        (
            "initial_device_identity_setup",
            "setDeviceIdentity(bytes32,address,bool)",
            [bytes32(300_000 + index), f"0x{400_000 + index:040x}", "true"],
        )
        for index in range(args.samples)
    ]
    submit_batch(
        args.cast,
        args.rpc,
        keys["owner"],
        actors["deployer"],
        contracts["DeviceIdentityRegistryV2"],
        initial_identity_calls,
    )
    replacement_calls = [
        (
            "replace_device_identity",
            "setDeviceIdentity(bytes32,address,bool)",
            [bytes32(300_000 + index), f"0x{500_000 + index:040x}", "true"],
        )
        for index in range(args.samples)
    ]
    measured.extend(
        submit_batch(
            args.cast,
            args.rpc,
            keys["owner"],
            actors["deployer"],
            contracts["DeviceIdentityRegistryV2"],
            replacement_calls,
        )
    )

    with output.open("w", encoding="utf-8") as stream:
        for row in measured:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    status = {
        "status": "PASS",
        "samples_per_operation": args.samples,
        "operation_types": sorted({row["operation"] for row in measured}),
        "measured_transactions": len(measured),
        "failed_transactions": sum(row["status"] != "success" for row in measured),
        "raw_evidence_path": str(output.relative_to(ROOT)),
    }
    status_path = ROOT / "results/reviewer_revision/validation/governance_lifecycle_gas_status.json"
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()
