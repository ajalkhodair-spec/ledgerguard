#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

./scripts/doctor.sh >/dev/null

# Ensure .env exists
if [ ! -f .env ]; then
  cp .env.example .env
fi
# shellcheck disable=SC1091
source .env

mkdir -p out/adversarial \
  out/adversarial/tamper \
  out/adversarial/badcid \
  out/adversarial/rollback

RPC_URL_DOCKER="http://besu-node1:8545"
IPFS_GATEWAY_DOCKER="http://ipfs:8080"

META_JSON="out/release_metadata.json"
if [ ! -f "$META_JSON" ]; then
  echo "[adv] ERROR: $META_JSON not found; run ./poc run first" >&2
  exit 1
fi

# Read addresses and metadata from the run
KM_ADDR=$(jq -r '.contracts.keyManager' "$META_JSON")
FR_ADDR=$(jq -r '.contracts.registry' "$META_JSON")
RC_ADDR=$(jq -r '.contracts.rollout' "$META_JSON")
DA_ADDR=$(jq -r '.contracts.attestation' "$META_JSON")

DEVICE_TYPE_BYTES32=$(jq -r '.device_type_bytes32' "$META_JSON")
DEVICE_TYPE_STR=$(jq -r '.device_type_str' "$META_JSON")
CID=$(jq -r '.cid' "$META_JSON")
SHA256_HEX=$(jq -r '.sha256_hex' "$META_JSON")
SIZE_BYTES=$(jq -r '.size_bytes' "$META_JSON")
SBOM_HASH=$(jq -r '.sbom_hash' "$META_JSON")
PROV_HASH=$(jq -r '.prov_hash' "$META_JSON")

# Compute addresses from private keys (inside foundry container)
VENDOR_ADDR=$(docker compose run --rm foundry "cast wallet address --private-key $VENDOR_PRIVATE_KEY")
SECURITY_ADDR=$(docker compose run --rm foundry "cast wallet address --private-key $SECURITY_PRIVATE_KEY")
REGULATOR_ADDR=$(docker compose run --rm foundry "cast wallet address --private-key $REGULATOR_PRIVATE_KEY")
OPERATOR_ADDR=$(docker compose run --rm foundry "cast wallet address --private-key $OPERATOR_PRIVATE_KEY")

RESULT_JSON="out/adversarial.json"
# Start JSON file
printf '{"tests":[]}\n' > "$RESULT_JSON"

add_test() {
  local name="$1"
  local passed="$2"   # 'true' or 'false'
  local details="$3"
  local evidence="$4"

  local tmp
  tmp="$(mktemp)"
  jq --arg name "$name" \
     --argjson passed "$passed" \
     --arg details "$details" \
     --arg evidence "$evidence" \
     '.tests += [{"name":$name,"passed":$passed,"details":$details,"evidence":$evidence}]' \
     "$RESULT_JSON" > "$tmp"
  mv "$tmp" "$RESULT_JSON"
}

first_line() {
  local f="$1"
  if [ -f "$f" ]; then
    head -n 1 "$f" | tr -d '\r'
  else
    echo ""
  fi
}

tx_hash_from_file() {
  awk '{
    line = $0
    while (match(line, /0x[0-9a-fA-F]{64}/)) {
      hash = substr(line, RSTART, RLENGTH)
      line = substr(line, RSTART + RLENGTH)
    }
  } END { print hash }' "$1"
}

receipt_failed() {
  grep -Eq 'status[[:space:]]+0[[:space:]]+[(]failed[)]|status[[:space:]]+0$' "$1"
}

# ------------------------------
# Test A: Hash substitution detection (expected fail)
# ------------------------------
TAMP_META="out/release_metadata_tampered.json"
# Replace expected sha256 with an invalid value
jq '.sha256_hex="0000000000000000000000000000000000000000000000000000000000000000"' \
  "$META_JSON" > "$TAMP_META"

set +e
docker compose run --rm sim \
  "python simulate_devices.py --out /out/adversarial/tamper --epoch 90 --devices 50 --rollout 100 --fail-rate 0 --seed 9001 --ipfs $IPFS_GATEWAY_DOCKER --meta /out/release_metadata_tampered.json" \
  > out/adversarial/tamper/stdout.txt 2> out/adversarial/tamper/stderr.txt
RC=$?
set -e

if [ "$RC" -ne 0 ]; then
  add_test "hash_substitution_detected" true "Simulator rejected payload whose sha256 does not match on-chain metadata." "$(first_line out/adversarial/tamper/stderr.txt)"
else
  add_test "hash_substitution_detected" false "Expected simulator to fail on sha256 mismatch, but it succeeded." "unexpected success"
fi

# ------------------------------
# Test B: Missing/invalid CID detection (expected fail)
# ------------------------------
BADCID_META="out/release_metadata_badcid.json"
# Intentionally invalid CID
jq '.cid="bafyINVALIDCIDFORTEST000000000000000000000000000000000000000000000000"' \
  "$META_JSON" > "$BADCID_META"

set +e
docker compose run --rm sim \
  "python simulate_devices.py --out /out/adversarial/badcid --epoch 91 --devices 10 --rollout 100 --fail-rate 0 --seed 9002 --ipfs $IPFS_GATEWAY_DOCKER --meta /out/release_metadata_badcid.json" \
  > out/adversarial/badcid/stdout.txt 2> out/adversarial/badcid/stderr.txt
RC=$?
set -e

if [ "$RC" -ne 0 ]; then
  add_test "cid_fetch_failure_detected" true "Simulator failed safely when the CID is invalid/unresolvable." "$(first_line out/adversarial/badcid/stderr.txt)"
else
  add_test "cid_fetch_failure_detected" false "Expected simulator to fail on invalid CID, but it succeeded." "unexpected success"
fi

# ------------------------------
# Test C: Anti-rollback gating (downgrade attempt) + merkle anchoring
# ------------------------------
# Register an older-version release (version=0) that points to the same payload.
# In real fleets, the ledger may still contain older releases; devices must enforce anti-rollback.
RID_ROLLBACK=$(docker compose run --rm foundry "cast call --rpc-url $RPC_URL_DOCKER $FR_ADDR 'nextReleaseId()(uint256)'" | awk '{print $1}')

TX_REG_OLD=$(docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $FR_ADDR 'registerRelease(bytes32,uint64,string,bytes32,uint32,bytes32,bytes32,uint32,uint64)' $DEVICE_TYPE_BYTES32 0 $CID 0x$SHA256_HEX $SIZE_BYTES $SBOM_HASH $PROV_HASH 0 0" \
  | awk '/transactionHash/ {print $2}')

# Approve (security + regulator) to satisfy the 2-of-3 policy.
docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $SECURITY_PRIVATE_KEY $FR_ADDR 'approveRelease(uint256)' $RID_ROLLBACK" >/dev/null

docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $REGULATOR_PRIVATE_KEY $FR_ADDR 'approveRelease(uint256)' $RID_ROLLBACK" >/dev/null

ROLLBACK_META="out/release_metadata_rollback.json"
jq --argjson rid "$RID_ROLLBACK" '.release_id=$rid | .version=0' "$META_JSON" > "$ROLLBACK_META"

# Simulate a downgrade attempt for all devices; emit rejects as receipts.
docker compose run --rm sim \
  "python simulate_devices.py --out /out/adversarial/rollback --epoch 1 --devices 1000 --rollout 100 --fail-rate 0 --seed 9003 --ipfs $IPFS_GATEWAY_DOCKER --meta /out/release_metadata_rollback.json --emit-rejects" \
  > out/adversarial/rollback/stdout.txt 2> out/adversarial/rollback/stderr.txt

ROOT_OLD=$(jq -r '.merkle_root' out/adversarial/rollback/outcomes_epoch_1.json)
S_OLD=$(jq -r '.success' out/adversarial/rollback/outcomes_epoch_1.json)
F_OLD=$(jq -r '.fail' out/adversarial/rollback/outcomes_epoch_1.json)
R_OLD=$(jq -r '.rollback' out/adversarial/rollback/outcomes_epoch_1.json)

TX_COMMIT_OLD=$(docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $DA_ADDR 'submitOutcomeRoot(uint256,uint32,bytes32,uint32,uint32,uint32)' $RID_ROLLBACK 1 $ROOT_OLD $S_OLD $F_OLD $R_OLD" \
  | awk '/transactionHash/ {print $2}')

# Sanity check: read back committed root
READBACK=$(docker compose run --rm foundry \
  "cast call --rpc-url $RPC_URL_DOCKER $DA_ADDR 'outcomes(uint256,uint32)(bytes32,uint32,uint32,uint32,uint64)' $RID_ROLLBACK 1" \
  2>/dev/null || true)

if echo "$READBACK" | grep -qi "${ROOT_OLD#0x}" && [ "${F_OLD:-0}" -gt 0 ]; then
  add_test "anti_rollback_rejects_downgrade" true "Devices rejected rollback (downgrade) attempts; outcome Merkle root was anchored on-chain." "tx=${TX_COMMIT_OLD:-}, fail=${F_OLD:-0}"
else
  add_test "anti_rollback_rejects_downgrade" false "Expected downgrade attempts to be rejected and anchored on-chain." "readback=${READBACK}"
fi

# ------------------------------
# Test D: Revoked signer cannot approve (regulator revocation)
# ------------------------------
# Register a new proposed release (version=2) referencing the same payload (sufficient for key test).
RID2=$(docker compose run --rm foundry "cast call --rpc-url $RPC_URL_DOCKER $FR_ADDR 'nextReleaseId()(uint256)'" | awk '{print $1}')

docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $FR_ADDR 'registerRelease(bytes32,uint64,string,bytes32,uint32,bytes32,bytes32,uint32,uint64)' $DEVICE_TYPE_BYTES32 2 $CID 0x$SHA256_HEX $SIZE_BYTES $SBOM_HASH $PROV_HASH 0 0" \
  >/dev/null

# Revoke regulator signer using governance owner (operator)
docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $KM_ADDR 'revokeSigner(address)' $REGULATOR_ADDR" \
  >/dev/null

set +e
docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $REGULATOR_PRIVATE_KEY $FR_ADDR 'approveRelease(uint256)' $RID2" \
  > out/adversarial/revoked_regulator.stdout 2> out/adversarial/revoked_regulator.stderr
RC=$?
set -e
TX_REVOKED_REGULATOR=$(tx_hash_from_file out/adversarial/revoked_regulator.stdout)

if [ "$RC" -ne 0 ] || receipt_failed out/adversarial/revoked_regulator.stdout; then
  add_test "revoked_regulator_cannot_approve" true "Revoked regulator signer could not approve a proposed release." "$(first_line out/adversarial/revoked_regulator.stderr)"
else
  add_test "revoked_regulator_cannot_approve" false "Expected revoked regulator approval tx to fail/revert." "unexpected success"
fi
if [ -n "$TX_REVOKED_REGULATOR" ]; then
  tmp="$(mktemp)"
  jq --arg tx "$TX_REVOKED_REGULATOR" '.tests[-1].evidence = ("tx=" + $tx + ", status=failed")' "$RESULT_JSON" > "$tmp"
  mv "$tmp" "$RESULT_JSON"
fi

# ------------------------------
# Test E: Revoked vendor cannot register releases
# ------------------------------
# Revoke vendor signer

docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $KM_ADDR 'revokeSigner(address)' $VENDOR_ADDR" \
  >/dev/null

set +e
# Attempt to register release (version=3) as vendor: should revert signer inactive

docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $FR_ADDR 'registerRelease(bytes32,uint64,string,bytes32,uint32,bytes32,bytes32,uint32,uint64)' $DEVICE_TYPE_BYTES32 3 $CID 0x$SHA256_HEX $SIZE_BYTES $SBOM_HASH $PROV_HASH 0 0" \
  > out/adversarial/revoked_vendor.stdout 2> out/adversarial/revoked_vendor.stderr
RC=$?
set -e
TX_REVOKED_VENDOR=$(tx_hash_from_file out/adversarial/revoked_vendor.stdout)

if [ "$RC" -ne 0 ] || receipt_failed out/adversarial/revoked_vendor.stdout; then
  add_test "revoked_vendor_cannot_register" true "Revoked vendor signer could not register new firmware releases." "$(first_line out/adversarial/revoked_vendor.stderr)"
else
  add_test "revoked_vendor_cannot_register" false "Expected revoked vendor registration to fail/revert." "unexpected success"
fi
if [ -n "$TX_REVOKED_VENDOR" ]; then
  tmp="$(mktemp)"
  jq --arg tx "$TX_REVOKED_VENDOR" '.tests[-1].evidence = ("tx=" + $tx + ", status=failed")' "$RESULT_JSON" > "$tmp"
  mv "$tmp" "$RESULT_JSON"
fi

# ------------------------------
# Test F: Kill-switch disables latestApproved()
# ------------------------------
# Security toggles kill-switch and we verify latestApproved becomes 0.

docker compose run --rm foundry \
  "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $SECURITY_PRIVATE_KEY $FR_ADDR 'setKillSwitch(bytes32,bool)' $DEVICE_TYPE_BYTES32 true" \
  >/dev/null

LATEST=$(docker compose run --rm foundry \
  "cast call --rpc-url $RPC_URL_DOCKER $FR_ADDR 'latestApproved(bytes32)(uint256)' $DEVICE_TYPE_BYTES32" \
  | awk '{print $1}')

if [ "$LATEST" = "0" ] || [ "$LATEST" = "0x0" ]; then
  add_test "kill_switch_disables_latestApproved" true "Kill-switch set => latestApproved returns 0 (devices should not install)." "latestApproved=${LATEST}"
else
  add_test "kill_switch_disables_latestApproved" false "Expected latestApproved=0 after kill-switch." "latestApproved=${LATEST}"
fi

echo "[adv] Wrote ${RESULT_JSON}"
