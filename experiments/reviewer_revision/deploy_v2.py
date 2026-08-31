#!/usr/bin/env python3
"""Deploy LedgerGuard V2 to a configured local Besu endpoint and preserve receipts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command[:3])}\n{result.stderr}\n{result.stdout}")
    return result.stdout


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise RuntimeError(f"JSON output missing: {output}")
    return json.loads(output[start:])


def address(cast: str, private_key: str, cwd: Path) -> str:
    return run([cast, "wallet", "address", "--private-key", private_key], cwd).strip()


def deploy(
    forge: str,
    rpc: str,
    private_key: str,
    contract: str,
    constructor_args: list[str],
    cwd: Path,
) -> dict[str, Any]:
    command = [
        forge, "create", "--rpc-url", rpc, "--private-key", private_key, "--broadcast", "--legacy",
        "--gas-price", "0", "--json", contract,
    ]
    if constructor_args:
        command.extend(["--constructor-args", *constructor_args])
    start_ns = time.time_ns()
    output = parse_json_output(run(command, cwd))
    output["submitted_at_ns"] = start_ns
    output["receipt_observed_at_ns"] = time.time_ns()
    output["contract"] = contract
    return output


def send(
    cast: str,
    rpc: str,
    private_key: str,
    target: str,
    signature: str,
    values: list[str],
    cwd: Path,
    value: str | None = None,
) -> dict[str, Any]:
    command = [
        cast, "send", "--rpc-url", rpc, "--private-key", private_key, "--legacy", "--gas-price", "0",
        "--poll-interval", "1", "--json",
    ]
    if value:
        command.extend(["--value", value])
    command.append(target)
    if signature:
        command.extend([signature, *values])
    start_ns = time.time_ns()
    receipt = parse_json_output(run(command, cwd))
    receipt["submitted_at_ns"] = start_ns
    receipt["receipt_observed_at_ns"] = time.time_ns()
    receipt["operation"] = signature
    return receipt


def required_key(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument("--forge", default=os.environ.get("FORGE_BIN", "forge"))
    parser.add_argument("--cast", default=os.environ.get("CAST_BIN", "cast"))
    parser.add_argument("--output", default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/deployment.json"))
    args = parser.parse_args()

    keys = {
        "deployer": required_key("LEDGERGUARD_DEPLOYER_PRIVATE_KEY"),
        "security": required_key("LEDGERGUARD_SECURITY_PRIVATE_KEY"),
        "regulator": required_key("LEDGERGUARD_REGULATOR_PRIVATE_KEY"),
        "operator": required_key("LEDGERGUARD_OPERATOR_PRIVATE_KEY"),
        "auditor": required_key("LEDGERGUARD_AUDITOR_PRIVATE_KEY"),
    }
    actors = {name: address(args.cast, key, ROOT) for name, key in keys.items()}
    contracts_dir = ROOT / "contracts"
    deployment: dict[str, Any] = {
        "evidence_type": "local_besu_deployment",
        "rpc": args.rpc,
        "generated_at_utc": utc_now(),
        "chain_id": 1337,
        "actors": actors,
        "contracts": {},
        "setup_transactions": [],
    }

    for account in ("operator", "auditor"):
        deployment["setup_transactions"].append(
            send(args.cast, args.rpc, keys["deployer"], actors[account], "", [], contracts_dir, value="1ether")
        )

    key_manager = deploy(args.forge, args.rpc, keys["deployer"], "src/KeyManager.sol:KeyManager", [], contracts_dir)
    deployment["contracts"]["KeyManager"] = key_manager
    key_manager_address = key_manager["deployedTo"]

    deployment_order = [
        ("FirmwareRegistry", "src/FirmwareRegistry.sol:FirmwareRegistry", [key_manager_address]),
        ("DeviceIdentityRegistryV2", "src/DeviceIdentityRegistryV2.sol:DeviceIdentityRegistryV2", [key_manager_address]),
        ("DeviceAttestationV2", "src/DeviceAttestationV2.sol:DeviceAttestationV2", [key_manager_address]),
    ]
    for name, contract, constructor_args in deployment_order:
        deployment["contracts"][name] = deploy(
            args.forge, args.rpc, keys["deployer"], contract, constructor_args, contracts_dir
        )

    registry = deployment["contracts"]["FirmwareRegistry"]["deployedTo"]
    identities = deployment["contracts"]["DeviceIdentityRegistryV2"]["deployedTo"]
    deployment["contracts"]["DeviceReceiptVerifierV2"] = deploy(
        args.forge, args.rpc, keys["deployer"], "src/DeviceReceiptVerifierV2.sol:DeviceReceiptVerifierV2",
        [identities], contracts_dir,
    )
    deployment["contracts"]["RolloutCoordinatorV2"] = deploy(
        args.forge, args.rpc, keys["deployer"], "src/RolloutCoordinatorV2.sol:RolloutCoordinatorV2",
        [key_manager_address, registry], contracts_dir,
    )

    roles = {"deployer": 1, "security": 2, "regulator": 3, "operator": 4, "auditor": 5}
    for actor_name, role in roles.items():
        deployment["setup_transactions"].append(
            send(
                args.cast, args.rpc, keys["deployer"], key_manager_address,
                "setSigner(address,uint8,bool)", [actors[actor_name], str(role), "true"], contracts_dir,
            )
        )
    device_type = "0x" + "4d34" + "00" * 30
    deployment["setup_transactions"].append(
        send(
            args.cast, args.rpc, keys["deployer"], key_manager_address,
            "setPolicy(bytes32,uint8,uint8)", [device_type, "12", "2"], contracts_dir,
        )
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(deployment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "contracts": {k: v["deployedTo"] for k, v in deployment["contracts"].items()}}, indent=2))


if __name__ == "__main__":
    main()
