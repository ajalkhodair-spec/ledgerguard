#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

mkdir -p results/raw/adversarial results/csv

cat > results/csv/adversarial_validation.csv <<'CSV'
case_id,attack_case,expected_behavior,observed_behavior,evidence_source,tx_hash,raw_log_path,result,notes
substituted_payload,wrong hash / substituted payload,rejected,not executed,not_run,,results/raw/adversarial/substituted_payload.jsonl,not_run,Requires baseline stack and simulator run.
unavailable_cid,bad CID / unavailable artifact,rejected,not executed,not_run,,results/raw/adversarial/unavailable_cid.jsonl,not_run,Requires baseline stack and simulator run.
revoked_signer_approval,revoked signer cannot approve,reverted,not executed,not_run,,results/raw/adversarial/revoked_signer_approval.jsonl,not_run,Requires Besu/Foundry run.
revoked_vendor_registration,revoked vendor cannot register or approve,reverted,not executed,not_run,,results/raw/adversarial/revoked_vendor_registration.jsonl,not_run,Requires Besu/Foundry run.
kill_switch_readback,kill switch disables release eligibility,latestApproved returns zero or rollout eligibility is blocked,not executed,not_run,,results/raw/adversarial/kill_switch_readback.jsonl,not_run,Requires Besu/Foundry run.
downgrade_attempt,downgrade attempt rejected,rejected,not executed,not_run,,results/raw/adversarial/downgrade_attempt.jsonl,not_run,Requires simulator or HIL logs.
duplicate_approval_attempt,duplicate approval attempt,does not increase threshold count twice,not executed,not_run,,results/raw/adversarial/duplicate_approval_attempt.jsonl,not_run,Requires Besu/Foundry run.
unauthorized_operator_attempt,unauthorized operator attempt,reverted,not executed,not_run,,results/raw/adversarial/unauthorized_operator_attempt.jsonl,not_run,Requires Besu/Foundry run.
low_success_rollout_advancement,low-success rollout advancement blocked,reverted,not executed,not_run,,results/raw/adversarial/low_success_rollout_advancement.jsonl,not_run,Requires rollout state setup.
tampered_merkle_proof,tampered Merkle proof,rejected,not executed,not_run,,results/raw/adversarial/tampered_merkle_proof.jsonl,not_run,Requires proof verification run.
missing_receipt_timeout,missing receipt / timeout,timeout recorded,not executed,not_run,,results/raw/adversarial/missing_receipt_timeout.jsonl,not_run,Requires device workflow timeout run.
CSV

python3 - <<'PY'
import json
from datetime import datetime, timezone
cases = [
    "substituted_payload", "unavailable_cid", "revoked_signer_approval", "revoked_vendor_registration",
    "kill_switch_readback", "downgrade_attempt", "duplicate_approval_attempt", "unauthorized_operator_attempt",
    "low_success_rollout_advancement", "tampered_merkle_proof", "missing_receipt_timeout",
]
for case in cases:
    with open(f"results/raw/adversarial/{case}.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "case_id": case,
            "status": "not_run",
            "reason": "Adversarial case is scaffolded; run Besu/simulator-backed case to collect evidence.",
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }, sort_keys=True) + "\n")
PY
