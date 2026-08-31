#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

need_cmd() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[doctor] Missing required command: $cmd" >&2
    echo "[doctor] $hint" >&2
    exit 1
  fi
}

need_cmd docker "Install/start Docker Desktop and ensure the Docker CLI is on PATH."
need_cmd jq "Install jq (e.g., brew install jq)."
need_cmd curl "curl is required for readiness checks and HTTP validation."
need_cmd perl "perl is required for portable millisecond timestamps."
need_cmd tar "tar is required to assemble the firmware bundle."
need_cmd openssl "openssl is required for deterministic firmware generation and sha256 fallbacks."

if ! docker info >/dev/null 2>&1; then
  echo "[doctor] Docker daemon is not reachable." >&2
  echo "[doctor] Start Docker Desktop, wait for 'Docker Engine running', then retry." >&2
  echo "[doctor] If Docker Desktop is already running, try: docker context use desktop-linux" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[doctor] Docker Compose v2 is required (docker compose ...)." >&2
  exit 1
fi


arch=$(uname -m 2>/dev/null || echo unknown)
if [ "$arch" = "arm64" ] || [ "$arch" = "aarch64" ]; then
  echo "[doctor] Host architecture: $arch (Apple Silicon / ARM64 path)"
fi
echo "[doctor] OK: docker daemon reachable and required host tools present"
