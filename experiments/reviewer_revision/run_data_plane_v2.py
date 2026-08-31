#!/usr/bin/env python3
"""Run local IPFS application-shaped network profiles and a concrete edge-cache ablation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILES = (
    ("P1", 20, 5.0),
    ("P2", 80, 5.0),
    ("P3", 200, 0.256),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str, expected_sha256: str, delay_ms: int = 0, bandwidth_mbps: float | None = None) -> dict[str, Any]:
    started_ns = time.time_ns()
    if delay_ms:
        time.sleep(delay_ms / 2000)
    payload = bytearray()
    read_started = time.monotonic()
    with urllib.request.urlopen(url, timeout=30) as response:
        status_code = response.status
        while True:
            chunk = response.read(16 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
            if bandwidth_mbps:
                required = (len(payload) * 8) / (bandwidth_mbps * 1_000_000)
                remaining = required - (time.monotonic() - read_started)
                if remaining > 0:
                    time.sleep(remaining)
    if delay_ms:
        time.sleep(delay_ms / 2000)
    ended_ns = time.time_ns()
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "started_at_ns": started_ns, "ended_at_ns": ended_ns,
        "elapsed_seconds": (ended_ns - started_ns) / 1_000_000_000,
        "bytes_transferred": len(payload), "http_status": status_code,
        "sha256": digest, "integrity_valid": digest == expected_sha256,
        "payload": bytes(payload),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network-repetitions", type=int, default=20)
    parser.add_argument("--cache-requests", type=int, default=1000)
    parser.add_argument("--cache-trials", type=int, default=10)
    parser.add_argument("--gateway", default="http://127.0.0.1:8080")
    parser.add_argument("--metadata", default=str(ROOT / "out/release_metadata.json"))
    args = parser.parse_args()

    metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    url = f"{args.gateway.rstrip('/')}/ipfs/{metadata['cid']}"
    expected_sha256 = metadata["sha256_hex"]
    expected_size = int(metadata["size_bytes"])
    raw_network = ROOT / "results/reviewer_revision/raw/network/application_shaped_fetches.jsonl"
    raw_cache = ROOT / "results/reviewer_revision/raw/cache/edge_cache_requests.jsonl"
    network_csv = ROOT / "results/reviewer_revision/csv/network_sensitivity.csv"
    cache_csv = ROOT / "results/reviewer_revision/csv/edge_cache_ablation.csv"
    cache_trials_csv = ROOT / "results/reviewer_revision/csv/edge_cache_trials.csv"
    network_status = ROOT / "results/reviewer_revision/validation/network_status.json"
    cache_status = ROOT / "results/reviewer_revision/validation/cache_status.json"
    for path in (raw_network, raw_cache, network_csv, cache_csv, cache_trials_csv, network_status, cache_status):
        if path.exists():
            raise RuntimeError(f"output already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    network_raw_rows = []
    for profile, delay_ms, bandwidth_mbps in PROFILES:
        for repetition in range(1, args.network_repetitions + 1):
            result = fetch(url, expected_sha256, delay_ms, bandwidth_mbps)
            row = {
                "run_id": f"network-{profile}-{repetition:02d}", "profile": profile,
                "repetition": repetition, "configured_application_delay_ms": delay_ms,
                "configured_read_rate_limit_mbps": bandwidth_mbps,
                "artifact_size_bytes": expected_size, "retrieval_time_seconds": result["elapsed_seconds"],
                "bytes_transferred": result["bytes_transferred"], "http_status": result["http_status"],
                "integrity_valid": result["integrity_valid"],
                "evidence_type": "application_shaped_local_ipfs_fetch",
                "status": "PASS" if result["integrity_valid"] and result["bytes_transferred"] == expected_size else "FAIL",
            }
            network_raw_rows.append(row)
            print(f"completed {profile} repetition {repetition}/{args.network_repetitions}", flush=True)
    with raw_network.open("w", encoding="utf-8") as stream:
        for row in network_raw_rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    network_rows = []
    for profile, delay_ms, bandwidth_mbps in PROFILES:
        values = [row["retrieval_time_seconds"] for row in network_raw_rows if row["profile"] == profile]
        failures = sum(row["status"] != "PASS" for row in network_raw_rows if row["profile"] == profile)
        network_rows.append({
            "profile": profile, "configured_application_delay_ms": delay_ms,
            "configured_read_rate_limit_mbps": bandwidth_mbps,
            "artifact_size_bytes": expected_size, "repetitions": len(values),
            "minimum_seconds": min(values), "median_seconds": statistics.median(values),
            "maximum_seconds": max(values), "mean_seconds": statistics.mean(values),
            "standard_deviation_seconds": statistics.stdev(values) if len(values) > 1 else 0,
            "total_bytes_transferred": expected_size * len(values), "failed_fetches": failures,
            "shaping_layer": "application_read_pacing_plus_configured_round_trip_delay",
            "evidence_type": "application_shaped_local_ipfs_fetch",
            "status": "PASS" if failures == 0 else "FAIL",
            "raw_evidence_path": str(raw_network.relative_to(ROOT)),
        })
    write_csv(network_csv, network_rows)

    cache_raw_rows = []
    cache_trials = []
    for mode in ("OFF", "ON"):
        for trial in range(1, args.cache_trials + 1):
            cached_payload: bytes | None = None
            origin_requests = 0
            origin_bytes = 0
            cache_hits = 0
            started = time.monotonic()
            for request_id in range(1, args.cache_requests + 1):
                request_started = time.time_ns()
                if mode == "ON" and cached_payload is not None:
                    payload = cached_payload
                    source = "edge_cache"
                    cache_hits += 1
                    origin_elapsed = 0.0
                else:
                    result = fetch(url, expected_sha256)
                    payload = result["payload"]
                    source = "ipfs_origin"
                    origin_elapsed = result["elapsed_seconds"]
                    origin_requests += 1
                    origin_bytes += len(payload)
                    if mode == "ON":
                        cached_payload = payload
                digest_valid = hashlib.sha256(payload).hexdigest() == expected_sha256
                request_ended = time.time_ns()
                cache_raw_rows.append({
                    "cache_mode": mode, "trial": trial, "request_id": request_id, "source": source,
                    "bytes_served": len(payload), "origin_elapsed_seconds": origin_elapsed,
                    "request_elapsed_seconds": (request_ended - request_started) / 1_000_000_000,
                    "integrity_valid": digest_valid, "status": "PASS" if digest_valid else "FAIL",
                })
            total_seconds = time.monotonic() - started
            trial_rows = [
                row for row in cache_raw_rows
                if row["cache_mode"] == mode and row["trial"] == trial
            ]
            warm_rows = [row for row in trial_rows if row["source"] == "edge_cache"]
            failures = sum(row["status"] != "PASS" for row in trial_rows)
            cache_trials.append({
                "cache_mode": mode, "trial": trial, "artifact_requests": args.cache_requests,
                "origin_requests": origin_requests, "cache_hits": cache_hits,
                "cache_misses": origin_requests, "cache_hit_rate": cache_hits / args.cache_requests,
                "origin_bytes_transferred": origin_bytes,
                "device_bytes_served": expected_size * args.cache_requests,
                "cold_fetch_time_seconds": trial_rows[0]["request_elapsed_seconds"],
                "median_warm_hit_time_seconds": statistics.median(
                    row["request_elapsed_seconds"] for row in warm_rows
                ) if warm_rows else "",
                "total_retrieval_time_seconds": total_seconds,
                "median_request_time_seconds": statistics.median(row["request_elapsed_seconds"] for row in trial_rows),
                "integrity_failures": failures, "artifact_size_bytes": expected_size,
                "evidence_type": "executed_local_ipfs_edge_cache_independent_trial",
                "status": "PASS" if failures == 0 else "FAIL",
                "raw_evidence_path": str(raw_cache.relative_to(ROOT)),
            })
            print(f"completed cache {mode} trial {trial}/{args.cache_trials}", flush=True)
    with raw_cache.open("w", encoding="utf-8") as stream:
        for row in cache_raw_rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    write_csv(cache_trials_csv, cache_trials)
    cache_summaries = []
    for mode in ("OFF", "ON"):
        mode_trials = [row for row in cache_trials if row["cache_mode"] == mode]
        totals = [float(row["total_retrieval_time_seconds"]) for row in mode_trials]
        cache_summaries.append({
            "cache_mode": mode, "independent_trials": len(mode_trials),
            "artifact_requests_per_trial": args.cache_requests,
            "median_origin_requests": statistics.median(row["origin_requests"] for row in mode_trials),
            "median_cache_hits": statistics.median(row["cache_hits"] for row in mode_trials),
            "median_cache_hit_rate": statistics.median(row["cache_hit_rate"] for row in mode_trials),
            "median_origin_bytes_transferred": statistics.median(row["origin_bytes_transferred"] for row in mode_trials),
            "minimum_total_retrieval_time_seconds": min(totals),
            "median_total_retrieval_time_seconds": statistics.median(totals),
            "maximum_total_retrieval_time_seconds": max(totals),
            "mean_total_retrieval_time_seconds": statistics.mean(totals),
            "standard_deviation_total_retrieval_time_seconds": statistics.stdev(totals),
            "integrity_failures": sum(row["integrity_failures"] for row in mode_trials),
            "artifact_size_bytes": expected_size,
            "evidence_type": "executed_local_ipfs_edge_cache_trial_summary",
            "status": "PASS" if all(row["status"] == "PASS" for row in mode_trials) else "FAIL",
            "raw_evidence_path": str(cache_trials_csv.relative_to(ROOT)),
        })
    write_csv(cache_csv, cache_summaries)

    network_failures = sum(row["status"] != "PASS" for row in network_raw_rows)
    network_status.write_text(json.dumps({
        "status": "PASS" if network_failures == 0 else "FAIL", "generated_at_utc": utc_now(),
        "profiles": len(PROFILES), "repetitions_per_profile": args.network_repetitions,
        "attempted_fetches": len(network_raw_rows), "failed_fetches": network_failures,
        "traffic_control_layer": "application", "os_netem_used": False,
        "terminology": "configured_application_delay_and_read_rate_limit",
        "wan_or_production_claim_supported": False,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cache_failures = sum(row["status"] != "PASS" for row in cache_raw_rows)
    cache_status.write_text(json.dumps({
        "status": "PASS" if cache_failures == 0 else "FAIL", "generated_at_utc": utc_now(),
        "cache_modes": ["OFF", "ON"], "independent_trials_per_mode": args.cache_trials,
        "requests_per_trial": args.cache_requests,
        "attempted_requests": len(cache_raw_rows), "failed_requests": cache_failures,
        "origin": "local_ipfs_gateway", "physical_device_used": False,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"network_failures": network_failures, "cache_failures": cache_failures}, sort_keys=True))


if __name__ == "__main__":
    main()
