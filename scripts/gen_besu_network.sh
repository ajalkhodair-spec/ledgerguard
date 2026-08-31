#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

# Ensure .env exists
if [ ! -f .env ]; then
  cp .env.example .env
fi
# shellcheck disable=SC1091
source .env

BESU_IMAGE=${BESU_IMAGE:-hyperledger/besu:25.12.0}
FOUNDRY_IMAGE=${FOUNDRY_IMAGE:-ghcr.io/foundry-rs/foundry:latest}
NODE_COUNT=${BESU_NODE_COUNT:-4}
BLOCK_PERIOD_SECONDS=${BLOCK_PERIOD_SECONDS:-2}

mkdir -p network

env_set() {
  local key="$1"
  local value="$2"
  local tmpfile
  tmpfile="$(mktemp)"
  awk -v key="$key" -v value="$value" '
    BEGIN { done=0 }
    $0 ~ "^" key "=" { print key "=" value; done=1; next }
    { print }
    END { if (!done) print key "=" value }
  ' .env > "$tmpfile"
  mv "$tmpfile" .env
}

ensure_private_key() {
  local key_name="$1"
  local current="${!key_name:-}"
  case "$current" in
    ""|changeme|CHANGE_ME|"<generate-on-first-run>")
      current="$(openssl rand -hex 32)"
      env_set "$key_name" "$current"
      export "$key_name=$current"
      echo "[gen] Generated local demo key: $key_name"
      ;;
  esac
}

address_for_key() {
  local private_key="$1"
  case "$private_key" in
    0x*) ;;
    *) private_key="0x${private_key}" ;;
  esac
  docker run --rm --entrypoint sh "$FOUNDRY_IMAGE" -lc \
    "cast wallet address --private-key '$private_key'" \
    | tr -d '\r'
}

ensure_private_key VENDOR_PRIVATE_KEY
ensure_private_key SECURITY_PRIVATE_KEY
ensure_private_key REGULATOR_PRIVATE_KEY
ensure_private_key OPERATOR_PRIVATE_KEY
ensure_private_key AUDITOR_PRIVATE_KEY

VENDOR_ADDR=$(address_for_key "$VENDOR_PRIVATE_KEY")
SECURITY_ADDR=$(address_for_key "$SECURITY_PRIVATE_KEY")
REGULATOR_ADDR=$(address_for_key "$REGULATOR_PRIVATE_KEY")
VENDOR_ALLOC=${VENDOR_ADDR#0x}
SECURITY_ALLOC=${SECURITY_ADDR#0x}
REGULATOR_ALLOC=${REGULATOR_ADDR#0x}

# Build an IBFT2 config file based on the Besu docs tutorial, with deterministic demo accounts.
# See: https://besu.hyperledger.org/private-networks/tutorials/ibft
cat > network/ibftConfigFile.json <<JSON
{
  "genesis": {
    "config": {
      "chainId": 1337,
      "berlinBlock": 0,
      "ibft2": {
        "blockperiodseconds": ${BLOCK_PERIOD_SECONDS},
        "epochlength": 30000,
        "requesttimeoutseconds": 4
      }
    },
    "nonce": "0x0",
    "timestamp": "0x58ee40ba",
    "gasLimit": "0x47b760",
    "difficulty": "0x1",
    "mixHash": "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365",
    "coinbase": "0x0000000000000000000000000000000000000000",
    "alloc": {
      "${VENDOR_ALLOC}": {
        "privateKey": "${VENDOR_PRIVATE_KEY}",
        "comment": "Generated local demo key: vendor/deployer (do not use in production)",
        "balance": "0xad78ebc5ac6200000"
      },
      "${SECURITY_ALLOC}": {
        "privateKey": "${SECURITY_PRIVATE_KEY}",
        "comment": "Generated local demo key: security signer (do not use in production)",
        "balance": "90000000000000000000000"
      },
      "${REGULATOR_ALLOC}": {
        "privateKey": "${REGULATOR_PRIVATE_KEY}",
        "comment": "Generated local demo key: regulator signer (do not use in production)",
        "balance": "90000000000000000000000"
      }
    }
  },
  "blockchain": {
    "nodes": {
      "generate": true,
      "count": ${NODE_COUNT}
    }
  }
}
JSON

# Clean previous generated files (if any)
rm -rf network/networkFiles network/Node-1 network/Node-2 network/Node-3 network/Node-4 network/genesis.json || true

echo "[gen] Generating IBFT2 genesis + node keys using ${BESU_IMAGE} (nodes=${NODE_COUNT})"

set +e
docker run --rm \
  -v "$ROOT_DIR/network":/work \
  -w /work \
  "$BESU_IMAGE" \
  operator generate-blockchain-config \
  --config-file=ibftConfigFile.json \
  --to=networkFiles \
  --private-key-file-name=key
gen_status=$?
set -e

if [ "$gen_status" -ne 0 ]; then
  if [ -f network/networkFiles/genesis.json ] && [ -d network/networkFiles/keys ]; then
    echo "[gen] Besu returned status $gen_status after producing network files; continuing"
  else
    echo "[gen] ERROR: Besu network generation failed" >&2
    exit "$gen_status"
  fi
fi

cp network/networkFiles/genesis.json network/genesis.json

# Copy node keys to deterministic Node-X directories expected by docker-compose.yml
KEY_DIRS=(network/networkFiles/keys/*)
if [ ${#KEY_DIRS[@]} -lt "$NODE_COUNT" ]; then
  echo "[gen] ERROR: expected $NODE_COUNT key directories, found ${#KEY_DIRS[@]}" >&2
  exit 1
fi

for i in $(seq 1 "$NODE_COUNT"); do
  mkdir -p "network/Node-${i}/data"
  src_dir="${KEY_DIRS[$((i-1))]}"
  cp "$src_dir/key" "network/Node-${i}/data/key"
  cp "$src_dir/key.pub" "network/Node-${i}/data/key.pub"
  echo "[gen] Node-$i key source: $src_dir"
done

# Compute bootnode enode for node1 (used by nodes 2..N).
BOOT_PUBKEY=$(cat network/Node-1/data/key.pub | tr -d '\n\r')
# Some Besu builds may prefix key.pub with 0x; strip to be safe for enode formatting.
BOOT_PUBKEY=${BOOT_PUBKEY#0x}
BOOTNODE_ENODE="enode://${BOOT_PUBKEY}@172.28.0.11:30303"

echo "[gen] Bootnode enode: ${BOOTNODE_ENODE}"

env_set "BOOTNODE_ENODE" "$BOOTNODE_ENODE"

echo "[gen] Wrote .env with BOOTNODE_ENODE"
