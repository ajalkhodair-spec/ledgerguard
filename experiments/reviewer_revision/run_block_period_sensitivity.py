#!/usr/bin/env python3
"""Run fresh native four-validator IBFT2 networks at multiple block periods."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PERIODS = (1, 2, 4)
VALIDATOR_PUBLIC_KEYS = [
    "21f4026c5faf04d058a9009eb32eb69b326f3a1a2765e7de17c8604abadddcf4d4ec8ba026283d9c216e3e7420e684700b9ad84a716ecb531e1de2a705bf7d51",
    "e57a279bba7536bbb0466a80aca3056bfe336aa0ca0d284c7fb17b3300f2409207f85cd443d584f6616075140ab635a09ec44cc2abca206be94d7fef4572c699",
    "53e3acfa9260e5ecbaad5a78e7947756cd8a37de13f32b79e561062bf2ed2e548a1a7c6791974df909b4a96a1d37c468d3fb614383c306d7dcc2f81a004458e8",
    "c36cf020363b7cd12dcef8bb3f44f662885dc94bf32c8e85828adc96479f678d95e3afa14e36db84fb1c109593354b2b3d2c55b6f4689d8762b9473a416c4268",
]
DEPLOYER_KEY_ENV = "LEDGERGUARD_DEPLOYER_PRIVATE_KEY"


def rpc(url: str, method: str, params: list[Any] | None = None) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read())
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


def command(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def parse_json(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise RuntimeError(f"JSON output missing: {output}")
    return json.loads(output[start:])


def wait_network(url: str, timeout: int = 90) -> dict[str, Any]:
    deadline = time.time() + timeout
    initial_block = None
    while time.time() < deadline:
        try:
            chain_id = int(rpc(url, "eth_chainId"), 16)
            validators = rpc(url, "ibft_getValidatorsByBlockNumber", ["latest"])
            block = int(rpc(url, "eth_blockNumber"), 16)
            if initial_block is None:
                initial_block = block
            if chain_id == 1337 and len(validators) == 4 and block > initial_block:
                return {"chain_id": chain_id, "validators": validators, "ready_block": block}
        except (OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError):
            pass
        time.sleep(1)
    raise RuntimeError(f"network did not become ready at {url}")


def sanitized_genesis(period: int) -> dict[str, Any]:
    genesis = json.loads((ROOT / "network/genesis.json").read_text(encoding="utf-8"))
    genesis["config"]["ibft2"]["blockperiodseconds"] = period
    for account in genesis["alloc"].values():
        account.pop("privateKey", None)
        account.pop("comment", None)
    return genesis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--besu", required=True)
    parser.add_argument("--forge", default=os.environ.get("FORGE_BIN", "forge"))
    parser.add_argument("--cast", default=os.environ.get("CAST_BIN", "cast"))
    parser.add_argument("--transactions", type=int, default=30)
    args = parser.parse_args()
    deployer_key = os.environ.get(DEPLOYER_KEY_ENV)
    if not deployer_key:
        raise RuntimeError(f"{DEPLOYER_KEY_ENV} is required")

    raw_root = ROOT / "results/reviewer_revision/raw/block_period"
    output = ROOT / "results/reviewer_revision/csv/block_period_sensitivity.csv"
    if output.exists():
        raise RuntimeError("block-period output already exists; choose a clean evidence tree")
    raw_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for profile_index, period in enumerate(PERIODS):
        profile = f"block_period_{period}s"
        profile_dir = raw_root / profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        raw_transactions = profile_dir / "transactions.jsonl"
        if raw_transactions.exists():
            preserved = [json.loads(line) for line in raw_transactions.read_text(encoding="utf-8").splitlines() if line]
            if len(preserved) == args.transactions and all(row["status"] == "success" for row in preserved):
                rows.extend({key: value for key, value in row.items() if key != "receipt"} for row in preserved)
                print(f"preserved completed profile {profile}", flush=True)
                continue
            if preserved:
                raise RuntimeError(f"partial profile requires manual audit before resume: {profile}")
        genesis_path = profile_dir / "genesis.json"
        genesis_path.write_text(json.dumps(sanitized_genesis(period), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_root = Path(tempfile.mkdtemp(prefix=f"ledgerguard-{profile}-"))
        rpc_port = 18545 + profile_index
        base_p2p_port = 31303 + profile_index * 10
        rpc_url = f"http://127.0.0.1:{rpc_port}"
        bootnode = f"enode://{VALIDATOR_PUBLIC_KEYS[0]}@127.0.0.1:{base_p2p_port}"
        processes: list[subprocess.Popen] = []
        log_streams = []
        try:
            for node_index in range(4):
                data_path = temp_root / f"node{node_index + 1}"
                data_path.mkdir(parents=True)
                log_stream = (profile_dir / f"node{node_index + 1}.log").open("w", encoding="utf-8")
                log_streams.append(log_stream)
                node_command = [
                    args.besu,
                    f"--data-path={data_path}",
                    f"--genesis-file={genesis_path.relative_to(ROOT)}",
                    f"--node-private-key-file=network/Node-{node_index + 1}/data/key",
                    "--profile=ENTERPRISE",
                    f"--p2p-port={base_p2p_port + node_index}",
                    "--p2p-host=127.0.0.1",
                    "--min-gas-price=0",
                    "--logging=INFO",
                    "--Xaltbn128-native-enabled=false",
                    "--Xblake2bf-native-enabled=false",
                    "--Xmodexp-native-enabled=false",
                    "--Xp256verify-native-enabled=false",
                    "--Xsecp256k1-native-enabled=false",
                ]
                if node_index == 0:
                    node_command.extend(
                        [
                            "--rpc-http-enabled", "--rpc-http-host=127.0.0.1",
                            f"--rpc-http-port={rpc_port}", "--rpc-http-api=ETH,NET,WEB3,IBFT",
                            "--host-allowlist=*", "--rpc-http-cors-origins=*",
                        ]
                    )
                else:
                    node_command.append(f"--bootnodes={bootnode}")
                processes.append(
                    subprocess.Popen(node_command, cwd=ROOT, stdout=log_stream, stderr=subprocess.STDOUT, text=True)
                )
            environment = wait_network(rpc_url)
            (profile_dir / "environment.json").write_text(
                json.dumps(environment | {"block_period_seconds": period}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            deploy = command(
                [
                    args.forge, "create", "--rpc-url", rpc_url, "--private-key", deployer_key,
                    "--broadcast", "--legacy", "--gas-price", "0", "--json", "src/KeyManager.sol:KeyManager",
                ],
                ROOT / "contracts",
            )
            if deploy.returncode:
                raise RuntimeError(deploy.stderr + deploy.stdout)
            key_manager = parse_json(deploy.stdout)["deployedTo"]
            deployer_address = command(
                [args.cast, "wallet", "address", "--private-key", deployer_key], ROOT
            ).stdout.strip()
            for repetition in range(1, args.transactions + 1):
                head = int(rpc(rpc_url, "eth_blockNumber"), 16)
                send_args = [
                    args.cast, "send", "--rpc-url", rpc_url, "--private-key", deployer_key,
                    "--legacy", "--gas-price", "0", "--poll-interval", "1", "--json",
                    key_manager, "setSigner(address,uint8,bool)", deployer_address, "1", "true",
                ]
                start_ns = time.time_ns()
                sent = command(send_args, ROOT)
                end_ns = time.time_ns()
                receipt = parse_json(sent.stdout) if sent.returncode == 0 else {}
                block_number = int(receipt.get("blockNumber", "0x0"), 16)
                success = sent.returncode == 0 and receipt.get("status") == "0x1"
                row = {
                    "profile": profile, "block_period_seconds": period, "repetition": repetition,
                    "operation": "set_signer", "submitted_at_ns": start_ns,
                    "receipt_observed_at_ns": end_ns,
                    "latency_seconds": (end_ns - start_ns) / 1_000_000_000,
                    "tx_hash": receipt.get("transactionHash", ""), "block_number": block_number or "",
                    "transaction_index": int(receipt.get("transactionIndex", "0x0"), 16) if receipt else "",
                    "gas_used": int(receipt.get("gasUsed", "0x0"), 16) if receipt else "",
                    "submission_head_block": head,
                    "inclusion_delay_blocks": block_number - head if block_number else "",
                    "first_eligible_block": block_number == head + 1 if block_number else "",
                    "receipt_poll_interval_seconds": 1, "validator_count": 4, "chain_id": 1337,
                    "status": "success" if success else "failed", "error_message": sent.stderr.strip(),
                    "evidence_type": "fresh_local_besu_measurement",
                    "raw_evidence_path": str(raw_transactions.relative_to(ROOT)),
                }
                rows.append(row)
                with raw_transactions.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row | {"receipt": receipt}, sort_keys=True) + "\n")
                print(f"completed {profile} {repetition}/{args.transactions}", flush=True)
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            for stream in log_streams:
                stream.close()
            shutil.rmtree(temp_root, ignore_errors=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "failed": sum(row["status"] != "success" for row in rows)}))


if __name__ == "__main__":
    main()
