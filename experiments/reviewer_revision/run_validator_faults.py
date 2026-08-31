#!/usr/bin/env python3
"""Measure local four-validator IBFT2 block progress across crash-fault boundaries."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import tempfile
import time
import os
from datetime import datetime, timezone
from pathlib import Path

from experiments.reviewer_revision.run_block_period_sensitivity import (
    ROOT,
    VALIDATOR_PUBLIC_KEYS,
    rpc,
    sanitized_genesis,
    wait_network,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def wait_for_blocks(rpc_url: str, starting_block: int, required_delta: int, timeout_seconds: int) -> tuple[int, float]:
    started = time.monotonic()
    deadline = started + timeout_seconds
    latest = starting_block
    while time.monotonic() < deadline:
        latest = int(rpc(rpc_url, "eth_blockNumber"), 16)
        if latest - starting_block >= required_delta:
            break
        time.sleep(0.25)
    return latest, time.monotonic() - started


def wait_for_peer_count(rpc_url: str, required: int, timeout_seconds: int = 120) -> int:
    deadline = time.monotonic() + timeout_seconds
    observed = 0
    while time.monotonic() < deadline:
        observed = int(rpc(rpc_url, "net_peerCount"), 16)
        if observed >= required:
            return observed
        time.sleep(0.5)
    raise RuntimeError(f"network reached only {observed} of {required} required peers")


def sanitize_log(path: Path, temp_root: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.replace(str(ROOT), "<REPOSITORY_ROOT>").replace(str(temp_root), "<TEMP_DATA>")
    text = re.sub(r"/" + r"Users/[^\s#]+", "<PRIVATE_PATH>", text)
    text = re.sub(r"/private/(?:tmp|var)/[^\s#]+", "<TEMP_PATH>", text)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--besu", required=True)
    parser.add_argument("--cast", default=os.environ.get("CAST_BIN", "cast"))
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--block-period", type=int, default=2)
    args = parser.parse_args()
    deployer_key = os.environ.get("LEDGERGUARD_DEPLOYER_PRIVATE_KEY", "")
    if not deployer_key:
        raise RuntimeError("LEDGERGUARD_DEPLOYER_PRIVATE_KEY is required")

    raw_root = ROOT / "results/reviewer_revision/raw/validator_faults"
    output = ROOT / "results/reviewer_revision/csv/validator_faults.csv"
    status_path = ROOT / "results/reviewer_revision/validation/validator_fault_status.json"
    if any(path.exists() for path in (raw_root, output, status_path)):
        raise RuntimeError("validator-fault output already exists; archive it before rerunning")
    raw_root.mkdir(parents=True)
    rows = []

    for trial in range(1, args.trials + 1):
        trial_dir = raw_root / f"trial_{trial:02d}"
        trial_dir.mkdir()
        genesis_path = trial_dir / "genesis.json"
        genesis_path.write_text(
            json.dumps(sanitized_genesis(args.block_period), indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        temp_root = Path(tempfile.mkdtemp(prefix=f"ledgerguard-validator-fault-{trial}-"))
        rpc_port = 19545 + trial
        base_p2p_port = 32303 + trial * 10
        rpc_url = f"http://127.0.0.1:{rpc_port}"
        enodes = [
            f"enode://{public_key}@127.0.0.1:{base_p2p_port + index}"
            for index, public_key in enumerate(VALIDATOR_PUBLIC_KEYS)
        ]
        processes: list[subprocess.Popen] = []
        logs = []
        try:
            commands: list[list[str]] = []
            for node_index in range(4):
                data_path = temp_root / f"node{node_index + 1}"
                data_path.mkdir(parents=True)
                log_path = trial_dir / f"node{node_index + 1}.log"
                stream = log_path.open("w", encoding="utf-8")
                logs.append((stream, log_path))
                command = [
                    args.besu, f"--data-path={data_path}",
                    f"--genesis-file={genesis_path.relative_to(ROOT)}",
                    f"--node-private-key-file=network/Node-{node_index + 1}/data/key",
                    "--profile=ENTERPRISE", f"--p2p-port={base_p2p_port + node_index}",
                    "--p2p-host=127.0.0.1", "--min-gas-price=0", "--logging=INFO",
                    "--Xaltbn128-native-enabled=false", "--Xblake2bf-native-enabled=false",
                    "--Xmodexp-native-enabled=false", "--Xp256verify-native-enabled=false",
                    "--Xsecp256k1-native-enabled=false",
                ]
                if node_index == 0:
                    command.extend([
                        "--rpc-http-enabled", "--rpc-http-host=127.0.0.1", f"--rpc-http-port={rpc_port}",
                        "--rpc-http-api=ETH,NET,WEB3,IBFT", "--host-allowlist=*", "--rpc-http-cors-origins=*",
                    ])
                command.append(
                    "--bootnodes=" + ",".join(enode for index, enode in enumerate(enodes) if index != node_index)
                )
                commands.append(command)
                processes.append(subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, text=True))
                time.sleep(1)

            environment = wait_network(rpc_url, timeout=240)
            environment["ready_peer_count"] = wait_for_peer_count(rpc_url, 3)
            baseline_start = int(rpc(rpc_url, "eth_blockNumber"), 16)
            baseline_end, baseline_seconds = wait_for_blocks(rpc_url, baseline_start, 2, 10)
            rows.append({
                "trial": trial, "fault_case": "zero_validators_stopped", "active_validator_processes": 4,
                "start_block": baseline_start, "end_block": baseline_end,
                "observed_block_delta": baseline_end - baseline_start, "observation_seconds": baseline_seconds,
                "expected_progress": True, "observed_progress": baseline_end > baseline_start,
                "status": "PASS" if baseline_end - baseline_start >= 2 else "FAIL",
                "evidence_type": "fresh_local_besu_crash_fault_measurement",
                "raw_evidence_path": str(trial_dir.relative_to(ROOT)),
                "restart_to_first_block_seconds": "", "restart_to_first_receipt_seconds": "",
                "restoration_tx_hash": "", "restoration_tx_status": "",
            })

            processes[3].terminate()
            processes[3].wait(timeout=20)
            one_start = int(rpc(rpc_url, "eth_blockNumber"), 16)
            one_end, one_seconds = wait_for_blocks(rpc_url, one_start, 1, 30)
            rows.append({
                "trial": trial, "fault_case": "one_validator_stopped", "active_validator_processes": 3,
                "start_block": one_start, "end_block": one_end, "observed_block_delta": one_end - one_start,
                "observation_seconds": one_seconds, "expected_progress": True,
                "observed_progress": one_end > one_start,
                "status": "PASS" if one_end - one_start >= 1 else "FAIL",
                "evidence_type": "fresh_local_besu_crash_fault_measurement",
                "raw_evidence_path": str(trial_dir.relative_to(ROOT)),
                "restart_to_first_block_seconds": "", "restart_to_first_receipt_seconds": "",
                "restoration_tx_hash": "", "restoration_tx_status": "",
            })

            processes[2].terminate()
            processes[2].wait(timeout=20)
            time.sleep(args.block_period + 1)
            two_start = int(rpc(rpc_url, "eth_blockNumber"), 16)
            time.sleep(args.block_period * 4)
            two_end = int(rpc(rpc_url, "eth_blockNumber"), 16)
            rows.append({
                "trial": trial, "fault_case": "two_validators_stopped", "active_validator_processes": 2,
                "start_block": two_start, "end_block": two_end, "observed_block_delta": two_end - two_start,
                "observation_seconds": args.block_period * 4, "expected_progress": False,
                "observed_progress": two_end > two_start,
                "status": "PASS" if two_end == two_start else "FAIL",
                "evidence_type": "fresh_local_besu_crash_fault_measurement",
                "raw_evidence_path": str(trial_dir.relative_to(ROOT)),
                "restart_to_first_block_seconds": "", "restart_to_first_receipt_seconds": "",
                "restoration_tx_hash": "", "restoration_tx_status": "",
            })

            restart_started = time.monotonic()
            processes[2] = subprocess.Popen(
                commands[2], cwd=ROOT, stdout=logs[2][0], stderr=subprocess.STDOUT, text=True
            )
            address_result = subprocess.run(
                [args.cast, "wallet", "address", "--private-key", deployer_key],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            deployer_address = address_result.stdout.strip()
            send_process = subprocess.Popen(
                [
                    args.cast, "send", "--rpc-url", rpc_url, "--private-key", deployer_key,
                    "--legacy", "--gas-price", "0", "--poll-interval", "1", "--json",
                    deployer_address, "--value", "0",
                ],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            restored_end = two_end
            first_block_wait = None
            block_deadline = time.monotonic() + 180
            while time.monotonic() < block_deadline:
                try:
                    restored_end = int(rpc(rpc_url, "eth_blockNumber"), 16)
                except (OSError, RuntimeError):
                    restored_end = two_end
                if restored_end > two_end:
                    first_block_wait = time.monotonic() - restart_started
                    break
                time.sleep(0.25)
            try:
                stdout, stderr = send_process.communicate(timeout=180)
            except subprocess.TimeoutExpired:
                send_process.terminate()
                stdout, stderr = send_process.communicate(timeout=20)
            receipt_wait = time.monotonic() - restart_started
            receipt = {}
            if stdout:
                start = stdout.find("{")
                if start >= 0:
                    try:
                        receipt, _end = json.JSONDecoder().raw_decode(stdout[start:])
                    except json.JSONDecodeError:
                        receipt = {}
            receipt_ok = send_process.returncode == 0 and receipt.get("status") == "0x1"
            transaction_attempts = 1
            while not receipt_ok and transaction_attempts < 3 and restored_end > two_end:
                transaction_attempts += 1
                retry = subprocess.run(
                    [
                        args.cast, "send", "--rpc-url", rpc_url, "--private-key", deployer_key,
                        "--legacy", "--gas-price", "0", "--poll-interval", "1", "--json",
                        deployer_address, "--value", "0",
                    ],
                    cwd=ROOT, text=True, capture_output=True, check=False, timeout=180,
                )
                start = retry.stdout.find("{")
                if start >= 0:
                    try:
                        receipt, _end = json.JSONDecoder().raw_decode(retry.stdout[start:])
                    except json.JSONDecodeError:
                        receipt = {}
                receipt_ok = retry.returncode == 0 and receipt.get("status") == "0x1"
                receipt_wait = time.monotonic() - restart_started
            if receipt_ok:
                restored_end = max(restored_end, int(receipt["blockNumber"], 16))
            restoration_ok = restored_end > two_end and receipt_ok
            rows.append({
                "trial": trial, "fault_case": "quorum_restored_after_validator_restart",
                "active_validator_processes": 3, "start_block": two_end, "end_block": restored_end,
                "observed_block_delta": restored_end - two_end,
                "observation_seconds": time.monotonic() - restart_started,
                "expected_progress": True, "observed_progress": restored_end > two_end,
                "status": "PASS" if restoration_ok else "FAIL",
                "evidence_type": "fresh_local_besu_crash_fault_restoration_measurement",
                "raw_evidence_path": str(trial_dir.relative_to(ROOT)),
                "restart_to_first_block_seconds": first_block_wait if first_block_wait is not None else "",
                "restart_to_first_receipt_seconds": receipt_wait,
                "restoration_tx_hash": receipt.get("transactionHash", ""),
                "restoration_tx_status": "success" if receipt_ok else "failed",
                "restoration_tx_attempts": transaction_attempts,
            })
            (trial_dir / "environment.json").write_text(json.dumps(
                environment | {"block_period_seconds": args.block_period, "fault_type": "process_crash"},
                indent=2, sort_keys=True,
            ) + "\n", encoding="utf-8")
            print(f"completed validator-fault trial {trial}/{args.trials}", flush=True)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                if process.poll() is None:
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
            for stream, _path in logs:
                stream.close()
            for _stream, path in logs:
                sanitize_log(path, temp_root)
            shutil.rmtree(temp_root, ignore_errors=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        columns = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    failed = sum(row["status"] != "PASS" for row in rows)
    status = {
        "status": "PASS" if failed == 0 else "FAIL", "generated_at_utc": utc_now(),
        "trials": args.trials, "cases": len(rows), "failed_cases": failed,
        "fault_type": "validator_process_crash", "byzantine_fault_injection": False,
        "four_validator_ibft_expected_fault_tolerance": 1,
        "quorum_restoration_tested": True,
        "successful_restoration_trials": sum(
            row["status"] == "PASS" and row["fault_case"] == "quorum_restored_after_validator_restart"
            for row in rows
        ),
    }
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()
