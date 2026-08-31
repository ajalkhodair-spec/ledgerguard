#!/usr/bin/env python3
"""Compile LedgerGuard Solidity sources with solc standard JSON and via-IR."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solcjs", required=True)
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument(
        "--out",
        default="results/reviewer_revision/raw/security/solidity_standard_json_output.json",
    )
    args = parser.parse_args()

    source_paths = sorted((ROOT / "contracts/src").glob("*.sol"))
    if args.include_tests:
        source_paths.extend(sorted((ROOT / "contracts/test").glob("*.sol")))
    sources = {
        str(path.relative_to(ROOT)): {"content": path.read_text(encoding="utf-8")}
        for path in source_paths
    }
    request = {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "viaIR": True,
            "evmVersion": "berlin",
            "outputSelection": {
                "*": {
                    "*": ["abi", "storageLayout"]
                }
            },
        },
    }
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as request_file, tempfile.NamedTemporaryFile(
        mode="w+", encoding="utf-8"
    ) as response_file, tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as error_file:
        json.dump(request, request_file)
        request_file.flush()
        request_file.seek(0)
        completed = subprocess.run(
            [args.solcjs, "--standard-json"],
            cwd=ROOT,
            stdin=request_file,
            stdout=response_file,
            stderr=error_file,
            text=True,
            check=False,
        )
        response_file.seek(0)
        error_file.seek(0)
        raw = response_file.read()
        stderr = error_file.read()
    json_start = raw.find("{")
    if json_start < 0:
        print(stderr or raw)
        return 1
    response = json.loads(raw[json_start:])
    errors = [item for item in response.get("errors", []) if item.get("severity") == "error"]
    for item in response.get("errors", []):
        print(item.get("formattedMessage", item.get("message", "solc diagnostic")))

    output_path = ROOT / args.out
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "generated_at_utc": utc_now(),
        "compiler_command": [args.solcjs, "--standard-json"],
        "compiler_exit_code": completed.returncode,
        "error_count": len(errors),
        "source_count": len(sources),
        "settings": request["settings"],
        "result": response,
    }
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "passed" if not errors and completed.returncode == 0 else "failed",
        "sources": len(sources),
        "errors": len(errors),
        "output": str(output_path.relative_to(ROOT)),
    }, sort_keys=True))
    return 0 if not errors and completed.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
