#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

./scripts/doctor.sh >/dev/null

# Parse flags
ADVERSARIAL=0
for arg in "$@"; do
  case "$arg" in
    --adversarial)
      ADVERSARIAL=1
      ;;
  esac
done

# Ensure .env exists
if [ ! -f .env ]; then
  cp .env.example .env
fi
# shellcheck disable=SC1091
source .env

# Fleet size for the simulator (can be overridden as an environment variable)
FLEET_SIZE=${FLEET_SIZE:-1000}

# Generate the network and local demo keys if missing.
echo "[run] Checking Besu network artifacts..."
if [ ! -f network/genesis.json ] || [ -z "${VENDOR_PRIVATE_KEY:-}" ] || [ -z "${SECURITY_PRIVATE_KEY:-}" ] || [ -z "${REGULATOR_PRIVATE_KEY:-}" ] || [ -z "${OPERATOR_PRIVATE_KEY:-}" ]; then
  echo "[run] Missing network artifacts or local demo keys; generating network (first run)"
  ./scripts/gen_besu_network.sh
  # shellcheck disable=SC1091
  source .env
fi

normalize_private_key() {
  case "$1" in
    0x*) echo "$1" ;;
    *) echo "0x$1" ;;
  esac
}

VENDOR_PRIVATE_KEY=$(normalize_private_key "$VENDOR_PRIVATE_KEY")
SECURITY_PRIVATE_KEY=$(normalize_private_key "$SECURITY_PRIVATE_KEY")
REGULATOR_PRIVATE_KEY=$(normalize_private_key "$REGULATOR_PRIVATE_KEY")
OPERATOR_PRIVATE_KEY=$(normalize_private_key "$OPERATOR_PRIVATE_KEY")

# Ensure output dirs (clean run for reproducibility)
mkdir -p out artifacts ipfs/data
rm -rf out/*

# Bring stack up
echo "[run] Starting docker stack"
docker compose up -d

# Wait for Besu JSON-RPC
echo "[run] Waiting for Besu RPC on http://localhost:8545"
for i in $(seq 1 60); do
  if curl -s -X POST http://localhost:8545 \
      -H 'Content-Type: application/json' \
      --data '{"jsonrpc":"2.0","method":"web3_clientVersion","params":[],"id":1}' \
    | grep -q "result"; then
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "[run] ERROR: Besu RPC did not become ready" >&2
    exit 1
  fi
done

# Wait for IPFS API
echo "[run] Waiting for IPFS API on http://localhost:5001"
for i in $(seq 1 60); do
  if curl -s -X POST "http://localhost:5001/api/v0/version" | grep -q "Version"; then
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "[run] ERROR: IPFS API did not become ready" >&2
    exit 1
  fi
done

# Helper: current time in milliseconds (portable: uses perl on macOS/Linux)
now_ms() {
  perl -MTime::HiRes=time -e 'printf("%.0f\n", time()*1000)'
}

# Helper: sha256(file) -> hex (portable: Linux sha256sum, macOS shasum, or openssl)
sha256_file() {
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$f" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$f" | awk '{print $1}'
  else
    openssl dgst -sha256 "$f" | awk '{print $2}'
  fi
}

RPC_URL_DOCKER="http://besu-node1:8545"

deployed_address_from_json() {
  local raw_output="$1"
  local create_json
  local addr from nonce nonce_dec

  addr=$(printf "%s\n" "$raw_output" | awk '/Deployed to:/ { print $3; exit }')
  if [ -n "$addr" ]; then
    echo "$addr"
    return
  fi

  create_json=$(printf "%s\n" "$raw_output" | awk 'BEGIN { json=0 } /^\{/ { json=1 } json { print }')

  addr=$(echo "$create_json" | jq -r '.deployedTo // .deployed_to // .contractAddress // .receipt.contractAddress // empty')
  if [ -n "$addr" ] && [ "$addr" != "null" ]; then
    echo "$addr"
    return
  fi

  from=$(echo "$create_json" | jq -r '.transaction.from')
  nonce=$(echo "$create_json" | jq -r '.transaction.nonce')
  nonce_dec=$((nonce))
  docker compose run --rm foundry "cast compute-address $from --nonce $nonce_dec" | awk '/Computed Address:/ {print $3}'
}

tx_hash_from_output() {
  awk '{
    line = $0
    while (match(line, /0x[0-9a-fA-F]{64}/)) {
      hash = substr(line, RSTART, RLENGTH)
      line = substr(line, RSTART + RLENGTH)
    }
  } END { print hash }'
}

json_escape() {
  jq -Rs .
}

# Compute addresses from private keys (inside foundry container for correctness)
VENDOR_ADDR=$(docker compose run --rm foundry "cast wallet address --private-key $VENDOR_PRIVATE_KEY")
SECURITY_ADDR=$(docker compose run --rm foundry "cast wallet address --private-key $SECURITY_PRIVATE_KEY")
REGULATOR_ADDR=$(docker compose run --rm foundry "cast wallet address --private-key $REGULATOR_PRIVATE_KEY")
OPERATOR_ADDR=$(docker compose run --rm foundry "cast wallet address --private-key $OPERATOR_PRIVATE_KEY")

echo "[run] Vendor     : $VENDOR_ADDR"
echo "[run] Security   : $SECURITY_ADDR"
echo "[run] Regulator  : $REGULATOR_ADDR"
echo "[run] Operator   : $OPERATOR_ADDR"

# Fund operator from vendor if needed
echo "[run] Funding operator account (1 ether)"
docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY --value 1ether $OPERATOR_ADDR" >/dev/null

# Deploy contracts
METRICS_JSON=out/metrics.json
RELEASE_META=out/release_metadata.json

T_START=$(now_ms)

echo "[run] Deploying contracts with Foundry (forge)"
KM_JSON=$(docker compose run --rm foundry "forge create --broadcast --legacy --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY src/KeyManager.sol:KeyManager --json")
KM_ADDR=$(deployed_address_from_json "$KM_JSON")
echo "[run] KeyManager        : $KM_ADDR"

FR_JSON=$(docker compose run --rm foundry "forge create --broadcast --legacy --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY src/FirmwareRegistry.sol:FirmwareRegistry --constructor-args $KM_ADDR --json")
FR_ADDR=$(deployed_address_from_json "$FR_JSON")
echo "[run] FirmwareRegistry  : $FR_ADDR"

RC_JSON=$(docker compose run --rm foundry "forge create --broadcast --legacy --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY src/RolloutCoordinator.sol:RolloutCoordinator --constructor-args $KM_ADDR $FR_ADDR --json")
RC_ADDR=$(deployed_address_from_json "$RC_JSON")
echo "[run] RolloutCoordinator: $RC_ADDR"

DA_JSON=$(docker compose run --rm foundry "forge create --broadcast --legacy --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY src/DeviceAttestation.sol:DeviceAttestation --constructor-args $KM_ADDR --json")
DA_ADDR=$(deployed_address_from_json "$DA_JSON")

echo "[run] DeviceAttestation : $DA_ADDR"

# Configure KeyManager: signers + policy
# Policy: require any 2 of {Vendor, Security, Regulator} for deviceType
# Role bits: Role enum in KeyManager is NONE=0,VENDOR=1,SECURITY=2,REGULATOR=3,OPERATOR=4,...
# mask = (1<<1)|(1<<2)|(1<<3) = 0b1110 = 14
REQUIRED_MASK=14
THRESHOLD=2

echo "[run] Configuring KeyManager signers and policy"
docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $KM_ADDR 'setSigner(address,uint8,bool)' $VENDOR_ADDR 1 true" >/dev/null
docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $KM_ADDR 'setSigner(address,uint8,bool)' $SECURITY_ADDR 2 true" >/dev/null
docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $KM_ADDR 'setSigner(address,uint8,bool)' $REGULATOR_ADDR 3 true" >/dev/null
docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $KM_ADDR 'setSigner(address,uint8,bool)' $OPERATOR_ADDR 4 true" >/dev/null
docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $KM_ADDR 'setPolicy(bytes32,uint8,uint8)' $DEVICE_TYPE_BYTES32 $REQUIRED_MASK $THRESHOLD" >/dev/null

# Transfer KeyManager ownership to the operator to model multi-stakeholder governance
# (owner is distinct from the vendor signer to make revocation meaningful in adversarial tests).
echo "[run] Transferring KeyManager ownership to operator (governance owner)"
docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $KM_ADDR 'transferOwnership(address)' $OPERATOR_ADDR" >/dev/null

# Create a deterministic demo firmware package
VERSION=1
RELEASE_DIR="artifacts/release_v${VERSION}"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# Generate firmware.bin deterministically (no host Python required)
# Uses AES-256-CTR keystream over a zero stream with a fixed key/iv.
FIRMWARE_SIZE_KIB=512
OPENSSL_KEY_HEX=000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
OPENSSL_IV_HEX=000102030405060708090a0b0c0d0e0f

dd if=/dev/zero bs=1024 count=$FIRMWARE_SIZE_KIB 2>/dev/null \
  | openssl enc -aes-256-ctr -K "$OPENSSL_KEY_HEX" -iv "$OPENSSL_IV_HEX" -nopad -nosalt \
  > "$RELEASE_DIR/firmware.bin"

# Minimal SBOM + provenance placeholders (hash-anchored on-chain)
cat > "$RELEASE_DIR/sbom.json" <<'JSON'
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "version": 1,
  "metadata": {
    "component": {
      "type": "firmware",
      "name": "ledgerguard-demo",
      "version": "1.0.0"
    }
  },
  "components": []
}
JSON

FIRMWARE_BIN_SHA256=$(sha256_file "$RELEASE_DIR/firmware.bin")

cat > "$RELEASE_DIR/provenance.json" <<JSON
{
  "statementType": "https://in-toto.io/Statement/v1",
  "subject": [{"name": "firmware.bin", "digest": {"sha256": "${FIRMWARE_BIN_SHA256}"}}],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {"builder": {"id": "ledgerguard-poc"}, "buildType": "demo"}
}
JSON

cat > "$RELEASE_DIR/manifest.json" <<JSON
{
  "deviceType": "$DEVICE_TYPE_STR",
  "version": $VERSION,
  "package": "firmware.tar",
  "hashes": {
    "firmware.bin.sha256": "${FIRMWARE_BIN_SHA256}",
    "sbom.json.sha256": "$(sha256_file "$RELEASE_DIR/sbom.json")",
    "provenance.json.sha256": "$(sha256_file "$RELEASE_DIR/provenance.json")"
  }
}
JSON

# Tar the package (PoC: no compression)
TARBALL="artifacts/firmware_v${VERSION}.tar"
tar -C "$RELEASE_DIR" -cf "$TARBALL" firmware.bin manifest.json sbom.json provenance.json

SIZE_BYTES=$(wc -c < "$TARBALL" | tr -d ' ')
SHA256_HEX=$(sha256_file "$TARBALL")
SBOM_HASH_HEX=$(sha256_file "$RELEASE_DIR/sbom.json")
PROV_HASH_HEX=$(sha256_file "$RELEASE_DIR/provenance.json")

echo "[run] Artifact tarball: $TARBALL ($SIZE_BYTES bytes)"
echo "[run] sha256         : $SHA256_HEX"

# Add to IPFS (from inside ipfs container). The /export mount is read-only, so we add the tarball path.
CID=$(docker compose exec -T ipfs ipfs add -Q "/export/firmware_v${VERSION}.tar")
echo "[run] IPFS CID        : $CID"

# Register + approvals
RELEASE_ID=$(docker compose run --rm foundry "cast call --rpc-url $RPC_URL_DOCKER $FR_ADDR 'nextReleaseId()(uint256)'")
# cast call outputs decimal by default for uint256; normalize to first whitespace-delimited token.
RELEASE_ID=$(echo "$RELEASE_ID" | awk '{print $1}')

echo "[run] Registering releaseId=$RELEASE_ID"
T_REGISTER=$(now_ms)
TX_REGISTER=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $VENDOR_PRIVATE_KEY $FR_ADDR 'registerRelease(bytes32,uint64,string,bytes32,uint32,bytes32,bytes32,uint32,uint64)' $DEVICE_TYPE_BYTES32 $VERSION $CID 0x$SHA256_HEX $SIZE_BYTES 0x$SBOM_HASH_HEX 0x$PROV_HASH_HEX 0 0" | tx_hash_from_output)
T_REGISTER_END=$(now_ms)

# Approvals (threshold=2): security + regulator
T_SEC_APPROVE=$(now_ms)
TX_SEC_APPROVE=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $SECURITY_PRIVATE_KEY $FR_ADDR 'approveRelease(uint256)' $RELEASE_ID" | tx_hash_from_output)
T_SEC_APPROVE_END=$(now_ms)

T_REG_APPROVE=$(now_ms)
TX_REG_APPROVE=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $REGULATOR_PRIVATE_KEY $FR_ADDR 'approveRelease(uint256)' $RELEASE_ID" | tx_hash_from_output)
T_REG_APPROVE_END=$(now_ms)

T_FINAL_APPROVAL=$T_REG_APPROVE_END

# Start rollout (1% canary, 10% batch)
T_ROLLOUT_STARTED=$(now_ms)
TX_ROLLOUT_STARTED=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $RC_ADDR 'startRollout(uint256,uint8,uint8)' $RELEASE_ID 1 10" | tx_hash_from_output)
T_ROLLOUT_STARTED_END=$(now_ms)

# Write metadata file consumed by simulator
cat > "$RELEASE_META" <<JSON
{
  "release_id": $RELEASE_ID,
  "device_type_bytes32": "$DEVICE_TYPE_BYTES32",
  "device_type_str": "$DEVICE_TYPE_STR",
  "version": $VERSION,
  "cid": "$CID",
  "sha256_hex": "$SHA256_HEX",
  "size_bytes": $SIZE_BYTES,
  "sbom_hash": "0x$SBOM_HASH_HEX",
  "prov_hash": "0x$PROV_HASH_HEX",
  "contracts": {
    "keyManager": "$KM_ADDR",
    "registry": "$FR_ADDR",
    "rollout": "$RC_ADDR",
    "attestation": "$DA_ADDR"
  }
}
JSON

# Epoch 1: canary 1%
echo "[run] Simulating epoch 1 (canary 1%)"
E1=$(docker compose run --rm sim "python simulate_devices.py --epoch 1 --devices $FLEET_SIZE --rollout 1 --fail-rate 0.02 --seed 1337 --ipfs http://ipfs:8080 --meta /out/release_metadata.json")
ROOT1=$(jq -r '.merkle_root' out/outcomes_epoch_1.json)
S1=$(jq -r '.success' out/outcomes_epoch_1.json)
F1=$(jq -r '.fail' out/outcomes_epoch_1.json)
R1=$(jq -r '.rollback' out/outcomes_epoch_1.json)
T_OUTCOME_1_START=$(now_ms)
TX_OUTCOME_1=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $DA_ADDR 'submitOutcomeRoot(uint256,uint32,bytes32,uint32,uint32,uint32)' $RELEASE_ID 1 $ROOT1 $S1 $F1 $R1" | tx_hash_from_output)
T_OUTCOME_1_END=$(now_ms)

# Verify low-success rollout advancement is blocked by the contract before the real promotion.
set +e
LOW_SUCCESS_ADVANCE_OUT=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $RC_ADDR 'advanceWithMetrics(uint256,uint32,uint32,uint32)' $RELEASE_ID 10 90 0" 2>&1)
LOW_SUCCESS_ADVANCE_RC=$?
set -e
LOW_SUCCESS_ADVANCE_REVERT=$(printf "%s" "$LOW_SUCCESS_ADVANCE_OUT" | tr '\n\r' ' ' | sed 's/"/'\''/g')
LOW_SUCCESS_ADVANCE_TX=$(printf "%s\n" "$LOW_SUCCESS_ADVANCE_OUT" | tx_hash_from_output)
if printf "%s" "$LOW_SUCCESS_ADVANCE_OUT" | grep -Eq 'status[[:space:]]+0[[:space:]]+[(]failed[)]|status[[:space:]]+0$'; then
  LOW_SUCCESS_ADVANCE_BLOCKED=true
  LOW_SUCCESS_ADVANCE_STATUS="failed"
elif [ "$LOW_SUCCESS_ADVANCE_RC" -ne 0 ]; then
  LOW_SUCCESS_ADVANCE_BLOCKED=true
  LOW_SUCCESS_ADVANCE_STATUS="reverted"
else
  LOW_SUCCESS_ADVANCE_BLOCKED=false
  LOW_SUCCESS_ADVANCE_STATUS="succeeded"
fi

# Advance to batch
echo "[run] Advancing rollout to BATCH"
T_ADVANCE_1_START=$(now_ms)
TX_ADVANCE_1=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $RC_ADDR 'advanceWithMetrics(uint256,uint32,uint32,uint32)' $RELEASE_ID $S1 $F1 $R1" | tx_hash_from_output)
T_ADVANCE_1_END=$(now_ms)

# Epoch 2: batch 10%
echo "[run] Simulating epoch 2 (batch 10%)"
E2=$(docker compose run --rm sim "python simulate_devices.py --epoch 2 --devices $FLEET_SIZE --rollout 10 --fail-rate 0.02 --seed 1337 --ipfs http://ipfs:8080 --meta /out/release_metadata.json")
ROOT2=$(jq -r '.merkle_root' out/outcomes_epoch_2.json)
S2=$(jq -r '.success' out/outcomes_epoch_2.json)
F2=$(jq -r '.fail' out/outcomes_epoch_2.json)
R2=$(jq -r '.rollback' out/outcomes_epoch_2.json)
T_OUTCOME_2_START=$(now_ms)
TX_OUTCOME_2=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $DA_ADDR 'submitOutcomeRoot(uint256,uint32,bytes32,uint32,uint32,uint32)' $RELEASE_ID 2 $ROOT2 $S2 $F2 $R2" | tx_hash_from_output)
T_OUTCOME_2_END=$(now_ms)

# Advance to global
echo "[run] Advancing rollout to GLOBAL"
T_ADVANCE_2_START=$(now_ms)
TX_ADVANCE_2=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $RC_ADDR 'advanceWithMetrics(uint256,uint32,uint32,uint32)' $RELEASE_ID $S2 $F2 $R2" | tx_hash_from_output)
T_ADVANCE_2_END=$(now_ms)

# Epoch 3: global 100%
echo "[run] Simulating epoch 3 (global 100%)"
E3=$(docker compose run --rm sim "python simulate_devices.py --epoch 3 --devices $FLEET_SIZE --rollout 100 --fail-rate 0.02 --seed 1337 --ipfs http://ipfs:8080 --meta /out/release_metadata.json")
ROOT3=$(jq -r '.merkle_root' out/outcomes_epoch_3.json)
S3=$(jq -r '.success' out/outcomes_epoch_3.json)
F3=$(jq -r '.fail' out/outcomes_epoch_3.json)
R3=$(jq -r '.rollback' out/outcomes_epoch_3.json)
T_OUTCOME_3_START=$(now_ms)
TX_OUTCOME_3=$(docker compose run --rm foundry "cast send --legacy --gas-limit 3000000 --rpc-url $RPC_URL_DOCKER --private-key $OPERATOR_PRIVATE_KEY $DA_ADDR 'submitOutcomeRoot(uint256,uint32,bytes32,uint32,uint32,uint32)' $RELEASE_ID 3 $ROOT3 $S3 $F3 $R3" | tx_hash_from_output)
T_OUTCOME_3_END=$(now_ms)

T_END=$(now_ms)

# Persist metrics
cat > "$METRICS_JSON" <<JSON
{
  "t_start_ms": $T_START,
  "t_end_ms": $T_END,
  "t_register_ms": $T_REGISTER,
  "t_register_end_ms": $T_REGISTER_END,
  "t_security_approve_ms": $T_SEC_APPROVE,
  "t_security_approve_end_ms": $T_SEC_APPROVE_END,
  "t_regulator_approve_ms": $T_REG_APPROVE,
  "t_regulator_approve_end_ms": $T_REG_APPROVE_END,
  "t_final_approval_ms": $T_FINAL_APPROVAL,
  "t_rollout_started_ms": $T_ROLLOUT_STARTED,
  "t_rollout_started_end_ms": $T_ROLLOUT_STARTED_END,
  "tx_register": "${TX_REGISTER:-}",
  "tx_security_approve": "${TX_SEC_APPROVE:-}",
  "tx_regulator_approve": "${TX_REG_APPROVE:-}",
  "tx_rollout_started": "${TX_ROLLOUT_STARTED:-}",
  "rollout_policy": {
    "min_success_bps": 9500,
    "low_success_block_test": {
      "attempted_success": 10,
      "attempted_fail": 90,
      "attempted_rollback": 0,
      "total_reports": 100,
      "success_rate_bps": 1000,
      "min_success_bps": 9500,
      "tx_hash": "${LOW_SUCCESS_ADVANCE_TX:-}",
      "tx_status": "$LOW_SUCCESS_ADVANCE_STATUS",
      "blocked": $LOW_SUCCESS_ADVANCE_BLOCKED,
      "return_code": $LOW_SUCCESS_ADVANCE_RC,
      "evidence": $(printf "%s" "$LOW_SUCCESS_ADVANCE_REVERT" | json_escape)
    },
    "advance_to_batch": {"tx_hash": "${TX_ADVANCE_1:-}", "t_submit_start_ms": $T_ADVANCE_1_START, "t_submit_end_ms": $T_ADVANCE_1_END, "success": $S1, "fail": $F1, "rollback": $R1},
    "advance_to_global": {"tx_hash": "${TX_ADVANCE_2:-}", "t_submit_start_ms": $T_ADVANCE_2_START, "t_submit_end_ms": $T_ADVANCE_2_END, "success": $S2, "fail": $F2, "rollback": $R2}
  },
  "release_id": $RELEASE_ID,
  "device_type": "$DEVICE_TYPE_STR",
  "fleet_size": $FLEET_SIZE,
  "cid": "$CID",
  "sha256_hex": "$SHA256_HEX",
  "contracts": {
    "keyManager": "$KM_ADDR",
    "registry": "$FR_ADDR",
    "rollout": "$RC_ADDR",
    "attestation": "$DA_ADDR"
  },
  "epochs": [
    {"epoch": 1, "merkle_root": "$ROOT1", "tx_outcome": "${TX_OUTCOME_1:-}", "t_submit_start_ms": $T_OUTCOME_1_START, "t_submit_end_ms": $T_OUTCOME_1_END},
    {"epoch": 2, "merkle_root": "$ROOT2", "tx_outcome": "${TX_OUTCOME_2:-}", "t_submit_start_ms": $T_OUTCOME_2_START, "t_submit_end_ms": $T_OUTCOME_2_END},
    {"epoch": 3, "merkle_root": "$ROOT3", "tx_outcome": "${TX_OUTCOME_3:-}", "t_submit_start_ms": $T_OUTCOME_3_START, "t_submit_end_ms": $T_OUTCOME_3_END}
  ],
  "notes": "PoC run_experiment.sh generated these metrics using wall-clock time on the orchestrator host."
}
JSON

echo "[run] Wrote $METRICS_JSON"
echo "[run] Wrote $RELEASE_META"

if [ "$ADVERSARIAL" -eq 1 ]; then
  echo "[run] Running adversarial validation suite"
  ./scripts/run_adversarial.sh
fi

echo "[run] Done. Next: ./poc results"
